"""Tests for services/entity_resolution_service.py (2026-07-13 plan §11.2):
embedding-based entity resolution at extraction time. Real Neo4j + real
embedder (a fast NVIDIA call, already confirmed live elsewhere) -- faking
vectors would trivialize the one thing worth testing: that the hybrid
vector-retrieval + label-token precision filter actually separates true
duplicates from superficially-similar-but-distinct entities, which plain
cosine similarity alone does not (see module docstring for the empirical
finding that motivated this design).
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from app.dependencies import get_embedder
from db.neo4j_client import Neo4jClient
from services import entity_resolution_service, graph_service, vector_search_service


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    yield client
    client.close()


@pytest.fixture
def embedder():
    e = get_embedder()
    try:
        e.verify()
    except Exception:
        pytest.skip("Embedding endpoint not reachable")
    return e


@pytest.fixture
def graph_id(neo4j):
    gid = f"test-{uuid.uuid4().hex[:8]}"
    yield gid
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=gid)
    neo4j.run("MATCH (d:DuplicateCandidate {graphId: $gid}) DETACH DELETE d", gid=gid)


def _seed_entity(neo4j, embedder, *, graph_id: str, entity_id: str, label: str, type_: str, summary: str) -> None:
    graph_service.upsert_entity(
        neo4j, graph_id=graph_id, entity_id=entity_id, label=label, type_=type_,
        source_doc="d", extraction_confidence=1.0,
    )
    vector_search_service.index_entity_summary(neo4j, embedder, graph_id=graph_id, entity_id=entity_id, summary=summary)


class TestLabelsPlausiblySameEntity:
    """Pure-function unit tests, no Neo4j needed -- calibrated against 7 real
    embedding-score pairs before this threshold was picked (see module
    docstring)."""

    def test_true_duplicates_after_stripping_legal_suffixes(self):
        from services.entity_resolution_service import _labels_plausibly_same_entity

        assert _labels_plausibly_same_entity("Acme Corp", "Acme Corporation")
        assert _labels_plausibly_same_entity("HDFC Bank Limited", "HDFC Bank")
        assert _labels_plausibly_same_entity("Deutsche Bank AG", "Deutsche Bank")
        assert _labels_plausibly_same_entity("UBS Group AG", "UBS")

    def test_genuinely_different_entities_are_not_flagged(self):
        from services.entity_resolution_service import _labels_plausibly_same_entity

        assert not _labels_plausibly_same_entity("Acme Corp", "Acme Bank")
        assert not _labels_plausibly_same_entity("Acme Preferred Stock", "Acme Common Stock")


def test_check_for_duplicate_flags_a_genuine_cross_document_duplicate(neo4j, embedder, graph_id):
    """Plan §11.2's own test spec: two documents producing near-identical
    names for the same real-world entity -> flagged as a candidate
    duplicate, not silently created."""
    vector_search_service.ensure_indexes(neo4j, dimensions=embedder.dimensions)
    _seed_entity(
        neo4j, embedder, graph_id=graph_id, entity_id="e1", label="Acme Corp", type_="organization",
        summary="Acme Corp is a company that issued preferred stock in a recent SEC filing.",
    )
    _seed_entity(
        neo4j, embedder, graph_id=graph_id, entity_id="e2", label="Acme Corporation", type_="organization",
        summary="Acme Corporation issued a new class of preferred stock according to a recent filing.",
    )

    candidate_id = entity_resolution_service.check_for_duplicate(
        neo4j, graph_id=graph_id, entity_id="e2", entity_label="Acme Corporation", entity_type="organization",
    )

    assert candidate_id is not None
    pending = entity_resolution_service.list_candidates(neo4j, graph_id=graph_id, status="pending")
    assert any(c["id"] == candidate_id and c["newEntityLabel"] == "Acme Corporation" and c["existingEntityLabel"] == "Acme Corp" for c in pending)


def test_check_for_duplicate_does_not_flag_genuinely_different_entities(neo4j, embedder, graph_id):
    """Plan §11.2's own test spec: two genuinely different entities with
    superficially similar names -> NOT flagged. This is the exact case
    where plain cosine similarity over full summaries scored the DIFFERENT
    pair higher than a true duplicate pair (see module docstring) -- the
    label-token filter is what actually prevents a false positive here."""
    vector_search_service.ensure_indexes(neo4j, dimensions=embedder.dimensions)
    _seed_entity(
        neo4j, embedder, graph_id=graph_id, entity_id="e1", label="Acme Preferred Stock", type_="security",
        summary="Acme Preferred Stock is a security issued by Acme Corp.",
    )
    _seed_entity(
        neo4j, embedder, graph_id=graph_id, entity_id="e2", label="Acme Common Stock", type_="security",
        summary="Acme Common Stock is a different security issued by Acme Corp.",
    )

    candidate_id = entity_resolution_service.check_for_duplicate(
        neo4j, graph_id=graph_id, entity_id="e2", entity_label="Acme Common Stock", entity_type="security",
    )

    assert candidate_id is None
    assert entity_resolution_service.list_candidates(neo4j, graph_id=graph_id, status="pending") == []


def test_check_for_duplicate_only_compares_within_the_same_entity_type(neo4j, embedder, graph_id):
    vector_search_service.ensure_indexes(neo4j, dimensions=embedder.dimensions)
    _seed_entity(
        neo4j, embedder, graph_id=graph_id, entity_id="e1", label="Acme Corp", type_="organization",
        summary="Acme Corp is a company that issued preferred stock in a recent SEC filing.",
    )
    _seed_entity(
        neo4j, embedder, graph_id=graph_id, entity_id="e2", label="Acme Corp Preferred Shares", type_="security",
        summary="Acme Corp Preferred Shares is a security issued by Acme Corp.",
    )

    # Same label, but a DIFFERENT type -- should never be treated as a
    # duplicate of the organization (e.g. an org and a security sharing a name prefix).
    candidate_id = entity_resolution_service.check_for_duplicate(
        neo4j, graph_id=graph_id, entity_id="e2", entity_label="Acme Corp Preferred Shares", entity_type="security",
    )

    assert candidate_id is None


def test_confirm_and_reject_duplicate_candidate(neo4j, embedder, graph_id):
    vector_search_service.ensure_indexes(neo4j, dimensions=embedder.dimensions)
    _seed_entity(
        neo4j, embedder, graph_id=graph_id, entity_id="e1", label="Acme Corp", type_="organization",
        summary="Acme Corp is a company that issued preferred stock in a recent SEC filing.",
    )
    _seed_entity(
        neo4j, embedder, graph_id=graph_id, entity_id="e2", label="Acme Corporation", type_="organization",
        summary="Acme Corporation issued a new class of preferred stock according to a recent filing.",
    )
    candidate_id = entity_resolution_service.check_for_duplicate(
        neo4j, graph_id=graph_id, entity_id="e2", entity_label="Acme Corporation", entity_type="organization",
    )
    assert candidate_id is not None

    entity_resolution_service.confirm_duplicate(neo4j, candidate_id)

    assert entity_resolution_service.list_candidates(neo4j, graph_id=graph_id, status="pending") == []
    approved = entity_resolution_service.list_candidates(neo4j, graph_id=graph_id, status="approved")
    assert any(c["id"] == candidate_id for c in approved)


def test_reject_duplicate_is_not_resurfaced_by_a_later_check(neo4j, embedder, graph_id):
    vector_search_service.ensure_indexes(neo4j, dimensions=embedder.dimensions)
    _seed_entity(
        neo4j, embedder, graph_id=graph_id, entity_id="e1", label="Acme Corp", type_="organization",
        summary="Acme Corp is a company that issued preferred stock in a recent SEC filing.",
    )
    _seed_entity(
        neo4j, embedder, graph_id=graph_id, entity_id="e2", label="Acme Corporation", type_="organization",
        summary="Acme Corporation issued a new class of preferred stock according to a recent filing.",
    )
    first_id = entity_resolution_service.check_for_duplicate(
        neo4j, graph_id=graph_id, entity_id="e2", entity_label="Acme Corporation", entity_type="organization",
    )
    assert first_id is not None

    entity_resolution_service.reject_duplicate(neo4j, first_id)
    second_id = entity_resolution_service.check_for_duplicate(
        neo4j, graph_id=graph_id, entity_id="e2", entity_label="Acme Corporation", entity_type="organization",
    )

    assert second_id == first_id  # same deterministic id, MERGE-safe
    assert entity_resolution_service.list_candidates(neo4j, graph_id=graph_id, status="pending") == []
    rejected = entity_resolution_service.list_candidates(neo4j, graph_id=graph_id, status="rejected")
    assert any(c["id"] == first_id for c in rejected)
