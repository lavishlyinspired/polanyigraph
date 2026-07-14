"""Named graph projections: materialize a graphId-scoped subgraph into a
plain networkx.DiGraph, no third node/edge model (PLAN: plans/
analytical-engine.md's "Data model mapping" and "Graph-agnostic,
concretely" sections). Algorithms only ever see the resulting nx.DiGraph --
never a Neo4jClient -- so this module is the only place in backend/analytics
that imports the store.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from db.neo4j_client import Neo4jClient
from services import graph_service
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

_REGISTRY: dict[str, "NamedProjection"] = {}


class EmptyGraphError(Exception):
    pass


def build_graph(nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for n in nodes:
        graph.add_node(
            n.id,
            label=n.label,
            type=n.type,
            salience=n.salience,
            activation=n.activation,
            derived=n.derived,
            community_id=n.community_id,
            **n.properties,
        )
    for e in edges:
        graph.add_edge(e.source, e.target, id=e.id, type=e.type, weight=e.weight)
    return graph


@dataclass(frozen=True)
class NamedProjection:
    name: str
    graph_id: str
    graph: nx.DiGraph

    @classmethod
    def create(cls, neo4j: Neo4jClient, *, name: str, graph_id: str) -> "NamedProjection":
        record = graph_service.get_graph(neo4j, graph_id)
        if not record.nodes:
            raise EmptyGraphError(f"Graph '{graph_id}' has no entities to project.")
        projection = cls(name=name, graph_id=graph_id, graph=build_graph(record.nodes, record.edges))
        _REGISTRY[name] = projection
        return projection

    @staticmethod
    def get(name: str) -> "NamedProjection | None":
        return _REGISTRY.get(name)

    @staticmethod
    def list_all() -> list["NamedProjection"]:
        return list(_REGISTRY.values())

    @staticmethod
    def drop(name: str) -> bool:
        return _REGISTRY.pop(name, None) is not None
