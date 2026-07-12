# Rule Mining + Compound-Query Implementation Plan

> **Created**: July 13, 2026
> **Status**: Plan — not implemented
> **Supersedes in scope**: the GNN/benchmark parts of `research/2025-07-12-research-analysis-and-update-plan.md`; keeps that doc's resource analysis, replaces its Phase A/C/D implementation with this.
> **Builds on**: `NESYM_RESEARCH_INTEGRATION_PLAN.md`'s Tier 1/2 items.
> **Grounded in real code**: `backend/reasoning/engine.py`, `backend/services/rules_store.py`, `backend/agents/graph.py`, `backend/agents/state.py` — read in full before writing this plan; every file/function referenced below exists today.

---

## 0. What this plan covers, and what it deliberately doesn't

Five features, ordered by dependency and risk:

0. **Skill-graph-driven selection** — replaces a hardcoded lookup table with the graph-based selection mechanism that already runs every turn and is currently discarded. Added in this revision — see §1.5 for why it's numbered before, and required by, Feature 4.
1. **Rule aggregation policy** — small, engine-only fix.
2. **Semantic conditioning at inference** — small, engine-only addition.
3. **Rule mining** (no GNN, no training data required) — new subsystem, human-approval gated.
4. **Compound-query answering** (multiple LangGraph nodes contributing to one answer) — the "multi-agent" ask, feature-flagged.
5. **Rule confidence evolves from human review** — added in §11.1, closes a gap flagged in `NESYM_RESEARCH_INTEGRATION_PLAN.md` but not yet turned into a feature.
6. **Embedding-based entity resolution at extraction time** — added in §11.2, same source, same reason.
7. **Autonomous graph maintenance loop** — added in §12.3, applies the core Loop Engineering principle (a system that prompts/runs the pipeline instead of a human doing it per request) to the KG business logic itself, orchestrating Features 3/5/6 on a schedule.

**Explicitly not in this plan** (per the earlier research-plan critique, still true): PyTorch/PyTorch Geometric, GPU training, FB15K-237/NELL-995 benchmarking, R-GCN, variational EM, trained multi-agent RL. Everything below runs on the stack you already have — Python, Neo4j, the existing `LLMClient` — no new dependency class.

---

## 1. Sequencing and why

```
Feature 1 (rule aggregation)  ─┐
Feature 2 (semantic gating)   ─┼─→ can ship independently, any order, ~days each
                                │
Feature 3 (rule mining)       ─┘  (reuses rules_store.create_rule -- zero new
                                    activation-path risk once a candidate is
                                    approved; it becomes a normal Rule)
                                    │
                                    ▼
Feature 4 (compound queries)  ────  depends on Feature 1 (multiple rules may
                                    now legitimately co-fire on the same edge
                                    once mined rules exist alongside hand-
                                    authored ones -- aggregation must exist
                                    first) and reuses the already-running
                                    ResilientSkillDiscovery / find_skills call
                                    in router_node for entity-type gating.
```

Do 1 and 2 first (cheap, de-risk the engine). Do 3 next (self-contained, human-gated, no agent-layer risk). Do 0 before 4 — see §1.5. Do 4 last, behind a flag, only after 1–3 are stable — it's the only one that touches the tested LangGraph topology.

### 1.5 Why Feature 0 has to happen before, not after, Feature 4

Confirming what you asked me to confirm, precisely, from re-reading `agents/graph.py`: the LLM does **not** decide which skill loads. It classifies `intent` (one word). Skill choice is `_SKILL_BY_INTENT.get(intent)` — a fixed Python dict, one skill per intent, no reasoning involved (`agents/graph.py:97-103`). Separately, `router_node` already calls `discovery.find_skills(...)` on every turn (`agents/graph.py:155`) — a real Neo4j full-text + graph-boost query over the `:Skill` graph scoped in `PLAN.md` §18 — and stores the result in `state["discovered_skills"]` purely for observability. The file's own docstring says it outright: *"discovery augments it, doesn't replace it."* That's the actual gap: a working graph-based selector runs every turn and gets thrown away next to a hardcoded table.

This matters for Feature 4 specifically because Feature 4's dispatch table as drafted in §5.4 (`_NODE_BY_INTENT`) is **the same anti-pattern** — a second hardcoded "which capability handles this" map, built independently of the first one. Two hand-maintained lookup tables deciding overlapping questions (which skill loads vs. which node gets dispatched to) will drift out of sync the first time either one is edited without the other. Building Feature 0 first means Feature 4's dispatch can query the *same* graph-driven mechanism instead of hardcoding a second table — one source of truth for "what handles this," not two.

---

## 2. Feature 0: Skill-Graph-Driven Selection

### What the research says to do here, staged (no GNN, same discipline as Features 1–4)

Mapped onto `NESYM_RESEARCH_INTEGRATION_PLAN.md`'s taxonomy (§2.1: three categories of neurosymbolic coupling) and the MAGRL article's "ontology constrains which agent handles what":

**Stage A — symbolic, sequential (survey category 1), ships now.** Stop discarding `discovery.find_skills()`'s output. Make it the actual selector, with the current hardcoded map demoted to a fallback for when discovery returns nothing or everything scores below a confidence floor — mirroring the exact safety pattern the router already uses for intent itself (`if intent not in _VALID_INTENTS: intent = "extract"`, `agents/graph.py:149-150`). This alone finishes what `PLAN.md` §18.3 already scoped and is, concretely, "logic (the skill graph's structure) determines what the system does next" — zero training, zero new dependency, and it's mostly deleting code (the hardcoded map shrinks to a fallback, not a primary path).

```python
def _select_skill(intent: str, text: str, discovered: list[DiscoveredSkill], *, min_confidence: float = 0.35) -> str:
    if discovered and discovered[0].score >= min_confidence:
        return discovered[0].name
    return _SKILL_BY_INTENT.get(intent, "kg-extraction")  # unchanged fallback, now a safety net not the primary path
```

**Stage B — lightweight bandit (survey category 3, minus the GNN), ship once Stage A has real usage.** `record_usage(name, session_id, success: bool)` already exists and already feeds a rolling-average `confidence` per skill (`PLAN.md` §18.4 item 4). That rolling average is a crude bandit already — upgrading it to epsilon-greedy or Thompson sampling over the small (~6-10) skill action space is a math change to the existing confidence-update formula, not a new subsystem, and converges fast precisely because the action space is tiny (unlike a full rule/relation vocabulary, where a bandit would need much more data to converge). Use `success` as the reward signal you're already recording. This is the actual, correctly-scoped version of "reinforcement learning informed routing" from the MAGRL article — not a GNN, a bandit.

**Stage C — ontology-constrained eligibility (MAGRL's specific mechanism), ship alongside Stage A.** `PLAN.md` §18.1 already schemas `:EntityType` and `:Domain` nodes on the skill graph but nothing enforces them yet. Before ranking candidates in Stage A, filter to skills whose `:EntityType`/`:Domain` edges match the entity types detected in the current turn's text (reuse whatever entity-type detection extraction already does) — this is literally MAGRL's "ontology constraints limit which agents handle which entity types," applied to skills instead of full agents, using schema you already have.

### Files

| File | Change |
|---|---|
| `backend/agents/skill_discovery.py` | expose `DiscoveredSkill.score` if not already surfaced (check first) |
| `backend/agents/graph.py` | `_select_skill()` replaces direct `_SKILL_BY_INTENT.get(intent)` calls in `responder_node` (and anywhere else it's used); `_NODE_BY_INTENT` in Feature 4 (§5.4) is rewritten to derive from the same selection call rather than a second hardcoded dict |
| `backend/services/skill_activation_store.py` or wherever `record_usage`'s confidence math lives | Stage B: rolling average → bandit update formula |
| `backend/db/neo4j_client` skill graph queries | Stage C: add `:EntityType`/`:Domain` filter to `find_skills` |

### Tests

- Stage A: with a real Neo4j skill graph seeded, a query whose text strongly matches a skill's description via full-text search selects that skill even when it doesn't match `_SKILL_BY_INTENT`'s hardcoded mapping for the classified intent — proves discovery is actually driving selection, not just being logged.
- Stage A fallback: with Neo4j unreachable (mirrors the existing `ResilientSkillDiscovery` degradation test pattern from `PLAN.md` §18.4 item 5), selection falls back to the hardcoded map and the agent still completes — no regression versus today's behavior in the failure case.
- Stage B: a scripted sequence of `record_usage` calls with known success/failure pattern converges the bandit toward the better-performing of two skills within a bounded number of trials — deterministic given a fixed random seed.
- Stage C: a query about a `RegulatoryAgency`-typed entity does not surface a skill tagged only for `Person`-typed entities, even if its full-text score would otherwise rank it first.

### Acceptance criteria
- Every one of the 6 router intents still resolves to a sensible skill with Stage A alone (no live-verification regression versus `PLAN.md`'s existing "live-verified for all 6 router intents" claim).
- Feature 4's dispatch (§5.4) is rewritten to call `_select_skill`-equivalent logic per required capability, not a second hardcoded map — see updated §5.4 below.

---

## 3. Feature 1: Rule Aggregation Policy

### The actual gap (verified in code)

In `run_inference` (`reasoning/engine.py:167-265`), `fact_id = f"fact-{rule.id}-{edge.id}"`. If two *different* rules both watch the same `edge_type`/`source_type`/`target_type` combination and both match the same edge (this becomes a real scenario once Feature 3 lets a mined rule and a hand-authored rule overlap), you get two separate `DerivedFact` nodes confirming the same real-world edge, at two different confidences, with no reconciliation. Today, with 4 hand-authored rules covering disjoint edge types, this never happens — but it's a landmine for Feature 3.

### Fix

Restructure `run_inference` to a two-pass evaluation:

```python
# Pass 1: collect all (rule, edge) pairs whose types/threshold match, per edge.id
candidates: dict[str, list[tuple[Rule, float]]] = defaultdict(list)  # edge.id -> [(rule, confidence), ...]
# ... same matching/threshold logic as today, but append instead of emitting immediately

# Pass 2: reduce per edge.id
for edge_id, firings in candidates.items():
    if len(firings) == 1:
        rule, conf = firings[0]
        # emit exactly as today
    else:
        # noisy-OR combination across all firing rules on this edge:
        combined_conf = 1 - prod(1 - conf for _, conf in firings)
        primary_rule = max(firings, key=lambda f: f[1])[0]  # highest-confidence rule's description/name used for the fact text
        # emit ONE DerivedFact, fact.confidence = combined_conf,
        # DerivedFact gains a new field: supporting_rule_ids: tuple[str, ...]
```

**Schema change**: `DerivedFact` (dataclass, `engine.py:77-87`) gains `supporting_rule_ids: tuple[str, ...] = field(default=())`. Backward compatible (default empty tuple; existing single-rule facts populate it with one id).

**Why noisy-OR, not max or sum**: max would throw away real corroborating signal (two independent rules agreeing should increase confidence, not just pick the stronger one); sum can exceed 1.0 and isn't a probability. Noisy-OR (`1 - Π(1-p_i)`) is the standard, cheap, dependency-free way to combine independent positive signals into a bounded [0,1] confidence — same math already implicitly used for the existing chain-confidence product in `run_inference`.

### Files

| File | Change |
|---|---|
| `backend/reasoning/engine.py` | `run_inference` two-pass restructure; `DerivedFact.supporting_rule_ids` field |
| `backend/tests/test_reasoning.py` (existing) | new test: two rules matching the same edge type/types, both firing on the same edge, assert single `DerivedFact` with `len(supporting_rule_ids) == 2` and noisy-OR confidence |

### Acceptance criteria
- All existing reasoning tests still pass unchanged (single-rule-per-edge case is a no-op path through the new logic).
- New aggregation test passes with the exact noisy-OR value asserted numerically.
- `InferenceTraceEntry` trace still logs every (rule, edge) evaluation individually (fired/skipped), even when facts get merged — the UI's "what was tried" view doesn't lose information, only the persisted `DerivedFact` count changes.

---

## 4. Feature 2: Semantic Conditioning at Inference

### The gap

`run_inference` checks `type_matches(src.type, rule.source_type)` / `type_matches(tgt.type, rule.target_type)` — but that's the *rule's own* declared types, not a broader ontology consistency check (e.g., a rule could theoretically be mis-authored, or a mined rule (Feature 3) could propose a technically type-matching but domain/range-invalid pattern the ontology itself would reject).

### Fix

Add one more gate in `run_inference`, after the existing threshold check, before emitting a fact: validate the *edge itself* (not just the rule's declared types) against the live ontology schema's actual domain/range constraints for `edge.type`, using the `schema.build_subclass_matcher()` already loaded in `reasoning_service.run_reasoning` (`services/reasoning_service.py:64-65`) — this is passed in as `type_matches`, so the function needs a second, schema-level check available. Concretely: pass an optional `domain_range_check: Callable[[str, str, str], bool] | None` (edge_type, source_type, target_type) -> bool, sourced from `ontology/loader.py`'s schema object (it presumably already has domain/range data for the vocabulary swap validation used elsewhere — reuse it, don't reimplement).

```python
if domain_range_check is not None and not domain_range_check(edge.type, src.type, tgt.type):
    trace.append(InferenceTraceEntry(..., fired=False, skip_reason="ontology domain/range violation"))
    continue
```

### Files

| File | Change |
|---|---|
| `backend/reasoning/engine.py` | `run_inference` gains optional `domain_range_check` param; new skip_reason string |
| `backend/services/reasoning_service.py` | wire `schema`'s domain/range check through to `run_reasoning_engine` |
| `backend/ontology/loader.py` | confirm/expose a `domain_range_check(edge_type, source_type, target_type) -> bool` method if not already present (check first — may already exist for extraction-time validation; reuse rather than duplicate) |

### Acceptance criteria
- A deliberately mis-typed rule/edge combination (test fixture: a rule whose declared types are broad enough to type-match via subclassing, but where the *edge type itself* is domain/range-invalid per the loaded ontology) is skipped with the new reason, not fired.
- No change to any currently-passing reasoning test (the check is additive and only rejects things the ontology itself disallows).

---

## 5. Feature 3: Rule Mining (no GNN, no training data)

### Corrected scope, matching what `Rule` actually does

Your engine's `Rule` doesn't compose two different relations into a new inferred one — it watches a single `(edge_type, source_type, target_type)` combination and, once source-activation clears `threshold`, mints a confirmed `DerivedFact` for that existing edge with `confidence = activation * weight`. So "mining a rule" here correctly means: **finding which `(edge_type, source_type, target_type)` combinations already occur often and consistently enough in the extracted graph to deserve becoming a scored, watchable `Rule`** — i.e. automating what a human currently does by eyeballing the ontology and hand-writing `fibo_rules.json` entries, not discovering brand-new relation types.

(A true two-relation composition miner — "if `A -[regulated_by]-> C` and `B -[regulated_by]-> C` and `A`/`B` share a board member, infer `A -[affiliated_with]-> B`" — is real and valuable, but requires extending `Rule` with a body pattern and extending `run_inference` to *create* a new edge instead of confirming an existing one. That's a bigger, riskier engine change. Scoped explicitly as **Phase 2 / future work**, not in this plan.)

### Algorithm (Phase 1 — ships against the engine unmodified)

For a given `graph_id`, using the same node/edge loader reasoning already uses (`graph_service.get_entities_and_edges_for_reasoning`):

```python
from collections import Counter, defaultdict

def mine_candidates(nodes, edges, *, min_support=3, min_confidence=0.6):
    by_id = {n.id: n for n in nodes}
    # Count occurrences of each (edge_type, source_type, target_type) combo,
    # and how often the SOURCE node also participates in >=1 other edge
    # (a crude proxy for "this entity is active enough in the graph that a
    # rule watching it would fire meaningfully" -- avoids proposing rules
    # for one-off edge types that appeared exactly once).
    combo_counts: Counter[tuple[str, str, str]] = Counter()
    for e in edges:
        src, tgt = by_id.get(e.source), by_id.get(e.target)
        if src is None or tgt is None:
            continue
        combo_counts[(e.type, src.type, tgt.type)] += 1

    candidates = []
    for (edge_type, source_type, target_type), support in combo_counts.items():
        if support < min_support:
            continue
        # confidence proxy: fraction of ALL edges out of source_type-typed
        # nodes that are this specific edge_type -- i.e. "when a
        # source_type node has an outgoing edge, how often is it this kind"
        total_out_of_source_type = sum(
            c for (et, st, tt), c in combo_counts.items() if st == source_type
        )
        confidence = support / total_out_of_source_type if total_out_of_source_type else 0.0
        if confidence < min_confidence:
            continue
        candidates.append(CandidateRule(
            edge_type=edge_type, source_type=source_type, target_type=target_type,
            support=support, confidence=confidence,
        ))
    return sorted(candidates, key=lambda c: -c.confidence)
```

Already-existing `(edge_type, source_type, target_type)` combos matching a rule already in `load_all_rules()` (hand-authored or previously-approved) are filtered out before returning — no point suggesting what's already a rule.

**Domain-agnostic by construction**: this reads `source.type`/`target.type` off whatever ontology is currently loaded (FIBO today, anything else after a vocabulary swap) — no FIBO-specific code anywhere in the miner.

**Scale note**: `Counter` over all edges is O(E), fine up to tens of thousands of edges in-memory (matches this project's current per-document graph sizes). If/when a single `graph_id`'s edge count grows past roughly 50k, move the counting into a Cypher aggregation (`MATCH (a)-[r]->(b) RETURN type(r), a.type, b.type, count(*)`) instead of pulling all edges into Python — flagged here as a known, documented scaling threshold, not a blocker today.

### Storage: `:CandidateRule` nodes, separate from `:Rule`

Mirrors the existing `:ImplicitFact` human-approval pattern (enrichment) and the existing `:Rule` custom-rule pattern (`rules_store.py`) — reuse both conventions rather than inventing a third.

```cypher
MERGE (c:CandidateRule {id: $id})
SET c.edgeType = $edge_type, c.sourceType = $source_type, c.targetType = $target_type,
    c.support = $support, c.confidence = $confidence, c.graphId = $graph_id,
    c.minedAt = datetime(), c.status = 'pending'
```
`id` is deterministic: `f"cand-{edge_type}-{source_type}-{target_type}"` (MERGE-safe — re-running mining doesn't duplicate).

### New service: `backend/services/rule_mining_service.py`

```python
def mine_candidates(neo4j, graphdb, settings, graph_id) -> list[CandidateRule]:
    nodes, edges = graph_service.get_entities_and_edges_for_reasoning(neo4j, graph_id)
    existing = {(r.edge_type, r.source_type, r.target_type) for r in load_all_rules(neo4j)}
    candidates = [c for c in _mine(nodes, edges) if (c.edge_type, c.source_type, c.target_type) not in existing]
    _persist_candidates(neo4j, graph_id, candidates)
    return candidates

def list_candidates(neo4j, *, status="pending") -> list[CandidateRule]: ...

def approve_candidate(neo4j, candidate_id) -> None:
    c = _get_candidate(neo4j, candidate_id)
    rules_store.create_rule(
        neo4j, rule_id=f"mined-{candidate_id}", name=f"Mined: {c.edge_type}",
        edge_type=c.edge_type, source_type=c.source_type, target_type=c.target_type,
        threshold=0.3,  # same default as hand-authored rules; tunable later via Construct tab, same as any custom rule
        weight=c.confidence,  # the mined confidence becomes the rule's starting weight -- the ONLY "learned" number in this whole feature, and it's a plain frequency ratio, not a trained parameter
        description="{source} " + c.edge_type + " {target} (mined, support=" + str(c.support) + ")",
    )
    _set_status(neo4j, candidate_id, "approved")

def reject_candidate(neo4j, candidate_id) -> None:
    _set_status(neo4j, candidate_id, "rejected")  # kept, not deleted, so re-mining doesn't re-surface it
```

**This is the key reason Feature 3 is low-risk**: `approve_candidate` calls the *existing, already-tested* `rules_store.create_rule()` — the exact function the Construct tab already uses for user-added rules, already wired into `load_all_rules()`, already consumed by `run_reasoning`. Nothing about the reasoning engine's activation path changes; mining only ever produces something that looks identical to a rule a human typed in by hand.

### New endpoints (`backend/app/main.py`)

| Endpoint | Behavior |
|---|---|
| `POST /rules/mine/{graph_id}` | runs `mine_candidates`, returns the list |
| `GET /rules/candidates?status=pending` | list |
| `POST /rules/candidates/{candidate_id}/approve` | promotes to a real `:Rule` |
| `POST /rules/candidates/{candidate_id}/reject` | marks rejected |

### Frontend

Extend the existing Construct tab's Rules Manager with a "Suggested Rules" section (reuse the existing rule-row component): each candidate shows `{source_type} -[{edge_type}]-> {target_type}`, support count, confidence %, Approve/Reject buttons. No new design system needed.

### Tests (real Neo4j, no mocks, per project convention)

`backend/tests/test_rule_mining_service.py`:
- Seed a real test `graph_id` with 5 organizations, all with a `REGULATED_BY` edge to the same agency, 4 of the 5 also with a `DOMICILED_IN` edge to the same jurisdiction. Run `mine_candidates`. Assert a candidate for `(DOMICILED_IN, organization, jurisdiction)` is returned with `support == 4` and the exact expected confidence ratio.
- Assert a combo already covered by an existing hand-authored rule (e.g. `issues-security`) is never proposed as a candidate.
- Approve a candidate; assert `rules_store.list_custom_rules()` now includes it, AND assert a subsequent `reasoning_service.run_reasoning()` call on that graph actually fires it (full integration through to a real `DerivedFact`) — this is the test that proves "ensure it works" end-to-end, not just that a Neo4j node got created.
- Reject a candidate; assert a second `mine_candidates()` call on the same graph does not re-surface it.

Add `evals/cases/rule-mining/case-01.json` following the existing `evals/lib.py` dispatch convention.

### Acceptance criteria
- Mining produces zero results on a graph too small to have repeating patterns (no false positives from noise) — add a test asserting this too.
- No change whatsoever to `reasoning/engine.py`'s firing behavior for anything except newly-approved rules.
- A rejected candidate never reappears from a fresh mining run on unchanged data.

---

## 6. Feature 4: Compound-Query Answering

This is the one that touches the tested `agents/graph.py` topology, so it ships **behind a feature flag**, additive, with the existing single-intent path completely untouched when the flag is off. This feature depends on Feature 0 (§2) for its dispatch mechanism — see §6.4.

### 5.1 Config

`backend/app/config.py`: add `enable_compound_queries: bool = False`.

### 5.2 State (`backend/agents/state.py`)

```python
from typing import Annotated
import operator

class AgentState(TypedDict):
    ...  # existing fields unchanged
    intents: list[str]                                    # NEW -- len 1 in the common case
    partial_answers: Annotated[dict[str, dict], operator.or_]  # NEW -- merges dict writes from parallel branches; REQUIRED, not optional -- LangGraph raises InvalidUpdateError on concurrent same-key writes to a plain dict field
    combined_answer: str                                  # NEW -- set by combiner_node
```

The `Annotated[..., operator.or_]` reducer is not optional decoration — without it, two specialist nodes writing to `partial_answers` in the same parallel superstep will crash the graph run. This is the single most important correctness detail in this feature; call it out in the PR description too.

### 5.3 Router changes (`agents/graph.py`)

```python
_COMPOUND_ADDENDUM = """
If the message clearly needs MORE THAN ONE of the above capabilities together \
to fully answer, respond with a comma-separated list instead of one word, e.g. \
"reason,recall". Only do this when genuinely necessary -- most messages need \
exactly one capability, and single-word answers remain correct for those.

Compound examples:
"Is Acme Bank's ownership chain compliant, and have we flagged this pattern before?" -> reason,recall
"Query the current ownership edges and also check reasoning for anything derivable." -> query,reason
"""

def router_node(state: AgentState) -> dict:
    system = _ROUTER_SYSTEM + (_COMPOUND_ADDENDUM if settings.enable_compound_queries else "")
    raw = llm.complete_json(system=system, user=state["text"])
    parts = [p.strip().lower() for p in raw.strip().split(",")]
    intents = [p for p in parts if p in _VALID_INTENTS] or ["extract"]
    discovered = discovery.find_skills(_discovery_query(intents[0], state["text"]), limit=3)
    return {
        "intents": intents,
        "intent": intents[0] if len(intents) == 1 else "compound",
        "discovered_skills": [d.name for d in discovered],
        "partial_answers": {},
    }
```

With `enable_compound_queries = False`, the LLM is never told compound is an option — `intents` is always length 1 in practice, `intent` is set exactly as it is today, and every downstream branch behaves identically to the current code. This is the regression-safety guarantee: **flag off = provably identical graph behavior**, not just "probably fine."

### 5.4 Fan-out (⚠️ spike this first — see §5.9), driven by Feature 0's selector, not a second hardcoded map

Intent strings already map 1:1 to node names for the single-path case (`"reason"` → `reasoner` node, etc.) — that mapping is structural (each node *is* the implementation of its intent) and is fine to keep as a small constant. What must **not** be a second hardcoded table is *which capabilities are even eligible to be dispatched* for a given compound query — that decision should come from the same discovery/eligibility mechanism Feature 0 builds (Stage A's discovery-based selection + Stage C's ontology-type gating), not an independent guess:

```python
from langgraph.types import Send  # confirm exact import path against installed langgraph version -- see spike note

_NODE_BY_INTENT = {"reason": "reasoner", "recall": "memory_agent", "query": "querier", "enrich": "enricher"}  # structural, 1:1, fine as a constant

def route_by_intent(state: AgentState):
    if len(state["intents"]) > 1:
        # Feature 0's eligibility check runs here, not a second ad-hoc rule:
        # an intent only gets dispatched if Feature 0's discovery+ontology-gate
        # would have selected its corresponding skill for this turn's text/entity
        # types -- reuses _select_skill's Stage A/C logic instead of assuming
        # every LLM-listed intent is automatically eligible to fire.
        eligible = [i for i in state["intents"] if i in _NODE_BY_INTENT and _is_eligible(i, state)]
        return [Send(_NODE_BY_INTENT[i], state) for i in eligible]
    return state["intents"][0]
```

This is the concrete answer to "do we need Feature 0 together with Feature 4": without it, compound dispatch trusts the router LLM's comma-separated list at face value with no independent check; with it, each proposed capability is cross-checked against the same graph-based relevance/eligibility signal used everywhere else, so a misfiring LLM classification (e.g. proposing `"reason,recall"` for a query that's really only about `reason`) gets one more real check before triggering two parallel node executions instead of one.

`add_conditional_edges("router", route_by_intent, {...single-intent map unchanged..., "extract": "extractor", ...})` — when `route_by_intent` returns a list of `Send`, LangGraph fans out to each named node in parallel with a copy of state; when it returns a single string, existing routing is unchanged.

### 5.5 Specialist nodes gain an additive `partial_answers` write

Each of `reasoner_node`, `querier_node`, `enricher_node`, `memory_agent_node` gets ~3 added lines, no change to existing return keys:

```python
def reasoner_node(state: AgentState) -> dict:
    # ... existing body, unchanged ...
    update = {"facts_derived": facts_derived, "fact_texts": fact_texts}
    if len(state["intents"]) > 1:
        conf = (sum(f.confidence for f in result.facts) / len(result.facts)) if result.facts else 0.0
        update["partial_answers"] = {"reasoner": {
            "summary": "; ".join(fact_texts[:5]) or "no new facts derived",
            "confidence": conf,
        }}
    return update
```

Same pattern for `querier_node` (confidence = 1.0 if `query_results` non-empty else 0.0), `memory_agent_node` (confidence = fraction of search terms with ≥1 hit), `enricher_node` (confidence = fraction of the 11 heuristics that produced a candidate).

### 5.6 Post-specialist routing becomes conditional

Each specialist's current fixed edge to `"responder"` becomes conditional on compound-ness:

```python
def _next_after_specialist(state: AgentState) -> str:
    return "combiner" if len(state["intents"]) > 1 else "responder"

for node in ("reasoner", "querier", "enricher", "memory_agent"):
    workflow.add_conditional_edges(node, _next_after_specialist, {"combiner": "combiner", "responder": "responder"})
```

(`extractor` keeps its unconditional edge to `reasoner` — extraction was never part of a compound set in this design; it always precedes reasoning as today.)

### 5.7 New `combiner_node`

```python
def combiner_node(state: AgentState) -> dict:
    sections = []
    for name in ("reasoner", "querier", "enricher", "memory_agent"):
        pa = state["partial_answers"].get(name)
        if pa:
            sections.append(f"[{name}, confidence={pa['confidence']:.2f}] {pa['summary']}")
    return {"combined_answer": "\n".join(sections) or "(no sub-answers produced)"}
```

Deterministic, no LLM call, fully testable with a plain dict fixture — no need to wait on the graph to test this node in isolation.

### 5.8 `responder_node` — one new branch

```python
if intent == "compound":
    user = f"Sub-answers from multiple specialists for: {state['text']}\n\n{state['combined_answer']}\n\nSynthesize one coherent answer, and note which specialist each part of your answer relies on."
```

Same `_RESPONDER_SYSTEM`, same `llm.complete_json` call already used for every other intent — no new LLM plumbing.

### 5.9 ⚠️ Spike required before full build: LangGraph fan-out/fan-in mechanics

The `Send`-based parallel dispatch and the `combiner` node acting as a join point (waiting for all dispatched branches to finish before running) is the one piece of this plan I have not verified against your installed LangGraph version's exact API (import path, whether `combiner` needs to be declared as a fan-in target explicitly, whether `Annotated[dict, operator.or_]` is the correct reducer syntax for your version). **Recommend a half-day spike**: a throwaway 3-node toy graph (`start → [Send(a), Send(b)] → join → end`) proving the fan-out/fan-in + concurrent dict-write pattern works as described, *before* wiring it into the real 7-node graph. If the API differs, this section gets corrected against real, run output — not assumed.

### 5.10 Tests

- Unit: router's comma-list parsing — single word (unchanged behavior), valid compound list, garbage/invalid LLM output (falls back to `["extract"]`, same safe default as today).
- Unit: `combiner_node` with a fabricated `partial_answers` dict — deterministic output, no graph/LLM needed.
- Regression (flag OFF): full existing agent test suite run unchanged against the new graph topology — must be bit-for-bit identical pass/fail results to before this feature existed. This is the test that actually proves "ensure it works" for the risky part of this plan.
- Integration (flag ON, real Neo4j + real LLM): 2–3 concrete compound queries seeded against a real small graph (e.g. "Is Acme Bank's ownership chain compliant, and have we seen this before?" against a graph with both a compliance-relevant derived fact and a prior matching chat-history entry) — assert `combined_answer` contains both specialists' contributions and the final `reply` references both.
- Live-verify once in the browser per the project's established convention (§9's UI live-verification pattern) with the flag on in a dev config.

### 5.11 Rollout

Ship with `enable_compound_queries=False` in every existing environment. Turn on only in a dev/staging config, validate against real compound queries for a period, then graduate to default-on — same cautious-flag discipline the project already uses implicitly (e.g. `MemoryInspector`/`SkillManager` shipped only once live-verified).

---

## 7. File change summary

### New files
| File | Purpose |
|---|---|
| `backend/services/rule_mining_service.py` | mining, candidate persistence, approve/reject |
| `backend/tests/test_rule_mining_service.py` | real-Neo4j tests per §4 |
| `evals/cases/rule-mining/case-01.json` | eval case |
| `frontend/src/components/SuggestedRules.tsx` (or extend existing Rules Manager component) | approve/reject UI |

### Modified files
| File | Change |
|---|---|
| `backend/reasoning/engine.py` | Feature 1 (aggregation), Feature 2 (domain/range gate), `DerivedFact.supporting_rule_ids` |
| `backend/services/reasoning_service.py` | wire domain/range check through |
| `backend/ontology/loader.py` | expose/confirm `domain_range_check` (reuse if it exists) |
| `backend/app/main.py` | 4 new `/rules/*` endpoints |
| `backend/app/config.py` | `enable_compound_queries` flag |
| `backend/agents/state.py` | `intents`, `partial_answers`, `combined_answer` fields |
| `backend/agents/graph.py` | router compound parsing, `Send` fan-out, `combiner_node`, conditional post-specialist edges, responder compound branch |
| `backend/tests/test_reasoning.py` | aggregation + domain/range tests |
| existing agent tests | regression pass with flag off |

### Unchanged
Everything about extraction, Polanyi enrichment, the Skills MCP server, the frontend's existing Reason/Memory/Skill tabs, `MVP_PLAN.md`'s Phase 6 LangGraph wrap as originally shipped for the single-intent path.

---

## 8. Non-goals (repeated for anyone skimming just this section)

- No PyTorch, PyTorch Geometric, or GPU dependency anywhere in this plan.
- No FB15K-237/NELL-995/external benchmark dataset.
- No trained model of any kind — the only "learned" number introduced (Feature 3's mined `weight = confidence`) is a plain support/total ratio computed with a `Counter`, fully deterministic, fully explainable by re-running the same count by hand.
- No change to the single-intent path's behavior when `enable_compound_queries` is off.
- No autonomous rule creation — every mined rule requires explicit human approval through the same UI pattern as enrichment's existing `:ImplicitFact` review.

---

## 9. Rough sequencing / effort

| Feature | Effort | Blocking risk |
|---|---|---|
| 0. Skill-graph-driven selection (Stage A + C) | 3–5 days | Low — mostly deleting the primary use of a hardcoded map, keeping it as fallback |
| 0. Skill-graph-driven selection (Stage B, bandit) | 2–3 days, but only after real usage exists | None on the critical path — purely additive to the confidence formula |
| 1. Rule aggregation | 2–3 days | None — isolated engine change |
| 2. Semantic conditioning | 2–3 days | None — isolated engine change, may need to confirm ontology loader already exposes domain/range (check before estimating further) |
| 3. Rule mining | 1–1.5 weeks | Low — new subsystem, but activation happens through already-tested `create_rule` |
| 4. Compound queries | 1.5–2 weeks + 0.5 day spike | Medium — the only feature touching tested agent topology; flag mitigates production risk, spike mitigates LangGraph API risk; depends on Feature 0 Stage A/C for dispatch eligibility (§6.4) |
| 5. Rule confidence from review (§11.1) | 3–5 days | Low — reuses Feature 0 Stage B's bandit code; depends on Feature 3 existing |
| 6. Embedding-based entity resolution (§11.2) | 3–5 days | Low — reuses existing embedder, no training; independent of all other features, can ship any time |
| 7. Autonomous graph maintenance loop (§12.3) | 1–1.5 weeks | Low — orchestrates already-built Features 3/5/6 on a schedule; every output already lands on an existing human-approval gate, so no new safety mechanism is needed; depends on 3, 5, 6 existing first |
| §12.4 grounding-check addition to Feature 4 | 1–2 days | Low — bounded single retry, deterministic check first; folds into Feature 4's existing test suite |

---

## 10. Loop Engineering (github.com/cobusgreyling/loop-engineering) — analysis and verdict

**Correction**: I initially drafted this section from an assumption about what "loop engineering" meant before fetching the actual repo. Having now fetched the real README, that assumption was wrong in an important way, and the section below replaces it rather than building on it.

### What the repo actually is

It's Cobus Greyling's practical toolkit (npm CLIs: `loop-audit`, `loop-init`, `loop-cost`) built around an essay by Addy Osmani, with the core claim credited to Boris Cherny (Head of Claude Code at Anthropic): *"I don't prompt Claude anymore. I have loops running that prompt Claude... My job is to write loops."* The subject is **scheduled, semi-autonomous coding-agent workflows for maintaining a software repository** — not a runtime LLM-answer-quality pattern. Its "Five Building Blocks": Automations/Scheduling, Worktrees (safe parallel execution), Skills (persistent project knowledge), Plugins & Connectors (MCP), Sub-agents (Maker/Checker split), plus Memory/State. Its shipped patterns are all repo-maintenance tasks: Daily Triage, PR Babysitter, CI Sweeper, Dependency Sweeper, Changelog Drafter, Post-Merge Cleanup, Issue Triage — each running on a cadence (minutes to days), each with a "Human Gate" that either auto-commits (safe/allowlisted changes) or escalates to a person (risky/ambiguous ones).

### Direct answer: no, this is not needed with Feature 4's multi-agent answering

This is a different layer of "the project" than Feature 4 touches. Feature 4 is about the **runtime KG app** answering one user's compound query, in-request, in seconds. Loop Engineering is about **how this codebase itself gets maintained over time** by a coding agent, on a schedule, across many separate runs. Bolting one onto the other would repeat the exact category error flagged earlier with the GNNComm-MARL wireless paper — borrowing a mechanism from a domain that only superficially resembles the target one (both involve "an agent orchestrating other agents," but at completely different timescales and for completely different jobs).

### Where it's genuinely relevant to this project — a different, real opportunity

Not the runtime pipeline — the **engineering workflow around this repo**, which you're already running through Claude Code / Cowork. Concretely, this project already has the ingredients the toolkit assumes: 240 backend tests, an `evals/` suite with a RED/FAIL path (`evals/validate.py`), and a documented convention of live-verifying before shipping. A scheduled loop could genuinely help here — e.g. a **Daily Triage**-style task (the `schedule` skill already available in this environment could set this up) that nightly runs `evals/run_evals.py`, diffs the results against the last run, and drafts a short report of newly-failing cases — a "Maker/Checker" pattern where the checker is your existing eval suite, not a new component. This is a legitimate, low-effort idea, but it's a **DevOps/process decision about how you maintain this codebase**, entirely separate from anything in Features 0–4 above. Flagging it here for visibility, not folding it into the implementation plan's scope — it doesn't touch `agents/graph.py`, `reasoning/engine.py`, or any file in the change-summary table (§7).

### Verdict on the runtime app (Features 0–4): unchanged
- **Not applicable to Feature 4 or any other feature in this plan** — different layer (repo maintenance vs. runtime query answering).

### Now with the Osmani essay read in full: this is concretely buildable in this exact environment, not just a good idea in the abstract

The essay names Claude Code's actual primitives — `/loop`, `/goal`, `git worktree` / `isolation: worktree`, `.claude/agents/` subagents, scheduled tasks/cron/hooks, `SKILL.md` — and every one of them maps to a real tool already available in this Cowork session, not a hypothetical:

| Osmani's primitive | Available in this session as |
|---|---|
| Automations (cadence) | `mcp__scheduled-tasks__create_scheduled_task` — real, already usable |
| Worktrees (parallel isolation) | `Agent` tool's `isolation: "worktree"` parameter — creates a temporary git worktree per subagent run, auto-cleaned up if unused |
| Skills (project knowledge) | This project's own `.claude/skills/*` — already 6+ dev-time skills (`neurosymbolic-reasoning`, `kg-extraction`, `polanyi-enrichment`, `graph-reasoning`, `ontology-mapping`, `temporal-memory`) |
| Sub-agents (maker/checker) | `Agent` tool with `subagent_type` — a `general-purpose` implementer and a separate checker call, or the project's own `review`/`security-review` skills as the checker |
| Plugins/connectors | MCP servers already connected (e.g. any GitHub connector, once authorized) |
| State/memory | A new markdown file in `.claude/docs/`, same convention this project already uses for `gaps.md`, `PLAN.md`'s decision records |

### Implementation: a Daily Triage loop for this repo

**Cadence**: `mcp__scheduled-tasks__create_scheduled_task`, cron `0 6 * * *` (6am daily, adjust to preference). Prompt: *"Run the neurosymbolic project's Daily Triage loop per `.claude/docs/research/LOOP_STATE.md`'s last recorded state: run the backend test suite and `evals/run_evals.py`, diff pass/fail counts against the last recorded run, and update `LOOP_STATE.md` with any newly-failing tests/eval cases. Report findings only — do not modify code."*

**State file**: `.claude/docs/research/LOOP_STATE.md` (new), the "durable spine outside any conversation" the source insists on — records: last run timestamp, test/eval pass-fail counts, a list of currently-open findings, a list of findings resolved since the last entry. Append-only log, not overwritten each run, so a human can scan history.

**Checker, reusing what already exists rather than adding an LLM judge**: this project already has 240 backend tests and `evals/validate.py`'s RED/FAIL path — that's the "verifier sub-agent + tests + gates" the source describes, already built, not something to add. The loop's job is to *run* that existing checker on a schedule and *report* its output, not to invent a new grading mechanism.

**Maker/checker split, if/when fixes are attempted (L2, not week one — see phasing below)**: an `Agent` call with `isolation: "worktree"` (implementer, general-purpose) attempts a fix for a single well-scoped finding (e.g. one failing test with an obvious cause) in its own isolated checkout; a second, separate `Agent` call (or the `review`/`security-review` skill) reviews the diff against the relevant `.claude/skills/*` conventions; the *real* test suite re-run is the actual gate, not either agent's opinion. Nothing merges automatically — findings and proposed diffs land in `LOOP_STATE.md` for Akash to review, matching the source's "Human Gate: risky/ambiguous → escalate to human with full context."

### Phased rollout — mirrors the source's own explicit guidance, not a cautious addition of mine

The source's own `README` defaults every single shipped pattern to report-only for week one ("Start report-only... No auto-fix in week one") and phases as L1 report → L2 assisted fixes → L3 unattended. Apply the same discipline here, for the same reason the source gives — Osmani's essay itself closes on three named risks (verification still being on you, comprehension debt, "cognitive surrender") that get *worse*, not better, as a loop gets more autonomous:

- **Week 1+ — L1, report-only** (what to actually build first): scheduled task runs tests/evals, writes findings to `LOOP_STATE.md`. No worktree, no subagent, no code change of any kind. Purely observational, proves the triage step is trustworthy before it gets any write access.
- **L2 — assisted fixes, only after L1 has run cleanly for a while**: allow the loop to spawn an implementer subagent (isolated worktree) for narrow, well-scoped findings, checker-reviewed, real-test-gated — but a human always reviews and merges. No auto-commit.
- **L3 — unattended**: **not recommended for this project.** This is a business-analyst-facing financial-reasoning tool where trust and auditability are already the explicit differentiator (per `PLAN.md`'s proof-path/interpretability design, referenced throughout this whole document) — unattended autonomous commits to a reasoning engine or extraction pipeline is a materially different risk profile than the source's own generic examples (dependency bumps, changelog drafts). Stop at L2 unless a long, specifically-trusted track record changes that calculus later.

### Where this connects back to Features 0–4 (optional, not required)

Once the L1 loop exists, it's a natural place to *also* run this plan's own new tests as they ship (Feature 1's aggregation test, Feature 3's rule-mining test, Feature 4's regression suite) — the same nightly run that catches an unrelated regression would catch a regression in this plan's own features too. That's a reason to build the loop *after* Features 0–4 ship, not before — there's more for it to usefully watch once it exists.

### Files
| File | Purpose |
|---|---|
| `.claude/docs/research/LOOP_STATE.md` | new — the loop's memory/state file |
| (scheduled task, not a repo file) | created via `mcp__scheduled-tasks__create_scheduled_task`, listed via `mcp__scheduled-tasks__list_scheduled_tasks` |

No changes to `agents/graph.py`, `reasoning/engine.py`, or anything in §7's file-change table — confirmed still true even with full implementation detail added, because this genuinely is a separate layer from the runtime app.

---

## 11. Reconciliation with `NESYM_RESEARCH_INTEGRATION_PLAN.md` and `research/2025-07-12-research-analysis-and-update-plan.md`

Cross-checked both earlier docs against Features 0–4 above. Two things were flagged there but never turned into an actual feature — added below as Features 5 and 6. One is a real, still-unaddressed gap, stated explicitly rather than silently dropped. One is a loose end between the two earlier docs worth closing on paper.

### 11.1 New Feature 5: Rule confidence evolves from human review (closes NESYM Tier 2 item 5 / the Pryor PSL reference)

`NESYM_RESEARCH_INTEGRATION_PLAN.md` §4 recommended "a learned rule confidence layer, PSL-flavored rather than full ExpressGNN," citing Pryor, Dickens & Getoor's Neural Probabilistic Soft Logic paper (§2.5 of that doc). Feature 3 (rule mining, §5 above) gives *newly mined* rules a starting confidence from frequency counting — but nothing lets a rule's weight move after it goes live, from real outcomes. That's the actual PSL-lite idea: a weight that tracks evidence over time, not a one-time snapshot.

Design, deliberately reusing the same reward-signal mechanism Feature 0 Stage B already introduces for skills, rather than building a second, parallel implementation of the same math:

- Every `:DerivedFact` a rule produces can be explicitly confirmed or rejected by a human — same UI affordance already built for enrichment's `:ImplicitFact` review, applied here to derived facts instead.
- `rules_store.py` gains `update_rule_weight(neo4j, rule_id, *, outcome: Literal["confirmed", "rejected"])` — a rolling-average update, structurally identical to the skill graph's `record_usage`, just writing to `Rule.weight` instead of `Skill.confidence`.
- `reasoning/engine.py` needs **no change at all** — it already reads `rule.weight` from whatever `load_all_rules()` returns. A rule whose weight moved from review outcomes is indistinguishable to the engine from one a human hand-set to that value.

Same justification as Feature 0 Stage B for why a bandit-style update (not a GNN) is the right amount of machinery: a handful of rules, not a large relation vocabulary, converges fast on sparse data.

**Files**: `backend/services/rules_store.py` (new `update_rule_weight`); reuse the existing enrichment approve/reject frontend component rather than building a second one for derived facts.
**Tests**: seed a rule, simulate a scripted sequence of confirm/reject outcomes with a known ratio, assert the weight converges toward that ratio within a bounded number of updates — real Neo4j, deterministic given a fixed sequence.
**Sequencing**: after Feature 3 (needs rules to exist first) and after Feature 0 Stage B ships (share the bandit-update code, don't duplicate it).

### 11.2 New Feature 6: Embedding-based entity resolution at extraction time (closes NESYM Tier 2 item 6 / the ReOnto reference)

`NESYM_RESEARCH_INTEGRATION_PLAN.md` §4 named ReOnto (ontology + GNN for relation extraction) as a Tier 2 direction for `kg-extraction`. The 2025-07-12 doc's own decision D3 committed to reusing the existing 1024-dim `summaryEmbedding` vectors rather than random-initializing anything for any future embedding work. And earlier in this conversation, when you asked how a GNN would concretely be used, the version that survived scrutiny was: skip training, use cosine similarity between existing embeddings directly. This feature is that surviving idea, finally turned into a real spec — the one piece of the ReOnto direction that's genuinely low-risk today.

**The real problem this fixes**: extraction has no cross-document memory. Document 1 creates entity "Acme Corp." Document 2's extraction creates "Acme Corporation" as a *second*, separate node for the same real company, because the LLM extractor never sees what already exists in the graph. Classic entity-resolution/deduplication failure, and a genuine data-quality issue for a business-analyst-facing tool — duplicate entities silently fragment one company's history across the graph.

**Design**: after `ingest_service.ingest_text` produces a candidate entity, before writing it as a new node, compute its embedding (the same embedding step already run for `summaryEmbedding`) and compare via cosine similarity against existing entities of the same type already in the graph. Above a high threshold (e.g. >0.92), don't silently create a new node or silently merge — flag "likely duplicate of X" for human confirmation, same review pattern as enrichment and Feature 11.1's rule review above. No training, no GNN, no new embedding computation beyond what's already run today.

**Files**: `backend/services/ingest_service.py` (dedup check before node creation), `llm/embedder.py` (reused, unchanged).
**Tests**: two documents producing near-identical names for the same real-world entity → flagged as a candidate duplicate, not silently created. Two genuinely different entities with superficially similar names → NOT flagged (real Neo4j + real embedder, no mocks, per project convention).
**Non-goal, restated**: this is a similarity lookup over embeddings you already compute, not the R-GCN/relation-aware structural-embedding idea from the earlier, rejected research plan — no message passing, no training loop.

### 11.3 Deliberately still open: temporal reasoning (2025-07-12 doc's Gap 7)

That doc's Gap 7 named a real, unaddressed gap: this project's bi-temporal data model (`validAt`/`invalidAt` on edges) records *when* a fact was true, but `reasoning/engine.py`'s fixpoint loop has no time dimension anywhere in its activation or firing logic — you can't currently ask "was entity A domiciled in Switzerland when it issued that security?" and get a temporally-aware answer. Its suggested reference, TFLEX, is not the right pointer to follow — it's a heavy, embedding-based temporal query-answering framework, the same category of overreach as the GPU/GNN items already excluded elsewhere in this plan (§8).

Not folded into Features 0–6 above because it's genuinely separate scope — temporal constraint propagation through the fixpoint loop deserves its own design pass, not a rushed subsection here. Stated explicitly, as both earlier docs did, so it isn't silently dropped: **a real gap, worth a dedicated follow-up plan**, symbolic-first (temporal constraint checks alongside Feature 2's ontology domain/range gate — same shape, added dimension — not a TFLEX-style embedding layer), once Features 0–6 are stable.

### 11.4 Closing the loop between the two earlier docs

`NESYM_RESEARCH_INTEGRATION_PLAN.md`'s Tier 3 item 8 — "MAGRL-style learned routing policy over the 7 LangGraph nodes / 6 skills" — was explicitly filed as "a research spike in a branch, not a roadmap item," too speculative to commit to without real usage data. Feature 0 Stage B (§2) is the concrete, de-risked version of that same underlying goal this plan actually commits to: not a trained GNN relevance graph, but a small bandit over a ~6–10 skill action space using usage data the project already records. Worth stating plainly rather than leaving the two documents implicitly disconnected: **Tier 3 item 8's goal is now addressed, via a different, smaller mechanism than originally speculated.** The full GNN version remains exactly as speculative as it was — nothing here changes that judgment, it's still not part of this plan.

### 11.5 Re-checked and correctly still excluded — no change

For completeness, re-verified against Features 0–6 and confirmed still out of scope:
- ExpressGNN / full MLN+GNN joint reasoning (NESYM Tier 3 item 7) — still gated behind Feature 11.1 proving insufficient first, per NESYM's own sequencing logic.
- FB15K-237/NELL-995 benchmarking, PyTorch/PyTorch Geometric, GPU training (2025-07-12 doc's Phase A/D) — still rejected; §8's Non-goals list stands unchanged.
- MAGNet's literal predator-prey/Pommerman RL machinery — still domain-mismatched; only the "learned relevance graph, decoupled from decision-making" idea transferred, into Feature 0 Stage B, not the RL environment specifics.

---

## 12. Loop Engineering applied to the core agentic orchestration framework — revised

**Correction to §10's scope**: §10 asked "is Loop Engineering needed with Feature 4" and answered by mapping the source's own shipped patterns (Daily Triage, PR Babysitter, CI Sweeper — all repo-maintenance) onto this project, concluding "different layer, not needed." That answer is still right for *those specific patterns*. But the question underneath the source's core claim — *"replacing yourself as the person who prompts the agent; you design the system that does it instead"* — is broader than its shipped examples, and re-reading `agents/graph.py` and `reasoning/engine.py` with that broader framing in mind, three things are worth separating out that §10 conflated into one "not applicable" verdict.

### 12.1 You already have one real instance of this in the core framework, just not named as such

`reasoning/engine.py`'s `reason()` function (`spread → infer → feed back → check convergence → repeat, max_iterations` cap) *is* the source's `/goal` primitive: *"keeps going until a condition you wrote is actually true, and after every turn a separate small model checks whether you are done, so the agent that wrote the code isn't the one grading it."* Your convergence check (`delta < epsilon` and no new facts, `engine.py:324-327`) is exactly that independent stopping-condition check — it's plain Python, not even a second model call, which is a *stricter* version of the source's own pattern (the source uses a small model to grade; you use deterministic code, consistent with this whole plan's bias toward determinism wherever possible). Worth stating plainly: this project didn't need to adopt Loop Engineering's goal-convergence primitive — it already built the pattern, independently, for a different reason (fixpoint correctness), and it turns out to be the same shape.

### 12.2 You already have the source's "Human Gate" primitive, repeated at every review point in this plan

The source's loop anatomy ends every cycle at: *"safe/allowlisted → auto-commit; risky/ambiguous → escalate to human with full context."* This project's human-approval workflow — enrichment's `:ImplicitFact` review, Feature 3's mined-rule candidate approval, Feature 5's derived-fact confirm/reject, Feature 6's duplicate-entity flagging — is that same gate, applied every time, never auto-committing. Not a gap to close; confirming the existing design already matches the source's own safety posture, independently arrived at.

### 12.3 What's genuinely missing from the core framework, and worth adding — a new Feature 7

What the core framework does *not* have is the source's **Automations** primitive applied to its own business logic — today, extraction/enrichment/reasoning/mining only run when a user's message triggers them, once, per request. There is no loop that periodically revisits existing graphs and does the maintenance work a user would otherwise have to remember to ask for. This is the genuine gap, distinct from both Feature 4 (single-request compound answering) and §10 (repo/CI maintenance) — an **autonomous graph-maintenance loop**, operating on the KG data itself.

**Design — Feature 7: Autonomous Graph Maintenance Loop**

Cadence via `mcp__scheduled-tasks__create_scheduled_task` (e.g. nightly per active `graph_id`, or triggered after N new documents ingested). Each run, for a given `graph_id`:

1. **Maker**: run Feature 3's `mine_candidates` → new `:CandidateRule` nodes.
2. **Maker**: run `reasoning_service.run_reasoning` to convergence (§12.1's already-built `/goal` loop) on any graph with unprocessed activation.
3. **Maker**: run Feature 6's entity-resolution check over entities added since the last loop run.
4. **Maker**: run Feature 5's `update_rule_weight` pass over any `:DerivedFact`s a human confirmed/rejected since the last run.
5. **Checker, not a second LLM grading the first one — the same real gates already built**: every output of steps 1–4 lands exactly where it already lands today (candidate rules await approval, derived facts await confirmation, duplicate entities await confirmation) — the loop's "checker" is the human-approval mechanism this plan already specifies throughout, not a new verification concept.
6. **State**: a per-`graph_id` summary appended to a new `.claude/docs/research/GRAPH_LOOP_STATE.md` (or a real `:LoopRun` Neo4j node if you want it queryable from the UI instead of a flat file) — "mined 3 candidates (2 auto-discarded as duplicates of existing rules), reasoning converged after 4 iterations with 2 new facts, flagged 1 likely-duplicate entity, 1 rule's weight moved 0.6→0.71."

**Why this is a new feature and not part of Feature 4**: Feature 4 answers one user's compound question, synchronously, in one request. Feature 7 runs unprompted, on a schedule, across possibly-many graphs, and its job is upkeep, not answering — same distinction the source itself draws between a single agent turn and a loop.

**Phased rollout — same discipline as §10, for the same reason**: L1 report-only first (run steps 1–4, write the summary, propose nothing for auto-action beyond what already requires human approval today — i.e. this is *already* L1-safe by construction, since every step 1–4 output was already gated by an existing human-approval mechanism before Feature 7 existed). There is no L2/L3 escalation temptation here the way there is in §10's code-fixing loop, because nothing in steps 1–4 was ever designed to auto-apply without review in the first place — Feature 7 doesn't need the same L1→L2→L3 caution ladder §10 needs, precisely *because* Features 3/5/6 were already designed with a mandatory human gate. Worth noting as a small piece of evidence that designing each feature with a human-approval boundary from the start (rather than bolting one on later) pays off exactly here.

### 12.4 Where a maker/checker split belongs inside Feature 4 specifically, correctly attributed this time

When first drafting §10, before fetching the real source, I proposed a bounded grounding-check-and-retry for Feature 4's `responder_node` on the `compound` path, then retracted it when the fetched source turned out to be about repo maintenance instead. Re-reading the source properly: that retraction was about *citation*, not about the *idea* — the source's actual maker/checker primitive (*"the model that wrote the code is way too nice grading its own homework... a fresh model decides if the loop is done instead of the one that did the work"*) is exactly the shape of that original proposal, just needed the right source this time instead of a guessed one. Reinstating it, correctly grounded now:

```python
def responder_node(state: AgentState) -> dict:
    ...
    reply = llm.complete_json(system=system, user=user)
    if state["intent"] == "compound":
        # Maker/checker split (Osmani's essay, "sub-agents" primitive): the
        # model that synthesized `reply` from multiple partial answers is not
        # the one that checks whether it over-claimed. A cheap, deterministic
        # grounding check first (does every claim trace to a substring in
        # combined_answer's sections); only escalate to a second LLM call if
        # the deterministic check actually finds something ungrounded --
        # bounded to one retry, not an open-ended loop, matching this
        # project's existing bias toward determinism wherever possible.
        ungrounded = _find_ungrounded_claims(reply, state["combined_answer"])
        if ungrounded:
            reply = llm.complete_json(
                system=system + "\n\nYour previous answer included claims not supported by the sub-answers. Only state what the sub-answers actually support.",
                user=user,
            )
    return {"reply": reply}
```

This is now formally part of Feature 4 (§6.8), not a separate item — add `_find_ungrounded_claims` and the bounded-retry branch to `responder_node`'s compound path as specified there, with a unit test asserting a deliberately over-claiming fabricated `reply` triggers exactly one retry, not a loop.

### 12.5 Revised bottom line

- **§10's specific verdict stands**: the source's *shipped patterns* (Daily Triage, CI Sweeper, etc.) are repo-maintenance, not core-orchestration, and stay scoped there.
- **The broader principle does apply to the core framework**, in three ways: it's already present once (§12.1, the reasoning engine's convergence loop), already present as a recurring design choice (§12.2, human-gated review everywhere), and genuinely missing once (§12.3, no automation loop over the graph's own upkeep — now Feature 7) plus one small addition worth folding into Feature 4 (§12.4).
- **Files added by this section**: `backend/services/graph_maintenance_loop.py` (new — orchestrates steps 1–4), `.claude/docs/research/GRAPH_LOOP_STATE.md` (new state file, or a `:LoopRun` Neo4j schema if UI-queryable state is preferred — worth a quick decision before building, not assumed here), `backend/agents/graph.py`'s `responder_node` (§12.4's grounding-check addition to Feature 4, not a new file).
- **Effort**: Feature 7 ≈ 1–1.5 weeks (mostly orchestration of already-built pieces — Features 3/5/6 — plus the scheduled-task wiring); §12.4's addition to Feature 4 ≈ 1–2 days.

---

## 13. Deferred reference design: GNN-augmented salience/weights (R-GCN)

Not scheduled. Recorded here because a detailed, well-reasoned architecture spec was proposed for it and deserves a real home rather than being lost — but it stays gated behind the same condition §11.5 already set for ExpressGNN-style work: Feature 5's bandit proving insufficient, on real production-scale confirm/reject volume, not before.

### 13.1 What's genuinely good in the proposal, worth keeping if this is ever built

- **Augment, don't replace, the spread-activation loop.** The proposal's own closing line — "keep the interpretable spread activation loop... seed it, don't break it" — is the correct design principle, consistent with this entire plan's bias toward determinism wherever possible.
- **R-GCN as the architecture choice**, correctly reasoned: this project's edges are typed (`edge_type` on every `Edge`), so per-relation-type weight matrices are the right tool if a GNN is ever warranted — better-justified than the earlier, vaguer "GNN embeddings" pitch from the original research-analysis doc.
- **Concatenation over replacement for the embedding itself**: `[nvidia_1024 || gnn_256]` keeps the existing semantic embedding intact and adds structural signal alongside it, rather than discarding work already done.
- **Integration point identified precisely**: `spread_activation()`'s `decay * edge.weight * salience.get(edge.target, 1.0)` computation (`engine.py`) as where GNN-derived values would enter — correct, and the same pure-function boundary Features 1/2 above already respected when adding `domain_range_check`.

### 13.2 A real contradiction in the proposal, corrected here

The proposal's own decision table says **"Replace"** for `Node.salience`, `Edge.weight`, and `decay` — directly contradicting its own closing recommendation to "seed it, don't break the loop." These are not the same thing: replacing salience/weight/decay with GNN output keeps the loop's *mechanics* interpretable but makes its *inputs* opaque — a business analyst asking "why did this edge matter" gets "the model's forward pass said so" instead of an inspectable number, the same audit-trail regression flagged earlier in this conversation for the original GNN proposal, just relocated one layer down instead of resolved. **If this is ever built: augment everywhere in that table, never replace** — e.g. `salience = base_salience * (1 + gnn_adjustment)`, clipped to a bounded range, with `base_salience` (today's constant 1.0) always visible as the starting point a reviewer can compare against, not silently discarded.

### 13.3 The "no labeled dataset needed" claim is true but incomplete

The proposal is right that human approval/rejection is a real, usable reward signal, and right that it doesn't require a separately-curated labeled dataset. What it doesn't address: **that signal already has a planned consumer** — Feature 5 (§11.1) builds the exact confirm/reject collection mechanism this proposal would need, feeding a small bandit-style weight update. The signal *existing* and the signal being *sufficient in volume* for GNN training are different claims; nothing in the proposal changes the volume math established earlier in this conversation (a handful of test documents' worth of approvals today, RLHF-style training typically wanting far more). Feature 5 is the right consumer of this signal at today's volume; a GNN becomes worth revisiting only once Feature 5's bandit has been running against real production usage long enough to show it isn't good enough — matching §11.5's existing gate for ExpressGNN, now with this proposal's concrete architecture as the thing to build if that day comes.

### 13.4 Link prediction / rule mining overlap with Feature 3 — related, not redundant

The proposal's third use case (GNN-based link prediction as a rule-mining aid) is not the same thing as Feature 3 (§5), which mines candidate rules by frequency-counting existing `(edge_type, source_type, target_type)` patterns — purely symbolic, no learned embeddings. A trained link predictor could in principle surface candidates a frequency-based miner would miss (patterns based on embedding similarity rather than exact type-pattern repetition). That's a real, distinct capability, not overlap to dismiss — but it inherits the same data-volume gate as the rest of this section, and Feature 3 already covers the lower-cost, higher-confidence version of "which relations deserve becoming a rule" for today's scale.

### 13.5 Infra note, updated from the earlier objection

The original GNN critique in this conversation was partly about GPU-scale training against FB15K-237-sized benchmarks — that objection doesn't fully apply here, since this proposal is scoped to this project's own (much smaller) graphs, where R-GCN training could plausibly run CPU-only. That removes one objection, not all of them: PyTorch + PyTorch Geometric is still a new dependency class this project has consistently avoided (per `MVP_PLAN.md`'s "rebuild natively" convention cited throughout this plan), and a trained model still needs versioning, a training loop, and a fallback path for when it's unavailable — none of which exist today and all of which are real engineering cost, just not GPU-cost specifically.

### 13.6 Bottom line

**Recommendation: document, don't schedule.** Nothing in §13 goes into the checklist. If Feature 5's bandit is running in production and demonstrably underperforming, revisit this section as the starting architecture spec — correct the replace→augment contradiction (§13.2) before building anything, and treat §13.4's link-prediction angle as the more likely first-value use case (it fills a real gap Feature 3 doesn't) rather than starting with salience/weight augmentation (§13.1–13.2), which delivers less obvious value for meaningfully more risk.
