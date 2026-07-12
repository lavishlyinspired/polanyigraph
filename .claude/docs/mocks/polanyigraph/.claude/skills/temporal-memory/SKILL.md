---
name: temporal-memory
description: Use when implementing or changing provenance linking, bi-temporal fact validity, evolving entity summaries, or chat session memory (backend/services/graph_service.py, chat_service.py, history_service.py). Enforces PLAN.md section 20 (Graphiti/Zep-inspired, rebuilt natively - no dependency on graphiti-core or the Zep API).
---

# Temporal Memory Layer (PLAN.md §20)

## When to use
Any work on fact contradiction/invalidation, `:IngestEvent` provenance linking,
`:Entity.summary`, or `POST /chat` session history.

## Non-negotiables
1. **Rebuild natively, no dependency.** This is a from-scratch reimplementation of
   Graphiti's/Zep's concepts against this project's own Neo4j — not a pip dependency
   on `graphiti-core`, not a call to the Zep hosted API, even though `zep_API_KEY`
   exists in `.env`. See §20.1/§20.6 for why.
2. **Bi-temporal, not overwrite.** `upsert_entity`/`upsert_relationship` currently do
   a blind `MERGE ... SET` — a second ingest asserting a contradicting fact silently
   destroys the old value. Fix: on contradiction (same subject + edge type, different
   target), set `invalidAt` on the old `:RELATES` edge instead of overwriting it.
   Old facts stay queryable ("what was true as of doc N"), mirroring Graphiti's
   `EntityEdge.valid_at`/`invalid_at`/`expired_at`.
3. **Provenance is a graph traversal, not a string match.** `:IngestEvent` already
   exists (real, shipped) but isn't linked to what it produced. Add
   `IngestEvent-[:PRODUCED]->Entity`/`RELATES` so "which document said this" is a
   real query, not `sourceDoc` string comparison.
4. **Entity summaries evolve, they don't get replaced.** `:Entity.summary` should
   accumulate context across ingests via a real LLM call each time a new episode
   references that entity — mirrors `EntityNode.summary` in Graphiti.
5. **Chat gets session memory.** `POST /chat` is currently stateless (rebuilds full
   context every call, no memory of prior turns). Add `:ChatSession`/`:ChatMessage`
   nodes; each turn appends and reads recent history alongside the existing
   graph-grounded context (`chat_service.py` stays the grounding mechanism — this
   only adds conversation continuity on top).
6. **Community detection is deferred**, not part of this skill's scope (§20.4 item 5,
   §20.6) — lowest priority, speculative value for this product's actual usage
   pattern (single-analyst exploration, not large multi-user social graphs).

## Where to start
Per §20.5: provenance linking + bi-temporal facts first (items 1–2) — smallest slice,
fixes a real correctness bug in already-shipped code, and establishes one provenance
pattern before Polanyi enrichment's `:ImplicitFact` needs its own.

## Definition of done
- A second ingest that contradicts an earlier fact invalidates (not overwrites) the
  old edge; both are queryable with their validity windows.
- Every `:Entity`/`:RELATES` traces back to the real `:IngestEvent` that produced it
  via a graph relationship, not a label match.
