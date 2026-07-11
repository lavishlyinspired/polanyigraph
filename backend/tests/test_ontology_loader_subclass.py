"""Live-GraphDB test: the loader must capture the real rdfs:subClassOf edges
that make ontology-aware rule matching (ontology/schema.py build_subclass_matcher)
work against actual FIBO data, not just synthetic fixtures.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from ontology.loader import load_schema


def _graphdb_or_skip() -> GraphDBClient:
    settings = get_settings()
    client = GraphDBClient(settings)
    try:
        client.verify()
    except Exception:
        pytest.skip("GraphDB not reachable")
    return client


def test_loader_captures_real_subclass_edges():
    settings = get_settings()
    client = _graphdb_or_skip()
    schema = load_schema(client, settings.graphdb_repository)
    client.close()

    assert len(schema.subclass_of) > 0


def test_commercial_bank_is_a_organization_in_real_fibo():
    """Confirms the exact real-world case discovered via live browser testing:
    an extracted "commercial bank" entity should satisfy a rule expecting
    "organization" once ontology-aware matching is used."""
    settings = get_settings()
    client = _graphdb_or_skip()
    schema = load_schema(client, settings.graphdb_repository)
    client.close()

    matcher = schema.build_subclass_matcher()
    assert matcher("commercial bank", "organization") is True


def test_central_bank_is_a_regulatory_agency_in_real_fibo():
    settings = get_settings()
    client = _graphdb_or_skip()
    schema = load_schema(client, settings.graphdb_repository)
    client.close()

    matcher = schema.build_subclass_matcher()
    assert matcher("central bank", "regulatory agency") is True
