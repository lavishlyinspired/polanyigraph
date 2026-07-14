"""Unit tests for analytics/algorithms/classification.py (pure, no DB)."""

from __future__ import annotations

from analytics.algorithms.classification import feature_based_classification, majority_vote_classification
from analytics.projection import build_graph
from services.graph_service import GraphEdgeRecord, GraphNodeRecord


def test_majority_vote_predicts_type_from_neighbor_majority():
    """Unlabeled node "u" has 2 "organization" neighbors and 1 "person"
    neighbor -- majority vote predicts organization, confidence 2/3."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("u", "org1", "org2", "person1")]
    edges = [
        GraphEdgeRecord(id="e1", source="u", target="org1", type="rel"),
        GraphEdgeRecord(id="e2", source="u", target="org2", type="rel"),
        GraphEdgeRecord(id="e3", source="u", target="person1", type="rel"),
    ]
    graph = build_graph(nodes, edges)
    labeled = {"org1": "organization", "org2": "organization", "person1": "person"}

    predictions = majority_vote_classification(graph, labeled)

    assert predictions["u"].predicted_type == "organization"
    assert abs(predictions["u"].confidence - 2 / 3) < 1e-9


def test_majority_vote_returns_existing_label_unchanged_for_labeled_nodes():
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a", "b")]
    graph = build_graph(nodes, [])
    labeled = {"a": "organization", "b": "person"}

    predictions = majority_vote_classification(graph, labeled)

    assert predictions["a"].predicted_type == "organization"
    assert predictions["a"].confidence == 1.0
    assert predictions["b"].predicted_type == "person"
    assert predictions["b"].confidence == 1.0


def test_majority_vote_on_a_fully_labeled_graph_overwrites_nothing():
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a", "b")]
    edges = [GraphEdgeRecord(id="e1", source="a", target="b", type="rel")]
    graph = build_graph(nodes, edges)
    labeled = {"a": "organization", "b": "person"}

    predictions = majority_vote_classification(graph, labeled)

    assert {p.predicted_type for p in predictions.values()} == {"organization", "person"}
    assert all(p.confidence == 1.0 for p in predictions.values())


def test_majority_vote_node_with_no_labeled_neighbors_is_unknown():
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("isolated", "labeled")]
    graph = build_graph(nodes, [])
    labeled = {"labeled": "organization"}

    predictions = majority_vote_classification(graph, labeled)

    assert predictions["isolated"].predicted_type == "unknown"
    assert predictions["isolated"].confidence == 0.0


def test_feature_based_classification_predicts_from_nearest_labeled_neighbor():
    """Node "u" has degree-2 structural feature, matching org1 (degree 2)
    much more closely than person1 (degree 10) -- nearest neighbor should
    predict organization."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("u", "org1", "person1")]
    graph = build_graph(nodes, [])
    features = {
        "u": {"degree": 2.0},
        "org1": {"degree": 2.0},
        "person1": {"degree": 10.0},
    }
    labels = {"org1": "organization", "person1": "person"}

    predictions = feature_based_classification(graph, features, labels)

    assert predictions["u"].predicted_type == "organization"
    assert predictions["u"].confidence > 0.0


def test_feature_based_classification_returns_existing_label_unchanged_for_labeled_nodes():
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a", "b")]
    graph = build_graph(nodes, [])
    features = {"a": {"degree": 1.0}, "b": {"degree": 5.0}}
    labels = {"a": "organization", "b": "person"}

    predictions = feature_based_classification(graph, features, labels)

    assert predictions["a"].predicted_type == "organization"
    assert predictions["a"].confidence == 1.0


def test_feature_based_classification_with_no_features_is_unknown():
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("u", "org1")]
    graph = build_graph(nodes, [])
    labels = {"org1": "organization"}

    predictions = feature_based_classification(graph, features={}, labels=labels)

    assert predictions["u"].predicted_type == "unknown"
    assert predictions["u"].confidence == 0.0
