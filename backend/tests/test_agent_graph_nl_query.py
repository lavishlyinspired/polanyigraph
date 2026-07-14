"""Integration tests for querier_node's NL-translation wiring (PLAN: plans/
nl-query-translation.md Slice 2). Kept in a separate file so
test_agent_graph.py's existing query-intent tests stay literally untouched
(same discipline as the analytics plan's Slice 3 GDS migration).

Conversation history is scoped by graph_id (not a separate chat session id)
-- agents/graph.py's LangGraph flow doesn't persist its own turns to
chat_history_service today (that's a different, parallel mechanism used by
services/chat_service.py's /chat endpoint), so this slice reads whatever
history is seeded under graph_id directly, deliberately not expanding scope
into wiring the agent's own turn-writing in this pass.
"""

from __future__ import annotations

import uuid

import pytest

from agents.graph import _find_ungrounded_claims, build_graph
from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import chat_history_service, nl_query_service


class FakeLLM:
    """Leaner than test_agent_graph.py's FakeLLM -- only the response types
    these query-focused tests need (routing, NL->DSL translation, reply)."""

    def __init__(self, *, route: str, translation: str, reply: str) -> None:
        self._route = route
        self._translation = translation
        self._reply = reply
        self.calls: list[dict[str, str]] = []

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.calls.append({"system": system, "user": user})
        if "routing classifier" in system.lower():
            return self._route
        if "predicate(subject, object) query language" in system:
            return self._translation
        return self._reply


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
    neo4j.run("MATCH (s:ChatSession {graphId: $gid})-[:HAS_MESSAGE]->(m:ChatMessage) DETACH DELETE m", gid=graph_id)
    neo4j.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=graph_id)
    neo4j.close()
    graphdb.close()


def _initial_state(graph_id: str, text: str) -> dict:
    return {
        "graph_id": graph_id, "text": text, "intent": "", "intents": [],
        "entities_extracted": 0, "relationships_extracted": 0, "facts_derived": 0,
        "fact_texts": [], "enrichment_fact_texts": [], "query_results": [], "query_error": "",
        "translated_query": "", "memory_hits": [], "analytics_summary": [],
        "discovered_skills": [], "discovered_skill_scores": [],
        "partial_answers": {}, "combined_answer": "", "reply": "",
    }


def _seed_graph(neo4j, graph_id: str) -> None:
    from services import graph_service

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="e1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="e2", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="r1", source_id="e1", target_id="e2", type_="issues", weight=1.0)


def test_dsl_syntax_query_skips_translation_entirely(services):
    neo4j, graphdb, settings, graph_id = services
    _seed_graph(neo4j, graph_id)
    llm = FakeLLM(route="query", translation="SHOULD-NEVER-BE-CALLED", reply="Acme Corp issues Acme Preferred Stock.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, 'issues("Acme Corp", X)'),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["translated_query"] == ""
    assert len(result["query_results"]) == 1
    translation_calls = [c for c in llm.calls if "predicate(subject, object) query language" in c["system"]]
    assert translation_calls == []


def test_natural_language_query_is_translated_and_executed(services):
    neo4j, graphdb, settings, graph_id = services
    _seed_graph(neo4j, graph_id)
    llm = FakeLLM(route="query", translation='issues("Acme Corp", X)', reply="Acme Corp issues Acme Preferred Stock.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "what does Acme Corp issue?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["translated_query"] == 'issues("Acme Corp", X)'
    assert len(result["query_results"]) == 1
    assert result["reply"] == "Acme Corp issues Acme Preferred Stock."


def test_responder_prompt_includes_the_translated_query_when_present(services):
    neo4j, graphdb, settings, graph_id = services
    _seed_graph(neo4j, graph_id)
    llm = FakeLLM(route="query", translation='issues("Acme Corp", X)', reply="Acme Corp issues Acme Preferred Stock.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    agent.invoke(
        _initial_state(graph_id, "what does Acme Corp issue?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert len(responder_calls) == 1
    assert 'issues("Acme Corp", X)' in responder_calls[0]["user"]


def test_responder_prompt_omits_translated_query_line_for_dsl_syntax_input(services):
    neo4j, graphdb, settings, graph_id = services
    _seed_graph(neo4j, graph_id)
    llm = FakeLLM(route="query", translation="SHOULD-NEVER-BE-CALLED", reply="Acme Corp issues Acme Preferred Stock.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    agent.invoke(
        _initial_state(graph_id, 'issues("Acme Corp", X)'),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    responder_calls = [c for c in llm.calls if "knowledge-graph analyst assistant" in c["system"].lower()]
    assert "Query run:" not in responder_calls[0]["user"]


def test_groundedness_check_does_not_flag_a_stated_translated_query():
    """The translated query itself is real, grounding data (it's IN the
    grounding_text) -- stating it back must never be treated as an
    ungrounded claim."""
    grounding_text = 'Query run: issues("Acme Corp", X)\nQuery: what does Acme Corp issue?\nResults:\nAcme Corp issues("Acme Preferred Stock")'
    reply = 'I ran issues("Acme Corp", X) and found that Acme Corp issues Acme Preferred Stock.'

    assert _find_ungrounded_claims(reply, grounding_text) == []


def test_out_of_scope_question_is_handled_gracefully_without_fabrication(services):
    neo4j, graphdb, settings, graph_id = services
    _seed_graph(neo4j, graph_id)
    llm = FakeLLM(
        route="query", translation=nl_query_service.NL_QUERY_OUT_OF_SCOPE,
        reply="I couldn't find anything in this graph matching that question.",
    )
    agent = build_graph(neo4j, graphdb, llm, settings)

    result = agent.invoke(
        _initial_state(graph_id, "what's the weather like today?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    assert result["translated_query"] == ""
    assert result["query_results"] == []
    assert result["query_error"] != ""


def test_followup_question_resolves_using_seeded_conversation_history(services):
    neo4j, graphdb, settings, graph_id = services
    _seed_graph(neo4j, graph_id)
    chat_history_service.append_message(
        neo4j, graph_id=graph_id, session_id=graph_id, message_id=f"{graph_id}:m1",
        role="user", content="tell me about Acme Corp",
    )
    chat_history_service.append_message(
        neo4j, graph_id=graph_id, session_id=graph_id, message_id=f"{graph_id}:m2",
        role="assistant", content="Acme Corp is an organization in this graph.",
    )
    llm = FakeLLM(route="query", translation='issues("Acme Corp", X)', reply="Acme Corp issues Acme Preferred Stock.")
    agent = build_graph(neo4j, graphdb, llm, settings)

    agent.invoke(
        _initial_state(graph_id, "what does it issue?"),
        config={"configurable": {"thread_id": f"{graph_id}:default"}},
    )

    translation_calls = [c for c in llm.calls if "predicate(subject, object) query language" in c["system"]]
    assert len(translation_calls) == 1
    assert "tell me about Acme Corp" in translation_calls[0]["user"]
