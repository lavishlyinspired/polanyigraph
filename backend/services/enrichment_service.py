"""Polanyi enrichment orchestration + :ImplicitFact persistence (PLAN.md §19.5).

:ImplicitFact is a third, distinct provenance layer -- kept separate from the
ontology-typed :Entity/:RELATES graph (extraction, real-data-only) and the
rule-derived :DerivedFact graph (reasoning/engine.py). Pending facts require
human-in-the-loop approval (§7.3) before they count as part of the graph;
rejected facts are kept (not deleted) so the audit trail of what an LLM
proposed and what a human rejected stays real and inspectable.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from db.neo4j_client import Neo4jClient
from enrichment.heuristics import ALL_HEURISTIC_MODULES
from enrichment.heuristics.base import HeuristicLLM, ImplicitFactCandidate
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

_VALID_STATUSES = {"pending", "approved", "rejected"}


def run_all_heuristics(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> list[ImplicitFactCandidate]:
    """PLAN.md §19.2: all 11 heuristics run together, not filtered by domain --
    one independent LLM call per heuristic against the same Base Graph +
    source text, with no data dependency between them, so they run
    concurrently rather than paying 11x sequential latency. A single
    heuristic's failure doesn't sink the whole enrichment pass -- it's
    dropped, same spirit as the "no valid anchors" drop rule inside
    run_heuristic."""
    candidates: list[ImplicitFactCandidate] = []
    with ThreadPoolExecutor(max_workers=len(ALL_HEURISTIC_MODULES)) as pool:
        futures = [
            pool.submit(module.run, llm, nodes=nodes, edges=edges, source_text=source_text)
            for module in ALL_HEURISTIC_MODULES
        ]
        for future in futures:
            try:
                result = future.result()
            except Exception:
                continue
            candidates.extend(result.candidates)
    return candidates


@dataclass(frozen=True)
class ImplicitFactRecord:
    id: str
    heuristic_type: str
    text: str
    confidence: float
    status: str
    anchor_entity_ids: tuple[str, ...]


def save_pending_facts(
    neo4j: Neo4jClient, *, graph_id: str, source_doc: str, candidates: list[ImplicitFactCandidate]
) -> list[str]:
    ids: list[str] = []
    for candidate in candidates:
        fact_id = f"{graph_id}:implicit-{uuid.uuid4().hex[:12]}"
        neo4j.run(
            """
            CREATE (f:ImplicitFact {
              id: $id, graphId: $graph_id, heuristicType: $heuristic_type,
              text: $text, confidence: $confidence, sourceDoc: $source_doc, status: 'pending'
            })
            WITH f
            UNWIND $anchor_ids AS aid
            MATCH (e:Entity {id: aid, graphId: $graph_id})
            MERGE (f)-[:ANCHORED_TO]->(e)
            """,
            id=fact_id,
            graph_id=graph_id,
            heuristic_type=candidate.heuristic_type,
            text=candidate.text,
            confidence=candidate.confidence,
            source_doc=source_doc,
            anchor_ids=list(candidate.anchor_entity_ids),
        )
        ids.append(fact_id)
    return ids


def _list_facts_by_status(neo4j: Neo4jClient, graph_id: str, status: str) -> list[ImplicitFactRecord]:
    rows = neo4j.run(
        """
        MATCH (f:ImplicitFact {graphId: $graph_id, status: $status})
        OPTIONAL MATCH (f)-[:ANCHORED_TO]->(e:Entity)
        WITH f, collect(e.id) AS anchorIds
        RETURN f.id AS id, f.heuristicType AS heuristicType, f.text AS text,
               f.confidence AS confidence, f.status AS status, anchorIds
        """,
        graph_id=graph_id,
        status=status,
    )
    return [
        ImplicitFactRecord(
            id=r["id"], heuristic_type=r["heuristicType"], text=r["text"],
            confidence=r["confidence"], status=r["status"], anchor_entity_ids=tuple(r["anchorIds"]),
        )
        for r in rows
    ]


def list_pending_facts(neo4j: Neo4jClient, graph_id: str) -> list[ImplicitFactRecord]:
    return _list_facts_by_status(neo4j, graph_id, "pending")


def list_approved_facts(neo4j: Neo4jClient, graph_id: str) -> list[ImplicitFactRecord]:
    return _list_facts_by_status(neo4j, graph_id, "approved")


def set_fact_status(neo4j: Neo4jClient, *, graph_id: str, fact_id: str, status: str) -> None:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}' -- must be one of {_VALID_STATUSES}.")
    neo4j.run(
        "MATCH (f:ImplicitFact {id: $fact_id, graphId: $graph_id}) SET f.status = $status",
        fact_id=fact_id,
        graph_id=graph_id,
        status=status,
    )
