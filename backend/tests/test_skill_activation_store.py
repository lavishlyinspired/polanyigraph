"""Integration tests for backend/services/skill_activation_store.py against
live Neo4j. Real, persisted "active skill" state -- previously skills were
loaded fresh per-call with no concept of being active/inactive (PLAN.md §10
Skills MCP server's activate_skill tool needed a real definition of
"activation", not a no-op).
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import skill_activation_store


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    yield client
    client.run("MATCH (s:ActiveSkill) WHERE s.name STARTS WITH 'test-' DETACH DELETE s")
    client.close()


def test_activate_skill_persists_across_calls(neo4j):
    skill_activation_store.activate_skill(neo4j, name="test-kg-extraction")

    assert skill_activation_store.is_active(neo4j, name="test-kg-extraction") is True


def test_skill_is_inactive_by_default(neo4j):
    assert skill_activation_store.is_active(neo4j, name="test-never-activated") is False


def test_deactivate_skill_removes_active_state(neo4j):
    skill_activation_store.activate_skill(neo4j, name="test-kg-query")
    skill_activation_store.deactivate_skill(neo4j, name="test-kg-query")

    assert skill_activation_store.is_active(neo4j, name="test-kg-query") is False


def test_list_active_skills_returns_all_currently_active(neo4j):
    skill_activation_store.activate_skill(neo4j, name="test-a")
    skill_activation_store.activate_skill(neo4j, name="test-b")

    active = skill_activation_store.list_active_skills(neo4j)

    assert {"test-a", "test-b"}.issubset(active)


def test_activate_skill_is_idempotent(neo4j):
    skill_activation_store.activate_skill(neo4j, name="test-idempotent")
    skill_activation_store.activate_skill(neo4j, name="test-idempotent")

    active = skill_activation_store.list_active_skills(neo4j)
    assert list(active).count("test-idempotent") == 1
