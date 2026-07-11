"""Pure-logic tests for ontology-aware subclass matching (no DB needed).

This is what fixes the real gap found via live testing: extraction correctly
returns specific ontology subclasses ("commercial bank") but hand-authored
rules reference generic ancestor types ("organization"); reasoning needs to
know the two are related via the ontology's real class hierarchy.
"""

from __future__ import annotations

from ontology.schema import OntologyClass, OntologySchema


def _schema() -> OntologySchema:
    # organization <- formal organization <- commercial bank  (two hops, like real FIBO)
    return OntologySchema(
        repository="test",
        classes=[
            OntologyClass(uri="urn:org", label="organization"),
            OntologyClass(uri="urn:formal-org", label="formal organization"),
            OntologyClass(uri="urn:bank", label="commercial bank"),
            OntologyClass(uri="urn:security", label="security"),
        ],
        properties=[],
        subclass_of=[("urn:formal-org", "urn:org"), ("urn:bank", "urn:formal-org")],
    )


def test_reflexive_same_type_matches():
    matcher = _schema().build_subclass_matcher()
    assert matcher("organization", "organization") is True


def test_direct_subclass_matches():
    matcher = _schema().build_subclass_matcher()
    assert matcher("formal organization", "organization") is True


def test_transitive_subclass_matches_through_multiple_hops():
    matcher = _schema().build_subclass_matcher()
    assert matcher("commercial bank", "organization") is True


def test_unrelated_types_do_not_match():
    matcher = _schema().build_subclass_matcher()
    assert matcher("security", "organization") is False


def test_superclass_does_not_match_subclass_direction():
    """is-a is directional: organization is NOT a commercial bank."""
    matcher = _schema().build_subclass_matcher()
    assert matcher("organization", "commercial bank") is False


def test_matching_is_case_insensitive():
    matcher = _schema().build_subclass_matcher()
    assert matcher("Commercial Bank", "Organization") is True


def test_unknown_type_does_not_match_anything():
    matcher = _schema().build_subclass_matcher()
    assert matcher("not-a-real-type", "organization") is False
