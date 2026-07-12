# Neurosymbolic KG UI/UX Refactor Plan

This document outlines a comprehensive analysis of the current **Neurosymbolic Knowledge Graph** interface and proposes a design overhaul inspired by the professional, minimal, and highly focused aesthetics of **Google AI Studio**.

**Hard constraint for every phase below: zero functionality loss.** Every button, form, badge, and data view catalogued in §1.1 must have an explicit new home in §5's mapping table before any code is written. This is a *reorganization and visual pass*, not a rewrite of business logic — nearly every existing panel component (`IngestPanel`, `ConstructionPanel`, `ReasoningPanel`, `EnrichmentPanel`, `QueryPanel`, `TripleStorePanel`, `OntologyPanel`, `LlmPanel`, `AgentPanel`, `SkillManager`, `MemoryInspector`, `GraphCanvas`) keeps its internals untouched and is simply re-mounted inside new, thinner composition wrappers.

**Revision note**: an earlier draft of this document moved the entire navigation to a left-edge rail, replacing the right sidebar outright. That was a misread of the brief — the right sidebar and its consolidated tabs stay exactly where they are (§2–§5 below), and the left side gets something genuinely *new*: a project-level navigation bar for pages that don't fit inside the single-graph workspace at all (§6). The two are complementary, not a replacement of one by the other.

---

## 1. Problem Statement: Why the Current UI Feels Cluttered

The current layout packs an enormous amount of functionality into a single viewport. While powerful, it suffers from several core design anti-patterns:

1. **Dual-Sidebar Squeeze**: Having both left and right sidebars active simultaneously (up to 640px each, 400px by default) restricts the central `GraphCanvas` to a narrow, vertical strip on anything under a 27" monitor. A graph visualization requires horizontal breathing room to prevent nodes from overlapping and lines from bunching.
2. **Metadata Overload ("Technical Larping")**: The header is crowded with raw telemetry: connection pings (`neo4j up`, `graphdb up`), node/edge counts, rule counts, fact counts, pending statuses, and iteration badges — all visible simultaneously, all fighting for the same 56px-tall strip. It resembles a server terminal rather than a polished product.
3. **Tab Fatigue**: Splitting workflows across **11 different tabs** (Left: *Ingest, Construct, Reason, Enrich*; Right: *Query, Triples, Ontology, LLM, Agent, Skills, Memory*) confuses the user. Several tab boundaries are semantically thin — "Query" vs. "Triples" are both "look at facts in the graph," and "LLM" vs. "Agent" are both "chat about the graph," differing only in whether the reply can mutate state.
4. **Visual Hierarchy Noise**: badges across amber/violet/emerald/rose/sky/fuchsia compete for attention across at least 5 different semantic meanings.
5. **No home for project-level capabilities**: two real backend surfaces built into this project — the ontology (`GET /ontology`) and rules (`GET/POST/DELETE /rules`) — are **not graph-scoped at all** (confirmed: neither endpoint takes a `graph_id`), yet today they're buried inside a single graph's workspace tabs as if they were per-graph data. And a brand-new real capability, the `evals/` skill-testing harness (11 real cases across all 6 runtime skills, real pass/fail results), has **no UI at all** — it's CLI-only. These don't fit the "tab inside one graph's workspace" model no matter how the tabs are reorganized, because they aren't about one graph. §6 addresses this directly.

### 1.1 Full Functional Inventory (baseline — nothing below may be dropped)

**Header** (`App.tsx` lines ~130–187): logo/title, ontology repo name (from `/health`), node count, edge count, rule count, fact count (conditional), pending-implicit-facts count (conditional, clickable → jumps to Enrich), iteration count (conditional), `AUTO-RUN` pulsing badge (conditional), neo4j up/down, graphdb up/down.

**Left sidebar — 4 tabs + 2 popover triggers:**
| Tab | Component | Contains |
|---|---|---|
| Ingest | `IngestPanel.tsx` | doc-type hint chips, textarea w/ char+word count, Extract→Graph button, Clear-text button, error banner w/ retry, last-4 recent-ingest cards |
| Construct | `ConstructionPanel.tsx` | Node Inspector (label/type/derived badge/activation %/source-doc/salience slider/properties k-v editor/proof-path steps/note textarea), Add Node (label input + ontology-backed type select + button), Add Edge (ontology-backed relation select + start/cancel linking), Rules Manager (list + create-custom-rule form: name/source type/target type/edge type/threshold slider/description, delete for custom rules only) |
| Reason | `ReasoningPanel.tsx` | intro blurb, 3-step status strip (neural/symbolic/feedback, live checkmarks), Auto-Run Loop button, heatmap toggle, proof-path toggle, Step 1 Spread Activation (button, clear, top-8 activated-node bars), Step 2 Run Inference (button, clear, fired/skipped inference trace list, derived-facts list w/ full proof path + ontology-resolution notes), Step 3 Feed Back (button w/ pending count), atomic "Run to Convergence" shortcut w/ convergedBy badge |
| Enrich | `EnrichmentPanel.tsx` | intro blurb, textarea + Run Enrichment button, confidence-sorted Pending Review cards (approve/reject), collapsible Approved list |
| *(popover)* | `GraphsPopover.tsx` | switch graph, create new graph |
| *(popover)* | `HistoryPopover.tsx` | full ingest-event history (per current graph), expandable full text |

**Right sidebar — 7 tabs:**
| Tab | Component | Contains |
|---|---|---|
| Query | `QueryPanel.tsx` | Datalog-style query console (input, run, last-5 history chips, 6 example-query buttons), Find Path (source/target inputs, BFS path result w/ chain + proof string), query results list (derived/base badges, confidence) |
| Triples | `TripleStorePanel.tsx` | full triple store, search/filter, derived/base badges, confidence |
| Ontology | `OntologyPanel.tsx` | collapsible Subclass Relations / Classes / Properties sections — **note: this data is NOT graph-scoped** (`GET /ontology` takes no `graph_id`), it reflects whatever ontology is loaded project-wide |
| LLM | `LlmPanel.tsx` | read-only Q&A chat grounded in graph state (`POST /chat`), suggestion chips |
| Agent | `AgentPanel.tsx` | LangGraph agent chat that can mutate the graph (`POST /agent`, 6 intents: extract/enrich/query/reason/recall/visualize), intent badges, suggestion chips |
| Skills | `SkillManager.tsx` | 6 runtime skills, active/inactive badges, expand-to-view SKILL.md body, activate button — **also not graph-scoped**, skill activation state is global |
| Memory | `MemoryInspector.tsx` | cross-source memory search (chat history + entity summaries, graph-scoped), key/value preferences CRUD — **the preferences half is not graph-scoped**, it's a global settings store |

**Canvas** (`GraphCanvas.tsx`): SVG pan/zoom/drag node placement, node select, link-mode click-to-connect w/ banner, floating top-right control stack (zoom in/out/reset, heatmap toggle, proof-path toggle, detect-communities, toggle community-coloring), bottom-right zoom% indicator, top-left type/community legend, bottom-left implicit-fact-count legend, hash-hue type/community coloring, activation glow rendering, derived-node pulse animation. Node layout is a deterministic circular layout (`layoutNodes` in `graphStore.ts`), not a physics simulation — a force-directed ("live physics") layout is a pre-existing, already-tracked deferred item (`UI_PLAN.md` §7: "d3-force layout"), not something this document invents; §7.4 revisits whether to pull it forward.

Every one of the ~45 individual controls/views above gets an explicit destination in §5.

---

## 2. Design Inspiration: Google AI Studio UI Principles

* **Canvas-First Layout**: the primary workspace (the Knowledge Graph Canvas) dominates the screen — it fully occupies the main viewport, flanked by the sidebar on the right, exactly as today, just with less of it lost to sidebar bloat.
* **Contextual Sidebar**: control panels are secondary and single-sided (right), collapsible, with grouped rather than flat-listed tabs, navigated via a compact **vertical icon rail embedded at the sidebar's own left margin** (not a horizontal tab strip on top of the panel, and not a separate full-height rail spanning the whole viewport) — this is the detail the first draft got wrong by moving the rail to the outer edge of the screen; it belongs *inside* the sidebar, right where the tab strip is today, just rendered as a narrow vertical icon column instead of a cramped horizontal row.
* **Subtle & Uniform Palette**: a monochrome foundation with a disciplined, small set of semantic accent colors instead of a rainbow of one-off badge colors (§4).
* **Low-Density Margins**: stats and connection status move into a thin, low-contrast footer instead of competing for header sightlines.
* **Typography**: standardize on **Inter** for UI text (body/headers) and **JetBrains Mono** for monospace contexts (queries, triples, rule/edge-type labels, footer telemetry) — both are the fonts Google AI Studio itself uses, and neither the current app nor `package.json` has any font dependency today, so this is a clean, deliberate adoption rather than a default to avoid disturbing.

---

## 3. The Right Sidebar: 11 Tabs → 6, One Consolidated Drawer

### 3.1 Tab Consolidation

The guiding rule: **group by user intent, not by backend endpoint.** A user thinks "I want to build the graph," "I want to reason over it," "I want to ask about it," or "I want to look something up" — not "which of 11 tabs holds the button I need."

| New tab | Icon | Replaces | Why grouped |
|---|---|---|---|
| **Build** | `Layers` | Ingest + Construct + Enrich (3 left tabs) | All three are "add or curate graph content" — ingest text, add nodes/edges/rules by hand, review AI-proposed implicit facts. Sequential in a typical session (ingest → inspect/construct → enrich), so an accordion (not sub-tabs) fits: one section expanded at a time, others collapsed but always one click away. |
| **Reason** | `Activity` | Reason (unchanged) | Kept as its own dedicated top-level tab — it's the single most complex, most frequently-iterated workflow (3 manual steps + trace + auto-run) and doesn't share enough surface with anything else to justify merging. |
| **Query** | `Search` | Query + Triples + Ontology (3 right tabs) | All three are "inspect what's already true in the graph," differing only in query style (pattern query / raw triple list / schema browse). A light segmented control (pill switcher, not full tabs) inside one panel keeps them one click apart without three more top-level tabs. *(The Ontology pill's content is project-wide, not graph-scoped — see §6.3 for the argument to eventually promote it to its own left-nav page; for now it stays here since moving it is a larger, separate decision from this consolidation.)* |
| **Assistant** | `Bot` | LLM + Agent (2 right tabs) | Both are chat interfaces over the same graph; the only difference is whether the reply can mutate state. Collapse into one chat surface with an **Ask / Act** mode toggle at the top — Ask hits `POST /chat` (current LLM tab behavior, read-only), Act hits `POST /agent` (current Agent tab behavior, can extract/enrich/query/reason/recall/visualize). One input box, one message thread, half the chrome. |
| **Tools** | `Wrench` | Skills + Memory (2 right tabs) | Both are meta/introspection surfaces used less frequently than Build/Reason/Query/Assistant during normal work. A sub-tab pill switcher (Skills / Memory) inside one panel. |

Net: **6 tabs, one sidebar, one resize handle, one collapse button** — down from 4+7 tabs across two independently-resizable sidebars, canvas regains up to ~400–480px of width whenever the (now-removed) left sidebar would previously also have been open.

### 3.2 Sidebar Internal Layout — Embedded Icon Rail

```
+-----------------------------------------------------------------------------------+
|  ⬡ Neurosymbolic KG   ontology: fibo    [⌂ default ▾]  [🕐]     ✦2 pending  ⚙     |  <- 48px header
+---------------------------------------------------------------+----+--------------+
|                                                                 |    |             |
|                                                                 | ▤  | Build       |
|                                                                 | Bld|  ▸ Ingest    |
|              Main Graph Canvas                                 |    |  ▾ Construct |
|              (dominates viewport, up to full width             | ◐  |    ...       |
|               when the sidebar is collapsed)                   | Rsn|  ▸ Enrich    |
|                                                                 |    |             |
|   [floating node inspector card, top-right,                    | 🔍 |             |
|    below the zoom/heatmap control stack, only when              | Qry|             |
|    a node is selected]                                         |    |             |
|                                                                 | 🤖 |             |
|                                                                 | Ast|             |
|                                                                 |    |             |
|                                                                 | 🔧 |             |
|                                                                 | Tls|             |
+-----------------------------------------------------------------------------------+
|  12 nodes · 14 edges · 4 rules · 3 facts   ·   ● neo4j   ● graphdb   iter 2        |  <- 22px footer
+-----------------------------------------------------------------------------------+
```

* The icon rail (`▤ ◐ 🔍 🤖 🔧` — Build/Reason/Query/Assistant/Tools) sits at the sidebar's own left edge, a fixed ~48px-wide column *inside* the sidebar's existing 400px (300–640px resizable) width — it is not a second sidebar and does not consume additional screen real estate beyond what the sidebar already occupies today. This directly answers "keep the vertical rail besides the sidebar, like before": the rail and the sidebar are one structure, not two.
* The sidebar's single collapse button (top-right of the rail, replacing today's `PanelRightClose`) hides the whole thing, same as today's right-sidebar collapse — no behavior change there.
* Each rail icon shows a compact 2-3 letter label beneath it (`Bld`, `Rsn`, `Qry`, `Ast`, `Tls`) at `text-[8px]`, since a vertical column has room for a label a horizontal 7-tab strip didn't.
* Clicking a rail icon swaps the panel body to its right, exactly like today's tab click — same interaction, just relabeled and vertically laid out.

### 3.3 Header Decluttering & Footer Status Bar

Unchanged from the original analysis: header keeps only logo, ontology name, graph switcher (`GraphsPopover`, relocated from the left sidebar's old `FolderOpen` icon into the header), ingest-history trigger (`HistoryPopover`, same relocation), the pending-implicit-facts badge (clicking it opens the Build tab with the Enrich section expanded), and the Auto-Run pulsing indicator. Node/edge/rule/fact/iteration counts and neo4j/graphdb status move to a new thin footer strip (`StatusFooter.tsx`, `font-mono text-[10px] text-zinc-500`, matching `IngestPanel`'s existing recent-ingest metadata style).

### 3.4 Contextual Node Inspector (floating, canvas-anchored)

A **compact, read-only summary card** floats over the canvas's top-right corner, below the existing zoom/heatmap control stack, whenever `selectedNodeId` is non-null: label, type, derived/activation badges, source-doc snippet, proof-path hop count — a strict subset of what `ConstructionPanel`'s Node Inspector already renders, extracted into `NodeInspectorCard.tsx`. A single **"Edit in Build →"** button opens the sidebar's Build tab with the Construct accordion section expanded; the full editable form (salience slider, properties editor, proof-path detail, note) stays exactly where it is today inside `ConstructionPanel.tsx`, completely unchanged — this card is a discoverable shortcut, not a replacement.

---

## 4. Color & Typography System

Auditing actual usage (`grep -rn "sky-\|fuchsia-\|violet-\|amber-\|emerald-\|rose-" frontend/src/components`) shows two genuinely different things are currently sharing the same "colored text" technique, and only one of them is the clutter problem:

1. **Data syntax-highlighting** — `QueryPanel`, `TripleStorePanel`, `OntologyPanel` consistently use `emerald` for subject/child and `sky` for object/target/parent across triple and query-result rendering (e.g. `QueryPanel.tsx:177-179`, `TripleStorePanel.tsx:82-84`, `OntologyPanel.tsx:64-66`). This is coherent and low-noise — closer to syntax highlighting than badge soup — and **should be kept as-is**.
2. **Status/state badges** — the actual source of visual noise: `amber` (derived), `violet` (proof-path), `sky` (custom-rule tag in `ConstructionPanel.tsx:396`, community-toggle in `GraphCanvas.tsx:360,377`), `fuchsia` (implicit-fact marker in `GraphCanvas.tsx:408`, and separately the "visualize" intent color in `AgentPanel.tsx:24`), `rose` (errors/destructive).

**Consolidated semantic palette for state/status badges only** (data syntax-highlighting above is unchanged):

| Role | Color | Used for |
|---|---|---|
| Neutral / selected | `white` / `zinc-100` on `zinc-800` | primary buttons, active tab, active toggle, selected node |
| Derived / pending / needs-attention | `amber-400` | derived nodes/facts/triples, pending feedback, pending implicit facts |
| Approved / structural-truth | `emerald-400` | approved facts, "up" status dots |
| Structural / explain | `violet-400` | proof-path, ontology-resolution notes, implicit-fact marker (folded in) |
| Destructive / error | `rose-400` | errors, delete, reject, stop |

Two narrow retirements: the custom-rule tag (`ConstructionPanel.tsx:396`) and community-toggle/legend (`GraphCanvas.tsx:360,377`) move from `sky` to a neutral `zinc-300` outline + existing icon; `AgentPanel.tsx`'s "visualize" intent badge moves from `fuchsia` to `sky` (freeing fuchsia entirely).

**Typography**: adopt **Inter** (UI text) and **JetBrains Mono** (queries, triples, rule/edge labels, footer) via `next/font`-equivalent self-hosted `@fontsource` packages (avoids a runtime Google Fonts network dependency) — replacing the current unstyled system-font stack. Also normalize the ad-hoc `text-[8px]`/`[9px]`/`[10px]`/`[11px]` mix down to 3 fixed steps: `text-[9px]` (micro-labels/badges/footer), `text-[11px]` (body/list content), `text-sm` (section headers, primary actions).

---

## 5. Functionality Preservation Matrix

Every control from §1.1's inventory, mapped to its new location. This table is the acceptance criteria for "ensure all existing functionalities still work."

| Feature | Old location | New location | Component change |
|---|---|---|---|
| Paste text, doc-type hint chips, char/word count | Left › Ingest | Sidebar rail `Build` › drawer § "Ingest" | `IngestPanel.tsx` unchanged, re-mounted |
| Extract → Graph button, loading state, Clear-text, error+retry | Left › Ingest | Sidebar rail `Build` › drawer § "Ingest" | unchanged |
| Recent-ingests list (last 4) | Left › Ingest | Sidebar rail `Build` › drawer § "Ingest" | unchanged |
| Node label/type/badges/source-doc | Left › Construct | Floating `NodeInspectorCard` (read view) + Sidebar rail `Build` › drawer § "Construct" (full view) | new `NodeInspectorCard.tsx`; `ConstructionPanel.tsx` unchanged |
| Salience slider, properties k-v editor, proof-path detail, note | Left › Construct | Sidebar rail `Build` › drawer § "Construct" | `ConstructionPanel.tsx` unchanged |
| Add Node form, Add Edge / link mode, Rules Manager (list/create/delete) | Left › Construct | Sidebar rail `Build` › drawer § "Construct" | unchanged; canvas link-mode banner unchanged |
| Enrichment run + pending review (approve/reject) + approved list | Left › Enrich | Sidebar rail `Build` › drawer § "Enrich" | `EnrichmentPanel.tsx` unchanged |
| 3-step loop status strip, Auto-Run, own heatmap/proof-path toggles, Step 1/2/3 buttons + Clear, trace list, derived-facts list, convergence shortcut | Left › Reason | Sidebar rail `Reason` › drawer (unchanged) | `ReasoningPanel.tsx` unchanged |
| Datalog query console, 6 example buttons, last-5 history, Find Path (BFS + proof) | Right › Query | Sidebar rail `Query` › drawer, pill "Pattern Query" | `QueryPanel.tsx` unchanged |
| Full triple list + search/filter | Right › Triples | Sidebar rail `Query` › drawer, pill "Triples" | `TripleStorePanel.tsx` unchanged |
| Ontology classes/properties/subclass browser | Right › Ontology | Sidebar rail `Query` › drawer, pill "Ontology" | `OntologyPanel.tsx` unchanged (candidate for promotion to a left-nav page later, §6.3) |
| Read-only chat (`POST /chat`) + suggestion chips | Right › LLM | Sidebar rail `Assistant` › drawer, mode "Ask" | `LlmPanel.tsx` unchanged, rendered under toggle |
| Mutating agent chat (`POST /agent`, 6 intents) + intent badges + suggestion chips | Right › Agent | Sidebar rail `Assistant` › drawer, mode "Act" | `AgentPanel.tsx` unchanged, rendered under toggle |
| Skills list w/ active badges, expand-to-view SKILL.md, activate button | Right › Skills | Sidebar rail `Tools` › drawer, pill "Skills" | `SkillManager.tsx` unchanged |
| Memory search (chat history + entity summaries) | Right › Memory | Sidebar rail `Tools` › drawer, pill "Memory" | `MemoryInspector.tsx` search half unchanged |
| Preferences CRUD | Right › Memory | Sidebar rail `Tools` › drawer, pill "Memory" (kept here for now; candidate for a left-nav Settings page, §6.5) | `MemoryInspector.tsx` preferences half unchanged |
| Switch/create graph | Left tab-strip icon → `GraphsPopover` | Header icon → `GraphsPopover` (same component) | anchor relocates, component unchanged |
| Ingest history, expandable full text | Left tab-strip icon → `HistoryPopover` | Header icon → `HistoryPopover` (same component) | anchor relocates, component unchanged |
| Node/edge/rule/fact counts, neo4j/graphdb up/down, iteration count | Header | Footer | new `StatusFooter.tsx`, same `useGraphStore()` fields |
| Pending-facts badge (click → Enrich) | Header | Header (kept) → opens Build drawer with Enrich section expanded | logic updated, still one click |
| AUTO-RUN pulsing badge | Header | Header (kept, unchanged) | unchanged |
| Canvas zoom/pan/drag/select/link-click, drag-and-drop node placement | Canvas | Canvas (unchanged) | `GraphCanvas.tsx` unchanged |
| Canvas floating controls, zoom % indicator, type/community/implicit-fact legends | Canvas | Canvas (unchanged) | unchanged |

No row results in a feature being deleted — every one is either "unchanged, different mount point" or "unchanged, behind one extra rail-click that replaces an old tab click 1-for-1." This table has 22 grouped rows covering every control named in §1.1 — grouping (e.g. one row for "6 example buttons + history") is for table readability, not omission.

---

## 6. NEW: Left Navigation Bar — Project-Level Pages

This is the genuinely new piece: a slim (~56px), always-visible, icon-only vertical bar on the **far left edge of the whole viewport** (outside and to the left of the canvas+sidebar workspace described above), for switching between distinct top-level **pages** of the project — not sub-panels of one graph's workspace, but separate surfaces the way AI Studio's own left rail switches between Chat / Stream / History / Library / Settings.

The single-graph canvas + right-sidebar workspace from §2–§5 becomes **one page** on this bar (`Workspace`, the default/home page, unchanged). Everything below is a **candidate** for the remaining slots — grounded in a real, already-built backend capability (per this project's "real data only" rule, nothing here is a placeholder or mock), tagged with how much new backend work each would need.

| Page | Icon | Backed by (real, already exists) | New backend work needed | Why it deserves to be a page, not a tab |
|---|---|---|---|---|
| **Workspace** | `Network` | everything in §2–§5 | none | the default landing page — today's whole app |
| **Graphs** | `FolderOpen` | `GET /graphs` (`graph_service.list_graphs`) | none for a read-only dashboard; a `DELETE /graphs/{id}` would be new if delete-from-UI is wanted | today's `GraphsPopover` is a cramped dropdown for what is, across a real project, actually a first-class "which knowledge base am I working in" decision — a full page (grid of graphs, node/edge counts, last-ingest date, click to open in Workspace) gives it the room that decision deserves |
| **Ontology & Rules** | `BookOpen` | `GET /ontology`, `GET/POST/DELETE /rules` (both confirmed **not graph-scoped**) | none | these two are project-wide configuration masquerading as per-graph tabs today (Ontology sits inside Query's pill switcher, Rules sits inside Build's Construct accordion) — moving them here isn't just decluttering, it's fixing a real information-architecture mismatch: editing a "global" rule from inside "graph X's workspace" implies a scoping that doesn't actually exist in the data model |
| **Evals** | `FlaskConical` | `evals/lib.py`, `evals/cases/*.json`, `evals/results/*.json` (11 real cases, 6 skills, built this session) | yes — needs a thin new REST layer: `GET /evals/cases` (list case files + metadata), `GET /evals/results` (read latest timestamped JSON from `evals/results/`); a `POST /evals/run` to trigger `run_evals.py` from the UI is a further, separate decision (running a backend subprocess from an HTTP request needs its own auth/rate-limit thinking, not just a route) | this infrastructure exists and works (11/11 cases pass against the real backend, verified live) but is **completely invisible** in the product today — a page showing case definitions and last-run pass/fail per skill turns real, already-built verification work into something the team can actually see without opening a terminal |
| **MCP Servers** | `Plug` | `mcp_server.py`, `mcp_neo4j_server.py`, `mcp_memory_server.py`, `mcp_skills_server.py` (4 real servers, real tools) | yes — needs new REST wrappers wherever we want the UI to call a tool directly (some already effectively exist as normal REST endpoints — e.g. Skills/Memory MCP tools are already duplicated as `/skills`/`/memory` REST routes for the sidebar; a dedicated page would mostly be surfacing `mcp.list_tools()` per server as a reference/catalog, which needs no new backend beyond a static description of the 4 servers) | there's no way today to see, from inside the app, that this project even *has* 4 working MCP servers — a low-effort read-only catalog page (server name, tool list, tool descriptions) makes real, already-shipped capability discoverable |
| **Settings** | `Settings` | `services/preferences_store.py`, `GET/PUT/DELETE /memory/preferences` | none | the preferences CRUD currently buried in the sidebar's Tools→Memory pill is global app config, not something tied to whichever graph happens to be open — giving it a dedicated page (and pulling it out of `MemoryInspector.tsx`, leaving that component's *search* half where it is per §5) matches how every other real settings surface in a serious tool is organized |

### 6.1 What this deliberately does NOT include

No fabricated pages. Two tempting additions were considered and rejected for now because they'd need either fake data or a materially bigger backend lift than "wrap an existing service":
* A cross-graph **Activity/History feed** (all ingests across all graphs, not just the current one) — `GET /history/{graph_id}` is graph-scoped today; a global version would need a new aggregation query. Worth doing later, not included as a page yet.
* A **Chat/Agent Sessions browser** (list past `:ChatSession`s the way `HistoryPopover` lists ingests) — the data exists (`:ChatSession`/`:ChatMessage` nodes, already read by `memory_service.search_memory`), but there's no "list sessions" query today, only "search within a session's messages." A small, real addition (`GET /memory/{graph_id}/sessions`) — flagged here so it's not forgotten, but not scheduled as a Phase below since it's genuinely new backend surface, not just relocation.

### 6.2 Left Nav Layout

```
+----+------------------------------------------------------------------------------+
|    |  ⬡ Neurosymbolic KG   ontology: fibo   [⌂ default ▾]  [🕐]   ✦2 pending  ⚙   |
| ⬡  +------------------------------------------------------+----+------------------+
|    |                                                        |    |                 |
| ⊙  |                                                        | ▤  |  (right sidebar |
| Wrk|              Main Graph Canvas                         | Bld|   as in §2–§5,  |
|    |              (Workspace page only)                     |    |   unchanged)    |
| 📁 |                                                        | ◐  |                 |
| Grf|                                                        | Rsn|                 |
|    |                                                        |    |                 |
| 📖 |                                                        | 🔍 |                 |
| Ont|                                                        | Qry|                 |
|    |                                                        |    |                 |
| ⚗  |                                                        | 🤖 |                 |
| Evl|                                                        | Ast|                 |
|    |                                                        |    |                 |
| 🔌 |                                                        | 🔧 |                 |
| Mcp|                                                        | Tls|                 |
|    |                                                        |    |                 |
| ⚙  |                                                        |    |                 |
| Set|                                                        |    |                 |
+----+------------------------------------------------------------------------------+
|    |  12 nodes · 14 edges · 4 rules · 3 facts   ·   ● neo4j   ● graphdb   iter 2   |
+----+------------------------------------------------------------------------------+
```

* This left bar is ~56px, fixed, outside the header row (spans full viewport height, header sits to its right) — a genuinely separate landmark from the right sidebar's embedded rail (§3.2), matching the "keep the vertical rail beside the [right] sidebar, and add left navigation separately" instruction directly.
* Only `Workspace` renders the canvas + right sidebar described in §2–§5. Every other page (`Graphs`, `Ontology & Rules`, `Evals`, `MCP Servers`, `Settings`) is a simple full-width content page with no canvas and no right sidebar — a lighter-weight `MainLayout` variant, not a squeezed-in third column.
* The header and footer persist across all pages (ontology name, graph switcher, connection status stay meaningful and visible everywhere), except the per-graph counts in the footer, which only make sense on the `Workspace` page and should read as blank/hidden on the others.

---

## 7. File-by-File Implementation Plan

Ordered as PR-sized, independently-shippable increments. Each phase leaves the app in a fully working state.

### Phase 0 — State model consolidation (no visual change, foundational)
* In `App.tsx`, replace `leftTab`/`rightTab`/`leftCollapsed`/`rightCollapsed`/`leftWidth`/`rightWidth` with `activeTool: 'build' | 'reason' | 'query' | 'assistant' | 'tools'` (the right sidebar's active tab) and `sidebarCollapsed: boolean` / `sidebarWidth: number` (unchanged behavior, renamed for clarity now that "sidebar" unambiguously means the one on the right).
* Separately, add `activePage: 'workspace' | 'graphs' | 'ontology-rules' | 'evals' | 'mcp' | 'settings'` for the new left nav (§6), defaulting to `'workspace'`.
* No `graphStore.ts` changes needed for either — both are local UI state, as today.

### Phase 1 — Right sidebar: consolidate 11→6 tabs with embedded icon rail
* New `components/Sidebar.tsx`: renders the embedded vertical icon rail (5 icons: Build/Reason/Query/Assistant/Tools) at the sidebar's own left margin, the collapse toggle, the resize handle, and the active tab's body. Replaces the near-duplicate left/right sidebar JSX blocks currently inline in `App.tsx`.
* New `components/panels/BuildPanel.tsx` (accordion: Ingest/Construct/Enrich), `QueryExplorePanel.tsx` (pill: Pattern Query/Triples/Ontology), `AssistantPanel.tsx` (Ask/Act toggle), `ToolsPanel.tsx` (pill: Skills/Memory) — each a thin composition wrapper rendering the existing, unmodified panel components from §1.1.
* `ReasoningPanel.tsx` mounts directly under the Reason rail item, no wrapper needed.

### Phase 2 — Header decluttering + footer status bar
* New `components/StatusFooter.tsx` (§3.3). Trim the header to the items listed in §3.3.

### Phase 3 — Contextual Node Inspector
* New `components/NodeInspectorCard.tsx` (§3.4), rendered inside `GraphCanvas.tsx`'s existing overlay div.

### Phase 4 — Color & typography normalization
* Narrow recolor of the 4 call sites in §4 (`ConstructionPanel.tsx:396`, `GraphCanvas.tsx:360,377,408`, `AgentPanel.tsx:24`). Data syntax-highlighting colors (`QueryPanel`/`TripleStorePanel`/`OntologyPanel`) are explicitly out of scope.
* Install `@fontsource/inter` and `@fontsource/jetbrains-mono`, wire into `index.css`/Tailwind config, apply the 3-step text-size scale.

### Phase 5 — Left navigation bar shell
* New `components/PageNav.tsx`: the ~56px far-left icon bar (§6.2), 6 icons, `activePage` state from Phase 0.
* New `components/layouts/PageLayout.tsx`: the lighter-weight full-width layout (header + footer persist, no canvas/sidebar) used by every page except `Workspace`.
* Wire `Workspace` to render exactly what `App.tsx` renders today (post Phases 1–4); other pages render a simple "coming soon" placeholder — this phase ships the navigation shell without yet building the 5 new pages' content.

### Phase 6 — Graphs page (zero new backend work)
* New `pages/GraphsPage.tsx`: grid of `GET /graphs` results (already fetched today for `GraphsPopover`), click-to-switch-and-open-Workspace. `GraphsPopover` itself can stay for quick-switch convenience, or be retired in favor of this page — a call to make once the page exists, not before.

### Phase 7 — Ontology & Rules page (zero new backend work)
* New `pages/OntologyRulesPage.tsx`: reuses `OntologyPanel.tsx`'s data-fetching (`GET /ontology`) and `ConstructionPanel.tsx`'s Rules Manager section (`GET/POST/DELETE /rules`), given more breathing room in a full-width layout instead of a squeezed sidebar pill/accordion section.
* Once this ships and is verified, revisit whether to remove the Ontology pill from the sidebar's Query tab and the Rules section from Build's Construct accordion (§5's matrix rows for these would need updating at that point) — not required to keep both a sidebar shortcut and a full page simultaneously, but worth deciding deliberately rather than by default.

### Phase 8 — Evals page (needs new thin backend endpoints)
* New backend: `GET /evals/cases` (walk `evals/cases/*/*.json`, return id/skill/summary), `GET /evals/results` (read the most recent `evals/results/run-*.json`).
* New `pages/EvalsPage.tsx`: list of cases grouped by skill, latest pass/fail per case from the results endpoint. Read-only; no "run evals from the browser" button in this phase (see §6's note on why that's a separate decision).

### Phase 9 — MCP Servers page (needs new thin backend/static content)
* New `pages/McpServersPage.tsx`: static catalog of the 4 servers and their tools/descriptions (sourced from each server's `@mcp.tool()` docstrings — could be hand-maintained or generated once via a small script calling `mcp.list_tools()` on each server and freezing the output, since MCP servers run over stdio and aren't naturally reachable from a browser session without a bridge).

### Phase 10 — Settings page (zero new backend work)
* New `pages/SettingsPage.tsx`: the preferences CRUD, moved out of `MemoryInspector.tsx` into its own page. `MemoryInspector.tsx` keeps only the memory-search half (still graph-scoped, still belongs in the sidebar's Tools tab).

---

## 8. Verification Plan

This project has no frontend automated test suite (confirmed: no `*.test.*`/`*.spec.*` files, no test runner in `package.json`), so verification is **live browser click-through**, per this project's established convention. For each phase:

1. `npm run typecheck` must pass.
2. Start the dev server, open the app, and walk §5's Functionality Preservation Matrix top to bottom for Phases 0–4; walk §6's page list for Phases 5–10 — every item must be reachable and every action must hit the same real backend endpoint with the same real effect.
3. Specifically re-verify: pending-facts badge still opens Build/Enrich; node selection still shows the floating card and "Edit in Build →" still lands on the right section with the same node selected; Auto-Run still pulses in the header regardless of active tab/page; sidebar collapse/resize still works; graph switching still resets/reloads dependent panels; the new left nav's `Workspace` page is pixel-for-pixel the same app as before Phase 5 (i.e. Phase 5 is purely additive navigation, not a Workspace redesign).
4. Before/after screenshots at a common resolution (1440×900) confirming the canvas visibly gains width and the header/footer are visibly lighter.

---

## 9. Architectural Notes

* No backend/API changes are required for Phases 0–7 (Phase 7's Ontology & Rules page reuses existing `GET /ontology` and `/rules` endpoints as-is). Phases 8–9 need small, additive new endpoints/scripts, called out explicitly above — nothing in this plan requires changing an existing endpoint's contract.
* No `graphStore.ts` (Zustand) changes are required anywhere in this plan — all new state (`activeTool`, `activePage`, accordion-expanded-section, drawer width) is local UI state, exactly matching how `leftTab`/`rightTab`/`leftCollapsed`/`rightCollapsed` are local today.
* Regression risk stays low and every phase is independently revertible: Phase 0 touches only state variable names, Phase 1 touches only mounting/composition, Phase 2 is additive, Phase 3 is purely additive, Phase 4 is a mechanical find-and-replace pass, Phase 5 is a new, currently-inert navigation shell, and Phases 6–10 each ship exactly one new, self-contained page.
