"""Integration tests for backend/services/preferences_store.py against live
Neo4j. Global, not graph-scoped -- a preference (e.g. "default_repository",
"auto_run_reasoning") is an app-level setting shared across graphs, same
convention as services/rules_store.py's custom rules. Backs the Memory MCP
server's save_preference tool (PLAN.md §10, no general preferences
mechanism previously existed).
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import preferences_store


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    yield client
    client.close()


def _key() -> str:
    return f"test-pref-{uuid.uuid4().hex[:8]}"


def test_save_and_get_preference(neo4j):
    key = _key()
    try:
        preferences_store.save_preference(neo4j, key=key, value="dark-mode")
        assert preferences_store.get_preference(neo4j, key=key) == "dark-mode"
    finally:
        preferences_store.delete_preference(neo4j, key=key)


def test_save_preference_overwrites_existing_value(neo4j):
    key = _key()
    try:
        preferences_store.save_preference(neo4j, key=key, value="first")
        preferences_store.save_preference(neo4j, key=key, value="second")
        assert preferences_store.get_preference(neo4j, key=key) == "second"
    finally:
        preferences_store.delete_preference(neo4j, key=key)


def test_get_preference_returns_none_when_unset(neo4j):
    assert preferences_store.get_preference(neo4j, key="no-such-preference-key") is None


def test_list_preferences_returns_all_saved(neo4j):
    key1, key2 = _key(), _key()
    try:
        preferences_store.save_preference(neo4j, key=key1, value="a")
        preferences_store.save_preference(neo4j, key=key2, value="b")

        prefs = preferences_store.list_preferences(neo4j)

        by_key = {p.key: p.value for p in prefs}
        assert by_key[key1] == "a"
        assert by_key[key2] == "b"
    finally:
        preferences_store.delete_preference(neo4j, key=key1)
        preferences_store.delete_preference(neo4j, key=key2)
