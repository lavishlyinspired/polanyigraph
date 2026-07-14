# Plan: Graph Analytical Engine

**Branch**: feat/analytical-engine
**Status**: Proposed (revised after codebase audit — see "Relationship to existing services")

## Goal

Build a graph-agnostic Python analytics engine — named graph projections, a
NetworkX-only algorithm library (centrality, community, graph metrics,
similarity, classification), custom neurosymbolic analytics, write-back and
ephemeral result modes — and wire it into the three places this product
actually surfaces capability: the REST API, the agent's intent router, and
the graph UI.

This revision replaces the original igraph/NetworkX hybrid draft. Digging
into `backend/services/` turned up three existing subsystems that overlap
with the original slices; each is resolved explicitly below instead of
silently duplicated.

## Why this exists (per-capability value, not generic)

- **Centrality** — today the only "important node" signal in the product is
  `kg-visualization`'s text-only heuristic ("entities have the most
  connections" — raw degree, described in prose, never computed). Real
  pagerank/betweenness/closeness give the agent and the UI an actual ranked
  answer to "what's central in this graph," not a guess.
- **Community detection** — already exists
  (`services/community_service.py`, Neo4j GDS Louvain), but it hard-depends
  on the Neo4j GDS plugin being installed — the module's own docstring notes
  this had to be manually confirmed (`gds.version()`) and flags the Cypher
  projection call it uses as already deprecated upstream. Reimplementing
  Louvain in NetworkX and **replacing** the GDS call removes a whole class of
  deployment risk (GDS plugin present/absent, version drift) with zero
  behavior change at the API boundary. This is an infra win, not a new
  feature.
- **Graph metrics / weighted pathfinding** — `services/path_engine.py`
  already does label-addressed, human-readable-proof BFS for the UI's "find
  path between two named entities" feature, but it is unweighted — it
  ignores `GraphEdgeRecord.weight` entirely. There is currently no way to
  answer "what's the *strongest* path" (using confidence/weight) or "how
  connected is this graph overall" (diameter, average path length,
  eccentricity — used to sanity-check extraction quality: a graph that's
  mostly disconnected components is a sign extraction missed relationships).
- **Structural similarity** — distinct from `entity_resolution_service.py`,
  which already does embedding + label-token similarity for
  extraction-time dedup (empirically calibrated against real false-positive
  pairs — not being touched). Structural similarity (shared-neighbor
  Jaccard/Adamic-Adar) answers a different question: "which entities play
  the same *role* in the graph," useful for link prediction and an
  analyst-facing "entities connected the same way" view — genuinely new.
- **Classification** — genuinely new. No existing service infers a likely
  `type` for a node from its neighborhood. Useful where extraction produced
  a node with low `extraction_confidence` or an ontology mapper left it
  unclassified.
- **Custom neurosymbolic analytics** — genuinely new. The reasoning engine
  (`reasoning_service.py`, `reasoning/engine.py`) already produces
  `DerivedFact`/`ProofStep` chains and per-node `activation`, and
  `rules_store.py` already lists rules, but nothing aggregates them: no
  "which rules never fire," "how deep do proofs get," "are there circular
  derivations." This closes that gap using data structures that already
  exist — no new instrumentation needed upstream.

## Where this fits in the pipeline

```
Ingest → Neo4j (:Entity/:RELATES, graphId-scoped)
              │
              ▼
   services/graph_service.get_graph()   ← canonical domain-agnostic read model
   (GraphNodeRecord / GraphEdgeRecord — same objects path_engine,
    community_service, and the REST graph API already consume)
              │
              ▼
   backend/analytics/  (NEW — this plan)
   projection.py  → networkx.Graph/DiGraph, attributes = dataclass fields
   algorithms/*    → pure functions over that graph
   store.py        → optional write-back onto :Entity/:RELATES properties
              │
     ┌────────┼─────────────┬──────────────┐
     ▼                       ▼              ▼
  REST API              Agent (LangGraph)   Frontend
  POST /analytics/run   new "analyze"       AnalyticsPage.tsx +
                         intent + node +     GraphCanvas centrality
                         kg-analytics skill  coloring mode
```

The engine sits as a **new peer service module** next to `graph_service.py`,
`community_service.py`, `path_engine.py`, `reasoning_service.py` — it reads
via `graph_service.get_graph()` like everything else, and (for one
algorithm) writes back onto the same `:Entity` nodes those other services
already touch.

## "Graph-agnostic," concretely

The rest of this codebase is *domain*-agnostic (ontology-swappable — no
hardcoded entity types). This engine adds a second, narrower axis:
*graph-source*-agnostic. Concretely:

1. The engine's only input contract is `GraphNodeRecord`/`GraphEdgeRecord`
   (or plain iterables shaped like them) — the same contract every other
   consumer in this codebase already uses. No Neo4j types, no Cypher, no
   driver leak into `backend/analytics/`.
2. No Neo4j-specific extension is required to run it (unlike
   `community_service.py` today) — pure Python + NetworkX, runs in unit
   tests, CI, or offline against a fixture graph with no live database.
3. `NamedProjection` is built from anything that can hand back
   `GraphNodeRecord`/`GraphEdgeRecord` lists. Today that's
   `graph_service.get_graph(neo4j, graph_id)`. Nothing in `algorithms/*`
   changes if that source is swapped later (a different store, a carved
   ontology subgraph, a test fixture).

Practical upshot: **NetworkX only, no igraph.** igraph's C-backend speed
advantage only pays for itself at graph sizes this product isn't targeting
(`community_service.py`'s own docstring describes "this product's
single-analyst usage pattern"), and igraph would still need NetworkX as a
fallback for classification/custom analytics/cosine similarity anyway per
the original draft — i.e. it bought nothing but a second dependency, a C
extension to build in every environment, and a conversion layer. NetworkX
alone covers the full algorithm list below, matches this repo's
all-pure-Python dependency profile, and keeps the graph-agnostic story
simple: one graph object, one library, no format bridging.

### Prior art

Checked how other projects solve "run graph algorithms without marrying one
graph backend," since this is a solved problem with a consistent answer,
not something to invent from scratch:

- **[GitNexus](https://github.com/abhigyanpatwari/GitNexus)** (client-side
  codebase-to-knowledge-graph tool, closest analogue to this project's
  shape) keeps the exact separation this plan uses: **Graphology**
  (NetworkX's JS equivalent) for in-memory analytics — Leiden clustering,
  blast-radius/impact traversal, execution-flow tracing — completely
  decoupled from its storage layer (LadybugDB/KuzuDB). Analytics code never
  touches the database; it only ever sees the in-memory graph object. That's
  the same shape as `backend/analytics/` reading via
  `graph_service.get_graph()` and never importing `Neo4jClient`.
- Two more data points confirm this is the standard pattern, not a GitNexus
  quirk: **[networkx-neo4j](https://github.com/neo4j-graph-analytics/networkx-neo4j)**
  exposes the NetworkX *function signatures* as the stable contract while
  swapping the execution backend to Neo4j GDS underneath — i.e. the
  algorithm library's API, not any particular database, is the thing kept
  stable. **Apache TinkerPop/Gremlin** does the same thing one layer up (a
  traversal language usable against Neo4j, JanusGraph, Neptune, CosmosDB
  interchangeably) for the same reason: pick one interface, let the backend
  vary behind it.
- Takeaway adopted here: this plan's `NamedProjection`/`GraphStore` split
  already matches this pattern (algorithms only ever see a plain
  `nx.DiGraph`; only `store.py` knows about Neo4j) — the research confirms
  it rather than changing it. Two refinements worth taking from GitNexus
  specifically, folded into the sections below: **confidence-scored
  results** (not just raw scores) and an **impact/blast-radius-style
  analytic** for the reasoning layer.

## Relationship to existing services (resolved)

| New capability | Existing service | Resolution |
|---|---|---|
| Community detection (Slice 3) | `community_service.py` (Neo4j GDS Louvain, writes `communityId`) | **Replace the implementation, keep the contract.** `detect_communities`/`get_communities`, the `CommunityMember` dataclass, the `communityId` write-back property, and the `/graph/{id}/communities` API route all stay. Only the internals swap: Cypher `gds.graph.project.cypher` + `gds.louvain.write` → `backend/analytics/algorithms/community.py`'s `louvain_communities` (networkx) run against a `NamedProjection`, then written back through the *existing* write path. `test_api_communities.py` and `test_community_service.py` must keep passing unmodified (API contract), asserted explicitly as a slice acceptance criterion. |
| Weighted/graph-metric pathfinding (Slice 4) | `path_engine.py` (label-addressed, unweighted BFS, human-readable proof string, backs `/query`'s `find_path_endpoint` and `QueryPage.tsx`'s BFS Path Lab) | **No change to `path_engine.py`.** It stays as the UI-facing single-path lookup. The new engine adds what it structurally can't do: weighted shortest path (uses `GraphEdgeRecord.weight`, which BFS ignores), all-pairs distances, diameter, average path length, eccentricity — framed as graph-health/analytics metrics, not a path-lookup replacement. |
| Structural similarity (Slice 5) | `entity_resolution_service.py` (embedding + label-token Jaccard, extraction-time dedup, empirically calibrated thresholds) | **No change, no shared code path.** New engine's similarity is topology-only (shared neighbors), never marketed or used as a dedup signal — different question, different consumer (analyst-facing "similar role in the graph," not extraction-time merge candidates). |
| Classification (Slice 6) | none found | New. |
| Custom neurosymbolic analytics (Slice 7) | none found (raw ingredients exist: `reasoning_service.py`, `rules_store.py`, `GraphNodeRecord.activation`) | New, wired directly to those existing data sources — see Slice 7. |

## Data model mapping (locks down the previous review's open question)

`backend/analytics/projection.py` builds a `networkx.DiGraph` directly from
`GraphNodeRecord`/`GraphEdgeRecord` — no third node/edge model, no `Graph`
wrapper class:

```python
g = nx.DiGraph()
for n in nodes:  # GraphNodeRecord
    g.add_node(
        n.id,
        label=n.label, type=n.type, salience=n.salience,
        activation=n.activation, derived=n.derived,
        community_id=n.community_id, **n.properties,
    )
for e in edges:  # GraphEdgeRecord
    g.add_edge(e.source, e.target, id=e.id, type=e.type, weight=e.weight)
```

Every field `GraphNodeRecord`/`GraphEdgeRecord` already carries (including
`activation`, `derived`, `community_id`, `salience`, arbitrary `properties`)
survives the projection as a NetworkX attribute, unchanged in name. This is
what makes Slice 7 possible without inventing new plumbing — `activation`
and `community_id` are already there on every node the moment a projection
is built. Algorithms read `graph.nodes[n]["activation"]`, not a bespoke
accessor. `AlgorithmResult.persist(store)` writes new attributes
(`centralityScore`, `communityId`, etc.) back onto the *original*
`:Entity`/`:RELATES` records by `id`, via `GraphStore` — nothing about the
projection format needs to round-trip.

`AlgorithmResult` carries an optional `confidence: dict[node_id, float] |
None`, separate from `node_scores` — following the "Prior art" finding
above (GitNexus tags every edge/result with a resolution-confidence value,
not just a raw score, and downstream tools filter on it). Populated where
the algorithm has a real, non-trivial notion of certainty — classification
(Slice 6: prediction confidence) and structural similarity (Slice 5: score
*is* effectively a confidence) — and left `None` for algorithms where the
score is already exact/deterministic (degree, pagerank — no separate
confidence concept applies). Consumers (UI, agent) that show scores should
show confidence alongside it when present, the same way GitNexus's `impact`
tool distinguishes "WILL BREAK" (high confidence) from "LIKELY AFFECTED"
(lower confidence) rather than presenting one undifferentiated number.

## Agentic integration

This product's agent (`backend/agents/graph.py`) is a **deterministic
router**, not a ReAct loop: `_VALID_INTENTS` classifies one word (or a
compound list), `_NODE_BY_INTENT` dispatches to a specialist LangGraph node,
and `_SKILL_BY_INTENT` injects a markdown skill file
(`backend/skills/*/SKILL.md`) that tells the LLM how to narrate that node's
real output. Every existing capability (`extract`, `enrich`, `query`,
`reason`, `visualize`, `recall`) is wired in exactly that way — analytics
should follow the same shape, not a new pattern:

1. **New intent**: add `"analyze"` to `_VALID_INTENTS`
   (`agents/graph.py:112`) and `_DISCOVERY_PHRASE_BY_INTENT` (near the
   existing `"visualize"` entry).
2. **New specialist node**: `analyst_node`, added to `_NODE_BY_INTENT`
   (`agents/graph.py:149`), calling `backend/analytics` the same way
   `reasoner`/`querier` call `reasoning_service`/`query_engine` — runs a
   projection + one or more algorithms, puts structured results
   (`AlgorithmResult`) on agent state for the responder to narrate.
3. **New skill**: `backend/skills/kg-analytics/SKILL.md`, same pattern as
   `kg-visualization/SKILL.md` but grounded in *real computed numbers*
   instead of prose heuristics — e.g. "state the top-N nodes by the
   requested centrality measure with their actual scores; if communities
   were detected, report the count and size distribution; never invent a
   score that wasn't returned by the tool." Carries a `neo4j-skills`-style
   **"When NOT to Use"** line (this catalog's skills are terse and mostly
   non-overlapping by router design, but this is the one genuinely
   overlapping pair being introduced): *"Don't use for a general/prose
   overview of the graph's shape (dominant types, isolated nodes, informal
   connectivity) — that's `kg-visualization`. Use this when the user wants
   a specific computed metric (centrality ranking, community sizes,
   similarity/classification results)."* `kg-visualization/SKILL.md` gets
   the reverse pointer added in the same slice, so the two skills stay
   distinguishable at discovery time rather than both plausibly matching
   "tell me about this graph."
4. **Tool registration**: add a `run_analytics` `@tool` in
   `agents/tools.py`, mirroring `run_reasoning`/`query_graph`. Per that
   file's own docstring, these tools aren't wired into an autonomous
   tool-selection loop yet — this keeps analytics consistent with every
   other capability for whenever that loop exists, at zero extra cost now.

This answers "is it part of the agentic approach, or do we need new skills"
directly: **both**, because that's how every other capability in this repo
is exposed — a router entry for deterministic dispatch today, a skill file
for response grounding today, and a tool registration for the ReAct future.

## UI integration

No `AnalyticsPage` or panel exists today. Two concrete, low-risk additions,
both reusing patterns already in the codebase rather than inventing new UI
idioms:

1. **New page**: `frontend/src/components/pages/AnalyticsPage.tsx`,
   structured like `QueryPage.tsx` (page-level `useState`, direct
   `api.ts` calls, no separate panel component) — run an algorithm, show
   ranked results in a table, offer "write back to graph" for
   write-back-capable algorithms.
2. **GraphCanvas centrality coloring**: `GraphCanvas.tsx` already has a
   complete pattern for a second coloring axis — `showCommunities` toggles
   `communityColor`/`communityColorDark`/`communityColorFill` (hash-hue
   functions) in place of type-based coloring (`GraphCanvas.tsx:303-305`).
   Add a third mode, `showCentrality`, using the same three-function
   shape but mapping a continuous `centralityScore` to hue/lightness
   instead of hashing a discrete id. This is additive to existing code,
   not a rewrite — same conditional, one more branch.

`frontend/src/lib/api.ts` gets the new analytics endpoints following its
existing `fetch(...).then(json<T>)` convention (see `getCommunities`,
`findPath` for the pattern to match).

## Acceptance Criteria

- [x] Named graph projection loads a graphId-scoped subgraph from Neo4j into a NetworkX graph, preserving `activation`/`community_id`/`derived`/`salience`/`properties` as node attributes
- [x] At least 4 centrality algorithms produce correct scores (degree, pagerank, betweenness, closeness)
- [x] `community_service.py` runs Louvain via the new engine instead of Neo4j GDS; existing tests (`test_community_service.py`, `test_api_communities.py`) pass unmodified
- [x] `path_engine.py` is untouched; new weighted shortest path + graph-health metrics (diameter, avg path length, eccentricity, all-pairs distances) ship as new, separately-named capability
- [x] Structural (Jaccard/Adamic-Adar) similarity produces correct scores against known graph structures, with no code path shared with `entity_resolution_service.py`
- [x] Node classification (majority vote from neighborhood) predicts labels
- [x] Custom analytics: activation pattern, rule coverage, proof chain analysis, wired to real `reasoning_service`/`rules_store` data (no synthetic fixtures at the service layer — fixtures only in tests)
- [x] Results can be written back to Neo4j (e.g., `centralityScore` property on `:Entity` nodes)
- [x] Results can be returned ephemeral (JSON response, no persistence)
- [x] API routes: `POST /analytics/projections`, `GET /analytics/algorithms`, `POST /analytics/run`, `POST /analytics/persist`
- [x] Agent: `analyze` intent routes to a real specialist node backed by this engine, narrated via a new `kg-analytics` skill
- [x] Frontend: `AnalyticsPage.tsx` runs algorithms and shows results; `GraphCanvas.tsx` gains a centrality coloring mode
- [x] All code has tests (unit for algorithms, integration for Neo4j projection + write-back)

## Dependencies

- `networkx>=3.4` — only new dependency. No igraph.
- Existing: `neo4j` driver (read via `graph_service.get_graph`), `fastapi` (API routes), `langgraph`/`langchain-core` (agent wiring)

## Slices

### Slice 1: Core projection + degree centrality (walking skeleton) — ✅ DONE

`backend/analytics/{projection,result,store}.py`, `algorithms/centrality.py`, `api/analytics.py`. 17 new tests, all green; 3 manual mutants applied (edge-direction swap, algorithm-check inversion, graph_id-scoping bypass), all killed; no REFACTOR needed. Pending: commit approval.

**Value**: Proves the end-to-end pipeline: Neo4j → `GraphNodeRecord`/`GraphEdgeRecord` → NetworkX projection → algorithm → result (ephemeral + write-back), with the attribute mapping locked down before anything else is built on top of it.
**Path**: API route → create projection from Neo4j via `graph_service.get_graph` → run degree centrality (networkx) → return scores + optionally write back to `:Entity` nodes
**Required implementation skills**: `tdd`, `testing`, `graph-reasoning`
**Acceptance criteria**:
- `projection.py`'s `build_graph(nodes, edges) -> nx.DiGraph` maps every `GraphNodeRecord`/`GraphEdgeRecord` field to a NetworkX attribute per the mapping above (unit test asserts `activation`/`community_id`/`derived`/`salience`/arbitrary `properties` all survive round-trip)
- `NamedProjection` materializes a graphId-scoped subgraph from Neo4j into that `nx.DiGraph`, cached by name
- `degree_centrality(graph)` returns `dict[node_id, float]` using `networkx.degree_centrality` (already normalized)
- `AlgorithmResult` wraps scores with metadata (`algorithm`, `projection`, `node_scores`)
- `Neo4jGraphStore.write_scores(projection, property_name, scores)` writes to `:Entity` nodes
- API: `POST /analytics/projections/{graphId}` creates projection, `POST /analytics/run` executes algorithm (hardcoded single-algorithm dispatch for now — the registry doesn't exist until Slice 2, this is intentional walking-skeleton scope, not an oversight)
- Unit tests for `build_graph` (attribute mapping), `degree_centrality` (pure, no DB)
- Integration test: create projection from a test graph, run centrality, verify scores

**RED**: Write failing tests for `build_graph`, `degree_centrality`, projection creation, and write-back
**GREEN**: Implement minimal code to pass all tests
**MUTATE**: Run mutation testing — produce report
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

### Slice 2: Algorithm registry + PageRank, Betweenness, Closeness — ✅ DONE

`analytics/registry.py` (AlgorithmRegistry, default_registry), 3 new centrality functions, `/analytics/run` now dispatches via registry, new `GET /analytics/algorithms`. 26 tests green (9 new); 2 manual mutants (wrong registry key, inverted spec-none check), both killed. Fixture note: pagerank/closeness are direction-sensitive (reward being pointed *to*), so they needed a separate inward-pointing star fixture from degree_centrality's outward one — not a code bug, a test-design correction.

**Value**: Three more centrality algorithms available through the same registry/execution path, and Slice 1's hardcoded dispatch gets replaced by a real registry.
**Path**: Register algorithms → `POST /analytics/run` with algorithm name → scores returned
**Required implementation skills**: `tdd`, `testing`
**Acceptance criteria**:
- `AlgorithmRegistry` maps name → algorithm function with metadata (category, params, return type)
- Slice 1's hardcoded `/analytics/run` dispatch is replaced by registry lookup
- `pagerank(graph, alpha=0.85)` returns correct scores (`networkx.pagerank`)
- `betweenness_centrality(graph)` returns correct scores (`networkx.betweenness_centrality`)
- `closeness_centrality(graph)` returns correct scores (`networkx.closeness_centrality`)
- API: `GET /analytics/algorithms` lists registered algorithms with categories
- Unit tests for each algorithm against known graph structures
- All algorithms produce results via the same `AlgorithmResult` interface

**RED**: Write failing tests for registry + each algorithm
**GREEN**: Implement registry + 3 algorithms + Slice 1 dispatch refactor
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

### Slice 3: Migrate community detection off Neo4j GDS — ✅ DONE

`analytics/algorithms/community.py` (louvain_communities, weakly_connected_components), `community_service.py`'s GDS Cypher calls fully deleted and replaced with the networkx engine. `test_community_service.py`/`test_api_communities.py` pass with **zero diff** (`git diff --stat` confirmed empty) — the live "gds.graph.project.cypher is deprecated" warning that used to fire on every call is gone. New GDS-spy test (`test_community_service_migration.py`) asserts no `gds.` Cypher is issued. 19 tests green; 3 mutants applied, 2 killed. One mutant (skip `to_undirected()`) survived after 3 different real test designs (cluster separation, direction-reversal invariance, asymmetric in/out-star fixture) — networkx's directed-vs-undirected Louvain modularity formulas are genuinely different but converge to the same partition for realistic dense-cluster-plus-weak-bridge graph shapes at this scale. Kept `to_undirected()` anyway (semantically correct: community grouping shouldn't depend on arbitrary relationship-extraction direction) and documented this as a judged near-equivalent survivor rather than chasing an unrealistic counter-example fixture.

**Value**: Removes the Neo4j GDS plugin as a hard runtime dependency; `community_service.py` keeps its exact public contract but no longer needs GDS installed, confirmed, or version-matched.
**Path**: `community_service.detect_communities` builds a projection, runs the new engine's Louvain, writes `communityId` back through the existing write path — same as today from the API's perspective.
**Required implementation skills**: `tdd`, `testing`
**Acceptance criteria**:
- `louvain_communities(graph, resolution=1.0)` returns community assignments (`networkx.algorithms.community.louvain_communities`)
- `weakly_connected_components(graph)` returns component IDs (`networkx.weakly_connected_components` / `connected_components` on the undirected view)
- `community_service.detect_communities` internals call the new engine instead of `gds.graph.project.cypher`/`gds.louvain.write`; the Cypher GDS calls are deleted, not left dead
- `community_service.get_communities`, `CommunityMember`, and the `/graph/{id}/communities` route are unchanged
- `test_community_service.py` and `test_api_communities.py` pass unmodified — no test-file edits required, asserted as a literal check before this slice is done
- Unit tests against known community structures for the new `louvain_communities` function itself

**RED**: Write failing tests for `louvain_communities`/`weakly_connected_components`, and a failing test asserting `community_service.detect_communities` no longer calls GDS (e.g. mock/assert no `gds.` Cypher is issued)
**GREEN**: Implement community algorithms, swap `community_service.py` internals
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass (including the pre-existing `test_community_service.py`/`test_api_communities.py` unmodified), mutation report reviewed, human approves commit

### Slice 4: Graph metrics + weighted pathfinding — ✅ DONE

`analytics/algorithms/pathfinding.py` (weighted_shortest_path, all_pairs_distances, graph_diameter, average_path_length, node_eccentricity). 8 tests green; 2 mutants (disconnected-count off-by-one, dropped edge weight in dijkstra) both killed. `path_engine.py`: zero diff, confirmed via `git diff --stat`.

**Value**: Fills the concrete gap `path_engine.py` structurally can't: weighted shortest path (uses `GraphEdgeRecord.weight`) and whole-graph health metrics (diameter, average path length, eccentricity) — extraction-quality signals, not a replacement for the label-based UI path lookup.
**Path**: Query weighted shortest path or graph-health metrics on a projection → return path + distance, or metric values
**Required implementation skills**: `tdd`, `testing`
**Acceptance criteria**:
- `weighted_shortest_path(graph, source, target)` returns node path + total weight (`networkx.dijkstra_path`/`dijkstra_path_length`), addressed by node `id` (not label — distinct from `path_engine.find_path`'s label-based contract)
- `all_pairs_distances(graph)` returns a distance matrix (`networkx.all_pairs_dijkstra_path_length`)
- `graph_diameter(graph)`, `average_path_length(graph)`, `eccentricity(graph)` — computed on the largest weakly-connected component when the graph is disconnected, with the disconnected-component count reported alongside (not silently dropped)
- Unit tests against known graph structures
- Handles disconnected graphs explicitly (documented behavior above, tested)
- `path_engine.py` has zero changes (asserted via no diff to that file, not just "not mentioned")

**RED**: Write failing tests for each metric/pathfinding function
**GREEN**: Implement
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

### Slice 5: Structural similarity — ✅ DONE

`analytics/algorithms/similarity.py` (jaccard_similarity, adamic_adar_similarity, similar_node_pairs). 8 tests green. Found and fixed a real bug during RED, not a mutant: `nx.jaccard_coefficient` silently returns `[]` (no error) when given a generator instead of a materialized list for `ebunch` — consumes it internally more than once. 2 mutants applied post-fix (`>=`→`>` threshold boundary — survived once until a boundary test was added, then killed; the generator-vs-list distinction itself, implicitly re-verified by the fix). No refactor needed.

**Value**: Topology-based "similar role in the graph" signal for link prediction / analyst exploration — explicitly not a dedup mechanism (that's `entity_resolution_service.py`, untouched, different signal).
**Path**: Compute structural similarity between nodes → return similarity scores
**Required implementation skills**: `tdd`, `testing`
**Acceptance criteria**:
- `jaccard_similarity(graph, node_a, node_b)` returns float [0, 1] (`networkx.jaccard_coefficient`)
- `adamic_adar_similarity(graph, node_a, node_b)` returns a non-negative float (`networkx.adamic_adar_index`) — replaces the original draft's "cosine similarity," which was NetworkX-native-graph-theoretically undefined without first choosing a feature/embedding space; Adamic-Adar is NetworkX's actual structural analogue and needs no embedding dependency
- `similar_node_pairs(graph, threshold=0.5)` returns node pairs above a Jaccard/Adamic-Adar threshold
- Unit tests against known similarity structures
- Handles nodes with no neighbors (returns 0.0, not an error)
- Docstring/skill copy explicitly states this is not used for entity deduplication

**RED**: Write failing tests for each similarity function
**GREEN**: Implement
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

### Slice 6: Node classification (majority vote, feature-based) — ✅ DONE

`analytics/algorithms/classification.py` (Prediction dataclass, majority_vote_classification, feature_based_classification — k=1 nearest-neighbor over caller-supplied feature dicts). 7 tests green; 2 mutants (least-common instead of most-common vote, farthest instead of nearest neighbor), both killed. No refactor needed.

**Value**: Predicts likely `type` for nodes with low `extraction_confidence` or no ontology mapping, from graph structure and existing labels.
**Path**: Classify unlabeled/low-confidence nodes → return predicted types + confidence
**Required implementation skills**: `tdd`, `testing`
**Acceptance criteria**:
- `majority_vote_classification(graph, labeled_nodes)` predicts `type` for unlabeled nodes from neighbor majority
- `feature_based_classification(graph, features, labels)` predicts types using node features (properties dict + structural features — degree, clustering coefficient)
- Confidence scores for each prediction
- Unit tests against known classification structures
- Handles fully-labeled graphs (returns existing labels, doesn't overwrite them)

**RED**: Write failing tests for each classification algorithm
**GREEN**: Implement
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

### Slice 7: Custom neurosymbolic analytics — ✅ DONE

`analytics/algorithms/custom.py` (activation_patterns, rule_coverage, proof_chain_analysis w/ networkx-cycle-based circular-derivation detection, fact_impact blast-radius). Built directly against real `reasoning.engine.Rule`/`DerivedFact` dataclasses; integration test runs the real `reason()` engine (pure, no DB) and analyzes its actual output. 12 tests green; 3 mutants applied (in/out-degree swap in bottleneck check, `<=`/`<` boundary on under-activated rules, source/target indexing swap in fact_impact) — 2 initially survived and were fixed with new boundary/direction-specific tests, all 3 ultimately killed. No refactor needed.

**Value**: Aggregate analysis over reasoning output that no existing service computes — wired directly to `reasoning_service.py`, `rules_store.py`, and `GraphNodeRecord.activation`, all of which already produce this data today with no new instrumentation needed.
**Path**: Analyze reasoning engine output (real, from a live graph) → return structured insights
**Required implementation skills**: `tdd`, `testing`, `neurosymbolic-reasoning`
**Acceptance criteria**:
- `activation_patterns(graph)` reads `activation` node attributes (already present per the Slice 1 mapping) to identify high-activation clusters, propagation paths, bottlenecks
- `rule_coverage(rules, derived_facts)` — `rules` from `rules_store.load_all_rules`, `derived_facts` from `reasoning_service`/`reason.py`'s `get_facts` — shows which rules fired (by `rule_id` on each `DerivedFact`), coverage gaps (rules that never fired), under-activated rules
- `proof_chain_analysis(derived_facts)` — walks each `DerivedFact.proof_path` (tuple of `ProofStep`) — analyzes proof depth (`iteration`), rule usage frequency, and circular derivations (a `source_id`/`target_id` cycle across proof steps)
- `fact_impact(derived_facts, fact_id)` — GitNexus-style blast-radius analytic adopted from the "Prior art" research: given one base or derived fact, returns every derived fact transitively dependent on it (by walking `proof_path.source_id`/`target_id` chains forward), depth-grouped like GitNexus's `impact` tool, so an analyst editing or rejecting one fact can see what else in the reasoning output would be invalidated — a genuinely neurosymbolic-specific instance of the same pattern, not a copy of GitNexus's code-dependency version
- Unit tests for each custom analytic against fixture `Rule`/`DerivedFact`/`ProofStep` data (real dataclasses from `reasoning/engine.py`, not reinvented shapes)
- Integration test: run the real reasoning engine on a small fixture graph, then run these analytics on its actual output

**RED**: Write failing tests for each custom analytic
**GREEN**: Implement
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

### Slice 8: API routes + write-back integration — ✅ DONE

Full `/analytics/*` surface: `GET`/`DELETE /analytics/projections`, `POST /analytics/persist` (reruns the algorithm server-side and calls `AlgorithmResult.persist` — never trusts client-supplied scores). `NamedProjection` gained `list_all()`/`drop()` and `.create()` now raises `EmptyGraphError` → 400 (only `.create()`, the registry-side-effecting path; `community_service.py`'s direct dataclass construction is unaffected). 13 API tests (8 new), 84 tests clean across the whole analytics suite; 2 mutants (bypassed drop-not-found check, inverted empty-graph check) both killed. No refactor needed.

**Value**: Full API surface for the analytical engine, integrated with the existing FastAPI app the same way every other router is registered.
**Path**: All algorithms accessible via REST API, write-back works end-to-end
**Required implementation skills**: `tdd`, `testing`
**Acceptance criteria**:
- `POST /analytics/projections` — create named projection
- `GET /analytics/projections` — list active projections
- `DELETE /analytics/projections/{name}` — drop projection
- `GET /analytics/algorithms` — list available algorithms with categories + params
- `POST /analytics/run` — execute algorithm on projection, return results
- `POST /analytics/persist` — write results back to graph store
- Router registered in `app/main.py` following the existing `from api import X as X_routes` / `app.include_router(X_routes.router)` pattern
- Error handling: unknown algorithm, missing projection, empty graph
- Integration tests against real Neo4j

**RED**: Write failing integration tests for each API route
**GREEN**: Implement all API routes
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

### Slice 9: Agent + UI integration — ✅ DONE

**Backend**: `"analyze"` intent + `analyst_node` + `services/analytics_service.py` (throwaway, unregistered projection — same discipline as `community_service.py`) + `backend/skills/kg-analytics/SKILL.md` (with the "When NOT to Use" cross-reference to `kg-visualization`, which got the reverse pointer + a stale-GDS-reference fix) + `run_analytics` tool in `agents/tools.py`. `AlgorithmSpec.chart_type` added to the registry (all 4 centrality algorithms → `"bar"`); `AlgorithmResult.suggested_chart` field added. 8 new backend tests, full suite (369+) clean.

**Frontend**: Vitest + Testing Library set up from scratch (this repo had zero test infra) — `vite.config.ts`, `src/test/setup.ts`, `package.json` `test`/`test:watch` scripts. `api.ts` analytics client functions, `AnalyticsPage.tsx` (run/rank/write-back), `GraphCanvas.tsx` `showCentrality` mode (continuous-score hue interpolation, not hash-hue like community — deliberately different per the plan), `LeftNavigation`/`App.tsx` wiring. 16 frontend tests; 6 total mutants across backend+frontend, all killed (one needed a real test strengthening for row-order, one for exact-mean boundary).

**Real gap found and fixed via actual browser verification** (not just tests): `centralityScore` was computable and persistable but never flowed back — `graph_service.get_graph()`'s Cypher never selected it, so the frontend could never see a written-back score and the `GraphCanvas` toggle would never appear. Added `GraphNodeRecord.centrality_score`, the Cypher `SELECT`, and `api/graph.py`'s `NodeResponse` field (3 call sites) — verified end-to-end in a live browser against the real `default` graph: ran degree centrality (26 real entities, HDFC Bank correctly ranked highest), wrote back, confirmed via direct API call that all 26 nodes now carry `centralityScore`, and confirmed the canvas toggle button appears and recolors nodes. Also caught and fixed a copy-paste bug in the same pass: `AnalyticsPage.tsx` was writing back under a per-algorithm property name (`degree_centralityScore`) instead of the fixed `"centralityScore"` the canvas reads — would have silently never worked for any algorithm.

**Value**: Makes the engine reachable the way every other capability in this product is reachable — through the agent's router and the graph UI — not just via a REST client.
**Path**: User asks the agent an analytics question, or opens the Analytics page / toggles centrality coloring on the graph canvas.
**Required implementation skills**: `tdd`, `testing`, `react-testing`
**Acceptance criteria**:
- `"analyze"` added to `_VALID_INTENTS` (`agents/graph.py`), with a discovery phrase in `_DISCOVERY_PHRASE_BY_INTENT`
- New `analyst_node`, wired into `_NODE_BY_INTENT`, calls the analytics engine (via a service-layer function, not the HTTP API) and puts an `AlgorithmResult` on agent state
- New `backend/skills/kg-analytics/SKILL.md`, added to `_SKILL_BY_INTENT`, grounding responses in real returned scores (no invented numbers), with a "When NOT to Use → see kg-visualization" line
- `backend/skills/kg-visualization/SKILL.md` gets a reverse "for computed metrics, not prose overview → see kg-analytics" pointer added
- `run_analytics` `@tool` added to `agents/tools.py`, matching the existing (currently unused-by-ReAct-loop) tool registration pattern
- `frontend/src/lib/api.ts` gains analytics endpoint functions matching its existing `fetch(...).then(json<T>)` convention
- New `frontend/src/components/pages/AnalyticsPage.tsx`, structured like `QueryPage.tsx`: run an algorithm, show ranked results, offer write-back for write-back-capable algorithms
- `GraphCanvas.tsx` gains a `showCentrality` coloring mode alongside the existing `showCommunities` mode, reusing the same hash-hue-function shape (`centralityColor`/`centralityColorDark`/`centralityColorFill`)
- `AlgorithmResult` carries a `suggested_chart: Literal["bar", "table", "distribution"] | None` field, set per-algorithm by the registry (e.g. centrality/similarity → `"bar"` ranked list, classification → `"table"`, community sizes → `"distribution"`) — adopted from researching [NeoConverse](https://neo4j.com/labs/genai-ecosystem/neoconverse/), which has the LLM pick a chart type per result set rather than always rendering the same widget. This project's version is deterministic (registry-driven, not an LLM guess) to stay consistent with this codebase's bias against non-deterministic behavior where a plain lookup will do; `AnalyticsPage.tsx` renders the hinted chart type instead of a single fixed table, replacing `kg-visualization`'s current prose-only description for analytics results specifically (query/reasoning results are untouched — out of scope here)
- Unit tests for the router change (intent classification, node dispatch) and the new frontend page/coloring mode

**RED**: Write failing tests for intent routing, the analyst node, and the frontend page/coloring mode
**GREEN**: Implement
**MUTATE**: Run mutation testing (backend portion)
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

## Verification

After all slices:
1. `pytest backend/tests/` — full suite passes, including pre-existing `test_community_service.py`/`test_api_communities.py` unmodified (Slice 3's contract)
2. Manual: create projection, run each algorithm via `POST /analytics/run`, verify results make sense against a known small graph
3. Manual: write-back → check `:Entity` properties updated in Neo4j (`centralityScore`, `communityId`)
4. Manual: ask the agent an analytics question ("what are the most central entities in this graph?") → confirm it routes through the new `analyze` intent and narrates real scores
5. Manual: open `AnalyticsPage.tsx`, run an algorithm, confirm results render; toggle `showCentrality` on the graph canvas and confirm node coloring updates

## Follow-up: Analytics Role Mapping (Phase 1, added 2026-07-14) ✅ DONE

Live testing of the shipped analytics engine against the real FIBO-backed
"default" graph surfaced a genuine noise problem: date/percentage entities
(`8-45`, `5-basis-points`, `august-5-2026`, ...) were dominating
`degree_centrality`'s "most central entity" ranking purely by co-occurring
with every fact that cites a rate or a date — not because they're actually
central subject matter.

Fix: a small universal role taxonomy (Actor/Event/Value/Temporal/Metadata),
mapped per-ontology-repository onto a handful of real "anchor" ontology
classes. Any class that IS-A an anchor (reflexively or transitively, via the
existing `OntologySchema.build_subclass_matcher()`) inherits its role;
Value/Temporal-role node scores are multiplied by 0.0 (a score-level
multiplier, not a graph-structure change, so betweenness-style algorithms
still route through those nodes correctly). Scoped to `category ==
"centrality"` algorithms only. Fails open: an unmapped repository, or a node
type with no matching anchor, is left unweighted (matches current
behavior) — confirmed for the FIBO repository with just two anchors
(`quantity value` → Value, `time instant` → Temporal), which covers every
noisy entity type found via live analytics runs without enumerating FIBO's
2000+ classes individually.

- [x] `backend/analytics/roles.py` — `AnalyticsRole`, `DEFAULT_ROLE_WEIGHT`, `ROLE_ANCHORS_BY_REPOSITORY`, `build_role_resolver`, `resolver_for_repository`, `apply_role_weights`, `apply_role_weights_if_centrality`
- [x] `services/analytics_service.run_default_analysis` — optional `graphdb`/`repository` kwargs, backward-compatible (omitting them keeps prior unweighted behavior)
- [x] `agents/graph.py`'s `analyst_node` wired to pass `graphdb`/`settings.graphdb_repository` through
- [x] `api/analytics.py`'s `POST /analytics/run` and `POST /analytics/persist` — role-weight centrality results via injected `GraphDBClient`/`Settings`
- [x] Unit tests (`test_analytics_roles.py`, 17 tests) + integration tests (`test_analytics_service.py`, `test_api_analytics.py`, `test_agent_graph_analyze.py`) proving the fix end-to-end through service, agent, and HTTP API layers
- [x] Manual mutation testing (6 representative mutants: score arithmetic, guard inversions, argument-order swap, `.get()` default values) — all killed
- [x] Live-verified against the real running "default" graph via `curl`: `5-basis-points`, `8-45`, `august-5-2026`, `july-7-2026`, `july-10-2026` all now score `0.0`; `hdfc-bank` (0.32), `credit-suisse`/`switzerland`/`ubs-group` (0.08) rank at the top instead

Phase 2 (design doc for a Semantic Materialization Engine — the deeper
question of why these entities become graph nodes at all rather than
properties) and Phase 3 (implementing that engine) are tracked separately,
not part of this plan.

---
*Delete this file when the plan is complete. If `plans/` is empty, delete the directory.*
