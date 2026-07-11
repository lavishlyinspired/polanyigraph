"""Tests for backend/mcp_neo4j_server.py (PLAN.md §10 MCP Layer, 2nd of the
4 originally-sketched servers): direct Neo4j graph access (get_schema,
read_cypher, write_cypher) for any MCP client. Real Neo4j, hand-rolled
against this project's own Neo4jClient -- not an external package, per the
same convention as mcp_server.py.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from mcp_neo4j_server import mcp


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
async def test_list_tools_exposes_the_3_real_neo4j_operations():
    tools = await mcp.list_tools()

    names = {t.name for t in tools}
    assert names == {"get_schema", "read_cypher", "write_cypher"}
    for t in tools:
        assert t.description


@pytest.mark.asyncio
async def test_get_schema_reports_real_labels_and_relationship_types():
    from services import graph_service

    neo4j = Neo4jClient(get_settings())
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    graph_service.upsert_entity(
        neo4j, graph_id=graph_id, entity_id="e1", label="Acme Corp",
        type_="organization", source_doc="d", extraction_confidence=1.0,
    )
    try:
        content, _structured = await mcp.call_tool("get_schema", {})
        text = content[0].text
        assert "Entity" in text
    finally:
        neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
        neo4j.close()


@pytest.mark.asyncio
async def test_read_cypher_returns_real_rows_for_the_real_graph():
    from services import graph_service

    neo4j = Neo4jClient(get_settings())
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    graph_service.upsert_entity(
        neo4j, graph_id=graph_id, entity_id="e1", label="Deutsche Bank AG",
        type_="organization", source_doc="d", extraction_confidence=1.0,
    )
    try:
        content, _structured = await mcp.call_tool(
            "read_cypher",
            {"cypher": f"MATCH (e:Entity {{graphId: '{graph_id}'}}) RETURN e.label AS label"},
        )
        text = content[0].text
        assert "Deutsche Bank AG" in text
    finally:
        neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
        neo4j.close()


@pytest.mark.asyncio
async def test_read_cypher_rejects_write_clauses_without_executing_them():
    marker = f"mcp-guard-{uuid.uuid4().hex[:8]}"
    neo4j = Neo4jClient(get_settings())
    try:
        content, _structured = await mcp.call_tool(
            "read_cypher", {"cypher": f"CREATE (n:GuardTestNode {{marker: '{marker}'}}) RETURN n"},
        )
        text = content[0].text
        assert "read-only" in text.lower() or "not allowed" in text.lower()

        rows = neo4j.run("MATCH (n:GuardTestNode {marker: $m}) RETURN n", m=marker)
        assert rows == []  # the write never actually ran
    finally:
        neo4j.run("MATCH (n:GuardTestNode {marker: $m}) DETACH DELETE n", m=marker)
        neo4j.close()


@pytest.mark.asyncio
async def test_write_cypher_executes_a_real_write():
    marker = f"mcp-write-{uuid.uuid4().hex[:8]}"
    neo4j = Neo4jClient(get_settings())
    try:
        content, _structured = await mcp.call_tool(
            "write_cypher", {"cypher": f"CREATE (n:GuardTestNode {{marker: '{marker}'}}) RETURN n"},
        )
        text = content[0].text
        assert "1" in text  # 1 row created/returned

        rows = neo4j.run("MATCH (n:GuardTestNode {marker: $m}) RETURN n", m=marker)
        assert len(rows) == 1
    finally:
        neo4j.run("MATCH (n:GuardTestNode {marker: $m}) DETACH DELETE n", m=marker)
        neo4j.close()
