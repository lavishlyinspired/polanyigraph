# Neurosymbolic Research → Project Integration Plan

> **Date**: July 12, 2026
> **Scope**: Maps 8 external sources (survey paper, GitHub org, workshop proceedings, 2 GNN/RL papers, 1 blog post, 1 Medium article) onto this project's actual architecture (`PLAN.md`, `MVP_PLAN.md`, `backend/reasoning/engine.py`, `backend/agents/graph.py`), and proposes what to incorporate.

---

## 1. What this project currently does (baseline)

Per `PLAN.md` and `MVP_PLAN.md`, the reasoning layer is **purely symbolic**:

- `backend/reasoning/engine.py` — forward-chaining, fixpoint rule engine over the FIBO ontology. Rules fire deterministically on (rule, edge) matches; a 3-step manual loop (spread activation → run inference → feed back) plus an atomic "run to convergence" shortcut.
- Every derived fact carries a full proof-path (`InferenceTraceEntry`, fired/skipped + reason) — good interpretability, no learned component.
- Extraction and enrichment (11 Polanyi heuristics) are LLM-prompted, not graph-embedding-based.
- The agent layer (`backend/agents/graph.py`) is a **LangGraph** with 7 deterministic nodes (`router`, `extractor`, `enricher`, `querier`, `reasoner`, `memory_agent`, `responder`) — routing is a classified-intent dispatch, not a trained policy.
- No knowledge-graph embeddings, no GNN, no rule-weight learning, no RL anywhere in the stack.

This means the project is **symbolic-only today**, despite being named/scoped "neurosymbolic." The research below is essentially a menu of ways to make it genuinely hybrid — or a set of reasons to consciously stay symbolic.

---

## 2. Source-by-source findings

### 2.1 DeLong, Mir & Fleuriot — *"Neurosymbolic AI for Reasoning over Knowledge Graphs: A Survey"*
(arXiv:2302.07200, published as IEEE TNNLS 2024, doi:10.1109/TNNLS.2024.3420218 — this **is** the paper behind `ieeexplore.ieee.org/document/10603423`, so those two links are the same work, one paywalled one open)

The survey's taxonomy is the single most useful artifact here. It splits 34 surveyed methods into three categories:

1. **Logically-informed embedding approaches** — symbolic inference augments the graph first, then a KG-embedding method (TransE-style, GNN, etc.) trains on the augmented graph. Inference and embedding are sequential, one-directional.
2. **Learning with logical constraints** — an embedding/GNN model is trained under logical rules that restrict what it's allowed to predict (regularization terms or loss penalties for rule violations). Logic bounds the neural model but doesn't get updated by it.
3. **Rule learning approaches** — the two directions run iteratively: a neural/embedding component proposes or scores rules, a symbolic component evaluates them over the graph, and the two sides update each other (e.g., ExpressGNN, RNNLogic, ANet). This is the category that actually matches the word "neurosymbolic" in the strong sense — bidirectional, not just sequenced.

**Where this project sits today**: none of the three. The reasoning engine is 100% rule-based with hand-authored rules and no embedding component at all — it precedes even category 1.

**Where this project could move**: category 1 first (cheapest, lowest regression risk), category 3 only if a learned confidence/rule-weight layer is genuinely wanted.

### 2.2 NeSymGraphs GitHub org (github.com/NeSymGraphs)
30 forked repos, one per method surveyed in 2.1, curated by the same authors (Edinburgh). Acts as a reference implementation catalog, not something to depend on directly (these are frozen forks of other people's research code — inconsistent Python/PyTorch versions, no packaging). Useful as **prior art to read**, not as a dependency to `pip install`. Most relevant repos for this project's domain (KG completion over FIBO-style typed graphs):
- `ExpressGNN` — see 2.3.
- `RNNLogic` — learns logic rules with an RNN generator + reasoning predictor, iterative EM-style training. Same "rule learning" category as ExpressGNN, C++-heavy, harder to adapt.
- `LPRules` (IBM) — rule induction via linear programming; lighter weight than RNNLogic, worth a skim for the induction algorithm on this project's own rule format.
- `reonto-relation-extraction` (ReOnto) — ontology + GNN for relation extraction from text. Directly relevant to the *extraction* skill (currently LLM-only), not just reasoning.

### 2.3 ExpressGNN — *"Efficient Probabilistic Logic Reasoning with Graph Neural Networks"* (arXiv:2012.09762, github.com/NeSymGraphs/ExpressGNN)
Combines Markov Logic Networks (MLN) with a GNN: instead of the traditional MLN grounding (combinatorial and expensive), ExpressGNN uses **tunable knowledge-graph embeddings** for most entities/relations plus a small set of learnable per-predicate weights, trained via variational EM. The GNN provides compact, generalizable entity representations; the MLN provides interpretable weighted first-order rules. Evaluated on Kinship and FB15k-237 — relational, closed-domain, rule-dense benchmarks, structurally similar to a FIBO-typed financial KG.

**Direct applicability**: this is the closest published architecture to "the current rule engine, but with learned rule confidence instead of hand-set thresholds." Rather than a fixpoint that treats every rule as certain-or-not, an ExpressGNN-style layer would give each rule a *learned weight*, and inference would become weighted/probabilistic (a fact "fires" with a confidence, not a boolean). This maps naturally onto the existing `InferenceTraceEntry` design (which already has a `skip reason` and could carry a `confidence` field).

Cost/risk: this is a real ML component — training data (positive/negative fact examples), a training loop, model versioning, and non-determinism, none of which exist in the codebase today. It's the highest-effort item in this plan.

### 2.4 AIhub — *"Neurosymbolic AI for graphs: a crime scene analogy"*
Plain-language explainer of 2.1's taxonomy (detective = neural/pattern-finder, forensic scientist = symbolic/logical, corkboard = the graph). No new technical content beyond 2.1 — useful only as onboarding material if this project ever needs to explain "what does neurosymbolic mean here" to a non-ML stakeholder (e.g., in a README or the business-analyst-facing docs, since the target audience per `PLAN.md` §1 is business analysts).

### 2.5 ICML 2023 Workshop — *Knowledge and Logical Reasoning in the Era of Data-driven Learning* (klr-icml2023.github.io)
60+ accepted papers; most relevant subset for this project:
- **DeLong et al., "Neurosymbolic AI for Reasoning on Biomedical Knowledge Graphs"** — the same author group's abridged, biomedical-domain version of 2.1. Relevant if this project's FIBO focus ever generalizes to other typed ontologies (it validates that the taxonomy transfers domains).
- **Pryor, Dickens & Getoor, "Deep Neuro-Symbolic Weight Learning in Neural Probabilistic Soft Logic"** — PSL (Probabilistic Soft Logic) with learned weights; PSL is often cited as more tractable than full MLN and might be a lighter-weight alternative to ExpressGNN for learned rule confidence.
- **Betz, Lüdtke, Meilicke & Stuckenschmidt, "On the Aggregation of Rules for Knowledge Graph Completion"** — directly about combining multiple fired rules' outputs, relevant to how the fixpoint engine currently just ORs rule firings together.
- **Ledaguenel, Hudelot & Khouadjia, "Semantic Conditioning at Inference"** — improving a neural model's *outputs* with logical background knowledge at inference time only (no retraining) — the cheapest possible integration pattern, worth considering before anything training-based.

The rest (LLM planning, visual reasoning, algorithmic alignment) is out of scope for this project.

### 2.6 MAGNet — *"Multi-agent Graph Network for Deep Multi-agent Reinforcement Learning"* (arXiv:2012.09762 — verified: this is the correct paper text)
Not a KG-reasoning paper — a MARL paper. Agents and environment objects are nodes in a *relevance graph* (learned via self-attention from state history), edges are learned importance weights, and decision-making happens via a message-passing actor-critic over that graph. Key mechanism: **relevance-graph generation is pre-trained separately, then frozen/fine-tuned alongside the policy network** — this decoupling (graph structure learned first, decisions learned second) is a useful pattern independent of the RL specifics.

**Where this maps onto the project**: the LangGraph agent layer (`router`, `extractor`, `enricher`, `querier`, `reasoner`, `memory_agent`, `responder`) is structurally a fixed graph with deterministic routing today. MAGNet's core idea — model agent-to-agent (or here, node-to-node/skill-to-skill) relevance as a learned, weighted graph rather than a fixed dispatch table — is the conceptual bridge to 2.7's MAGRL article. Not something to lift wholesale (Pommerman/predator-prey specifics don't transfer), but the "relevance graph over agents, decoupled from decision-making" idea does.

### 2.7 Akash Goyal — *"Ontology-Grounded Multi-Agent Graph Reinforcement Learning (MAGRL) for Healthcare"* (Medium, Jan 2026)
Paywalled beyond the intro (member-only); visible content: MAGRL "models agents as nodes in a graph and their interactions as edges," explicitly grounded by ontologies/KGs, targeted at clinical multi-agent decision systems. This reads as the author's own synthesis of 2.1 (neurosymbolic KG reasoning) + 2.6 (MAGNet-style graph-structured MARL), specialized to a healthcare ontology instead of FIBO.

**Direct applicability**: this is the most structurally relevant piece to your *own* project, since it's the same author independently arriving at "ontology + graph + multi-agent RL" for a different domain (healthcare vs. this project's finance/FIBO). It suggests the natural v2 direction for this project's agent layer: instead of (or alongside) the deterministic router, an **ontology-grounded relevance/policy graph over the 7 LangGraph nodes and 6 skills**, where routing weights are learned from skill-usage history — which the project already half-has via `§18`'s Neo4j skill graph (`:Skill`, `USED_IN`, `record_skill_usage`, confidence scores). That skill graph is currently a lookup table; MAGRL-style thinking is what would turn it into an actual learned policy.

---

## 3. Gap analysis: research → this project

| Research theme | Project component it touches | Current state | Gap |
|---|---|---|---|
| Logically-informed embeddings (2.1 cat. 1) | `reasoning/engine.py` | Pure rules, no embeddings | No KG embedding layer exists at all |
| Rule weight/confidence learning (2.1 cat. 3, 2.3, 2.5-Pryor) | `reasoning/engine.py`, `InferenceTraceEntry` | Boolean fire/skip only | No learned confidence; `heuristicType` enum is fixed, not learned |
| Semantic conditioning at inference only (2.5-Ledaguenel) | `services/reasoning_service.py` | N/A | Cheapest possible neurosymbolic upgrade, unexplored |
| Rule aggregation across multiple firings (2.5-Betz) | `reasoning/engine.py` fixpoint loop | Rules OR'd together implicitly | No principled aggregation/conflict policy |
| Ontology-driven relation extraction with GNN (2.2-ReOnto) | `kg-extraction` skill | LLM-prompted extraction only | No graph-structural signal used during extraction |
| Graph-structured agent routing / learned relevance (2.6 MAGNet, 2.7 MAGRL) | `backend/agents/graph.py`, `§18` Neo4j skill graph | Deterministic router + static skill graph with usage-based confidence (not RL) | Skill graph confidence is a rolling average, not a trained policy; router doesn't consult it before dispatch (per `§18.3`, that wiring is still pending) |
| Plain-language framing for non-ML stakeholders (2.4) | Docs / business-analyst-facing UI copy | `PLAN.md` has no "what is neurosymbolic" explainer | Low priority, easy win |

---

## 4. Recommended incorporations, prioritized

### Tier 1 — cheap, low-risk, ship soon
1. **Wire the router to `find_relevant_skills` before `load_skill`**, per the already-planned but unimplemented `§18.3` item. This is not new research — it's finishing existing scope — but it's the prerequisite for anything MAGRL-flavored (4.3 below) to matter later, since there needs to be a real usage-weighted signal in the loop before it can be learned over.
2. **Semantic-conditioning-at-inference pass** (2.5-Ledaguenel pattern): before returning `reasoner` node output, run a cheap post-hoc consistency check against ontology constraints already loaded (`fibo.py`) — reject/flag derived facts that violate a subclass or domain/range constraint even if the rule fired. No training, no new dependency, reuses the existing `InferenceTraceEntry` skip-reason mechanism.
3. **Add a "what is neurosymbolic AI" explainer** to the business-analyst-facing docs/UI, adapted from the crime-scene analogy (2.4) with FIBO-flavored examples (a rule-based deduction vs. a learned pattern) instead of a corkboard. One afternoon of writing.
4. **Add a rule-aggregation policy** (2.5-Betz): when multiple rules derive the same fact independently, currently they likely just co-exist as separate proof paths. Define and document an explicit aggregation rule (e.g., "most specific ontology match wins" or "highest hand-set rule priority wins") rather than leaving it implicit.

### Tier 2 — medium effort, real architectural addition
5. **Learned rule confidence layer**, PSL-flavored (2.5-Pryor) rather than full ExpressGNN (2.3) to start — PSL's soft-logic/weighted-satisfaction framing is a smaller lift than MLN+GNN joint training, and produces a `confidence: float` per rule that slots directly into the existing `InferenceTraceEntry`/derived-fact schema without changing the rest of the pipeline. Requires: a small labeled set of "known-good" vs. "known-bad" derived facts (can be bootstrapped from human-in-the-loop enrichment corrections already captured by the enricher node), a weight-learning loop, versioned weights stored alongside the ontology.
6. **KG-embedding-augmented extraction** (2.2-ReOnto pattern): give the `kg-extraction` skill a lightweight GNN or embedding signal over the *already-extracted* portion of the graph, to bias entity/relation typing toward locally-consistent structure, on top of the existing LLM extraction — not a replacement.

### Tier 3 — larger bets, evaluate before committing
7. **Full ExpressGNN-style joint MLN+GNN reasoning layer** (2.3): only worth it if Tier 2's simpler PSL weighting proves insufficient — i.e., if rule confidence alone doesn't capture cases where the *graph structure itself* (not just which rules fired) should influence what's inferred. This is a genuine new ML subsystem: training data curation, a training/eval loop, model versioning, non-determinism handling, and a fallback path when the model is unavailable (mirroring the `ResilientSkillDiscovery` fallback pattern already used for the skill graph in `§18.4`).
8. **MAGRL-style learned routing policy over the 7 LangGraph nodes / 6 skills** (2.6, 2.7): replace or augment the deterministic router with an ontology-grounded relevance graph whose edge weights are trained from the skill-usage history already being recorded (`record_skill_usage`, `:SkillUsage` nodes). This is the most speculative item — it changes a currently deterministic, fully-tested, live-verified routing path into a probabilistic one, which conflicts with this project's stated preference for determinism and full test coverage (`PLAN.md` §2's "Tool Layer" note explicitly chose *not* to rewire tested nodes for architectural purity). Recommend treating this as a **research spike in a branch**, not a roadmap item, unless routing quality becomes a measured problem with the current deterministic approach.

### Explicitly not recommended
- Depending directly on any `NeSymGraphs/*` fork as a runtime dependency — they're frozen research forks (inconsistent PyTorch/Python pins, no CI, no packaging), consistent with this project's existing "rebuild natively, don't bolt on someone else's library" convention (see `PLAN.md` §19.3, §20 re: Polanyi and Graphiti).
- Adopting MAGNet's exact predator-prey/Pommerman RL machinery — it's a different problem shape (competitive game agents vs. cooperative reasoning/extraction pipeline nodes); only the "learned relevance graph" *idea* transfers, not the implementation.

---

## 5. Suggested sequencing relative to existing phases

- Tier 1 items (esp. #1, the skill-graph routing wire-up) slot into the still-open `§18.3` work — no new phase needed, just closing an already-scoped gap.
- Tier 2 items become a new **Phase 12: Learned Reasoning Confidence** in `PLAN.md` §16, gated behind Phase 8 (Reasoning Engine, already DONE) since it extends rather than replaces it.
- Tier 3 items should **not** get a phase number yet — add them to `PLAN.md`'s existing Decision Record pattern (§18/§19/§20 style) as a proposed "§21: Learned Reasoning — Research Spike," decided only after Tier 1/2 ship and there's real usage data to justify the investment.

---

## 6. Reference list

1. DeLong, L. N., Mir, R. F., & Fleuriot, J. D. (2024). *Neurosymbolic AI for Reasoning over Knowledge Graphs: A Survey.* IEEE TNNLS. doi:10.1109/TNNLS.2024.3420218 / arXiv:2302.07200.
2. NeSymGraphs GitHub organization — https://github.com/NeSymGraphs (30 forked reference repos, curated by DeLong et al.)
3. Mir, R. F. & DeLong, L. N. (2023). *Neurosymbolic AI for graphs: a crime scene analogy.* AIhub. https://aihub.org/2023/03/23/neurosymbolic-ai-for-graphs-a-crime-scene-analogy/
4. ICML 2023 Workshop, *Knowledge and Logical Reasoning in the Era of Data-driven Learning* — https://klr-icml2023.github.io/papers.html
5. Zhang, Y., Chen, X., Yang, Y., Ramamurthy, A., Li, B., Qi, Y., & Song, L. (2020). *Efficient Probabilistic Logic Reasoning with Graph Neural Networks.* arXiv:2012.09762 (ExpressGNN). Code: https://github.com/NeSymGraphs/ExpressGNN
6. Malysheva, A., Kudenko, D., & Shpilman, A. (2020). *MAGNet: Multi-agent Graph Network for Deep Multi-agent Reinforcement Learning.* arXiv:2012.09762. *(Note: same arXiv ID as source 5 in this task's link list, per the user-supplied URL — content confirmed to be the MAGNet paper, not ExpressGNN; verify the intended ID if source 5's paper was meant to be a different identifier.)*
7. Goyal, A. (2026). *Ontology-Grounded Multi-Agent Graph Reinforcement Learning (MAGRL) for Healthcare.* Medium. https://medium.com/@aiwithakashgoyal/ontology-grounded-multi-agent-graph-reinforcement-learning-magrl-for-healthcare-7f565da526f9 (paywalled past intro)
8. This project's own `PLAN.md`, `MVP_PLAN.md`, and `.claude/docs/gaps.md` — used as the baseline for the gap analysis in §3.

> **Flag**: sources 5 and 6 in the original request both resolved to arXiv ID `2012.09762`, but that ID is MAGNet (multi-agent RL), not the ExpressGNN paper "Efficient Probabilistic Logic Reasoning with Graph Neural Networks" (which is arXiv:2012.09702, one digit off). Section 2.3 above describes ExpressGNN correctly from its GitHub README and known publication record; Section 2.6 describes what actually loaded at the `2012.09762` PDF link. Worth double-checking the ExpressGNN arXiv ID before citing it elsewhere.
