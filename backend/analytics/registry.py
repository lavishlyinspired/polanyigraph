"""AlgorithmRegistry: name -> algorithm function with metadata, replacing
Slice 1's hardcoded single-algorithm dispatch in api/analytics.py (PLAN:
plans/analytical-engine.md Slice 2). default_registry is populated with
every algorithm as it's added slice by slice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import networkx as nx

from analytics.algorithms.centrality import betweenness_centrality, closeness_centrality, degree_centrality, pagerank


@dataclass(frozen=True)
class AlgorithmSpec:
    name: str
    category: str
    func: Callable[[nx.DiGraph], dict[str, float]]
    params: dict[str, Any] = field(default_factory=dict)
    chart_type: str | None = None


class AlgorithmRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, AlgorithmSpec] = {}

    def register(self, spec: AlgorithmSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> AlgorithmSpec | None:
        return self._specs.get(name)

    def list(self) -> list[AlgorithmSpec]:
        return list(self._specs.values())


default_registry = AlgorithmRegistry()
default_registry.register(AlgorithmSpec(name="degree_centrality", category="centrality", func=degree_centrality, chart_type="bar"))
default_registry.register(AlgorithmSpec(name="pagerank", category="centrality", func=pagerank, params={"alpha": 0.85}, chart_type="bar"))
default_registry.register(AlgorithmSpec(name="betweenness_centrality", category="centrality", func=betweenness_centrality, chart_type="bar"))
default_registry.register(AlgorithmSpec(name="closeness_centrality", category="centrality", func=closeness_centrality, chart_type="bar"))
