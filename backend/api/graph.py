"""GET /graph/{graph_id} — read the real extracted+reasoned graph from Neo4j.

Also: manual Add Node / Add Edge (the Construct tab's graph-building
capability), reusing the same validation as real extraction -- a type or
relation that doesn't exist in the loaded ontology is rejected, and manually
added entities get the same deterministic id as extraction would, so a later
extraction of the same real-world entity MERGEs into it rather than
duplicating.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.dependencies import get_graphdb, get_neo4j
from app.schemas import ApiModel
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from ontology.loader import load_schema
from services import community_service, graph_service, history_service
from services.ids import edge_id as make_edge_id
from services.ids import entity_id as make_entity_id

router = APIRouter(tags=["graph"])


class NodeResponse(ApiModel):
    id: str
    label: str
    type: str
    activation: float | None = None
    derived: bool = False
    source_doc: str | None = None
    salience: float = 1.0
    properties: dict[str, str] = {}
    note: str = ""
    summary: str = ""
    community_id: int | None = None


class EdgeResponse(ApiModel):
    id: str
    source: str
    target: str
    type: str
    weight: float = 1.0
    valid_at: str | None = None
    invalid_at: str | None = None
    produced_by_event_id: str | None = None


class GraphResponse(ApiModel):
    nodes: list[NodeResponse]
    edges: list[EdgeResponse]


class GraphEdgesResponse(ApiModel):
    edges: list[EdgeResponse]


class IngestEventSummary(ApiModel):
    id: str
    text: str
    created_at: str


class NodeProvenanceResponse(ApiModel):
    events: list[IngestEventSummary]


@router.get("/graph/{graph_id}", response_model=GraphResponse, response_model_by_alias=True)
def get_graph(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> GraphResponse:
    record = graph_service.get_graph(neo4j, graph_id)
    return GraphResponse(
        nodes=[
            NodeResponse(
                id=n.id, label=n.label, type=n.type,
                activation=n.activation, derived=n.derived, source_doc=n.source_doc,
                salience=n.salience, properties=n.properties, note=n.note, summary=n.summary,
                community_id=n.community_id,
            )
            for n in record.nodes
        ],
        edges=[
            EdgeResponse(
                id=e.id, source=e.source, target=e.target, type=e.type, weight=e.weight,
                valid_at=e.valid_at, invalid_at=e.invalid_at, produced_by_event_id=e.produced_by_event_id,
            )
            for e in record.edges
        ],
    )


@router.get("/graph/{graph_id}/nodes/{node_id}/provenance", response_model=NodeProvenanceResponse, response_model_by_alias=True)
def get_node_provenance(graph_id: str, node_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> NodeProvenanceResponse:
    events = history_service.get_entity_provenance(neo4j, graph_id=graph_id, entity_id=node_id)
    return NodeProvenanceResponse(
        events=[IngestEventSummary(id=e.id, text=e.text, created_at=e.created_at) for e in events]
    )


@router.get("/graph/{graph_id}/relationships/history", response_model=GraphEdgesResponse, response_model_by_alias=True)
def get_relationship_history(
    graph_id: str,
    source_id: str = Query(alias="sourceId"),
    type_: str = Query(alias="type"),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> "GraphEdgesResponse":
    """UI_PLAN.md §9.2.2: current + invalidated edges for a (source, relation
    type), for a fact-history/timeline view -- get_graph() stays current-only."""
    edges = graph_service.get_relationship_history(neo4j, graph_id=graph_id, source_id=source_id, type_=type_)
    return GraphEdgesResponse(
        edges=[
            EdgeResponse(
                id=e.id, source=e.source, target=e.target, type=e.type, weight=e.weight,
                valid_at=e.valid_at, invalid_at=e.invalid_at, produced_by_event_id=e.produced_by_event_id,
            )
            for e in edges
        ]
    )


class AddNodeRequest(ApiModel):
    label: str
    type: str


class AddEdgeRequest(ApiModel):
    source_id: str
    target_id: str
    type: str


@router.post("/graph/{graph_id}/nodes", response_model=NodeResponse, response_model_by_alias=True)
def add_node(
    graph_id: str,
    request: AddNodeRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    graphdb: GraphDBClient = Depends(get_graphdb),
    settings: Settings = Depends(get_settings),
) -> NodeResponse:
    schema = load_schema(graphdb, settings.graphdb_repository)
    if not schema.is_known_type(request.type):
        raise HTTPException(status_code=400, detail=f"'{request.type}' is not a known type in the loaded ontology.")

    entity_id = make_entity_id(graph_id, request.label)
    graph_service.upsert_entity(
        neo4j, graph_id=graph_id, entity_id=entity_id, label=request.label,
        type_=request.type, source_doc="manual-entry", extraction_confidence=1.0,
    )
    record = graph_service.get_graph(neo4j, graph_id)
    node = next(n for n in record.nodes if n.id == entity_id)
    return NodeResponse(
        id=node.id, label=node.label, type=node.type, activation=node.activation, derived=node.derived,
        source_doc=node.source_doc, salience=node.salience, properties=node.properties, note=node.note,
        summary=node.summary, community_id=node.community_id,
    )


class UpdateNodeRequest(ApiModel):
    salience: float | None = None
    properties: dict[str, str] | None = None
    note: str | None = None


@router.patch("/graph/{graph_id}/nodes/{node_id}", response_model=NodeResponse, response_model_by_alias=True)
def update_node(
    graph_id: str,
    node_id: str,
    request: UpdateNodeRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> NodeResponse:
    graph_service.update_entity_metadata(
        neo4j, graph_id=graph_id, entity_id=node_id,
        salience=request.salience, properties=request.properties, note=request.note,
    )
    record = graph_service.get_graph(neo4j, graph_id)
    node = next((n for n in record.nodes if n.id == node_id), None)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in graph '{graph_id}'.")
    return NodeResponse(
        id=node.id, label=node.label, type=node.type, activation=node.activation, derived=node.derived,
        source_doc=node.source_doc, salience=node.salience, properties=node.properties, note=node.note,
        summary=node.summary, community_id=node.community_id,
    )


@router.post("/graph/{graph_id}/edges", response_model=EdgeResponse, response_model_by_alias=True)
def add_edge(
    graph_id: str,
    request: AddEdgeRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    graphdb: GraphDBClient = Depends(get_graphdb),
    settings: Settings = Depends(get_settings),
) -> EdgeResponse:
    schema = load_schema(graphdb, settings.graphdb_repository)
    known_properties = {p.lower() for p in schema.property_labels}
    if request.type.lower() not in known_properties:
        raise HTTPException(status_code=400, detail=f"'{request.type}' is not a known relation in the loaded ontology.")

    record = graph_service.get_graph(neo4j, graph_id)
    node_ids = {n.id for n in record.nodes}
    if request.source_id not in node_ids or request.target_id not in node_ids:
        raise HTTPException(status_code=400, detail="source_id/target_id must reference existing entities in this graph.")

    source = next(n for n in record.nodes if n.id == request.source_id)
    target = next(n for n in record.nodes if n.id == request.target_id)
    edge_id = make_edge_id(graph_id, source.label, request.type, target.label)
    graph_service.upsert_relationship(
        neo4j, graph_id=graph_id, edge_id=edge_id,
        source_id=request.source_id, target_id=request.target_id, type_=request.type, weight=1.0,
        produced_by_event_id="manual-entry",
    )
    edge = next(e for e in graph_service.get_graph(neo4j, graph_id).edges if e.id == edge_id)
    return EdgeResponse(
        id=edge.id, source=edge.source, target=edge.target, type=edge.type, weight=edge.weight,
        valid_at=edge.valid_at, invalid_at=edge.invalid_at, produced_by_event_id=edge.produced_by_event_id,
    )


class CommunityMemberResponse(ApiModel):
    entity_id: str
    label: str
    community_id: int


class CommunitiesResponse(ApiModel):
    members: list[CommunityMemberResponse]


def _to_community_response(members: list) -> CommunitiesResponse:
    return CommunitiesResponse(
        members=[CommunityMemberResponse(entity_id=m.entity_id, label=m.label, community_id=m.community_id) for m in members]
    )


@router.post("/graph/{graph_id}/communities", response_model=CommunitiesResponse, response_model_by_alias=True)
def detect_communities(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> CommunitiesResponse:
    """PLAN.md §20 item 5: runs Neo4j GDS Louvain over the real graph_id-scoped
    subgraph, writes communityId onto each :Entity."""
    members = community_service.detect_communities(neo4j, graph_id)
    return _to_community_response(members)


@router.get("/graph/{graph_id}/communities", response_model=CommunitiesResponse, response_model_by_alias=True)
def get_communities(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> CommunitiesResponse:
    members = community_service.get_communities(neo4j, graph_id)
    return _to_community_response(members)
