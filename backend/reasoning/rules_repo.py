"""Load reasoning rules from a hand-authored JSON file.

Per docs/MVP_PLAN.md §11: rules are hand-authored per ontology repository
rather than derived automatically, since a small curated rule set is faster to
ship and easier to validate for MVP. `data/rules/fibo_rules.json` references
real FIBO vocabulary (confirmed against the live repository), not placeholders.
Swapping domains means authoring a new rules file, not writing code.
"""

from __future__ import annotations

import json
from pathlib import Path

from reasoning.engine import Rule

DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "rules" / "fibo_rules.json"


def load_rules(path: Path = DEFAULT_RULES_PATH) -> list[Rule]:
    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")
    raw = json.loads(path.read_text())
    return [
        Rule(
            id=r["id"],
            name=r["name"],
            edge_type=r["edge_type"],
            source_type=r["source_type"],
            target_type=r["target_type"],
            threshold=r["threshold"],
            weight=r.get("weight", 1.0),
            description=r.get("description", "{source} -> {target}"),
        )
        for r in raw
    ]
