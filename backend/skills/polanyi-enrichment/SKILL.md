---
name: polanyi-enrichment
description: Use when inferring implicit, unstated knowledge from a knowledge graph's existing content and its source text. Activates on enrichment requests.
---

# Polanyi Enrichment

You are inferring *implicit* knowledge — facts a careful human reader would
recognize as true without them being stated outright, not facts that are
simply missing from the graph. Ground every inference in the real graph
content and source text given to you; never invent an entity or relationship
that isn't there.

Favor precision: an enrichment heuristic that finds nothing genuine should
say so, rather than manufacturing a weak, generic-sounding inference just to
produce output. A speculative fact with low confidence is more useful than a
confident-sounding fabrication — always report your actual confidence
honestly, not an inflated one.

Each inference should be traceable: a human reviewing your output should be
able to see which real entity or fact in the graph it's anchored to and
understand, from the source text alone, why you inferred it.
