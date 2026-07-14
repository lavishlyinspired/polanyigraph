"""Neo4j instance-graph read/write.

Storage shape (see ontology/sync.py for the rationale): every extracted instance
is a single ``:Entity`` node with a free-text ``type`` property (the ontology
class label), scoped by ``graphId``. Relationships are a single ``:RELATES``
type with a ``type`` property. This keeps the schema domain-agnostic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from db.neo4j_client import Neo4jClient
from reasoning.engine import DerivedFact as ReasoningDerivedFact
from reasoning.engine import Edge as ReasoningEdge
from reasoning.engine import Node as ReasoningNode
from reasoning.engine import ProofStep as ReasoningProofStep


@dataclass(frozen=True)
class GraphNodeRecord:
    id: str
    label: str
    type: str
    source_doc: str | None = None
    extraction_confidence: float | None = None
    activation: float | None = None
    derived: bool = False
    salience: float = 1.0
    # Arbitrary user-defined key-value pairs, not a fixed FIBO-specific field
    # list (ISIN/LEI/etc) -- this product is domain-agnostic.
    properties: dict[str, str] = field(default_factory=dict)
    note: str = ""
    summary: str = ""
    community_id: int | None = None
    # Written back by the analytics engine's Neo4jGraphStore (PLAN: plans/
    # analytical-engine.md Slice 1/9) under the literal property name
    # "centralityScore" -- callers persisting other centrality algorithms
    # (pagerank, betweenness, closeness) share this one property, same as
    # community_id is shared across community algorithms; only the most
    # recently persisted centrality run is ever visible here.
    centrality_score: float | None = None


@dataclass(frozen=True)
class GraphEdgeRecord:
    id: str
    source: str
    target: str
    type: str
    weight: float = 1.0
    valid_at: str | None = None
    invalid_at: str | None = None
    produced_by_event_id: str | None = None


@dataclass(frozen=True)
class GraphRecord:
    nodes: list[GraphNodeRecord]
    edges: list[GraphEdgeRecord]


@dataclass(frozen=True)
class GraphSummary:
    graph_id: str
    node_count: int
    edge_count: int
    last_ingest_at: str | None


def upsert_entity(
    neo4j: Neo4jClient,
    *,
    graph_id: str,
    entity_id: str,
    label: str,
    type_: str,
    source_doc: str,
    extraction_confidence: float,
    salience: float = 1.0,
) -> None:
    neo4j.run(
        """
        MERGE (e:Entity {id: $entity_id, graphId: $graph_id})
        SET e.label = $label,
            e.type = $type,
            e.sourceDoc = $source_doc,
            e.extractionConfidence = $extraction_confidence,
            e.salience = coalesce(e.salience, $salience),
            e.activation = coalesce(e.activation, 0.0),
            e.derived = coalesce(e.derived, false)
        """,
        entity_id=entity_id,
        graph_id=graph_id,
        label=label,
        type=type_,
        source_doc=source_doc,
        extraction_confidence=extraction_confidence,
        salience=salience,
    )


def upsert_relationship(
    neo4j: Neo4jClient,
    *,
    graph_id: str,
    edge_id: str,
    source_id: str,
    target_id: str,
    type_: str,
    weight: float = 1.0,
    produced_by_event_id: str | None = None,
) -> None:
    """Bi-temporal (PLAN.md §20 item 2): a same-source-and-type edge asserting a
    *different* target is treated as superseding the prior one (this graph models
    each relation type as single-valued per source) -- the old edge is invalidated,
    not overwritten, so it stays queryable via get_relationship_history()."""
    neo4j.run(
        """
        MATCH (s:Entity {id: $source_id, graphId: $graph_id})
        MATCH (t:Entity {id: $target_id, graphId: $graph_id})
        WITH s, t
        OPTIONAL MATCH (s)-[old:RELATES {graphId: $graph_id, type: $type}]->(other:Entity)
        WHERE other.id <> $target_id AND old.invalidAt IS NULL
        SET old.invalidAt = datetime()
        WITH s, t
        MERGE (s)-[r:RELATES {id: $edge_id, graphId: $graph_id}]->(t)
        SET r.type = $type, r.weight = $weight,
            r.validAt = coalesce(r.validAt, datetime()),
            r.producedByEventId = coalesce(r.producedByEventId, $produced_by_event_id)
        """,
        edge_id=edge_id,
        graph_id=graph_id,
        source_id=source_id,
        target_id=target_id,
        type=type_,
        weight=weight,
        produced_by_event_id=produced_by_event_id,
    )


def get_relationship_history(
    neo4j: Neo4jClient, *, graph_id: str, source_id: str, type_: str
) -> list[GraphEdgeRecord]:
    """All edges (current + invalidated) for a given (source, relation type),
    for provenance/timeline UI (UI_PLAN.md §9.2) -- get_graph() stays current-only."""
    rows = neo4j.run(
        """
        MATCH (s:Entity {id: $source_id, graphId: $graph_id})-[r:RELATES {graphId: $graph_id, type: $type}]->(t:Entity)
        RETURN r.id AS id, s.id AS source, t.id AS target, r.type AS type, r.weight AS weight,
               toString(r.validAt) AS validAt, toString(r.invalidAt) AS invalidAt,
               r.producedByEventId AS producedByEventId
        """,
        graph_id=graph_id,
        source_id=source_id,
        type=type_,
    )
    return [
        GraphEdgeRecord(
            id=row["id"], source=row["source"], target=row["target"], type=row["type"],
            weight=row["weight"] or 1.0, valid_at=row.get("validAt"), invalid_at=row.get("invalidAt"),
            produced_by_event_id=row.get("producedByEventId"),
        )
        for row in rows
    ]


def update_entity_metadata(
    neo4j: Neo4jClient,
    *,
    graph_id: str,
    entity_id: str,
    salience: float | None = None,
    properties: dict[str, str] | None = None,
    note: str | None = None,
) -> None:
    """Partial update: only fields explicitly passed (non-None) are changed."""
    sets = []
    params: dict[str, object] = {"entity_id": entity_id, "graph_id": graph_id}
    if salience is not None:
        sets.append("e.salience = $salience")
        params["salience"] = salience
    if properties is not None:
        sets.append("e.propertiesJson = $properties_json")
        params["properties_json"] = json.dumps(properties)
    if note is not None:
        sets.append("e.note = $note")
        params["note"] = note
    if not sets:
        return
    neo4j.run(
        f"MATCH (e:Entity {{id: $entity_id, graphId: $graph_id}}) SET {', '.join(sets)}",
        **params,
    )


def get_entity_summary(neo4j: Neo4jClient, *, graph_id: str, entity_id: str) -> str:
    rows = neo4j.run(
        "MATCH (e:Entity {id: $entity_id, graphId: $graph_id}) RETURN coalesce(e.summary, '') AS summary",
        entity_id=entity_id,
        graph_id=graph_id,
    )
    return rows[0]["summary"] if rows else ""


def update_entity_summary(neo4j: Neo4jClient, *, graph_id: str, entity_id: str, summary: str) -> None:
    """PLAN.md §20 item 3: mirrors Graphiti's EntityNode.summary -- regenerated by
    a real LLM call each time a new ingest references this entity (services/
    summary_service.py), accumulating context instead of staying extraction-only."""
    neo4j.run(
        "MATCH (e:Entity {id: $entity_id, graphId: $graph_id}) SET e.summary = $summary",
        entity_id=entity_id,
        graph_id=graph_id,
        summary=summary,
    )


def get_graph(neo4j: Neo4jClient, graph_id: str) -> GraphRecord:
    node_rows = neo4j.run(
        """
        MATCH (e:Entity {graphId: $graph_id})
        RETURN e.id AS id, e.label AS label, e.type AS type,
               e.sourceDoc AS sourceDoc, e.extractionConfidence AS extractionConfidence,
               e.activation AS activation, e.derived AS derived,
               coalesce(e.salience, 1.0) AS salience,
               coalesce(e.propertiesJson, '{}') AS propertiesJson,
               coalesce(e.note, '') AS note,
               coalesce(e.summary, '') AS summary,
               e.communityId AS communityId,
               e.centralityScore AS centralityScore
        ORDER BY e.id
        """,
        graph_id=graph_id,
    )
    edge_rows = neo4j.run(
        """
        MATCH (s:Entity {graphId: $graph_id})-[r:RELATES {graphId: $graph_id}]->(t:Entity {graphId: $graph_id})
        WHERE r.invalidAt IS NULL
        RETURN r.id AS id, s.id AS source, t.id AS target, r.type AS type, r.weight AS weight,
               toString(r.validAt) AS validAt, toString(r.invalidAt) AS invalidAt,
               r.producedByEventId AS producedByEventId
        """,
        graph_id=graph_id,
    )
    nodes = [
        GraphNodeRecord(
            id=row["id"],
            label=row["label"],
            type=row["type"],
            source_doc=row.get("sourceDoc"),
            extraction_confidence=row.get("extractionConfidence"),
            activation=row.get("activation"),
            derived=bool(row.get("derived")),
            salience=row.get("salience", 1.0),
            properties=json.loads(row.get("propertiesJson") or "{}"),
            note=row.get("note") or "",
            summary=row.get("summary") or "",
            community_id=row.get("communityId"),
            centrality_score=row.get("centralityScore"),
        )
        for row in node_rows
    ]
    edges = [
        GraphEdgeRecord(
            id=row["id"], source=row["source"], target=row["target"], type=row["type"],
            weight=row["weight"] or 1.0, valid_at=row.get("validAt"), invalid_at=row.get("invalidAt"),
            produced_by_event_id=row.get("producedByEventId"),
        )
        for row in edge_rows
    ]
    return GraphRecord(nodes=nodes, edges=edges)


def apply_activation(neo4j: Neo4jClient, *, graph_id: str, activation: dict[str, float]) -> None:
    """Persist the final activation values from a reasoning run onto entities."""
    neo4j.run(
        """
        UNWIND $rows AS row
        MATCH (e:Entity {id: row.id, graphId: $graph_id})
        SET e.activation = row.activation
        """,
        graph_id=graph_id,
        rows=[{"id": entity_id, "activation": value} for entity_id, value in activation.items()],
    )


def save_derived_facts(neo4j: Neo4jClient, *, graph_id: str, facts: list[ReasoningDerivedFact]) -> None:
    """Persist derived facts as :DerivedFact nodes and mark their target :Entity as derived."""
    if not facts:
        return
    rows = [
        {
            "id": f.id,
            "ruleId": f.rule_id,
            "ruleName": f.rule_name,
            "sourceId": f.source_id,
            "targetId": f.target_id,
            "fact": f.fact,
            "confidence": f.confidence,
            "iteration": f.iteration,
            # The rule's edge_type is the derived relation's predicate (a rule
            # only fires on edges of its own edge_type — see reasoning/engine.py
            # run_inference), captured on the final proof step.
            "edgeType": f.proof_path[-1].edge_type if f.proof_path else None,
            # Full proof chain, serialized -- needed to reconstruct real
            # ProofStep objects across separate manual-step API calls (Reason
            # tab prototype parity: Spread/Infer/Feed Back as distinct steps).
            "proofPathJson": json.dumps([
                {
                    "ruleName": step.rule_name, "edgeType": step.edge_type,
                    "sourceLabel": step.source_label, "targetLabel": step.target_label,
                    "premiseActivation": step.premise_activation, "iteration": step.iteration,
                    "typeResolution": step.type_resolution,
                }
                for step in f.proof_path
            ]),
        }
        for f in facts
    ]
    neo4j.run(
        """
        UNWIND $rows AS row
        MERGE (f:DerivedFact {id: row.id, graphId: $graph_id})
        SET f.ruleId = row.ruleId, f.ruleName = row.ruleName,
            f.sourceId = row.sourceId, f.targetId = row.targetId,
            f.fact = row.fact, f.confidence = row.confidence, f.iteration = row.iteration,
            f.edgeType = row.edgeType, f.proofPathJson = row.proofPathJson,
            f.fedBack = coalesce(f.fedBack, false)
        WITH f, row
        MATCH (t:Entity {id: row.targetId, graphId: $graph_id})
        SET t.derived = true
        MERGE (f)-[:DERIVED_FOR]->(t)
        """,
        graph_id=graph_id,
        rows=rows,
    )


@dataclass(frozen=True)
class DerivedFactRecord:
    id: str
    rule_id: str
    rule_name: str
    source_id: str
    target_id: str
    fact: str
    confidence: float
    iteration: int
    fed_back: bool
    review_status: str = "pending"
    proof_path: tuple[ReasoningProofStep, ...] = field(default=())


def get_derived_facts_full(neo4j: Neo4jClient, graph_id: str) -> list[DerivedFactRecord]:
    """Full derived-fact records (real proof paths, fed-back status) for the
    Reason tab's manual step-by-step mode and its richer UI display -- unlike
    get_derived_facts(), which only returns {fact, confidence} for chat grounding."""
    rows = neo4j.run(
        """
        MATCH (f:DerivedFact {graphId: $graph_id})
        RETURN f.id AS id, f.ruleId AS ruleId, f.ruleName AS ruleName,
               f.sourceId AS sourceId, f.targetId AS targetId, f.fact AS fact,
               f.confidence AS confidence, f.iteration AS iteration,
               coalesce(f.fedBack, false) AS fedBack,
               coalesce(f.reviewStatus, 'pending') AS reviewStatus,
               coalesce(f.proofPathJson, '[]') AS proofPathJson
        ORDER BY f.iteration, f.id
        """,
        graph_id=graph_id,
    )
    records = []
    for row in rows:
        proof_path = tuple(
            ReasoningProofStep(
                rule_name=step["ruleName"], edge_type=step["edgeType"],
                source_label=step["sourceLabel"], target_label=step["targetLabel"],
                premise_activation=step["premiseActivation"], iteration=step["iteration"],
                type_resolution=step.get("typeResolution"),
            )
            for step in json.loads(row["proofPathJson"])
        )
        records.append(
            DerivedFactRecord(
                id=row["id"], rule_id=row["ruleId"], rule_name=row["ruleName"],
                source_id=row["sourceId"], target_id=row["targetId"], fact=row["fact"],
                confidence=row["confidence"], iteration=row["iteration"],
                fed_back=row["fedBack"], review_status=row["reviewStatus"], proof_path=proof_path,
            )
        )
    return records


def get_derived_fact_rule_id(neo4j: Neo4jClient, *, graph_id: str, fact_id: str) -> str | None:
    rows = neo4j.run(
        "MATCH (f:DerivedFact {id: $fact_id, graphId: $graph_id}) RETURN f.ruleId AS ruleId",
        fact_id=fact_id, graph_id=graph_id,
    )
    return rows[0]["ruleId"] if rows else None


def set_derived_fact_review_status(neo4j: Neo4jClient, *, graph_id: str, fact_id: str, status: str) -> None:
    """2026-07-13 plan §11.1: marks a :DerivedFact as reviewed (confirmed/
    rejected) so it isn't re-surfaced for review -- same Human Gate pattern
    as enrichment's :ImplicitFact status and Feature 3's :CandidateRule
    status."""
    neo4j.run(
        "MATCH (f:DerivedFact {id: $fact_id, graphId: $graph_id}) SET f.reviewStatus = $status",
        fact_id=fact_id, graph_id=graph_id, status=status,
    )


def mark_facts_fed_back(neo4j: Neo4jClient, *, graph_id: str, fact_ids: list[str]) -> None:
    neo4j.run(
        """
        UNWIND $fact_ids AS fid
        MATCH (f:DerivedFact {id: fid, graphId: $graph_id})
        SET f.fedBack = true
        """,
        graph_id=graph_id,
        fact_ids=fact_ids,
    )


def clear_activation(neo4j: Neo4jClient, graph_id: str) -> None:
    """Reason tab's manual "Clear" for the Neural Activation step."""
    neo4j.run(
        "MATCH (e:Entity {graphId: $graph_id}) SET e.activation = 0.0",
        graph_id=graph_id,
    )


def clear_derived_facts(neo4j: Neo4jClient, graph_id: str) -> None:
    """Reason tab's manual "Clear" for the Symbolic Inference step -- removes
    :DerivedFact nodes and unsets the :Entity.derived flag they set."""
    neo4j.run(
        """
        MATCH (f:DerivedFact {graphId: $graph_id})
        OPTIONAL MATCH (f)-[:DERIVED_FOR]->(t:Entity)
        SET t.derived = false
        WITH DISTINCT f
        DETACH DELETE f
        """,
        graph_id=graph_id,
    )


def load_triples(neo4j: Neo4jClient, graph_id: str) -> list["Triple"]:
    """All stored + derived triples for a graph, in subject/predicate/object form
    (by entity label, matching the query language's literal matching), for the
    structured query engine (services/query_engine.py)."""
    from services.query_engine import Triple

    stored_rows = neo4j.run(
        """
        MATCH (s:Entity {graphId: $graph_id})-[r:RELATES {graphId: $graph_id}]->(t:Entity {graphId: $graph_id})
        WHERE r.invalidAt IS NULL
        RETURN s.label AS subject, r.type AS predicate, t.label AS object
        """,
        graph_id=graph_id,
    )
    derived_rows = neo4j.run(
        """
        MATCH (f:DerivedFact {graphId: $graph_id})
        MATCH (s:Entity {id: f.sourceId, graphId: $graph_id})
        MATCH (t:Entity {id: f.targetId, graphId: $graph_id})
        WHERE f.edgeType IS NOT NULL
        RETURN s.label AS subject, f.edgeType AS predicate, t.label AS object, f.confidence AS confidence
        """,
        graph_id=graph_id,
    )
    triples = [
        Triple(subject=r["subject"], predicate=r["predicate"], object=r["object"], derived=False, confidence=1.0)
        for r in stored_rows
    ]
    triples += [
        Triple(subject=r["subject"], predicate=r["predicate"], object=r["object"], derived=True, confidence=r["confidence"])
        for r in derived_rows
    ]
    return triples


def list_graphs(neo4j: Neo4jClient) -> list[GraphSummary]:
    """All graphs that have at least one entity, with counts, for the UI's
    graph switcher. A graph is created implicitly by ingesting into a new
    graphId — there is no separate "create empty graph" concept server-side."""
    rows = neo4j.run(
        """
        MATCH (e:Entity)
        WITH DISTINCT e.graphId AS graphId
        OPTIONAL MATCH (n:Entity {graphId: graphId})
        WITH graphId, count(n) AS nodeCount
        OPTIONAL MATCH (:Entity {graphId: graphId})-[r:RELATES {graphId: graphId}]->(:Entity {graphId: graphId})
        WITH graphId, nodeCount, count(r) AS edgeCount
        OPTIONAL MATCH (h:IngestEvent {graphId: graphId})
        RETURN graphId, nodeCount, edgeCount, toString(max(h.createdAt)) AS lastIngestAt
        ORDER BY lastIngestAt DESC
        """
    )
    return [
        GraphSummary(
            graph_id=row["graphId"], node_count=row["nodeCount"],
            edge_count=row["edgeCount"], last_ingest_at=row["lastIngestAt"],
        )
        for row in rows
    ]


def get_derived_facts(neo4j: Neo4jClient, graph_id: str) -> list[dict]:
    """Stored derived facts for a graph (fact text + confidence), for grounding
    the chat console in real, previously-derived reasoning results."""
    rows = neo4j.run(
        """
        MATCH (f:DerivedFact {graphId: $graph_id})
        RETURN f.fact AS fact, f.confidence AS confidence
        ORDER BY f.iteration DESC
        """,
        graph_id=graph_id,
    )
    return [{"fact": r["fact"], "confidence": r["confidence"]} for r in rows]


def get_entities_and_edges_for_reasoning(
    neo4j: Neo4jClient, graph_id: str
) -> tuple[list[ReasoningNode], list[ReasoningEdge]]:
    """Load the graph in the shape reasoning.engine.reason() expects."""
    record = get_graph(neo4j, graph_id)
    nodes = [ReasoningNode(id=n.id, label=n.label, type=n.type, salience=n.salience) for n in record.nodes]
    edges = [ReasoningEdge(id=e.id, source=e.source, target=e.target, type=e.type, weight=e.weight) for e in record.edges]
    return nodes, edges
