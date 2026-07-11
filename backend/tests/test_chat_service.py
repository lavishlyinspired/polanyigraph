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
from services import chat_service, graph_service


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_call: dict[str, str] | None = None

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_call = {"system": system, "user": user}
        return self._response


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
    reply = chat_service.answer(neo4j=client, llm=llm, graph_id=graph_id, message="Who regulates Deutsche Bank?")

    assert reply == "Deutsche Bank AG is a commercial bank regulated by the ECB."
    assert llm.last_call is not None
    # The real entities/facts must actually be in the prompt sent to the LLM.
    assert "Deutsche Bank AG" in llm.last_call["system"] or "Deutsche Bank AG" in llm.last_call["user"]
    assert "European Central Bank" in llm.last_call["system"] or "European Central Bank" in llm.last_call["user"]
    assert "is regulated by European Central Bank" in llm.last_call["system"] or "is regulated by European Central Bank" in llm.last_call["user"]


def test_chat_on_empty_graph_still_answers(neo4j):
    client, graph_id = neo4j
    llm = FakeLLM("This graph is empty. Ingest a document to populate it.")
    reply = chat_service.answer(neo4j=client, llm=llm, graph_id=graph_id, message="What's in the graph?")
    assert reply == "This graph is empty. Ingest a document to populate it."
