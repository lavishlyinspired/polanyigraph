"""Mirror the ontology's shape into Neo4j as constraints/indexes.

Domain-agnostic by design: rather than one Neo4j node label per ontology class
(which would explode into thousands of labels for an ontology like FIBO, and
collide after sanitizing labels like "joint stock company"), every extracted
instance is a single ``:Entity`` node with a free-text ``type`` property holding
the ontology class label. Relationships are similarly a single ``:RELATES`` type
with a ``type`` property. This is exactly the shape `reasoning.engine.Node`/`Edge`
expect (``type: str`` compared against ``Rule.source_type``/``edge_type``), and it
means swapping the GraphDB repository swaps the domain with zero Neo4j schema
changes — there is no per-domain migration to write.
"""

from __future__ import annotations

from db.neo4j_client import Neo4jClient

CONSTRAINT_NAMES = {"entity_id_unique", "derived_fact_id_unique"}

_STATEMENTS = [
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
    "FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT derived_fact_id_unique IF NOT EXISTS "
    "FOR (f:DerivedFact) REQUIRE f.id IS UNIQUE",
    "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
    "CREATE INDEX entity_graph_idx IF NOT EXISTS FOR (e:Entity) ON (e.graphId)",
    "CREATE INDEX relates_type_idx IF NOT EXISTS FOR ()-[r:RELATES]-() ON (r.type)",
]


def ensure_constraints(neo4j: Neo4jClient) -> None:
    """Idempotent: safe to call on every backend startup."""
    for statement in _STATEMENTS:
        neo4j.run(statement)
