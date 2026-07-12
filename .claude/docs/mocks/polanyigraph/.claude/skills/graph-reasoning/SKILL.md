---
name: graph-reasoning
description: Use when writing Cypher/graph-service code against Neo4j or SPARQL against GraphDB - reads, writes, constraints, and the structured triple query. Keeps the two-store split clean and queries parameterized.
---

# Graph Reasoning (Neo4j Cypher + GraphDB SPARQL)

## When to use
Work on `backend/services/graph_service.py`, `backend/db/*`, or `/graph` `/query`.

## Two-store discipline
- **Neo4j (LPG):** instances, activation, derived facts, visualization. Use
  `Neo4jClient.run` with **parameterized** Cypher (never string-interpolate input).
- **GraphDB (RDF):** ontology + SPARQL. Use `GraphDBClient.select`.
- Do not run instance reasoning in GraphDB or store the ontology in Neo4j.

## Query surface (MVP)
Structured triple query `predicate(subject, object)` runs over stored + derived
triples. Variables are `X`/`Y`/`Z`/`_`; literals match case-insensitively.
NL -> Cypher is deferred to v1 — do not add it to the MVP.

## Definition of done
- All Cypher is parameterized; a test proves injection-style input is inert.
- `MERGE` (idempotent) for writes; constraints created via a migration.
- Derived facts are queryable alongside stored edges.
