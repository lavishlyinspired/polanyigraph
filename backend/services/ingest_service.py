"""Orchestrates extraction -> ontology validation -> Neo4j write with provenance.

Entity/edge ids are deterministic slugs of (graph_id, name) / (graph_id, source,
relation, target), so re-ingesting the same or an overlapping document is
idempotent: the same real-world entity mentioned twice MERGEs into one node
instead of duplicating, and repeated docs don't grow the graph unboundedly.
"""

from __future__ import annotations

import uuid

from analytics.roles import resolver_for_repository
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from extraction.pipeline import ExtractionResult, extract
from llm.client import LLMClient
from llm.embedder import EmbeddingClient
from materialization.client import Neo4jGraphClient
from materialization.commands import StorageCommand
from materialization.policy import (
    MaterializationDecision,
    MaterializationPolicy,
    compute_fanout,
    find_introducing_relationship,
    plan_materialization,
)
from ontology.loader import load_schema
from services import entity_resolution_service, graph_service, history_service, summary_service, vector_search_service
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
    # Real extraction can label the same real-world entity with a different
    # (but ontology-related) subtype across documents ("stock corporation"
    # vs "corporation") -- see entity_resolution_service.check_for_duplicate's
    # docstring for the live-verified gap this closes. Reuses the schema
    # already loaded above for extraction, no extra GraphDB call.
    type_matches = schema.build_subclass_matcher()

    # PLAN Phase 3 (.claude/docs/research/2026-07-14-semantic-materialization
    # -engine-design.md): decide, per entity, whether it becomes a node (as
    # every extracted entity did before this) or is inlined as a property on
    # the one other entity it's related to -- fixes the real, live-verified
    # noise problem where a percentage or a date dominated centrality
    # rankings purely by co-occurring with every fact that cites one. Reuses
    # Phase 1's ontology-anchor role resolver unchanged.
    resolve_role = resolver_for_repository(schema)
    fanout = compute_fanout(result.relationships)
    decisions: dict[str, MaterializationDecision] = {}
    for entity in result.entities:
        entity_fanout = fanout.get(entity.name, 0)
        introducing = (
            find_introducing_relationship(entity.name, result.relationships)
            if entity_fanout == 1 else None
        )
        decisions[entity.name] = plan_materialization(entity, resolve_role(entity.type), entity_fanout, introducing)
    graph_client = Neo4jGraphClient(neo4j, graph_id=graph_id)

    produced_entity_ids = []
    for entity in result.entities:
        if decisions[entity.name].policy == MaterializationPolicy.PROPERTY:
            continue  # inlined onto the owning entity below, once relationships are processed
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
            # 2026-07-13 plan §11.2: cross-document entity resolution --
            # extraction has no memory of what's already in the graph, so a
            # name variation ("Acme Corp" vs "Acme Corporation") always
            # produces a second, separate node otherwise. Flags for human
            # confirmation, never silently merges (see
            # entity_resolution_service module docstring for why this
            # doesn't just use a plain cosine-similarity threshold).
            entity_resolution_service.check_for_duplicate(
                neo4j, graph_id=graph_id, entity_id=eid, entity_label=entity.name, entity_type=entity.type,
                type_matches=type_matches,
            )

    for rel in result.relationships:
        target_decision = decisions[rel.target]
        source_decision = decisions[rel.source]
        if target_decision.policy == MaterializationPolicy.PROPERTY and target_decision.attach_to_entity_name == rel.source:
            graph_client.execute(StorageCommand(
                operation="SET_PROPERTY",
                subject_id=entity_id(graph_id, rel.source),
                key=target_decision.property_key,
                value=rel.target,
            ))
            continue
        if source_decision.policy == MaterializationPolicy.PROPERTY and source_decision.attach_to_entity_name == rel.target:
            graph_client.execute(StorageCommand(
                operation="SET_PROPERTY",
                subject_id=entity_id(graph_id, rel.target),
                key=source_decision.property_key,
                value=rel.source,
            ))
            continue
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
