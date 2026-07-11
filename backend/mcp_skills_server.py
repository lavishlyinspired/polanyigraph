"""MCP server (PLAN.md §10 MCP Layer, 4th and last of the 4
originally-sketched servers): load_skill, list_skills, activate_skill --
wrapping agents/skill_store.py's real Discovery/Activation and the new
services/skill_activation_store.py for a real, persisted "active" state
(skills were previously loaded fresh per-call with no such concept). Same
FastMCP pattern as mcp_server.py.

Run: `python mcp_skills_server.py` (stdio transport).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from agents import skill_store
from app.dependencies import get_neo4j
from services import skill_activation_store

mcp = FastMCP("neurosymbolic-skills")


@mcp.tool()
def list_skills() -> str:
    """List every real runtime skill discovered under backend/skills/, each
    with its description and whether it is currently active."""
    active = skill_activation_store.list_active_skills(get_neo4j())
    metas = skill_store.scan()
    if not metas:
        return "No runtime skills found."
    lines = []
    for m in metas:
        status = "[active]" if m.name in active else "[inactive]"
        lines.append(f"- {m.name} {status}: {m.description}")
    return "\n".join(lines)


@mcp.tool()
def load_skill(name: str) -> str:
    """Load the full content of a real runtime skill by name, for the
    calling agent/LLM to follow. Returns an error message if the skill
    doesn't exist."""
    try:
        return skill_store.load(name)
    except FileNotFoundError as e:
        return str(e)


@mcp.tool()
def activate_skill(name: str) -> str:
    """Mark a real runtime skill as active, persisted in Neo4j -- a real,
    observable state change (services/skill_activation_store.py), not a
    no-op. Rejects unknown skill names without persisting anything."""
    known_names = {m.name for m in skill_store.scan()}
    if name not in known_names:
        return f"No runtime skill named '{name}' in {skill_store.SKILLS_DIR}"
    skill_activation_store.activate_skill(get_neo4j(), name=name)
    return f"Activated skill '{name}'."


if __name__ == "__main__":
    mcp.run()
