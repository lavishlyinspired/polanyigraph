"""Chat service tests. LLM is faked (network-free); the graph context passed
to it is real, live Neo4j data -- this proves grounding, not a canned response
like the prototype's random-response mock.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from reasoning.engine import DerivedFact, ProofStep
from services import chat_history_service, chat_service, graph_service


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_call: dict[str, str] | None = None

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_call = {"system": system, "user": user}
        return self._response

    def stream_complete(self, *, system: str, user: str, temperature: float = 0.0):
        self.last_call = {"system": system, "user": user}
        words = self._response.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    yield client, graph_id
    client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    client.run("MATCH (f:DerivedFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    client.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=graph_id)
    client.close()


def test_chat_grounds_prompt_in_real_graph_data(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e1", label="Deutsche Bank AG", type_="commercial bank", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e2", label="European Central Bank", type_="central bank", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="r1", source_id="e1", target_id="e2", type_="is regulated by", weight=1.0)
    step = ProofStep(rule_name="r", edge_type="is regulated by", source_label="Deutsche Bank AG", target_label="European Central Bank", premise_activation=1.0, iteration=1)
    fact = DerivedFact(id="f1", rule_id="r1", rule_name="r", source_id="e1", target_id="e2", fact="Deutsche Bank AG is regulated by European Central Bank", confidence=0.9, iteration=1, proof_path=(step,))
    graph_service.save_derived_facts(client, graph_id=graph_id, facts=[fact])

    llm = FakeLLM("Deutsche Bank AG is a commercial bank regulated by the ECB.")
    reply = chat_service.answer(neo4j=client, llm=llm, graph_id=graph_id, message="Who regulates Deutsche Bank?", session_id="s1")

    assert reply == "Deutsche Bank AG is a commercial bank regulated by the ECB."
    assert llm.last_call is not None
    # The real entities/facts must actually be in the prompt sent to the LLM.
    assert "Deutsche Bank AG" in llm.last_call["system"] or "Deutsche Bank AG" in llm.last_call["user"]
    assert "European Central Bank" in llm.last_call["system"] or "European Central Bank" in llm.last_call["user"]
    assert "is regulated by European Central Bank" in llm.last_call["system"] or "is regulated by European Central Bank" in llm.last_call["user"]


def test_chat_on_empty_graph_still_answers(neo4j):
    client, graph_id = neo4j
    llm = FakeLLM("This graph is empty. Ingest a document to populate it.")
    reply = chat_service.answer(neo4j=client, llm=llm, graph_id=graph_id, message="What's in the graph?", session_id="s1")
    assert reply == "This graph is empty. Ingest a document to populate it."


def test_chat_remembers_prior_turns_in_same_session(neo4j):
    """PLAN.md §20 item 4: a second call in the same session should see the
    first turn in its prompt -- proving real continuity, not just grounding."""
    client, graph_id = neo4j
    llm = FakeLLM("first reply")
    chat_service.answer(neo4j=client, llm=llm, graph_id=graph_id, message="My favorite number is 42.", session_id="s1")

    llm2 = FakeLLM("second reply")
    chat_service.answer(neo4j=client, llm=llm2, graph_id=graph_id, message="What's my favorite number?", session_id="s1")

    assert "My favorite number is 42." in llm2.last_call["system"]
    assert "first reply" in llm2.last_call["system"]


def test_chat_sessions_do_not_leak_across_each_other(neo4j):
    client, graph_id = neo4j
    llm = FakeLLM("reply in session A")
    chat_service.answer(neo4j=client, llm=llm, graph_id=graph_id, message="Session A message.", session_id="session-a")

    llm2 = FakeLLM("reply in session B")
    chat_service.answer(neo4j=client, llm=llm2, graph_id=graph_id, message="Session B message.", session_id="session-b")

    assert "Session A message." not in llm2.last_call["system"]


def test_chat_stream_yields_incremental_chunks_that_join_into_the_full_reply(neo4j):
    client, graph_id = neo4j
    llm = FakeLLM("Hello there friend")

    chunks = list(chat_service.stream_answer(neo4j=client, llm=llm, graph_id=graph_id, message="Hi", session_id="s1"))

    assert len(chunks) > 1  # actually streamed in pieces, not one shot
    assert "".join(chunks) == "Hello there friend"


def test_chat_stream_persists_full_reply_and_grounds_like_answer(neo4j):
    client, graph_id = neo4j
    llm = FakeLLM("Streamed grounded reply.")

    list(chat_service.stream_answer(neo4j=client, llm=llm, graph_id=graph_id, message="Hi", session_id="s1"))

    history = chat_history_service.get_recent_messages(client, graph_id=graph_id, session_id="s1")
    assert any(m.role == "user" and m.content == "Hi" for m in history)
    assert any(m.role == "assistant" and m.content == "Streamed grounded reply." for m in history)


def test_chat_stream_remembers_prior_turns_in_same_session(neo4j):
    client, graph_id = neo4j
    llm = FakeLLM("first reply")
    list(chat_service.stream_answer(neo4j=client, llm=llm, graph_id=graph_id, message="My favorite number is 42.", session_id="s1"))

    llm2 = FakeLLM("second reply")
    list(chat_service.stream_answer(neo4j=client, llm=llm2, graph_id=graph_id, message="What's my favorite number?", session_id="s1"))

    assert "My favorite number is 42." in llm2.last_call["system"]
