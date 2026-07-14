"""Integration tests for the "analyze" intent (PLAN: plans/
analytical-engine.md Slice 9) -- same pattern as the existing query/reason/
visualize intent tests in test_agent_graph.py (LLM faked, Neo4j real), kept
in a separate file so this new intent's tests don't touch that file.
"""

from __future__ import annotations

import uuid

import pytest

from agents.graph import build_graph
from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import skill_graph_service
from tests.test_agent_graph import FakeLLM, _PAYLOAD


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
    # kg-analytics is a new skill (PLAN Slice 9) -- must be (re-)seeded into
    # the live Neo4j skill graph before Stage A discovery can rank it,
    # same requirement test_agent_graph.py's discovery-focused tests have.
    skill_graph_service.ensure_schema(neo4j)
    skill_graph_service.seed_skills(neo4j)
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    yield neo4j, graphdb, settings, graph_id
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.close()
    graphdb.close()


def _initial_state(graph_id: str, text: str) -> dict:
    return {
        "graph_id": graph_id, "text": text, "intent": "", "intents": [],
        "entities_extracted": 0, "relationships_extracted": 0, "facts_derived": 0,
        "fact_texts": [], "enrichment_fact_texts": [], "query_results": [], "query_error": "",
        "memory_hits": [], "discovered_skills": [], "discovered_skill_scores": [],
        "partial_answers": {}, "combined_answer": "", "reply": "", "analytics_summary": [],
    }


def test_analyze_intent_runs_the_real_analytics_engine(services):
    neo4j, graphdb, settings, graph_id = services
    from services import graph_service

    # Hub connects to two leaves (different relation types -- upsert_relationship
    # treats a same-source-and-type edge to a different target as superseding,
    # not additive, see its docstring) -- degree 2 vs 1, so ranking is meaningful.
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="hub", label="Hub Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="leaf1", label="Leaf One", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="leaf2", label="Leaf Two", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="hub", target_id="leaf1", type_="owns", weight=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e2", source_id="hub", target_id="leaf2", type_="manages", weight=1.0)

    llm = FakeLLM(_PAYLOAD, route="analyze", reply="Hub Corp is the most central entity.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "What are the most central entities in this graph?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["reply"] == "Hub Corp is the most central entity."
    assert len(result["analytics_summary"]) == 3  # one line per node
    assert "Hub Corp" in result["analytics_summary"][0]  # highest degree, ranked first

    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert "kg-analytics" in responder_calls[0]["system"].lower() or "centrality" in responder_calls[0]["system"].lower()


def test_analyze_intent_role_weights_a_noisy_value_entity_out_of_the_ranking(services):
    """End-to-end Analytics Role Mapping fix (PLAN Phase 1, agreed
    2026-07-14): a "rate of return"-typed entity -- a real FIBO subclass of
    quantity value -- must rank last (score 0.0) instead of dominating
    degree_centrality purely by co-occurring with every fact that cites a
    rate, the exact noise pattern found via live browser testing."""
    neo4j, graphdb, settings, graph_id = services
    from services import graph_service

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="hub", label="Hub Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="rate", label="8.45%", type_="rate of return", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="hub", target_id="rate", type_="reports", weight=1.0)

    llm = FakeLLM(_PAYLOAD, route="analyze", reply="Hub Corp is the most central entity.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "What are the most central entities in this graph?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["analytics_summary"][0].startswith("Hub Corp")
    assert "8.45%: 0.000" in result["analytics_summary"]


def test_analyze_intent_on_an_empty_graph_does_not_crash(services):
    neo4j, graphdb, settings, graph_id = services

    llm = FakeLLM(_PAYLOAD, route="analyze", reply="The graph is empty, nothing to analyze.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "What's central in this graph?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["analytics_summary"] == []
    assert result["reply"] == "The graph is empty, nothing to analyze."


def test_router_classifies_a_centrality_question_as_analyze(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD, route="analyze", reply="ok")
    agent = build_graph(neo4j, graphdb, llm, settings)

    agent.invoke(
        _initial_state(graph_id, "Which entities are most central or influential in this graph?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    router_calls = [c for c in llm.calls if "routing classifier" in c["system"].lower()]
    assert "analyze" in router_calls[0]["system"]
