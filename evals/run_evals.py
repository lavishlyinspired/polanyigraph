"""Full-suite skill eval runner (PLAN.md §14, Python adaptation of the
originally-sketched run-evals.js). Runs every case under evals/cases/,
against the real backend services + real Neo4j/GraphDB/LLM, and writes a
timestamped JSON summary to evals/results/.

Usage:
    .venv/bin/python evals/run_evals.py                  # all skills
    .venv/bin/python evals/run_evals.py --skill kg-query  # one skill
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from lib import RESULTS_DIR, load_cases, neo4j_reachable, run_case


def main() -> int:
    parser = argparse.ArgumentParser(description="Run skill eval cases against the real backend.")
    parser.add_argument("--skill", help="Only run cases for this skill (e.g. kg-extraction).")
    args = parser.parse_args()

    if not neo4j_reachable():
        print("Neo4j not reachable -- skipping eval run (this mirrors backend/tests/ skip behavior).")
        return 0

    cases = load_cases(args.skill)
    if not cases:
        print(f"No eval cases found{f' for skill {args.skill!r}' if args.skill else ''}.")
        return 1

    results = [run_case(path) for path in cases]

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.skill}/{r.case_id}")
        if r.error:
            print(f"    error: {r.error}")
        for a in r.assertions:
            if not a.passed:
                print(f"    FAILED assertion {a.assertion}: {a.detail}")

    passed = sum(1 for r in results if r.passed)
    print(f"\n{passed}/{len(results)} cases passed.")

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(
        [
            {
                "case_id": r.case_id, "skill": r.skill, "passed": r.passed, "error": r.error,
                "assertions": [{"assertion": a.assertion, "passed": a.passed, "detail": a.detail} for a in r.assertions],
            }
            for r in results
        ],
        indent=2,
    ))
    print(f"Results written to {out_path.relative_to(RESULTS_DIR.parent.parent)}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
