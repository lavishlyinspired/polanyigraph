"""Integration tests for backend/agents/graph.py -- the LangGraph wrap
(MVP_PLAN.md Phase 6): extractor -> reasoner -> responder, calling the same
real, already-tested services (ingest_service, reasoning_service) as the
REST endpoints, not a parallel reimplementation. LLM is faked (network-free);
Neo4j/GraphDB are real, per this repo's convention.
"""

from __future__ import annotations

import json
import uuid

import pytest

from agents.graph import build_graph
from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import skill_graph_service


class FakeLLM:
    def __init__(self, extraction_payload: str, reply: str = "Extraction and reasoning complete.", route: str | None = None, enrichment_payload: str | None = None) -> None:
        self._extraction_payload = extraction_payload
        self._reply = reply
        self._route = route
        self._enrichment_payload = enrichment_payload or '{"facts": []}'
        self.calls: list[dict[str, str]] = []

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.calls.append({"system": system, "user": user})
        if "information extraction engine" in system.lower():
            return self._extraction_payload
        if "routing classifier" in system.lower():
            return self._route or "extract"
        if "expert ontology engineer" in system.lower():
            return self._enrichment_payload
        return self._reply


_PAYLOAD = json.dumps({
    "entities": [
        {"name": "Acme Corp", "type": "organization", "confidence": 0.9},
        {"name": "Acme Preferred Stock", "type": "security", "confidence": 0.85},
    ],
    "relationships": [
        {"source": "Acme Corp", "relation": "issues", "target": "Acme Preferred Stock", "confidence": 0.8},
    ],
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
    neo4j.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=graph_id)
    neo4j.close()
    graphdb.close()


def _initial_state(graph_id: str, text: str) -> dict:
    return {
        "graph_id": graph_id, "text": text, "intent": "",
        "entities_extracted": 0, "relationships_extracted": 0, "facts_derived": 0,
        "fact_texts": [], "enrichment_fact_texts": [], "query_results": [], "query_error": "",
        "memory_hits": [], "discovered_skills": [], "reply": "",
    }


def test_graph_extracts_reasons_and_responds(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD, reply="Extracted 2 entities and derived 1 fact.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Acme Corp issued preferred stock."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["entities_extracted"] == 2
    assert result["relationships_extracted"] == 1
    assert result["reply"] == "Extracted 2 entities and derived 1 fact."


def test_responder_prompt_is_grounded_in_real_extracted_content(services):
    """Live verification against the real running server found the responder
    replying "I don't have any information about the text you're referring
    to" -- the user message only carried bare counts, not the actual
    extracted entities/facts, so the LLM had nothing real to summarize.
    Fixed by grounding the responder prompt in real graph content, same
    pattern as chat_service._build_system_prompt."""
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)
    agent = build_graph(neo4j, graphdb, llm, settings)

    agent.invoke(
        _initial_state(graph_id, "Acme Corp issued preferred stock."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert len(responder_calls) == 1
    combined = responder_calls[0]["system"] + responder_calls[0]["user"]
    assert "Acme Corp" in combined


def test_graph_extractor_uses_the_kg_extraction_runtime_skill(services):
    """PLAN.md §13.2: the extractor node loads a real runtime skill and
    threads its content into the extraction prompt -- not just specced."""
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)
    agent = build_graph(neo4j, graphdb, llm, settings)

    agent.invoke(
        _initial_state(graph_id, "Acme Corp issued preferred stock."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    extraction_calls = [c for c in llm.calls if "information extraction engine" in c["system"].lower()]
    assert len(extraction_calls) == 1
    assert "Prefer precision over recall" in extraction_calls[0]["system"]


def test_router_calls_find_relevant_skills_before_any_node_loads_a_skill(services):
    """PLAN.md §18: 'Router node is updated to call find_relevant_skills
    before load_skill.' The router runs first in the graph (before
    extractor/responder, the only nodes that call load_skill), and populates
    discovered_skills from the real Neo4j skill graph -- not a placeholder.

    Uses task-phrased text ("extract entities...") rather than bare document
    content deliberately: find_relevant_skills is a Lucene full-text match
    against skill *descriptions* ("Use when extracting entities..."), which
    only hits when the routed text shares vocabulary with that description.
    Raw document text being ingested (e.g. "Acme Corp issued preferred
    stock.") shares no such vocabulary and legitimately returns zero matches
    -- a real, separate discovery-quality limitation, not something this test
    should paper over."""
    neo4j, graphdb, settings, graph_id = services
    skill_graph_service.ensure_schema(neo4j)
    skill_graph_service.seed_skills(neo4j)
    llm = FakeLLM(_PAYLOAD)
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Extract entities and relationships from this text: Acme Corp issued preferred stock."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["discovered_skills"]
    assert "kg-extraction" in result["discovered_skills"]


def test_graph_handles_extraction_that_yields_no_reasonable_facts(services):
    """Empty extraction -> reasoner has nothing to reason over -> graph still
    completes and responds, rather than crashing on EmptyGraphError."""
    neo4j, graphdb, settings, graph_id = services
    empty_payload = json.dumps({"entities": [], "relationships": []})
    llm = FakeLLM(empty_payload, reply="Nothing extractable in that text.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "The weather was nice."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["entities_extracted"] == 0
    assert result["facts_derived"] == 0
    assert result["reply"] == "Nothing extractable in that text."


def test_router_prompt_disambiguates_extract_from_enrich_with_examples(services):
    """Live discovery: the real LLM (llama-3.1-8b-instruct) misclassified a
    plain declarative sentence ("Deutsche Bank AG issues bonds...") as
    "enrich" instead of "extract" -- both "operate on text" from the model's
    perspective without a clearer signal. Fixed with few-shot examples;
    this locks in that the disambiguating prompt content survives."""
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)
    agent = build_graph(neo4j, graphdb, llm, settings)

    agent.invoke(
        _initial_state(graph_id, "Acme Corp issued preferred stock."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    router_calls = [c for c in llm.calls if "routing classifier" in c["system"].lower()]
    assert len(router_calls) == 1
    assert "default for any plain declarative" in router_calls[0]["system"]
    assert "Deutsche Bank AG issued a bond." in router_calls[0]["system"]


def test_router_defaults_to_extract_when_llm_returns_something_unrecognized(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD, route="not-a-real-intent")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Acme Corp issued preferred stock."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["entities_extracted"] == 2  # extractor ran -> "extract" was the effective route


def test_enrich_intent_runs_all_11_heuristics_against_the_real_graph(services):
    """PLAN.md §19.2: enrichment is real via the agent too, not only /enrich."""
    neo4j, graphdb, settings, graph_id = services
    from services import graph_service

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="e1", label="the match", type_="event", source_doc="d", extraction_confidence=1.0)
    enrichment_payload = json.dumps({"facts": [{"text": "an implicit fact", "anchors": ["e1"], "confidence": 0.7}]})
    llm = FakeLLM(_PAYLOAD, route="enrich", enrichment_payload=enrichment_payload, reply="Found implicit facts.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Enrich the graph."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["reply"] == "Found implicit facts."
    assert len(result["enrichment_fact_texts"]) == 11  # one candidate from each of the 11 heuristics
    from services import enrichment_service
    assert len(enrichment_service.list_pending_facts(neo4j, graph_id)) == 11

    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert "favor precision" in responder_calls[0]["system"].lower()


def test_query_intent_runs_the_real_query_engine(services):
    neo4j, graphdb, settings, graph_id = services
    from services import graph_service

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="e1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="e2", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="r1", source_id="e1", target_id="e2", type_="issues", weight=1.0)

    llm = FakeLLM(_PAYLOAD, route="query", reply="Acme Corp issues Acme Preferred Stock.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, 'issues("Acme Corp", X)'),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["reply"] == "Acme Corp issues Acme Preferred Stock."
    assert len(result["query_results"]) == 1

    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert "kg query" in responder_calls[0]["system"].lower() or "query language" in responder_calls[0]["system"].lower()


def test_reason_intent_runs_reasoning_without_a_preceding_extraction(services):
    neo4j, graphdb, settings, graph_id = services
    from services import graph_service

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="sec1", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    llm = FakeLLM(_PAYLOAD, route="reason", reply="Reasoning derived a new fact.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Run reasoning over the graph."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["entities_extracted"] == 0  # no extraction happened for this intent
    assert result["facts_derived"] == 1
    assert result["reply"] == "Reasoning derived a new fact."


def test_visualize_intent_describes_the_real_graph(services):
    neo4j, graphdb, settings, graph_id = services
    from services import graph_service

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="e1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)

    llm = FakeLLM(_PAYLOAD, route="visualize", reply="The graph has one organization: Acme Corp.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Show me the graph."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["reply"] == "The graph has one organization: Acme Corp."
    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert "Acme Corp" in responder_calls[0]["user"]


def test_recall_intent_runs_the_real_memory_agent_node(services):
    """PLAN.md §2: memory_agent, the 7th of the originally-sketched 7 agent
    nodes. Searches real, already-persisted chat history
    (services/chat_history_service.py) via services/memory_service.py --
    not a new mock store."""
    neo4j, graphdb, settings, graph_id = services
    from services import chat_history_service

    chat_history_service.append_message(
        neo4j, graph_id=graph_id, session_id=f"{graph_id}:default",
        message_id="m1", role="user", content="Who regulates Credit Suisse?",
    )

    llm = FakeLLM(_PAYLOAD, route="recall", reply="You previously asked about Credit Suisse's regulator.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "What did I previously ask about Credit Suisse?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["reply"] == "You previously asked about Credit Suisse's regulator."
    assert len(result["memory_hits"]) == 1
    assert "Credit Suisse" in result["memory_hits"][0]

    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert "bi-temporal" in responder_calls[0]["system"].lower()  # memory-recall skill loaded


def test_recall_intent_with_no_matches_still_responds(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD, route="recall", reply="I don't have any memory of that.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "What did I ask about before?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["memory_hits"] == []
    assert result["reply"] == "I don't have any memory of that."


def test_temporal_question_loads_memory_recall_skill_in_addition(services):
    neo4j, graphdb, settings, graph_id = services

    llm = FakeLLM(_PAYLOAD, route="query", reply="Historical answer.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    agent.invoke(
        _initial_state(graph_id, 'What was true historically for domicile("Acme Corp", X)?'),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert "bi-temporal" in responder_calls[0]["system"].lower()
