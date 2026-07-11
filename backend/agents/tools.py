"""Formal LangChain @tool registrations (PLAN.md §16 Phase 5, Tool Layer),
wrapping the same real service functions the agent graph's nodes (agents/
graph.py) and the REST endpoints already use -- not a parallel
reimplementation.

Not currently wired into an autonomous ReAct-style tool-calling loop --
agents/graph.py's routing is deterministic (a router node classifies intent,
then a fixed edge leads to the matching node), not LLM-driven tool
selection. This formalizes the operation surface explicitly and gives each
one a real, testable description an LLM (or future ReAct agent) could pick
from, rather than leaving "what can this agent do" implicit in graph.py's
node bodies.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.config import Settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient
from services import enrichment_service, graph_service, ingest_service, reasoning_service
from services.query_engine import execute_query


def build_tools(neo4j: Neo4jClient, graphdb: GraphDBClient, llm: LLMClient, settings: Settings) -> list:
    @tool
    def extract_entities(graph_id: str, text: str) -> str:
        """Extract real entities and relationships from text into the knowledge graph,
        validated against the loaded ontology. Returns a summary of what was extracted."""
        _record, result = ingest_service.ingest_text(
            neo4j=neo4j, graphdb=graphdb, llm=llm, graph_id=graph_id, text=text,
            source_doc=f"tool:{graph_id}", repository=settings.graphdb_repository,
        )
        return f"Extracted {len(result.entities)} entities and {len(result.relationships)} relationships."

    @tool
    def run_reasoning(graph_id: str) -> str:
        """Run the neurosymbolic persistent-activation reasoning loop over the existing
        knowledge graph, deriving new facts from real relationships. Returns a summary."""
        try:
            result = reasoning_service.run_reasoning(neo4j, graphdb, settings, graph_id=graph_id, source_id=None)
        except (reasoning_service.EmptyGraphError, reasoning_service.UnknownSourceError) as e:
            return str(e)
        return f"Derived {len(result.facts)} new facts, converged by {result.converged_by}."

    @tool
    def run_enrichment(graph_id: str, text: str) -> str:
        """Run all 11 Polanyi enrichment heuristics over the graph plus source text,
        inferring implicit knowledge. Results are pending human approval before they
        count as part of the graph. Returns a summary."""
        record = graph_service.get_graph(neo4j, graph_id)
        candidates = enrichment_service.run_all_heuristics(llm, nodes=record.nodes, edges=record.edges, source_text=text)
        enrichment_service.save_pending_facts(neo4j, graph_id=graph_id, source_doc=text, candidates=candidates)
        return f"Found {len(candidates)} implicit facts, pending review."

    @tool
    def query_graph(graph_id: str, query: str) -> str:
        """Run a structured query, predicate(subject, object), against the graph's real
        stored and derived facts. Variables are capitalized (X, Y, Z). Returns the results."""
        triples = graph_service.load_triples(neo4j, graph_id)
        result = execute_query(query, triples)
        if result.error:
            return f"Query error: {result.error}"
        if not result.results:
            return "No results found."
        return "\n".join(f'{r.subject} {r.predicate}("{r.object}")' for r in result.results)

    return [extract_entities, run_reasoning, run_enrichment, query_graph]
