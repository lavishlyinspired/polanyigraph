# UI Improvement Plan — Neurosymbolic KG

> **Created**: July 11, 2026
> **Status**: [SUPERSEDED — see section 8] Phases 1-5 implemented; the plan's incremental approach was overtaken by a direct request to match the prototype's UI exactly. Kept for history; section 8 documents what actually shipped.
> **Scope**: Frontend + minor backend API changes

---

## 1. History & Context

### What was built (prototype → MVP)

| Phase | What happened | Files |
|-------|---------------|-------|
| **Prototype** | Local-only demo with hardcoded FIBO data, mock LLM, seed graph, shadcn/ui components, lucide icons, sonner toasts | `docs/src/` |
| **MVP** | Real backend, real LLM, real ontology from GraphDB, domain-agnostic extraction, reasoning engine | `frontend/src/` |
| **MVP gap** | Prototype's rich UI features were dropped during the rewrite to focus on backend correctness | — |

### Prototype features that were dropped

| Feature | Prototype (docs/src/) | MVP (frontend/) | Impact |
|---------|----------------------|-----------------|--------|
| Icons | `lucide-react` throughout | None | No visual hierarchy |
| Toasts | `sonner` for all actions | Inline error only | No success feedback |
| Collapsible sidebars | Left/right collapse with transitions | Fixed 300px/320px columns | Wasted space |
| Neurosymbolic loop viz | 3-step progress (Neural→Symbolic→Feedback) | Single "Reasoning..." button | No reasoning visibility |
| Heatmap toggle | Toggle button on canvas | Always-on glow | No user control |
| Proof path viz | Toggle + purple edge highlighting | Not on canvas | Can't see derivation chains |
| Query history | Last 5 queries as clickable chips | None | No query reuse |
| Example queries | 6 examples shown when empty | None | User doesn't know syntax |
| Node stats in header | Badges: nodes, edges, rules, facts, iteration | Just health status | No at-a-glance stats |
| Salience slider | Adjustable per node | Not exposed | Can't tune activation |
| Properties editor | Full property grid per node | Not shown | Can't inspect entities |
| Proof path in inspector | Detailed hop-by-hop breakdown | Not shown | Can't trace derivations |
| Grid background | Subtle dot pattern | Flat black | No spatial reference |
| Auto-run indicator | Pulsing badge with iteration | None | No loop progress |
| Edge direction markers | Multiple marker types (active, derived, proof) | Single marker | Less visual distinction |
| Depth display | Shows "depth N" on activated nodes | Not shown | Can't see hop distance |
| LLM console | Chat interface with suggested queries | Not wired (mock removed) | No natural language query |

### What the MVP does well (keep)

- Domain-agnostic type coloring (hash-based, not hardcoded FIBO enum)
- Real backend integration (ingest, graph, reason, query)
- Clean component separation
- Zustand store with proper state management
- SVG graph with drag support

---

## 2. Critical Gap: Ontology Resolution Visibility

### Problem

The neurosymbolic reasoning engine correctly resolves extracted entity types (e.g., "commercial bank") against generic rule types (e.g., "organization") via transitive `rdfs:subClassOf` traversal. However, this process is **invisible to the user** — the API strips proof path and rule metadata, and the frontend only shows fact text + confidence.

### Current State

| Layer | Has proof_path? | Has rule_name? | Visible to user? |
|-------|----------------|----------------|------------------|
| Engine (`reasoning/engine.py`) | Yes (`DerivedFact.proof_path`) | Yes | — |
| API (`api/reason.py`) | **No** (stripped in `DerivedFactResponse`) | **No** | — |
| Frontend types (`api.ts`) | **No** | **No** | — |
| UI (`InspectorPanel.tsx`) | **No** | **No** | **No** |

### What the user sees now

> Commercial Bank is under regulatory oversight by FINMA — confidence: 0.45 · iter 1

### What the user should see

> **Commercial Bank is under regulatory oversight by FINMA**
> Rule: Regulatory Oversight · Confidence: 0.45 · Iter 1
>
> **Proof path:**
> 1. [Regulatory Oversight] FINMA → regulates → Commercial Bank (activation: 85%)

### Fix: 3 files to modify

| File | Change |
|------|--------|
| `backend/api/reason.py` | Add `ProofStepResponse` model, extend `DerivedFactResponse` with `rule_name` + `proof_path` |
| `frontend/src/lib/api.ts` | Add `ProofStep` interface, extend `DerivedFact` with `ruleName` + `proofPath` |
| `frontend/src/components/InspectorPanel.tsx` | Render rule name + proof path hop-by-hop in facts tab |

---

## 3. Improvement Phases

### Phase 1: Foundation (icons, toasts, layout)

**Goal**: Visual polish and basic UX patterns.

| Task | Files | Description |
|------|-------|-------------|
| 1.1 Install lucide-react | `package.json` | Add dependency |
| 1.2 Add Toaster | `App.tsx` | Wrap with `<Toaster theme="dark" position="bottom-right" />` |
| 1.3 Wire toasts | `graphStore.ts` | Add `toast.success/error` for ingest, reason, query |
| 1.4 Add icons to buttons | `App.tsx`, `InspectorPanel.tsx` | Replace text-only buttons with icon+text |
| 1.5 Collapsible sidebars | `App.tsx` | Add `leftCollapsed`/`rightCollapsed` state, transition animation |
| 1.6 Header badges | `App.tsx` | Add node/edge/fact count badges |
| 1.7 Empty state | `App.tsx` | Rich empty state with example documents to paste |

**Dependencies**: `lucide-react`, `sonner` (already in package.json)

---

### Phase 2: Canvas Enhancement

**Goal**: Better graph visualization and interaction.

| Task | Files | Description |
|------|-------|-------------|
| 2.1 Grid background | `GraphCanvas.tsx` | Add dot pattern `<pattern id="grid">` |
| 2.2 Zoom/pan | `GraphCanvas.tsx`, `graphStore.ts` | Wheel zoom + drag on background |
| 2.3 Heatmap toggle | `App.tsx`, `GraphCanvas.tsx` | Toggle button, conditional glow rendering |
| 2.4 Proof path toggle | `App.tsx`, `GraphCanvas.tsx` | Toggle button, purple edge highlighting |
| 2.5 Edge markers | `GraphCanvas.tsx` | Separate markers for active/derived/proof |
| 2.6 Type legend | `GraphCanvas.tsx` | Overlay showing type→color mapping |
| 2.7 Depth display | `GraphCanvas.tsx` | Show "depth N" on activated nodes |

**No new dependencies** — all SVG/CSS.

---

### Phase 3: Inspector Richness

**Goal**: Make reasoning results explorable.

| Task | Files | Description |
|------|-------|-------------|
| 3.1 Salience slider | `InspectorPanel.tsx` | Range input for node salience (0.5–2.0) |
| 3.2 Extraction confidence | `InspectorPanel.tsx` | Show confidence % in node details |
| 3.3 Proof path | `InspectorPanel.tsx` | Hop-by-hop breakdown with activation/threshold |
| 3.4 Rule name | `InspectorPanel.tsx` | Show which rule derived each fact |
| 3.5 Query examples | `InspectorPanel.tsx` | 6 example queries shown when empty |
| 3.6 Query history | `InspectorPanel.tsx` | Last 5 queries as clickable chips |
| 3.7 Query result formatting | `InspectorPanel.tsx` | Color-coded subject/predicate/object |
| 3.8 Facts tab enrichment | `InspectorPanel.tsx` | Rule name + proof path per fact |

**Backend dependency**: `DerivedFactResponse` needs `proof_path` and `rule_name` fields (see Phase 5).

---

### Phase 4: Reasoning UX

**Goal**: Make the neurosymbolic loop visible and controllable.

| Task | Files | Description |
|------|-------|-------------|
| 4.1 Loop progress indicator | `InspectorPanel.tsx` | 3-step viz: Neural→Symbolic→Feedback with status icons |
| 4.2 Auto-run button | `InspectorPanel.tsx` | Start/stop auto-loop with iteration counter |
| 4.3 Auto-run badge | `App.tsx` | Pulsing "AUTO-RUN · ITER N" badge on canvas |
| 4.4 Inference trace | `InspectorPanel.tsx` | Show fired/skipped rules with activation comparison |
| 4.5 Activation ranked list | `InspectorPanel.tsx` | Show top activated nodes with bar chart |

**No backend changes** — frontend state management only.

---

### Phase 5: Backend Support (prerequisites for Phase 3)

**Goal**: Expose proof path and rule metadata in API responses.

| Task | Files | Description |
|------|-------|-------------|
| 5.1 Add ProofStepResponse | `backend/api/reason.py` | New Pydantic model for proof steps |
| 5.2 Extend DerivedFactResponse | `backend/api/reason.py` | Add `rule_name`, `proof_path` fields |
| 5.3 Update response construction | `backend/api/reason.py` | Map engine's DerivedFact to extended response |
| 5.4 Extend frontend types | `frontend/src/lib/api.ts` | Add `ProofStep` interface, extend `DerivedFact` |

**Engine already computes**: `proof_path` and `rule_name` on every `DerivedFact` — just need to expose them.

---

### Phase 6: Empty & Loading States

**Goal**: Better feedback during async operations.

| Task | Files | Description |
|------|-------|-------------|
| 6.1 Rich empty state | `App.tsx` | Example documents, feature highlights |
| 6.2 Loading skeleton | `GraphCanvas.tsx` | Shimmer effect during graph load |
| 6.3 Ingest progress | `App.tsx` | Progress bar or step indicator during extraction |
| 6.4 Error recovery | `App.tsx` | Retry button on errors |

---

## 4. Implementation Order

```
Phase 1 (Foundation)  ← start here, quick wins
    ↓
Phase 2 (Canvas)      ← depends on Phase 1 for icons/toasts
    ↓
Phase 5 (Backend)     ← unblocks Phase 3
    ↓
Phase 3 (Inspector)   ← needs Phase 5 for proof path data
    ↓
Phase 4 (Reasoning)   ← builds on Phase 3's enriched inspector
    ↓
Phase 6 (Polish)      ← final touches
```

---

## 5. File Change Summary

| File | Changes |
|------|---------|
| `frontend/package.json` | Add `lucide-react` |
| `frontend/src/App.tsx` | Icons, toasts, collapsible sidebars, header badges, empty state, auto-run badge |
| `frontend/src/components/GraphCanvas.tsx` | Grid, zoom/pan, heatmap toggle, proof path toggle, edge markers, type legend, depth display |
| `frontend/src/components/InspectorPanel.tsx` | Salience slider, proof path, rule name, query examples, query history, loop progress, auto-run, inference trace |
| `frontend/src/stores/graphStore.ts` | Toast integration, zoom/pan state, heatmap/proof toggles |
| `frontend/src/lib/api.ts` | `ProofStep` interface, extended `DerivedFact` |
| `backend/api/reason.py` | `ProofStepResponse`, extended `DerivedFactResponse` |

---

## 6. Testing Checklist

After each phase:

- [ ] `cd frontend && npm run typecheck` — no TypeScript errors
- [ ] `cd frontend && npm run build` — successful build
- [ ] Manual: Open app, verify no console errors
- [ ] Manual: Ingest a document, verify toast appears
- [ ] Manual: Run reasoning, verify loop progress visible
- [ ] Manual: Query the graph, verify results formatted correctly
- [ ] Manual: Check responsive behavior at different window sizes

---

## 7. Open Questions

1. **[RESOLVED] shadcn/ui components?** Not adopted. Raw Tailwind reproduces the prototype's exact classes (`text-[11px] font-bold uppercase tracking-wider`, `rounded-lg border`, etc.) without the dependency/setup overhead, and the visual result is pixel-equivalent for this design.

2. **[RESOLVED] Wire the LLM console?** Wired to a real endpoint: `POST /chat/{graphId}` (`backend/api/chat.py`, `services/chat_service.py`). The system prompt is built from the real graph's entities, relationships, and stored derived facts (`chat_service._build_system_prompt`) — verified live: asked "What entities are in this graph?" and the response listed exactly the 5 real entities present, not invented ones.

3. **[OPEN] d3-force layout?** Still deterministic circular layout (`graphStore.ts layoutNodes`). Not revisited in this pass.

4. **[OPEN] Mobile support?** Still fixed-column. Not revisited in this pass.

## 8. What actually shipped (final architecture)

Superseding the phased plan above: the user asked for the UI to match `.claude/docs/src` (the prototype) exactly — same layout, tabs, typography, spacing — while staying real-data-only and domain-agnostic. Implemented as:

**Left sidebar — Construct / Reason tabs** (`ConstructionPanel.tsx`, `ReasoningPanel.tsx`), replacing the single "Ingest" panel:
- **Construct**: Node Inspector (selected node + provenance) → Graphs (switcher: list existing graphs with counts, create/switch via a text input — backed by `GET /graphs`) → Ingest Document (paste text, unchanged) → Rules (read-only list from `GET /rules`, since rules are hand-authored against the real ontology; freehand rule authoring from the UI was cut — a made-up relation could reference something that doesn't exist in the ontology and would silently never fire).
- **Reason**: ported the prototype's info banner, 3-step Neural→Symbolic→Feedback loop visual, Auto-Run/Stop, heatmap/proof-path toggles, activated-nodes ranking, and derived-facts list with proof paths. **One deliberate deviation**: the prototype had three separately-clickable manual steps (Spread Activation / Run Inference / Feed Back); the real backend's `/reason` (PLAN.md §8.4) runs the whole persistent-activation loop to convergence as one atomic, already-verified call, so these collapse into a single "Run reasoning" action while the 3-step visual still reflects real progress.

**Right sidebar — Query / LLM tabs** (`QueryPanel.tsx`, `LlmPanel.tsx`): Query is the existing triple-query console, effectively unchanged. LLM is new — see item 2 above.

**Ontology resolution visibility** (the specific ask: "ensure ontology resolution is visible in the UI"): `ProofStep` (`reasoning/engine.py`) gained a `type_resolution` field, populated when a rule fired via subclass match rather than an exact type match (e.g. `"commercial bank" is-a "organization"`). Rendered per proof-path hop in `ReasoningPanel.tsx`. Verified end-to-end with the real Deutsche Bank AG / European Central Bank scenario from PLAN.md §12.

**Graph persistence across restarts**: `graphStore.ts` persists the active `graphId` to `localStorage` (`neurosymbolic:activeGraphId`), restored on load. The graph data itself was already persistent (Neo4j) — this persists *which graph the UI shows* after a reload. Verified: restarted both servers via `dev.sh restart`, reloaded the page, same graph reappeared.

**History**: unchanged from the prior turn — left-sidebar icon + popover (`HistoryPopover.tsx`), not a tab (per explicit direction).


UI Improvements Needed — Gap Analysis
What's in the plans but NOT in the actual frontend code:
A. From PLAN.md §6 Frontend Architecture (v2 plan)
Planned Component
SkillManager.tsx — skill browsing/activation
MemoryInspector.tsx — memory visualization
agentStore.ts — agent state management
websocket.ts — SSE/WS connection
hooks/useGraph.ts
hooks/useAgent.ts
Streaming LLM responses
B. From UI_PLAN.md (phases 1-6)
Phase	Feature
Phase 1	Icons (lucide-react)
Phase 1	Toasts (sonner)
Phase 1	Collapsible sidebars
Phase 1	Header badges
Phase 1	Empty state
Phase 2	Grid background
Phase 2	Zoom/pan
Phase 2	Heatmap toggle
Phase 2	Proof path toggle
Phase 2	Edge markers (active/derived/proof)
Phase 2	Type legend
Phase 2	Depth display on nodes
Phase 3	Salience slider
Phase 3	Extraction confidence
Phase 3	Proof path in inspector
Phase 3	Rule name per fact
Phase 3	Query examples
Phase 3	Query history chips
Phase 3	Query result formatting
Phase 4	Loop progress (3-step viz)
Phase 4	Auto-run button
Phase 4	Auto-run badge on canvas
Phase 4	Inference trace (per-rule fired/skipped)
Phase 4	Activation ranked list
Phase 5	ProofStepResponse (backend)
Phase 5	Extended DerivedFactResponse
Phase 6	Loading skeleton
Phase 6	Ingest progress indicator
Phase 6	Error retry button
C. From prototype features not ported to production
Prototype Feature
Inference trace — per-rule fired/skipped with activation vs threshold, amber/zinc highlighting, CheckCircle2/AlertCircle icons
Three manual reasoning steps — separate Spread Activation / Run Inference / Feed Back buttons
Path highlighting on canvas — cyan edges + pulsing cyan node rings
Derived-edge visual distinction — thick amber stroke for derived edges
Depth label on nodes — "depth N" text below activated nodes
Derived-by-rule name inline in node inspector
Edge symmetric/transitive toggles
CPU load indicator
Auto-scroll in LLM panel
D. Additional improvements not in any plan
Improvement
d3-force layout
Mobile support
Responsive breakpoints
Keyboard shortcuts
Accessibility (a11y)
Internationalization (i18n)
Dark/light theme toggle
Export graph as image
Undo/redo
Batch operations
Drag-resizable sidebars
Multi-graph management
Priority Summary
Priority	Items
High (core UX gaps)	Inference trace, path highlighting on canvas, depth display
Medium (v2 plan components)	SkillManager, MemoryInspector, agentStore, websocket/SSE, streaming LLM
Low (polish)	Auto-scroll, derived-edge distinction, edge toggles, CPU load
Deferred (UI_PLAN.md §7)	d3-force layout, mobile support
The most impactful missing feature is the inference trace — the prototype showed which rules fired and which were skipped at each iteration, which is critical for understanding the neurosymbolic reasoning process. The production UI only shows the final derived facts, losing the step-by-step reasoning visibility.
▣  Plan · Big Pickle · 6m 13s
what is a better way to place the triples and ontology instead of placing them in the sidebars.also provide . Neural Activation and 2. Symbolic Inference -> nference trace:
1 and nference trace:  Derived facts (12): and 3. Feedback to Neural. see how '/Users/akash/KG_Projects/neurosymbolic/.claude/docs/src' it provides for the reason tab. the write to '/Users/akash/KG_Projects/neurosymbolic/.claude/docs/UI_PLAN.md'

---

## 9. Sync with PLAN.md §19 (Polanyi Enrichment) and §20 (Temporal Memory)

**[NEW]** Neither the gap analysis above (A–D) nor any earlier phase in this document plans UI for `PLAN.md` §19 or §20 — both were speced after this document's phases were written. Backend implementation of §20 items 1–2 (provenance linking + bi-temporal facts) is starting now (`services/graph_service.py`, `services/history_service.py`); this section is the corresponding UI plan so the two docs don't drift apart again. None of this is built yet.

### 9.1 Provenance (§20 item 1: `IngestEvent-[:PRODUCED]->Entity`)

| Task | Files | Description |
|---|---|---|
| 9.1.1 Node provenance list | `InspectorPanel.tsx` (or `ConstructionPanel.tsx`'s node inspector) | **Backend done, UI not started.** Replace the current single `sourceDoc` string with the real list of ingest events that produced/touched this entity (an entity mentioned across 3 documents should show 3, not overwrite to the last one) |
| 9.1.2 Provenance API | `backend/api/graph.py` | **[DONE]** `GET /graph/{graphId}/nodes/{nodeId}/provenance` → `{events: [{id, text, createdAt}]}`, backing 9.1.1 |
| 9.1.3 Jump to source | `InspectorPanel.tsx` | Clicking a provenance entry opens/scrolls the existing `HistoryPopover.tsx` to that event's full text |
| 9.1.4 Entity summary display | `InspectorPanel.tsx` | **Backend done (`node.summary`, §20 item 3), UI not started.** Show the accumulated, LLM-synthesized summary in the node inspector — richer than a single provenance snippet, since it synthesizes across every ingest that touched the entity |

### 9.2 Bi-temporal facts (§20 item 2: `validAt`/`invalidAt` on `:RELATES`)

| Task | Files | Description |
|---|---|---|
| 9.2.1 "Superseded" badge | `GraphCanvas.tsx`, `QueryPanel.tsx` | **Backend done, UI not started.** An edge with `invalidAt` set is historical, not current — needs visual distinction (dim/dashed) wherever edges render, so invalidated facts aren't confused with live ones |
| 9.2.2 Fact history view | `QueryPanel.tsx` or a new tab | **Backend + API done (see 9.2.3), UI not started.** Toggle "show historical facts" — when a query/predicate has more than one value over time (e.g. `hasDomicile("Acme", X)` returning both Zurich (invalidated) and Geneva (current)), show both with their validity window instead of only the current one |
| 9.2.3 History API | `backend/api/graph.py` | **[DONE]** `EdgeResponse` carries `validAt`/`invalidAt`/`producedByEventId`; `get_graph`/`load_triples` stay current-state-only by default. New `GET /graph/{graphId}/relationships/history?sourceId=&type=` returns full history (current + invalidated) — backs 9.2.2. Verified live: two real ingests asserting Zurich then Geneva for the same (Acme, "is domiciled in") correctly show Zurich invalidated, Geneva current. |

### 9.3 Polanyi enrichment (§19: 11 heuristics, `:ImplicitFact`, human-in-the-loop)

**[DONE]** Backend and frontend both complete. `enrichment/heuristics/` has all 11 modules + a registry (`ALL_HEURISTIC_MODULES`) so a single `/enrich` call produces facts across every category. `EnrichmentPanel.tsx` (new, wired as a 4th left-sidebar tab "Enrich" alongside Ingest/Construct/Reason) implements 9.3.1/9.3.2/9.3.5. **Live-verified in the browser** against the real running app + real graph: pasted text, ran enrichment (real LLM, ~13s for 11 heuristic calls), got 33 real pending facts across 10 heuristic types with distinct color-coded badges, confidence-sorted (95% down to 60%); approved one (moved to a collapsible Approved section, header "N pending" badge decremented); rejected another (removed from pending entirely, count decremented). Header gained a clickable "N pending" badge (violet, Sparkles icon) that jumps to the Enrich tab.

| Task | Files | Description |
|---|---|---|
| 9.3.1 Enrichment tab or section | `EnrichmentPanel.tsx`, wired into `App.tsx` as left-sidebar tab 4 (Ingest/Construct/Reason/**Enrich**) | **[DONE]** Lists pending `:ImplicitFact` assertions, each with a heuristic-type badge (same hash-hue coloring approach as `GraphCanvas.tsx`'s node types) |
| 9.3.2 Approve/reject UI | `EnrichmentPanel.tsx` | **[DONE]** Approve/Reject buttons per card, wired to `graphStore.ts`'s `approveFact`/`rejectFact`. Confirmed live: `symbolic_coercion`'s speculative low-confidence facts (the known limitation from §19.6) are exactly what a reviewer sees and can reject here |
| 9.3.3 Enrichment API | `backend/api/enrich.py` | **[DONE]** `POST /enrich/{graphId}`, `GET /enrich/{graphId}/pending`, `GET /enrich/{graphId}/approved`, `POST /enrich/{graphId}/{factId}/approve\|reject` |
| 9.3.4 Canvas indicator | `GraphCanvas.tsx` | **[DONE]** Nodes anchored by a pending or approved `:ImplicitFact` get a small fuchsia dot badge (distinct from amber `derived` ring and violet proof-path dashing), plus a bottom-left "N nodes with implicit facts" legend. Live-verified: ran enrichment, 4 nodes correctly marked. |
| 9.3.5 Confidence-sorted review queue | `EnrichmentPanel.tsx` | **[DONE]** Pending list sorts by confidence descending client-side; live-verified the weakest facts (e.g. a 60% `symbolic_coercion`) surface for easy rejection instead of being buried in generation order |

**Remaining**: none — §19.6 step 5 / UI_PLAN.md §9.3 fully complete, backend and frontend.

### 9.4 Chat session memory (§20 item 4: `:ChatSession`/`:ChatMessage`) — **[NEW] backend done, UI not started**

`POST /chat/{graphId}` now accepts an optional `sessionId` and defaults to one continuous session per graph server-side if the client sends none — so `LlmPanel.tsx` needs **no changes to keep working**, but currently gets no UI control over sessions (can't start a fresh conversation without a fresh graph). Verified live: two calls with no `sessionId`, second one correctly recalled the first's content.

| Task | Files | Description |
|---|---|---|
| 9.4.1 "New conversation" button | `LlmPanel.tsx` | Generates a new `sessionId` (e.g. `${graphId}:${uuid}`), stored in Zustand/localStorage similar to `activeGraphId` (`UI_PLAN.md` §8's "Graph persistence" pattern), sent on every `/chat` call from then on |
| 9.4.2 Session-aware chat client | `lib/api.ts` | `chat(graphId, message, sessionId?)` passes `sessionId` through; omit for the existing default-session behavior |

### 9.5 Community detection (§20 item 5: Neo4j GDS Louvain) — **[DONE]**

`services/community_service.py` + `POST`/`GET /graph/{graphId}/communities` are real and live-verified. Frontend complete: `GraphCanvas.tsx` toolbar gained a "Detect Communities" button (`Boxes` icon, spinner while running) and a "color by community" toggle (only shown once at least one node has a `communityId`), which swaps the top-left legend from Types to Communities (color swatch + member count per community) and recolors node fill/stroke by `communityId` hash instead of type hash, reusing the same hash-hue function.

| Task | Files | Description |
|---|---|---|
| 9.5.1 "Detect Communities" action | `GraphCanvas.tsx` toolbar | **[DONE]** Button calling `POST /graph/{graphId}/communities` via `graphStore.ts`'s `detectCommunities()`, reloads the graph afterward so `communityId` populates, turns on community-coloring automatically. Live-verified: toast "Found 2 communities across 7 entities" on the real `default` graph. |
| 9.5.2 Community coloring/grouping on canvas | `GraphCanvas.tsx` | **[DONE]** Toggleable "color by community" mode (node fill/stroke keyed on `communityId` instead of `type`) plus a Communities legend. Not built: a background halo/region grouping (considered, deprehensioned as unnecessary complexity — color-by-community was sufficient and matches the existing type-legend visual language). |
| 9.5.3 Community API client | `lib/api.ts` | **[DONE]** `detectCommunities(graphId)`, `getCommunities(graphId)`, `CommunityMember`/`CommunitiesResponse` types, `ApiNode.communityId` field |

**Remaining**: none for the MVP slice of this feature.

---

## 10. Agent tab (MVP_PLAN.md Phase 6, PLAN.md §8 Agent Layer) — **[DONE]**

New right-sidebar tab "Agent" (`AgentPanel.tsx`, 5th tab alongside Query/Triples/Ontology/LLM), distinct from the existing "LLM" tab: LLM (`LlmPanel.tsx`) hits `POST /chat`, read-only Q&A grounded in graph state; Agent hits `POST /agent`, a real LangGraph agent (`backend/agents/graph.py`) that classifies intent and can mutate the graph for real — extract new entities, run reasoning, run Polanyi enrichment, answer a structured query, or describe a visualization.

| Task | Files | Description |
|---|---|---|
| Chat-style UI | `AgentPanel.tsx` | Same message-bubble visual language as `LlmPanel.tsx`, plus a color-coded intent badge per assistant reply (emerald=extract, violet=enrich, sky=query, amber=reason, fuchsia=visualize) so the user sees what the router decided, not just the reply |
| Agent API client | `lib/api.ts` | `AgentResponse` type (reply, intent, entitiesExtracted, relationshipsExtracted, factsDerived, enrichmentFactTexts, queryResults, queryError), `runAgent(graphId, text, sessionId?)` |
| Store wiring | `graphStore.ts` | `agentMessages`, `agentLoading`, `sendAgentMessage()` — since extract/enrich/reason intents mutate real Neo4j state, a successful call also reloads the graph, pending facts, history, and graphs list (unlike `sendChatMessage`, which is read-only and doesn't refresh anything) |

**Live-verified in the browser** against the real running app + real graph (25 entities, 14 edges, from a real HDFC/SEC/Credit Suisse ingest): "Show me an overview of the graph." correctly routed to `visualize`, replied grounded in the real entity types and names present ("thing in role", "Credit Suisse", "UBS Group"). `is regulated by("Credit Suisse", X)` correctly routed to `query`, replied "Credit Suisse is regulated by 'FINMA'" — matching the real stored fact. Neither call mutated node/edge counts, confirming read-only intents stay read-only.