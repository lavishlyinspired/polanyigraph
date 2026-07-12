---
name: neurosymbolic-reasoning
description: Use when implementing or changing the reasoning engine (spread activation + rule inference + feedback loop) in backend/reasoning/. Enforces the corrected PLAN.md section 8.4 semantics so the loop is real, not cosmetic.
---

# Neurosymbolic Reasoning (PLAN.md §8.4)

## When to use
Any work on `backend/reasoning/*` or the `/reason` endpoint.

## The rules (do NOT reintroduce the prototype's broken loop)
1. **Persistent activation.** Activation accumulates across iterations; feedback
   seeds the next spread. Never reset activation to 0 between rounds — that is the
   bug that made the prototype cosmetic.
2. **Directed + consistent.** Spread follows directed out-edges, matching how
   rules read edges. Neural and symbolic layers agree on direction.
3. **Fixpoint spread.** Max-activation relaxation to a fixpoint (order-independent),
   not a BFS sweep. There is a test asserting order-independence — keep it green.
4. **Honest convergence.** Stop on `(no new facts) AND (delta < epsilon)` -> report
   `fixpoint`; otherwise `max_iterations`. Never label a cap a fixpoint.
5. **One confidence calculus.** `confidence = activation(premise) * rule.weight`;
   along a proof chain it is the bounded product. This value flows to queries/UI.

## Definition of done
- `backend/tests/test_reasoning.py` passes, including the multi-hop test (a fact
  derivable only after feedback lifts an intermediate node past its threshold).
- Parameters (decay/epsilon/max_iterations) come from config, never magic numbers.
