"""MCP server (PLAN.md §10 MCP Layer, 4th and last of the 4
originally-sketched servers): load_skill, list_skills, activate_skill --
wrapping agents/skill_store.py's real Discovery/Activation and the new
services/skill_activation_store.py for a real, persisted "active" state
(skills were previously loaded fresh per-call with no such concept). Same
FastMCP pattern as mcp_server.py.

Also exposes the Neo4j skill graph (PLAN.md §18/§2.9.14) -- find_relevant_skills
and record_skill_usage -- as tools on this same server rather than a parallel
MCP surface, per §18.3's stated phase placement.

Run: `python mcp_skills_server.py` (stdio transport).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from agents import skill_store
from app.dependencies import get_neo4j
from services import skill_activation_store, skill_graph_service

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


@mcp.tool()
def find_relevant_skills(task_description: str, domain: str | None = None, limit: int = 5) -> str:
    """Rank real runtime skills by relevance to a task description, using the
    Neo4j full-text skill graph (PLAN.md §18/§2.9.14) -- confidence-filtered,
    REQUIRES-aware, most-relevant first. Returns a plain-text list."""
    matches = skill_graph_service.find_relevant_skills(get_neo4j(), task_description, domain=domain, limit=limit)
    if not matches:
        return "No relevant skills found."
    lines = []
    for m in matches:
        requires = f" (requires: {', '.join(m.requires)})" if m.requires else ""
        lines.append(f"- {m.name} [confidence={m.confidence:.2f}, score={m.score:.2f}]{requires}: {m.description}")
    return "\n".join(lines)


@mcp.tool()
def record_skill_usage(
    skill_name: str, session_id: str, success: bool,
    accuracy: float | None = None, tokens_used: int | None = None, error: str | None = None,
) -> str:
    """Record a real skill-usage outcome in the Neo4j skill graph and update
    that skill's rolling-average confidence (PLAN.md §18.4 item 4)."""
    new_confidence = skill_graph_service.record_skill_usage(
        get_neo4j(), skill_name=skill_name, session_id=session_id, success=success,
        accuracy=accuracy, tokens_used=tokens_used, error=error,
    )
    return f"Recorded usage for '{skill_name}'; confidence now {new_confidence:.2f}."


if __name__ == "__main__":
    mcp.run()
