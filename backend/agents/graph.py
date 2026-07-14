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

Compound-query answering (2026-07-13 plan §6, behind
settings.enable_compound_queries, default off): the router can list more
than one capability ("reason,recall") when the flag is on; route_by_intent
then fans out via LangGraph's Send to each eligible specialist in parallel
(cross-checked against Stage A discovery via _is_eligible, not trusted
blindly), each writes an additive entry into partial_answers (an
Annotated[dict, operator.or_]-reduced field -- required, not decorative, or
two parallel writes in the same superstep raise LangGraph's
InvalidUpdateError), combiner_node joins them deterministically, and
responder_node's "compound" branch synthesizes one reply. With the flag off,
router_node truncates to a single intent unconditionally -- provably
identical to pre-Feature-4 behavior, not just "probably fine." The Send/
reducer/join mechanics were verified against the installed langgraph version
via a throwaway spike (plan §6.9) before any of this was wired into the real
graph.

Skill graph (PLAN.md §18/§2.9.14, extended by 2026-07-13 plan §2 Stage A):
every skill load above goes through ResilientSkillDiscovery instead of
agents/skill_store.py directly -- same filesystem content, but the router
additionally calls find_relevant_skills() every turn, and every node that
loads a skill calls record_usage() after acting on it, so the graph's
Skill.confidence is a real rolling average of outcomes, not a static number.
responder_node's skill choice now goes through _select_skill(): discovery's
top match wins when it clears a confidence floor (_SKILL_SELECTION_MIN_SCORE),
_SKILL_BY_INTENT is the fallback for everything else (Neo4j down, low-
confidence match, or no match at all) -- the same defensive pattern already
used for intent itself just above. The discovery query itself is built by
_discovery_query(intent, text), not raw state["text"] alone: routed text is
often bare document content ("Acme Corp issued preferred stock.") sharing no
vocabulary with skill descriptions ("Use when extracting entities..."), which
would make the Lucene full-text match return nothing -- folding in an
intent-derived phrase guarantees a match while the real text still
contributes to ranking among matches.
"""

from __future__ import annotations

import re

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agents.skill_discovery import ResilientSkillDiscovery
from agents.state import AgentState
from app.config import Settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from enrichment.heuristics.base import HEURISTIC_TYPES
from llm.client import LLMClient
from llm.embedder import EmbeddingClient
from ontology.loader import load_schema
from services import (
    analytics_service,
    chat_history_service,
    enrichment_service,
    graph_service,
    ingest_service,
    memory_config_service,
    memory_service,
    nl_query_service,
    reasoning_service,
)
from services.query_engine import execute_query

_ROUTER_SYSTEM = """You are a routing classifier for a knowledge graph agent. Classify the \
user's message as exactly one of: extract, enrich, query, reason, visualize, recall, analyze.

- extract: the message IS a document or passage of real-world text (a sentence, paragraph, \
filing excerpt) to add to the knowledge graph. This is the default for any plain declarative \
text that is not an explicit request about the graph itself.
- enrich: the user explicitly asks to find implicit, hidden, or unstated knowledge in the \
graph's EXISTING content (e.g. "what's implied by...", "enrich the graph").
- query: the message is a structured query in the form predicate(subject, object), e.g. regulates("FINMA", X)
- reason: the user explicitly asks to run reasoning/inference over the existing graph, without adding new text.
- visualize: the user explicitly asks to see, visualize, or get an overview/export of the graph.
- recall: the user asks what THEY (or the assistant) said/asked before, in a prior turn or \
session -- about the conversation itself, not about graph content (e.g. "what did I ask about \
before?", "what did we discuss earlier?").
- analyze: the user asks a computed-metric question about the graph's structure -- which \
entities are most central/important/influential, how connected the graph is, or similar graph \
analytics questions. Distinct from visualize (a prose overview), reason (deriving new facts), \
and query (looking up existing facts by predicate).

Examples:
"Deutsche Bank AG issued a bond." -> extract
"Acme Corp is regulated by FINMA and domiciled in Zurich." -> extract
"Enrich the graph with implicit knowledge." -> enrich
"What is implied about the company that is not stated directly?" -> enrich
regulates("FINMA", X) -> query
"Run reasoning over the graph." -> reason
"Show me an overview of the graph." -> visualize
"What did I ask about before?" -> recall
"What did we discuss earlier in this conversation?" -> recall
"Which entities are most central or influential in this graph?" -> analyze
"How connected is this graph overall?" -> analyze

Respond with ONLY one word: extract, enrich, query, reason, visualize, recall, or analyze."""

_VALID_INTENTS = {"extract", "enrich", "query", "reason", "visualize", "recall", "analyze"}

# 2026-07-13 plan §6: only appended to _ROUTER_SYSTEM when
# settings.enable_compound_queries -- with the flag off, the LLM is never
# told compound is an option, so router_node's output is provably identical
# to pre-Feature-4 behavior (single word, never a comma-list).
_COMPOUND_ADDENDUM = """
If the message clearly needs MORE THAN ONE of the above capabilities together \
to fully answer, respond with a comma-separated list instead of one word, e.g. \
"reason,recall". Only do this when genuinely necessary -- most messages need \
exactly one capability, and single-word answers remain correct for those.

Compound examples:
"Is Acme Bank's ownership chain compliant, and have we flagged this pattern before?" -> reason,recall
"Query the current ownership edges and also check reasoning for anything derivable." -> query,reason
"""

_RESPONDER_SYSTEM = """You are a knowledge-graph analyst assistant. Summarize, in 1-3 \
sentences, what just happened during ingestion and reasoning over a real document -- \
using ONLY the real entities, relationships, and facts listed below. Do not invent \
anything not listed."""

_SKILL_BY_INTENT = {
    "enrich": "polanyi-enrichment",
    "query": "kg-query",
    "reason": "neurosymbolic-reasoning",
    "visualize": "kg-visualization",
    "recall": "memory-recall",
    "analyze": "kg-analytics",
}

# 2026-07-13 plan §6.4: structural 1:1 map from a compound-eligible intent to
# its specialist node. Deliberately excludes "extract" (extraction can't be
# one of several parallel Send branches -- reasoning/querying/etc. over a
# graph "extract" hasn't written to yet would race it; router_node collapses
# any intents list containing "extract" back to single-intent before this is
# ever consulted) and "visualize" (no specialist node of its own -- reads the
# final graph state directly inside responder_node).
_NODE_BY_INTENT = {"reason": "reasoner", "recall": "memory_agent", "query": "querier", "enrich": "enricher", "analyze": "analyst"}


def _is_eligible(intent: str, raw_text_discovered_skills: list[str]) -> bool:
    """2026-07-13 plan §6.4: cross-checks a compound-listed SECONDARY intent
    against discovery run on the RAW turn text (route_by_intent -- not
    _discovery_query's intent-phrase-boosted version, which would make an
    intent's own mapped skill win its own query almost tautologically,
    defeating the point of an independent check) -- only dispatches if its
    corresponding skill genuinely showed up as relevant to the actual text,
    not just because the router LLM listed the word. The PRIMARY intent
    (intents[0]) is exempt from this check in route_by_intent -- trusted
    exactly as much as the existing single-intent path already trusts the
    router's own classification, never gated further. Stage C's ontology-
    type gate is deliberately not part of this check (skipped this round --
    see 2026-07-13 checklist: no real entity-type-restricted skill exists
    yet to gate on)."""
    skill_name = _SKILL_BY_INTENT.get(intent)
    return skill_name is not None and skill_name in raw_text_discovered_skills


def combiner_node(state: AgentState) -> dict:
    """2026-07-13 plan §5.7: deterministic join of parallel specialist
    output, no LLM call -- module-level (not a build_graph closure) since it
    only ever reads state["partial_answers"], needing none of build_graph's
    captured neo4j/llm/discovery/settings -- fully testable in isolation
    with a fabricated partial_answers dict, per the plan's own test spec."""
    sections = []
    for name in ("reasoner", "querier", "enricher", "memory_agent"):
        pa = state["partial_answers"].get(name)
        if pa:
            sections.append(f"[{name}, confidence={pa['confidence']:.2f}] {pa['summary']}")
    return {"combined_answer": "\n".join(sections) or "(no sub-answers produced)"}


def _find_ungrounded_claims(reply: str, grounding_text: str) -> list[str]:
    """2026-07-13 plan §12.4 maker/checker split, generalized (follow-up
    request) from just the "compound" intent to every responder_node reply:
    the model that synthesized `reply` is not the one that checks whether
    it over-claimed. Deterministic first (only escalates to a second LLM
    call if this actually finds something -- see responder_node).
    `grounding_text` is whatever real data the caller built `reply` from --
    responder_node passes its own `user` prompt, which already holds the
    real query results / derived facts / entities / memory hits / combined
    sub-answers for every intent, so this one check works everywhere with
    no per-intent plumbing.

    Flags sentences that introduce a specific factual token -- a multi-word
    proper-noun phrase or a number -- that never appears anywhere in
    grounding_text. Deliberately NOT a raw keyword-overlap-ratio check:
    calibrated against a real live-captured compound reply before writing
    this, and plain word overlap flagged genuinely grounded paraphrase
    sentences ("However, I couldn't find...") just as readily as fabricated
    ones -- natural connective language dilutes overlap either way. A novel
    specific token is a much lower-false-positive signal of invention, not
    paraphrase (verified zero false positives against that same real reply,
    and correctly caught two novel tokens in a deliberately fabricated one).

    Known limitation, accepted as a reasonable precision/recall tradeoff:
    single-word proper nouns (e.g. a lone invented city name) aren't caught
    by the multi-word-phrase pattern -- catching *some* signal to trigger a
    bounded retry matters more here than exhaustive detection, and a
    single-word regex reintroduces the sentence-initial-capitalization
    false-positive problem this was calibrated to avoid."""
    grounding_lower = grounding_text.lower()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", reply) if s.strip()]
    ungrounded = []
    for sentence in sentences:
        # Sentence-initial capitalization is a grammar artifact, not
        # evidence of a proper noun -- lower just that first character
        # before matching.
        adjusted = (sentence[0].lower() + sentence[1:]) if sentence else sentence
        proper_noun_phrases = re.findall(r"\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)+\b", adjusted)
        numbers = re.findall(r"\b\d[\d,.]{2,}\b", adjusted)
        novel = [t for t in proper_noun_phrases + numbers if t.lower() not in grounding_lower]
        if novel:
            ungrounded.append(sentence)
    return ungrounded

# 2026-07-13 plan §2 Stage A: minimum Lucene full-text score (not a
# normalized 0-1 confidence -- observed real scores range roughly 0.3-1.5)
# for discovery's top match to override _SKILL_BY_INTENT. Calibrated against
# live-observed scores in tests/test_agent_graph.py's Stage A tests, not
# picked blindly.
_SKILL_SELECTION_MIN_SCORE = 0.35


def _select_skill(intent: str, discovered_names: list[str], discovered_scores: list[float]) -> str | None:
    """2026-07-13 plan §2 Stage A: discovery becomes the actual selector,
    not just observability (PLAN.md §18.4 item 3's original scope) --
    _SKILL_BY_INTENT is demoted to a fallback for when discovery returns
    nothing or its top match scores below the confidence floor, mirroring
    the exact defensive pattern the router already uses for intent itself
    (`if intent not in _VALID_INTENTS: intent = "extract"` below).

    Deliberately falls back to `_SKILL_BY_INTENT.get(intent)` -- which is
    None for "extract"/"reason", intents the map never covered -- rather
    than the plan sketch's `"kg-extraction"` default: preserves this
    function's exact prior no-op behavior for those intents (responder_node
    loaded no guidance for them before this change either), while still
    letting a confident discovery match apply even there. Never a
    regression versus pre-Stage-A behavior, only ever a strict addition."""
    if discovered_names and discovered_scores and discovered_scores[0] >= _SKILL_SELECTION_MIN_SCORE:
        return discovered_names[0]
    return _SKILL_BY_INTENT.get(intent)

# find_relevant_skills is a Lucene full-text match against skill
# *descriptions* (e.g. kg-extraction's: "Use when extracting entities and
# relationships from real-world source text..."). Routed text is often the
# raw document being ingested ("Acme Corp issued preferred stock."), which
# shares no vocabulary with any skill description and would return zero
# matches. Once intent is classified, prefix the discovery query with a
# phrase lifted from the matching skill's own description -- guarantees
# vocabulary overlap -- while still folding in the real text so genuine
# content can still influence ranking among the skills that do match.
_DISCOVERY_PHRASE_BY_INTENT = {
    "extract": "extracting entities and relationships from real-world source text into the knowledge graph, extraction ingest",
    "enrich": "inferring implicit unstated knowledge from a knowledge graph's existing content and its source text, enrichment",
    "query": "answering a structured query or formatting query results from the knowledge graph",
    "reason": "explaining neurosymbolic reasoning results, spread activation, derived facts, proof paths",
    "visualize": "visualize, export, or get a visual overview of the knowledge graph",
    "recall": "a question that references prior conversation, a point in time, or how a fact has changed, temporal historical recall",
    "analyze": "computed graph analytics, centrality, most important or influential entities, graph connectivity metrics",
}


def _discovery_query(intent: str, text: str) -> str:
    phrase = _DISCOVERY_PHRASE_BY_INTENT.get(intent, "")
    return f"{phrase} {text}".strip()

# Lightweight heuristic, not an LLM call -- matches PLAN.md §20's memory-recall
# skill's own trigger condition: "activates on temporal/historical requests."
_TEMPORAL_KEYWORDS = ("historical", "as of", "previously", "used to", "before", "changed", "supersede")

# Words to drop when turning a recall question ("What did I previously ask
# about Credit Suisse?") into search terms for memory_service.search_memory --
# a real, deterministic keyword extraction (not an LLM call), not the
# full-question-as-substring search that CONTAINS-matching can't satisfy.
_RECALL_STOPWORDS = {
    "what", "did", "i", "you", "we", "ask", "asked", "about", "before", "earlier",
    "previously", "discuss", "discussed", "when", "where", "was", "were", "have",
    "has", "the", "this", "that", "said", "conversation",
}


def build_graph(neo4j: Neo4jClient, graphdb: GraphDBClient, llm: LLMClient, settings: Settings, embedder: EmbeddingClient | None = None):
    discovery = ResilientSkillDiscovery(neo4j)

    def router_node(state: AgentState) -> dict:
        system = _ROUTER_SYSTEM + (_COMPOUND_ADDENDUM if settings.enable_compound_queries else "")
        raw = llm.complete_json(system=system, user=state["text"])
        parts = [p.strip().lower() for p in raw.strip().split(",")]
        intents = [p for p in parts if p in _VALID_INTENTS] or ["extract"]  # safe, most-tested default
        if not settings.enable_compound_queries or "extract" in intents:
            # Flag off: never fan out, full stop -- this is the regression-
            # safety guarantee, not just "probably fine" (a base-prompt LLM
            # free-associating a stray comma would otherwise silently enable
            # compound behavior even with the flag off). "extract" present:
            # collapse to single-intent regardless of the flag -- extraction
            # structurally can't be one of several parallel branches (see
            # _NODE_BY_INTENT's docstring).
            intents = intents[:1]
        primary_intent = intents[0]
        # 2026-07-13 plan §2 Stage A: find_relevant_skills' ranked output now
        # actually drives responder_node's skill selection (_select_skill),
        # not just observability -- degrades to filesystem keyword matching
        # if Neo4j is down (ResilientSkillDiscovery), never blocks routing.
        # Wider limit for a compound turn: a secondary intent's skill needs a
        # fair shot at appearing in the ranked list _is_eligible checks
        # against, not to be starved by a cutoff sized for the single-intent
        # case.
        discovery_limit = 3 if len(intents) == 1 else 6
        discovered = discovery.find_skills(_discovery_query(primary_intent, state["text"]), limit=discovery_limit)
        return {
            "intent": primary_intent if len(intents) == 1 else "compound",
            "intents": intents,
            "discovered_skills": [d.name for d in discovered],
            "discovered_skill_scores": [d.score for d in discovered],
            "partial_answers": {},
        }

    def route_by_intent(state: AgentState):
        if len(state["intents"]) > 1:
            primary, secondary = state["intents"][0], state["intents"][1:]
            eligible = [primary] if primary in _NODE_BY_INTENT else []
            secondary_candidates = [i for i in secondary if i in _NODE_BY_INTENT]
            if secondary_candidates:
                # Deliberately the RAW text, no _discovery_query intent-phrase
                # boost: a phrase-boosted query would make an intent's own
                # mapped skill win its own query almost tautologically (see
                # Stage A's empirical findings), which defeats the point of
                # cross-checking a SECONDARY intent -- this needs a signal
                # independent of "the router already said so." Raw-text
                # relevance is exactly that independent signal (verified
                # empirically before writing this: a genuinely relevant
                # secondary intent's skill does surface this way; an
                # unrelated one legitimately doesn't).
                raw_discovered = discovery.find_skills(state["text"], limit=6)
                raw_names = [d.name for d in raw_discovered]
                eligible += [i for i in secondary_candidates if _is_eligible(i, raw_names)]
            if eligible:
                return [Send(_NODE_BY_INTENT[i], state) for i in eligible]
            # Nothing survived (rare -- the primary intent is exempt from
            # this check) -- fall back to the primary intent's ordinary
            # single-path routing rather than dispatching zero branches.
        return state["intents"][0]

    def extractor_node(state: AgentState) -> dict:
        # PLAN.md §13.2: Discovery -> Activation -> Execution, for real --
        # the runtime skill's content becomes part of the actual LLM prompt.
        guidance = discovery.load_skill("kg-extraction")
        active_embedder = embedder if embedder is not None and memory_config_service.get_backend(neo4j) == "native" else None
        try:
            _record, result = ingest_service.ingest_text(
                neo4j=neo4j, graphdb=graphdb, llm=llm, graph_id=state["graph_id"],
                text=state["text"], source_doc=f"agent:{state['graph_id']}",
                repository=settings.graphdb_repository, extra_guidance=guidance,
                embedder=active_embedder,
            )
        except Exception:
            discovery.record_usage("kg-extraction", session_id=state["graph_id"], success=False)
            raise
        discovery.record_usage("kg-extraction", session_id=state["graph_id"], success=True)
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
            update = {"facts_derived": 0, "fact_texts": []}
            if len(state["intents"]) > 1:
                update["partial_answers"] = {"reasoner": {"summary": "no new facts derived", "confidence": 0.0}}
            return update
        fact_texts = [f.fact for f in result.facts]
        update = {"facts_derived": len(result.facts), "fact_texts": fact_texts}
        if len(state["intents"]) > 1:
            conf = (sum(f.confidence for f in result.facts) / len(result.facts)) if result.facts else 0.0
            update["partial_answers"] = {"reasoner": {"summary": "; ".join(fact_texts[:5]) or "no new facts derived", "confidence": conf}}
        return update

    def enricher_node(state: AgentState) -> dict:
        record = graph_service.get_graph(neo4j, state["graph_id"])
        candidates = enrichment_service.run_all_heuristics(
            llm, nodes=record.nodes, edges=record.edges, source_text=state["text"],
        )
        enrichment_service.save_pending_facts(
            neo4j, graph_id=state["graph_id"], source_doc=state["text"], candidates=candidates,
        )
        candidate_texts = [c.text for c in candidates]
        update = {"enrichment_fact_texts": candidate_texts}
        if len(state["intents"]) > 1:
            heuristics_with_hits = len({c.heuristic_type for c in candidates})
            update["partial_answers"] = {"enricher": {
                "summary": "; ".join(candidate_texts[:5]) or "no implicit facts found",
                "confidence": heuristics_with_hits / len(HEURISTIC_TYPES),
            }}
        return update

    def querier_node(state: AgentState) -> dict:
        triples = graph_service.load_triples(neo4j, state["graph_id"])
        query_text = state["text"]
        translated_query = ""

        if not nl_query_service.is_dsl_syntax(query_text):
            schema = load_schema(graphdb, settings.graphdb_repository)
            predicates = sorted({t.predicate for t in triples})
            entity_labels = sorted({t.subject for t in triples} | {t.object for t in triples})
            fewshot = nl_query_service.get_fewshot_examples(neo4j, settings.graphdb_repository)
            # Scoped by graph_id, not a separate chat-session id: this
            # LangGraph flow doesn't persist its own turns to
            # chat_history_service today (services/chat_service.py's /chat
            # endpoint is the parallel mechanism that does) -- reads
            # whatever history is seeded under graph_id directly.
            history = chat_history_service.get_recent_messages(neo4j, graph_id=state["graph_id"], session_id=state["graph_id"])
            translated = nl_query_service.translate_to_dsl(
                query_text, schema=schema, predicates=predicates, entity_labels=entity_labels,
                fewshot=fewshot, history=history, llm=llm,
            )
            if translated == nl_query_service.NL_QUERY_OUT_OF_SCOPE:
                error = "I couldn't map that question to anything in this graph."
                update = {"query_results": [], "query_error": error, "translated_query": ""}
                if len(state["intents"]) > 1:
                    update["partial_answers"] = {"querier": {"summary": f"query error: {error}", "confidence": 0.0}}
                return update
            query_text = translated
            translated_query = translated

        result = execute_query(query_text, triples)
        if result.error:
            update = {"query_results": [], "query_error": result.error, "translated_query": translated_query}
            if len(state["intents"]) > 1:
                update["partial_answers"] = {"querier": {"summary": f"query error: {result.error}", "confidence": 0.0}}
            return update
        query_results = [f'{r.subject} {r.predicate}("{r.object}")' for r in result.results]
        update = {"query_results": query_results, "query_error": "", "translated_query": translated_query}
        if len(state["intents"]) > 1:
            update["partial_answers"] = {"querier": {
                "summary": "; ".join(query_results[:5]) or "no query results",
                "confidence": 1.0 if query_results else 0.0,
            }}
        return update

    def analyst_node(state: AgentState) -> dict:
        # v1 scope (PLAN Slice 9): always runs degree_centrality -- the
        # simplest, always-available metric. NL selection of a specific
        # algorithm from the user's phrasing is a real future extension,
        # not required by this slice's acceptance criteria.
        scores = analytics_service.run_default_analysis(neo4j, state["graph_id"], algorithm="degree_centrality")
        record = graph_service.get_graph(neo4j, state["graph_id"])
        labels_by_id = {n.id: n.label for n in record.nodes}
        ranked = sorted(scores.items(), key=lambda item: -item[1])
        analytics_summary = [f"{labels_by_id.get(node_id, node_id)}: {score:.3f}" for node_id, score in ranked]
        update = {"analytics_summary": analytics_summary}
        if len(state["intents"]) > 1:
            update["partial_answers"] = {"analyst": {
                "summary": "; ".join(analytics_summary[:5]) or "no analytics results",
                "confidence": 1.0 if analytics_summary else 0.0,
            }}
        return update

    def memory_agent_node(state: AgentState) -> dict:
        words = [w.strip("?.,!\"'") for w in state["text"].split()]
        terms = [w for w in words if len(w) > 3 and w.lower() not in _RECALL_STOPWORDS] or [state["text"]]
        seen_ids: set[str] = set()
        hits = []
        terms_with_hits = 0
        for term in terms:
            term_hits = memory_service.search_memory(neo4j, graph_id=state["graph_id"], query=term, embedder=embedder, settings=settings)
            if term_hits:
                terms_with_hits += 1
            for hit in term_hits:
                if hit.id not in seen_ids:
                    seen_ids.add(hit.id)
                    hits.append(hit)
        memory_hits = [f"[{h.kind}] {h.text}" for h in hits[:10]]
        update = {"memory_hits": memory_hits}
        if len(state["intents"]) > 1:
            update["partial_answers"] = {"memory_agent": {
                "summary": "; ".join(memory_hits[:5]) or "no matching memory found",
                "confidence": (terms_with_hits / len(terms)) if terms else 0.0,
            }}
        return update

    def _next_after_specialist(state: AgentState) -> str:
        return "combiner" if len(state["intents"]) > 1 else "responder"

    def responder_node(state: AgentState) -> dict:
        intent = state["intent"]
        guidance_parts = []
        loaded_skills = []
        skill_name = _select_skill(intent, state["discovered_skills"], state["discovered_skill_scores"])
        if skill_name:
            guidance_parts.append(discovery.load_skill(skill_name))
            loaded_skills.append(skill_name)
        if any(kw in state["text"].lower() for kw in _TEMPORAL_KEYWORDS) and "memory-recall" not in loaded_skills:
            guidance_parts.append(discovery.load_skill("memory-recall"))
            loaded_skills.append("memory-recall")
        system = _RESPONDER_SYSTEM
        if guidance_parts:
            system = f"{system}\n\n" + "\n\n".join(guidance_parts)

        if intent == "query":
            results_text = "\n".join(state["query_results"]) or "(no results)"
            error_text = f"\nError: {state['query_error']}" if state["query_error"] else ""
            # PLAN: plans/nl-query-translation.md Slice 5. Included directly in
            # `user` (not a separate field) so _find_ungrounded_claims -- which
            # checks `reply` against this same `user` string -- doesn't flag a
            # stated query as an unsupported claim; no extra plumbing needed.
            translated_line = f"Query run: {state['translated_query']}\n" if state["translated_query"] else ""
            user = f"{translated_line}Query: {state['text']}\nResults:\n{results_text}{error_text}"
        elif intent == "enrich":
            facts_text = "\n".join(f"- {f}" for f in state["enrichment_fact_texts"]) or "(none found)"
            user = f"Implicit facts found by the 11 Polanyi heuristics:\n{facts_text}"
        elif intent == "recall":
            hits_text = "\n".join(f"- {h}" for h in state["memory_hits"]) or "(no matching memory found)"
            user = f"Memory search for: {state['text']}\nMatches:\n{hits_text}"
        elif intent == "analyze":
            scores_text = "\n".join(f"- {line}" for line in state["analytics_summary"]) or "(empty graph, nothing to analyze)"
            user = f"Degree centrality scores for the real graph, highest first:\n{scores_text}"
        elif intent == "visualize":
            record = graph_service.get_graph(neo4j, state["graph_id"])
            entities_text = "\n".join(f"- {n.label} ({n.type})" for n in record.nodes) or "(empty graph)"
            user = (
                f"The user wants to visualize/see an overview of the real graph "
                f"({len(record.nodes)} entities, {len(record.edges)} relationships):\n{entities_text}"
            )
        elif intent == "compound":
            user = (
                f"Sub-answers from multiple specialists for: {state['text']}\n\n{state['combined_answer']}\n\n"
                "Synthesize one coherent answer, and note which specialist each part of your answer relies on."
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

        try:
            reply = llm.complete_json(system=system, user=user)
            # 2026-07-13 plan §12.4 maker/checker split, generalized from
            # just the "compound" branch to EVERY responder reply (follow-up
            # request: apply the same Generate-Review-Act discipline to the
            # whole orchestrator, not one branch). The model that
            # synthesized `reply` isn't the one that checks it -- and `user`
            # already holds the real data this reply must be grounded in for
            # every intent (query results, derived facts, real entities,
            # memory hits, or combined sub-answers for compound), so the
            # same check generalizes with no new plumbing. Bounded to
            # exactly one retry, not an open-ended loop -- if the retry
            # still doesn't pass, its output is used as-is rather than
            # looping (this project's existing bias toward bounded,
            # deterministic control flow).
            if _find_ungrounded_claims(reply, user):
                reply = llm.complete_json(
                    system=system + "\n\nYour previous answer included claims not supported by the real data provided above. Only state what that data actually supports.",
                    user=user,
                )
        except Exception:
            for name in loaded_skills:
                discovery.record_usage(name, session_id=state["graph_id"], success=False)
            raise
        for name in loaded_skills:
            discovery.record_usage(name, session_id=state["graph_id"], success=True)
        return {"reply": reply}

    workflow = StateGraph(AgentState)
    workflow.add_node("router", router_node)
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("reasoner", reasoner_node)
    workflow.add_node("enricher", enricher_node)
    workflow.add_node("querier", querier_node)
    workflow.add_node("memory_agent", memory_agent_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("combiner", combiner_node)
    workflow.add_node("responder", responder_node)

    workflow.add_edge(START, "router")
    workflow.add_conditional_edges("router", route_by_intent, {
        "extract": "extractor",
        "enrich": "enricher",
        "query": "querier",
        "reason": "reasoner",
        "visualize": "responder",
        "recall": "memory_agent",
        "analyze": "analyst",
    })
    # extractor keeps its unconditional edge to reasoner -- extraction was
    # never part of the compound set (see _NODE_BY_INTENT's docstring), so
    # this path is always single-intent and len(intents) == 1 here.
    workflow.add_edge("extractor", "reasoner")
    # 2026-07-13 plan §5.6: each specialist's next hop depends on whether
    # this turn is compound (len(intents) > 1 -> combiner, a real join point
    # LangGraph waits at for every dispatched Send branch to finish) or
    # single-intent (-> responder, unchanged from pre-Feature-4 behavior).
    for node in ("reasoner", "querier", "enricher", "memory_agent", "analyst"):
        workflow.add_conditional_edges(node, _next_after_specialist, {"combiner": "combiner", "responder": "responder"})
    workflow.add_edge("combiner", "responder")
    workflow.add_edge("responder", END)

    return workflow.compile(checkpointer=InMemorySaver())
