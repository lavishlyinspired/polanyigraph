"""StorageCommand: the backend-neutral instruction plan_materialization's
decision is converted into before being executed by a GraphClient (PLAN
Phase 3 design doc's "Storage Adapter Pattern"). v1 only ever constructs
SET_PROPERTY -- NODE-policy entities still go through services/graph_service.py's
existing upsert_entity/upsert_relationship untouched, per the design doc's
explicit non-goal of not retrofitting already-working Neo4j-coupled code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StorageCommand:
    operation: str
    subject_id: str
    key: str | None = None
    value: Any = None
