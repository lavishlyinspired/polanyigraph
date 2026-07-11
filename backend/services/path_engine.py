"""BFS path-finding between graph nodes with explainable proof strings.

Ported from the prototype (docs/src/lib/engine.ts findPath). Uses the real
graph data (nodes + edges from Neo4j), never a demo dataset.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from services.graph_service import GraphNodeRecord, GraphEdgeRecord


@dataclass(frozen=True)
class PathEdge:
    source: str
    target: str
    label: str


@dataclass(frozen=True)
class PathResult:
    found: bool
    path: list[str]
    edges: list[PathEdge]
    proof: str
    error: str | None = None


def find_path(
    source_label: str,
    target_label: str,
    nodes: list[GraphNodeRecord],
    edges: list[GraphEdgeRecord],
) -> PathResult:
    """BFS shortest path between two nodes by label (case-insensitive).

    Returns the path as a list of labels, the traversed edges, and a
    human-readable proof string like:
        ``A →[edgeType]→ B →[edgeType]→ C``
    """
    source_label = source_label.strip()
    target_label = target_label.strip()
    if not source_label or not target_label:
        return PathResult(found=False, path=[], edges=[], proof="", error="Source and target labels required.")

    by_id = {n.id: n for n in nodes}
    # Build adjacency: id -> list[(neighbor_id, edge_label)]
    adj: dict[str, list[tuple[str, str]]] = {}
    for e in edges:
        adj.setdefault(e.source, []).append((e.target, e.type))
        adj.setdefault(e.target, []).append((e.source, e.type))

    # Find source and target nodes by label (case-insensitive)
    source_node = next((n for n in nodes if n.label.lower() == source_label.lower()), None)
    target_node = next((n for n in nodes if n.label.lower() == target_label.lower()), None)

    if source_node is None:
        return PathResult(found=False, path=[], edges=[], proof="", error=f'Node "{source_label}" not found.')
    if target_node is None:
        return PathResult(found=False, path=[], edges=[], proof="", error=f'Node "{target_label}" not found.')
    if source_node.id == target_node.id:
        return PathResult(found=True, path=[source_node.label], edges=[], proof=source_node.label)

    # BFS
    queue: deque[tuple[str, list[str], list[PathEdge]]] = deque()
    queue.append((source_node.id, [source_node.label], []))
    visited: set[str] = {source_node.id}

    while queue:
        current_id, path, path_edges = queue.popleft()
        for neighbor_id, edge_label in adj.get(current_id, []):
            if neighbor_id in visited:
                continue
            visited.add(neighbor_id)
            neighbor = by_id.get(neighbor_id)
            if neighbor is None:
                continue
            new_path = path + [neighbor.label]
            new_edges = path_edges + [PathEdge(source=current_id, target=neighbor_id, label=edge_label)]
            if neighbor_id == target_node.id:
                proof = _build_proof(new_path, new_edges)
                return PathResult(found=True, path=new_path, edges=new_edges, proof=proof)
            queue.append((neighbor_id, new_path, new_edges))

    return PathResult(
        found=False,
        path=[],
        edges=[],
        proof="",
        error=f'No path found between "{source_label}" and "{target_label}".',
    )


def _build_proof(path: list[str], edges: list[PathEdge]) -> str:
    """Build human-readable proof: ``A →[edgeType]→ B →[edgeType]→ C``."""
    parts: list[str] = [path[0]]
    for i, edge in enumerate(edges):
        parts.append(f" →[{edge.label}]→ {path[i + 1]}")
    return "".join(parts)
