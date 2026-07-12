"""Tests for backend/mcp_skills_server.py (PLAN.md §10 MCP Layer, 4th and
last of the originally-sketched servers): load_skill, list_skills,
activate_skill wrapping agents/skill_store.py + the new real
services/skill_activation_store.py, for any MCP client.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from mcp_skills_server import mcp


@pytest.fixture(autouse=True)
def _skip_if_neo4j_unreachable():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    finally:
        client.close()


@pytest.fixture(autouse=True)
def _cleanup_activation():
    yield
    client = Neo4jClient(get_settings())
    client.run("MATCH (s:ActiveSkill {name: 'kg-extraction'}) DETACH DELETE s")
    client.close()


@pytest.mark.asyncio
async def test_list_tools_exposes_the_5_real_skills_operations():
    tools = await mcp.list_tools()

    names = {t.name for t in tools}
    assert names == {
        "load_skill", "list_skills", "activate_skill",
        "find_relevant_skills", "record_skill_usage",
    }
    for t in tools:
        assert t.description


@pytest.mark.asyncio
async def test_list_skills_reports_the_real_backend_skills_with_inactive_by_default():
    content, _structured = await mcp.call_tool("list_skills", {})
    text = content[0].text
    assert "kg-extraction" in text
    assert "inactive" in text.lower()


@pytest.mark.asyncio
async def test_load_skill_returns_the_real_skill_md_content():
    content, _structured = await mcp.call_tool("load_skill", {"name": "kg-extraction"})
    text = content[0].text
    assert len(text) > 0


@pytest.mark.asyncio
async def test_load_skill_reports_error_for_unknown_skill():
    content, _structured = await mcp.call_tool("load_skill", {"name": "no-such-skill"})
    text = content[0].text
    assert "no runtime skill" in text.lower() or "not found" in text.lower()


@pytest.mark.asyncio
async def test_activate_skill_persists_real_active_state_visible_in_list_skills():
    activate_content, _ = await mcp.call_tool("activate_skill", {"name": "kg-extraction"})
    assert "activated" in activate_content[0].text.lower()

    list_content, _ = await mcp.call_tool("list_skills", {})
    text = list_content[0].text
    assert "kg-extraction" in text
    assert "[active]" in text.lower()


@pytest.mark.asyncio
async def test_activate_skill_rejects_unknown_skill_name():
    content, _structured = await mcp.call_tool("activate_skill", {"name": "no-such-skill"})
    text = content[0].text
    assert "no runtime skill" in text.lower() or "not found" in text.lower()

    from services import skill_activation_store
    neo4j = Neo4jClient(get_settings())
    assert skill_activation_store.is_active(neo4j, name="no-such-skill") is False
    neo4j.close()
