"""MCP server (PLAN.md §10 MCP Layer, 3rd of the 4 originally-sketched
servers): search_memory (wraps services/memory_service.py's real cross-source
search over chat history + entity summaries) and save_preference (wraps the
new services/preferences_store.py) for any MCP client. Same FastMCP pattern
as mcp_server.py, hand-rolled against this project's own Neo4jClient.

Run: `python mcp_memory_server.py` (stdio transport).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.dependencies import get_neo4j
from services import memory_service, preferences_store

mcp = FastMCP("neurosymbolic-memory")


@mcp.tool()
def search_memory(graph_id: str, query: str) -> str:
    """Search real, already-persisted memory for a graph -- chat session
    history and entity evolving-summaries -- for text matching the query.
    Returns matching hits, or reports no matches found."""
    hits = memory_service.search_memory(get_neo4j(), graph_id=graph_id, query=query)
    if not hits:
        return "No matching memory found."
    return "\n".join(f"[{h.kind}] {h.text}" for h in hits)


@mcp.tool()
def save_preference(key: str, value: str) -> str:
    """Save a real, persisted app-level preference (key/value), shared across
    graphs. Overwrites any existing value for the same key."""
    preferences_store.save_preference(get_neo4j(), key=key, value=value)
    return f"Saved preference '{key}' = '{value}'."


if __name__ == "__main__":
    mcp.run()
