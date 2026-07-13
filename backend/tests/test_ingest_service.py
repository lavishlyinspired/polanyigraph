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
from app.dependencies import get_embedder
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import entity_resolution_service, graph_service, history_service, vector_search_service
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
    neo4j.run("MATCH (d:DuplicateCandidate {graphId: $gid}) DETACH DELETE d", gid=graph_id)
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


def test_ingest_links_provenance_for_produced_entities_and_edges(services):
    """PLAN.md §20 item 1: the real ingest path (not just the service function in
    isolation) links IngestEvent-[:PRODUCED]->Entity and stamps producedByEventId
    on the RELATES edge it creates."""
    neo4j, graphdb, settings, graph_id = services
    llm = FakeLLM(_PAYLOAD)

    record, _ = ingest_text(
        neo4j=neo4j, graphdb=graphdb, llm=llm, graph_id=graph_id,
        text="Acme Corp issued preferred stock.", source_doc="d1", repository=settings.graphdb_repository,
    )

    events = history_service.list_ingest_events(neo4j, graph_id)
    event_id = events[0].id
    produced = history_service.get_produced_entity_ids(neo4j, graph_id=graph_id, event_id=event_id)
    assert set(produced) == {n.id for n in record.nodes}

    edge = graph_service.get_graph(neo4j, graph_id).edges[0]
    assert edge.produced_by_event_id == event_id
    assert edge.valid_at is not None


def test_ingest_passes_extra_guidance_through_to_extraction(services):
    """PLAN.md §13.2: the agent's extractor node loads the kg-extraction
    runtime skill and threads its content through ingest_text -> extract."""
    neo4j, graphdb, settings, graph_id = services

    class CapturingFakeLLM(FakeLLM):
        def __init__(self, response: str) -> None:
            super().__init__(response)
            self.all_systems: list[str] = []

        def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
            self.all_systems.append(system)
            return super().complete_json(system=system, user=user, temperature=temperature)

    llm = CapturingFakeLLM(_PAYLOAD)

    ingest_text(
        neo4j=neo4j, graphdb=graphdb, llm=llm, graph_id=graph_id,
        text="Acme Corp issued preferred stock.", source_doc="d1", repository=settings.graphdb_repository,
        extra_guidance="Prefer precision over recall.",
    )

    assert any("Prefer precision over recall." in s for s in llm.all_systems)


def test_ingest_generates_and_accumulates_entity_summaries(services):
    """PLAN.md §20 item 3: a real LLM call synthesizes existing summary + new
    source text into an updated summary, each time an entity is re-mentioned."""
    neo4j, graphdb, settings, graph_id = services

    class SummaryAwareFakeLLM:
        """Extraction and summary generation both go through complete_json, so
        this fakes both: extraction payload for the 'entities'/'relationships'
        JSON call, a fixed summary string for anything else."""

        def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
            if "Existing summary" in user:
                marker = "New source text mentioning this entity:\n"
                start = user.index(marker) + len(marker)
                end = user.index("\n\nWrite one updated summary")
                return f"Summary based on: {user[start:end]}"
            return _PAYLOAD

    llm = SummaryAwareFakeLLM()

    record, _ = ingest_text(
        neo4j=neo4j, graphdb=graphdb, llm=llm, graph_id=graph_id,
        text="Acme Corp issued preferred stock.", source_doc="d1", repository=settings.graphdb_repository,
    )

    acme = next(n for n in record.nodes if n.label == "Acme Corp")
    assert acme.summary != ""
    assert "Acme Corp issued preferred stock." in acme.summary


def test_ingest_indexes_entity_summary_embedding_when_embedder_given(services):
    """GRAPHITI_INTEGRATION_PLAN.md §4 Option A: when an embedder is passed,
    each entity's summary gets embedded for native vector search -- optional,
    off by default (existing callers pass no embedder and are unaffected)."""
    neo4j, graphdb, settings, graph_id = services
    embedder = get_embedder()
    try:
        embedder.verify()
    except Exception:
        pytest.skip("Embedding endpoint not reachable")
    llm = FakeLLM(_PAYLOAD)

    ingest_text(
        neo4j=neo4j, graphdb=graphdb, llm=llm, graph_id=graph_id,
        text="Acme Corp issued preferred stock.", source_doc="d1",
        repository=settings.graphdb_repository, embedder=embedder,
    )

    rows = neo4j.run(
        "MATCH (e:Entity {graphId: $gid, label: 'Acme Corp'}) RETURN e.summaryEmbedding AS embedding",
        gid=graph_id,
    )
    assert rows[0]["embedding"] is not None
    assert len(rows[0]["embedding"]) == embedder.dimensions


def test_ingest_flags_a_cross_document_duplicate_entity(services):
    """2026-07-13 plan §11.2, wired end-to-end: document 1 extracts "Acme
    Corp"; document 2 extracts "Acme Corporation" (a name variation for the
    same real company, deliberately a different entity_id since ids are
    deterministic slugs of the extracted name -- see ingest_service.py's
    module docstring) -- flagged as a likely duplicate, not silently created
    as an unrelated second entity."""
    neo4j, graphdb, settings, graph_id = services
    embedder = get_embedder()
    try:
        embedder.verify()
    except Exception:
        pytest.skip("Embedding endpoint not reachable")

    payload_1 = json.dumps({
        "entities": [{"name": "Acme Corp", "type": "organization", "confidence": 0.9}],
        "relationships": [],
    })
    payload_2 = json.dumps({
        "entities": [{"name": "Acme Corporation", "type": "organization", "confidence": 0.9}],
        "relationships": [],
    })

    class SummaryAwareFakeLLM:
        def __init__(self, extraction_payload: str) -> None:
            self._extraction_payload = extraction_payload

        def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
            if "Existing summary" in user:
                marker = "New source text mentioning this entity:\n"
                start = user.index(marker) + len(marker)
                end = user.index("\n\nWrite one updated summary")
                return user[start:end]
            return self._extraction_payload

    ingest_text(
        neo4j=neo4j, graphdb=graphdb, llm=SummaryAwareFakeLLM(payload_1), graph_id=graph_id,
        text="Acme Corp is a company that issued preferred stock in a recent SEC filing.",
        source_doc="d1", repository=settings.graphdb_repository, embedder=embedder,
    )
    ingest_text(
        neo4j=neo4j, graphdb=graphdb, llm=SummaryAwareFakeLLM(payload_2), graph_id=graph_id,
        text="Acme Corporation issued a new class of preferred stock according to a recent filing.",
        source_doc="d2", repository=settings.graphdb_repository, embedder=embedder,
    )

    pending = entity_resolution_service.list_candidates(neo4j, graph_id=graph_id, status="pending")
    assert any(c["newEntityLabel"] == "Acme Corporation" and c["existingEntityLabel"] == "Acme Corp" for c in pending)
