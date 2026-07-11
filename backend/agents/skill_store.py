"""Runtime skill loading for the LangGraph agent (PLAN.md §2.9/§13.2).

Distinct from `.claude/skills/` (dev-time -- guides the coding agent that
builds this codebase). These live in `backend/skills/` and are loaded by the
agent *itself* at inference time via load_skill(), following the
Discovery (cheap, frontmatter only) -> Activation (full content on demand) ->
Execution (LLM follows the loaded instructions) pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Minimal frontmatter parser for the flat `key: value` shape used by
    every SKILL.md in this project -- no YAML dependency needed."""
    if not text.startswith("---"):
        return {}
    _, frontmatter, _ = text.split("---", 2)
    fields: dict[str, str] = {}
    current_key: str | None = None
    for line in frontmatter.splitlines():
        if not line.strip():
            continue
        if line.startswith((" ", "\t")) and current_key:
            fields[current_key] += " " + line.strip()
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            current_key = key.strip()
            fields[current_key] = value.strip()
    return fields


def scan() -> list[SkillMetadata]:
    """Discovery: parses only the YAML frontmatter of every backend/skills/*/
    SKILL.md, not the full body -- cheap enough to run on every agent turn."""
    skills = []
    if not SKILLS_DIR.is_dir():
        return skills
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        fields = _parse_frontmatter(skill_file.read_text())
        if "name" in fields and "description" in fields:
            skills.append(SkillMetadata(name=fields["name"], description=fields["description"]))
    return skills


def load(name: str) -> str:
    """Activation: the full SKILL.md body content for the LLM to follow."""
    skill_file = SKILLS_DIR / name / "SKILL.md"
    if not skill_file.is_file():
        raise FileNotFoundError(f"No runtime skill named '{name}' in {SKILLS_DIR}")
    return skill_file.read_text()
