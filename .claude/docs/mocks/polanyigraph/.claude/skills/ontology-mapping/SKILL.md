---
name: ontology-mapping
description: Use when working with the ontology layer - loading RDF/OWL from Ontotext GraphDB via SPARQL, deriving the domain-agnostic type vocabulary, or mapping extracted instances to ontology classes. Keeps the product domain-agnostic.
---

# Ontology Mapping (GraphDB / RDF / SPARQL)

## When to use
Any work on `backend/ontology/*`, `backend/db/graphdb_client.py`, or anything that
decides "what types exist".

## Principles
1. **GraphDB is the symbolic layer.** Ontotext GraphDB holds the ontology (TBox)
   as RDF/OWL. Neo4j holds instances (ABox) + activation. Do not duplicate the
   ontology into code.
2. **The repository IS the domain.** `Settings.graphdb_repository` selects the
   ontology (`fibo` today; could be any OWL). All type/relationship knowledge is
   queried, never hardcoded.
3. **SPARQL for discovery.** Use `GraphDBClient.select`. Classes come from
   `owl:Class`; properties from `owl:ObjectProperty`/`owl:DatatypeProperty`.
4. **Graceful labels.** When `rdfs:label` is missing, fall back to the IRI local
   name (see `_local_name`).

## Definition of done
- `load_schema` returns non-empty classes for the configured repo.
- Changing `repositoryId` changes the vocabulary with no code edit.
- No SPARQL query assumes FIBO-specific IRIs.
