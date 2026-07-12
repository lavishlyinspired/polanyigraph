"""Integration tests for services/skill_graph_service.py -- the Neo4j-backed
skill graph (PLAN.md §18/§2.9.14: Skill node schema, full-text discovery,
usage-tracked confidence). Real Neo4j, real skill files under backend/skills/.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
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


def test_seed_skills_creates_a_skill_node_per_real_runtime_skill(neo4j):
    rows = neo4j.run("MATCH (s:Skill) RETURN s.name AS name")
    names = {r["name"] for r in rows}
    assert "kg-extraction" in names
    assert "polanyi-enrichment" in names
    assert "neurosymbolic-reasoning" in names


def test_seed_skills_is_idempotent(neo4j):
    skill_graph_service.seed_skills(neo4j)  # run again
    rows = neo4j.run("MATCH (s:Skill {name: 'kg-extraction'}) RETURN count(s) AS c")
    assert rows[0]["c"] == 1


def test_seed_requires_edges_for_genuine_prerequisites(neo4j):
    rows = neo4j.run(
        "MATCH (s:Skill {name: 'polanyi-enrichment'})-[:REQUIRES]->(dep:Skill) RETURN dep.name AS name"
    )
    assert {r["name"] for r in rows} == {"kg-extraction"}


def test_find_relevant_skills_ranks_extraction_first_for_extraction_task(neo4j):
    results = skill_graph_service.find_relevant_skills(neo4j, "extract entities and relationships from financial text")
    assert len(results) > 0
    assert results[0].name == "kg-extraction"


def test_find_relevant_skills_includes_requires_chain(neo4j):
    results = skill_graph_service.find_relevant_skills(neo4j, "infer implicit unstated knowledge enrichment")
    enrichment = next((r for r in results if r.name == "polanyi-enrichment"), None)
    assert enrichment is not None
    assert "kg-extraction" in enrichment.requires


def test_find_relevant_skills_respects_limit(neo4j):
    results = skill_graph_service.find_relevant_skills(neo4j, "graph", limit=2)
    assert len(results) <= 2


def test_record_skill_usage_creates_usage_node_and_updates_confidence(neo4j):
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    new_confidence = skill_graph_service.record_skill_usage(
        neo4j, skill_name="kg-extraction", session_id=session_id, success=True, accuracy=0.9, tokens_used=1200,
    )
    assert new_confidence is not None

    rows = neo4j.run(
        "MATCH (u:SkillUsage {sessionId: $sid})-[:USED_SKILL]->(s:Skill {name: 'kg-extraction'}) "
        "RETURN u.success AS success, u.accuracy AS accuracy",
        sid=session_id,
    )
    assert len(rows) == 1
    assert rows[0]["success"] is True
    assert rows[0]["accuracy"] == 0.9


def test_record_skill_usage_confidence_is_rolling_average_of_successes(neo4j):
    skill_name = f"test-skill-{uuid.uuid4().hex[:8]}"
    neo4j.run("MERGE (s:Skill {name: $name}) SET s.confidence = 1.0", name=skill_name)

    skill_graph_service.record_skill_usage(neo4j, skill_name=skill_name, session_id=f"test-{uuid.uuid4().hex[:8]}", success=True)
    skill_graph_service.record_skill_usage(neo4j, skill_name=skill_name, session_id=f"test-{uuid.uuid4().hex[:8]}", success=False)
    final = skill_graph_service.record_skill_usage(neo4j, skill_name=skill_name, session_id=f"test-{uuid.uuid4().hex[:8]}", success=True)

    assert final == pytest.approx(2 / 3)
    neo4j.run("MATCH (s:Skill {name: $name}) DETACH DELETE s", name=skill_name)
