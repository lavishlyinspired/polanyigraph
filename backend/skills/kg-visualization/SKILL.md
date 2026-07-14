---
name: kg-visualization
description: Use when a user asks to visualize, export, or get a visual/textual overview of the knowledge graph. Activates on visualization requests.
---

# Knowledge Graph Visualization

This agent cannot render an image — describe what a useful visualization
would show, in text, grounded in the graph's real content (real entity
types, real relationship types, real counts). Don't describe a generic or
hypothetical graph; describe *this* graph.

Useful things to call out: which entity types dominate (a natural coloring
axis in the real UI, which hashes type to color), which entities have the
most connections (natural focal points in a force-directed layout), and
whether any nodes are isolated (no edges at all — worth flagging, since an
isolated node is often a sign of a missed relationship during extraction).

If the graph has multiple detected communities (from Louvain community
detection, when available), describe them as the natural grouping a "color
by community" view would highlight, distinct from the type-based coloring.

When NOT to use: for a specific computed metric (centrality ranking,
similarity/classification results, community sizes) rather than a general
prose overview, that's `kg-analytics` instead.
