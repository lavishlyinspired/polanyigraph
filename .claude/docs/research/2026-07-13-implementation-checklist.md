# Implementation Checklist

> Companion to `2026-07-13-rule-mining-and-compound-query-implementation-plan.md` — same features, ordered as a build sequence with checkboxes. Update this file's checkboxes as work lands; don't duplicate status in the plan doc itself.
>
> **Revision note (2nd)**: §10 ("Loop Engineering — analysis and verdict," the repo-maintenance Daily Triage idea) is **out of scope for this checklist** — not being built. Dropped entirely, including the `LOOP_STATE.md` state file. What stays in scope is §12, "Loop Engineering applied to the core agentic orchestration framework" — the part that actually touches this project's own KG business logic (Feature 7, the autonomous graph maintenance loop) and Feature 4's synthesis step (§12.4's grounding check). Those are represented explicitly below, not scattered into other phases.

## Phase 1 — De-risk the reasoning engine (no dependencies, do first)

- [x] **Feature 1: Rule Aggregation Policy** (plan §3) — **done**
  - [x] Two-pass restructure of `run_inference` in `reasoning/engine.py`
  - [x] `DerivedFact.supporting_rule_ids` + `contributing_fact_ids` fields
  - [x] Noisy-OR combination for multi-rule firings on the same edge
  - [x] `reason()`'s idempotency bookkeeping updated to track all contributing rules' fact ids, not just the merged fact's id (regression guard test added)
  - [x] Tests: aggregation (noisy-OR value + supporting/contributing ids), single-rule case unchanged, no re-firing across iterations — `tests/test_reasoning.py`, 14/14 passing including 3 new tests
- [x] **Feature 2: Semantic Conditioning at Inference** (plan §4) — **done**
  - [x] Confirmed the ontology loader had no domain/range check yet; added `OntologySchema.build_domain_range_matcher()` in `ontology/schema.py`, fail-open for properties the loaded ontology doesn't describe
  - [x] Added `domain_range_check` param (default permissive `_always_valid`) to both `run_inference` and `reason()` in `reasoning/engine.py`, new `"ontology domain/range violation: ..."` skip_reason
  - [x] Wired through `reasoning_service.run_reasoning` via `schema.build_domain_range_matcher()`
  - [x] Tests: `tests/test_ontology_subclass.py` (6 new: accepts correct typing, rejects wrong source/target, subclass-aware, fails open for unknown property, fails open with no properties loaded) + `tests/test_reasoning.py` (2 new: gate actually skips a rule that would otherwise fire, default behavior unchanged when not supplied) — 29/29 passing across both files
  - [x] Confirmed all files touched (`reasoning/engine.py`, `ontology/schema.py`, `services/reasoning_service.py`) and every test importing them collect cleanly (live Neo4j/GraphDB-dependent tests can't execute in this sandbox, but import/wiring is verified sound)

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

## Phase 4 — Compound-query answering, including §12's core-framework Loop Engineering additions

- [ ] **Spike first**: throwaway 3-node LangGraph (`start → [Send(a), Send(b)] → join → end`) proving fan-out/fan-in + `Annotated[dict, operator.or_]` concurrent-write pattern works against the installed LangGraph version (plan §6.9)
- [ ] **Feature 4: Compound-Query Answering** (plan §6)
  - [ ] `Settings.enable_compound_queries` flag (default off)
  - [ ] `AgentState`: `intents`, `partial_answers` (with `operator.or_` reducer), `combined_answer`
  - [ ] Router: comma-list parsing, compound few-shot examples (flag-gated)
  - [ ] Dispatch via `Send`, eligibility check against Feature 0's selector (not a second hardcoded map)
  - [ ] Specialist nodes (`reasoner`, `querier`, `enricher`, `memory_agent`) write `partial_answers`
  - [ ] Conditional post-specialist routing (`combiner` vs `responder`)
  - [ ] `combiner_node` (deterministic)
- [ ] **§12.4 — maker/checker grounding check** (plan §12.4, folded into Feature 4, not a separate feature number): `responder_node`'s compound branch gets a deterministic `_find_ungrounded_claims` check + one bounded LLM retry if it finds an over-claim — the model that synthesized the answer is not the one that checks it
  - [ ] Test: a deliberately fabricated over-claiming `reply` triggers exactly one retry, not a loop
- [ ] Tests: router parsing (single/compound/garbage), `combiner_node` unit test, full regression suite with flag off (must be bit-for-bit identical), integration test with flag on against 2–3 real compound queries
- [ ] Live-verify once in the browser with flag on in dev config

### §12.1 / §12.2 — already true today, confirm only, no code

- [ ] **§12.1**: confirm `reasoning/engine.py`'s `reason()` convergence loop (spread → infer → feed back → check convergence → repeat) is documented as this project's existing instance of the source's `/goal` primitive — no implementation, just a one-line pointer added to `engine.py`'s module docstring or `PLAN.md` §8.4
- [ ] **§12.2**: confirm every human-approval point introduced by Features 3/5/6 (mined-rule approval, derived-fact confirm/reject, duplicate-entity flagging) is consistently described as the same "Human Gate" pattern in each feature's own UI copy/docs

## Phase 5 — Independent add-ons (any order, after their stated deps)

- [ ] **Feature 6: Embedding-based entity resolution** (plan §11.2) — no dependencies, can ship any time
  - [ ] Dedup check in `ingest_service.py` using existing `summaryEmbedding` cosine similarity
  - [ ] Tests: near-identical names flagged; genuinely different similar-looking names not flagged
- [ ] **Feature 5: Rule confidence evolves from human review** (plan §11.1) — depends on Feature 3 + Feature 0 Stage B
  - [ ] `rules_store.update_rule_weight`
  - [ ] Confirm/reject UI affordance for `:DerivedFact` (reuse enrichment's component)
  - [ ] Test: scripted confirm/reject sequence converges weight to known ratio

## Phase 6 — Autonomous graph maintenance loop (plan §12.3 — hard dependency on 3, 5, 6; cannot move earlier)

- [ ] **Feature 7: Autonomous Graph Maintenance Loop** (plan §12.3)
  - [ ] `services/graph_maintenance_loop.py` orchestrating mine → reason → dedup-check → weight-update
  - [ ] State: `GRAPH_LOOP_STATE.md` or `:LoopRun` Neo4j nodes (decide before building) — this is Feature 7's own state file, scoped to graph upkeep, unrelated to the dropped §10 repo-maintenance idea
  - [ ] `mcp__scheduled-tasks__create_scheduled_task` wiring
  - [ ] Confirm L1-safe-by-construction claim holds (every step lands on an existing human gate — true by construction since Features 3/5/6 were each designed with a mandatory human gate from the start)

---

**Not on this checklist, by design** (plan §8/§11.5 Non-goals, plus §10 dropped per your instruction): PyTorch/PyTorch Geometric, GPU training, FB15K-237/NELL-995 benchmarking, full ExpressGNN/variational EM, MAGNet's literal RL machinery, temporal reasoning (flagged open in plan §11.3, deliberately deferred to its own future plan), and §10's repo-maintenance Daily Triage loop / `LOOP_STATE.md`.

**Documented but deliberately not scheduled**: plan §13, an R-GCN-based GNN reference design for salience/edge-weight augmentation and link-prediction-based rule mining — real architecture spec worth keeping, gated behind Feature 5's bandit proving insufficient on real production confirm/reject volume first. Nothing in §13 has a checklist item above; revisit §13 directly if that gate is ever met.
