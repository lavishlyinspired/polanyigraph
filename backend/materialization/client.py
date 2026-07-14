"""GraphClient: the one seam a second graph-database backend would
implement (PLAN Phase 3 design doc's "Storage Adapter Pattern").
Neo4jGraphClient is the only real implementation -- per the user's
explicit 2026-07-14 sequencing decision, this does not retrofit the ~42
other Neo4j-coupled files in this backend; it exists so the Materialization
Engine's new write path (SET_PROPERTY for PROPERTY-materialized values)
doesn't hardcode Cypher inline in services/ingest_service.py, and so a
second backend is an additive adapter later, not a rewrite.

SET_PROPERTY writes into the entity's existing "arbitrary user-defined
key-value pairs" mechanism (services/graph_service.py's propertiesJson ->
GraphNodeRecord.properties) rather than a raw dynamic Neo4j field, so an
inlined value flows through get_graph() and the frontend the same way any
other entity property already does -- reusing an existing seam instead of
inventing a second, parallel one.
"""

from __future__ import annotations

import json
from typing import Protocol

from db.neo4j_client import Neo4jClient
from materialization.commands import StorageCommand


class GraphClient(Protocol):
    def execute(self, command: StorageCommand) -> None: ...


class Neo4jGraphClient:
    def __init__(self, neo4j: Neo4jClient, *, graph_id: str) -> None:
        self._neo4j = neo4j
        self._graph_id = graph_id

    def execute(self, command: StorageCommand) -> None:
        if command.operation != "SET_PROPERTY":
            raise ValueError(f"Neo4jGraphClient does not yet support operation: {command.operation!r}")
        rows = self._neo4j.run(
            "MATCH (e:Entity {id: $id, graphId: $graph_id}) RETURN coalesce(e.propertiesJson, '{}') AS propertiesJson",
            id=command.subject_id,
            graph_id=self._graph_id,
        )
        existing = json.loads(rows[0]["propertiesJson"]) if rows else {}
        existing[command.key] = command.value
        self._neo4j.run(
            "MATCH (e:Entity {id: $id, graphId: $graph_id}) SET e.propertiesJson = $properties_json",
            id=command.subject_id,
            graph_id=self._graph_id,
            properties_json=json.dumps(existing),
        )
