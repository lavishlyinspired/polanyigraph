"""Pure-logic tests for the structured triple query engine (no DB needed).

Ported from the prototype's executeQuery (engine.ts) with the same query
language: predicate(subject, object), where subject/object are quoted literals
or variables (X/Y/Z/_), and comma-separated atoms are conjunctive joins.
"""

from __future__ import annotations

from services.query_engine import Triple, execute_query


def _triples():
    return [
        Triple(subject="Acme Corp", predicate="issues", object="Acme Preferred Stock", derived=False, confidence=1.0),
        Triple(subject="Acme Corp", predicate="is regulated by", object="FINMA", derived=False, confidence=1.0),
        Triple(subject="Acme Corp", predicate="is domiciled in", object="Switzerland", derived=True, confidence=0.6),
    ]


def test_single_atom_literal_subject():
    result = execute_query('is regulated by("Acme Corp", X)', _triples())
    assert result.error is None
    assert [r.object for r in result.results] == ["FINMA"]


def test_single_atom_no_match_returns_empty_not_error():
    result = execute_query('issues("Nobody", X)', _triples())
    assert result.error is None
    assert result.results == []


def test_conjunctive_join_binds_shared_variable():
    query = 'issues("Acme Corp", Y), is regulated by("Acme Corp", X)'
    result = execute_query(query, _triples())
    assert result.error is None
    assert len(result.results) == 1


def test_invalid_syntax_reports_error():
    result = execute_query("not a valid query", _triples())
    assert result.error is not None
    assert result.results == []


def test_empty_query_reports_error():
    result = execute_query("   ", _triples())
    assert result.error is not None


def test_derived_flag_and_confidence_carried_through():
    result = execute_query('is domiciled in("Acme Corp", X)', _triples())
    assert result.results[0].derived is True
    assert result.results[0].confidence == 0.6
