---
name: neurosymbolic-reasoning
description: Use when explaining neurosymbolic reasoning results (spread activation, derived facts, proof paths) to a user. Activates on reasoning requests.
---

# Neurosymbolic Reasoning

Reasoning here is a persistent-activation loop: activation spreads from a
source entity through real relationships (decaying per hop, weighted by
edge weight and node salience), a symbolic rule fires when an entity's
activation crosses that rule's threshold, and the resulting derived fact
feeds back into activation for the next iteration — not a single one-shot
inference pass.

When explaining a derived fact, cite its actual proof path: which rule
fired, over which real edge, at what activation level. If the proof path
shows a `type_resolution` (the rule matched via an ontology subclass, e.g.
"commercial bank" satisfying a rule written for "organization"), mention
this explicitly — it's often the most informative part of the explanation,
since it shows the reasoning generalized correctly rather than requiring an
exact type match.

Report whether the loop converged by fixpoint (stabilized) or hit
max_iterations (didn't stabilize in the allotted budget) — these mean
different things and a user asking "why didn't more facts get derived"
deserves the honest one, not a vague "reasoning complete."
