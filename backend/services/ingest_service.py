"""Orchestrates extraction -> ontology validation -> Neo4j write with provenance.

Entity/edge ids are deterministic slugs of (graph_id, name) / (graph_id, source,
relation, target), so re-ingesting the same or an overlapping document is
idempotent: the same real-world entity mentioned twice MERGEs into one node
instead of duplicating, and repeated docs don't grow the graph unboundedly.
"""

from __future__ import annotations

import uuid

from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from extraction.pipeline import ExtractionResult, extract
from llm.client import LLMClient
from llm.embedder import EmbeddingClient
from ontology.loader import load_schema
from services import graph_service, history_service, summary_service, vector_search_service
from services.graph_service import GraphRecord
from services.ids import edge_id, entity_id


def ingest_text(
    *,
    neo4j: Neo4jClient,
    graphdb: GraphDBClient,
    llm: LLMClient,
    graph_id: str,
    text: str,
    source_doc: str,
    repository: str,
    extra_guidance: str = "",
    embedder: EmbeddingClient | None = None,
) -> tuple[GraphRecord, ExtractionResult]:
    schema = load_schema(graphdb, repository)
    result = extract(text, schema=schema, llm=llm, extra_guidance=extra_guidance)
    event_id = f"{graph_id}:evt-{uuid.uuid4().hex[:12]}"

    produced_entity_ids = []
    for entity in result.entities:
        eid = entity_id(graph_id, entity.name)
        graph_service.upsert_entity(
            neo4j,
            graph_id=graph_id,
            entity_id=eid,
            label=entity.name,
            type_=entity.type,
            source_doc=source_doc,
            extraction_confidence=entity.confidence,
        )
        produced_entity_ids.append(eid)

        # PLAN.md §20 item 3: synthesize the existing summary with this ingest's
        # source text into an updated one, accumulating context across ingests.
        existing_summary = graph_service.get_entity_summary(neo4j, graph_id=graph_id, entity_id=eid)
        new_summary = summary_service.generate_summary(
            llm, label=entity.name, type_=entity.type, existing_summary=existing_summary, new_context=text,
        )
        graph_service.update_entity_summary(neo4j, graph_id=graph_id, entity_id=eid, summary=new_summary)
        if embedder is not None:
            vector_search_service.index_entity_summary(
                neo4j, embedder, graph_id=graph_id, entity_id=eid, summary=new_summary,
            )

    for rel in result.relationships:
        graph_service.upsert_relationship(
            neo4j,
            graph_id=graph_id,
            edge_id=edge_id(graph_id, rel.source, rel.relation, rel.target),
            source_id=entity_id(graph_id, rel.source),
            target_id=entity_id(graph_id, rel.target),
            type_=rel.relation,
            weight=rel.confidence,
            produced_by_event_id=event_id,
        )

    history_service.record_ingest_event(
        neo4j,
        graph_id=graph_id,
        event_id=event_id,
        text=text,
        entity_count=len(result.entities),
        relationship_count=len(result.relationships),
        dropped_count=len(result.dropped),
        entity_ids=produced_entity_ids,
    )

    return graph_service.get_graph(neo4j, graph_id), result
