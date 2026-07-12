# graphiti-core Integration: Decision & Plan

> **Added**: 2026-07-12
> **Status**: Plan only — nothing in this document has been implemented.
> **Supersedes/extends**: `PLAN.md` §20 ("Decision Record: Temporal Memory Layer (Graphiti/Zep-inspired, rebuilt natively)"), which explicitly deferred any dependency on `graphiti-core` (§20.6). This document re-opens that decision on your request and gives a corrected integration plan either way.

## 0. Read this first

Before anything else: **this project already has a documented decision not to depend on `graphiti-core`, and has already built 5/5 of the capabilities Graphiti would provide, natively, tested, and live-verified.** That's `PLAN.md` §20, dated one day before this document. I'm restating it because it changes the shape of the question you asked — this isn't "how do we bolt Graphiti onto a system with no memory layer," it's "do we replace or augment a working, native memory layer with an external library the project already deliberately chose not to use."

What's already built (`backend/services/`):

| Capability | Graphiti's version | This project's native version | Status |
|---|---|---|---|
| Provenance (source → fact) | `EpisodicNode` → `EntityEdge.episodes` | `IngestEvent-[:PRODUCED]->Entity`, `producedByEventId` on edges | Done, tested |
| Bi-temporal facts | `EntityEdge.valid_at`/`invalid_at` | `:RELATES.validAt`/`invalidAt`, `get_relationship_history()` | Done, tested, one documented simplification (see §3.5) |
| Evolving entity summaries | `EntityNode.summary` | `:Entity.summary` via `summary_service.generate_summary` | Done, tested, live-verified |
| Chat session memory | Zep's `memory.add`/`memory.get` | `:ChatSession`/`:ChatMessage`, `chat_history_service.py` | Done, tested, live-verified (and now streams over SSE) |
| Community detection | `build_communities()` | `community_service.py` via real Neo4j GDS Louvain | Done, tested, live-verified |

What's genuinely **not** built, and is the real gap: **semantic/embedding-based search**. `services/memory_service.py` does `WHERE toLower(x) CONTAINS toLower($query)` — plain substring matching, no vector similarity, no fulltext ranking. This is the one piece of Graphiti's value proposition this project doesn't already have an answer for.

That reframes the whole decision. Section 4 below gives you the actual choice: adopt the library for that one gap, close that one gap natively without the library, or leave it.

## 1. Correcting your proposed architecture

Your instinct — memory layer on top of Neo4j, don't let it touch GraphDB, wrap it behind a service interface — is directionally right and matches how this codebase is already built (services own their store, API/agent layers never touch Cypher directly). Four specific corrections, verified against the real `graphiti-core` source (`/Users/akash/KG_Projects/graphitti/graphiti`) and the real code in this repo, not assumptions:

### 1.1 "Separate Neo4j database" — right idea, wrong mechanism

You wrote:
```python
graphiti = Graphiti("bolt://localhost:7687", "neo4j", "password")
```
implying you'd pass a database name at construction. You can't — `Graphiti.__init__` takes only `uri`, `user`, `password` (plus client overrides); there's no `database` parameter (`graphiti_core/graphiti.py:138-151`). The Neo4j driver defaults to database `"neo4j"` (`graphiti_core/driver/neo4j_driver.py:69`).

Database selection actually happens through `group_id`: `add_episode(group_id=...)` clones the driver to a different database when `group_id` differs from the driver's current one (`graphiti.py:1079-1082`, `driver.clone(database=group_id)`). So the "separate database" isolation you want is achievable, just via a different lever than the constructor. This is fine — it's the same idea, corrected.

This project's own `Neo4jClient` already does per-call database selection (`db/neo4j_client.py:29`, `session(database=self._settings.neo4j_database)`), so the *pattern* of "one driver, database chosen per call" is already familiar in this codebase — just note that Graphiti's version of that pattern is keyed off `group_id`, not a settings value you control directly.

### 1.2 GraphDB / ontology resolution — Graphiti already has a hook for this, you don't need a separate resolver step

Your diagram puts a standalone "Ontology Resolver" between Graphiti and GraphDB, disambiguating e.g. "Apple" → Apple Inc. vs. Apple (fruit) after extraction. Graphiti actually supports constraining extraction *at ingest time*: `add_episode(entity_types: dict[str, type[BaseModel]] | None)`. Each entry is a Pydantic model whose docstring becomes the type description in the extraction prompt, and the LLM is instructed to classify into only those types (falls back to a generic "Entity" type otherwise) — verified in `graphiti_core/utils/maintenance/node_operations.py:152-181`.

That means the type vocabulary this project already loads from Ontotext GraphDB (`ontology/loader.py`'s `load_schema()`, already used by `kg-extraction` and rule validation) could be handed to Graphiti as `entity_types` directly, so extraction is ontology-constrained from the start — no separate post-hoc resolution pass needed. Cleaner than your diagram, same effect.

### 1.3 The blocking gap you didn't flag: embeddings are mandatory, not optional

This is the correction that matters most. Graphiti's entity/edge deduplication and its `search()`/`search_()` methods **require** an embedder — confirmed in `node_operations.py` (cosine similarity dedup, threshold `0.6`) and `search/search.py` (`embedder.create()` builds the search vector). Default is `OpenAIEmbedder`, 1024-dim (`graphiti.py:223`).

I told you earlier this session, from direct code inspection: **this project has zero embedding infrastructure today** (`grep -rn "embedding|vector"` across `backend/` returns nothing outside tests). Adopting `graphiti-core` isn't just "add a pip package" — it's "stand up an embedding pipeline for the first time," because without one, Graphiti's own dedup and search degrade or fail outright. This is the real cost of your proposal, and it's bigger than the Neo4j-database-separation question you were focused on.

Two ways to supply it, both viable:
- **`OpenAIEmbedder`** against the NVIDIA endpoint already configured (`llm_base_url`/`nvidia_api_key` in `app/config.py`) — works only if that endpoint serves an embeddings model; not confirmed, needs a live check.
- **Local embeddings** via the optional `sentence-transformers` extra (`graphiti-core[sentence-transformers]`) — no external API dependency, but a new local ML dependency and a real download/runtime cost.

### 1.4 Dependency compatibility — actually fine, correcting an assumption you didn't state but I'd have flagged anyway

`graphiti-core` requires `neo4j>=5.26.0`, `openai>=1.91.0`, `pydantic>=2.11.5`. This project's `requirements.txt` already pins `neo4j>=5.26`, `openai>=1.54`, `pydantic>=2.9` — all compatible floors, pip will just resolve upward. No version conflict. (It does add `tenacity`, `numpy`, `python-dotenv`, and `posthog` as new transitive dependencies — `posthog` is telemetry, see §3.6.)

## 2. What LangGraph piece you already have

Your diagram's "LangGraph Agents" box is real and already exists: `backend/agents/graph.py` is a compiled `StateGraph` with a router that classifies intent (`extract | enrich | query | reason | visualize | recall`) and branches accordingly. There's already a `memory_agent` node (`graph.py:159-169`) that calls `memory_service.search_memory` on `recall` intent and folds hits into the responder's prompt. If you adopt Graphiti, this is the exact node that would call it instead — no new agent-layer plumbing needed, just swap what `memory_agent_node` calls internally.

## 3. What adopting `graphiti-core` would actually change

### 3.1 Schema Graphiti would write (verified from `graphiti_core/graph_queries.py`)

Node labels: `Entity`, `Episodic`, `Community`, `Saga`. Relationship types: `RELATES_TO`, `MENTIONS`, `HAS_MEMBER`, `HAS_EPISODE`, `NEXT_EPISODE`. It also creates fulltext indices (`episode_content`, `node_name_and_summary`, `community_name`, `edge_name_and_fact`) and UUID/temporal indices per node/edge type.

Note the label collision risk: **this project already has an `:Entity` label** (`services/graph_service.py`) with its own meaning (real domain entities, `graphId`-scoped, ontology-typed). Graphiti's `:Entity` is a different schema (`name_embedding`, `summary`, `attributes`, no `graphId`/ontology-type concept). Running both in the *same* Neo4j database would either collide on the label or force you to prefix/namespace one of them — this is the strongest argument for the separate-database approach you proposed, not a nice-to-have.

### 3.2 What you'd gain

- **Real hybrid search** (embedding cosine similarity + Lucene fulltext + graph traversal) over facts and entities, replacing `memory_service.py`'s `CONTAINS` matching. This is the one capability this project doesn't already have a good answer for.
- **Embedding-based entity dedup** at ingest — reduces duplicate entities from name variants ("Deutsche Bank" vs "Deutsche Bank AG") in a way exact-match `MERGE` in `graph_service.upsert_entity` can't.
- **LLM-generated community summaries** (`build_communities()`) — the native `community_service.py` gives you Louvain clusters (structural) but no narrative summary of what each cluster *is*; Graphiti's would.
- A maintained bi-temporal invalidation implementation, vs. the native version's documented known simplification (§3.5 below).

### 3.3 What you'd pay

- A new mandatory dependency graph (embeddings, `openai`/`anthropic`/etc. client libs even if unused, `posthog`).
- Standing up embedding infrastructure for the first time, project-wide.
- A second, separately-schemaed memory system running alongside the native one — either replacing it (throwing away tested, live-verified, working code) or running in parallel (two places "memory" partially lives, until you fully migrate).
- Reversal of a decision this project's own planning doc made one day earlier, with reasons given (§20.1, §20.6) — worth being sure the new information (this conversation) actually changes the calculus, not just revisits it because the library came up again.

### 3.4 Telemetry — needs disabling before use

`graphiti-core` sends anonymous PostHog events on `Graphiti()` initialization by default (`graphiti_core/telemetry/telemetry.py`) — opt-out via `GRAPHITI_TELEMETRY_ENABLED=false`. Given this project processes real (if synthetic-for-now) financial-document content, this should be set explicitly, not left on defaults, before any real ingest touches it.

### 3.5 The native implementation's one open gap, for context

`PLAN.md` §20.4 item 2 already documents a known limitation in the native bi-temporal implementation: it treats every relation type as single-valued per source (no cardinality metadata from the ontology to know if a predicate like "hasSubsidiary" is genuinely multi-valued), so a second assertion would incorrectly invalidate a prior *co-existing* fact rather than a superseded one. Graphiti's model has the same theoretical issue unless you feed it cardinality info via `entity_types`/edge type constraints — it's not a Graphiti-solves-this-for-free gap, just worth not overstating as a reason to switch.

### 3.6 FalkorDB, if it ever comes up

Unprompted, but worth flagging since it's sitting in this project's `.env` unused: `graphiti-core` also supports FalkorDB as a graph backend (`falkordb>=1.1.2` optional extra), and this project already has provisioned-but-unwired `FALKOR_DB_*` credentials (found in the `.env` audit earlier this session). Not a recommendation — just noting the coincidence in case it changes your thinking about where Graphiti's data should live (a dedicated FalkorDB instance instead of a second Neo4j database would sidestep the label-collision issue in §3.1 entirely). Out of scope for this plan unless you want it explored separately.

## 4. Your actual options

### Option A — Don't adopt `graphiti-core`; close the real gap natively (recommended default)

Add vector search to the *existing* native memory layer instead of importing a new library: an embedding column on `:Entity.summary` and `:ChatMessage.content`, a Neo4j vector index (native Neo4j 5.x feature, no plugin needed), and `memory_service.search_memory` upgraded from `CONTAINS` to a hybrid vector+text query. This closes the one real gap (§0) without a second schema, a new mandatory dependency, or reversing §20's decision — consistent with this project's stated "rebuild natively" convention, and the smallest slice that fixes the actual problem.

Cost: still need an embedding model from somewhere (same §1.3 question — NVIDIA endpoint or local `sentence-transformers`), but nothing else changes: no new node labels, no separate database, no `graphiti-core` dependency footprint, no telemetry to manage.

### Option B — Adopt `graphiti-core`, correctly scoped (if you want the library specifically, not just the capability)

Use it as a bounded, swappable memory-search upgrade, isolated behind the interface you already sketched (`memory.ingest`/`memory.search`/`memory.timeline`/`memory.current_state`) so nothing outside `services/memory_service.py` (and the `memory_agent` node) ever imports `graphiti_core` directly. Concretely:

1. **Isolation**: separate Neo4j database (e.g. `graphiti_memory`, using the `group_id` mechanism from §1.1) — not the same database as `graphos`'s `:Entity`/`:RELATES` schema, to avoid the label collision in §3.1.
2. **Ontology constraint**: pass this project's real GraphDB-derived types to `add_episode(entity_types=...)` (§1.2), built from `ontology/loader.py`'s existing `load_schema()` — don't let Graphiti invent free-form types when this project already has a real type vocabulary.
3. **Embeddings**: resolve §1.3 first — confirm whether the NVIDIA endpoint serves an embeddings model, or add `sentence-transformers` as a local fallback. This is a prerequisite, not a detail.
4. **Wrapper service**: `services/graphiti_memory_service.py` (new), implementing exactly the four methods you proposed, each a thin call into a module-level `Graphiti` client. `memory_agent_node` in `agents/graph.py` calls this instead of (or alongside, during migration) `memory_service.search_memory`.
5. **Config**: new `Settings` fields (`graphiti_neo4j_database`, `GRAPHITI_TELEMETRY_ENABLED=false` at process env level, embedding model choice) — same pattern as every other config value in `app/config.py`.
6. **Migration, not replacement, of existing data**: the native `:ChatSession`/`:ChatMessage` and `:Entity.summary` data stays where it is and keeps working (nothing reads Graphiti's schema today); Graphiti's store starts empty and accumulates going forward. Decide explicitly whether/when to backfill history into it, or let it start fresh.
7. **Tests**: per this project's non-negotiable TDD convention — fake the `Graphiti` client the same way `FakeLLM` fakes `LLMClient` in existing tests, so `graphiti_memory_service.py` tests don't require a live embedding call or a live Neo4j `graphiti_memory` database in CI. Real end-to-end verification (per this session's established pattern) against the actual running stack, once.
8. **Kill switch**: keep `memory_service.py` (native) importable and working throughout — if Graphiti's embedding dependency turns out to be a dead end (§1.3 unresolved), you haven't broken chat/recall, you've just not gained the upgrade yet.

### Option C — Full replacement of the native memory layer with `graphiti-core`

Not recommended. Would mean discarding tested, live-verified, working code (§0's table) to re-derive the same capabilities through a new dependency, for a net gain limited to the search-quality improvement in §3.2 — the same gain Option A gets natively, cheaper.

## 5. My recommendation

**Option A.** The honest answer to "how do I use graphiti-core" is: the one thing it would give you that you don't have is embedding-based search, and you can add that directly to the memory layer you already built and tested, without a new dependency, a new database, a schema collision to manage, or telemetry to disable. That's not a dodge of your question — it's the corrected version of your own instinct (wrap it behind a service interface, keep it swappable) applied one layer earlier: don't wrap the library, build the interface, and let the *interface* be what's swappable, exactly like your `memory.ingest`/`memory.search` sketch — just implemented natively first.

If there's a reason to want the actual library specifically — e.g. you're planning multi-user/multi-tenant memory where Zep's session/user model matters more, or you want Graphiti's maintained temporal-invalidation edge cases without re-deriving them — Option B is the corrected, safe way to do it. Worth naming that reason explicitly before starting, since "the capability" and "the library" aren't the same ask, and §0 shows the capability gap is narrower than it first looked.
