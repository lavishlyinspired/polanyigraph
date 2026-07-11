from __future__ import annotations

from pathlib import Path

from reasoning.engine import Rule
from reasoning.rules_repo import DEFAULT_RULES_PATH, load_rules


def test_default_rules_file_exists_and_loads():
    assert DEFAULT_RULES_PATH.exists()
    rules = load_rules(DEFAULT_RULES_PATH)
    assert len(rules) > 0
    assert all(isinstance(r, Rule) for r in rules)


def test_rules_reference_real_fibo_vocabulary():
    """Sanity check: this is a hand-authored real rule set (not placeholders)."""
    rules = load_rules(DEFAULT_RULES_PATH)
    edge_types = {r.edge_type for r in rules}
    assert "issues" in edge_types


def test_load_rules_rejects_missing_file(tmp_path: Path):
    missing = tmp_path / "nope.json"
    try:
        load_rules(missing)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
