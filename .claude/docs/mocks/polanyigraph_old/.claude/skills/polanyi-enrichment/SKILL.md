---
name: polanyi-enrichment
description: Use when implementing or changing the 11-heuristic implicit-knowledge enrichment layer (backend/enrichment/heuristics/) - presuppositions, implicatures, factual impact, image schemas, metonymic/moral-value/symbolic coercion, event sequences, causal relations, implied future/non-events. Enforces PLAN.md section 19.
---

# Polanyi Enrichment (PLAN.md §19)

## When to use
Any work on `backend/enrichment/`, `services/enrichment_service.py`, or the `/enrich` endpoint.

## Non-negotiables
1. **Domain-agnostic, all 11 together.** The heuristics are general cognitive/pragmatic
   categories (presupposition, implicature, causal relation, ...), not domain-specific.
   Do not filter by "is this relevant to the current domain" — a legal contract has
   causal relations exactly like a financial filing does. Ship all 11, never a subset.
2. **Base Graph = existing extraction.** Do not build or depend on AMR/SPRING/AMR2FRED/
   BLINK/eWiSeR/DOLCE. The already-extracted, ontology-typed `:Entity`/`:RELATES` graph
   *is* the Base Graph the heuristics run against (see §19.3 for why the full paper's
   AMR/FRED pipeline is redundant with what this project already has).
3. **`:ImplicitFact`, not `:Entity`/`:DerivedFact`.** Enriched facts are a third,
   distinct provenance layer: `(:ImplicitFact {heuristicType, text, confidence})
   -[:ANCHORED_TO]->(:Entity)`. `heuristicType` is validated against the fixed
   11-category enum (Polanyi's own typology), not the swappable domain ontology.
4. **Prompt structure per heuristic** (§19.5, matches the paper's own §3.3.2): role
   ("expert ontology engineer") + input format (Base Graph subset + source text) +
   heuristic definition + few-shot examples (from the paper, §3.2) + output format
   (new assertions only, each naming anchor node(s) + confidence + heuristic type).
5. **Real LLM only.** No canned/templated enrichment output — matches every other
   real-data-only path in this codebase.
6. **Human-in-the-loop before merge.** Pending `:ImplicitFact` assertions are approved
   or rejected before they're queryable, per §7.3.

## Where to start
Per §19.6: shared `enrichment/heuristics/base.py` + `services/enrichment_service.py`
first. Then **Causal Relations** as the first concrete heuristic (clearest few-shot
examples in the paper, composes naturally with the reasoning engine). Prove the
pattern once, then the remaining 10 are mechanical repetition, not 10 new designs.

**[DONE]** All 11 heuristics implemented (`enrichment/heuristics/*.py`), registered
in `ALL_HEURISTIC_MODULES`, orchestrated by `services/enrichment_service.
run_all_heuristics()`, exposed via `POST /enrich/{graphId}` (+
pending/approved/approve/reject). Live-verified running together against a real
graph. Only the frontend (`UI_PLAN.md` §9.3, an `EnrichmentPanel.tsx` with
approve/reject) remains.

**Known limitation found via live verification, not tests**: sparse/subjective
heuristics (confirmed for `symbolic_coercion`) can over-generate speculative,
low-confidence facts on scenarios where the heuristic doesn't really apply,
rather than correctly returning empty. This is exactly what the pending/approve
human-in-the-loop step exists to catch — don't try to prompt-engineer this away
per-heuristic; build the review UI instead.

## Definition of done
- Each heuristic module: real graph + real source text in, real LLM call (fake in
  unit tests, per this repo's convention), asserts an `:ImplicitFact` anchored to a
  real node with a valid `heuristicType`.
- No heuristic silently no-ops on a domain it "doesn't apply to" — all 11 run on
  every graph.
