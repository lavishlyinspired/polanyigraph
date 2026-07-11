"""Tests for backend/agents/skill_store.py -- runtime skill loading for the
LangGraph agent (PLAN.md §2.9/§13.2). Distinct from .claude/skills/ (dev-time,
guides the coding agent building this codebase): these live in
backend/skills/ and are loaded by the agent itself at inference time,
Discovery (cheap, frontmatter only) -> Activation (full content on demand).
"""

from __future__ import annotations

from agents import skill_store


def test_scan_discovers_kg_extraction_skill_metadata_only():
    skills = skill_store.scan()

    names = {s.name for s in skills}
    assert "kg-extraction" in names
    kg_extraction = next(s for s in skills if s.name == "kg-extraction")
    assert "extract" in kg_extraction.description.lower()
    # Discovery is metadata-only -- shouldn't carry the full SKILL.md body.
    assert "Prefer precision over recall" not in kg_extraction.description


def test_load_returns_full_skill_content():
    content = skill_store.load("kg-extraction")

    assert "Prefer precision over recall" in content
    assert "confidence honestly" in content.lower()


def test_load_raises_for_unknown_skill():
    import pytest

    with pytest.raises(FileNotFoundError):
        skill_store.load("not-a-real-skill")
