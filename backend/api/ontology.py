"""GET /ontology — full ontology schema (classes, properties, subclass relationships)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.dependencies import get_graphdb
from app.schemas import ApiModel
from db.graphdb_client import GraphDBClient
from ontology.loader import load_schema

router = APIRouter(tags=["ontology"])


class OntologyClassItem(ApiModel):
    label: str
    uri: str
    comment: str | None = None


class OntologyPropertyItem(ApiModel):
    label: str
    uri: str
    domain: str | None = None
    range: str | None = None


class SubclassRelation(ApiModel):
    child: str
    parent: str


class OntologySchemaResponse(ApiModel):
    class_labels: list[str]
    property_labels: list[str]
    classes: list[OntologyClassItem]
    properties: list[OntologyPropertyItem]
    subclass_of: list[SubclassRelation]
    class_count: int
    property_count: int


@router.get("/ontology", response_model=OntologySchemaResponse, response_model_by_alias=True)
def get_ontology(
    graphdb: GraphDBClient = Depends(get_graphdb),
    settings: Settings = Depends(get_settings),
) -> OntologySchemaResponse:
    schema = load_schema(graphdb, settings.graphdb_repository)

    # Build label lookup for subclass relations (URI -> label)
    uri_to_label: dict[str, str] = {c.uri: c.label for c in schema.classes}

    return OntologySchemaResponse(
        class_labels=sorted({c.label for c in schema.classes}),
        property_labels=sorted({p.label for p in schema.properties}),
        classes=[
            OntologyClassItem(label=c.label, uri=c.uri, comment=c.comment)
            for c in schema.classes
        ],
        properties=[
            OntologyPropertyItem(label=p.label, uri=p.uri, domain=p.domain, range=p.range)
            for p in schema.properties
        ],
        subclass_of=[
            SubclassRelation(
                child=uri_to_label.get(child_uri, child_uri),
                parent=uri_to_label.get(parent_uri, parent_uri),
            )
            for child_uri, parent_uri in schema.subclass_of
        ],
        class_count=len(schema.classes),
        property_count=len(schema.properties),
    )
