# MVP Plan — Neurosymbolic KG (v0.1, workable, real data only)

> **Created**: July 11, 2026
> **Relationship to PLAN.md**: PLAN.md is the full v1+ architecture. This is the *walking skeleton* — the smallest end-to-end slice that produces real value for a business analyst, with **zero demo/mock data**. Everything here is a strict subset of PLAN.md; nothing contradicts it.
> **[UPDATED] Status**: **All 10 phases below are now DONE, and EDGAR (originally "optional") is also now done.** Phase 6 (LangGraph wrap) — the last original MVP item — is implemented, tested, and live-verified; see §9 Phase 6. PLAN.md §1.1 cross-references this file's phase numbers against its own (broader, non-matching) §16 phase list — read that note if "Phase N" is ambiguous between the two docs.

---

## 1. The one vertical slice

> **An analyst pastes (or fetches) a real financial document → the system extracts a real entity/relationship graph with a real LLM → writes it to Neo4j → runs neurosymbolic reasoning over it → the analyst sees the real graph, derived facts, and can query it.**

If that flow works end-to-end on a real 8-K or press release, the MVP is done. Everything else in PLAN.md is deferred.

## 2. Hard rules

- **No demo data.** The current `src/lib/fibo-data.ts` seed graph and the `src/lib/llm.ts` keyword mock (`llmRespond`) are **removed from the running path**. Graph content comes only from real extraction of real documents.
- **Real LLM.** Extraction and reasoning explanation use a live model over an OpenAI-compatible endpoint (default: NVIDIA-hosted GLM `z-ai/glm-5.2`, configurable). No canned responses. Offline keyword fallback is allowed only as an explicit, labeled dev toggle — never the default, never presented as extraction output.
- **Real, domain-agnostic ontology.** The ontology lives in **Ontotext GraphDB** (RDF/OWL) and defines the entity **types**. Whatever ontology is loaded in the configured repository (`fibo` today, any OWL tomorrow) is the vocabulary — nothing is hardcoded. The graph's *nodes and edges* are still 100% extracted from user documents.
- **Workable = runnable.** Neo4j Desktop + GraphDB Desktop running locally, `uvicorn` backend, `npm run dev` frontend — a working app extracting a real document.

## 3. Explicitly cut from the MVP (deferred to v1 per PLAN.md)

| Deferred | Why it's not in the MVP |
|---|---|
| Redis + PostgreSQL | Two stores only: **Neo4j** (instances + reasoning + LangGraph checkpointing via `Neo4jSaver`) and **GraphDB** (ontology/RDF). No Redis/Postgres. Qdrant (in `.env`) is deferred to v1 for vector memory. |
| MCP servers (all 4) | No external agent surface needed to prove the slice. |
| Dual dev/runtime skill system + **Neo4j skill graph** | Skill graph stays a **v1** feature (PLAN.md §18); the MVP hardcodes the pipeline. |
| Five-memory-system layer (episodic/semantic/long-term) | MVP keeps only conversation checkpointing + the graph itself. |
| Polanyi 11-heuristic enrichment | **[UPDATED]** All 11 heuristics now implemented and live-verified running together (25 real facts across 10 heuristic types on one real scenario) as a v1 addition beyond the original MVP scope — see `PLAN.md` §19.6 steps 1–4. Only the frontend (Enrich tab, `UI_PLAN.md` §9.3) still not started. |
| NL → Cypher | MVP ships the structured triple query (`predicate(subject, object)`) that already exists; NL→Cypher is v1. |
| Multi-agent router/enricher/etc. | MVP LangGraph = `extractor → reasoner → responder` only. |

**[REVERSED]** Manual node/edge/rule construction (the prototype's `ConstructionPanel`) was initially cut as conflicting with "real data only" — reinstated per explicit direction. Resolution: it's real, not demo — every manual add is validated against the live ontology and persisted to Neo4j exactly like an extraction, so it's a second real-data input method (analyst-asserted facts), not a mock. See §9 Phase 8.

## 4. Architecture (lean)

```
┌──────────────────────────────────────────────┐
│ Frontend (existing React prototype, rewired)  │
│  IngestPanel → GraphCanvas → InspectorPanel   │
│  Zustand (graphStore, agentStore)             │
│  lib/api.ts  → REST + SSE (no mock llm.ts)    │
└───────────────────────┬──────────────────────┘
                        │ HTTP / SSE
┌───────────────────────┴──────────────────────┐
│ Backend (FastAPI)                             │
│  /ingest  → extraction/pipeline.py (real LLM) │
│  /graph   → services/graph_service.py         │
│  /reason  → reasoning/engine.py (§8.4 fixed)  │
│  /query   → structured triple query           │
│  LangGraph: extractor → reasoner → responder  │
│             (Neo4jSaver checkpointing)        │
└───────────────────────┬──────────────────────┘
              bolt:// │        │ SPARQL (http://localhost:7200)
┌───────────────────┴──┐  ┌──┴──────────────────────────────┐
│ Neo4j Desktop (LPG)  │  │ Ontotext GraphDB Desktop (RDF)   │
│  extracted instances │  │  ontology = types/constraints    │
│  activation + facts  │  │  domain-agnostic (repo = domain) │
│  LangGraph checkpts  │  │  SPARQL vocabulary discovery     │
└──────────────────────┘  └──────────────────────────────────┘
```

## 5. Backend spec

**Stack**: FastAPI, `neo4j` driver, `httpx` (GraphDB SPARQL), `openai` SDK (pointed at the NVIDIA endpoint), `pydantic` v2, `langgraph` (Phase 6, now wired in — `backend/agents/`). TDD throughout (pytest, 198 tests).

**Models**: OpenAI-compatible endpoint, model configurable via `NVIDIA_MODEL`/`LLM_BASE_URL`. Default is `meta/llama-3.1-8b-instruct` (§11 — `z-ai/glm-5.2` hangs on real chat completions in this environment). No vendor hardcoded — call sites depend only on `llm.client.LLMClient`.

### 5.1 Endpoints

| Method | Path | Body / params | Returns |
|---|---|---|---|
| `GET` | `/health` | — | `{status, neo4j, graphdb, llm}` reachability |
| `POST` | `/ingest` | `{graphId, source: {type:"text", text}}` or `{graphId, source: {type:"edgar", ticker, formType}}` | `{nodes, edges, dropped}` written to Neo4j. **Not implemented as SSE** — plain synchronous POST. **[UPDATED]** `source.type: "edgar"` now real — fetches the real filing from SEC's public API via `services/edgar_service.py`, feeds the same extraction pipeline; 404 if no such ticker/form. Each node also carries a real LLM-generated `summary` that accumulates across ingests (PLAN.md §20 item 3). |
| `GET` | `/graph/{graphId}` | — | `{nodes, edges}` (real, from Neo4j). **[UPDATED]** Edges now also carry `validAt`/`invalidAt`/`producedByEventId` (PLAN.md §20 items 1–2); `get_graph` returns current (non-invalidated) edges only. |
| `GET` | `/graph/{graphId}/nodes/{nodeId}/provenance` | — | **[NEW]** `{events}` — every ingest event that produced/touched this entity, via a real `IngestEvent-[:PRODUCED]->Entity` traversal, not a `sourceDoc` string match (PLAN.md §20 item 1) |
| `GET` | `/graph/{graphId}/relationships/history` | `?sourceId=&type=` | **[NEW]** `{edges}` — full history (current + invalidated) for a (source, relation type), including `validAt`/`invalidAt` (PLAN.md §20 item 2) |
| `POST` | `/enrich/{graphId}` | `{text}` | **[NEW, UPDATED]** Runs all 11 Polanyi heuristics (PLAN.md §19, §19.2 — they ship together) against the real graph + given text, one real LLM call per heuristic (~11 sequential calls), returns newly created pending `:ImplicitFact` assertions |
| `GET` | `/enrich/{graphId}/pending` | — | **[NEW]** `{facts}` — pending `:ImplicitFact` assertions awaiting approval |
| `GET` | `/enrich/{graphId}/approved` | — | **[NEW]** `{facts}` — approved `:ImplicitFact` assertions |
| `POST` | `/enrich/{graphId}/{factId}/approve` \| `/reject` | — | **[NEW]** Human-in-the-loop approval/rejection (PLAN.md §7.3); rejected facts are kept with `status: "rejected"`, not deleted |
| `POST` | `/graph/{graphId}/communities` | — | **[NEW]** Runs Neo4j GDS Louvain over the real graph, writes `communityId` onto each entity (PLAN.md §20 item 5) |
| `GET` | `/graph/{graphId}/communities` | — | **[NEW]** `{members}` — reads the last-computed community assignment without recomputing |
| `POST` | `/agent/{graphId}` | `{text, sessionId?}` | **[NEW]** Phase 6 — LangGraph-orchestrated `extractor → reasoner → responder` (`backend/agents/graph.py`). One message in, real extraction + real reasoning + a grounded natural-language reply out. Loads the `kg-extraction` runtime skill (`backend/skills/`, PLAN.md §13.2) for real, not just specced. |
| `POST` | `/reason/{graphId}` | `{sourceId?}` | `{activation, facts, iterations, convergedBy}` (§5.3), each fact carries `ruleName` + `proofPath`; each proof step carries `typeResolution` when the rule fired via ontology subclass match rather than exact type equality |
| `POST` | `/query/{graphId}` | `{query}` e.g. `regulates("FINMA", X)` | `{results, error}` over stored + derived triples |
| `GET` | `/history/{graphId}` | — | `{events}` — every past ingest for this graph: full posted text, timestamp, entity/relationship/dropped counts, most recent first |
| `GET` | `/rules` | — | `{rules}` — seed (`data/rules/fibo_rules.json`, read-only) + custom (Neo4j-stored) rules, each tagged `source: "seed"\|"custom"` |
| `POST` | `/rules` | `{name, edgeType, sourceType, targetType, threshold, weight?, description?}` | Creates a custom rule, validated against the live ontology; participates in `/reason` immediately |
| `DELETE` | `/rules/{ruleId}` | — | Deletes a custom rule (400 if the id isn't `custom-*`, i.e. a seed rule) |
| `GET` | `/graphs` | — | `{graphs}` — every graph that has entities, with node/edge counts + last ingest time, for the UI's graph switcher |
| `POST` | `/chat/{graphId}` | `{message, sessionId?}` | `{reply}` — real LLM call grounded in the graph's actual entities/relationships/derived facts (`services/chat_service.py`). **[UPDATED]** Also grounded in real conversation history for `sessionId` (PLAN.md §20 item 4); omitting `sessionId` defaults to one continuous session per graph. |
| `GET` | `/ontology` | — | `{classLabels, propertyLabels}` — real vocabulary from the loaded ontology, for the Construct tab's Add Node/Edge/Rule pickers |
| `POST` | `/graph/{graphId}/nodes` | `{label, type}` | Manually add an entity (Construct tab), validated against the ontology, `sourceDoc: "manual-entry"`, same id-slug scheme as extraction so it merges with a later real extraction of the same entity |
| `POST` | `/graph/{graphId}/edges` | `{sourceId, targetId, type}` | Manually add a relationship, validated against the ontology + that both nodes exist |
| `PATCH` | `/graph/{graphId}/nodes/{nodeId}` | `{salience?, properties?, note?}` | Partial update of a node's salience, generic key-value properties bag, and freeform note |

### 5.2 Extraction (real, no mock)

- `extraction/pipeline.py`: chunk document → `LLMClient.complete_json` structured call → validate against the `OntologySchema` (types from GraphDB) → dedupe (exact + case-insensitive name match) → `MERGE` into Neo4j with `graph_id`, `source_doc`, `extraction_confidence`.
- Prompt lives in `prompts/extraction.txt`; entity types + relationship taxonomy are injected from the loaded ontology (`ontology/loader.py`), not a hardcoded list.
- Every node/edge records provenance (`source_doc`, `char_span` if available) so nothing in the graph is unattributable.

### 5.3 Reasoning (implements PLAN.md §8.4 — the fixed loop)

`reasoning/engine.py`, ported from `engine.ts` **with the corrections**:

- Load `{nodes, edges}` for `graph_id` from Neo4j.
- **Directed** spread from `source_id` (or highest-degree node if omitted): `newAct = act(src)·decay·weight·salience`, relaxed to a **max-activation fixpoint** (repeat until stable), not a single BFS sweep.
- Fire single-premise rules where `act(source) ≥ threshold`; derive fact on target; **persist** the feedback boost into activation (do not reset between iterations).
- Loop `spread → fire → feedback` until **(no new facts) AND (Δactivation < ε)**, capped at `MAX_ITERATIONS`; return `converged_by ∈ {"fixpoint","max_iterations"}`.
- `fact.confidence = act(premise)·rule.weight`; proof-chain confidence = bounded product. One calculus, surfaced to `/query` and UI.
- Persist derived facts back to Neo4j as `:DerivedFact` nodes with `proof_path`.

### 5.4 Ontology loader (domain-agnostic)

`ontology/loader.py`: query the configured GraphDB repository via SPARQL for `owl:Class` and object/datatype properties → build an `OntologySchema` (`ontology/schema.py`). A separate step mirrors those types into Neo4j as uniqueness constraints/indexes for instance storage. Changing the GraphDB `repositoryId` changes the domain with zero code edits. This replaces the toy `fibo-data.ts`.

## 6. Frontend spec

**[DONE]** No demo/mock wiring anywhere in `frontend/src/` — the prototype (`.claude/docs/src`, kept for reference/visual-parity only) never entered the build path. Current structure: `App.tsx` (layout + header), `components/{ConstructionPanel,ReasoningPanel,QueryPanel,LlmPanel,GraphCanvas,HistoryPopover}.tsx`, `stores/graphStore.ts` (Zustand), `lib/api.ts` (typed fetch client, camelCase wire contract). No SSE (plain synchronous POSTs), no EDGAR (paste-only). Full UI architecture and the prototype-parity decisions are documented in `UI_PLAN.md` §8 — this section doesn't duplicate it.

## 7. Real data sources

- **Primary (always available)**: analyst pastes real text (a real 8-K, press release, or filing excerpt).
- **Convenience**: **[DONE]** SEC EDGAR full-text/submissions API — fetch a real filing by ticker + form type (free, no key). `services/edgar_service.py` downloads, strips HTML to text, skips past the XBRL cover-page metadata block to the real narrative section (a real ~430K-character 10-K's first ~39K characters are machine-readable tags, not prose — found and fixed via live verification, not caught by unit tests), truncates to `MAX_FILING_CHARS` (8000) since a whole filing blows past any practical LLM context/latency budget, feeds the same extraction pipeline. Live-verified: a real Tesla 10-K correctly produced entities like "Full Self-Driving (FSD)", "Robotaxi", "Optimus", "Cybertruck", "Powerwall" — genuine business content, not boilerplate.
- **Ontology**: whatever OWL is loaded into the GraphDB repository (`fibo` today). Domain-agnostic — reference data lives in GraphDB, not the code.

No synthetic/seed graph is ever loaded. An empty `graph_id` shows an empty canvas with an "ingest a document" prompt.

## 8. Build & run

- **Databases run as local desktop apps** (per the chosen stack), not containers: Neo4j Desktop on `bolt://localhost:7687`, Ontotext GraphDB on `http://localhost:7200` (repo `fibo`). The backend connects to them; only the backend (and later frontend) is containerized.
- `.env` (see `.env.example`): `NVIDIA_API_KEY`, `NVIDIA_MODEL`, `LLM_BASE_URL`, `NEO4J_*_DESKTOP`, `ONTOTEXT_DB_REPO_URL_DESKTOP`.
- Backend: `cd backend && .venv/bin/uvicorn app.main:app --reload`.
- Frontend: `cd frontend && npm i && npm run dev` (Vite), proxying `/api` to `:8000`.
- `GET /health` must show Neo4j + GraphDB + LLM reachable before ingest.

## 9. Phases (small, TDD increments)

0. **[DONE] Scaffold + cleanup** — backend/frontend/`.claude/skills` tree; frontend build config; backend `pyproject.toml`/`requirements.txt`; `config.py` (desktop/cloud profiles); `/health` probing Neo4j + GraphDB + LLM; `.gitignore` protecting `.env`.
1. **[DONE] Ontology loader** — `ontology/loader.py` reads `owl:Class`/properties from GraphDB via SPARQL into `OntologySchema`, tested against the live `fibo` repo (2446 classes, 1136 properties, 456K triples); `ontology/sync.py` mirrors the domain-agnostic `:Entity`/`:RELATES` shape into Neo4j constraints/indexes (idempotent, run at startup).
2. **[DONE] Real extraction** — `/ingest` text path; `extraction/pipeline.py` builds a relevance-ranked prompt from the live ontology, calls `LLMClient`, validates entities/relations against the full `OntologySchema`; `services/ingest_service.py` MERGEs into Neo4j with provenance via deterministic slugged ids (idempotent across re-ingests). Verified live: real NVIDIA-hosted LLM extracting real FIBO-typed entities from pasted text, in the browser.
3. **[DONE] Graph read + render** — `/graph/{id}`; `GraphCanvas.tsx`/`InspectorPanel.tsx` rewired (domain-agnostic: type-hash coloring instead of the prototype's FIBO-enum coloring) to `graphStore.ts` + `api.ts`; verified rendering a real extracted graph live in Chrome.
4. **[DONE] Reasoning (§8.4)** — `reasoning/engine.py` with the fixes, `backend/tests/test_reasoning.py` green (persistent activation, directed spread, multi-hop, honest `converged_by`); `/reason` endpoint persists `:DerivedFact` + activation to Neo4j; `data/rules/fibo_rules.json` hand-authored against real FIBO vocabulary. Ontology-aware subclass matching (§12) is now implemented and verified against the exact live scenario that exposed the gap.
5. **[DONE] Query** — `services/query_engine.py` ports the triple-query language (fixed a real bug found via TDD: naive comma-split broke multi-word predicates like "is regulated by"); `/query/{id}` wired to the query panel; verified live.
6. **[DONE] LangGraph wrap** — `backend/agents/state.py` (`AgentState`), `backend/agents/graph.py` (`extractor → reasoner → responder`, each node calling the same real, already-tested service functions the REST endpoints use — `ingest_service`, `reasoning_service`, not a parallel reimplementation). `POST /agent/{graphId}` (`api/agent.py`). Checkpointing uses LangGraph's built-in `InMemorySaver`, not a custom `Neo4jSaver` — see `backend/agents/graph.py`'s module docstring for the reasoning (a real `langgraph-checkpoint-neo4j` package exists but is pre-1.0/0.0.1, installing it was declined as an unvetted external dependency; the actual cross-session-memory need is already served by `chat_history_service.py`, §20 item 4). Tests: `test_agent_graph.py`, `test_api_agent.py`, plus the extracted `test_reasoning_service.py` (a small refactor pulling `api/reason.py`'s inline logic into `services/reasoning_service.py` so both the REST endpoint and the agent's reasoner node share one tested implementation). **Live-verified against the real running server, real LLM**: real extraction (2 entities, 1 relationship), real reasoning (1 derived fact, `activation: 0.95`), a grounded natural-language reply — and a **real bug found and fixed via live verification, not caught by unit tests alone**: the first version's responder prompt only carried bare counts, and the LLM correctly refused to summarize ("I don't have any information about the text you're referring to") since it had nothing real to reference — fixed by grounding the responder in the actual extracted entity labels and derived fact text, re-verified live. EDGAR ingest source (marked "optional" in the original scope) is now also done — see §5.1/§7 above. **[UPDATED]** The agent now also has a real 5-intent router (extract/enrich/query/reason/visualize — `backend/agents/graph.py`), all 6 runtime skills wired for real (`backend/skills/`), a formal Tool Layer (`backend/agents/tools.py`), a real MCP server (`backend/mcp_server.py`), and a frontend UI (`AgentPanel.tsx`, `UI_PLAN.md` §10) — see `PLAN.md` §1.1's Implementation Status matrix for the full picture.
7. **[DONE] Polish** — loading/error states, empty-graph prompt, provenance display in `InspectorPanel` — all verified live in the browser.
8. **[DONE, beyond original scope] Manual construction + ontology-aware UI parity** — `GET /ontology`, `POST`/`PATCH /graph/{id}/nodes`, `POST /graph/{id}/edges` (Add Node/Edge, ontology-validated, same id-slug scheme as extraction so it merges cleanly); Rules Manager CRUD (`POST`/`DELETE /rules`, custom rules stored in Neo4j, participate in real `/reason` calls); `POST /chat/{graphId}` (real LLM console grounded in actual graph state, replacing the prototype's random-canned-response mock); full prototype-parity UI (Construct/Reason/Ingest left tabs, Query/LLM right tabs, resizable sidebars, domain-agnostic node coloring). See §3 and UI_PLAN.md §8.

## 10. Acceptance criteria (MVP is "workable" when all hold)

1. With Neo4j empty, opening the app shows an **empty** canvas and an ingest prompt — no demo graph.
2. Pasting a **real** document (any domain matching the loaded ontology) produces a graph in Neo4j whose nodes/edges are all attributable to that document (provenance visible in the inspector) and typed against the ontology.
3. `/reason` on that graph derives at least one **multi-hop** fact (a fact whose premise is itself a derived/boosted node) — proving the feedback loop is real, not cosmetic.
4. `/reason` reports `converged_by: "fixpoint"` on a graph that stabilizes, and `"max_iterations"` on one that doesn't — the loop is not hardwired to stop at iteration 2.
5. A structured query (`<relation>(<entity>, X)`, relation drawn from the loaded ontology) returns rows from the real stored + derived triples.
6. No code path invokes `llmRespond` or imports `fibo-data.ts`; grepping the running bundle for them returns nothing.
7. From a clean checkout with Neo4j Desktop + GraphDB Desktop running: `uvicorn` backend + `npm run dev` frontend reproduce the full flow.

## 11. Open decisions (need your call before Phase 2/4)

- **[RESOLVED] Extraction model**: `z-ai/glm-5.2` was tried first (it's listed in NVIDIA's catalog and `/v1/models` reaches it) but hangs indefinitely on real `/chat/completions` calls (confirmed via direct curl: 30s+, zero bytes back). `meta/llama-3.1-8b-instruct` on the same key/endpoint responds in ~0.3s — switched to it as the default (user decision). `z-ai/glm-5.2` can be swapped back in `NVIDIA_MODEL` once its availability is confirmed working.
- **[RESOLVED] Rules seed**: hand-authored `backend/data/rules/fibo_rules.json`, referencing real FIBO vocabulary confirmed live against the repo (`issues`, `is regulated by`, `is domiciled in`, `governs`; `organization`, `security`, `regulatory agency`, `jurisdiction`).
- **[RESOLVED] Rule language for reasoning**: single-premise pattern rules, as shipped in `reasoning/engine.py`.
- **[RESOLVED, DONE]** EDGAR/source fetch: paste-only was the MVP default; EDGAR is now also implemented (`services/edgar_service.py`, `api/ingest.py` `source.type: "edgar"`), live-verified against the real SEC API.

## 12. [FIXED] Rule matching is now ontology-aware (was exact-string)

Discovered via live end-to-end testing (real text → real LLM → real graph → real reasoning, driven in a browser), not by inspection: `run_inference` (`reasoning/engine.py`) matched `node.type` against `rule.source_type`/`target_type` with exact string equality. Live extraction correctly returns specific, real FIBO subclasses ("commercial bank", "central bank") rather than the generic types the hand-authored rules reference ("organization", "regulatory agency") — so real graphs derived zero facts even though neural activation spread correctly (verified: fixpoint convergence, correct decay).

This was good extraction behavior (accurate typing) exposing a real reasoning gap, not an extraction bug. The type relationship *does* exist — GraphDB holds `rdfs:subClassOf` triples connecting "commercial bank" to "organization" — the engine just never queried it.

**Fix (implemented)**: `OntologySchema.build_subclass_matcher()` (`ontology/schema.py`) loads all direct `rdfs:subClassOf` edges via `ontology/loader.py` (12,927 real edges in the `fibo` repo) and does a transitive, case-insensitive, reflexive closure check, built once per `/reason` call and cached in-memory for that call (not per Neo4j query — chose the fast path, since the ontology doesn't change mid-request). `reasoning/engine.py` stayed dependency-free: `run_inference`/`reason()` accept an injected `type_matches` function (default: exact equality, so all pre-existing pure unit tests are untouched), and `api/reason.py` wires in the real matcher. Verified: `commercial bank IS-A organization` and `central bank IS-A regulatory agency` confirmed against the live repo, and the exact Deutsche Bank AG / European Central Bank scenario that originally derived 0 facts now derives 1, live in the browser.
