"""GET /graphs — list all graphs (for the UI's graph switcher).

Separate from graph.py (singular) which reads one graph's nodes/edges.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_neo4j
from app.schemas import ApiModel
from db.neo4j_client import Neo4jClient
from services import graph_service

router = APIRouter(tags=["graphs"])


class GraphSummaryResponse(ApiModel):
    graph_id: str
    node_count: int
    edge_count: int
    last_ingest_at: str | None


class GraphsResponse(ApiModel):
    graphs: list[GraphSummaryResponse]


@router.get("/graphs", response_model=GraphsResponse, response_model_by_alias=True)
def list_graphs(neo4j: Neo4jClient = Depends(get_neo4j)) -> GraphsResponse:
    graphs = graph_service.list_graphs(neo4j)
    return GraphsResponse(
        graphs=[
            GraphSummaryResponse(
                graph_id=g.graph_id, node_count=g.node_count,
                edge_count=g.edge_count, last_ingest_at=g.last_ingest_at,
            )
            for g in graphs
        ]
    )
