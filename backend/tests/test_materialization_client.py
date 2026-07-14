"""Integration tests for materialization/client.py's Neo4jGraphClient
against live Neo4j (PLAN Phase 3 design doc's "Storage Adapter Pattern" --
the one seam a second graph-database backend would implement; only
Neo4jGraphClient is real today, per the user's explicit 2026-07-14
sequencing decision not to retrofit the rest of this backend)."""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from materialization.client import Neo4jGraphClient
from materialization.commands import StorageCommand
from services import graph_service


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    yield client, graph_id
    client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    client.close()


def test_set_property_writes_into_the_entitys_existing_properties_json(neo4j):
    """Reuses graph_service.py's own "arbitrary user-defined key-value
    pairs" mechanism (propertiesJson -> GraphNodeRecord.properties) rather
    than a raw dynamic Neo4j property, so an inlined value flows through
    get_graph() and the frontend the same way any other entity property
    already does."""
    client, graph_id = neo4j
    graph_service.upsert_entity(
        client, graph_id=graph_id, entity_id="hub", label="HDFC Bank", type_="organization",
        source_doc="d", extraction_confidence=1.0,
    )
    graph_client = Neo4jGraphClient(client, graph_id=graph_id)

    graph_client.execute(StorageCommand(operation="SET_PROPERTY", subject_id="hub", key="reports", value="8.45%"))

    record = graph_service.get_graph(client, graph_id)
    hub = next(n for n in record.nodes if n.id == "hub")
    assert hub.properties["reports"] == "8.45%"


def test_set_property_merges_with_existing_properties_rather_than_replacing_them(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(
        client, graph_id=graph_id, entity_id="hub", label="HDFC Bank", type_="organization",
        source_doc="d", extraction_confidence=1.0,
    )
    graph_service.update_entity_metadata(client, graph_id=graph_id, entity_id="hub", properties={"lei": "ABC123"})
    graph_client = Neo4jGraphClient(client, graph_id=graph_id)

    graph_client.execute(StorageCommand(operation="SET_PROPERTY", subject_id="hub", key="reports", value="8.45%"))

    record = graph_service.get_graph(client, graph_id)
    hub = next(n for n in record.nodes if n.id == "hub")
    assert hub.properties == {"lei": "ABC123", "reports": "8.45%"}


def test_set_property_only_touches_the_named_subject(neo4j):
    client, graph_id = neo4j
    for eid in ("a1", "a2"):
        graph_service.upsert_entity(
            client, graph_id=graph_id, entity_id=eid, label=eid, type_="organization",
            source_doc="d", extraction_confidence=1.0,
        )
    graph_client = Neo4jGraphClient(client, graph_id=graph_id)

    graph_client.execute(StorageCommand(operation="SET_PROPERTY", subject_id="a1", key="rate", value="8.45%"))

    record = graph_service.get_graph(client, graph_id)
    a2 = next(n for n in record.nodes if n.id == "a2")
    assert a2.properties == {}


def test_set_property_is_scoped_to_graph_id(neo4j):
    """Same entity id in a different graphId must not be touched --
    matches graph_service.py's own graphId-scoping discipline."""
    client, graph_id = neo4j
    other_graph_id = f"test-{uuid.uuid4().hex[:8]}"
    graph_service.upsert_entity(
        client, graph_id=other_graph_id, entity_id="hub", label="Other Hub", type_="organization",
        source_doc="d", extraction_confidence=1.0,
    )
    graph_client = Neo4jGraphClient(client, graph_id=graph_id)  # different graph_id, entity doesn't exist here

    graph_client.execute(StorageCommand(operation="SET_PROPERTY", subject_id="hub", key="rate", value="8.45%"))

    record = graph_service.get_graph(client, other_graph_id)
    hub = next(n for n in record.nodes if n.id == "hub")
    assert hub.properties == {}
    client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=other_graph_id)


def test_unsupported_operation_raises():
    graph_client = Neo4jGraphClient(None, graph_id="x")  # no Neo4j call reached for an unsupported op

    with pytest.raises(ValueError):
        graph_client.execute(StorageCommand(operation="CREATE_EDGE", subject_id="a"))
