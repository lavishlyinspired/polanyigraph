"""Tests for backend/agents/tools.py -- formal LangChain @tool registrations
(PLAN.md §11 Tool Layer) wrapping the same real, already-tested service
functions the agent graph nodes and REST endpoints use. Real Neo4j/GraphDB,
faked LLM per this repo's convention."""

from __future__ import annotations

import json
import uuid

import pytest

from agents.tools import build_tools
from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import graph_service


class FakeLLM:
    def __init__(self, extraction_payload: str, enrichment_payload: str | None = None) -> None:
        self._extraction_payload = extraction_payload
        self._enrichment_payload = enrichment_payload or '{"facts": []}'

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        if "information extraction engine" in system.lower():
            return self._extraction_payload
        return self._enrichment_payload


_PAYLOAD = json.dumps({
    "entities": [{"name": "Acme Corp", "type": "organization", "confidence": 0.9}],
    "relationships": [],
})


@pytest.fixture
def services():
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    graphdb = GraphDBClient(settings)
    try:
        neo4j.verify()
        graphdb.verify()
    except Exception:
        pytest.skip("Neo4j/GraphDB not reachable")
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    yield neo4j, graphdb, settings, graph_id
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.run("MATCH (f:DerivedFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    neo4j.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=graph_id)
    neo4j.run("MATCH (f:ImplicitFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    neo4j.close()
    graphdb.close()


def test_build_tools_returns_the_4_formal_tools(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)
    tools = build_tools(neo4j, graphdb, llm, settings)

    names = {t.name for t in tools}
    assert names == {"extract_entities", "run_reasoning", "run_enrichment", "query_graph"}
    for t in tools:
        assert t.description  # every tool needs a real description for an LLM to pick from


def test_extract_entities_tool_writes_to_the_real_graph(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)
    tools = build_tools(neo4j, graphdb, llm, settings)
    extract_entities = next(t for t in tools if t.name == "extract_entities")

    result = extract_entities.invoke({"graph_id": graph_id, "text": "Acme Corp filed a report."})

    assert "1 entities" in result or "1 entity" in result
    record = graph_service.get_graph(neo4j, graph_id)
    assert any(n.label == "Acme Corp" for n in record.nodes)


def test_run_reasoning_tool_on_empty_graph_reports_gracefully(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)
    tools = build_tools(neo4j, graphdb, llm, settings)
    run_reasoning = next(t for t in tools if t.name == "run_reasoning")

    result = run_reasoning.invoke({"graph_id": graph_id})

    assert "no entities" in result.lower()


def test_run_enrichment_tool_saves_pending_facts(services):
    neo4j, graphdb, settings, graph_id = services
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="e1", label="the match", type_="event", source_doc="d", extraction_confidence=1.0)
    enrichment_payload = json.dumps({"facts": [{"text": "an implicit fact", "anchors": ["e1"], "confidence": 0.7}]})
    llm = FakeLLM(_PAYLOAD, enrichment_payload=enrichment_payload)
    tools = build_tools(neo4j, graphdb, llm, settings)
    run_enrichment = next(t for t in tools if t.name == "run_enrichment")

    result = run_enrichment.invoke({"graph_id": graph_id, "text": "context"})

    assert "11" in result  # one candidate per heuristic
    from services import enrichment_service
    assert len(enrichment_service.list_pending_facts(neo4j, graph_id)) == 11


def test_query_graph_tool_runs_the_real_query_engine(services):
    neo4j, graphdb, settings, graph_id = services
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="e1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="e2", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="r1", source_id="e1", target_id="e2", type_="issues", weight=1.0)
    llm = FakeLLM(_PAYLOAD)
    tools = build_tools(neo4j, graphdb, llm, settings)
    query_graph = next(t for t in tools if t.name == "query_graph")

    result = query_graph.invoke({"graph_id": graph_id, "query": 'issues("Acme Corp", X)'})

    assert "Acme Preferred Stock" in result


def test_query_graph_tool_reports_no_results_plainly(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)
    tools = build_tools(neo4j, graphdb, llm, settings)
    query_graph = next(t for t in tools if t.name == "query_graph")

    result = query_graph.invoke({"graph_id": graph_id, "query": 'issues("Nobody", X)'})

    assert "no results" in result.lower()
