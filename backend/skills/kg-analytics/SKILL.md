---
name: kg-analytics
description: Use when a user asks a computed-metric question about the graph's structure -- which entities are most central/important/influential, or other graph analytics results. Activates on analytics requests.
---

# Knowledge Graph Analytics

Ground every statement in the real scores returned by the analytics engine,
listed below in the data you were given -- never invent a score, and never
present an estimate as if it were computed.

State the top entities by the requested metric with their actual numeric
scores, highest first. If the score list is empty, say plainly that the
graph has nothing to analyze (an empty graph), not that analytics failed.

When NOT to use: for a general prose overview of the graph's shape
(dominant entity types, informal connectivity, isolated nodes) with no
specific computed metric requested, that's `kg-visualization` instead.
