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
from ontology.loader import load_schema
from services import graph_service, history_service
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
) -> tuple[GraphRecord, ExtractionResult]:
    schema = load_schema(graphdb, repository)
    result = extract(text, schema=schema, llm=llm)

    for entity in result.entities:
        graph_service.upsert_entity(
            neo4j,
            graph_id=graph_id,
            entity_id=entity_id(graph_id, entity.name),
            label=entity.name,
            type_=entity.type,
            source_doc=source_doc,
            extraction_confidence=entity.confidence,
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
        )

    history_service.record_ingest_event(
        neo4j,
        graph_id=graph_id,
        event_id=f"{graph_id}:evt-{uuid.uuid4().hex[:12]}",
        text=text,
        entity_count=len(result.entities),
        relationship_count=len(result.relationships),
        dropped_count=len(result.dropped),
    )

    return graph_service.get_graph(neo4j, graph_id), result
