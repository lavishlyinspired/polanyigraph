# Neurosymbolic KG UI/UX Refactor Plan

This document outlines a comprehensive analysis of the current **Neurosymbolic Knowledge Graph** interface and proposes a complete design overhaul inspired by the professional, minimal, and highly focused aesthetics of **Google AI Studio**.

**Hard constraint for every phase below: zero functionality loss.** Every button, form, badge, and data view catalogued in §1.1 must have an explicit new home in §4's mapping table before any code is written. This is a *reorganization and visual pass*, not a rewrite of business logic — nearly every existing panel component (`IngestPanel`, `ConstructionPanel`, `ReasoningPanel`, `EnrichmentPanel`, `QueryPanel`, `TripleStorePanel`, `OntologyPanel`, `LlmPanel`, `AgentPanel`, `SkillManager`, `MemoryInspector`, `GraphCanvas`) keeps its internals untouched and is simply re-mounted inside new, thinner composition wrappers.

---

## 1. Problem Statement: Why the Current UI Feels Cluttered

The current layout packs an enormous amount of functionality into a single viewport. While powerful, it suffers from several core design anti-patterns:

1. **Dual-Sidebar Squeeze**: Having both left and right sidebars active simultaneously (up to 640px each, 400px by default) restricts the central `GraphCanvas` to a narrow, vertical strip on anything under a 27" monitor. A graph visualization requires horizontal breathing room to prevent nodes from overlapping and lines from bunching.
2. **Metadata Overload ("Technical Larping")**: The header is crowded with raw telemetry: connection pings (`neo4j up`, `graphdb up`), node/edge counts, rule counts, fact counts, pending statuses, and iteration badges — all visible simultaneously, all fighting for the same 56px-tall strip. It resembles a server terminal rather than a polished product.
3. **Tab Fatigue**: Splitting workflows across **11 different tabs** (Left: *Ingest, Construct, Reason, Enrich*; Right: *Query, Triples, Ontology, LLM, Agent, Skills, Memory*) confuses the user. Several tab boundaries are semantically thin — "Query" vs. "Triples" are both "look at facts in the graph," and "LLM" vs. "Agent" are both "chat about the graph," differing only in whether the reply can mutate state. Each tab strip is 36px tall serving up to 7 tabs, so every label is compressed to 9px uppercase text — already at the limit of legibility.
4. **Visual Hierarchy Noise**: High-contrast, multi-colored badges (violet, amber, rose, emerald, sky, fuchsia, white) fight for attention across at least 5 different semantic meanings (derived fact, proof-path, implicit-fact anchor, community, custom-rule tag). This visual competition creates high cognitive load and obscures the actual graph data.
5. **Node Inspector Steals Persistent Real Estate**: The Construct tab's Node Inspector, Add Node form, Add Edge form, and Rules Manager are all permanently mounted in the sidebar regardless of whether a node is selected, competing for scroll space with three other unrelated sub-features in the same tab.

### 1.1 Full Functional Inventory (baseline — nothing below may be dropped)

**Header** (`App.tsx` lines ~130–187): logo/title, ontology repo name (from `/health`), node count, edge count, rule count, fact count (conditional), pending-implicit-facts count (conditional, clickable → jumps to Enrich), iteration count (conditional), `AUTO-RUN` pulsing badge (conditional), neo4j up/down, graphdb up/down.

**Left sidebar — 4 tabs + 2 popover triggers:**
| Tab | Component | Contains |
|---|---|---|
| Ingest | `IngestPanel.tsx` | doc-type hint chips, textarea w/ char+word count, Extract→Graph button, error banner w/ retry, last-4 recent-ingest cards |
| Construct | `ConstructionPanel.tsx` | Node Inspector (label/type/derived badge/activation %/source-doc/salience slider/properties k-v editor/proof-path steps/note textarea), Add Node (label input + ontology-backed type select + button), Add Edge (ontology-backed relation select + start/cancel linking), Rules Manager (list + create-custom-rule form: name/source type/target type/edge type/threshold slider/description, delete for custom rules only) |
| Reason | `ReasoningPanel.tsx` | intro blurb, 3-step status strip (neural/symbolic/feedback, live checkmarks), Auto-Run Loop button, heatmap toggle, proof-path toggle, Step 1 Spread Activation (button, clear, top-8 activated-node bars), Step 2 Run Inference (button, clear, fired/skipped inference trace list, derived-facts list w/ full proof path + ontology-resolution notes), Step 3 Feed Back (button w/ pending count), atomic "Run to Convergence" shortcut w/ convergedBy badge |
| Enrich | `EnrichmentPanel.tsx` | intro blurb, textarea + Run Enrichment button, confidence-sorted Pending Review cards (approve/reject), collapsible Approved list |
| *(popover)* | `GraphsPopover.tsx` | switch graph, create new graph |
| *(popover)* | `HistoryPopover.tsx` | full ingest-event history, expandable full text |

**Right sidebar — 7 tabs:**
| Tab | Component | Contains |
|---|---|---|
| Query | `QueryPanel.tsx` | Datalog-style query console (input, run, last-5 history chips, 6 example-query buttons), Find Path (source/target inputs, BFS path result w/ chain + proof string), query results list (derived/base badges, confidence) |
| Triples | `TripleStorePanel.tsx` | full triple store, search/filter, derived/base badges, confidence |
| Ontology | `OntologyPanel.tsx` | collapsible Subclass Relations / Classes / Properties sections |
| LLM | `LlmPanel.tsx` | read-only Q&A chat grounded in graph state (`POST /chat`), suggestion chips |
| Agent | `AgentPanel.tsx` | LangGraph agent chat that can mutate the graph (`POST /agent`, 6 intents: extract/enrich/query/reason/recall/visualize), intent badges, suggestion chips |
| Skills | `SkillManager.tsx` | 6 runtime skills, active/inactive badges, expand-to-view SKILL.md body, activate button |
| Memory | `MemoryInspector.tsx` | cross-source memory search (chat history + entity summaries), key/value preferences CRUD |

**Canvas** (`GraphCanvas.tsx`, already reasonably decluttered): SVG pan/zoom/drag, node select, link-mode click-to-connect w/ banner, floating top-right control stack (zoom in/out/reset, heatmap toggle, proof-path toggle, detect-communities, toggle community-coloring), bottom-right zoom% indicator, top-left type/community legend, bottom-left implicit-fact-count legend.

Every one of the ~45 individual controls/views above gets an explicit destination in §4.

---

## 2. Design Inspiration: Google AI Studio UI Principles

Google AI Studio is built around **creative focus**, **architectural clarity**, and **intentional negative space**. We adapt its design language through four principles:

* **Canvas-First Layout**: The primary workspace (the Knowledge Graph Canvas) dominates the screen. One sidebar, not two.
* **Contextual Sidebars**: Control panels are secondary and single-sided (right), collapsible, with grouped rather than flat-listed tabs.
* **Subtle & Uniform Palette**: A monochrome foundation (deep grays, soft whites, thin borders) with a disciplined, small set of semantic accent colors instead of a rainbow of one-off badge colors.
* **Low-Density Margins**: Stats and connection status move into a thin, low-contrast footer instead of competing for header sightlines.

---

## 3. The New Information Architecture

### 3.1 Tab Consolidation: 11 tabs → 6 tabs, 2 sidebars → 1

The guiding rule: **group by user intent, not by backend endpoint.** A user thinks "I want to build the graph," "I want to reason over it," "I want to ask about it," or "I want to look something up" — not "which of 11 tabs holds the button I need."

| New tab | Icon | Replaces | Why grouped |
|---|---|---|---|
| **Build** | `Layers` | Ingest + Construct + Enrich (3 left tabs) | All three are "add or curate graph content" — ingest text, add nodes/edges/rules by hand, review AI-proposed implicit facts. Sequential in a typical session (ingest → inspect/construct → enrich), so an accordion (not sub-tabs) fits: one section expanded at a time, others collapsed but always one click away. |
| **Reason** | `Activity` | Reason (unchanged) | Kept as its own dedicated top-level tab — it's the single most complex, most frequently-iterated workflow (3 manual steps + trace + auto-run) and doesn't share enough surface with anything else to justify merging. Diluting it into an accordion would bury its own internal step-by-step structure under a second layer of disclosure. |
| **Query** | `Search` | Query + Triples + Ontology (3 right tabs) | All three are "inspect what's already true in the graph," differing only in query style (pattern query / raw triple list / schema browse). A light segmented control (pill switcher, not full tabs) inside one panel keeps them one click apart without three more top-level tabs. |
| **Assistant** | `Bot` | LLM + Agent (2 right tabs) | Both are chat interfaces over the same graph; the only difference is whether the reply can mutate state. Collapse into one chat surface with an **Ask / Act** mode toggle at the top — Ask hits `POST /chat` (current LLM tab behavior, read-only), Act hits `POST /agent` (current Agent tab behavior, can extract/enrich/query/reason/recall/visualize). One input box, one message thread, half the chrome. |
| **Tools** | `Wrench` | Skills + Memory (2 right tabs) | Both are meta/introspection surfaces (what capabilities exist, what does the system remember) used far less frequently than Build/Reason/Query/Assistant during normal work. A sub-tab pill switcher (Skills / Memory) inside one panel, matching the Query tab's internal pattern for consistency. |

Net: **6 top-level tabs, one sidebar, one resize handle, one collapse button** — down from 4+7 tabs across two independently-resizable sidebars.

### 3.2 New Layout Grid

```
+---------------------------------------------------------------------------------+
|  ⬡ Neurosymbolic KG   ontology: fibo    [⌂ default ▾]  [🕐]     ✦2 pending  ⚙   |  <- 48px header
+---------------------------------------------------------------------------------+
|                                                              |                  |
|                                                              |  Build           |
|                                                              |  Reason          |
|                                                              |  Query           |
|                    Main Graph Canvas                         |  Assistant       |
|                    (dominates viewport)                      |  Tools           |
|                                                              |                  |
|              [floating node inspector card,                  |  (active tab     |
|               appears only when a node is selected]          |   content here)  |
|                                                              |                  |
+---------------------------------------------------------------------------------+
|  12 nodes · 14 edges · 4 rules · 3 facts   ·   ● neo4j   ● graphdb   iter 2      |  <- 22px footer
+---------------------------------------------------------------------------------+
```

* Sidebar default width unchanged (400px, 300–640px resizable, collapsible) — but now there is only **one**, so the canvas gains up to ~400–480px of width back whenever the left panel would previously also have been open (which was the common case, since Ingest/Construct/Reason/Enrich were all left-tab defaults).
* Vertical tab labels move from a single 36px horizontal strip (cramped 9px text across up to 7 tabs) to a **left-edge vertical icon rail** (like AI Studio / Linear / VS Code activity bars) — 5–6 icons stack vertically with room for a 10–11px label, no compression needed regardless of tab count growing later.

### 3.3 Header Decluttering

Keep only: logo, ontology name, graph switcher (was `GraphsPopover`, triggered from the left sidebar's `FolderOpen` icon — now lives in the header), ingest-history trigger (was `HistoryPopover`, same relocation), the pending-implicit-facts badge (high-value, keep — clicking it opens Build → Enrich section directly), and the Auto-Run pulsing indicator (an active, time-sensitive state the user must not lose visibility of, even mid-workflow on any tab).

**Moved out of the header, into the footer**: node count, edge count, rule count, fact count, iteration count, neo4j status, graphdb status. These are useful for a developer to glance at but are not decision-relevant on every screen — footer text is `font-mono text-[10px] text-zinc-500`, same as the existing `IngestPanel` recent-ingest metadata style, so no new typographic pattern is introduced.

### 3.4 Footer Status Bar (new)

A single new 22–24px strip, `bg-zinc-900/50 border-t border-zinc-800`, containing exactly what the header used to show mid-strip: `{nodes} nodes · {edges} edges · {rules} rules · {facts} facts` (facts clause conditional on `facts.length > 0`, matching current behavior) followed by `● neo4j` / `● graphdb` status dots (green/red) and, conditionally, `iter {n}`.

### 3.5 Contextual Node Inspector (floating, canvas-anchored)

Today, selecting a node dumps a large always-mounted form into the Construct tab regardless of whether the user is looking at the canvas or another tab. New behavior:

* A **compact, read-only summary card** floats over the canvas (top-right, below the existing zoom/heatmap control stack, or bottom-left, anchored the same way `GraphsPopover`/`HistoryPopover` already anchor to a trigger) whenever `selectedNodeId` is non-null: label, type, derived/activation badges, source-doc snippet, proof-path hop count. This is new but trivial — it's a strict subset of what `ConstructionPanel`'s Node Inspector already renders, just extracted into `NodeInspectorCard.tsx` and fed the same `selected` node the Construct section already computes (`nodes.find(n => n.id === selectedNodeId)`).
* A single **"Edit in Build →"** link/button on that card sets `activeTab = 'build'` and auto-expands the Construct accordion section. The full editable form — salience slider, properties k-v editor, proof-path detail, note textarea — **stays exactly where it is today**, inside the (now accordion-nested) `ConstructionPanel.tsx`, completely unchanged. Nothing about node editing is removed or reimplemented; it's given a discoverable shortcut from the canvas instead of only being reachable by manually switching tabs.
* Add Node / Add Edge / Rules Manager stay inside Build → Construct as well, unchanged internally — the "float everything on the canvas" idea from the original draft of this plan (a Figma-style floating toolbar) is deliberately **deferred to §3.7 as an optional Phase 5 polish item**, not required for the decluttering goal, since it would require new drag/positioning engineering for comparatively small benefit once the sidebar itself is already down to one column.

### 3.6 Color & Typography System

Auditing actual usage (`grep -rn "sky-\|fuchsia-\|violet-\|amber-\|emerald-\|rose-" frontend/src/components`) shows two genuinely different things are currently sharing the same "colored text" technique, and only one of them is the clutter problem:

1. **Data syntax-highlighting** — `QueryPanel`, `TripleStorePanel`, `OntologyPanel` consistently use `emerald` for subject/child and `sky` for object/target/parent across triple and query-result rendering (e.g. `QueryPanel.tsx:177-179`, `TripleStorePanel.tsx:82-84`, `OntologyPanel.tsx:64-66`). This is a coherent, low-noise convention — closer to syntax highlighting than to badge soup — and **should be kept as-is**, not touched by this refactor.
2. **Status/state badges** — this is the actual source of visual noise: `amber` (derived), `violet` (proof-path), `sky` (custom-rule tag in `ConstructionPanel.tsx:396`, community-toggle in `GraphCanvas.tsx:360`, community legend in `GraphCanvas.tsx:377`), `fuchsia` (implicit-fact marker in `GraphCanvas.tsx:408`, and separately as the "visualize" intent color in `AgentPanel.tsx:24`), `rose` (errors/destructive) — 5 hues covering state badges that appear right next to the syntax-highlighted data, making it hard to tell "this color means data type" from "this color means system state" at a glance.

**Consolidated semantic palette for state/status badges only** (data syntax-highlighting in item 1 is unchanged):

| Role | Color | Used for |
|---|---|---|
| Neutral / selected | `white` / `zinc-100` on `zinc-800` | primary buttons, active tab, active toggle, selected node |
| Derived / pending / needs-attention | `amber-400` | derived nodes/facts/triples, pending feedback, pending implicit facts |
| Approved / structural-truth | `emerald-400` | approved facts, "up" status dots (kept distinct from the syntax-highlight use of emerald since the two never appear in the same visual cluster) |
| Structural / explain | `violet-400` | proof-path, ontology-resolution notes, implicit-fact marker (folded in — an implicit fact is itself a kind of derivation/explanation) |
| Destructive / error | `rose-400` | errors, delete, reject, stop |

Two specific, narrow retirements (not a full-palette rewrite): the **custom-rule tag** (`ConstructionPanel.tsx:396`) and **community-toggle/legend** (`GraphCanvas.tsx:360,377`) move from `sky` to a neutral `zinc-300` outline + existing icon (`Cpu`/`Boxes` already carries the meaning, so the extra hue was redundant), and `AgentPanel.tsx`'s "visualize" intent badge moves from `fuchsia` to `sky` (freeing fuchsia entirely, and reusing a hue that's otherwise only present in the syntax-highlight layer, which never appears inside a chat message bubble alongside it).

**Typography**: keep the existing Tailwind default stack (no new font dependency to install/verify) but standardize the *scale* that's currently ad-hoc across `[8px]`/`[9px]`/`[10px]`/`[11px]` text sizes sprinkled per-component. Adopt 3 fixed steps: `text-[9px]` (micro-labels, badges, footer), `text-[11px]` (body/list content — most panel text today already gravitates here), `text-sm` (section headers, primary actions). This is a mechanical find-and-normalize pass across existing components, not a new type system.

### 3.7 Deferred / Optional Polish (Phase 5, not required for decluttering)

These are worth naming so they're not silently forgotten, but they add engineering risk/cost disproportionate to the decluttering goal and should only be picked up if there's appetite after Phases 1–4 ship and are verified:

* Floating Figma-style Add Node/Edge toolbar directly on the canvas (vs. staying in the Build tab).
* `motion/react` micro-animations for tab/accordion transitions (currently plain CSS `transition-colors`/`transition-all`, which is already smooth and costs nothing to keep).
* Custom display font (e.g. Space Grotesk) for headers — cosmetic only, adds a font-loading dependency for a project that currently ships zero custom web fonts.
* Glassmorphism (`backdrop-blur` + translucency) on the floating node inspector card, matching the header's existing `backdrop-blur`.

---

## 4. Functionality Preservation Matrix

Every control from §1.1's inventory, mapped to its new location. This table is the acceptance criteria for "ensure all existing functionalities still work" — each row should be checked off during implementation via live browser verification (§6).

| Feature | Old location | New location | Component change |
|---|---|---|---|
| Paste text, doc hints, extract→graph, error+retry, recent ingests | Left › Ingest | Build › accordion § "Ingest" | `IngestPanel.tsx` unchanged, re-mounted |
| Node label/type/badges/source-doc | Left › Construct | Floating `NodeInspectorCard` (read view) + Build › accordion § "Construct" (full view) | New `NodeInspectorCard.tsx`; `ConstructionPanel.tsx` unchanged |
| Salience slider, properties editor, proof-path detail, note | Left › Construct | Build › accordion § "Construct" | `ConstructionPanel.tsx` unchanged |
| Add Node form | Left › Construct | Build › accordion § "Construct" | unchanged |
| Add Edge / link mode | Left › Construct | Build › accordion § "Construct" | unchanged; canvas link-mode banner unchanged |
| Rules Manager (list, create, delete) | Left › Construct | Build › accordion § "Construct" | unchanged |
| Enrichment run + pending/approved review | Left › Enrich | Build › accordion § "Enrich" | `EnrichmentPanel.tsx` unchanged |
| 3-step Reason loop, trace, auto-run, convergence shortcut | Left › Reason | Reason (unchanged top-level tab) | `ReasoningPanel.tsx` unchanged |
| Datalog query console + examples + history | Right › Query | Query › pill "Pattern Query" | `QueryPanel.tsx` unchanged |
| Find Path (BFS + proof) | Right › Query | Query › pill "Pattern Query" (same panel, unchanged) | unchanged |
| Full triple list + filter | Right › Triples | Query › pill "Triples" | `TripleStorePanel.tsx` unchanged |
| Ontology classes/properties/subclass browser | Right › Ontology | Query › pill "Ontology" | `OntologyPanel.tsx` unchanged |
| Read-only chat (`/chat`) | Right › LLM | Assistant › mode "Ask" | `LlmPanel.tsx` unchanged, rendered under toggle |
| Mutating agent chat (`/agent`, 6 intents) | Right › Agent | Assistant › mode "Act" | `AgentPanel.tsx` unchanged, rendered under toggle |
| Skills list/activate/view SKILL.md | Right › Skills | Tools › pill "Skills" | `SkillManager.tsx` unchanged |
| Memory search + preferences CRUD | Right › Memory | Tools › pill "Memory" | `MemoryInspector.tsx` unchanged |
| Switch/create graph | Left tab-strip icon → `GraphsPopover` | Header icon → `GraphsPopover` (same component) | anchor div relocates, component unchanged |
| Ingest history | Left tab-strip icon → `HistoryPopover` | Header icon → `HistoryPopover` (same component) | anchor div relocates, component unchanged |
| Node/edge/rule/fact counts | Header | Footer | new `StatusFooter.tsx`, values sourced from same `useGraphStore()` fields |
| neo4j/graphdb up/down | Header | Footer | same |
| Iteration count | Header | Footer | same |
| Pending-facts badge (click → Enrich) | Header | Header (kept) → now sets `activeTab='build'` + expands Enrich accordion section | logic updated, still one click |
| AUTO-RUN pulsing badge | Header | Header (kept, unchanged) | unchanged |
| Canvas zoom/pan/drag/select/link-click | Canvas | Canvas (unchanged) | `GraphCanvas.tsx` unchanged |
| Canvas floating controls (zoom/heatmap/proof-path/communities) | Canvas | Canvas (unchanged) | unchanged |
| Type/community legend, implicit-fact legend | Canvas | Canvas (unchanged) | unchanged |

No row in this table results in a feature being deleted — every one is either "unchanged, different mount point" or "unchanged, behind one extra affordance click (accordion expand / pill switch / mode toggle) that replaces a tab click 1-for-1."

---

## 5. File-by-File Implementation Plan

Ordered as PR-sized, independently-shippable increments. Each phase leaves the app in a fully working state — this is not a big-bang rewrite.

### Phase 0 — State model consolidation (no visual change, foundational)
* In `App.tsx`, replace `leftTab`/`rightTab`/`leftCollapsed`/`rightCollapsed`/`leftWidth`/`rightWidth`/`resizing: 'left'|'right'|null` with a single `activeTab: 'build' | 'reason' | 'query' | 'assistant' | 'tools'`, `sidebarCollapsed: boolean`, `sidebarWidth: number`, `resizing: boolean`.
* No `graphStore.ts` changes needed — all of this is local UI state, not application data, exactly as it is today. Verify with a no-op sanity check: app still renders the *current* (pre-refactor) tabs against the new state names before any layout changes land, to isolate risk.

### Phase 1 — Single sidebar, 6 consolidated tabs
* New `components/Sidebar.tsx`: renders the vertical icon rail (5 icons: Build/Reason/Query/Assistant/Tools), the collapse toggle, the resize handle, and the active tab's body. Replaces the near-duplicate left-sidebar and right-sidebar JSX blocks currently inline in `App.tsx` (lines ~192–260 and ~285–379) with one component used once.
* New `components/panels/BuildPanel.tsx`: accordion shell with 3 sections (Ingest / Construct / Enrich), each rendering the existing `IngestPanel`, `ConstructionPanel`, `EnrichmentPanel` unchanged. Default-expanded section: Ingest if the graph is empty, else Construct.
* New `components/panels/QueryExplorePanel.tsx`: pill switcher (Pattern Query / Triples / Ontology) rendering existing `QueryPanel`, `TripleStorePanel`, `OntologyPanel` unchanged.
* New `components/panels/AssistantPanel.tsx`: Ask/Act toggle rendering existing `LlmPanel` / `AgentPanel` unchanged.
* New `components/panels/ToolsPanel.tsx`: pill switcher (Skills / Memory) rendering existing `SkillManager` / `MemoryInspector` unchanged.
* `ReasoningPanel.tsx` mounts directly under the Reason tab, no wrapper needed.
* Update `App.tsx` to render `<Sidebar activeTab={...} ... />` once, remove the old dual-sidebar markup.

### Phase 2 — Header decluttering + footer status bar
* New `components/StatusFooter.tsx`: reads `nodes, edges, rules, facts, iterations` and `health` from the same sources the header used, renders the thin bottom strip described in §3.4.
* Trim `App.tsx`'s `<header>` down to: logo/title/ontology name, `GraphsPopover` trigger (relocated from the old left tab-strip `FolderOpen` button), `HistoryPopover` trigger (relocated from the old `History` button), pending-facts badge (logic updated to set `activeTab='build'` + an Enrich-section-expand signal), Auto-Run badge.
* Remove the now-redundant node/edge/rule/fact/iteration/neo4j/graphdb JSX from the header; mount `<StatusFooter />` at the bottom of the root flex column in `App.tsx`.

### Phase 3 — Contextual Node Inspector
* New `components/NodeInspectorCard.tsx`: floating card, same anchoring pattern as `GraphsPopover`/`HistoryPopover` (`absolute` positioned, `ref`-based outside-click dismissal optional since it's not a menu — it can just persist while a node is selected and disappear on deselect, matching current Construct-tab behavior of "nothing shown when no node selected"). Renders label, type, derived/activation badges, source-doc snippet, proof-path hop count, and an "Edit in Build →" button.
* Render `<NodeInspectorCard />` inside `GraphCanvas.tsx`'s existing overlay `<div className="relative w-full h-full">`, alongside the current control stack — same overlay pattern already used for the link-mode banner and legends, no new positioning system required.
* Wire the "Edit in Build →" button to the same tab-switch + accordion-expand mechanism the header's pending-facts badge now uses (Phase 2), for consistency.

### Phase 4 — Color & typography normalization
* Narrow, targeted recolor of exactly 3 call sites (§3.6): `ConstructionPanel.tsx:396` (custom-rule tag `sky`→`zinc-300` outline), `GraphCanvas.tsx:360,377` (community toggle + legend `sky`→`zinc-300` outline), `AgentPanel.tsx:24` (visualize intent badge `fuchsia`→`sky`). Also fold `GraphCanvas.tsx:408`'s implicit-fact marker from `fuchsia` to `violet-400`. The `emerald`/`sky` data syntax-highlighting convention in `QueryPanel.tsx`, `TripleStorePanel.tsx`, `OntologyPanel.tsx` is explicitly **out of scope** — verified in §3.6 to be a different, non-cluttering use of color that should not change.
* Normalize the `text-[8px]` / `text-[9px]` / `text-[10px]` / `text-[11px]` mix down to the 3-step scale from §3.6, panel by panel.

### Phase 5 — Optional polish (see §3.7)
Not scheduled; revisit only after Phases 1–4 are live-verified and the team wants to invest further.

---

## 6. Verification Plan

This project has no frontend automated test suite (confirmed: no `*.test.*`/`*.spec.*` files, no test runner in `package.json`), so verification is **live browser click-through**, per this project's established convention for frontend work. For each phase:

1. `npm run typecheck` must pass (no `any`, no broken imports from the file moves).
2. Start the dev server, open the app, and walk the §4 Functionality Preservation Matrix top to bottom — every row's "new location" must be reachable and every action must still hit the same real backend endpoint with the same real effect (no mocked/stubbed intermediate state).
3. Specifically re-verify the interactions that are most likely to break during the reorganization (state that depends on which tab is "active" or whether a section is expanded):
   * Pending-facts header badge still jumps to a visible, expanded Enrich section.
   * Selecting a node shows the floating inspector card; "Edit in Build →" switches tabs and expands the right accordion section with the same node still selected.
   * Auto-Run Loop still visibly pulses in the header regardless of which tab is active while it runs.
   * Sidebar collapse/expand and resize-drag still work with the single consolidated sidebar.
   * Switching graphs via the (relocated) `GraphsPopover` still resets/reloads all dependent panels exactly as today (`switchGraph` in `graphStore.ts` is unchanged).
4. Take before/after screenshots of the full viewport at a common resolution (e.g. 1440×900) to confirm the canvas visibly gains width and the header/footer are visibly lighter.

---

## 7. Architectural Notes

* No backend/API changes are required anywhere in this plan — this is purely `frontend/src/App.tsx` plus new composition components under `frontend/src/components/` (and a new `frontend/src/components/panels/` subfolder for the 4 new accordion/pill-switcher wrappers). Every existing panel component's props and internal logic are untouched.
* No `graphStore.ts` (Zustand) changes are required — `activeTab`/`sidebarCollapsed`/accordion-expanded-section state is local UI state in `App.tsx`/`Sidebar.tsx`, exactly matching how `leftTab`/`rightTab`/`leftCollapsed`/`rightCollapsed` are local today.
* This keeps regression risk low and each phase independently revertible: Phase 0 touches only state variable names, Phase 1 touches only mounting/composition, Phase 2 is additive (new footer) plus deletion of already-duplicated header JSX, Phase 3 is purely additive, Phase 4 is a mechanical find-and-replace pass.
