"""MCP server (PLAN.md §10 MCP Layer, 2nd of the 4 originally-sketched
servers): direct Neo4j graph access -- get_schema, read_cypher, write_cypher
-- for any MCP client. Hand-rolled against this project's own Neo4jClient,
not an external "official Neo4j MCP" package, per the same "rebuild
natively" convention as mcp_server.py (the Custom KG MCP server).

Run: `python mcp_neo4j_server.py` (stdio transport), or configure this as a
separate MCP server entry in a client's config.
"""

from __future__ import annotations

import json
import re

from mcp.server.fastmcp import FastMCP

from app.dependencies import get_neo4j

mcp = FastMCP("neo4j")

# Rejects obvious write clauses in read_cypher -- a real, if not bulletproof,
# safeguard: keyword match on Cypher's actual write clauses, not just a
# substring check, so "MATCH (n) WHERE n.label = 'CREATE'" still passes.
_WRITE_CLAUSE_RE = re.compile(
    r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP|DETACH)\b", re.IGNORECASE
)


@mcp.tool()
def get_schema() -> str:
    """Real, live Neo4j graph schema: node labels, relationship types, and
    property keys currently present in the database (not the domain
    ontology -- see the Custom KG MCP server's ontology://schema resource
    for that)."""
    neo4j = get_neo4j()
    labels = [r["label"] for r in neo4j.run("CALL db.labels() YIELD label RETURN label ORDER BY label")]
    rel_types = [
        r["relationshipType"]
        for r in neo4j.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType")
    ]
    prop_keys = [
        r["propertyKey"] for r in neo4j.run("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey ORDER BY propertyKey")
    ]
    return (
        "Node labels:\n" + "\n".join(f"- {l}" for l in labels)
        + "\n\nRelationship types:\n" + "\n".join(f"- {r}" for r in rel_types)
        + "\n\nProperty keys:\n" + "\n".join(f"- {p}" for p in prop_keys)
    )


@mcp.tool()
def read_cypher(cypher: str) -> str:
    """Run a real read-only Cypher query against Neo4j and return the results
    as JSON. Write clauses (CREATE, MERGE, DELETE, SET, REMOVE, DROP,
    DETACH) are rejected -- use write_cypher for those."""
    if _WRITE_CLAUSE_RE.search(cypher):
        return "Rejected: read_cypher is read-only. Write clauses are not allowed here -- use write_cypher."
    rows = get_neo4j().run(cypher)
    if not rows:
        return "No results."
    return json.dumps(rows, default=str)


@mcp.tool()
def write_cypher(cypher: str) -> str:
    """Run a real write Cypher query (CREATE, MERGE, SET, DELETE, etc.)
    against Neo4j. Returns how many rows the query returned."""
    rows = get_neo4j().run(cypher)
    return f"Query executed. {len(rows)} row(s) returned."


if __name__ == "__main__":
    mcp.run()
