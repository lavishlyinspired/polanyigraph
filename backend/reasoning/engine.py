"""Neurosymbolic reasoning engine (implements PLAN.md §8.4).

Corrects the prototype's cosmetic loop:
  * activation PERSISTS across iterations (feedback seeds the next spread) so
    derived facts can trigger further rules -> genuine multi-hop reasoning;
  * spread is DIRECTED and consistent with rule evaluation;
  * spread is a max-activation FIXPOINT (order-independent), not a BFS sweep;
  * convergence = (no new facts) AND (activation delta < epsilon), capped;
  * a single confidence calculus: fact.confidence = activation(premise) * rule.weight,
    and along a proof chain confidence is the bounded product.

Domain-agnostic: nodes carry a ``type`` string that comes from the loaded
ontology; rules reference those type strings. No domain is hardcoded.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Literal

ConvergedBy = Literal["fixpoint", "max_iterations"]

# candidate_type, expected_type -> bool. Default is exact equality (the
# original, dependency-free behavior). Callers with a live ontology (see
# ontology/schema.py build_subclass_matcher) can inject subclass-aware
# matching without coupling this pure module to GraphDB.
TypeMatcher = Callable[[str, str], bool]


def _exact_match(candidate: str, expected: str) -> bool:
    return candidate == expected


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    type: str
    salience: float = 1.0


@dataclass(frozen=True)
class Edge:
    id: str
    source: str
    target: str
    type: str
    weight: float = 1.0


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    edge_type: str
    source_type: str
    target_type: str
    threshold: float
    weight: float = 1.0
    description: str = "{source} -> {target}"


@dataclass(frozen=True)
class ProofStep:
    rule_name: str
    edge_type: str
    source_label: str
    target_label: str
    premise_activation: float
    iteration: int
    # Set when the rule fired via ontology-aware matching rather than an exact
    # type match (e.g. "commercial bank" IS-A "organization") -- makes the
    # otherwise-invisible subclass resolution visible in the UI.
    type_resolution: str | None = None


@dataclass(frozen=True)
class DerivedFact:
    id: str
    rule_id: str
    rule_name: str
    source_id: str
    target_id: str
    fact: str
    confidence: float
    iteration: int
    proof_path: tuple[ProofStep, ...] = field(default=())


@dataclass(frozen=True)
class ReasoningResult:
    activation: dict[str, float]
    facts: tuple[DerivedFact, ...]
    iterations: int
    converged_by: ConvergedBy


def spread_activation(
    nodes: list[Node],
    edges: list[Edge],
    source_id: str,
    *,
    decay: float,
    seed: dict[str, float] | None = None,
) -> dict[str, float]:
    """Directed max-activation fixpoint. ``seed`` carries persisted activation."""
    salience = {n.id: n.salience for n in nodes}
    activation: dict[str, float] = dict(seed or {})
    activation[source_id] = max(activation.get(source_id, 0.0), 1.0)

    changed = True
    while changed:
        changed = False
        for edge in edges:
            a_src = activation.get(edge.source, 0.0)
            if a_src <= 0.0:
                continue
            candidate = a_src * decay * edge.weight * salience.get(edge.target, 1.0)
            if candidate > activation.get(edge.target, 0.0) + 1e-12:
                activation[edge.target] = candidate
                changed = True
    return activation


def _proof_path_for(
    premise_activation: dict[str, DerivedFact],
    source_id: str,
    step: ProofStep,
) -> tuple[ProofStep, ...]:
    prior = premise_activation.get(source_id)
    if prior is None:
        return (step,)
    return (*prior.proof_path, step)


def _type_resolution_note(source_type: str, rule_source_type: str, target_type: str, rule_target_type: str) -> str | None:
    """Human-readable explanation when a rule fired on types that don't match
    exactly (i.e. type_matches returned True via an ontology-aware matcher,
    not identity). Generic wording since run_inference only knows a match
    happened, not the matcher's internal reasoning."""
    notes = []
    if source_type.lower() != rule_source_type.lower():
        notes.append(f'"{source_type}" is-a "{rule_source_type}"')
    if target_type.lower() != rule_target_type.lower():
        notes.append(f'"{target_type}" is-a "{rule_target_type}"')
    return "; ".join(notes) if notes else None


def run_inference(
    nodes: list[Node],
    edges: list[Edge],
    rules: list[Rule],
    activation: dict[str, float],
    *,
    iteration: int,
    existing_fact_ids: frozenset[str],
    facts_by_target: dict[str, DerivedFact],
    type_matches: TypeMatcher = _exact_match,
) -> list[DerivedFact]:
    by_id = {n.id: n for n in nodes}
    new_facts: list[DerivedFact] = []

    for rule in rules:
        for edge in edges:
            if edge.type != rule.edge_type:
                continue
            src = by_id.get(edge.source)
            tgt = by_id.get(edge.target)
            if src is None or tgt is None:
                continue
            if not type_matches(src.type, rule.source_type) or not type_matches(tgt.type, rule.target_type):
                continue

            premise = activation.get(src.id, 0.0)
            if premise < rule.threshold:
                continue

            fact_id = f"fact-{rule.id}-{edge.id}"
            if fact_id in existing_fact_ids:
                continue

            step = ProofStep(
                rule_name=rule.name,
                edge_type=edge.type,
                source_label=src.label,
                target_label=tgt.label,
                premise_activation=premise,
                iteration=iteration,
                type_resolution=_type_resolution_note(src.type, rule.source_type, tgt.type, rule.target_type),
            )
            proof_path = _proof_path_for(facts_by_target, src.id, step)
            chain_conf = premise * rule.weight
            for prior_step in proof_path[:-1]:
                chain_conf *= prior_step.premise_activation

            new_facts.append(
                DerivedFact(
                    id=fact_id,
                    rule_id=rule.id,
                    rule_name=rule.name,
                    source_id=src.id,
                    target_id=tgt.id,
                    fact=rule.description.replace("{source}", src.label).replace("{target}", tgt.label),
                    confidence=min(1.0, chain_conf),
                    iteration=iteration,
                    proof_path=proof_path,
                )
            )
    return new_facts


def reason(
    nodes: list[Node],
    edges: list[Edge],
    rules: list[Rule],
    source_id: str,
    *,
    decay: float = 0.45,
    epsilon: float = 1e-3,
    max_iterations: int = 10,
    feedback_gain: float = 0.5,
    type_matches: TypeMatcher = _exact_match,
) -> ReasoningResult:
    """Run the persistent-activation neurosymbolic loop until convergence."""
    activation: dict[str, float] = {}
    all_facts: list[DerivedFact] = []
    existing_ids: set[str] = set()
    facts_by_target: dict[str, DerivedFact] = {}
    converged_by: ConvergedBy = "max_iterations"
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        prev = dict(activation)
        # Neural: spread, seeded with persisted (fed-back) activation.
        activation = spread_activation(nodes, edges, source_id, decay=decay, seed=activation)

        # Symbolic: fire rules over the current activation.
        new_facts = run_inference(
            nodes, edges, rules, activation,
            iteration=iteration,
            existing_fact_ids=frozenset(existing_ids),
            facts_by_target=facts_by_target,
            type_matches=type_matches,
        )

        # Feedback: derived targets gain persistent activation.
        for fact in new_facts:
            boosted = min(1.0, activation.get(fact.target_id, 0.0) + fact.confidence * feedback_gain)
            activation[fact.target_id] = boosted
            existing_ids.add(fact.id)
            facts_by_target[fact.target_id] = fact
        all_facts.extend(new_facts)

        delta = max((abs(activation.get(k, 0.0) - prev.get(k, 0.0)) for k in set(activation) | set(prev)), default=0.0)
        if not new_facts and delta < epsilon:
            converged_by = "fixpoint"
            break

    return ReasoningResult(
        activation=activation,
        facts=tuple(all_facts),
        iterations=iteration,
        converged_by=converged_by,
    )
