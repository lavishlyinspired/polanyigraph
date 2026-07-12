# Neurosymbolic KG UI/UX Refactor Plan

This document outlines a comprehensive analysis of the current **Neurosymbolic Knowledge Graph** interface and proposes a complete design overhaul inspired by the professional, minimal, and highly focused aesthetics of **Google AI Studio**.

---

## 1. Problem Statement: Why the Current UI Feels Cluttered

The current layout packs an enormous amount of functionality into a single viewport. While powerful, it suffers from several core design anti-patterns:

1. **Dual-Sidebar Squeeze**: Having both left and right sidebars active simultaneously restricts the central `GraphCanvas` to a narrow, vertical strip. A graph visualization requires horizontal breathing room to prevent nodes from overlapping and lines from bunching.
2. **Metadata Overload ("Technical Larping")**: The header is crowded with raw telemetry: connection pings (`neo4j up`, `graphdb up`), node/edge counts, rule counts, fact counts, pending statuses, and iteration badges. It resembles a server terminal rather than a polished product.
3. **Tab Fatigue**: Splitting workflows across **9 different tabs** (Left: *Ingest, Construct, Reason, Enrich*; Right: *Query, Triples, Ontology, LLM, Agent*) confuses the user. The boundaries between "Query", "Triples", and "Ontology" or "LLM" and "Agent" are semantically thin, creating disjointed user journeys.
4. **Visual Hierarchy Noise**: High-contrast, multi-colored badges (violet, amber, rose, emerald, white) fight for attention. This visual competition creates high cognitive load and obscures the actual graph data.

---

## 2. Design Inspiration: Google AI Studio UI Principles

Google AI Studio is built around **creative focus**, **architectural clarity**, and **intentional negative space**. We can adapt its design language through four key principles:

*   **Canvas-First Layout**: The primary workspace (in AI Studio, the prompt editor; in our app, the Knowledge Graph Canvas) must dominate the screen.
*   **Contextual Sidebars**: Control panels are secondary. They should reside on a single side (typically the right), leaving the rest of the workspace completely clean, with collapsible toggle controls.
*   **Subtle & Uniform Palette**: A monochrome foundation (deep grays, soft whites, thin borders) with a single, premium accent color (e.g., Google Blue or a sophisticated indigo) to denote focus, execution, and state.
*   **Low-Density Margins**: Avoid placing stats and statuses in primary sightlines. Hide them behind expandable popovers or put them in a tiny, low-contrast footer.

---

## 3. The Proposed Refactor: Step-by-Step

### Phase A: Layout Simplification (The AI Studio Workspace Grid)

```
+-------------------------------------------------------------------------+
|  Logo  [Select Graph v]                 [Run Loop] [Agent]  Settings    |  <- Minimal Header
+-------------------------------------------------------------------------+
|                                                           |             |
|                                                           |             |
|                                                           |  Contextual |
|                                                           |  Sidebar    |
|                      Main Graph Canvas                    |  (Tabs:     |
|                      (Dominates Viewport)                 |   Ingest,   |
|                                                           |   Model/LLM,|
|                                                           |   Rules)    |
|                                                           |             |
|                                                           |             |
+-------------------------------------------------------------------------+
|  [System Status]  ·  6 Nodes · 6 Edges  ·  neo4j online                 |  <- Clean Footer
+-------------------------------------------------------------------------+
```

1.  **Eliminate the Left Sidebar entirely**:
    *   Move **Ingest** to a main overlay modal or a dedicated starting state. When the graph is empty, show a spacious, beautiful Google-style dropzone.
    *   Move **Enrichment/Pending Facts** into a contextual tray or review drawer that slides up from the bottom when new implicit facts are generated.
    *   Move **Construct (Add Node/Edge)** to a floating, minimalist toolbar directly on the `GraphCanvas` (similar to Figma or Google Maps).
2.  **Consolidate the Right Sidebar**:
    *   Group the 9 scattered tabs into **3 logical, high-level control tabs**:
        1.  `Model` (Combines Chat, Smart Agent, and Reasoning controls like spread/infer)
        2.  `Query & Rules` (Combines Structured queries, pathfinders, and rule editing)
        3.  `Schema` (Combines the Ontology class list and raw Triple store tables)
3.  **Collapsible Panel Drawer**:
    *   Add a single, smooth transition collapse button (`PanelRightClose` / `PanelRightOpen`) with micro-animations from `motion/react` to allow the user to go full-screen with the graph instantly.

---

### Phase B: Header and Footer Restructuring

1.  **Header Decluttering**:
    *   Remove all raw connection state text and badge colors from the top bar.
    *   Keep the header simple: Brand Name/Logo on the left, a dropdown to switch active graphs, a primary "Run Neurosymbolic Loop" action button in the center-right, and an "Agent Settings" gear icon on the far right.
2.  **System Status Footer**:
    *   Create a thin (24px) footer at the very bottom of the screen.
    *   Render the database counts (Nodes, Edges, Rules) and connection states in a small, low-contrast, muted monospace font (`font-mono text-[10px] text-zinc-500`). This keeps the data accessible to developers without cluttering the main workspace.

---

### Phase C: Typography, Color, and Styling Polish

1.  **Unified Color Palette**:
    *   Backgrounds: `bg-zinc-950` (Canvas/Body) and `bg-zinc-900/50` (Sidebar) to create depth.
    *   Borders: Standardize on a ultra-thin, low-contrast border (`border-zinc-800/80`).
    *   Accents: Replace wild colored badges with a single elegant accent color (such as a clean, soft indigo/blue `text-indigo-400 bg-indigo-500/10` or white borders).
2.  **Typography Overhaul**:
    *   Set primary interface typography to **Inter** with medium tracking and weight.
    *   Use **Space Grotesk** or **Outfit** for clean, modern displaying headers.
    *   Use **JetBrains Mono** only in specific code contexts: raw URIs, rule logic, Sparql queries, and footer telemetry.

---

### Phase D: Interactive Canvas Enhancements

1.  **Floating Control Overlay**:
    *   Place a small, floating glassmorphic panel in the bottom-left of the canvas.
    *   Include controls for: Zoom In, Zoom Out, Reset Layout, Toggle Heatmap, and Toggle Proof Paths.
2.  **Contextual Node Inspector (Floating Card)**:
    *   Instead of editing node properties inside a sidebar, show a beautifully styled floating card next to the selected node on the canvas.
    *   This keeps the user's eyes on the visual graph while modifying properties.

---

## 4. Architectural Implementation Strategy

To implement these changes without breaking any of the existing backend API integrations, we can perform targeted modifications in `frontend/src/App.tsx` and consolidate existing components:

*   **Step 1**: Update `App.tsx` layout grids to remove the dual-sidebar structure and introduce the single right-hand contextual sidebar and minimalist footer.
*   **Step 2**: Reorganize existing components (`IngestPanel`, `LlmPanel`, `ReasoningPanel`, `QueryPanel`, etc.) into the new unified tab hierarchy.
*   **Step 3**: Extract floating canvas controls from the sidebar and render them as an overlay on the `GraphCanvas` component.
*   **Step 4**: Verify compile status and test performance using the integrated compiler.

This roadmap will instantly elevate the product, shifting it from a dense developer prototype to a highly refined, premium AI enterprise application.
