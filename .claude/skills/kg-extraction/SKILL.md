---
name: kg-extraction
description: Use when implementing or changing knowledge-graph extraction (text -> entities/relationships) in this repo. Domain-agnostic - entity types come from the loaded ontology (GraphDB), never hardcoded. Follows TDD.
---

# Knowledge-Graph Extraction

## When to use
Any work on `backend/extraction/*` or the `/ingest` endpoint.

## Non-negotiables
1. **Domain-agnostic.** Never hardcode entity/relationship types. Read them from
   the `OntologySchema` (`backend/ontology/loader.py`) for the configured GraphDB
   repository. Swapping the repo must swap the vocabulary with zero code changes.
2. **Real LLM only.** Use `llm.client.LLMClient` (OpenAI-compatible, NVIDIA GLM by
   default). No keyword mocks in the running path. An offline extractor may exist
   only behind an explicit, labeled dev flag.
3. **Provenance.** Every extracted node/edge records `source_doc` (and char span
   when available). Nothing unattributable enters Neo4j.
4. **TDD.** Write a failing test in `backend/tests/test_extraction.py` first, using
   a small real text fixture. Assert entities exist and are ontology-typed.

## Flow
`text -> chunk -> LLM structured output -> validate against OntologySchema ->
dedupe (exact + case-insensitive) -> MERGE into Neo4j with provenance`.

## Definition of done
- Extracted types all satisfy `OntologySchema.is_known_type`.
- Re-ingesting the same doc is idempotent (MERGE, not CREATE).
- Test passes without network by injecting a fake `LLMClient`.
