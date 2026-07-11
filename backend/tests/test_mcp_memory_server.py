"""Tests for backend/mcp_memory_server.py (PLAN.md §10 MCP Layer, 3rd of the
4 originally-sketched servers): search_memory (wraps services/memory_service.py)
and save_preference (wraps the new services/preferences_store.py) for any
MCP client. Real Neo4j, same FastMCP pattern as mcp_server.py.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from mcp_memory_server import mcp


@pytest.fixture(autouse=True)
def _skip_if_neo4j_unreachable():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    finally:
        client.close()


@pytest.mark.asyncio
async def test_list_tools_exposes_the_2_real_memory_operations():
    tools = await mcp.list_tools()

    names = {t.name for t in tools}
    assert names == {"search_memory", "save_preference"}
    for t in tools:
        assert t.description


@pytest.mark.asyncio
async def test_search_memory_finds_real_chat_history():
    from services import chat_history_service

    neo4j = Neo4jClient(get_settings())
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    chat_history_service.append_message(
        neo4j, graph_id=graph_id, session_id="s1", message_id="m1",
        role="user", content="Who regulates Credit Suisse?",
    )
    try:
        content, _structured = await mcp.call_tool(
            "search_memory", {"graph_id": graph_id, "query": "Credit Suisse"},
        )
        text = content[0].text
        assert "Credit Suisse" in text
    finally:
        neo4j.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=graph_id)
        neo4j.close()


@pytest.mark.asyncio
async def test_search_memory_reports_no_matches_found():
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    content, _structured = await mcp.call_tool(
        "search_memory", {"graph_id": graph_id, "query": "nonexistent-term"},
    )
    text = content[0].text
    assert "no" in text.lower()


@pytest.mark.asyncio
async def test_save_preference_persists_a_real_value():
    from services import preferences_store

    neo4j = Neo4jClient(get_settings())
    key = f"test-pref-{uuid.uuid4().hex[:8]}"
    try:
        content, _structured = await mcp.call_tool(
            "save_preference", {"key": key, "value": "dark-mode"},
        )
        assert "saved" in content[0].text.lower()

        assert preferences_store.get_preference(neo4j, key=key) == "dark-mode"
    finally:
        preferences_store.delete_preference(neo4j, key=key)
        neo4j.close()
