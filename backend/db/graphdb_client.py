"""Ontotext GraphDB client — the ontology (RDF/OWL) + SPARQL layer.

This is the symbolic half of the neurosymbolic system and the reason the product
is domain-agnostic: the set of valid entity types and relationships is read from
whatever ontology is loaded into the configured repository, via SPARQL. No domain
is baked into the code.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings

SPARQL_SELECT_ACCEPT = "application/sparql-results+json"


class GraphDBClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._endpoint = settings.graphdb_sparql_endpoint
        auth = None
        if settings.profile == "cloud" and settings.ontotext_db_username_cloud:
            auth = (settings.ontotext_db_username_cloud, settings.ontotext_db_password_cloud)
        self._client = httpx.Client(timeout=30.0, auth=auth)

    def close(self) -> None:
        self._client.close()

    def verify(self) -> bool:
        rows = self.select("ASK-STYLE probe", probe=True)
        return rows is not None

    def select(self, query: str, *, probe: bool = False) -> list[dict[str, Any]]:
        """Run a SPARQL SELECT and return the bindings as plain dicts."""
        q = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1" if probe else query
        resp = self._client.post(
            self._endpoint,
            data={"query": q},
            headers={"Accept": SPARQL_SELECT_ACCEPT},
        )
        resp.raise_for_status()
        payload = resp.json()
        bindings = payload.get("results", {}).get("bindings", [])
        return [{k: v.get("value") for k, v in row.items()} for row in bindings]
