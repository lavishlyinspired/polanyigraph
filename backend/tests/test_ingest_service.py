"""Integration test: extraction -> live GraphDB validation -> live Neo4j write.

LLM is faked (network-free, per kg-extraction's definition of done); GraphDB and
Neo4j are the real local services — this proves the write path end to end
against the real ontology and the real graph store, not fixtures.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import history_service
from services.ingest_service import ingest_text


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        return self._response


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
    neo4j.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=graph_id)
    neo4j.close()
    graphdb.close()


_PAYLOAD = json.dumps({
    "entities": [
        {"name": "Acme Corp", "type": "organization", "confidence": 0.9},
        {"name": "Acme Preferred Stock", "type": "security", "confidence": 0.85},
    ],
    "relationships": [
        {"source": "Acme Corp", "relation": "issues", "target": "Acme Preferred Stock", "confidence": 0.8},
    ],
})


def test_ingest_writes_real_entities_with_provenance(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)

    record, result = ingest_text(
        neo4j=neo4j, graphdb=graphdb, llm=llm,
        graph_id=graph_id, text="Acme Corp issued preferred stock.",
        source_doc="test-doc-1", repository=settings.graphdb_repository,
    )

    assert len(record.nodes) == 2
    acme = next(n for n in record.nodes if n.label == "Acme Corp")
    assert acme.type == "organization"
    assert acme.source_doc == "test-doc-1"
    assert acme.extraction_confidence == 0.9
    assert len(record.edges) == 1
    assert result.dropped == []


def test_ingest_is_idempotent_across_repeated_ingests(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)

    ingest_text(neo4j=neo4j, graphdb=graphdb, llm=llm, graph_id=graph_id, text="t1", source_doc="d1", repository=settings.graphdb_repository)
    record, _ = ingest_text(neo4j=neo4j, graphdb=graphdb, llm=llm, graph_id=graph_id, text="t2", source_doc="d2", repository=settings.graphdb_repository)

    # Same two real-world entities mentioned again -> MERGE, not duplicate.
    assert len(record.nodes) == 2
    assert len(record.edges) == 1


def test_ingest_records_reviewable_history(services):
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)

    ingest_text(
        neo4j=neo4j, graphdb=graphdb, llm=llm, graph_id=graph_id,
        text="Acme Corp issued preferred stock.", source_doc="d1", repository=settings.graphdb_repository,
    )

    events = history_service.list_ingest_events(neo4j, graph_id)
    assert len(events) == 1
    assert events[0].text == "Acme Corp issued preferred stock."
    assert events[0].entity_count == 2
    assert events[0].relationship_count == 1
