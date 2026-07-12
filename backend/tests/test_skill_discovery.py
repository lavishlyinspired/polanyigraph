"""Tests for agents/skill_discovery.py -- PLAN.md §18.4 acceptance criterion 5
in particular: with Neo4j unreachable, ResilientSkillDiscovery must degrade to
filesystem keyword matching rather than raise, so an agent turn still
completes (degraded discovery, no crash).
"""

from __future__ import annotations

import uuid

import pytest

from agents.skill_discovery import HybridSkillDiscovery, ResilientSkillDiscovery
from app.config import Settings, get_settings
from db.neo4j_client import Neo4jClient
from services import skill_graph_service


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    skill_graph_service.ensure_schema(client)
    skill_graph_service.seed_skills(client)
    yield client
    client.run("MATCH (u:SkillUsage) WHERE u.sessionId STARTS WITH 'test-' DETACH DELETE u")
    client.close()


@pytest.fixture
def unreachable_neo4j():
    """A real Neo4jClient pointed at a port nothing listens on -- simulates
    Neo4j being down mid-run, not a mock of the failure."""
    settings = Settings(neo4j_uri_desktop="bolt://localhost:1", profile="desktop")
    client = Neo4jClient(settings)
    yield client
    client.close()


def test_hybrid_get_catalog_lists_real_skills(neo4j):
    discovery = HybridSkillDiscovery(neo4j)
    catalog = discovery.get_catalog()
    assert "kg-extraction" in catalog


def test_hybrid_find_skills_delegates_to_neo4j(neo4j):
    discovery = HybridSkillDiscovery(neo4j)
    results = discovery.find_skills("extract entities and relationships from financial text")
    assert results[0].name == "kg-extraction"


def test_hybrid_load_skill_reads_real_file(neo4j):
    discovery = HybridSkillDiscovery(neo4j)
    content = discovery.load_skill("kg-extraction")
    assert "Knowledge Graph Extraction" in content


def test_hybrid_record_usage_updates_confidence(neo4j):
    discovery = HybridSkillDiscovery(neo4j)
    confidence = discovery.record_usage("kg-extraction", session_id=f"test-{uuid.uuid4().hex[:8]}", success=True)
    assert confidence is not None


def test_resilient_find_skills_falls_back_to_filesystem_when_neo4j_unreachable(unreachable_neo4j):
    discovery = ResilientSkillDiscovery(unreachable_neo4j)

    results = discovery.find_skills("extract entities and relationships from financial text")

    assert len(results) > 0
    assert any(r.name == "kg-extraction" for r in results)


def test_resilient_record_usage_does_not_raise_when_neo4j_unreachable(unreachable_neo4j):
    discovery = ResilientSkillDiscovery(unreachable_neo4j)

    result = discovery.record_usage("kg-extraction", session_id="test-degraded", success=True)  # must not raise

    assert result is None


def test_resilient_get_catalog_works_even_when_neo4j_unreachable(unreachable_neo4j):
    """The catalog is filesystem-only in both classes -- Neo4j being down
    should never affect it."""
    discovery = ResilientSkillDiscovery(unreachable_neo4j)
    catalog = discovery.get_catalog()
    assert "kg-extraction" in catalog


def test_resilient_load_skill_works_even_when_neo4j_unreachable(unreachable_neo4j):
    discovery = ResilientSkillDiscovery(unreachable_neo4j)
    content = discovery.load_skill("kg-extraction")
    assert "Knowledge Graph Extraction" in content
