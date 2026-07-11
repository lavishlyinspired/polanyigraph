"""Neo4j (LPG) client — the instance graph + reasoning + visualization store.

Thin wrapper around the official driver. Domain-agnostic: it stores whatever
nodes/edges extraction produces; node labels come from the loaded ontology, not
from any hardcoded schema.
"""

from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase, Driver

from app.config import Settings


class Neo4jClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._driver: Driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def verify(self) -> bool:
        self._driver.verify_connectivity()
        return True

    def run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        with self._driver.session(database=self._settings.neo4j_database) as session:
            result = session.run(cypher, **params)
            return [record.data() for record in result]
