"""LangGraph agent (MVP_PLAN.md Phase 6 + PLAN.md §8 Agent Layer): a router
classifies intent, then branches to extractor/enricher/querier/reasoner --
every node calls the same real, already-tested service functions the REST
endpoints use (ingest_service, reasoning_service, enrichment_service,
query_engine) -- this is an orchestration layer over real work, not a
parallel reimplementation. All paths converge on a single responder.

Checkpointing: `InMemorySaver`, not a custom Neo4j-backed checkpointer.
`BaseCheckpointSaver`'s real interface (delta channel history, pruning,
allowlists) is substantially larger than a hand-rolled implementation could
safely cover for this MVP slice, and a third-party `langgraph-checkpoint-neo4j`
package exists but is pre-1.0 (0.0.1) -- installing an unvetted, very-early
external dependency was declined. The actual user-facing need this MVP cares
about (cross-session conversational memory) is already served by
services/chat_history_service.py (PLAN.md §20 item 4, native, tested, live-
verified); LangGraph's own checkpointing here is about resuming a single
in-flight graph run, which InMemorySaver handles correctly for a
single-process desktop app. Revisit with a real Neo4j-backed saver if this
ever needs to survive a process restart mid-run.

Runtime skills (PLAN.md §13.2, backend/skills/): kg-extraction is loaded by
the extractor node directly (it feeds a real LLM call). kg-query,
neurosymbolic-reasoning, kg-visualization, and polanyi-enrichment don't have
as natural a home in their own nodes -- the query engine and reasoning
engine are deterministic, LLM-free by design -- so they're loaded by the
responder based on intent, where the LLM call that actually needs the
guidance lives. memory-recall loads in addition whenever the message itself
looks temporal, regardless of primary intent.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents import skill_store
from agents.state import AgentState
from app.config import Settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient
from services import enrichment_service, graph_service, ingest_service, reasoning_service
from services.query_engine import execute_query

_ROUTER_SYSTEM = """You are a routing classifier for a knowledge graph agent. Classify the \
user's message as exactly one of: extract, enrich, query, reason, visualize.

- extract: the message IS a document or passage of real-world text (a sentence, paragraph, \
filing excerpt) to add to the knowledge graph. This is the default for any plain declarative \
text that is not an explicit request about the graph itself.
- enrich: the user explicitly asks to find implicit, hidden, or unstated knowledge in the \
graph's EXISTING content (e.g. "what's implied by...", "enrich the graph").
- query: the message is a structured query in the form predicate(subject, object), e.g. regulates("FINMA", X)
- reason: the user explicitly asks to run reasoning/inference over the existing graph, without adding new text.
- visualize: the user explicitly asks to see, visualize, or get an overview/export of the graph.

Examples:
"Deutsche Bank AG issued a bond." -> extract
"Acme Corp is regulated by FINMA and domiciled in Zurich." -> extract
"Enrich the graph with implicit knowledge." -> enrich
"What is implied about the company that is not stated directly?" -> enrich
regulates("FINMA", X) -> query
"Run reasoning over the graph." -> reason
"Show me an overview of the graph." -> visualize

Respond with ONLY one word: extract, enrich, query, reason, or visualize."""

_VALID_INTENTS = {"extract", "enrich", "query", "reason", "visualize"}

_RESPONDER_SYSTEM = """You are a knowledge-graph analyst assistant. Summarize, in 1-3 \
sentences, what just happened during ingestion and reasoning over a real document -- \
using ONLY the real entities, relationships, and facts listed below. Do not invent \
anything not listed."""

_SKILL_BY_INTENT = {
    "enrich": "polanyi-enrichment",
    "query": "kg-query",
    "reason": "neurosymbolic-reasoning",
    "visualize": "kg-visualization",
}

# Lightweight heuristic, not an LLM call -- matches PLAN.md §20's memory-recall
# skill's own trigger condition: "activates on temporal/historical requests."
_TEMPORAL_KEYWORDS = ("historical", "as of", "previously", "used to", "before", "changed", "supersede")


def build_graph(neo4j: Neo4jClient, graphdb: GraphDBClient, llm: LLMClient, settings: Settings):
    def router_node(state: AgentState) -> dict:
        raw = llm.complete_json(system=_ROUTER_SYSTEM, user=state["text"])
        intent = raw.strip().lower()
        if intent not in _VALID_INTENTS:
            intent = "extract"  # safe, most-tested default
        return {"intent": intent}

    def route_by_intent(state: AgentState) -> str:
        return state["intent"]

    def extractor_node(state: AgentState) -> dict:
        # PLAN.md §13.2: Discovery -> Activation -> Execution, for real --
        # the runtime skill's content becomes part of the actual LLM prompt.
        guidance = skill_store.load("kg-extraction")
        _record, result = ingest_service.ingest_text(
            neo4j=neo4j, graphdb=graphdb, llm=llm, graph_id=state["graph_id"],
            text=state["text"], source_doc=f"agent:{state['graph_id']}",
            repository=settings.graphdb_repository, extra_guidance=guidance,
        )
        return {
            "entities_extracted": len(result.entities),
            "relationships_extracted": len(result.relationships),
        }

    def reasoner_node(state: AgentState) -> dict:
        try:
            result = reasoning_service.run_reasoning(
                neo4j, graphdb, settings, graph_id=state["graph_id"], source_id=None,
            )
        except (reasoning_service.EmptyGraphError, reasoning_service.UnknownSourceError):
            # Nothing was extracted (or nothing reasonable to reason from) --
            # a normal outcome for non-domain text, not an error.
            return {"facts_derived": 0, "fact_texts": []}
        return {"facts_derived": len(result.facts), "fact_texts": [f.fact for f in result.facts]}

    def enricher_node(state: AgentState) -> dict:
        record = graph_service.get_graph(neo4j, state["graph_id"])
        candidates = enrichment_service.run_all_heuristics(
            llm, nodes=record.nodes, edges=record.edges, source_text=state["text"],
        )
        enrichment_service.save_pending_facts(
            neo4j, graph_id=state["graph_id"], source_doc=state["text"], candidates=candidates,
        )
        return {"enrichment_fact_texts": [c.text for c in candidates]}

    def querier_node(state: AgentState) -> dict:
        triples = graph_service.load_triples(neo4j, state["graph_id"])
        result = execute_query(state["text"], triples)
        if result.error:
            return {"query_results": [], "query_error": result.error}
        return {
            "query_results": [f'{r.subject} {r.predicate}("{r.object}")' for r in result.results],
            "query_error": "",
        }

    def responder_node(state: AgentState) -> dict:
        intent = state["intent"]
        guidance_parts = []
        skill_name = _SKILL_BY_INTENT.get(intent)
        if skill_name:
            guidance_parts.append(skill_store.load(skill_name))
        if any(kw in state["text"].lower() for kw in _TEMPORAL_KEYWORDS):
            guidance_parts.append(skill_store.load("memory-recall"))
        system = _RESPONDER_SYSTEM
        if guidance_parts:
            system = f"{system}\n\n" + "\n\n".join(guidance_parts)

        if intent == "query":
            results_text = "\n".join(state["query_results"]) or "(no results)"
            error_text = f"\nError: {state['query_error']}" if state["query_error"] else ""
            user = f"Query: {state['text']}\nResults:\n{results_text}{error_text}"
        elif intent == "enrich":
            facts_text = "\n".join(f"- {f}" for f in state["enrichment_fact_texts"]) or "(none found)"
            user = f"Implicit facts found by the 11 Polanyi heuristics:\n{facts_text}"
        elif intent == "visualize":
            record = graph_service.get_graph(neo4j, state["graph_id"])
            entities_text = "\n".join(f"- {n.label} ({n.type})" for n in record.nodes) or "(empty graph)"
            user = (
                f"The user wants to visualize/see an overview of the real graph "
                f"({len(record.nodes)} entities, {len(record.edges)} relationships):\n{entities_text}"
            )
        else:  # extract or reason -- grounded in the real current graph state
            record = graph_service.get_graph(neo4j, state["graph_id"])
            entities_text = "\n".join(f"- {n.label}" for n in record.nodes) or "(none)"
            facts_text = "\n".join(f"- {fact}" for fact in state["fact_texts"]) or "(none)"
            user = (
                f"Entities in the graph:\n{entities_text}\n\n"
                f"Relationships extracted this turn: {state['relationships_extracted']}\n\n"
                f"Facts derived by reasoning:\n{facts_text}"
            )

        reply = llm.complete_json(system=system, user=user)
        return {"reply": reply}

    workflow = StateGraph(AgentState)
    workflow.add_node("router", router_node)
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("reasoner", reasoner_node)
    workflow.add_node("enricher", enricher_node)
    workflow.add_node("querier", querier_node)
    workflow.add_node("responder", responder_node)

    workflow.add_edge(START, "router")
    workflow.add_conditional_edges("router", route_by_intent, {
        "extract": "extractor",
        "enrich": "enricher",
        "query": "querier",
        "reason": "reasoner",
        "visualize": "responder",
    })
    workflow.add_edge("extractor", "reasoner")
    workflow.add_edge("reasoner", "responder")
    workflow.add_edge("enricher", "responder")
    workflow.add_edge("querier", "responder")
    workflow.add_edge("responder", END)

    return workflow.compile(checkpointer=InMemorySaver())
