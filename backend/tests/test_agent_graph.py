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
    def __init__(
        self, extraction_payload: str, reply: str = "Extraction and reasoning complete.",
        route: str | None = None, enrichment_payload: str | None = None, replies: list[str] | None = None,
    ) -> None:
        self._extraction_payload = extraction_payload
        self._reply = reply
        self._route = route
        self._enrichment_payload = enrichment_payload or '{"facts": []}'
        # For tests needing a DIFFERENT reply on successive responder calls
        # (e.g. plan §12.4's grounding-check retry) -- pops in order, holds
        # the last entry once exhausted. None (the common case) means every
        # responder call gets the same fixed `reply`, unchanged behavior.
        self._replies = list(replies) if replies else None
        self.calls: list[dict[str, str]] = []

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.calls.append({"system": system, "user": user})
        if "information extraction engine" in system.lower():
            return self._extraction_payload
        if "routing classifier" in system.lower():
            return self._route or "extract"
        if "expert ontology engineer" in system.lower():
            return self._enrichment_payload
        if self._replies is not None:
            return self._replies.pop(0) if len(self._replies) > 1 else self._replies[0]
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
    neo4j.run("MATCH (s:ChatSession {graphId: $gid})-[:HAS_MESSAGE]->(m:ChatMessage) DETACH DELETE m", gid=graph_id)
    neo4j.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=graph_id)
    neo4j.close()
    graphdb.close()


def _initial_state(graph_id: str, text: str) -> dict:
    return {
        "graph_id": graph_id, "text": text, "intent": "", "intents": [],
        "entities_extracted": 0, "relationships_extracted": 0, "facts_derived": 0,
        "fact_texts": [], "enrichment_fact_texts": [], "query_results": [], "query_error": "",
        "memory_hits": [], "discovered_skills": [], "discovered_skill_scores": [],
        "partial_answers": {}, "combined_answer": "", "reply": "",
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

    Deliberately uses bare document content with NO extraction-task
    vocabulary ("Acme Corp issued preferred stock." -- what a real ingested
    document looks like, not a task description). find_relevant_skills is a
    Lucene full-text match against skill *descriptions* ("Use when
    extracting entities..."), so a raw document alone would share no
    vocabulary and return nothing -- the router now folds in an
    intent-derived phrase (_discovery_query) precisely so this realistic
    case still resolves correctly."""
    neo4j, graphdb, settings, graph_id = services
    skill_graph_service.ensure_schema(neo4j)
    skill_graph_service.seed_skills(neo4j)
    llm = FakeLLM(_PAYLOAD)
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Acme Corp issued preferred stock."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["discovered_skills"]
    assert "kg-extraction" in result["discovered_skills"]


def test_discovery_query_folds_in_intent_vocabulary_so_bare_documents_still_match():
    """Unit-level proof of the fix, independent of Neo4j: for every intent,
    the synthesized discovery query must contain words a human would
    recognize from that skill's own SKILL.md description, plus the original
    text (so real content can still contribute to ranking)."""
    from agents.graph import _discovery_query

    assert "extract" in _discovery_query("extract", "Acme Corp issued preferred stock.").lower()
    assert "Acme Corp issued preferred stock." in _discovery_query("extract", "Acme Corp issued preferred stock.")
    assert "implicit" in _discovery_query("enrich", "some text").lower()
    assert "quer" in _discovery_query("query", "regulates(X, Y)").lower()
    assert "reason" in _discovery_query("reason", "some text").lower()
    assert "visual" in _discovery_query("visualize", "some text").lower()
    assert "prior conversation" in _discovery_query("recall", "some text").lower()


def test_select_skill_prefers_a_confident_discovery_match_over_the_hardcoded_map():
    """2026-07-13 plan §2 Stage A pure-function unit: discovery's top match
    wins once it clears the confidence floor, even when it disagrees with
    _SKILL_BY_INTENT's mapping for the given intent."""
    from agents.graph import _select_skill

    assert _select_skill("query", ["polanyi-enrichment", "kg-query"], [0.9, 0.4]) == "polanyi-enrichment"


def test_select_skill_falls_back_to_hardcoded_map_below_confidence_floor():
    from agents.graph import _select_skill

    assert _select_skill("query", ["kg-visualization"], [0.1]) == "kg-query"


def test_select_skill_falls_back_to_hardcoded_map_with_no_discovery_results():
    from agents.graph import _select_skill

    assert _select_skill("query", [], []) == "kg-query"


def test_select_skill_returns_none_for_unmapped_intent_with_no_confident_discovery():
    """extract/reason were never in _SKILL_BY_INTENT -- Stage A must not
    start loading guidance for them where none loaded before (no regression
    versus pre-Stage-A responder_node behavior)."""
    from agents.graph import _select_skill

    assert _select_skill("extract", [], []) is None
    assert _select_skill("extract", ["kg-query"], [0.1]) is None


def test_select_skill_lets_a_confident_match_apply_even_to_an_unmapped_intent():
    """Strict improvement, not a regression: extract/reason previously never
    loaded guidance in responder_node; Stage A now lets a genuinely
    confident discovery match apply there too."""
    from agents.graph import _select_skill

    assert _select_skill("extract", ["polanyi-enrichment"], [0.9]) == "polanyi-enrichment"


def test_stage_a_discovery_overrides_the_hardcoded_map_for_a_strongly_matching_text(services):
    """2026-07-13 plan §2 Stage A acceptance test: a query whose text
    strongly matches a DIFFERENT skill's description via full-text search
    selects that skill even though the classified intent ('query') maps to
    kg-query in _SKILL_BY_INTENT. Empirically verified against the real
    skill graph before writing this assertion (kg-query's own intent-phrase
    boost is real competition, not a strawman)."""
    neo4j, graphdb, settings, graph_id = services
    skill_graph_service.ensure_schema(neo4j)
    skill_graph_service.seed_skills(neo4j)
    overwhelming_enrichment_text = " ".join(["implicit", "unstated", "enrichment", "inferring"] * 8)
    llm = FakeLLM(_PAYLOAD, route="query", reply="Answer.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    agent.invoke(
        _initial_state(graph_id, overwhelming_enrichment_text),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert "careful human reader" in responder_calls[0]["system"].lower()


def test_stage_a_composition_survives_a_genuinely_unreachable_neo4j():
    """Mirrors ResilientSkillDiscovery's existing degradation test pattern
    (tests/test_skill_discovery.py): with Neo4j unreachable, find_skills
    degrades to filesystem keyword matching (never raises), and feeding that
    into _select_skill always yields a sensible result -- never a crash.
    Tests this composition directly rather than through a full build_graph()
    run: passing a dead Neo4j client to build_graph would also break
    querier_node's own (unrelated) Neo4j reads, which isn't what Stage A's
    fallback guarantee is about -- it's specifically about discovery/
    selection surviving Neo4j being down, isolated from the rest of the
    graph's real Neo4j dependency."""
    from agents.graph import _select_skill
    from agents.skill_discovery import ResilientSkillDiscovery
    from app.config import Settings

    dead_neo4j = Neo4jClient(Settings(neo4j_uri_desktop="bolt://localhost:1", profile="desktop"))
    discovery = ResilientSkillDiscovery(dead_neo4j)

    discovered = discovery.find_skills("regulates(X, Y) structured query knowledge graph", limit=3)
    selected = _select_skill("query", [d.name for d in discovered], [d.score for d in discovered])

    assert selected is not None  # "query" always has a _SKILL_BY_INTENT fallback, so never None here
    assert selected in {d.name for d in discovered} | {"kg-query"}


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


# --- 2026-07-13 plan §6: Feature 4 (Compound-Query Answering) ---

def test_combiner_node_produces_deterministic_output_from_a_fabricated_partial_answers_dict():
    """Plan §5.10: no graph/LLM needed -- combiner_node is a pure,
    module-level function (agents/graph.py), not a build_graph closure."""
    from agents.graph import combiner_node

    state = {
        "partial_answers": {
            "reasoner": {"summary": "Acme Corp issues Acme Preferred Stock", "confidence": 0.8},
            "memory_agent": {"summary": "no matching memory found", "confidence": 0.0},
        }
    }

    result = combiner_node(state)

    assert "[reasoner, confidence=0.80] Acme Corp issues Acme Preferred Stock" in result["combined_answer"]
    assert "[memory_agent, confidence=0.00] no matching memory found" in result["combined_answer"]


def test_combiner_node_reports_no_sub_answers_for_an_empty_dict():
    from agents.graph import combiner_node

    assert combiner_node({"partial_answers": {}})["combined_answer"] == "(no sub-answers produced)"


def test_flag_off_never_fans_out_even_if_the_llm_returns_a_comma_list(services):
    """Plan §5.3's core regression-safety guarantee: with the flag off, a
    stray comma from the base-prompt LLM must not silently enable compound
    behavior. Router truncates to the primary intent unconditionally."""
    neo4j, graphdb, settings, graph_id = services
    assert settings.enable_compound_queries is False

    llm = FakeLLM(_PAYLOAD, route="reason,recall", reply="Single-path reply.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Some text."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["intents"] == ["reason"]
    assert result["intent"] == "reason"
    assert result["combined_answer"] == ""  # combiner never ran
    assert result["reply"] == "Single-path reply."


def test_flag_on_parses_a_single_word_route_unchanged(services):
    neo4j, graphdb, _settings, graph_id = services
    settings = _settings.model_copy(update={"enable_compound_queries": True})
    from services import graph_service

    llm = FakeLLM(_PAYLOAD, route="reason", reply="Reasoning derived a new fact.")
    agent = build_graph(neo4j, graphdb, llm, settings)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="sec1", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    result = agent.invoke(
        _initial_state(graph_id, "Run reasoning over the graph."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["intents"] == ["reason"]
    assert result["intent"] == "reason"  # not "compound" -- single-word route stays single-path even with the flag on


def test_flag_on_falls_back_to_extract_for_garbage_compound_output(services):
    neo4j, graphdb, _settings, graph_id = services
    settings = _settings.model_copy(update={"enable_compound_queries": True})

    llm = FakeLLM(_PAYLOAD, route="not-a-real-intent,also-garbage")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Acme Corp issued preferred stock."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["intents"] == ["extract"]
    assert result["entities_extracted"] == 2  # extractor really ran


def test_flag_on_extract_in_a_compound_list_collapses_to_single_intent(services):
    """extract can't be one of several parallel Send branches -- reasoning
    over a graph "extract" hasn't written to yet would race it."""
    neo4j, graphdb, _settings, graph_id = services
    settings = _settings.model_copy(update={"enable_compound_queries": True})

    llm = FakeLLM(_PAYLOAD, route="extract,reason")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Acme Corp issued preferred stock."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["intents"] == ["extract"]
    assert result["intent"] == "extract"
    assert result["entities_extracted"] == 2  # extraction really ran, not silently skipped


def test_flag_on_compound_query_fans_out_to_both_specialists_and_combines_real_output(services):
    """Plan §5.10 integration test: a real compound query against a real
    small graph -- reasoner and memory_agent both dispatch in parallel
    (LangGraph Send), partial_answers merges both writes via the
    operator.or_ reducer, combiner joins them, and responder's "compound"
    branch synthesis prompt references both."""
    neo4j, graphdb, _settings, graph_id = services
    settings = _settings.model_copy(update={"enable_compound_queries": True})
    from services import graph_service

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="sec1", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    from services import chat_history_service
    chat_history_service.append_message(
        neo4j, graph_id=graph_id, session_id=f"{graph_id}:default",
        message_id="m1", role="user", content="Who regulates Credit Suisse?",
    )

    llm = FakeLLM(_PAYLOAD, route="reason,recall", reply="Combined answer.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Is Acme Corp issuance compliant, and have we previously discussed Credit Suisse in an earlier conversation?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["intents"] == ["reason", "recall"]
    assert result["intent"] == "compound"
    assert result["facts_derived"] == 1  # reasoner branch really ran
    assert len(result["memory_hits"]) == 1  # memory_agent branch really ran
    assert "reasoner" in result["combined_answer"]
    assert "memory_agent" in result["combined_answer"]
    assert result["reply"] == "Combined answer."

    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert len(responder_calls) == 1
    assert "reasoner" in responder_calls[0]["user"]
    assert "memory_agent" in responder_calls[0]["user"]
    assert "Synthesize one coherent answer" in responder_calls[0]["user"]


def test_find_ungrounded_claims_is_clean_on_a_real_grounded_reply():
    """Calibrated against a real live-captured compound reply (2026-07-13
    plan §12.4): plain keyword-overlap flagged genuinely grounded paraphrase
    sentences just as readily as fabricated ones, so this checks for NOVEL
    specific tokens (multi-word proper nouns / numbers) instead."""
    from agents.graph import _find_ungrounded_claims

    combined_answer = (
        "[reasoner, confidence=1.00] Acme Corp issues Acme Preferred Stock\n"
        "[memory_agent, confidence=0.20] [chat_message] Who regulates Credit Suisse?"
    )
    real_reply = (
        "Based on the provided information, here's a synthesized answer:\n\n"
        "Acme Corp issued Acme Preferred Stock, which is a type of security. "
        "However, I couldn't find any information about the regulation of Acme Corp's issuance.\n\n"
        "Regarding Credit Suisse, it was previously discussed in an earlier conversation, "
        "and the question about its regulation was asked.\n\n"
        "The first part of the answer relies on the reasoner's output, which states that "
        "Acme Corp issued Acme Preferred Stock. The second part relies on the memory agent's "
        "output, which indicates that Credit Suisse was previously discussed in an earlier conversation."
    )

    assert _find_ungrounded_claims(real_reply, combined_answer) == []


def test_find_ungrounded_claims_catches_a_fabricated_novel_fact():
    from agents.graph import _find_ungrounded_claims

    combined_answer = "[reasoner, confidence=1.00] Acme Corp issues Acme Preferred Stock"
    fabricated_reply = (
        "Acme Corp is headquartered in Geneva and was founded in 1998 by a consortium of European banks. "
        "It also secretly controls a shadow subsidiary in the Cayman Islands that has never been disclosed to regulators."
    )

    ungrounded = _find_ungrounded_claims(fabricated_reply, combined_answer)

    assert len(ungrounded) == 2


def test_compound_grounding_check_triggers_exactly_one_bounded_retry(services):
    """Plan §12.4's own test spec: a deliberately fabricated over-claiming
    reply triggers exactly one retry, not a loop."""
    neo4j, graphdb, _settings, graph_id = services
    settings = _settings.model_copy(update={"enable_compound_queries": True})
    from services import graph_service

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="sec1", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    from services import chat_history_service
    chat_history_service.append_message(
        neo4j, graph_id=graph_id, session_id=f"{graph_id}:default",
        message_id="m1", role="user", content="Who regulates Credit Suisse?",
    )

    fabricated_first_reply = "Acme Corp is secretly headquartered in Geneva and controls a shadow subsidiary in the Cayman Islands."
    clean_retry_reply = "Acme Corp issues Acme Preferred Stock; no memory of Credit Suisse discussion was found."
    llm = FakeLLM(_PAYLOAD, route="reason,recall", replies=[fabricated_first_reply, clean_retry_reply])
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Is Acme Corp's issuance compliant, and have we previously discussed Credit Suisse in an earlier conversation?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["reply"] == clean_retry_reply
    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert len(responder_calls) == 2  # exactly one retry, not a loop
    assert "claims not supported by the real data provided" in responder_calls[1]["system"]


def test_compound_grounding_check_does_not_retry_a_genuinely_grounded_reply(services):
    neo4j, graphdb, _settings, graph_id = services
    settings = _settings.model_copy(update={"enable_compound_queries": True})
    from services import graph_service

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="sec1", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    from services import chat_history_service
    chat_history_service.append_message(
        neo4j, graph_id=graph_id, session_id=f"{graph_id}:default",
        message_id="m1", role="user", content="Who regulates Credit Suisse?",
    )

    grounded_reply = "Acme Corp issues Acme Preferred Stock. No prior discussion of Credit Suisse was found in memory."
    llm = FakeLLM(_PAYLOAD, route="reason,recall", reply=grounded_reply)
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Is Acme Corp's issuance compliant, and have we previously discussed Credit Suisse in an earlier conversation?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["reply"] == grounded_reply
    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert len(responder_calls) == 1  # no retry needed


def test_grounding_check_generalizes_to_a_single_intent_reply_not_just_compound(services):
    """Follow-up request: the maker/checker grounding check applies to
    EVERY responder reply now, not just the "compound" branch -- proven
    here against a plain "reason" intent, whose grounding source is
    responder_node's own `user` prompt (real entities/facts), not
    combined_answer (which only compound turns ever populate)."""
    neo4j, graphdb, settings, graph_id = services
    from services import graph_service

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="sec1", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    fabricated_first_reply = "Acme Corp is secretly headquartered in Geneva and was founded in 1998 by a shadow consortium."
    clean_retry_reply = "Acme Corp issues Acme Preferred Stock, as derived by reasoning."
    llm = FakeLLM(_PAYLOAD, route="reason", replies=[fabricated_first_reply, clean_retry_reply])
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "Run reasoning over the graph."),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["intent"] == "reason"  # not compound -- confirms this isn't the compound code path
    assert result["reply"] == clean_retry_reply
    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert len(responder_calls) == 2  # exactly one retry, not a loop, for a plain single-intent reply
