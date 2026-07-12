"""Pure-logic tests for ontology-aware subclass matching (no DB needed).

This is what fixes the real gap found via live testing: extraction correctly
returns specific ontology subclasses ("commercial bank") but hand-authored
rules reference generic ancestor types ("organization"); reasoning needs to
know the two are related via the ontology's real class hierarchy.
"""

from __future__ import annotations

from ontology.schema import OntologyClass, OntologyProperty, OntologySchema


def _schema() -> OntologySchema:
    # organization <- formal organization <- commercial bank  (two hops, like real FIBO)
    return OntologySchema(
        repository="test",
        classes=[
            OntologyClass(uri="urn:org", label="organization"),
            OntologyClass(uri="urn:formal-org", label="formal organization"),
            OntologyClass(uri="urn:bank", label="commercial bank"),
            OntologyClass(uri="urn:security", label="security"),
            OntologyClass(uri="urn:regulator", label="regulatory agency"),
        ],
        properties=[],
        subclass_of=[("urn:formal-org", "urn:org"), ("urn:bank", "urn:formal-org")],
    )


def _schema_with_domain_range() -> OntologySchema:
    schema = _schema()
    return schema.model_copy(update={
        "properties": [
            # "issues" only ever connects organization -> security, per the ontology.
            OntologyProperty(uri="urn:issues", label="issues", domain="urn:org", range="urn:security"),
            # "is regulated by" only ever connects organization -> regulatory agency.
            OntologyProperty(
                uri="urn:regulated-by", label="is regulated by", domain="urn:org", range="urn:regulator",
            ),
        ],
    })


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


# --- Feature 2: semantic conditioning at inference (2026-07-13 plan §4) -----
# build_domain_range_matcher() catches a different gap than
# build_subclass_matcher(): a rule can type-match by its OWN declared types
# yet still describe an edge the ontology's real rdfs:domain/rdfs:range
# never allows (e.g. a mined rule whose types are broad enough to pass the
# rule's own check but violate the property's own declared domain/range).

def test_domain_range_matcher_accepts_a_correctly_typed_edge():
    valid = _schema_with_domain_range().build_domain_range_matcher()
    assert valid("issues", "organization", "security") is True


def test_domain_range_matcher_rejects_wrong_source_type():
    valid = _schema_with_domain_range().build_domain_range_matcher()
    assert valid("issues", "security", "security") is False


def test_domain_range_matcher_rejects_wrong_target_type():
    valid = _schema_with_domain_range().build_domain_range_matcher()
    assert valid("issues", "organization", "organization") is False


def test_domain_range_matcher_is_subclass_aware():
    """A subtype of the declared domain still satisfies it -- same subclass
    resolution build_subclass_matcher already uses, not exact-string-only."""
    valid = _schema_with_domain_range().build_domain_range_matcher()
    assert valid("issues", "commercial bank", "security") is True


def test_domain_range_matcher_fails_open_for_unknown_property():
    """A property the loaded ontology doesn't describe at all is not an
    error -- this is a consistency check ON TOP OF a rule's own type match,
    not a second, independent source of false rejections."""
    valid = _schema_with_domain_range().build_domain_range_matcher()
    assert valid("some-property-not-in-the-ontology", "organization", "security") is True


def test_domain_range_matcher_fails_open_when_no_properties_loaded_at_all():
    valid = _schema().build_domain_range_matcher()  # properties=[]
    assert valid("issues", "organization", "security") is True
