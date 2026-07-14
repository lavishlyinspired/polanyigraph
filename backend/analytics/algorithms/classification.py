"""Node classification: predicts a likely `type` for nodes with low
extraction_confidence or no ontology mapping, from graph structure and
existing labels (PLAN: plans/analytical-engine.md Slice 6).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True)
class Prediction:
    node_id: str
    predicted_type: str
    confidence: float


def majority_vote_classification(graph: nx.DiGraph, labeled_nodes: dict[str, str]) -> dict[str, Prediction]:
    undirected = graph.to_undirected()
    predictions: dict[str, Prediction] = {}
    for node in graph.nodes:
        if node in labeled_nodes:
            predictions[node] = Prediction(node_id=node, predicted_type=labeled_nodes[node], confidence=1.0)
            continue
        neighbor_labels = [labeled_nodes[n] for n in undirected.neighbors(node) if n in labeled_nodes]
        if not neighbor_labels:
            predictions[node] = Prediction(node_id=node, predicted_type="unknown", confidence=0.0)
            continue
        predicted_type, count = Counter(neighbor_labels).most_common(1)[0]
        predictions[node] = Prediction(node_id=node, predicted_type=predicted_type, confidence=count / len(neighbor_labels))
    return predictions


def feature_based_classification(
    graph: nx.DiGraph, features: dict[str, dict[str, float]], labels: dict[str, str]
) -> dict[str, Prediction]:
    """Nearest-neighbor (k=1, Euclidean over shared feature keys) using
    labeled nodes as reference points. `features` is caller-supplied --
    typically a node's properties dict merged with structural features
    (degree, clustering coefficient) the caller computed."""
    labeled_feature_vectors = [(node, features[node]) for node in labels if node in features]
    predictions: dict[str, Prediction] = {}
    for node in graph.nodes:
        if node in labels:
            predictions[node] = Prediction(node_id=node, predicted_type=labels[node], confidence=1.0)
            continue
        node_vec = features.get(node)
        if node_vec is None or not labeled_feature_vectors:
            predictions[node] = Prediction(node_id=node, predicted_type="unknown", confidence=0.0)
            continue
        distances = []
        for other_node, other_vec in labeled_feature_vectors:
            shared_keys = set(node_vec) & set(other_vec)
            if not shared_keys:
                continue
            distance = math.sqrt(sum((node_vec[k] - other_vec[k]) ** 2 for k in shared_keys))
            distances.append((distance, other_node))
        if not distances:
            predictions[node] = Prediction(node_id=node, predicted_type="unknown", confidence=0.0)
            continue
        nearest_distance, nearest_node = min(distances, key=lambda d: d[0])
        predictions[node] = Prediction(
            node_id=node, predicted_type=labels[nearest_node], confidence=1.0 / (1.0 + nearest_distance)
        )
    return predictions
