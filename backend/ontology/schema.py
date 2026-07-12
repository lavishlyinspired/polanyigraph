"""Domain-agnostic ontology schema model.

An ``OntologySchema`` is whatever we discover from the RDF ontology loaded in
GraphDB. It is not FIBO-specific; the same code describes a bio-ontology, CCO,
schema.org, etc. Extraction and typing are driven entirely by this object.
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel


class OntologyClass(BaseModel):
    uri: str
    label: str
    comment: str | None = None


class OntologyProperty(BaseModel):
    uri: str
    label: str
    domain: str | None = None  # class URI
    range: str | None = None   # class URI


class OntologySchema(BaseModel):
    repository: str
    classes: list[OntologyClass]
    properties: list[OntologyProperty]
    # (child_uri, parent_uri) pairs from rdfs:subClassOf. Real ontologies like
    # FIBO give a class multiple rdfs:label values (e.g. "commercial bank" and
    # "Commercial Bank" on the same URI), so matching is done by URI, not label.
    subclass_of: list[tuple[str, str]] = []

    @property
    def class_labels(self) -> list[str]:
        return [c.label for c in self.classes]

    @property
    def property_labels(self) -> list[str]:
        return [p.label for p in self.properties]

    def is_known_type(self, label: str) -> bool:
        return label.lower() in {c.label.lower() for c in self.classes}

    def build_subclass_matcher(self) -> Callable[[str, str], bool]:
        """Return a ``matches(candidate_label, expected_label) -> bool`` closure
        that is true when candidate IS-A expected (reflexively or transitively
        via real rdfs:subClassOf edges), built once so reasoning doesn't rebuild
        the index on every rule x edge comparison.

        Fixes the real gap found via live testing: extraction correctly returns
        specific subclasses ("commercial bank") while hand-authored rules
        reference generic ancestor types ("organization"); exact string
        equality never connected the two even though the ontology does.
        """
        uris_by_label: dict[str, set[str]] = {}
        for c in self.classes:
            uris_by_label.setdefault(c.label.lower(), set()).add(c.uri)

        parents_by_uri: dict[str, set[str]] = {}
        for child_uri, parent_uri in self.subclass_of:
            parents_by_uri.setdefault(child_uri, set()).add(parent_uri)

        def matches(candidate_label: str, expected_label: str) -> bool:
            if candidate_label.lower() == expected_label.lower():
                return True
            candidate_uris = uris_by_label.get(candidate_label.lower(), set())
            expected_uris = uris_by_label.get(expected_label.lower(), set())
            if not candidate_uris or not expected_uris:
                return False

            visited: set[str] = set()
            frontier = set(candidate_uris)
            while frontier:
                if frontier & expected_uris:
                    return True
                visited |= frontier
                next_frontier: set[str] = set()
                for uri in frontier:
                    next_frontier |= parents_by_uri.get(uri, set())
                frontier = next_frontier - visited
            return False

        return matches

    def build_domain_range_matcher(self) -> Callable[[str, str, str], bool]:
        """Return a ``valid(edge_type_label, source_type_label, target_type_label)
        -> bool`` closure: true when the ontology's own ``rdfs:domain``/
        ``rdfs:range`` for the property matching ``edge_type_label`` accepts
        the given source/target types (via the same subclass-aware matching
        ``build_subclass_matcher`` uses), OR when the property isn't found in
        the ontology / has no domain or range declared for it at all.

        Deliberately fails OPEN in the unknown case: this is a consistency
        gate layered on top of a rule's own (already-checked) type match, not
        a second, independent source of false rejections for edge types the
        loaded ontology simply doesn't describe a domain/range for. Fixes a
        different gap than build_subclass_matcher: that one checks a rule's
        declared types against the real graph; this one checks the edge
        itself against what the ontology says the property is actually
        allowed to connect, catching a rule that type-matches by coincidence
        but produces a domain/range-invalid edge (e.g. a mined rule whose
        source/target types are broad enough to pass the rule's own check but
        still violate the property's own declared domain/range).
        """
        subclass_matches = self.build_subclass_matcher()
        uri_to_label: dict[str, str] = {c.uri: c.label for c in self.classes}
        props_by_label: dict[str, list[OntologyProperty]] = {}
        for p in self.properties:
            props_by_label.setdefault(p.label.lower(), []).append(p)

        def valid(edge_type_label: str, source_type_label: str, target_type_label: str) -> bool:
            candidates = props_by_label.get(edge_type_label.lower())
            if not candidates:
                return True  # ontology says nothing about this property -- nothing to validate
            for prop in candidates:
                domain_label = uri_to_label.get(prop.domain) if prop.domain else None
                range_label = uri_to_label.get(prop.range) if prop.range else None
                domain_ok = domain_label is None or subclass_matches(source_type_label, domain_label)
                range_ok = range_label is None or subclass_matches(target_type_label, range_label)
                if domain_ok and range_ok:
                    return True
            return False

        return valid
