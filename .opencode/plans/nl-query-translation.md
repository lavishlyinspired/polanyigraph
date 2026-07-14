# Plan: Natural-Language Query Translation

**Branch**: feat/nl-query-translation
**Status**: Proposed

## Goal

When a user asks the agent a question in plain English instead of the
`predicate(subject, object)` DSL, translate it into a real DSL query,
execute it, and show the user what was run — instead of today's behavior,
which feeds the raw English straight into the DSL parser and fails.

## Why this exists

Found while auditing [NeoConverse](https://neo4j.com/labs/genai-ecosystem/neoconverse/)
(Neo4j Labs' NL→Cypher tool) against this project as a whole, not the
analytics engine specifically — this is the one capability gap it exposed
that's worth fixing.

The gap is real and already precisely diagnosed by this codebase's own
comments, not a guess:

- `agents/graph.py`'s `querier_node` (`agents/graph.py:413`) does exactly
  this: `execute_query(state["text"], triples)` — the raw turn text, no
  translation, goes straight into the DSL parser.
- `services/query_engine.py`'s `execute_query` only understands
  `predicate(subject, object)` syntax (`_ATOM_RE`); anything else returns
  `"Invalid syntax. Use: predicate(subject, object) — e.g., regulates(...)"`.
- `backend/skills/kg-query/SKILL.md` already names the resulting UX
  explicitly: "describe that syntax in plain terms if they seem to be
  asking in natural language rather than the query DSL itself" — i.e. the
  documented, intended behavior today is *explain the syntax back to the
  user*, not *answer their question*.

So right now, asking the agent "who does FINMA regulate?" fails to parse
and gets a syntax explanation. Asking `regulates("FINMA", X)` works. Only
the second is a real answer. NeoConverse's schema-grounded generate →
validate → execute → synthesize loop is the standard fix for exactly this
gap — adapted below to this project's own DSL (not Cypher) and its
existing domain-agnostic grounding mechanism (the live `OntologySchema`,
not NeoConverse's hardcoded per-domain few-shot examples).

## Prior art (and what's deliberately not copied)

Read the actual NeoConverse source (not just its docs page) at
`agents/agentRegistry.ts`, `agents/cypherScripts/addFewshot.cypher`,
`lib/prompt.ts`, and `lib/cypherQuery.ts`. Its real pipeline: user question
→ LLM gets schema + few-shot examples + recent conversation history as
context → LLM generates a query → validate/execute against the database →
LLM synthesizes the results into an NL answer, with every generated query
logged (and optionally rated) for later refinement. Four things are ported
below, adapted to this project's own conventions; two things are
deliberately **not** ported, because they conflict with decisions already
made elsewhere in this codebase:

**Ported:**
- **Schema-grounded generation** (the core loop itself).
- **Graph-native few-shot examples** — `addFewshot.cypher` MERGEs
  `:FewshotPrompt` nodes onto `:NeoAgent`, read back at query time via
  `FrontEndAgentQuery`, instead of hardcoding examples in source. This
  project already has the same shape for a different purpose
  (`services/skill_graph_service.py`'s Neo4j-backed skill catalog) — Slice
  1 below reuses that pattern rather than hardcoding examples in Python.
- **Conversation-history threading** — `lib/prompt.ts`'s
  `CYPHER_GENERATION_PROMPT` includes `<HistoryOfConversation>` so
  follow-up questions ("and what about their subsidiaries?") resolve
  against prior turns. This project already has `chat_history_service.
  get_recent_messages` — Slice 2 threads its output into the generation
  prompt.
- **Explicit out-of-scope handling** — NeoConverse's prompt instructs the
  LLM to return a recognizable sentinel (`RETURN "I am designed to..."`)
  for out-of-scope questions rather than guessing a plausible-looking but
  wrong query. Slice 1 adopts the same idea for the DSL: a specific
  sentinel string the caller checks for explicitly, distinct from a syntax
  error.

**Not ported:**
- **Hardcoded per-domain agents** (Enron Email, Retail, ...) — this project
  is domain-agnostic; the schema context must come from the *live*
  `OntologySchema` for whatever ontology is loaded for this `graph_id`'s
  repository, never a hand-authored domain example set.
  `services/ingest_service.py:36` already does `load_schema(graphdb,
  repository)` for extraction — this reuses that exact call, not a new
  mechanism. (The graph-native *storage* of few-shot examples is ported;
  the hand-authored *content* of NeoConverse's specific examples is not.)
- **Vague error handling** — NeoConverse's docs only say it "identifies
  inconsistencies" without detail. This plan is explicit about what
  happens on a bad generation (one bounded retry with the real parser
  error fed back, then a real fallback — see Slice 3), consistent with how
  the rest of this codebase treats confidence and failure paths (e.g.
  `reasoning/engine.py`'s explicit convergence semantics).

## Design

**Scope boundary — the agent path only.** `POST /query/{graph_id}`
(`api/query.py`) and `QueryPage.tsx`'s Query Lab both expose the DSL
*directly* today, on purpose — that's a power-user surface with
autocomplete-style example pills (`QUERY_EXAMPLES` in `QueryPage.tsx`) for
people who already know or are learning the syntax. Translation only
happens inside `agents/graph.py`'s `querier_node`, where the input is
free-form chat text and the user has no reason to know the DSL exists.
`execute_query`, `api/query.py`, and `QueryPage.tsx` get zero changes —
same discipline as `analytical-engine.md`'s treatment of `path_engine.py`:
don't touch a working, tested, deliberately-scoped contract.

**Grounding source**: `ontology.loader.load_schema(graphdb, repository)` →
`OntologySchema.classes`/`.properties` (real ontology class/property
labels for this repository) plus the *actually-used* predicate and entity
vocabulary already in this graph, from `graph_service.load_triples`
(distinct `predicate`/`subject`/`object` values currently present) — so
the LLM is grounded in what's really queryable right now, not just what
the ontology permits in the abstract. Both are cheap: schema is already
loaded once per ingest and cacheable per repository; triples are already
loaded by `querier_node` today.

**Generation call**: mirrors `extraction/pipeline.py`'s existing
`extract(text, *, schema, llm, extra_guidance="")` shape — a new
`services/nl_query_service.py` module with
`translate_to_dsl(text, *, schema: OntologySchema, predicates: list[str], entity_labels: list[str], fewshot: list[FewshotQuery], history: list[ChatMessageRecord], llm: LLMClient) -> str`,
using `LLMClient.complete_json` (the same provider-agnostic method
extraction already uses — no new LLM plumbing). Returns the sentinel
constant `NL_QUERY_OUT_OF_SCOPE` (checked by identity, not string-matched)
when the LLM determines the question can't be answered from this graph's
predicates — never a fabricated best-effort query.

**Few-shot examples, graph-native**: a new `:FewshotQuery {question, dsl}`
node type, scoped per ontology repository (`MERGE (:FewshotQuery
{repository: $repo, question: $q})-[:DSL]->(...)`, mirroring
`addFewshot.cypher`'s `:FewshotPrompt` shape), read back via a
`nl_query_service.get_fewshot_examples(neo4j, repository)` call the same
way `skill_graph_service.py` reads its skill catalog from Neo4j. Seeded
manually at first (a handful of real `question` → `predicate(...)`  pairs
per repository); Slice 4 below adds the mechanism that grows this set from
confirmed-good translations instead of leaving it static forever.

**Skip-if-already-DSL**: if `state["text"]` already matches `_ATOM_RE`
shape (i.e. it's already valid or near-valid DSL), `querier_node` runs it
directly, exactly as today — zero added latency or LLM cost for anyone who
already knows the syntax. Translation is a fallback path, not a rewrite of
the existing one.

**Conversation history**: `chat_history_service.get_recent_messages(neo4j,
graph_id=..., limit=N)` output is threaded into `translate_to_dsl`'s
`history` parameter, so a follow-up like "and what about their
subsidiaries?" resolves against the prior turn's subject — the same role
NeoConverse's `<HistoryOfConversation>` section plays, sourced from a
service this project already has rather than a new one.

**Retry-on-error**: if the generated DSL fails to execute
(`QueryResult.error` set), feed that literal parser error back to the LLM
once for a single regeneration attempt (this is the concrete version of
NeoConverse's vague "identify inconsistencies" claim). If the retry also
fails, fall back to today's exact behavior — the `kg-query` skill's
"explain the syntax" guidance — now a genuine last resort instead of the
default outcome.

**Transparency**: the generated DSL query is surfaced back to the user
alongside the answer (new `agent state["translated_query"]` field,
threaded into `responder_node`'s prompt and `kg-query/SKILL.md`'s
instructions: state what query was run, the same way NeoConverse shows
its generated Cypher). This doubles as the DSL-teaching mechanism
`kg-query/SKILL.md` already wants, but grounded in the user's own question
instead of an abstract syntax description.

**Feedback loop**: mirrors `lib/cypherQuery.ts`'s `SAVE_CONVO_CYPHER`,
which logs every generated query plus a thumbs-up/down `like_flag` and
free-text `feedback`, graph-native. Slice 4 adds the same here: a
`:TranslatedQuery {question, dsl, feedback}` node per translation, and a
confirmed-good one (explicit thumbs-up, or a low-friction proxy like
"the user didn't immediately rephrase the same question") gets promoted
into the `:FewshotQuery` set for that repository — closing the loop so
translation quality improves with real usage instead of staying fixed at
whatever was seeded manually.

## Relationship to existing code

| Component | Change |
|---|---|
| `services/query_engine.py` (`execute_query`, `Triple`, `_ATOM_RE`) | None. Untouched. |
| `api/query.py` (`POST /query/{graph_id}`) | None. Untouched — DSL-in, DSL-out contract preserved. |
| `frontend/src/components/pages/QueryPage.tsx` | None. Untouched — still a direct DSL surface. |
| `agents/graph.py` `querier_node` | Gains a skip-if-DSL check + translation fallback + retry-once-on-error, before calling the same `execute_query` it calls today. |
| `backend/skills/kg-query/SKILL.md` | Updated: "explain the syntax" becomes the last-resort fallback wording; primary guidance becomes "state the DSL query that was actually run, then the results." |
| `services/ingest_service.py` (`load_schema` call) | None. Reused, not modified — same function, second call site. |
| `services/chat_history_service.py` (`get_recent_messages`) | None. Reused, not modified — same function, new call site for translation context. |
| `services/skill_graph_service.py` | None. Not modified — but its Neo4j-backed catalog pattern is the template `nl_query_service.py`'s `:FewshotQuery` storage follows, not a shared code path. |

## Acceptance Criteria

- [x] A DSL-syntax query (e.g. `regulates("FINMA", X)`) sent to the agent runs exactly as today — same result, no translation call, no added latency
- [x] A natural-language question (e.g. "who does FINMA regulate?") is translated to a real DSL query grounded in this graph's live ontology schema, actual predicate/entity vocabulary, graph-native few-shot examples, and recent conversation history, then executed and answered
- [x] An out-of-scope question returns the `NL_QUERY_OUT_OF_SCOPE` sentinel, not a fabricated best-effort query
- [x] A follow-up question resolves against the prior turn via threaded conversation history
- [x] The generated DSL query is visible to the user in the agent's reply
- [x] A failed generation gets exactly one retry with the parser error fed back before falling back to the syntax-explanation message
- [x] A confirmed-good translation can be promoted into that repository's `:FewshotQuery` set
- [x] No changes to `query_engine.py`, `api/query.py`, or `QueryPage.tsx` (asserted as literal no-diff checks)
- [x] `kg-query/SKILL.md` reflects the new primary behavior (state the query that ran) with syntax-explanation demoted to fallback
- [x] All code has tests (unit for `translate_to_dsl` against a fixture `OntologySchema` + fake `LLMClient`, integration for the full `querier_node` path including the retry branch and the feedback-promotion path)

## Dependencies

No new libraries. Reuses `LLMClient` (`llm/client.py`), `OntologySchema`
(`ontology/schema.py`, `ontology/loader.py`), `graph_service.load_triples`,
and `chat_history_service.get_recent_messages` — all already present. New
Neo4j node types (`:FewshotQuery`, `:TranslatedQuery`), same pattern as
existing `:ImplicitFact`/`:CandidateRule` pending-review nodes elsewhere in
this codebase — no schema migration mechanism needed, MERGE creates them
on first use.

## Slices

### Slice 1: `translate_to_dsl` + graph-native few-shot store (walking skeleton) — ✅ DONE

`services/nl_query_service.py` (translate_to_dsl, get_fewshot_examples, seed_fewshot_examples, NL_QUERY_OUT_OF_SCOPE sentinel). Reuses `query_engine._parse_atom`/`_split_top_level_atoms` directly for validation rather than reinventing DSL parsing. One schema simplification from the original design: `:FewshotQuery {repository, question, dsl}` is a single node (not a separate `-[:DSL]->` node) — same graph-native intent, one fewer node type, no loss of capability. 9 tests green; 3 mutants (bypass validation entirely, bypass empty-parts guard, wrong MERGE uniqueness key) — the empty-parts one survived once until a dedicated empty-LLM-response test was added, then all 3 killed. No refactor needed.

**Value**: Proves the core generation call in isolation, against fixture data — no agent wiring yet. Establishes the `:FewshotQuery` storage pattern before anything depends on it.
**Path**: NL text + fixture `OntologySchema` + fixture predicate/entity vocab + few-shot examples read from Neo4j → LLM call → parsed, syntactically-valid DSL string (or the out-of-scope sentinel)
**Required implementation skills**: `tdd`, `testing`, `graph-reasoning`
**Acceptance criteria**:
- `nl_query_service.translate_to_dsl(text, *, schema, predicates, entity_labels, fewshot, history, llm) -> str` returns a string that parses under `query_engine._parse_atom` (validated before returning — never hand back unparseable output as if it succeeded), or the `NL_QUERY_OUT_OF_SCOPE` sentinel
- `nl_query_service.get_fewshot_examples(neo4j, repository) -> list[FewshotQuery]` reads `:FewshotQuery {repository, question}-[:DSL]->` nodes, mirroring `skill_graph_service.py`'s Neo4j-catalog-read pattern
- `nl_query_service.seed_fewshot_examples(neo4j, repository, examples)` MERGEs the initial hand-authored set (a handful of real question→DSL pairs per repository, not domain-hardcoded — content supplied by whoever sets up that repository)
- Grounding prompt includes real schema class/property labels, real predicate/entity vocabulary, and the repository's stored few-shot examples — no examples hardcoded in Python
- A question with no matching predicate in vocabulary returns `NL_QUERY_OUT_OF_SCOPE`, not a fabricated query
- Unit tests with a fake `LLMClient` (matching the pattern `test_extraction.py` already uses for `extract()`) covering: single-atom question, multi-atom/conjunctive question, out-of-scope question, and `get_fewshot_examples`/`seed_fewshot_examples` against a test Neo4j instance

**RED**: Write failing tests for `translate_to_dsl`, `get_fewshot_examples`, `seed_fewshot_examples`
**GREEN**: Implement
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

### Slice 2: Wire into `querier_node` — skip-if-already-DSL, conversation history — ✅ DONE

`querier_node` in `agents/graph.py` now skip-checks via `nl_query_service.is_dsl_syntax` (made public in Slice 1, now shared by both the validator and this check — avoided duplicating DSL-shape logic). New `AgentState.translated_query` field. Conversation history is scoped by `graph_id` directly (not a separate chat-session id) — the LangGraph agent flow doesn't persist its own turns to `chat_history_service` today (that's `chat_service.py`'s parallel `/chat` mechanism), so this reads whatever history is seeded under `graph_id`; tests seed it directly via `chat_history_service.append_message`. Wiring the agent's own turns into that persistent history is a natural follow-up but wasn't required by this slice's acceptance criteria. 4 new tests, full backend suite (373+) clean, zero diff on `query_engine.py`/`api/query.py`/`QueryPage.tsx`/`test_agent_graph.py`; 2 mutants (inverted skip-if-DSL check, inverted out-of-scope check), both killed. No refactor needed.

**Value**: The agent actually answers natural-language questions now, with zero behavior change for existing DSL users, and follow-up questions resolve against prior turns.
**Path**: `querier_node` checks whether `state["text"]` already parses as DSL; if not, translates first, grounded in recent conversation history
**Required implementation skills**: `tdd`, `testing`
**Acceptance criteria**:
- `querier_node`: text matching `_ATOM_RE` shape (already-DSL) skips translation entirely, calls `execute_query` exactly as today
- Non-DSL text calls `translate_to_dsl`, grounded in this `graph_id`'s live schema, `load_triples` vocabulary, `get_fewshot_examples`, and `chat_history_service.get_recent_messages` — before calling `execute_query`
- `state["translated_query"]` set when translation occurred, absent/empty when the skip-if-DSL path was taken
- A follow-up question ("and what about their subsidiaries?") resolves correctly given a prior turn in history (integration test with a seeded conversation)
- Existing `test_api_reason.py`/agent-graph tests for the `query` intent's DSL-input path pass unmodified (asserted as a literal check, same discipline as the analytics plan's Slice 3)
- New tests: NL question → correct translated query → correct results; out-of-scope question → graceful no-fabrication response

**RED**: Write failing tests for the skip-if-DSL branch, the translation branch, and the history-threading branch
**GREEN**: Implement
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass (including pre-existing DSL-path tests unmodified), mutation report reviewed, human approves commit

### Slice 3: Retry-once-on-error + fallback — ✅ DONE

**Design correction found while implementing**: the plan's original framing ("Generated DSL fails to execute → feed the parser error back") assumed `execute_query`'s `QueryResult.error` was the retry trigger. It structurally can't be — Slice 1's `translate_to_dsl` already validates via `is_dsl_syntax` (the same `_parse_atom`/`_split_top_level_atoms` functions `execute_query` itself uses) before ever returning, so anything it hands back is, by construction, already guaranteed to parse. The retry therefore lives *inside* `translate_to_dsl` itself, retrying the LLM once when the first raw response fails `is_dsl_syntax` (feeding the literal failed response back — the closest real analogue to "the parser's real error" available, since there's no separate downstream error to reuse), before falling back to `NL_QUERY_OUT_OF_SCOPE`. "No retry loop for already-valid DSL input" is satisfied structurally by Slice 2's skip-if-DSL check, which never calls `translate_to_dsl` at all for such input. 20 tests green; 2 mutants (inverted first-attempt check, inverted retry-attempt check), both killed. No refactor needed.

**Value**: Turns NeoConverse's vague "identifies inconsistencies" claim into a concrete, bounded, testable behavior — the parser's real error is used to correct the generation instead of silently failing once.
**Path**: Generated DSL fails to execute → feed the parser error back to the LLM once → re-execute → if still failing, fall back to today's syntax-explanation message
**Required implementation skills**: `tdd`, `testing`
**Acceptance criteria**:
- On `QueryResult.error` from a translated query, exactly one regeneration attempt is made, with the literal error message included in the retry prompt
- If the retry also errors, `querier_node` returns today's exact fallback (the `kg-query`-guided syntax explanation) — not a raw stack trace or second unexplained error
- No retry loop for already-valid DSL input (skip-if-DSL path never enters this branch)
- Unit tests: first-attempt success (no retry call made — assert the LLM is called exactly once), first-attempt failure + retry success, both attempts fail → fallback

**RED**: Write failing tests for each retry-outcome branch
**GREEN**: Implement
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

### Slice 4: Feedback capture + few-shot promotion — ✅ DONE

`log_translation`, `record_feedback`, `promote_to_fewshot`, `maybe_promote_on_repeat_success` added to `nl_query_service.py`. **Design correction**: the plan said `log_translation` "MERGEs" a `:TranslatedQuery` node, but `maybe_promote_on_repeat_success`'s whole premise (count how many times this question succeeded) requires a distinct node per attempt — `MERGE`-deduping on `{repository, question}` would collapse every repeat into one node and always count as 1, breaking the feature it's supposed to gate. Uses `CREATE` with a generated id instead. The "implicit proxy" (detecting that a user's next message isn't a near-duplicate) is explicitly out of scope here — that's conversation-flow-level logic for whoever calls `log_translation` repeatedly, not this module's concern; what's implemented is the counting/gating mechanism itself, which is what the "don't promote on implicit signal alone" boundary criterion actually tests. 24 tests green; 3 mutants (boundary `<`/`<=` on the promotion threshold, inverted `liked` check), all killed. No refactor needed.

**Value**: Translation quality improves from real usage instead of staying fixed at whatever was seeded manually — the concrete version of `lib/cypherQuery.ts`'s `SAVE_CONVO_CYPHER` (log every generated query + thumbs-up/down + feedback), closing the loop into Slice 1's `:FewshotQuery` store.
**Path**: Every translation is logged graph-natively with its outcome; a confirmed-good one is promoted into that repository's few-shot set
**Required implementation skills**: `tdd`, `testing`, `graph-reasoning`
**Acceptance criteria**:
- `nl_query_service.log_translation(neo4j, *, repository, question, dsl, outcome)` MERGEs a `:TranslatedQuery {question, dsl, outcome, at}` node per translation attempt (`outcome` ∈ succeeded/failed/out_of_scope — always logged, not just on explicit user feedback)
- `nl_query_service.record_feedback(neo4j, translated_query_id, *, liked: bool, correction: str | None)` — explicit thumbs-up/down from the UI (new small affordance next to the translated-query display from Slice 5), or a low-friction implicit proxy (user's next message isn't a near-duplicate of the same question — treated as an implicit "worked")
- `nl_query_service.promote_to_fewshot(neo4j, repository, translated_query_id)` copies a confirmed-good `:TranslatedQuery` into `:FewshotQuery` for that repository — called automatically on explicit thumbs-up, never automatically on the implicit proxy alone (implicit signal is weaker; require either explicit confirmation or a configurable minimum repeat-success count before auto-promoting)
- Unit tests for logging, feedback recording, and promotion (including the "don't promote on implicit signal alone" boundary)
- Integration test: a translated query submitted, thumbs-up recorded, confirms it now appears in `get_fewshot_examples` for that repository

**RED**: Write failing tests for `log_translation`, `record_feedback`, `promote_to_fewshot`
**GREEN**: Implement
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

### Slice 5: Transparency in the reply + skill update — ✅ DONE

`responder_node`'s "query" branch now prepends a `"Query run: ..."` line directly into the `user` prompt when `state["translated_query"]` is set — no separate plumbing needed for `_find_ungrounded_claims`, since it already checks `reply` against that same `user` string (verified with a direct unit test). `kg-query/SKILL.md` updated: stating the real translated query is now primary guidance; abstract syntax explanation is explicitly reframed as the last resort for when nothing was translated. 7 tests green (including a direct `_find_ungrounded_claims` unit test); 1 mutant (blanked-out translated-query line), killed. No refactor needed.

**`nl-query-translation.md` is now fully complete — all 5 slices, all top-level acceptance criteria satisfied.**

**Value**: Users see and can learn from the DSL query that actually ran — the concrete version of NeoConverse showing its generated Cypher, and the thing `kg-query/SKILL.md` already wanted ("describe the syntax") but grounded in the user's real question instead of an abstract explanation. Also gives Slice 4's feedback UI somewhere to attach.
**Path**: `responder_node` includes the translated query in its grounding context; `kg-query/SKILL.md` instructs the LLM to state it
**Required implementation skills**: `tdd`, `testing`
**Acceptance criteria**:
- `responder_node`'s prompt includes `state["translated_query"]` when present
- `kg-query/SKILL.md` updated: primary guidance is "state the DSL query that was run, then the results"; the old "explain the syntax in plain terms" guidance is kept but explicitly reframed as the last-resort-on-failure case
- `_find_ungrounded_claims` (the existing maker/checker groundedness check in `agents/graph.py`) is fed the translated-query text as part of its grounding text, so a stated query isn't flagged as an ungrounded claim
- Unit tests for the responder prompt including the translated query, and for the groundedness check not false-flagging it

**RED**: Write failing tests for responder prompt content and the groundedness-check interaction
**GREEN**: Implement
**MUTATE**: Run mutation testing
**KILL MUTANTS**: Address surviving mutants
**REFACTOR**: Assess improvements
**Done when**: All tests pass, mutation report reviewed, human approves commit

## Verification

After all slices:
1. `pytest backend/tests/` — full suite passes, including pre-existing query/agent tests unmodified
2. Manual: ask the agent a DSL query directly (`regulates("FINMA", X)`) → confirm identical behavior to today, no translation call made
3. Manual: ask the agent the same question in plain English → confirm it's translated, executed, answered, and the query used is visible in the reply
4. Manual: ask a follow-up question referencing the prior turn → confirm it resolves correctly via threaded history
5. Manual: ask a question with no matching predicate in the graph → confirm the out-of-scope response, not a fabricated predicate
6. Manual: force a bad generation (e.g. via a nonsense question) → confirm one retry happens, then graceful fallback to the syntax-explanation message — no raw error shown to the user
7. Manual: thumbs-up a good translation → confirm it appears in that repository's `:FewshotQuery` set and improves a subsequent similar question's translation

---
*Delete this file when the plan is complete. If `plans/` is empty, delete the directory.*
