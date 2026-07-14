---
name: kg-query
description: Use when answering a structured query or formatting query results from the knowledge graph for a user. Activates on query requests.
---

# Knowledge Graph Query

The query language is `predicate(subject, object)` — quoted literals or
capitalized variables (X, Y, Z), joined conjunctively with commas across
multiple atoms.

If a natural-language question was translated into this DSL before running
(see "Query run:" in the data above), state the query that actually ran,
then the results — this is the primary way a user learns the DSL, grounded
in their own real question rather than an abstract syntax description.
Explaining the syntax in the abstract is a last resort only: use it when no
translated query is present and the user seems to be asking in natural
language directly (nothing was run for them yet).

When formatting results: state how many rows were found. Distinguish a
**base fact** (directly stored, from real extraction or manual entry) from a
**derived fact** (produced by the reasoning engine) — these carry different
epistemic weight and a user should know which they're looking at. Report the
confidence for derived facts; base facts don't need one unless it's
meaningfully below 1.0.

An empty result set is a valid, informative answer — say plainly that
nothing matched, and suggest checking the predicate/entity names against
what's actually in the graph rather than assuming the query itself is wrong.
