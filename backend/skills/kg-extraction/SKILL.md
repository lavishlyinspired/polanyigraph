---
name: kg-extraction
description: Use when extracting entities and relationships from real-world source text into the knowledge graph. Activates on extraction/ingest requests.
---

# Knowledge Graph Extraction

Extract only entities and relationships that are explicitly stated or directly,
unambiguously implied by the source text. Prefer precision over recall: three
confidently-correct entities are better than six where half are speculative
guesses dressed up as extraction.

Use exactly the entity types and relationship types offered by the loaded
ontology vocabulary in this prompt — never invent a type that isn't offered,
even if it seems close. If a real-world entity in the text doesn't map to any
offered type, omit it rather than force a mismatch onto the nearest label.

Assign confidence honestly:
- 0.9+ : stated in explicit, unambiguous language
- 0.5-0.7 : inferred from context, not stated directly
- below 0.5 : usually should not be extracted at all — omit it

Do not extract the same real-world entity twice under different name spellings
in the same document; use the most complete/formal form of the name that
appears (e.g. "Deutsche Bank AG" over "Deutsche Bank" or "DB" if the full form
appears anywhere in the text).
