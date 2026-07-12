"""Skill evaluation infrastructure (PLAN.md §14), adapted to this project's
real stack: Python + the backend's own real services, not the originally-
sketched validate-skills.js/run-evals.js against a hypothetical JS harness.
Every case here drives real Neo4j + GraphDB + LLM calls through the exact
same service functions the API/agent/MCP layers use -- no mocks, no fixture
graphs standing in for a real extraction/reasoning/query/enrichment/memory
run.

Each case seeds its own graph_id (or reuses one, per the case file) and
tears it down after grading, mirroring the `test-{uuid}` + DETACH DELETE
convention already used throughout backend/tests/.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVALS_DIR.parent / "backend"
CASES_DIR = EVALS_DIR / "cases"
RESULTS_DIR = EVALS_DIR / "results"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.dependencies import get_graphdb, get_llm, get_neo4j  # noqa: E402
from db.neo4j_client import Neo4jClient  # noqa: E402
from services import (  # noqa: E402
    enrichment_service,
    graph_service,
    ingest_service,
    memory_service,
    reasoning_service,
)
from services.path_engine import find_path  # noqa: E402
from services.query_engine import execute_query  # noqa: E402


@dataclass
class EvalOutput:
    """Normalized shape every skill's real output is reduced to, so one
    generic assertion evaluator (see `grade`) can check all 6 skills."""

    entities: list[tuple[str, str]] = field(default_factory=list)  # (name, type)
    relationships: list[tuple[str, str, str]] = field(default_factory=list)  # (source, type, target)
    items: list[str] = field(default_factory=list)  # generic textual output items (facts/results/hits/description)
    raw: dict = field(default_factory=dict)


@dataclass
class AssertionResult:
    assertion: dict
    passed: bool
    detail: str


@dataclass
class CaseResult:
    case_id: str
    skill: str
    passed: bool
    assertions: list[AssertionResult]
    error: str | None = None


def neo4j_reachable() -> bool:
    client = Neo4jClient(get_settings())
    try:
        client.verify()
        return True
    except Exception:
        return False
    finally:
        client.close()


def load_case(path: Path) -> dict:
    return json.loads(path.read_text())


def load_cases(skill: str | None = None) -> list[Path]:
    if not CASES_DIR.is_dir():
        return []
    paths = sorted(CASES_DIR.glob("*/case-*.json"))
    if skill:
        paths = [p for p in paths if p.parent.name == skill]
    return paths


def _cleanup_graph(neo4j: Neo4jClient, graph_id: str) -> None:
    neo4j.run("MATCH (n {graphId: $graph_id}) DETACH DELETE n", graph_id=graph_id)
    neo4j.run("MATCH (e:IngestEvent {graphId: $graph_id}) DETACH DELETE e", graph_id=graph_id)


def _run_kg_extraction(case: dict) -> EvalOutput:
    settings = get_settings()
    ctx = case["input"].get("context", {})
    graph_id = ctx.get("graph_id") or f"eval-kg-extraction-{uuid.uuid4().hex[:8]}"
    neo4j = get_neo4j()
    try:
        _record, result = ingest_service.ingest_text(
            neo4j=neo4j, graphdb=get_graphdb(), llm=get_llm(),
            graph_id=graph_id, text=case["input"]["text"], source_doc="eval", repository=settings.graphdb_repository,
        )
        return EvalOutput(
            entities=[(e.name, e.type) for e in result.entities],
            relationships=[(r.source, r.relation, r.target) for r in result.relationships],
            items=[f"{e.name} ({e.type})" for e in result.entities],
            raw={"dropped": result.dropped},
        )
    finally:
        _cleanup_graph(neo4j, graph_id)


def _run_polanyi_enrichment(case: dict) -> EvalOutput:
    ctx = case["input"].get("context", {})
    graph_id = ctx.get("graph_id") or f"eval-polanyi-{uuid.uuid4().hex[:8]}"
    seed_text = ctx.get("seed_text", case["input"]["text"])
    settings = get_settings()
    neo4j = get_neo4j()
    try:
        record, _extraction = ingest_service.ingest_text(
            neo4j=neo4j, graphdb=get_graphdb(), llm=get_llm(),
            graph_id=graph_id, text=seed_text, source_doc="eval-seed", repository=settings.graphdb_repository,
        )
        candidates = enrichment_service.run_all_heuristics(
            get_llm(), nodes=record.nodes, edges=record.edges, source_text=case["input"]["text"],
        )
        return EvalOutput(
            items=[f"[{c.heuristic_type}] {c.text}" for c in candidates],
            raw={"heuristic_types": sorted({c.heuristic_type for c in candidates})},
        )
    finally:
        _cleanup_graph(neo4j, graph_id)


def _run_kg_query(case: dict) -> EvalOutput:
    ctx = case["input"].get("context", {})
    graph_id = ctx.get("graph_id") or f"eval-kg-query-{uuid.uuid4().hex[:8]}"
    seed_text = ctx.get("seed_text")
    settings = get_settings()
    neo4j = get_neo4j()
    try:
        if seed_text:
            ingest_service.ingest_text(
                neo4j=neo4j, graphdb=get_graphdb(), llm=get_llm(),
                graph_id=graph_id, text=seed_text, source_doc="eval-seed", repository=settings.graphdb_repository,
            )
        if "path" in case["input"]:
            record = graph_service.get_graph(neo4j, graph_id)
            path_result = find_path(case["input"]["path"]["source"], case["input"]["path"]["target"], record.nodes, record.edges)
            return EvalOutput(
                items=path_result.path,
                raw={"error": path_result.error, "found": path_result.found, "proof": path_result.proof},
            )
        triples = graph_service.load_triples(neo4j, graph_id)
        result = execute_query(case["input"]["query"], triples)
        return EvalOutput(
            items=[f"{r.subject} {r.predicate} {r.object}" for r in result.results],
            raw={"error": result.error},
        )
    finally:
        _cleanup_graph(neo4j, graph_id)


def _run_neurosymbolic_reasoning(case: dict) -> EvalOutput:
    ctx = case["input"].get("context", {})
    graph_id = ctx.get("graph_id") or f"eval-reasoning-{uuid.uuid4().hex[:8]}"
    seed_text = ctx["seed_text"]
    settings = get_settings()
    neo4j = get_neo4j()
    try:
        ingest_service.ingest_text(
            neo4j=neo4j, graphdb=get_graphdb(), llm=get_llm(),
            graph_id=graph_id, text=seed_text, source_doc="eval-seed", repository=settings.graphdb_repository,
        )
        result = reasoning_service.run_reasoning(
            neo4j, get_graphdb(), settings, graph_id=graph_id, source_id=ctx.get("source_id"),
        )
        return EvalOutput(
            items=[f.fact for f in result.facts],
            raw={"iterations": result.iterations, "converged_by": result.converged_by},
        )
    finally:
        _cleanup_graph(neo4j, graph_id)


def _run_kg_visualization(case: dict) -> EvalOutput:
    """No backend visualization/export service exists -- confirmed:
    backend/skills/kg-visualization/SKILL.md tells the agent it cannot
    render an image and must describe the graph in text instead. The
    closest real backend behavior to grade is the same real graph read
    (services/graph_service.get_graph) that description would be based on."""
    ctx = case["input"].get("context", {})
    graph_id = ctx.get("graph_id") or f"eval-kg-viz-{uuid.uuid4().hex[:8]}"
    seed_text = ctx["seed_text"]
    settings = get_settings()
    neo4j = get_neo4j()
    try:
        ingest_service.ingest_text(
            neo4j=neo4j, graphdb=get_graphdb(), llm=get_llm(),
            graph_id=graph_id, text=seed_text, source_doc="eval-seed", repository=settings.graphdb_repository,
        )
        record = graph_service.get_graph(neo4j, graph_id)
        return EvalOutput(
            entities=[(n.label, n.type) for n in record.nodes],
            relationships=[(e.source, e.type, e.target) for e in record.edges],
            items=[f"{n.label} ({n.type})" for n in record.nodes],
        )
    finally:
        _cleanup_graph(neo4j, graph_id)


def _run_memory_recall(case: dict) -> EvalOutput:
    ctx = case["input"].get("context", {})
    graph_id = ctx.get("graph_id") or f"eval-memory-{uuid.uuid4().hex[:8]}"
    neo4j = get_neo4j()
    session_id = f"eval-session-{uuid.uuid4().hex[:8]}"
    seed_messages = ctx.get("seed_messages", [])
    try:
        for i, content in enumerate(seed_messages):
            neo4j.run(
                """
                MERGE (s:ChatSession {id: $session_id, graphId: $graph_id})
                CREATE (s)-[:HAS_MESSAGE]->(m:ChatMessage {id: $msg_id, content: $content, seq: $seq, createdAt: datetime()})
                """,
                session_id=session_id, graph_id=graph_id, msg_id=f"eval-msg-{uuid.uuid4().hex[:8]}",
                content=content, seq=i,
            )
        hits = memory_service.search_memory(neo4j, graph_id=graph_id, query=case["input"]["query"])
        return EvalOutput(items=[f"[{h.kind}] {h.text}" for h in hits])
    finally:
        neo4j.run("MATCH (s:ChatSession {id: $session_id}) DETACH DELETE s", session_id=session_id)
        _cleanup_graph(neo4j, graph_id)


_RUNNERS = {
    "kg-extraction": _run_kg_extraction,
    "polanyi-enrichment": _run_polanyi_enrichment,
    "kg-query": _run_kg_query,
    "neurosymbolic-reasoning": _run_neurosymbolic_reasoning,
    "kg-visualization": _run_kg_visualization,
    "memory-recall": _run_memory_recall,
}


def _entity_type(output: EvalOutput, name: str) -> str | None:
    for n, t in output.entities:
        if n == name:
            return t
    return None


def _relationship_type(output: EvalOutput, source: str) -> str | None:
    for s, t, _tgt in output.relationships:
        if s == source:
            return t
    return None


def grade(assertion: dict, output: EvalOutput) -> AssertionResult:
    kind = assertion["type"]
    if kind == "entity_count":
        actual = len(output.entities)
        return AssertionResult(assertion, actual == assertion["value"], f"expected {assertion['value']} entities, got {actual}")
    if kind == "relationship_count":
        actual = len(output.relationships)
        return AssertionResult(assertion, actual == assertion["value"], f"expected {assertion['value']} relationships, got {actual}")
    if kind == "min_entity_count":
        actual = len(output.entities)
        return AssertionResult(assertion, actual >= assertion["value"], f"expected >= {assertion['value']} entities, got {actual}")
    if kind == "min_relationship_count":
        actual = len(output.relationships)
        return AssertionResult(assertion, actual >= assertion["value"], f"expected >= {assertion['value']} relationships, got {actual}")
    if kind == "item_count":
        actual = len(output.items)
        return AssertionResult(assertion, actual == assertion["value"], f"expected {assertion['value']} items, got {actual}")
    if kind == "min_item_count":
        actual = len(output.items)
        return AssertionResult(assertion, actual >= assertion["value"], f"expected >= {assertion['value']} items, got {actual}")
    if kind == "entity_type_match":
        actual = _entity_type(output, assertion["entity"])
        return AssertionResult(assertion, actual == assertion["expected_type"], f"entity '{assertion['entity']}' has type {actual!r}")
    if kind == "relationship_type_match":
        actual = _relationship_type(output, assertion["source"])
        return AssertionResult(assertion, actual == assertion["expected_type"], f"relationship from '{assertion['source']}' has type {actual!r}")
    if kind == "no_error":
        err = output.raw.get("error")
        return AssertionResult(assertion, err is None, f"raw error: {err!r}")
    if kind == "min_iterations":
        actual = output.raw.get("iterations", 0)
        return AssertionResult(assertion, actual >= assertion["value"], f"expected >= {assertion['value']} iterations, got {actual}")
    if kind == "converged":
        converged_by = output.raw.get("converged_by")
        return AssertionResult(assertion, converged_by is not None, f"converged_by: {converged_by!r}")
    if kind == "path_found":
        found = bool(output.raw.get("found"))
        return AssertionResult(assertion, found, f"path found: {found} (proof: {output.raw.get('proof')!r})")
    if kind == "contains_text":
        found = any(assertion["text"].lower() in item.lower() for item in output.items)
        return AssertionResult(assertion, found, f"{'found' if found else 'did not find'} {assertion['text']!r} in items")
    return AssertionResult(assertion, False, f"unknown assertion type '{kind}'")


def run_case(path: Path) -> CaseResult:
    case = load_case(path)
    runner = _RUNNERS.get(case["skill"])
    if runner is None:
        return CaseResult(case["id"], case["skill"], False, [], error=f"no runner registered for skill '{case['skill']}'")
    try:
        output = runner(case)
    except Exception as exc:  # noqa: BLE001 - report as a failed case, don't crash the suite
        return CaseResult(case["id"], case["skill"], False, [], error=f"{type(exc).__name__}: {exc}")
    assertions = [grade(a, output) for a in case.get("assertions", [])]
    return CaseResult(case["id"], case["skill"], all(a.passed for a in assertions), assertions)
