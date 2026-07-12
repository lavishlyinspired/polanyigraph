"""Single-case validator (PLAN.md §14.2's RED/GREEN skill-authoring loop,
Python adaptation of the originally-sketched validate-skills.js). Point it
at one case file while iterating on a SKILL.md or a service: RED until the
skill/service produces the expected real output, GREEN once it does.

Usage:
    .venv/bin/python evals/validate.py cases/kg-extraction/case-001-basic-extraction.json
"""

from __future__ import annotations

import sys
from pathlib import Path

from lib import neo4j_reachable, run_case


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate.py <path/to/case.json>")
        return 2

    if not neo4j_reachable():
        print("Neo4j not reachable -- cannot validate against real state.")
        return 1

    path = Path(sys.argv[1])
    if not path.is_file():
        path = Path(__file__).resolve().parent / sys.argv[1]
    if not path.is_file():
        print(f"No such case file: {sys.argv[1]}")
        return 2

    result = run_case(path)
    print(f"[{'PASS' if result.passed else 'FAIL'}] {result.skill}/{result.case_id}")
    if result.error:
        print(f"  error: {result.error}")
    for a in result.assertions:
        mark = "✓" if a.passed else "✗"
        print(f"  {mark} {a.assertion.get('type')}: {a.detail}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
