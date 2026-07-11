"""Tests for the ontology layer against the live local services.

These are integration tests by nature (SPARQL + Cypher have no useful pure-unit
substitute for "does this actually work against GraphDB/Neo4j"). They skip
cleanly when the local desktop services aren't running, per this repo's
no-mock-data policy: we verify against the real FIBO repository, not a fixture.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from ontology.loader import load_schema
from ontology.sync import CONSTRAINT_NAMES, ensure_constraints


def _graphdb_or_skip() -> GraphDBClient:
    settings = get_settings()
    client = GraphDBClient(settings)
    try:
        client.verify()
    except Exception:
        pytest.skip("GraphDB not reachable at " + settings.graphdb_sparql_endpoint)
    return client


def _neo4j_or_skip() -> Neo4jClient:
    settings = get_settings()
    client = Neo4jClient(settings)
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable at " + settings.neo4j_uri)
    return client


def test_load_schema_returns_real_ontology_classes():
    settings = get_settings()
    client = _graphdb_or_skip()
    schema = load_schema(client, settings.graphdb_repository)
    client.close()

    # No fixture, no fabricated classes: whatever is actually loaded in the
    # configured repository. For the fibo repo this is thousands of real
    # FIBO classes; the assertion only requires the pipeline works end to end.
    assert schema.repository == settings.graphdb_repository
    assert len(schema.classes) > 0
    assert all(c.label for c in schema.classes)


def test_is_known_type_is_case_insensitive():
    settings = get_settings()
    client = _graphdb_or_skip()
    schema = load_schema(client, settings.graphdb_repository)
    client.close()

    sample = schema.classes[0].label
    assert schema.is_known_type(sample.upper())
    assert not schema.is_known_type("definitely-not-a-real-ontology-class-xyz")


def test_ensure_constraints_is_idempotent():
    client = _neo4j_or_skip()
    try:
        ensure_constraints(client)
        ensure_constraints(client)  # must not raise on second run

        rows = client.run("SHOW CONSTRAINTS YIELD name RETURN name")
        names = {r["name"] for r in rows}
        assert CONSTRAINT_NAMES.issubset(names)
    finally:
        client.close()
