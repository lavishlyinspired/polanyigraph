"""Natural-language -> predicate(subject, object) DSL translation (PLAN:
plans/nl-query-translation.md Slice 1). Mirrors extraction/pipeline.py's
real-LLM, schema-grounded pattern -- domain-agnostic, grounded in the live
OntologySchema and this graph's actually-used vocabulary, never hardcoded
examples. Few-shot examples are graph-native (:FewshotQuery nodes), same
shape decision as services/skill_graph_service.py's Neo4j-backed catalog.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from db.neo4j_client import Neo4jClient
from llm.client import LLMClient
from ontology.schema import OntologySchema
from services.chat_history_service import ChatMessageRecord
from services.query_engine import _parse_atom, _split_top_level_atoms

NL_QUERY_OUT_OF_SCOPE = "__NL_QUERY_OUT_OF_SCOPE__"

_SYSTEM_TEMPLATE = """You translate a user's natural-language question into the \
predicate(subject, object) query language for a knowledge graph, grounded ONLY in the \
real schema, predicates, and entities listed below -- never invent a predicate or entity \
that isn't listed.

Respond with ONLY the translated query, in the exact form predicate(subject, object), \
optionally joined by commas for conjunctive multi-atom queries. Subject/object are \
double-quoted literals or capitalized variables (X, Y, Z).

If the question cannot be answered using the predicates and entities listed below, \
respond with exactly: {sentinel}

Ontology classes: {classes}
Ontology properties: {properties}"""


@dataclass(frozen=True)
class FewshotQuery:
    question: str
    dsl: str


def is_dsl_syntax(text: str) -> bool:
    """Public: also used by agents/graph.py's querier_node to decide whether
    to skip translation entirely for text that's already valid DSL."""
    parts = _split_top_level_atoms(text.strip())
    if not parts:
        return False
    return all(_parse_atom(p) is not None for p in parts)


def _build_prompt(
    text: str,
    schema: OntologySchema,
    predicates: list[str],
    entity_labels: list[str],
    fewshot: list[FewshotQuery],
    history: list[ChatMessageRecord],
) -> tuple[str, str]:
    system = _SYSTEM_TEMPLATE.format(
        sentinel=NL_QUERY_OUT_OF_SCOPE,
        classes=", ".join(c.label for c in schema.classes) or "(none)",
        properties=", ".join(p.label for p in schema.properties) or "(none)",
    )

    user_parts = [
        f"Predicates currently used in this graph: {', '.join(predicates) or '(none)'}",
        f"Entities currently in this graph: {', '.join(entity_labels) or '(none)'}",
    ]
    if fewshot:
        examples_text = "\n".join(f'Q: {ex.question}\nA: {ex.dsl}' for ex in fewshot)
        user_parts.append(f"Examples:\n{examples_text}")
    if history:
        history_text = "\n".join(f"{h.role}: {h.content}" for h in history)
        user_parts.append(f"Conversation so far:\n{history_text}")
    user_parts.append(f"Question: {text}")

    return system, "\n\n".join(user_parts)


def translate_to_dsl(
    text: str,
    *,
    schema: OntologySchema,
    predicates: list[str],
    entity_labels: list[str],
    fewshot: list[FewshotQuery],
    history: list[ChatMessageRecord],
    llm: LLMClient,
) -> str:
    """Bounded, exactly-one-retry generation (PLAN: plans/nl-query-translation.md
    Slice 3). Since is_dsl_syntax already gates everything this function
    returns, a translated query can never fail execute_query's own syntax
    check downstream -- the real, testable "does the parser reject this"
    signal lives here, at generation time, not at querier_node's
    execute_query call. The retry feeds the literal failed response back,
    the closest available analogue to "the parser's real error" this
    architecture has (there's no separate execute_query-level error to
    reuse, since this function never hands back anything execute_query
    would reject)."""
    system, user = _build_prompt(text, schema, predicates, entity_labels, fewshot, history)
    raw = llm.complete_json(system=system, user=user).strip()
    if raw == NL_QUERY_OUT_OF_SCOPE:
        return NL_QUERY_OUT_OF_SCOPE
    if is_dsl_syntax(raw):
        return raw

    retry_user = (
        f"{user}\n\nYour previous response, {raw!r}, did not parse as valid "
        f"predicate(subject, object) syntax. Respond with ONLY a syntactically "
        f"valid query, or exactly {NL_QUERY_OUT_OF_SCOPE} if genuinely out of scope."
    )
    retry_raw = llm.complete_json(system=system, user=retry_user).strip()
    if retry_raw == NL_QUERY_OUT_OF_SCOPE:
        return NL_QUERY_OUT_OF_SCOPE
    if is_dsl_syntax(retry_raw):
        return retry_raw
    return NL_QUERY_OUT_OF_SCOPE


def get_fewshot_examples(neo4j: Neo4jClient, repository: str) -> list[FewshotQuery]:
    rows = neo4j.run(
        "MATCH (f:FewshotQuery {repository: $repository}) RETURN f.question AS question, f.dsl AS dsl",
        repository=repository,
    )
    return [FewshotQuery(question=r["question"], dsl=r["dsl"]) for r in rows]


def seed_fewshot_examples(neo4j: Neo4jClient, repository: str, examples: list[FewshotQuery]) -> None:
    for ex in examples:
        neo4j.run(
            "MERGE (f:FewshotQuery {repository: $repository, question: $question}) SET f.dsl = $dsl",
            repository=repository,
            question=ex.question,
            dsl=ex.dsl,
        )


# PLAN Slice 4: minimum repeat successes before the low-friction implicit
# signal (repeated identical questions that keep succeeding) auto-promotes
# a translation into the few-shot set -- deliberately higher than 1, since
# that signal is weaker than an explicit thumbs-up (which promotes
# immediately, no threshold).
_MIN_REPEAT_SUCCESSES_FOR_IMPLICIT_PROMOTION = 3


def log_translation(neo4j: Neo4jClient, *, repository: str, question: str, dsl: str, outcome: str) -> str:
    """CREATEs a distinct :TranslatedQuery node per attempt (not MERGE --
    the plan's original wording said MERGE, but a usage log needs one node
    per attempt for maybe_promote_on_repeat_success's counting to mean
    anything; MERGE-deduping on {repository, question} would collapse every
    repeat attempt into a single node and always count as 1). Returns the
    new node's id."""
    query_id = f"{repository}:{uuid.uuid4().hex[:12]}"
    neo4j.run(
        """
        CREATE (t:TranslatedQuery {
            id: $id, repository: $repository, question: $question, dsl: $dsl,
            outcome: $outcome, at: datetime()
        })
        """,
        id=query_id,
        repository=repository,
        question=question,
        dsl=dsl,
        outcome=outcome,
    )
    return query_id


def record_feedback(neo4j: Neo4jClient, translated_query_id: str, *, liked: bool, correction: str | None = None) -> None:
    """Explicit thumbs-up/down. liked=True promotes immediately -- the only
    feedback path that promotes without a repeat-count threshold, since an
    explicit human confirmation is a stronger signal than repeated implicit
    success."""
    neo4j.run(
        "MATCH (t:TranslatedQuery {id: $id}) SET t.liked = $liked, t.correction = $correction",
        id=translated_query_id,
        liked=liked,
        correction=correction,
    )
    if liked:
        rows = neo4j.run("MATCH (t:TranslatedQuery {id: $id}) RETURN t.repository AS repository", id=translated_query_id)
        if rows:
            promote_to_fewshot(neo4j, rows[0]["repository"], translated_query_id)


def promote_to_fewshot(neo4j: Neo4jClient, repository: str, translated_query_id: str) -> bool:
    rows = neo4j.run(
        "MATCH (t:TranslatedQuery {id: $id, repository: $repository}) RETURN t.question AS question, t.dsl AS dsl",
        id=translated_query_id,
        repository=repository,
    )
    if not rows:
        return False
    seed_fewshot_examples(neo4j, repository, [FewshotQuery(question=rows[0]["question"], dsl=rows[0]["dsl"])])
    return True


def maybe_promote_on_repeat_success(neo4j: Neo4jClient, repository: str, translated_query_id: str, question: str) -> bool:
    """Implicit-signal auto-promotion path: only promotes once this exact
    question has succeeded at least _MIN_REPEAT_SUCCESSES_FOR_IMPLICIT_PROMOTION
    times for this repository. A single implicit success is deliberately
    never enough on its own."""
    rows = neo4j.run(
        "MATCH (t:TranslatedQuery {repository: $repository, question: $question, outcome: 'succeeded'}) RETURN count(t) AS n",
        repository=repository,
        question=question,
    )
    count = rows[0]["n"] if rows else 0
    if count < _MIN_REPEAT_SUCCESSES_FOR_IMPLICIT_PROMOTION:
        return False
    return promote_to_fewshot(neo4j, repository, translated_query_id)
