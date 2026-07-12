# Neurosymbolic KG UI/UX Refactor Plan

This document specifies a UI overhaul for the **Neurosymbolic Knowledge Graph** app, now grounded in a real, detailed reference mockup at `.claude/docs/mocks/polanyigraph/frontend/mockup.html` (2709 lines, fully interactive HTML/Tailwind/vanilla-JS — not a rough sketch). This revision treats that mockup as the source of visual/structural truth and works out exactly how to build it against this project's real backend without losing anything.

**Hard constraint: zero functionality loss.** Every control catalogued in §1.1 must have an explicit new home in §5's mapping table. This is a reorganization and visual pass — every existing panel component (`IngestPanel`, `ConstructionPanel`, `ReasoningPanel`, `EnrichmentPanel`, `QueryPanel`, `TripleStorePanel`, `OntologyPanel`, `LlmPanel`, `AgentPanel`, `SkillManager`, `MemoryInspector`, `GraphCanvas`) keeps its internals and real API calls untouched, reused inside new composition wrappers (and, per §3, duplicated into a second, richer wrapper for the dedicated Lab pages).

**Revision history**: three earlier drafts iterated on where navigation should live (left rail replacing the sidebar → left rail beside the sidebar → left rail switching which panel sits beside a persistent canvas). All three turned out to be solving a false dilemma. **The mockup's actual answer, now adopted**: keep the existing right sidebar exactly as a quick-access companion to the canvas (§2), *and separately* add dedicated, richer, canvas-free "Lab" pages reachable from a left nav (§3) — the same underlying data and actions are deliberately available in both places, not migrated from one to the other. This resolves the "does Solver Lab need to see the canvas" question the earlier drafts kept getting stuck on: it doesn't, because the sidebar's Reason tab remains available whenever canvas-coupled quick actions are wanted, and the Solver Lab page visualizes activation via a live numeric leaderboard + console log instead, which needs no canvas at all.

---

## 1. Problem Statement

1. **Dual-Sidebar Squeeze** (today): both sidebars open at once (up to 640px each) restrict `GraphCanvas` to a narrow strip.
2. **Metadata Overload**: header crams connection pings, counts, badges into one 56px strip.
3. **Tab Fatigue**: 11 tabs (4 left, 7 right), several semantically thin (Query vs. Triples; LLM vs. Agent).
4. **Visual Hierarchy Noise**: 7 badge colors covering ~5 overlapping meanings.
5. **No room for depth**: every one of today's 11 tabs is squeezed into a fraction of one drawer's width — fine for quick actions, not enough room for the kind of dense, tabular, multi-column work the mockup's Lab pages show is actually wanted (a real triples table with filters, a 2-column rule studio, a 3-column document review hub).
6. **No home for project-level or graph-wide-but-not-canvas capabilities**: `GET /ontology` and `GET/POST/DELETE /rules` aren't graph-scoped (no `graph_id` param on either). The `evals/` skill-testing harness (11 real cases, 6 skills, built this session) has zero UI.

### 1.1 Full Functional Inventory (baseline — nothing below may be dropped)

**Header**: logo/title, ontology name, node/edge/rule/fact counts (conditional), pending-facts count (conditional, clickable), iteration count (conditional), `AUTO-RUN` badge (conditional), neo4j/graphdb status, atomic "Run to Convergence" shortcut.

**Left sidebar — 4 tabs + 2 popovers** (today): Ingest (`IngestPanel.tsx`), Construct (`ConstructionPanel.tsx`: Node Inspector, Add Node, Add Edge, Rules Manager), Reason (`ReasoningPanel.tsx`), Enrich (`EnrichmentPanel.tsx`), plus `GraphsPopover.tsx` and `HistoryPopover.tsx`.

**Right sidebar — 7 tabs** (today): Query (`QueryPanel.tsx`), Triples (`TripleStorePanel.tsx`), Ontology (`OntologyPanel.tsx`, not graph-scoped), LLM (`LlmPanel.tsx`), Agent (`AgentPanel.tsx`), Skills (`SkillManager.tsx`, not graph-scoped), Memory (`MemoryInspector.tsx`: search is graph-scoped, preferences CRUD is not).

**Canvas** (`GraphCanvas.tsx`): SVG pan/zoom/drag, select, link-mode, floating controls (zoom/heatmap/proof-path/communities), legends. Deterministic layout (`layoutNodes` in `graphStore.ts`), not physics — the mockup also uses static hardcoded node positions (confirmed: no `d3`/`force`/`simulation` anywhere in its source), so force-directed layout stays an explicitly-deferred item (`UI_PLAN.md` §7), not something this revision needs to add.

Every control above gets an explicit destination in §5.

---

## 2. The Workspace Page: Sidebar Stays, Consolidates to 5 Tabs with an Embedded Rail

This is unchanged in substance from earlier drafts and **directly matches the mockup's `#sidebar`/`switchTab()` implementation** (mockup lines 400–460, 2115–2150):

| Tab | Icon | Absorbs | Mockup panel title |
|---|---|---|---|
| **Build** | `Layers` | Ingest + Construct + Enrich, as a 3-section accordion | "Build & Curate Workspace" |
| **Reason** | `Activity` | Reason (unchanged) | "Deductive & Neural Loops" |
| **Query** | `Search` | Query + Triples + Ontology, as 3 pills ("3 browse modes") | "Inspect and Query Records" |
| **Assistant** | `Bot` | LLM + Agent, Ask/Act toggle | "Consult [LLM] Assistant" *(mockup copy says "Gemini" — cosmetic flavor text only; the real backend's active model is whatever `/health`'s `llm.model` reports, e.g. today's `meta/llama-3.1-8b-instruct` — nothing here should hardcode a vendor name)* |
| **Tools** | `Wrench` | Skills + Memory, pill-switched | "System Introspection & Memory" |

**Structural confirmation from the mockup, superseding an earlier draft's guess**: the icon rail is embedded at the sidebar's own left margin (48px column inside the sidebar's own width, `railBtn-*`/`railActive-*` in the mockup), a 2px right-edge indigo accent line marks the active tab, and the **Build tab is a 3-section accordion** (`toggleAccordion('build-ingest'|'build-construct'|'build-enrich')`) — exactly matching the "Build" consolidation proposed in earlier drafts of this document, now verified against a real implementation. The Construct accordion section holds the **full** Node Inspector (label/type/badges, activation %, salience slider, properties k-v editor, proof-path, notes), **plus** Add Manual Entity, Add Relationship/linking mode, **and** a full Deductive Inference Rules sub-section (list + create-custom-rule form) — i.e. Rules Manager stays here in full, not extracted out. This settles an open item from an earlier draft (whether node editing needs a new floating toolbar): it doesn't — the sidebar already does this well, unchanged.

Header/footer per the mockup (§4) stay a light trim of what exists today, not a redesign.

---

## 3. NEW: Left Navigation — 5 Dedicated Lab Pages

A left nav bar (72px, mockup lines 165–235) with **5 items**, each with its own accent color via a colored left-edge indicator bar (not one flat tint for the whole group): **Canvas** (indigo), **Documents** (emerald), **Logic** (violet), **Solver** (amber), **Query Lab** (sky). Selecting one calls `switchPage()`, swapping which of 5 full-viewport `<div id="page-*">` sections is shown — **Canvas is the only one of the five that shows the graph canvas + sidebar from §2; the other four are genuinely canvas-free, full-width, multi-column pages.**

Critically, per the mockup, **these are not migrations of sidebar content — they're richer duplicates that call the same real data/actions**, deliberately available from two places (quick, in-context, while working the canvas; or deep, full-width, when that's what the moment calls for):

### 3.1 Documents Lab (mockup lines 1236–1355)
Three columns, no canvas:
* **Source Registry** (left, `w-80`): a real list of every ingested document for the current graph (richer than today's last-4-only `IngestPanel` history — this should be the *full* `GET /history/{graph_id}` result, not truncated), with entity/relationship counts per document, clickable/searchable.
* **Ingestion & Extraction Lab** (center, flexible): the same paste-text-and-extract flow as `IngestPanel.tsx`, given a full-height textarea and clearer hint buttons.
* **Polanyi Review Hub** (right, `w-96`): the same pending-facts approve/reject queue as `EnrichmentPanel.tsx`, full height instead of squeezed into an accordion section.

### 3.2 Logic Lab (mockup lines 1358–1498)
Two columns, no canvas:
* **Ontology Schema Registry** (left, `w-[420px]`): `OntologyPanel.tsx`'s data (class hierarchy, object properties with domain/range), laid out with more room than the sidebar's collapsible-section version.
* **Deductive Rule Studio** (right, flexible, 2-col grid): the same Rules Manager data as `ConstructionPanel.tsx`'s rules section — **new here**: each rule additionally renders as a plain-language Horn-clause implication sentence (e.g. *"If Bond is issuedBy a Bank, and Bank hasDomicile at BusinessCenter, then Bond issuerDomicile at BusinessCenter."*) built from the rule's existing `source_type`/`edge_type`/`target_type`/`description` fields — a real, derivable presentation improvement, not new data.
* Since Ontology and Rules are genuinely global config (§1.1 item 6), Logic Lab is the more architecturally honest home for them than the per-graph sidebar tab they've always lived in — though per §3's duplication principle, they stay in the sidebar too for quick access.

### 3.3 Solver Lab (mockup lines 1501–1629)
Three columns, no canvas — **and it doesn't need one**:
* **NS-Loop Control Deck** (left, `w-[360px]`): the same 3-step status strip + Auto-Run + manual step buttons as `ReasoningPanel.tsx`.
* **Live Activation Metrics** (center, flexible): a real-time **"Top Activated Entities" leaderboard table** (entity name + activation value, sorted) plus a **console run-trace log** (`>_ ` prefixed lines narrating each step as it happens) — this is the piece that resolves the canvas-coupling question from earlier drafts. Real-time reasoning feedback doesn't require watching canvas node glow; a live table + append-only log conveys the same information and is arguably clearer for a diagnostics-focused page. Both are driven by the same real `spread_activation`/`run_inference` responses `ReasoningPanel.tsx` already consumes — no new backend needed, just a different rendering of the same `activation: Record<string, number>` and trace data.
* **Introspective Fact Trace** (right, `w-96`): the same derived-facts + proof-path data as `ReasoningPanel.tsx`'s Step 2 section, full height.

### 3.4 Query Lab (mockup lines 1632–1791)
Two columns, no canvas:
* **Datalog Pattern Console + Shortest Path Finder** (left, `w-[420px]`): same as `QueryPanel.tsx`, unchanged logic.
* **Tabular Triples Store** (right, flexible): **new presentation** — a real HTML `<table>` (Subject/Predicate/Object/Origin columns, 4-field filter row) instead of `TripleStorePanel.tsx`'s stacked cards. Same `GET /query/{graph_id}/triples` data, genuinely better for scanning many rows at once — worth adopting for both the Lab page and (optionally, smaller effort) the sidebar's Triples pill.

---

## 4. Header, Footer, Color & Typography — Verified Against the Mockup

**Header** (mockup lines 68–163, 48px not 56px): logo/title/ontology name (unchanged), graph-switcher dropdown (`GraphsPopover`, unchanged popover pattern), history dropdown (`HistoryPopover`, unchanged), pulsing `AUTO-RUN ACTIVE` badge, pending-facts badge (`✦ N Pending`, indigo not amber — a color correction from earlier drafts), and **a promoted primary action**: `mainLoopBtn` "Run Neurosymbolic Loop" — this is today's atomic Run-to-Convergence shortcut (currently buried at the bottom of the Reason tab), elevated to a header-level, always-visible primary CTA. A settings gear icon sits at the far right (mockup doesn't specify a destination for it — treat as a placeholder for wherever global settings end up, §6.1).

**Footer** (mockup lines 1791–1816, 24px): node/edge/rule/fact counts, neo4j/graphdb status dots, iteration count — all as earlier drafts proposed — **plus one addition**: `powered by {model}`, sourced from the real `/health` endpoint's already-existing `llm.model` field (the mockup's "gemini-3.5-flash" is placeholder copy; the real value is whatever `HealthResponse.llm.model` reports). Zero new backend work.

**Color**: data syntax-highlighting (`emerald`=subject, `sky`=object in Query/Triples/Ontology panels) stays as real signal. Status badges consolidate per earlier drafts' audit (5 roles: neutral/derived/approved/structural/destructive), **plus** the mockup's per-Lab left-nav accent colors are a new, additional use of color (indigo/emerald/violet/amber/sky, one per Lab) — these are navigation landmarks, not status badges, and don't need to fit the 5-role status palette; they're a separate, deliberate 5-color coding scheme for "which Lab am I in," consistent with how each Lab's node-halo color in the canvas mockup (`node-n*-halo`) already uses a distinct hue per entity type.

**Typography**: Inter (`font-sans`, weights 300–700) + JetBrains Mono (`.font-mono`, weights 400–600) — confirmed directly from the mockup's own `<head>` (Google Fonts `<link>`, lines 9–11), not a proposal anymore. Implementation should self-host via `@fontsource` packages rather than a runtime Google Fonts fetch (avoids a network dependency the mockup's static-HTML-prototype nature didn't need to worry about, but a real app should).

---

## 5. Functionality Preservation Matrix

| Feature | Old location | New location(s) | Notes |
|---|---|---|---|
| Paste text, hints, extract, history | Left › Ingest | Sidebar › Build (accordion) **and** Documents Lab | duplicated per §3's principle; Documents Lab's Source Registry shows full history, not last-4 |
| Node Inspector (full edit), Add Node, Add Edge, Rules Manager | Left › Construct | Sidebar › Build (accordion, unchanged, full-featured per mockup) | **not** extracted to a floating toolbar — mockup confirms the accordion already handles this well |
| Rules Manager (deep view) | *(new)* | Logic Lab, Deductive Rule Studio | same data as sidebar's rules list, richer 2-col layout + Horn-clause phrasing |
| Enrichment run + review | Left › Enrich | Sidebar › Build (accordion) **and** Documents Lab's Polanyi Review Hub | duplicated |
| 3-step loop, Auto-Run, trace, derived facts | Left › Reason | Sidebar › Reason **and** Solver Lab | Solver Lab additionally gets a live leaderboard + console log rendering, same underlying data |
| Ontology browser | Right › Ontology | Sidebar › Query (pill) **and** Logic Lab | duplicated |
| Query console + Find Path | Right › Query | Sidebar › Query (pill) **and** Query Lab | duplicated |
| Triples store | Right › Triples | Sidebar › Query (pill, cards) **and** Query Lab (real table) | Lab version gets the new tabular presentation |
| Read-only chat | Right › LLM | Sidebar › Assistant, mode "Ask" | unchanged, no Lab-page duplicate (not in mockup) |
| Mutating agent chat | Right › Agent | Sidebar › Assistant, mode "Act" | unchanged, no Lab-page duplicate |
| Skills | Right › Skills | Sidebar › Tools (pill) | unchanged, no Lab-page duplicate |
| Memory search + preferences | Right › Memory | Sidebar › Tools (pill) | unchanged, no Lab-page duplicate (see §6.1 for optional Settings-page extraction) |
| Switch/create graph | Left tab-strip → `GraphsPopover` | Header dropdown | unchanged component, relocated trigger only |
| Ingest history (quick) | Left tab-strip → `HistoryPopover` | Header dropdown | unchanged |
| Node/edge/rule/fact/iteration counts, neo4j/graphdb status | Header | Footer | new `StatusFooter.tsx` |
| Atomic "Run to Convergence" | Bottom of Reason tab | **Header**, primary `mainLoopBtn` | promoted per mockup, still calls the same `reason()` action |
| Pending-facts badge | Header | Header (kept, color corrected to indigo) | opens Build accordion's Enrich section |
| AUTO-RUN badge | Header | Header (kept) | unchanged |
| Canvas pan/zoom/drag/select/link-click, floating controls, legends | Canvas | Canvas — present only on the **Canvas** left-nav page | unchanged; the 4 Lab pages are canvas-free by design |

Every §1.1 control appears above, either once (unique home) or twice (deliberate sidebar+Lab duplication per §3).

---

## 6. File-by-File Implementation Plan

### Phase 0 — State model
* `App.tsx`: `activeTab: 'build'|'reason'|'query'|'assistant'|'tools'` (sidebar, was `rightTab`) + `buildSection: 'ingest'|'construct'|'enrich'` (accordion) + `activePage: 'canvas'|'documents'|'logic'|'solver'|'query-lab'` (left nav, new). Drop `leftTab` entirely (its 4 tabs are absorbed into `buildSection` and `activePage`). No `graphStore.ts` changes.

### Phase 1 — Sidebar: embedded rail + Build accordion
* `components/Sidebar.tsx`: rail (5 icons, 2px active indicator) + active tab's panel.
* `components/panels/BuildPanel.tsx`: 3-section accordion wrapping unchanged `IngestPanel`, `ConstructionPanel`, `EnrichmentPanel`.
* `components/panels/QueryExplorePanel.tsx` (3 pills: Pattern/Triples/Ontology), `AssistantPanel.tsx` (Ask/Act), `ToolsPanel.tsx` (Skills/Memory pills) — thin wrappers, unchanged inner components.
* Remove old dual-sidebar markup from `App.tsx`.

### Phase 2 — Header + footer
* Trim header to: logo/ontology, `GraphsPopover`/`HistoryPopover` triggers, pending-facts badge (color→indigo), `mainLoopBtn` (wraps existing `reason()` store action), AUTO-RUN badge.
* New `components/StatusFooter.tsx`: counts + status + `powered by {health.llm.model}`.

### Phase 3 — Left nav shell + Canvas page
* `components/NavRail.tsx` (5 items, per-item accent color).
* `App.tsx` restructured: `NavRail` + (`activePage === 'canvas'` ? Canvas+Sidebar from Phases 1–2 : one of the 4 Lab pages).
* This phase ships pure navigation — Documents/Logic/Solver/Query-Lab pages can be simple "under construction" placeholders here, filled in Phases 4–7.

### Phase 4 — Documents Lab
* `pages/DocumentsLab.tsx`: 3-column layout. Source Registry needs the **full** (not last-4) ingest history — check whether `GET /history/{graph_id}` already returns everything or needs a `limit` param removed/increased (currently `HistoryPopover`/`IngestPanel` both consume `graphStore.history`, populated by `loadHistory()`; confirm no truncation happens server-side before assuming this is frontend-only). Extraction column and Review Hub reuse `IngestPanel`/`EnrichmentPanel` logic (either by importing their internals directly, or extracting shared hooks if the accordion-sized and Lab-sized versions diverge enough to need it — decide during implementation, not before).

### Phase 5 — Logic Lab
* `pages/LogicLab.tsx`: 2-column layout reusing `OntologyPanel`/`ConstructionPanel`'s rules-section data. New: a small pure function `ruleToHornClauseSentence(rule: Rule): string` deriving the plain-language sentence from existing `Rule` fields — no new backend, no new stored data.

### Phase 6 — Solver Lab
* `pages/SolverLab.tsx`: 3-column layout reusing `ReasoningPanel`'s store actions/data. New: an activation leaderboard component (sort `activation: Record<string, number>` by value, render as a table) and a console-log component (append a line per step transition — spread/infer/feedback — using data already present in `TraceEntry`/`DerivedFact` responses, no new backend).

### Phase 7 — Query Lab
* `pages/QueryLab.tsx`: 2-column layout reusing `QueryPanel`'s data. New: `TriplesTable.tsx`, a real `<table>` rendering of `Triple[]` with 4 filter inputs — could also backport into the sidebar's Triples pill afterward as a small follow-up, not required for this phase.

### Phase 8 — Color/typography polish
* Install `@fontsource/inter` + `@fontsource/jetbrains-mono`, apply site-wide. Apply the 5-role status-badge palette from §4 (unchanged from earlier drafts' audit) and the 5-color Lab-accent scheme (already itemized in §3's intro) to `NavRail.tsx`.

---

## 6.1 Explicitly Out of Scope / Optional Extensions (not in the mockup)

The mockup doesn't cover two things earlier drafts of this plan proposed on their own initiative. Neither is contradicted by the mockup — they're just additional, not validated by it, so they're kept separate rather than silently merged in:

* **Project-level pages** (Graphs dashboard, Evals results viewer, MCP Servers catalog, Settings/preferences) — real backend capabilities (`GET /graphs`, the `evals/` harness built this session, 4 real MCP servers, `services/preferences_store.py`) that have no UI today and aren't graph-scoped. If wanted, these would extend the left nav with a second, visually-separated group below the 5 Lab items (divider, dimmer accent) — worth doing, but a separate decision from "build what the mockup shows," not bundled into Phases 0–8 above.
* **D3-force physics layout** — neither today's app nor the mockup implements this; stays a deferred item (`UI_PLAN.md` §7) unless separately prioritized, since it's real new engineering (dependency, simulation tuning, drag/pin interaction) unrelated to this navigation reorg.

---

## 7. Verification Plan

No frontend test suite exists, so verification is live browser click-through:
1. `npm run typecheck` per phase.
2. Walk §5's matrix — every item reachable, every action hits the same real backend endpoint with the same real effect, in **both** its sidebar and Lab-page location where duplicated.
3. Specifically: `mainLoopBtn` in the header triggers the same real `POST /reason/{graph_id}` the old Reason-tab button did; Documents Lab's Source Registry shows genuinely all ingested documents for the graph, not a hardcoded slice; Solver Lab's leaderboard and console log update from the same real `spread_activation`/`run_inference` responses as the sidebar's Reason tab, with no divergence between the two views of the same run; Logic Lab's Horn-clause sentences render correctly for every existing rule shape (custom and seed).
4. Before/after screenshots at 1440×900, and a side-by-side comparison against the mockup's own screenshots/rendering for each of the 5 pages.

## 8. Architectural Notes

* No backend changes needed for Phases 0–8 — every Lab page reuses existing endpoints. §6.1's optional Evals extension is the only piece that would need new (thin, read-only) endpoints, and it's explicitly deferred.
* No `graphStore.ts` changes — all new state (`activeTab`, `buildSection`, `activePage`) is local UI state in `App.tsx`/`Sidebar.tsx`/`NavRail.tsx`, same convention as today's `leftTab`/`rightTab`.
* Regression risk: Phases 0–2 touch the most shared surface (state model, sidebar, header/footer) and should get the most scrutiny; Phases 4–7 are additive, independent, and can ship in any order or in parallel once Phase 3's shell exists.
