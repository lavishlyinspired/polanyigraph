"""Pure-logic tests for analytics/roles.py -- Analytics Role Mapping (PLAN:
Phase 1, follow-up work agreed 2026-07-14 after live-testing the analytics
engine surfaced date/percentage entities dominating "most central entity"
rankings in the real FIBO-backed graph).

A small universal role taxonomy (actor/event/value/temporal/metadata) is
mapped per-ontology-repository to a handful of real ontology "anchor"
classes; any class that IS-A an anchor (reflexively or transitively, via the
same build_subclass_matcher() reasoning already uses) inherits that anchor's
role. Centrality algorithms multiply a node's raw score by its role's
weight -- zeroing out Value/Temporal/Metadata noise without altering graph
topology, so path-based algorithms (betweenness) still route through those
nodes correctly if the real topology needs to.
"""

from __future__ import annotations

import networkx as nx

from analytics.roles import (
    ROLE_ANCHORS_BY_REPOSITORY,
    AnalyticsRole,
    apply_role_weights,
    apply_role_weights_if_centrality,
    build_role_resolver,
    resolver_for_repository,
)
from ontology.schema import OntologyClass, OntologySchema


def _fibo_like_schema() -> OntologySchema:
    # rate of return <- percentage <- quantity value  (matches real FIBO shape)
    # date <- time instant
    # organization has no ontology-anchor ancestor at all
    return OntologySchema(
        repository="fibo",
        classes=[
            OntologyClass(uri="urn:qv", label="quantity value"),
            OntologyClass(uri="urn:pct", label="percentage"),
            OntologyClass(uri="urn:ror", label="rate of return"),
            OntologyClass(uri="urn:ti", label="time instant"),
            OntologyClass(uri="urn:date", label="date"),
            OntologyClass(uri="urn:org", label="organization"),
        ],
        properties=[],
        subclass_of=[
            ("urn:pct", "urn:qv"),
            ("urn:ror", "urn:pct"),
            ("urn:date", "urn:ti"),
        ],
    )


# --- build_role_resolver ----------------------------------------------------

def test_resolver_matches_the_anchor_class_itself():
    schema = _fibo_like_schema()
    resolve = build_role_resolver(schema, {"quantity value": AnalyticsRole.VALUE})

    assert resolve("quantity value") == AnalyticsRole.VALUE


def test_resolver_matches_a_transitive_subclass_of_the_anchor():
    schema = _fibo_like_schema()
    resolve = build_role_resolver(schema, {"quantity value": AnalyticsRole.VALUE})

    assert resolve("rate of return") == AnalyticsRole.VALUE


def test_resolver_matches_a_different_anchor_for_a_different_branch():
    schema = _fibo_like_schema()
    resolve = build_role_resolver(
        schema, {"quantity value": AnalyticsRole.VALUE, "time instant": AnalyticsRole.TEMPORAL}
    )

    assert resolve("date") == AnalyticsRole.TEMPORAL


def test_resolver_returns_none_for_a_type_with_no_matching_anchor():
    schema = _fibo_like_schema()
    resolve = build_role_resolver(schema, {"quantity value": AnalyticsRole.VALUE})

    assert resolve("organization") is None


def test_resolver_returns_none_for_empty_node_type():
    schema = _fibo_like_schema()
    resolve = build_role_resolver(schema, {"quantity value": AnalyticsRole.VALUE})

    assert resolve("") is None


def test_resolver_with_no_anchors_configured_always_returns_none():
    schema = _fibo_like_schema()
    resolve = build_role_resolver(schema, {})

    assert resolve("rate of return") is None


# --- resolver_for_repository -----------------------------------------------

def test_resolver_for_repository_uses_the_real_fibo_anchors():
    schema = _fibo_like_schema()
    resolve = resolver_for_repository(schema)

    assert resolve("rate of return") == AnalyticsRole.VALUE
    assert resolve("date") == AnalyticsRole.TEMPORAL
    assert resolve("organization") is None


def test_resolver_for_repository_fails_open_for_an_unmapped_repository():
    """A repository this codebase hasn't been configured with real anchors
    for yet must behave exactly like today (no weighting at all) -- fails
    open the same way build_domain_range_matcher() does for unknown
    properties, so an unconfigured ontology never gets its centrality
    rankings silently altered."""
    schema = _fibo_like_schema().model_copy(update={"repository": "some-other-ontology"})
    resolve = resolver_for_repository(schema)

    assert resolve("rate of return") is None
    assert resolve("date") is None


def test_fibo_anchors_are_registered():
    assert ROLE_ANCHORS_BY_REPOSITORY["fibo"] == {
        "quantity value": AnalyticsRole.VALUE,
        "time instant": AnalyticsRole.TEMPORAL,
    }


# --- apply_role_weights ------------------------------------------------------

def _graph_with_types(types: dict[str, str]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for node_id, node_type in types.items():
        graph.add_node(node_id, type=node_type)
    return graph


def test_apply_role_weights_zeroes_out_value_role_scores():
    graph = _graph_with_types({"hdfc-bank": "organization", "8-45-percent": "rate of return"})
    scores = {"hdfc-bank": 0.32, "8-45-percent": 0.04}
    resolve = build_role_resolver(_fibo_like_schema(), {"quantity value": AnalyticsRole.VALUE})

    weighted = apply_role_weights(scores, graph, resolve)

    assert weighted["8-45-percent"] == 0.0
    assert weighted["hdfc-bank"] == 0.32


def test_apply_role_weights_zeroes_out_temporal_role_scores():
    graph = _graph_with_types({"hdfc-bank": "organization", "august-5-2026": "date"})
    scores = {"hdfc-bank": 0.32, "august-5-2026": 0.04}
    resolve = build_role_resolver(_fibo_like_schema(), {"time instant": AnalyticsRole.TEMPORAL})

    weighted = apply_role_weights(scores, graph, resolve)

    assert weighted["august-5-2026"] == 0.0
    assert weighted["hdfc-bank"] == 0.32


def test_apply_role_weights_leaves_unresolved_role_nodes_unweighted():
    graph = _graph_with_types({"hdfc-bank": "organization"})
    scores = {"hdfc-bank": 0.32}
    resolve = build_role_resolver(_fibo_like_schema(), {"quantity value": AnalyticsRole.VALUE})

    weighted = apply_role_weights(scores, graph, resolve)

    assert weighted["hdfc-bank"] == 0.32


def test_apply_role_weights_defaults_to_unweighted_for_a_role_missing_from_a_custom_table():
    """A caller-supplied role_weights table that only covers some roles must
    not silently suppress a resolved role it doesn't mention."""
    graph = _graph_with_types({"hdfc-bank": "organization"})
    scores = {"hdfc-bank": 0.32}
    resolve = build_role_resolver(_fibo_like_schema(), {"organization": AnalyticsRole.ACTOR})

    weighted = apply_role_weights(scores, graph, resolve, role_weights={AnalyticsRole.VALUE: 0.0})

    assert weighted["hdfc-bank"] == 0.32


def test_apply_role_weights_uses_a_custom_weight_table():
    graph = _graph_with_types({"acme-launch": "event"})
    scores = {"acme-launch": 0.5}
    resolve = build_role_resolver(_fibo_like_schema(), {"event": AnalyticsRole.EVENT})

    weighted = apply_role_weights(scores, graph, resolve, role_weights={AnalyticsRole.EVENT: 0.25})

    assert weighted["acme-launch"] == 0.125


# --- apply_role_weights_if_centrality ---------------------------------------

def test_apply_role_weights_if_centrality_weights_a_centrality_result():
    schema = _fibo_like_schema()
    graph = _graph_with_types({"hdfc-bank": "organization", "8-45-percent": "rate of return"})
    scores = {"hdfc-bank": 0.32, "8-45-percent": 0.04}

    weighted = apply_role_weights_if_centrality(scores, graph, "centrality", schema)

    assert weighted["8-45-percent"] == 0.0
    assert weighted["hdfc-bank"] == 0.32


def test_apply_role_weights_if_centrality_leaves_non_centrality_categories_untouched():
    schema = _fibo_like_schema()
    graph = _graph_with_types({"8-45-percent": "rate of return"})
    scores = {"8-45-percent": 0.04}

    weighted = apply_role_weights_if_centrality(scores, graph, "community", schema)

    assert weighted["8-45-percent"] == 0.04


def test_apply_role_weights_if_centrality_leaves_scores_untouched_when_no_schema_available():
    graph = _graph_with_types({"8-45-percent": "rate of return"})
    scores = {"8-45-percent": 0.04}

    weighted = apply_role_weights_if_centrality(scores, graph, "centrality", None)

    assert weighted["8-45-percent"] == 0.04
