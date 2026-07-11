"""Real-LLM chat grounded in real graph state.

Replaces the prototype's LLM console, which picked a random canned string
from a fixed list (docs/src/components/InspectorPanel.tsx LlmPanel). This
calls a real LLM with the graph's actual entities, relationships, and derived
facts in the prompt, so answers are grounded in what's really in Neo4j.
"""

from __future__ import annotations

import uuid

from db.neo4j_client import Neo4jClient
from llm.client import LLMClient
from services import chat_history_service, graph_service

_SYSTEM_TEMPLATE = """You are a knowledge-graph analyst assistant. Answer the user's question \
using ONLY the graph data below -- do not invent entities, relationships, or facts that \
aren't listed. If the graph is empty or doesn't contain the answer, say so plainly.

Graph: {node_count} entities, {edge_count} relationships.

Entities:
{entities}

Relationships:
{relationships}

Derived facts (from reasoning):
{facts}

Conversation so far (most recent first turn omitted if none):
{history}"""


def _build_system_prompt(graph_id: str, session_id: str, neo4j: Neo4jClient) -> str:
    record = graph_service.get_graph(neo4j, graph_id)
    facts = graph_service.get_derived_facts(neo4j, graph_id)
    history = chat_history_service.get_recent_messages(neo4j, graph_id=graph_id, session_id=session_id)

    entities = "\n".join(f"- {n.label} ({n.type})" for n in record.nodes) or "(none)"
    relationships = "\n".join(
        f"- {next((n.label for n in record.nodes if n.id == e.source), e.source)} "
        f"--{e.type}--> "
        f"{next((n.label for n in record.nodes if n.id == e.target), e.target)}"
        for e in record.edges
    ) or "(none)"
    facts_text = "\n".join(f"- {f['fact']} (confidence: {f['confidence']:.2f})" for f in facts) or "(none)"
    history_text = "\n".join(f"- {m.role}: {m.content}" for m in history) or "(none)"

    return _SYSTEM_TEMPLATE.format(
        node_count=len(record.nodes), edge_count=len(record.edges),
        entities=entities, relationships=relationships, facts=facts_text,
        history=history_text,
    )


def answer(*, neo4j: Neo4jClient, llm: LLMClient, graph_id: str, message: str, session_id: str) -> str:
    """PLAN.md §20 item 4: each call reads recent history for this session into
    the prompt, then appends the new turn -- real conversational continuity,
    not a stateless single-shot call."""
    system = _build_system_prompt(graph_id, session_id, neo4j)
    reply = llm.complete_json(system=system, user=message)

    chat_history_service.append_message(
        neo4j, graph_id=graph_id, session_id=session_id,
        message_id=f"{session_id}:{uuid.uuid4().hex[:12]}", role="user", content=message,
    )
    chat_history_service.append_message(
        neo4j, graph_id=graph_id, session_id=session_id,
        message_id=f"{session_id}:{uuid.uuid4().hex[:12]}", role="assistant", content=reply,
    )
    return reply
