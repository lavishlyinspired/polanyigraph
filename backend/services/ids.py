"""Shared entity/edge id slugging.

Both extraction (services/ingest_service.py) and manual construction
(api/graph.py add-node/add-edge) must derive the same id from the same
label/graph_id -- that's what makes a manually-added "Acme Corp" MERGE with
an extracted "Acme Corp" instead of creating a duplicate node.
"""

from __future__ import annotations

import re


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def entity_id(graph_id: str, label: str) -> str:
    return f"{graph_id}:{slug(label)}"


def edge_id(graph_id: str, source_label: str, relation: str, target_label: str) -> str:
    return f"{graph_id}:{slug(source_label)}->{slug(relation)}->{slug(target_label)}"
