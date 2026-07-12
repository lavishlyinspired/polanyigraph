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

# edge_type, source_type, target_type -> bool. Default is permissive (no
# domain/range gate at all), matching the original, dependency-free
# behavior. Callers with a live ontology (see ontology/schema.py
# build_domain_range_matcher) can inject the real rdfs:domain/rdfs:range
# check without coupling this pure module to GraphDB.
DomainRangeChecker = Callable[[str, str, str], bool]


def _exact_match(candidate: str, expected: str) -> bool:
    return candidate == expected


def _always_valid(edge_type: str, source_type: str, target_type: str) -> bool:
    return True


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
    # Populated when >1 rule fires on the SAME edge in the same iteration
    # (e.g. a hand-authored rule and a mined rule both watching the same
    # edge_type/source_type/target_type combo -- a real scenario once rule
    # mining exists). Confidence is then a noisy-OR combination across all
    # contributing rules rather than either rule's confidence alone, and
    # this field records which rules contributed so the proof trail stays
    # honest about it. Single-element (this fact's own rule) in the common
    # single-rule case, never empty.
    supporting_rule_ids: tuple[str, ...] = field(default=())
    # Internal bookkeeping, not for display: the per-(rule, edge) fact ids
    # that were merged into this one (or just this fact's own id, in the
    # single-rule case). run_inference/reason() use this to mark EVERY
    # contributing rule's evaluation as "already derived" in later
    # iterations, not just the merged fact's own id -- otherwise the same
    # rules would re-fire and mint a fresh aggregated fact every iteration.
    contributing_fact_ids: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class InferenceTraceEntry:
    """One (rule, edge) evaluation -- whether it fired or was skipped, and why.
    The prototype's Reason tab shows both, not just what fired (PLAN.md §16
    Phase 9 UI parity)."""
    rule_name: str
    edge_type: str
    source_label: str
    target_label: str
    source_activation: float
    threshold: float
    fired: bool
    iteration: int
    skip_reason: str | None = None
    fact_id: str | None = None


@dataclass(frozen=True)
class ReasoningResult:
    activation: dict[str, float]
    facts: tuple[DerivedFact, ...]
    iterations: int
    converged_by: ConvergedBy
    trace: tuple[InferenceTraceEntry, ...] = field(default=())


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


@dataclass(frozen=True)
class _Firing:
    """One rule's would-fire evaluation on one edge, held back from becoming
    a DerivedFact until the aggregation pass (see run_inference) decides
    whether it's the only rule that fired on this edge this iteration, or
    one of several that need to be combined."""
    rule: Rule
    source: Node
    target: Node
    proof_path: tuple[ProofStep, ...]
    chain_confidence: float
    fact_id: str


def _aggregate_firings(edge_id: str, firings: list[_Firing], *, iteration: int) -> DerivedFact:
    """Reduce one-or-more rules firing on the SAME edge this iteration to a
    single DerivedFact. Single firing: unchanged from the pre-aggregation
    behavior (same id format, same confidence). Multiple firings: noisy-OR
    combination (independent corroborating signals -> higher, still-bounded
    confidence) rather than picking a winner or silently dropping the rest;
    the highest-confidence firing's rule/proof_path represents the merged
    fact's primary text, all contributing rules are recorded either way."""
    primary = max(firings, key=lambda f: f.chain_confidence)
    contributing_fact_ids = tuple(f.fact_id for f in firings)
    supporting_rule_ids = tuple(f.rule.id for f in firings)

    if len(firings) == 1:
        confidence = primary.chain_confidence
        fact_id = primary.fact_id
    else:
        product_of_complements = 1.0
        for f in firings:
            product_of_complements *= (1.0 - f.chain_confidence)
        confidence = 1.0 - product_of_complements
        fact_id = f"fact-agg-{edge_id}"

    return DerivedFact(
        id=fact_id,
        rule_id=primary.rule.id,
        rule_name=primary.rule.name,
        source_id=primary.source.id,
        target_id=primary.target.id,
        fact=primary.rule.description.replace("{source}", primary.source.label).replace("{target}", primary.target.label),
        confidence=min(1.0, confidence),
        iteration=iteration,
        proof_path=primary.proof_path,
        supporting_rule_ids=supporting_rule_ids,
        contributing_fact_ids=contributing_fact_ids,
    )


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
    domain_range_check: DomainRangeChecker = _always_valid,
) -> tuple[list[DerivedFact], list[InferenceTraceEntry]]:
    """Returns (new_facts, trace) -- trace covers every (rule, edge) pair whose
    types match, fired or not, so the UI can show what was tried and why it
    was skipped, not just what fired.

    Two passes: (1) evaluate every (rule, edge) pair exactly as before,
    logging every trace entry immediately; would-fire evaluations are held
    as _Firing candidates, keyed by edge.id, instead of becoming a
    DerivedFact right away. (2) reduce each edge's candidate list to exactly
    one DerivedFact via _aggregate_firings -- a no-op for the common
    single-rule-per-edge case, a noisy-OR combination when >1 rule fires on
    the same edge this iteration."""
    by_id = {n.id: n for n in nodes}
    trace: list[InferenceTraceEntry] = []
    candidates: dict[str, list[_Firing]] = {}

    for rule in rules:
        for edge in edges:
            if edge.type != rule.edge_type:
                continue
            src = by_id.get(edge.source)
            tgt = by_id.get(edge.target)
            if src is None or tgt is None:
                continue
            if not type_matches(src.type, rule.source_type) or not type_matches(tgt.type, rule.target_type):
                trace.append(
                    InferenceTraceEntry(
                        rule_name=rule.name, edge_type=edge.type,
                        source_label=src.label, target_label=tgt.label,
                        source_activation=activation.get(src.id, 0.0), threshold=rule.threshold,
                        fired=False, iteration=iteration,
                        skip_reason=f'type mismatch: "{src.type}"/"{tgt.type}" vs rule\'s "{rule.source_type}"/"{rule.target_type}"',
                    )
                )
                continue

            premise = activation.get(src.id, 0.0)
            if premise < rule.threshold:
                trace.append(
                    InferenceTraceEntry(
                        rule_name=rule.name, edge_type=edge.type,
                        source_label=src.label, target_label=tgt.label,
                        source_activation=premise, threshold=rule.threshold,
                        fired=False, iteration=iteration,
                        skip_reason=f"activation {premise:.2f} below threshold {rule.threshold:.2f}",
                    )
                )
                continue

            fact_id = f"fact-{rule.id}-{edge.id}"
            if fact_id in existing_fact_ids:
                trace.append(
                    InferenceTraceEntry(
                        rule_name=rule.name, edge_type=edge.type,
                        source_label=src.label, target_label=tgt.label,
                        source_activation=premise, threshold=rule.threshold,
                        fired=False, iteration=iteration, skip_reason="already derived",
                    )
                )
                continue

            if not domain_range_check(edge.type, src.type, tgt.type):
                trace.append(
                    InferenceTraceEntry(
                        rule_name=rule.name, edge_type=edge.type,
                        source_label=src.label, target_label=tgt.label,
                        source_activation=premise, threshold=rule.threshold,
                        fired=False, iteration=iteration,
                        skip_reason=f'ontology domain/range violation: "{edge.type}" does not accept "{src.type}" -> "{tgt.type}" per the loaded schema',
                    )
                )
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
            chain_conf = min(1.0, chain_conf)

            candidates.setdefault(edge.id, []).append(
                _Firing(rule=rule, source=src, target=tgt, proof_path=proof_path, chain_confidence=chain_conf, fact_id=fact_id)
            )
            trace.append(
                InferenceTraceEntry(
                    rule_name=rule.name, edge_type=edge.type,
                    source_label=src.label, target_label=tgt.label,
                    source_activation=premise, threshold=rule.threshold,
                    fired=True, iteration=iteration, fact_id=fact_id,
                )
            )

    new_facts = [_aggregate_firings(edge_id, firings, iteration=iteration) for edge_id, firings in candidates.items()]
    return new_facts, trace


def feed_back_activation(
    activation: dict[str, float], facts: list[DerivedFact], *, feedback_gain: float,
) -> dict[str, float]:
    """Derived facts' targets gain persistent activation. Pure function --
    returns a new dict, doesn't mutate the input (mirrors the feedback phase
    previously inlined in reason()'s loop; also usable standalone for the
    Reason tab's manual "Feed Back" step)."""
    boosted = dict(activation)
    for fact in facts:
        boosted[fact.target_id] = min(1.0, boosted.get(fact.target_id, 0.0) + fact.confidence * feedback_gain)
    return boosted


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
    domain_range_check: DomainRangeChecker = _always_valid,
) -> ReasoningResult:
    """Run the persistent-activation neurosymbolic loop until convergence."""
    activation: dict[str, float] = {}
    all_facts: list[DerivedFact] = []
    all_trace: list[InferenceTraceEntry] = []
    existing_ids: set[str] = set()
    facts_by_target: dict[str, DerivedFact] = {}
    converged_by: ConvergedBy = "max_iterations"
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        prev = dict(activation)
        # Neural: spread, seeded with persisted (fed-back) activation.
        activation = spread_activation(nodes, edges, source_id, decay=decay, seed=activation)

        # Symbolic: fire rules over the current activation.
        new_facts, trace = run_inference(
            nodes, edges, rules, activation,
            iteration=iteration,
            existing_fact_ids=frozenset(existing_ids),
            facts_by_target=facts_by_target,
            type_matches=type_matches,
            domain_range_check=domain_range_check,
        )
        all_trace.extend(trace)

        # Feedback: derived targets gain persistent activation.
        activation = feed_back_activation(activation, new_facts, feedback_gain=feedback_gain)
        for fact in new_facts:
            existing_ids.add(fact.id)
            # Every rule that contributed to this fact (1 in the common case,
            # >1 when aggregated) must be marked derived, not just the
            # merged fact's own id -- otherwise the same rules re-fire next
            # iteration and mint a fresh aggregated fact every time.
            existing_ids.update(fact.contributing_fact_ids)
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
        trace=tuple(all_trace),
    )
