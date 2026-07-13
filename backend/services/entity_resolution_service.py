"""Embedding-based entity resolution at extraction time (2026-07-13 plan
§11.2): the real problem this fixes -- extraction has no cross-document
memory, so "Acme Corp" in document 1 and "Acme Corporation" in document 2
become two separate nodes for the same real company (entity ids are
deterministic slugs of the extracted name, so a name variation always
produces a different node -- see services/ingest_service.py). Reuses the
same summaryEmbedding vectors already computed for search_entities -- no
new embedding call, no training, no GNN.

Doesn't silently merge: flags a likely duplicate for human confirmation,
same :ImplicitFact/:CandidateRule pending/approved/rejected review pattern
used throughout this project (2026-07-13 plan §12.2's "Human Gate").
Deliberately doesn't implement the actual node-merge mechanics (re-pointing
edges, deleting the duplicate) -- real graph surgery, out of scope here,
same as Feature 3's two-relation composition miner was explicitly scoped
out; this only ever detects and surfaces the candidate for a human to act
on.

Why this isn't a plain cosine-similarity threshold, corrected from the
plan's own suggested "e.g. >0.92" after empirical testing against the real
embedding model (nvidia/nv-embedqa-e5-v5): a genuine duplicate pair ("Acme
Corp" / "Acme Corporation", same company, different summary wording) scored
only ~0.87 -- BELOW that suggested cutoff -- while a genuinely different
pair ("Acme Preferred Stock" / "Acme Common Stock", two distinct securities
from the same issuer) scored ~0.88, HIGHER than the true duplicate. Full-
summary embeddings pick up on shared sentence structure/context as much as
shared entity identity, so no single cosine threshold cleanly separates the
two cases. Fix: use the vector index purely for cheap candidate RETRIEVAL
(find_similar_entities_by_type's loose floor), then apply a deterministic
label-token Jaccard check -- after stripping common legal-entity suffixes
(Corp, AG, Ltd, ...) -- as the actual precision filter. Verified against 7
real calibration pairs (both true and false duplicates) before picking the
0.6 threshold below; every pair classified correctly.
"""

from __future__ import annotations

import re
from typing import Callable

from db.neo4j_client import Neo4jClient
from services import vector_search_service

# candidate_type, expected_type -> bool. Default is exact equality, matching
# reasoning/engine.py's own _exact_match default for the same reason: this
# module stays usable without a live ontology schema (e.g. plain unit
# tests); callers with one (ingest_service.py, which already loads it for
# extraction) should inject OntologySchema.build_subclass_matcher() instead.
TypeMatcher = Callable[[str, str], bool]


def _exact_match(candidate_type: str, expected_type: str) -> bool:
    return candidate_type == expected_type

_VALID_STATUSES = {"pending", "approved", "rejected"}

# Legal-entity-form words that don't distinguish one real company from
# another -- stripped before comparing core name tokens. Not a domain
# ontology concept, just orthographic noise ("Acme Corp" vs "Acme
# Corporation" should compare as {"acme"} == {"acme"}, not {"acme","corp"}
# vs {"acme","corporation"}).
_LEGAL_SUFFIXES = {
    "corp", "corporation", "inc", "incorporated", "ag", "ltd", "limited",
    "group", "plc", "llc", "gmbh", "sa", "nv", "co", "company",
}

# Empirically calibrated (see module docstring) against 7 real embedding
# pairs -- every true duplicate's label-token Jaccard was 1.0, the one
# genuinely-different pair with a deceptively high embedding score was
# exactly 0.5. 0.6 sits with margin on the correct side of both.
_LABEL_OVERLAP_THRESHOLD = 0.6


def _core_tokens(label: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", label.lower())
    return {w for w in words if w not in _LEGAL_SUFFIXES}


def _labels_plausibly_same_entity(label_a: str, label_b: str) -> bool:
    tokens_a, tokens_b = _core_tokens(label_a), _core_tokens(label_b)
    if not tokens_a or not tokens_b:
        return False
    union = tokens_a | tokens_b
    return len(tokens_a & tokens_b) / len(union) >= _LABEL_OVERLAP_THRESHOLD


def check_for_duplicate(
    neo4j: Neo4jClient, *, graph_id: str, entity_id: str, entity_label: str, entity_type: str,
    type_matches: TypeMatcher = _exact_match,
) -> str | None:
    """Called right after an entity's summaryEmbedding is indexed
    (ingest_service.ingest_text). Returns the flagged :DuplicateCandidate's
    id if one was created, else None (no candidate cleared the type-
    compatibility check, the vector retrieval floor, and the label-token
    precision filter).

    type_matches defaults to exact string equality, but ingest_service.py
    passes the real ontology's subclass matcher: live-verifying against a
    real LLM's extraction (not the deterministic FakeLLM used in this
    module's own tests) found that the same real company can get different
    FIBO subtype labels across documents ("stock corporation" vs
    "corporation") -- exact-match alone silently missed a genuine
    duplicate. Checked in both directions since neither extraction is
    inherently "more correct" about which subtype applies."""
    candidates = vector_search_service.find_similar_entities(neo4j, graph_id=graph_id, entity_id=entity_id)
    match = next(
        (
            c for c in candidates
            if c.type is not None
            and (type_matches(entity_type, c.type) or type_matches(c.type, entity_type))
            and _labels_plausibly_same_entity(entity_label, c.text)
        ),
        None,
    )
    if match is None:
        return None

    candidate_id = f"dup-{graph_id}-{entity_id}-{match.id}"
    neo4j.run(
        """
        MERGE (d:DuplicateCandidate {id: $id})
        ON CREATE SET d.status = 'pending'
        SET d.graphId = $graph_id, d.newEntityId = $new_entity_id, d.newEntityLabel = $new_entity_label,
            d.existingEntityId = $existing_entity_id, d.existingEntityLabel = $existing_entity_label,
            d.similarity = $similarity, d.flaggedAt = datetime()
        """,
        id=candidate_id, graph_id=graph_id, new_entity_id=entity_id, new_entity_label=entity_label,
        existing_entity_id=match.id, existing_entity_label=match.text, similarity=match.score,
    )
    return candidate_id


def list_candidates(neo4j: Neo4jClient, *, graph_id: str, status: str = "pending") -> list[dict]:
    rows = neo4j.run(
        """
        MATCH (d:DuplicateCandidate {graphId: $graph_id, status: $status})
        RETURN d.id AS id, d.newEntityId AS newEntityId, d.newEntityLabel AS newEntityLabel,
               d.existingEntityId AS existingEntityId, d.existingEntityLabel AS existingEntityLabel,
               d.similarity AS similarity, d.status AS status
        ORDER BY d.similarity DESC
        """,
        graph_id=graph_id, status=status,
    )
    return [dict(row) for row in rows]


def _set_status(neo4j: Neo4jClient, candidate_id: str, status: str) -> None:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}' -- must be one of {_VALID_STATUSES}.")
    neo4j.run("MATCH (d:DuplicateCandidate {id: $id}) SET d.status = $status", id=candidate_id, status=status)


def confirm_duplicate(neo4j: Neo4jClient, candidate_id: str) -> None:
    """Human confirms these are the same real-world entity. Does NOT merge
    the nodes (see module docstring) -- only records the human judgment."""
    _set_status(neo4j, candidate_id, "approved")


def reject_duplicate(neo4j: Neo4jClient, candidate_id: str) -> None:
    """Kept, not deleted, so a later check_for_duplicate call doesn't
    re-surface it (MERGE only sets status on node creation)."""
    _set_status(neo4j, candidate_id, "rejected")
