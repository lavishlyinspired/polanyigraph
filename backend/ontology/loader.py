"""Load an OntologySchema from GraphDB via SPARQL.

Domain-agnostic: queries for ``owl:Class`` / ``rdf:Property`` in the configured
repository. Whatever ontology is loaded there defines the extraction vocabulary.
"""

from __future__ import annotations

from db.graphdb_client import GraphDBClient
from ontology.schema import OntologyClass, OntologyProperty, OntologySchema

_CLASSES_QUERY = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?uri ?label ?comment WHERE {
  ?uri a owl:Class .
  OPTIONAL { ?uri rdfs:label ?label }
  OPTIONAL { ?uri rdfs:comment ?comment }
  FILTER(isIRI(?uri))
}
LIMIT 5000
"""

_PROPERTIES_QUERY = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?uri ?label ?domain ?range WHERE {
  { ?uri a owl:ObjectProperty } UNION { ?uri a owl:DatatypeProperty }
  OPTIONAL { ?uri rdfs:label ?label }
  OPTIONAL { ?uri rdfs:domain ?domain }
  OPTIONAL { ?uri rdfs:range ?range }
  FILTER(isIRI(?uri))
}
LIMIT 5000
"""

# Direct (non-transitive) subClassOf edges. build_subclass_matcher() walks these
# transitively at query time, so only direct edges need to be loaded here.
_SUBCLASS_QUERY = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?child ?parent WHERE {
  ?child rdfs:subClassOf ?parent .
  FILTER(isIRI(?child))
  FILTER(isIRI(?parent))
}
LIMIT 100000
"""


def _local_name(uri: str) -> str:
    for sep in ("#", "/"):
        if sep in uri:
            return uri.rsplit(sep, 1)[-1]
    return uri


def load_schema(client: GraphDBClient, repository: str) -> OntologySchema:
    class_rows = client.select(_CLASSES_QUERY)
    prop_rows = client.select(_PROPERTIES_QUERY)
    subclass_rows = client.select(_SUBCLASS_QUERY)

    classes = [
        OntologyClass(
            uri=r["uri"],
            label=r.get("label") or _local_name(r["uri"]),
            comment=r.get("comment"),
        )
        for r in class_rows
        if r.get("uri")
    ]
    properties = [
        OntologyProperty(
            uri=r["uri"],
            label=r.get("label") or _local_name(r["uri"]),
            domain=r.get("domain"),
            range=r.get("range"),
        )
        for r in prop_rows
        if r.get("uri")
    ]
    subclass_of = [(r["child"], r["parent"]) for r in subclass_rows if r.get("child") and r.get("parent")]
    return OntologySchema(repository=repository, classes=classes, properties=properties, subclass_of=subclass_of)
