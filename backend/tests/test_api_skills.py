"""REST surface for the real runtime skills (PLAN.md §13.2), so the
SkillManager frontend component can list/load/activate skills the same way
mcp_skills_server.py does for MCP clients -- both wrap the same
agents/skill_store.py + services/skill_activation_store.py.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings
from db.neo4j_client import Neo4jClient


def _neo4j_reachable() -> bool:
    client = Neo4jClient(get_settings())
    try:
        client.verify()
        return True
    except Exception:
        return False
    finally:
        client.close()


def _cleanup_activation() -> None:
    client = Neo4jClient(get_settings())
    client.run("MATCH (s:ActiveSkill {name: 'kg-extraction'}) DETACH DELETE s")
    client.close()


def test_get_skills_lists_the_real_backend_skills_with_inactive_by_default():
    if not _neo4j_reachable():
        return
    with TestClient(app) as client:
        resp = client.get("/skills")
    assert resp.status_code == 200
    body = resp.json()
    names = {s["name"] for s in body["skills"]}
    assert "kg-extraction" in names
    kg_extraction = next(s for s in body["skills"] if s["name"] == "kg-extraction")
    assert kg_extraction["active"] is False
    assert kg_extraction["description"]


def test_get_skill_content_returns_the_real_skill_md_body():
    with TestClient(app) as client:
        resp = client.get("/skills/kg-extraction/content")
    assert resp.status_code == 200
    assert len(resp.json()["content"]) > 0


def test_get_skill_content_404s_for_unknown_skill():
    with TestClient(app) as client:
        resp = client.get("/skills/no-such-skill/content")
    assert resp.status_code == 404


def test_activate_skill_persists_real_active_state_visible_in_get_skills():
    if not _neo4j_reachable():
        return
    try:
        with TestClient(app) as client:
            activate_resp = client.post("/skills/kg-extraction/activate")
            assert activate_resp.status_code == 200
            assert activate_resp.json()["active"] is True

            list_resp = client.get("/skills")
            kg_extraction = next(s for s in list_resp.json()["skills"] if s["name"] == "kg-extraction")
            assert kg_extraction["active"] is True
    finally:
        _cleanup_activation()


def test_activate_skill_404s_for_unknown_skill():
    with TestClient(app) as client:
        resp = client.post("/skills/no-such-skill/activate")
    assert resp.status_code == 404
