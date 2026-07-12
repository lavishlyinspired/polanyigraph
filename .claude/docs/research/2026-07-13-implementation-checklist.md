# Implementation Checklist

> Companion to `2026-07-13-rule-mining-and-compound-query-implementation-plan.md` — same features, ordered as a build sequence with checkboxes. Update this file's checkboxes as work lands; don't duplicate status in the plan doc itself.

## Phase 1 — De-risk the reasoning engine (no dependencies, do first)

- [ ] **Feature 1: Rule Aggregation Policy** (plan §3)
  - [ ] Two-pass restructure of `run_inference` in `reasoning/engine.py`
  - [ ] Add `DerivedFact.supporting_rule_ids: tuple[str, ...] = ()`
  - [ ] Noisy-OR combination for multi-rule firings on the same edge
  - [ ] Test: two rules firing on the same edge → one `DerivedFact`, correct noisy-OR confidence
  - [ ] Confirm all existing reasoning tests still pass unchanged
- [ ] **Feature 2: Semantic Conditioning at Inference** (plan §4)
  - [ ] Confirm/expose `domain_range_check` on the ontology loader (check first — may already exist)
  - [ ] Add optional `domain_range_check` param to `run_inference`, new skip_reason
  - [ ] Wire through `reasoning_service.run_reasoning`
  - [ ] Test: deliberately mis-typed edge is skipped with the new reason, not fired

## Phase 2 — Rule mining (self-contained, no agent-layer risk)

- [ ] **Feature 3: Rule Mining** (plan §5)
  - [ ] `services/rule_mining_service.py`: `mine_candidates`, `list_candidates`, `approve_candidate`, `reject_candidate`
  - [ ] `:CandidateRule` Neo4j schema (MERGE-safe deterministic id)
  - [ ] `approve_candidate` calls existing `rules_store.create_rule` — confirm zero engine changes needed
  - [ ] REST endpoints: `POST /rules/mine/{graph_id}`, `GET /rules/candidates`, `POST /rules/candidates/{id}/approve`, `POST /rules/candidates/{id}/reject`
  - [ ] Frontend: "Suggested Rules" section in the existing Rules Manager
  - [ ] Tests: known repeating pattern → correct support/confidence; already-covered combo not re-proposed; approve → real rule fires in `run_reasoning`; reject → not re-surfaced
  - [ ] `evals/cases/rule-mining/case-01.json`

## Phase 3 — Skill-graph-driven selection (prerequisite for Feature 4)

- [ ] **Feature 0, Stage A: symbolic selection** (plan §2)
  - [ ] `_select_skill()` replaces direct `_SKILL_BY_INTENT.get(intent)` calls, hardcoded map demoted to fallback
  - [ ] Test: discovery-driven selection overrides the old hardcoded mapping when confidence is high
  - [ ] Test: Neo4j-down fallback still completes (mirrors existing `ResilientSkillDiscovery` degradation test)
- [ ] **Feature 0, Stage C: ontology-constrained eligibility** (plan §2)
  - [ ] Filter candidates by `:EntityType`/`:Domain` match before ranking
  - [ ] Test: entity-type mismatch excludes an otherwise-high-scoring skill
- [ ] **Feature 0, Stage B: bandit** (plan §2) — defer until Stage A has real usage data
  - [ ] Upgrade `record_usage`'s rolling average to epsilon-greedy/Thompson sampling
  - [ ] Test: scripted success/failure sequence converges toward the better skill

## Phase 4 — Compound-query answering (touches tested agent topology — flagged off by default)

- [ ] **Spike first**: throwaway 3-node LangGraph (`start → [Send(a), Send(b)] → join → end`) proving fan-out/fan-in + `Annotated[dict, operator.or_]` concurrent-write pattern works against the installed LangGraph version (plan §6.9)
- [ ] **Feature 4: Compound-Query Answering** (plan §6)
  - [ ] `Settings.enable_compound_queries` flag (default off)
  - [ ] `AgentState`: `intents`, `partial_answers` (with `operator.or_` reducer), `combined_answer`
  - [ ] Router: comma-list parsing, compound few-shot examples (flag-gated)
  - [ ] Dispatch via `Send`, eligibility check against Feature 0's selector (not a second hardcoded map)
  - [ ] Specialist nodes (`reasoner`, `querier`, `enricher`, `memory_agent`) write `partial_answers`
  - [ ] Conditional post-specialist routing (`combiner` vs `responder`)
  - [ ] `combiner_node` (deterministic)
  - [ ] `responder_node` compound branch + §12.4's grounding-check-and-bounded-retry
  - [ ] Tests: router parsing (single/compound/garbage), `combiner_node` unit test, full regression suite with flag off (must be bit-for-bit identical), integration test with flag on against 2-3 real compound queries
  - [ ] Live-verify once in the browser with flag on in dev config

## Phase 5 — Independent add-ons (any order, after their stated deps)

- [ ] **Feature 6: Embedding-based entity resolution** (plan §11.2) — no dependencies, can ship any time
  - [ ] Dedup check in `ingest_service.py` using existing `summaryEmbedding` cosine similarity
  - [ ] Tests: near-identical names flagged; genuinely different similar-looking names not flagged
- [ ] **Feature 5: Rule confidence evolves from human review** (plan §11.1) — depends on Feature 3 + Feature 0 Stage B
  - [ ] `rules_store.update_rule_weight`
  - [ ] Confirm/reject UI affordance for `:DerivedFact` (reuse enrichment's component)
  - [ ] Test: scripted confirm/reject sequence converges weight to known ratio

## Phase 6 — Autonomous graph maintenance loop (depends on 3, 5, 6)

- [ ] **Feature 7: Autonomous Graph Maintenance Loop** (plan §12.3)
  - [ ] `services/graph_maintenance_loop.py` orchestrating mine → reason → dedup-check → weight-update
  - [ ] State: `GRAPH_LOOP_STATE.md` or `:LoopRun` Neo4j nodes (decide before building)
  - [ ] `mcp__scheduled-tasks__create_scheduled_task` wiring
  - [ ] Confirm L1-safe-by-construction claim holds (every step lands on an existing human gate)

## Separate layer — not gated by anything above, optional, any time

- [ ] **§10: Engineering loop for this repo** (Daily Triage) — repo maintenance, not the runtime app
  - [ ] `LOOP_STATE.md`
  - [ ] Scheduled task: nightly test/eval run, report-only (L1)
  - [ ] Explicitly do not progress past L2 (assisted, human-reviewed) for this project

---

**Not on this checklist, by design** (plan §8/§11.5 Non-goals): PyTorch/PyTorch Geometric, GPU training, FB15K-237/NELL-995 benchmarking, full ExpressGNN/variational EM, MAGNet's literal RL machinery, temporal reasoning (flagged open in plan §11.3, deliberately deferred to its own future plan).
