"""Tests for backend/mcp_server.py (PLAN.md §10 MCP Layer): exposes the same
real knowledge-graph operations as agents/tools.py to any MCP client. Real
Neo4j/GraphDB/LLM (module-level singletons via app.dependencies, same as the
FastAPI app) -- per this repo's convention, no mocking the store or the LLM
for the one true end-to-end test; registration/shape checks don't need a
live call.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from mcp_server import mcp


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
async def test_list_tools_exposes_the_4_real_kg_operations():
    tools = await mcp.list_tools()

    names = {t.name for t in tools}
    assert names == {"extract_entities", "run_reasoning", "run_enrichment", "query_graph"}
    for t in tools:
        assert t.description  # a real MCP client picks tools by description


@pytest.mark.asyncio
async def test_ontology_schema_resource_is_registered():
    resources = await mcp.list_resources()
    uris = {str(r.uri) for r in resources}
    assert "ontology://schema" in uris


@pytest.mark.asyncio
async def test_extract_entities_tool_writes_to_the_real_graph():
    """Real end-to-end: real Neo4j, real GraphDB, real LLM -- this is the one
    true integration proof; registration checks above don't need a live call."""
    from db.graphdb_client import GraphDBClient

    settings = get_settings()
    neo4j = Neo4jClient(settings)
    graphdb = GraphDBClient(settings)
    try:
        graphdb.verify()
    except Exception:
        pytest.skip("GraphDB not reachable")

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    try:
        content, _structured = await mcp.call_tool(
            "extract_entities", {"graph_id": graph_id, "text": "Deutsche Bank AG issued a bond."},
        )
        text = content[0].text
        assert "entities" in text.lower()

        from services import graph_service
        record = graph_service.get_graph(neo4j, graph_id)
        assert len(record.nodes) >= 1
    finally:
        neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
        neo4j.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=graph_id)
        neo4j.close()
        graphdb.close()
