"""Custom neurosymbolic analytics (PLAN: plans/analytical-engine.md Slice 7).
Wired directly to data already produced by reasoning/engine.py (Rule,
DerivedFact) and Slice 1's activation node attribute -- no new
instrumentation needed upstream.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import networkx as nx

from reasoning.engine import DerivedFact, Rule


@dataclass(frozen=True)
class ActivationPatterns:
    high_activation_nodes: list[str]
    bottlenecks: list[str]
    mean_activation: float


def activation_patterns(graph: nx.DiGraph, threshold: float | None = None) -> ActivationPatterns:
    activations = {n: (graph.nodes[n].get("activation") or 0.0) for n in graph.nodes}
    values = list(activations.values())
    mean_activation = sum(values) / len(values) if values else 0.0
    cutoff = mean_activation if threshold is None else threshold
    high = sorted((n for n, a in activations.items() if a > cutoff), key=lambda n: -activations[n])
    bottlenecks = [n for n in high if graph.out_degree(n) == 0]
    return ActivationPatterns(high_activation_nodes=high, bottlenecks=bottlenecks, mean_activation=mean_activation)


@dataclass(frozen=True)
class RuleCoverage:
    fired_rule_ids: set[str]
    never_fired_rule_ids: set[str]
    fire_counts: dict[str, int]
    under_activated_rule_ids: set[str]


def rule_coverage(rules: list[Rule], derived_facts: list[DerivedFact]) -> RuleCoverage:
    fire_counts = Counter(f.rule_id for f in derived_facts)
    all_rule_ids = {r.id for r in rules}
    fired = {rid for rid in fire_counts if rid in all_rule_ids}
    never_fired = all_rule_ids - fired
    if fired:
        mean_fires = sum(fire_counts[rid] for rid in fired) / len(fired)
        under_activated = {rid for rid in fired if fire_counts[rid] < mean_fires}
    else:
        under_activated = set()
    return RuleCoverage(
        fired_rule_ids=fired,
        never_fired_rule_ids=never_fired,
        fire_counts={rid: fire_counts[rid] for rid in fired},
        under_activated_rule_ids=under_activated,
    )


@dataclass(frozen=True)
class ProofChainAnalysis:
    max_proof_depth: int
    rule_usage_frequency: dict[str, int]
    circular_fact_ids: set[str]


def proof_chain_analysis(derived_facts: list[DerivedFact]) -> ProofChainAnalysis:
    max_depth = max((len(f.proof_path) for f in derived_facts), default=0)
    rule_usage = dict(Counter(f.rule_id for f in derived_facts))

    chain_graph = nx.DiGraph()
    for f in derived_facts:
        chain_graph.add_edge(f.source_id, f.target_id, fact_id=f.id)
    circular_fact_ids: set[str] = set()
    for cycle in nx.simple_cycles(chain_graph):
        cycle_edges = list(zip(cycle, cycle[1:] + cycle[:1]))
        for u, v in cycle_edges:
            circular_fact_ids.add(chain_graph.edges[u, v]["fact_id"])

    return ProofChainAnalysis(max_proof_depth=max_depth, rule_usage_frequency=rule_usage, circular_fact_ids=circular_fact_ids)


@dataclass(frozen=True)
class ImpactedFact:
    fact_id: str
    depth: int


def fact_impact(derived_facts: list[DerivedFact], fact_id: str) -> list[ImpactedFact]:
    facts_by_id = {f.id: f for f in derived_facts}
    root = facts_by_id.get(fact_id)
    if root is None:
        return []

    by_source: dict[str, list[DerivedFact]] = {}
    for f in derived_facts:
        by_source.setdefault(f.source_id, []).append(f)

    impacted: list[ImpactedFact] = []
    seen = {fact_id}
    frontier = [root]
    depth = 1
    while frontier:
        next_frontier: list[DerivedFact] = []
        for f in frontier:
            for dependent in by_source.get(f.target_id, []):
                if dependent.id in seen:
                    continue
                seen.add(dependent.id)
                impacted.append(ImpactedFact(fact_id=dependent.id, depth=depth))
                next_frontier.append(dependent)
        frontier = next_frontier
        depth += 1
    return impacted
