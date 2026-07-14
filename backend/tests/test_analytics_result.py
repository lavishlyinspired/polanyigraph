"""Unit test for AlgorithmResult.persist (pure -- fake store, no DB)."""

from __future__ import annotations

from analytics.projection import NamedProjection
from analytics.result import AlgorithmResult
import networkx as nx


class _FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple[NamedProjection, str, dict[str, float]]] = []

    def write_scores(self, projection: NamedProjection, property_name: str, scores: dict[str, float]) -> None:
        self.calls.append((projection, property_name, scores))


def test_persist_delegates_to_the_store_with_projection_and_scores():
    projection = NamedProjection(name="p1", graph_id="g1", graph=nx.DiGraph())
    result = AlgorithmResult(algorithm="degree_centrality", projection=projection, node_scores={"a": 0.5})
    store = _FakeStore()

    result.persist(store, "centralityScore")

    assert store.calls == [(projection, "centralityScore", {"a": 0.5})]
