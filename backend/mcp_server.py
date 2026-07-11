"""MCP server (PLAN.md §10 MCP Layer / §16 Phase 4): exposes the same real
knowledge-graph operations as agents/tools.py -- extraction, reasoning,
enrichment, query -- to any MCP client (e.g. Claude Desktop), over stdio.
Every tool wraps the same real, already-tested service functions the
LangGraph agent nodes and REST endpoints use, not a parallel
reimplementation.

Run: `python mcp_server.py` (stdio transport, for local MCP clients), or
configure this as an MCP server entry in a client's config pointing at this
file with the backend's .venv Python.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.dependencies import get_graphdb, get_llm, get_neo4j, settings as get_settings
from ontology.loader import load_schema
from services import enrichment_service, graph_service, ingest_service, reasoning_service
from services.query_engine import execute_query

mcp = FastMCP("neurosymbolic-kg")


@mcp.tool()
def extract_entities(graph_id: str, text: str) -> str:
    """Extract real entities and relationships from text into the knowledge graph,
    validated against the loaded ontology. Returns a summary of what was extracted."""
    settings = get_settings()
    _record, result = ingest_service.ingest_text(
        neo4j=get_neo4j(), graphdb=get_graphdb(), llm=get_llm(), graph_id=graph_id, text=text,
        source_doc=f"mcp:{graph_id}", repository=settings.graphdb_repository,
    )
    return f"Extracted {len(result.entities)} entities and {len(result.relationships)} relationships."


@mcp.tool()
def run_reasoning(graph_id: str) -> str:
    """Run the neurosymbolic persistent-activation reasoning loop over the existing
    knowledge graph, deriving new facts from real relationships. Returns a summary."""
    settings = get_settings()
    try:
        result = reasoning_service.run_reasoning(get_neo4j(), get_graphdb(), settings, graph_id=graph_id, source_id=None)
    except (reasoning_service.EmptyGraphError, reasoning_service.UnknownSourceError) as e:
        return str(e)
    return f"Derived {len(result.facts)} new facts, converged by {result.converged_by}."


@mcp.tool()
def run_enrichment(graph_id: str, text: str) -> str:
    """Run all 11 Polanyi enrichment heuristics over the graph plus source text,
    inferring implicit knowledge. Results are pending human approval before they
    count as part of the graph. Returns a summary."""
    neo4j = get_neo4j()
    record = graph_service.get_graph(neo4j, graph_id)
    candidates = enrichment_service.run_all_heuristics(get_llm(), nodes=record.nodes, edges=record.edges, source_text=text)
    enrichment_service.save_pending_facts(neo4j, graph_id=graph_id, source_doc=text, candidates=candidates)
    return f"Found {len(candidates)} implicit facts, pending review."


@mcp.tool()
def query_graph(graph_id: str, query: str) -> str:
    """Run a structured query, predicate(subject, object), against the graph's real
    stored and derived facts. Variables are capitalized (X, Y, Z). Returns the results."""
    triples = graph_service.load_triples(get_neo4j(), graph_id)
    result = execute_query(query, triples)
    if result.error:
        return f"Query error: {result.error}"
    if not result.results:
        return "No results found."
    return "\n".join(f'{r.subject} {r.predicate}("{r.object}")' for r in result.results)


@mcp.resource("ontology://schema")
def get_ontology_schema() -> str:
    """The real, currently-loaded domain ontology's vocabulary -- whatever repository
    is configured defines this app's domain, with zero code changes needed to swap it."""
    settings = get_settings()
    schema = load_schema(get_graphdb(), settings.graphdb_repository)
    classes = "\n".join(f"- {c}" for c in schema.class_labels)
    properties = "\n".join(f"- {p}" for p in schema.property_labels)
    return f"Entity types:\n{classes}\n\nRelationship types:\n{properties}"


if __name__ == "__main__":
    mcp.run()
