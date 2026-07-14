"""Tests for services/nl_query_service.py (PLAN: plans/nl-query-translation.md
Slice 1). LLM is injected (a fake), matching test_extraction.py's pattern for
extract() -- no network for the unit tests. get_fewshot_examples/
seed_fewshot_examples run against a real Neo4j instance, matching this
repo's "no mocking the store itself" convention.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from ontology.schema import OntologyClass, OntologyProperty, OntologySchema
from services.chat_history_service import ChatMessageRecord
from services.nl_query_service import (
    NL_QUERY_OUT_OF_SCOPE,
    FewshotQuery,
    get_fewshot_examples,
    is_dsl_syntax,
    log_translation,
    maybe_promote_on_repeat_success,
    promote_to_fewshot,
    record_feedback,
    seed_fewshot_examples,
    translate_to_dsl,
)


def test_is_dsl_syntax_accepts_a_single_atom_query():
    assert is_dsl_syntax('regulates("FINMA", X)') is True


def test_is_dsl_syntax_accepts_a_conjunctive_query():
    assert is_dsl_syntax('regulates("FINMA", X), hasDomicile(X, "Zurich")') is True


def test_is_dsl_syntax_rejects_plain_english():
    assert is_dsl_syntax("who does FINMA regulate?") is False


def test_is_dsl_syntax_rejects_empty_text():
    assert is_dsl_syntax("") is False


class FakeLLM:
    def __init__(self, response: str | None = None, *, responses: list[str] | None = None) -> None:
        self._responses = list(responses) if responses is not None else [response]
        self.last_call: dict[str, str] | None = None
        self.calls: list[dict[str, str]] = []

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_call = {"system": system, "user": user}
        self.calls.append(self.last_call)
        # Pops in order for retry tests; holds the last entry once exhausted,
        # same convention as test_agent_graph.py's FakeLLM._replies.
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]


def _schema() -> OntologySchema:
    return OntologySchema(
        repository="fibo",
        classes=[
            OntologyClass(uri="urn:organization", label="organization"),
            OntologyClass(uri="urn:regulator", label="regulator"),
        ],
        properties=[OntologyProperty(uri="urn:regulates", label="regulates")],
    )


def test_translate_to_dsl_makes_no_retry_when_the_first_attempt_is_valid():
    llm = FakeLLM('regulates("FINMA", X)')

    result = translate_to_dsl(
        "who does FINMA regulate?",
        schema=_schema(), predicates=["regulates"], entity_labels=["FINMA"],
        fewshot=[], history=[], llm=llm,
    )

    assert result == 'regulates("FINMA", X)'
    assert len(llm.calls) == 1


def test_translate_to_dsl_retries_once_and_succeeds_on_the_retry():
    llm = FakeLLM(responses=["not valid dsl at all", 'regulates("FINMA", X)'])

    result = translate_to_dsl(
        "who does FINMA regulate?",
        schema=_schema(), predicates=["regulates"], entity_labels=["FINMA"],
        fewshot=[], history=[], llm=llm,
    )

    assert result == 'regulates("FINMA", X)'
    assert len(llm.calls) == 2
    # The literal failed first response is fed back into the retry prompt.
    assert "not valid dsl at all" in llm.calls[1]["user"]


def test_translate_to_dsl_falls_back_to_out_of_scope_when_both_attempts_fail():
    llm = FakeLLM(responses=["still not valid", "nope still not valid either"])

    result = translate_to_dsl(
        "who does FINMA regulate?",
        schema=_schema(), predicates=["regulates"], entity_labels=["FINMA"],
        fewshot=[], history=[], llm=llm,
    )

    assert result == NL_QUERY_OUT_OF_SCOPE
    assert len(llm.calls) == 2


def test_translate_to_dsl_returns_a_syntactically_valid_single_atom_query():
    llm = FakeLLM('regulates("FINMA", X)')

    result = translate_to_dsl(
        "who does FINMA regulate?",
        schema=_schema(), predicates=["regulates"], entity_labels=["FINMA"],
        fewshot=[], history=[], llm=llm,
    )

    assert result == 'regulates("FINMA", X)'


def test_translate_to_dsl_returns_a_syntactically_valid_conjunctive_query():
    llm = FakeLLM('regulates("FINMA", X), hasDomicile(X, "Zurich")')

    result = translate_to_dsl(
        "what does FINMA regulate that is domiciled in Zurich?",
        schema=_schema(), predicates=["regulates", "hasDomicile"], entity_labels=["FINMA", "Zurich"],
        fewshot=[], history=[], llm=llm,
    )

    assert result == 'regulates("FINMA", X), hasDomicile(X, "Zurich")'


def test_translate_to_dsl_returns_out_of_scope_sentinel_when_llm_says_so():
    llm = FakeLLM(NL_QUERY_OUT_OF_SCOPE)

    result = translate_to_dsl(
        "what's the weather like today?",
        schema=_schema(), predicates=["regulates"], entity_labels=["FINMA"],
        fewshot=[], history=[], llm=llm,
    )

    assert result == NL_QUERY_OUT_OF_SCOPE


def test_translate_to_dsl_returns_out_of_scope_sentinel_for_unparseable_llm_output():
    """Never hand back unparseable output as if it succeeded, even if the LLM
    didn't explicitly say out-of-scope."""
    llm = FakeLLM("I'm not sure what you mean by that.")

    result = translate_to_dsl(
        "huh?",
        schema=_schema(), predicates=["regulates"], entity_labels=["FINMA"],
        fewshot=[], history=[], llm=llm,
    )

    assert result == NL_QUERY_OUT_OF_SCOPE


def test_translate_to_dsl_returns_out_of_scope_sentinel_for_an_empty_llm_response():
    """An empty string parses as zero atoms -- vacuously "all valid" if the
    empty-parts case isn't guarded explicitly. Must not be treated as a
    valid (empty) query."""
    llm = FakeLLM("")

    result = translate_to_dsl(
        "??",
        schema=_schema(), predicates=["regulates"], entity_labels=["FINMA"],
        fewshot=[], history=[], llm=llm,
    )

    assert result == NL_QUERY_OUT_OF_SCOPE


def test_translate_to_dsl_grounds_the_prompt_in_real_schema_and_vocabulary_not_hardcoded_examples():
    llm = FakeLLM('regulates("FINMA", X)')

    translate_to_dsl(
        "who does FINMA regulate?",
        schema=_schema(), predicates=["regulates"], entity_labels=["FINMA"],
        fewshot=[FewshotQuery(question="who owns Acme?", dsl='owns(X, "Acme")')],
        history=[ChatMessageRecord(role="user", content="tell me about FINMA", created_at="2026-01-01T00:00:00Z")],
        llm=llm,
    )

    assert "regulator" in llm.last_call["system"]  # real schema class label
    assert "regulates" in llm.last_call["user"]  # real predicate vocabulary
    assert "who owns Acme?" in llm.last_call["user"]  # real stored few-shot example
    assert "tell me about FINMA" in llm.last_call["user"]  # real conversation history


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    repository = f"test-repo-{uuid.uuid4().hex[:8]}"
    yield client, repository
    client.run("MATCH (f:FewshotQuery {repository: $repository}) DETACH DELETE f", repository=repository)
    client.run("MATCH (t:TranslatedQuery {repository: $repository}) DETACH DELETE t", repository=repository)
    client.close()


def test_seed_and_get_fewshot_examples_round_trip(neo4j):
    client, repository = neo4j
    examples = [
        FewshotQuery(question="who regulates FINMA?", dsl='regulates(X, "FINMA")'),
        FewshotQuery(question="who owns Acme?", dsl='owns(X, "Acme")'),
    ]

    seed_fewshot_examples(client, repository, examples)
    result = get_fewshot_examples(client, repository)

    assert {e.question for e in result} == {"who regulates FINMA?", "who owns Acme?"}
    by_question = {e.question: e.dsl for e in result}
    assert by_question["who regulates FINMA?"] == 'regulates(X, "FINMA")'


def test_seed_fewshot_examples_is_idempotent(neo4j):
    client, repository = neo4j
    example = FewshotQuery(question="who regulates FINMA?", dsl='regulates(X, "FINMA")')

    seed_fewshot_examples(client, repository, [example])
    seed_fewshot_examples(client, repository, [example])

    result = get_fewshot_examples(client, repository)
    assert len(result) == 1


def test_get_fewshot_examples_is_scoped_to_repository(neo4j):
    client, repository = neo4j
    other_repository = f"{repository}-other"
    seed_fewshot_examples(client, repository, [FewshotQuery(question="q1", dsl='p(X, "a")')])
    try:
        seed_fewshot_examples(client, other_repository, [FewshotQuery(question="q2", dsl='p(X, "b")')])
        result = get_fewshot_examples(client, repository)
        assert {e.question for e in result} == {"q1"}
    finally:
        client.run("MATCH (f:FewshotQuery {repository: $repository}) DETACH DELETE f", repository=other_repository)


def test_log_translation_creates_a_distinct_node_per_attempt(neo4j):
    """CREATE, not MERGE -- a usage log needs one node per attempt so
    repeat-success counting (maybe_promote_on_repeat_success) has something
    to count. Two identical logged attempts must be two distinct nodes."""
    client, repository = neo4j

    id1 = log_translation(client, repository=repository, question="who regulates FINMA?", dsl='regulates(X, "FINMA")', outcome="succeeded")
    id2 = log_translation(client, repository=repository, question="who regulates FINMA?", dsl='regulates(X, "FINMA")', outcome="succeeded")

    assert id1 != id2
    rows = client.run(
        "MATCH (t:TranslatedQuery {repository: $repository, question: $question}) RETURN count(t) AS n",
        repository=repository, question="who regulates FINMA?",
    )
    assert rows[0]["n"] == 2


def test_record_feedback_with_liked_true_promotes_to_fewshot(neo4j):
    client, repository = neo4j
    query_id = log_translation(client, repository=repository, question="who owns Acme?", dsl='owns(X, "Acme")', outcome="succeeded")

    record_feedback(client, query_id, liked=True)

    result = get_fewshot_examples(client, repository)
    assert any(e.question == "who owns Acme?" and e.dsl == 'owns(X, "Acme")' for e in result)


def test_record_feedback_with_liked_false_does_not_promote(neo4j):
    client, repository = neo4j
    query_id = log_translation(client, repository=repository, question="who owns Acme?", dsl='owns(X, "Acme")', outcome="succeeded")

    record_feedback(client, query_id, liked=False)

    result = get_fewshot_examples(client, repository)
    assert result == []


def test_record_feedback_stores_an_optional_correction(neo4j):
    client, repository = neo4j
    query_id = log_translation(client, repository=repository, question="who owns Acme?", dsl='owns(X, "Ac")', outcome="succeeded")

    record_feedback(client, query_id, liked=False, correction='owns(X, "Acme")')

    rows = client.run("MATCH (t:TranslatedQuery {id: $id}) RETURN t.correction AS correction", id=query_id)
    assert rows[0]["correction"] == 'owns(X, "Acme")'


def test_promote_to_fewshot_returns_false_for_an_unknown_query_id(neo4j):
    client, repository = neo4j

    promoted = promote_to_fewshot(client, repository, "does-not-exist")

    assert promoted is False


def test_maybe_promote_on_repeat_success_does_not_promote_on_a_single_implicit_success(neo4j):
    """The core "don't promote on implicit signal alone" boundary: one
    logged success is not enough."""
    client, repository = neo4j
    query_id = log_translation(client, repository=repository, question="who owns Acme?", dsl='owns(X, "Acme")', outcome="succeeded")

    promoted = maybe_promote_on_repeat_success(client, repository, query_id, "who owns Acme?")

    assert promoted is False
    assert get_fewshot_examples(client, repository) == []


def test_maybe_promote_on_repeat_success_promotes_once_the_threshold_is_cleared(neo4j):
    client, repository = neo4j
    last_id = ""
    for _ in range(3):
        last_id = log_translation(client, repository=repository, question="who owns Acme?", dsl='owns(X, "Acme")', outcome="succeeded")

    promoted = maybe_promote_on_repeat_success(client, repository, last_id, "who owns Acme?")

    assert promoted is True
    result = get_fewshot_examples(client, repository)
    assert any(e.question == "who owns Acme?" for e in result)


def test_maybe_promote_on_repeat_success_only_counts_succeeded_outcomes(neo4j):
    client, repository = neo4j
    for _ in range(3):
        log_translation(client, repository=repository, question="who owns Acme?", dsl='owns(X, "Acme")', outcome="failed")
    last_id = log_translation(client, repository=repository, question="who owns Acme?", dsl='owns(X, "Acme")', outcome="succeeded")

    promoted = maybe_promote_on_repeat_success(client, repository, last_id, "who owns Acme?")

    assert promoted is False
