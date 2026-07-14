# Semantic Materialization Engine — Design (Phase 2) + v1 Implementation (Phase 3)

**Status:** Phase 2 (this document) is design-only. **Phase 3 (v1) shipped
2026-07-14** — see "Phase 3 implementation status" near the end of this
document for exactly what was built, what was deliberately left out of
scope, and how it was verified (TDD, mutation testing, and a live
end-to-end run against the real FIBO ontology and a real LLM).

**Context:** Follow-up work agreed 2026-07-14, after [Analytics Role
Mapping](../../.opencode/plans/analytical-engine.md#follow-up-analytics-role-mapping-phase-1-added-2026-07-14)
(Phase 1) shipped as a read-time fix for a real, live-verified problem: date
and percentage entities (`8-45`, `august-5-2026`, ...) dominated
`degree_centrality`'s "most central entity" ranking in the real FIBO-backed
graph, purely by co-occurring with every fact that cites a rate or a date.

Phase 1 fixed the *symptom* at analysis time (multiply a node's centrality
score by 0.0 once its ontology type resolves to a Value/Temporal role).
This document addresses the *cause*: why does a percentage or a date become
a first-class graph node at all?

## The real gap, grounded in current code

`backend/services/ingest_service.py::ingest_text` is the actual extraction
→ storage pipeline:

```python
result = extract(text, schema=schema, llm=llm, extra_guidance=extra_guidance)
for entity in result.entities:
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id=eid,
                                 label=entity.name, type_=entity.type, ...)
```

Every `ExtractedEntity` the LLM returns unconditionally becomes a
`:Entity` node via `graph_service.upsert_entity`. There is no decision
point at all — `graph_service.py`'s own module docstring states the
design explicitly:

> "every extracted instance is a single `:Entity` node with a free-text
> `type` property ... This keeps the schema domain-agnostic."

That uniform-materialization choice is *why* extracting "the rate was
8.45%" produces a `:Entity {type: "rate of return", label: "8.45%"}` node
indistinguishable, structurally, from `:Entity {type: "organization",
label: "HDFC Bank"}` — both get identical degree/pagerank treatment,
identical query-DSL predicate targets, identical everything, even though
one is a real actor and the other is a value attached to a fact.

`ontology/loader.py` is correctly scoped today: it faithfully loads
whatever `owl:Class`/`rdfs:subClassOf` structure GraphDB has, with zero
opinion about storage. That's the right job for a loader. The missing
piece is a **separate** layer, downstream of extraction and upstream of
the Neo4j write, that decides *how* a given extracted concept should be
stored — not *whether* it's real (extraction already decided that).

## Relationship to Analytics Role Mapping (Phase 1)

Phase 1's `backend/analytics/roles.py` already built the reusable core of
this idea: `AnalyticsRole` (Actor/Event/Value/Temporal/Metadata),
anchor-class-driven resolution via `OntologySchema.build_subclass_matcher()`,
and a fails-open per-repository config (`ROLE_ANCHORS_BY_REPOSITORY`).

The Materialization Engine reuses that exact role taxonomy and resolution
mechanism, applied at a different point in the pipeline:

| | Analytics Role Mapping (Phase 1, shipped) | Materialization Engine (Phase 3, this doc) |
|---|---|---|
| **When it runs** | Read time, per analytics query | Write time, per ingested entity |
| **What it changes** | A centrality score (`score * weight`) | The actual Neo4j storage shape (node vs property vs ...) |
| **Reversible?** | Yes — re-running analytics with different weights changes nothing stored | No — changes what's actually persisted; requires a migration story |
| **Blast radius** | `analytics/`, `services/analytics_service.py`, `api/analytics.py` | `services/ingest_service.py`, `services/graph_service.py`, the query DSL, the frontend graph canvas |

Phase 1 is the safe, reversible workaround. This document is the
deliberate, harder fix — hence being designed separately rather than
folded into an inline refactor of the ingestion pipeline.

## Graph database agnosticism (added 2026-07-14, same-day follow-up)

The user flagged that this project is meant to be **graph-database-
agnostic** — not just domain-agnostic (which the rest of this codebase
already is, via the ontology-driven type vocabulary) — and that this
document's code examples are Neo4j-specific
(`graph_service.upsert_entity(neo4j, ...)`, raw Cypher). That callout is
correct. Ground truth, checked against this repo rather than assumed:

- 42 files import `Neo4jClient` directly and ~46 modules embed raw Cypher
  strings (`MATCH`/`MERGE`) — essentially the entire backend: every
  service, every agent node, every API route, including Phase 1's own
  `analytics/roles.py` integration.
- `ontology/loader.py`/`db/graphdb_client.py` are RDF/SPARQL-specific by
  original design (the two-store architecture: Neo4j for instance data,
  GraphDB/Ontotext for the RDF/OWL ontology) — a separate, pre-existing
  decision, not something this document changes.
- One genuinely good existing counter-example: `services/query_engine.py`'s
  `execute_query(query, triples: list[Triple])` takes a plain in-memory
  triple list and evaluates the DSL entirely in Python — no Neo4j import,
  no Cypher. `api/query.py` is the only place that touches Neo4j
  (`graph_service.get_graph(neo4j, graph_id)`), converting the result to
  `Triple` objects before handing off to `execute_query`. The fetch
  (backend-specific) / execute (backend-agnostic) seam this project needs
  *already exists*, in exactly one place. `ingest_service.py`'s writes and
  Phase 1's `analytics/roles.py` reads don't follow it yet.
- Also already backend-agnostic, and worth crediting rather than treating
  as a new gap: Phase 1's centrality scores come from `networkx`, not
  Neo4j GDS — `plans/analytical-engine.md` made that choice explicitly,
  earlier in this same session, specifically to avoid Neo4j-algorithm
  lock-in. The Materialization Engine's `WorkloadContext` assembly
  (`reference_count_by_value`, `relationship_fanout_by_entity_name`) is
  the one *new* piece here that would need a fetch abstraction, since it
  currently would have to be built via direct Cypher in
  `ingest_service.py` were it implemented today.

**Why this affects sequencing, not just phrasing.** "Make this design's
interfaces backend-agnostic" is cheap — they mostly already are (see
below). "Retrofit the ~40 files this session already shipped directly
against `Neo4jClient`" is a full rewrite of the data-access layer, and is
not something this design document can respond to just by adding a
section — the actual code was built this session in the other direction
(agents/graph.py, ingest_service.py, community_service.py, all of
analytics/, all take a `Neo4jClient` argument directly, by explicit design
choice at the time).

Worth surfacing plainly: this exact tension is already captured in a saved
memory (`graphos_vision.md`) from earlier the same day — the user was
asked directly whether to start building a graph-agnostic adapter layer
then, and chose to save it as a vision note rather than start a pilot,
reasoning that no second backend need had appeared yet. This message
revisits that. This document updates the *design* accordingly below, but
does not treat that as authorization to retrofit the ~40 already-shipped
files — see the sequencing question this document ends with.

### What in this design was already agnostic

- `AnalyticsRole`, `MaterializationPolicy`, `MaterializationDecision`,
  `WorkloadContext`, and `plan_materialization()` (below) — all pure
  Python, no Neo4j import, no Cypher. The *decision* layer never needed to
  change for this.
- `OntologySchema.build_subclass_matcher()` (Phase 1's resolver) — works
  off `OntologySchema.subclass_of` tuples. Those happen to be sourced from
  GraphDB/SPARQL today, but the matcher itself has no SPARQL in it; it
  would work identically fed from a local OWL file via `rdflib` or a
  different triplestore.

### What needs an explicit seam: the Storage Adapter Pattern

`plan_materialization()` should stop being followed by a direct
`graph_service.upsert_entity(neo4j, ...)` call and instead emit a small,
backend-neutral instruction the caller executes through an adapter:

```python
@dataclass(frozen=True)
class StorageCommand:
    operation: str  # "UPSERT_NODE" | "SET_PROPERTY" | "MERGE_NODE_ON_VALUE" | "CREATE_EDGE" | "EMBED_OBJECT"
    subject_id: str
    key: str | None = None
    value: object = None
    merge_key: str | None = None  # SHARED_NODE / TIME_NODE: field to MERGE on


class GraphClient(Protocol):
    def execute(self, command: StorageCommand) -> None: ...
    def fetch_graph(self, graph_id: str) -> GraphRecord: ...
    def fetch_fanout(self, entity_id: str) -> int: ...
    def fetch_reference_count(self, value: str) -> int: ...
```

`Neo4jGraphClient` (wrapping today's `graph_service.py` Cypher) is the
first, and for now only, real implementation — naming this interface
changes nothing about today's runtime behavior. A second backend
(Neptune/Memgraph/ArangoDB, or an RDF store via the existing
`GraphDBClient`) only needs a second implementation of the same four
methods; nothing above the adapter (extraction, role resolution,
materialization decisions, the agent) needs to know which one is live.

Per policy, `StorageCommand.operation` maps roughly as:

| Policy | Command | Neo4j (today) | RDF-store equivalent (illustrative, not built) |
|---|---|---|---|
| NODE | `UPSERT_NODE` | `MERGE (e:Entity {id, graphId}) SET ...` | `subject rdf:type Class` + literal triples |
| PROPERTY | `SET_PROPERTY` | `SET e[$key] = $value` | `subject predicate "value"` (datatype literal) |
| SHARED_NODE | `MERGE_NODE_ON_VALUE` | `MERGE (v:Value {normalized})` | check-then-bind to an existing subject URI for that literal value |
| EVENT_NODE | `UPSERT_NODE` (+ FK) | as NODE, plus `producedByEventId` property | as NODE, plus a triple linking the event subject |
| EMBEDDED_OBJECT | `EMBED_OBJECT` | nested map property (Neo4j supports map/list properties) | blank node (`_:b1`) with its own triples, or property-key prefixing (`address.street`) |
| TIME_NODE | `MERGE_NODE_ON_VALUE` | as SHARED_NODE, typed `:TimeInstant` | as SHARED_NODE, `xsd:dateTime` literal or an OWL-Time resource |

EMBEDDED_OBJECT is the one row where "different syntax, same shape" breaks
down: RDF triplestores have no first-class nested-object type, so an
adapter targeting one has to actually choose blank nodes vs. key-prefixing
— a real per-adapter design decision, not a pure translation.

## Materialization policies

A concept extracted from text can be stored one of six ways:

- **NODE** — a first-class `:Entity` node, as today. For concepts with
  independent identity that participate in multiple relationships (Actor,
  Event roles): organizations, people, securities, regulatory filings.
- **PROPERTY** — a scalar property on the entity/edge that mentions it,
  never its own node. For single-use Value/Metadata data with no
  relationships of its own: a percentage, a monetary amount, a document
  reference number.
- **SHARED_NODE** — a node, but deduplicated/MERGEd on value rather than
  on extraction identity, because the same value is meaningfully referenced
  by many entities and *is* worth graph-native querying (e.g. "which
  companies are all regulated by FINMA" benefits from `regulatory agency`
  being a shared node; "which companies report an 8.45% rate" does not
  benefit the same way, since values rarely need traversal).
- **EVENT_NODE** — a node, but one whose identity is inherently temporal
  and relationship-mediated (a filing event, an earnings call, a rate
  change) — distinct from Actor nodes because it's expected to have
  `valid_at`/`invalid_at` bounds and to be the `produced_by_event_id`
  target other edges point back to (this project already has that FK-style
  field on `GraphEdgeRecord`, currently populated ad hoc by
  `ingest_service.py`'s `event_id`).
- **EMBEDDED_OBJECT** — a small, structurally fixed cluster of properties
  (e.g. an address: street/city/postal-code) stored as a prefixed property
  group on the owning entity rather than as a node or a single scalar.
  Distinguished from PROPERTY by having internal structure; distinguished
  from NODE by never being independently queried or related-to.
- **TIME_NODE** — a special case of SHARED_NODE for temporal anchors
  (a specific date/timestamp) *only* when the workload genuinely needs
  time-based traversal (e.g. "what else happened within 7 days of this
  filing") — otherwise it collapses to PROPERTY, same as any other Value.

## Decision inputs

Two independent signals feed the decision, matching the "ontology
semantics + workload" split from the original discussion:

1. **Ontology semantics** — the extracted concept's `AnalyticsRole`
   (reusing Phase 1's `resolver_for_repository`/`build_role_resolver`
   unchanged). Actor/Event roles default toward NODE/EVENT_NODE;
   Value/Temporal/Metadata roles default toward PROPERTY.
2. **Workload signals**, evaluated per concept *instance*, not just per
   class — the same ontology class can resolve to different policies for
   different instances:
   - **Reference count**: is this exact value referenced by more than one
     entity? (A `SHARED_NODE` candidate only if reused; otherwise inline as
     PROPERTY even for an Actor-adjacent role like `regulatory agency`, if
     it turns out only one filing ever mentions it.)
   - **Relationship fan-out**: does extraction produce edges *from* or *to*
     this concept beyond the one edge that introduced it? A percentage that
     only ever appears as `reports(Company, "8.45%")` has fan-out 0 →
     PROPERTY. A regulator with `regulates`, `headquartered-in`, and
     `oversees` edges has fan-out 3 → NODE.
   - **Query DSL dependency**: does any stored/promoted DSL query
     (`nl_query_service.py`'s `:FewshotQuery`/`:TranslatedQuery` catalog)
     reference this concept as a subject/object? If real usage already
     queries it as a node, demoting it to PROPERTY would break that query
     — materialization must consult the query catalog, not just the
     ontology, before demoting an existing node.

This mirrors the "System 1 vs System 2" distinction already established in
the Phase 1 discussion: role gives the fast, ontology-driven default;
workload signals are the slower, evidence-driven override — checked in
that order, workload signals win when they disagree with the role default.

## Interfaces (Phase 3 implementation target — not implemented here)

```python
class MaterializationPolicy(str, Enum):
    NODE = "node"
    PROPERTY = "property"
    SHARED_NODE = "shared_node"
    EVENT_NODE = "event_node"
    EMBEDDED_OBJECT = "embedded_object"
    TIME_NODE = "time_node"


@dataclass(frozen=True)
class MaterializationDecision:
    policy: MaterializationPolicy
    # For PROPERTY/EMBEDDED_OBJECT: which entity the value attaches to.
    # For NODE/SHARED_NODE/EVENT_NODE/TIME_NODE: None (it attaches to itself).
    attach_to_entity_id: str | None
    property_key: str | None  # e.g. "rateOfReturn" -- None for node policies
    reason: str  # human-auditable: which signal decided this, for debugging


@dataclass(frozen=True)
class WorkloadContext:
    """Everything beyond ontology role a decision needs. Assembled once per
    ingest_text() call, not per entity -- most of this is already-loaded
    ExtractionResult data, no extra DB round trips per entity. The two
    counts below are the one part of this design that needs live-graph
    data, not just the current document's ExtractionResult -- assemble
    them via GraphClient.fetch_fanout()/fetch_reference_count() (see
    "Graph database agnosticism" above), not direct Cypher, so this
    dataclass itself stays backend-neutral regardless of how it's filled."""
    reference_count_by_value: dict[str, int]
    relationship_fanout_by_entity_name: dict[str, int]
    referenced_in_query_catalog: set[str]  # entity ids already targeted by a stored/promoted DSL query


def plan_materialization(
    entity: ExtractedEntity,
    role: AnalyticsRole | None,
    context: WorkloadContext,
) -> MaterializationDecision:
    """Pure function: ontology role (Phase 1's resolver) + workload signals
    -> a single storage decision. No I/O -- context is pre-assembled by the
    caller so this stays unit-testable without a live Neo4j/GraphDB."""
    ...
```

Pipeline insertion point (`services/ingest_service.py::ingest_text`,
illustrative, not a diff to apply now):

```
extract()  →  build WorkloadContext  →  plan_materialization() per entity
                                              │
                                              ▼
                                   MaterializationDecision
                                              │
                                              ▼
                                   StorageCommand (backend-neutral)
                                              │
                                              ▼
                                  GraphClient.execute(command)
                                              │
                       ┌──────────────────────┼───────────────────────┐
                       ▼                      ▼                       ▼
              Neo4jGraphClient        (future) NeptuneGraphClient   (future) RDF-store client
              (today's only real       — same StorageCommand,        — same StorageCommand,
               implementation)          different Cypher/Gremlin      different SPARQL UPDATE
```

The decision layer (`plan_materialization`) and the command it emits are
identical regardless of backend; only the box at the bottom of the fan-out
changes. Nothing here requires more than one adapter to exist before
Phase 3 starts — `Neo4jGraphClient` alone is enough to ship the
Materialization Engine's actual value (stop over-materializing
Value/Temporal nodes); the interface just doesn't foreclose a second
adapter later the way a direct `graph_service.upsert_entity(neo4j, ...)`
call would.

## Per-workload materialization table (FIBO, illustrative)

| Ontology class (anchor) | Default role (Phase 1) | Default policy | Override condition |
|---|---|---|---|
| `organization`, `person` | Actor | NODE | — |
| filing/announcement-shaped events | Event | EVENT_NODE | — |
| `quantity value` (percentage, monetary amount, ratio value) | Value | PROPERTY | SHARED_NODE if reference_count > 1 *and* fan-out > 0 (rare — most values are single-use) |
| `time instant` (date, time of day) | Temporal | PROPERTY | TIME_NODE if workload has ≥1 stored query doing time-window traversal |
| `regulatory agency` | Actor (but often single-mention) | NODE by role, but PROPERTY if reference_count == 1 and fan-out == 0 for that instance | promoted to NODE the moment a second entity references the same value |
| addresses / identifiers with internal structure, no ontology anchor | Metadata | EMBEDDED_OBJECT | — |

This table is not exhaustive and not binding — it's the worked example
that motivated the interface shapes above. Real anchor/policy pairs belong
in a `MATERIALIZATION_POLICY_BY_REPOSITORY` config (Phase 3), mirroring
`ROLE_ANCHORS_BY_REPOSITORY`'s per-repository, fails-open shape.

## Non-goals of this document

- No code changes. `analytics/roles.py` (Phase 1) is unaffected by
  anything here.
- **Does not retrofit the ~42 files already coupled to `Neo4jClient`
  directly**, including everything Phase 1 of this same follow-up shipped
  (`analytics/roles.py`, `services/analytics_service.py`,
  `api/analytics.py`). Introducing `GraphClient`/`StorageCommand` as the
  interface a *new* Materialization Engine writes through is in scope for
  Phase 3. Rewriting the rest of the backend's existing direct Neo4j calls
  onto that same interface is a separate, much larger, unscoped initiative
  — it should be sized and sequenced on its own, not assumed as a
  byproduct of Phase 3.
- No decision yet on backward compatibility for existing graphs already
  holding Value/Temporal nodes under the current uniform NODE policy —
  that's a real migration question (and, per the agnosticism discussion
  above, a *per-backend* migration question — a Cypher rewrite script
  doesn't help a Neptune or RDF-store deployment) deliberately deferred to
  Phase 3 scoping, not resolved here.
- No decision on whether the query DSL (`predicate(subject, object)`,
  `services/query_engine.py`) needs new syntax to query a PROPERTY-
  materialized value directly (e.g. `rateOfReturn(Company, X)` resolving
  to a property read instead of a node traversal) — flagged as an open
  question for whoever scopes Phase 3, not answered here. Note that
  `execute_query()` itself already operates on backend-neutral `Triple`
  objects (see above), so this is a DSL-semantics question, not a
  backend-coupling one — the agnosticism gap here is smaller than it looks.

## Open questions for Phase 3 scoping

1. Does `plan_materialization` run synchronously inside `ingest_text`, or
   as a deferred re-classification pass (so an entity that starts as
   PROPERTY can later be promoted to NODE once a second reference appears,
   without re-ingesting the original document)?
2. How does `EVENT_NODE`'s existing `produced_by_event_id` convention on
   `GraphEdgeRecord` (already shipped, used ad hoc) formalize into this
   engine's `EVENT_NODE` policy — is it the same mechanism or does it need
   reconciling?
3. What does `graph_service.get_graph()` return for a PROPERTY-
   materialized value that used to be a node — does the frontend graph
   canvas need a "value chip on an entity" rendering mode, or do these
   simply stop appearing as graph elements entirely (consistent with "it's
   not a graph node," but a UX regression if a user expects to see it)?
   Agnosticism note: whatever `GraphClient.fetch_graph()` returns
   (`GraphRecord`) is already the shape the frontend consumes via the
   HTTP API's JSON response, not a driver-specific object — the frontend
   never needs to know the backend either way; this question is about UX,
   not coupling.
4. **Sequencing — resolved 2026-07-14.** Phase 3 scopes narrowly: the
   Materialization Engine ships against a `GraphClient` interface with
   only `Neo4jGraphClient` implemented. The other ~42 already-Neo4j-
   coupled files are explicitly **not** retrofitted as part of this work.
   A second backend adapter is an additive change whenever a real need for
   one appears — consistent with `graphos_vision.md`'s existing guidance.
   The two questions below (translation-layer strategy, per-backend
   migration tooling) are accordingly deferred until a second backend is
   actually being added, not resolved now.
5. (Deferred until a second backend is real) Is the translation layer
   hand-built (a custom IR, what this document calls `StorageCommand`,
   deliberately small and specific to this engine's six policies) or
   should it adopt an existing standard (Apache TinkerPop/Gremlin as a
   universal graph IR, or wait for broader GQL driver support)? Gremlin
   buys existing multi-backend drivers but is a poor fit for the analytics
   layer's needs (which this project already solved differently, via
   NetworkX); a custom IR is more work but stays scoped to exactly what
   materialization needs.
6. (Deferred until a second backend is real) Per-backend migration tooling
   (Cypher `ALTER`-style rewrites vs. Gremlin traversal-based rewrites vs.
   SPARQL `UPDATE`/`DELETE`-`INSERT` — these do not share a common syntax
   the way the `StorageCommand` write path can) needs its own design pass
   when it becomes relevant; not attempted here.

## Phase 3 implementation status (shipped 2026-07-14)

Built with full TDD (RED-GREEN-MUTATE-KILL MUTANTS), scoped exactly to the
narrow sequencing decision above.

**What shipped:**

- `backend/materialization/policy.py` — `MaterializationPolicy` (all six
  values defined; only `NODE`/`PROPERTY` are ever actually decided, per
  the explicit v1 scope below), `MaterializationDecision`,
  `plan_materialization(entity, role, fanout, introducing_relationship)`
  (pure function, reuses Phase 1's `analytics.roles` resolver unchanged),
  `compute_fanout()`, `find_introducing_relationship()`.
- `backend/materialization/commands.py` — `StorageCommand` (only the
  `SET_PROPERTY` operation is constructed by anything in this codebase
  today).
- `backend/materialization/client.py` — `GraphClient` Protocol,
  `Neo4jGraphClient` (the only real implementation, per the sequencing
  decision). `SET_PROPERTY` writes into the entity's existing
  `propertiesJson` blob (`services/graph_service.py`'s pre-existing
  "arbitrary user-defined key-value pairs" mechanism), not a raw dynamic
  Neo4j field — reusing an existing seam instead of inventing a parallel
  one, so an inlined value flows through `get_graph()` and the frontend
  exactly like any other entity property already does.
- `services/ingest_service.py::ingest_text` — wired in: for each extracted
  entity, resolves its `AnalyticsRole` and fan-out, calls
  `plan_materialization`. A `PROPERTY` decision skips node creation
  (and, correctly, skips the summary/embedding/duplicate-check calls that
  only make sense for a real node) and inlines the value onto the other
  entity in its one relationship via `Neo4jGraphClient.execute()` instead
  of `graph_service.upsert_relationship()`.

**v1 scope, deliberately narrower than the full design above:**

- Only `NODE` and `PROPERTY` policies are ever decided.
  `SHARED_NODE`/`EVENT_NODE`/`EMBEDDED_OBJECT`/`TIME_NODE` remain defined
  enum values for forward compatibility with this document but nothing
  constructs them — no evidenced need for them exists yet, matching
  "no speculative generality."
- Inlining triggers only when an entity's role resolves to
  Value/Temporal/Metadata **and** its relationship fan-out is exactly 1
  (it's the target or source of exactly one relationship and nothing
  else) — the precise shape of the real noise pattern found via live
  testing. An entity referenced by more than one relationship always
  stays a node, so no information is silently dropped.
- `WorkloadContext`'s `reference_count_by_value` and
  `referenced_in_query_catalog` fields from the design above were **not**
  built — fan-out alone was sufficient to fix the real, evidenced problem.
  If a future need requires reference-count- or query-catalog-aware
  decisions, add them then.
- Existing already-ingested data is untouched — this only changes the
  behavior of new ingests going forward, per the design doc's explicit
  non-goal about migration.

**Verification:**

- Unit tests: `tests/test_materialization_policy.py` (13 tests, pure
  logic, no DB), `tests/test_materialization_client.py` (7 tests, real
  Neo4j).
- Integration tests: 3 new tests in `tests/test_ingest_service.py`
  (inlining happens for fan-out 1, stays a node for fan-out 2, existing
  Actor-role behavior is unaffected) plus all 8 pre-existing
  `test_ingest_service.py` tests pass unmodified.
- Manual mutation testing (4 representative mutants on the pure decision
  function: fanout equality inversion, ternary branch swap, self-loop
  guard inversion, `compute_fanout` increment removal) — all killed.
- Full backend suite (`pytest backend/tests/`, excluding two pre-existing,
  unrelated Graphiti-memory flaky tests) — green.
- **Live end-to-end verification** against the real running backend (real
  FIBO GraphDB, real Neo4j, real LLM — not `FakeLLM`): ingested "UBS Group
  has amount 8.45 percent." via `POST /ingest`. Result: exactly one node
  (`UBS Group`); the percentage was **not** materialized as a node — it
  landed as `properties: {"has amount": "8.45"}` on the `UBS Group` node,
  confirmed via `GET /graph/{id}`. Test data cleaned up afterward.
