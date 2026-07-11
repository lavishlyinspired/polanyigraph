"""Structured triple query engine: ``predicate(subject, object)``.

Ported from the prototype (docs/src/lib/engine.ts executeQuery) with the same
language: subject/object are quoted literals or variables (X/Y/Z/_); comma
separated atoms join conjunctively on shared variable bindings. Operates over
stored + derived triples (real graph data), never a demo dataset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ATOM_RE = re.compile(r'^(\w[\w ]*?)\s*\(\s*(?:"([^"]*)"|(\w+))\s*,\s*(?:"([^"]*)"|(\w+))\s*\)$')
_VARIABLE_NAMES = {"X", "Y", "Z", "_"}


@dataclass(frozen=True)
class Triple:
    subject: str
    predicate: str
    object: str
    derived: bool
    confidence: float


@dataclass(frozen=True)
class ResultRow:
    subject: str
    predicate: str
    object: str
    derived: bool
    confidence: float


@dataclass(frozen=True)
class QueryResult:
    query: str
    results: list[ResultRow]
    error: str | None = None


@dataclass(frozen=True)
class _Atom:
    predicate: str
    subject_literal: str | None
    subject_var: str | None
    object_literal: str | None
    object_var: str | None


def _parse_atom(part: str) -> _Atom | None:
    m = _ATOM_RE.match(part.strip())
    if not m:
        return None
    return _Atom(
        predicate=m.group(1).strip(),
        subject_literal=m.group(2),
        subject_var=m.group(3),
        object_literal=m.group(4),
        object_var=m.group(5),
    )


def _is_variable(name: str | None) -> bool:
    return bool(name) and name.upper() in _VARIABLE_NAMES


def _split_top_level_atoms(text: str) -> list[str]:
    """Split on commas that separate atoms, not the subject/object comma inside
    a single atom's parens — required because predicates may contain spaces
    (real ontology property labels like "is regulated by"), so a naive
    ``split(",")`` would cut atoms in half."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def execute_query(query: str, triples: list[Triple]) -> QueryResult:
    trimmed = query.strip()
    if not trimmed:
        return QueryResult(query=query, results=[], error="Empty query.")

    parts = _split_top_level_atoms(trimmed)
    atoms = [_parse_atom(p) for p in parts]
    if any(a is None for a in atoms):
        return QueryResult(
            query=query,
            results=[],
            error='Invalid syntax. Use: predicate(subject, object) — e.g., regulates("FINMA", X)',
        )
    valid_atoms = [a for a in atoms if a is not None]

    if len(valid_atoms) == 1:
        return _execute_single(query, valid_atoms[0], triples)
    return _execute_join(query, valid_atoms, triples)


def _execute_single(query: str, atom: _Atom, triples: list[Triple]) -> QueryResult:
    results: list[ResultRow] = []
    seen: set[tuple[str, str, bool]] = set()
    for t in triples:
        if t.predicate != atom.predicate:
            continue
        if not _matches(t.subject, atom.subject_literal, atom.subject_var):
            continue
        if not _matches(t.object, atom.object_literal, atom.object_var):
            continue
        key = (t.subject, t.object, t.derived)
        if key in seen:
            continue
        seen.add(key)
        results.append(ResultRow(subject=t.subject, predicate=t.predicate, object=t.object, derived=t.derived, confidence=t.confidence))
    return QueryResult(query=query, results=results)


def _matches(value: str, literal: str | None, var: str | None) -> bool:
    if literal is not None:
        return value.lower() == literal.lower()
    if var is not None and not _is_variable(var):
        return value.lower() == var.lower()
    return True  # unbound variable (X/Y/Z/_) matches anything


def _execute_join(query: str, atoms: list[_Atom], triples: list[Triple]) -> QueryResult:
    bindings: list[dict[str, str]] = [{}]

    for atom in atoms:
        new_bindings: list[dict[str, str]] = []
        for binding in bindings:
            for t in triples:
                if t.predicate != atom.predicate:
                    continue
                subject_val = _resolve(atom.subject_literal, atom.subject_var, binding)
                object_val = _resolve(atom.object_literal, atom.object_var, binding)
                if subject_val is not None and t.subject.lower() != subject_val.lower():
                    continue
                if object_val is not None and t.object.lower() != object_val.lower():
                    continue
                nb = dict(binding)
                if _is_variable(atom.subject_var) and atom.subject_var not in binding:
                    nb[atom.subject_var] = t.subject
                if _is_variable(atom.object_var) and atom.object_var not in binding:
                    nb[atom.object_var] = t.object
                new_bindings.append(nb)
        bindings = new_bindings
        if not bindings:
            break

    first = atoms[0]
    results: list[ResultRow] = []
    for binding in bindings:
        subject = binding.get(first.subject_var or "", first.subject_literal or "")
        obj = binding.get(first.object_var or "", first.object_literal or "")
        if not subject or not obj:
            continue
        existing = next((t for t in triples if t.subject == subject and t.predicate == first.predicate and t.object == obj), None)
        results.append(
            ResultRow(
                subject=subject, predicate=first.predicate, object=obj,
                derived=existing.derived if existing else False,
                confidence=existing.confidence if existing else 1.0,
            )
        )
    return QueryResult(query=query, results=results)


def _resolve(literal: str | None, var: str | None, binding: dict[str, str]) -> str | None:
    if literal is not None:
        return literal
    if var is not None and _is_variable(var):
        return binding.get(var)
    return var
