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
