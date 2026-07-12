# Neurosymbolic Knowledge Graph Reasoning Application — Complete Plan

> **Last Updated**: July 11, 2026
> **Status**: [UPDATED] MVP walking-skeleton (see `MVP_PLAN.md`) is built and runnable end-to-end — **all 10 of its phases are now done**, including Phase 6 (LangGraph wrap, live-verified). This document's own §16 phase list is the broader, aspirational v1+ build order and uses a **separate, non-matching phase numbering** — see §1.1 before citing a phase number from either document.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
   - [1.1 Implementation Status](#11-implementation-status)
2. [How Agents Use Skills](#2-how-agents-use-skills)
3. [Agentic Memory Systems](#3-agentic-memory-systems)
4. [Neo4j Context Graphs + Memory](#4-neo4j-context-graphs--memory)
5. [System Architecture](#5-system-architecture)
6. [Frontend Architecture](#6-frontend-architecture)
7. [Backend Architecture](#7-backend-architecture)
8. [Agent Layer](#8-agent-layer)
9. [Memory Layer](#9-memory-layer)
10. [MCP Layer](#10-mcp-layer)
11. [Tool Layer](#11-tool-layer)
12. [LLM Integration](#12-llm-integration)
13. [Project-Specific Skills](#13-project-specific-skills)
14. [Skill Testing Infrastructure](#14-skill-testing-infrastructure)
15. [Infrastructure & Deployment](#15-infrastructure--deployment)
16. [Implementation Phases](#16-implementation-phases)
17. [Reference Papers](#17-reference-papers)

---

## 1. Executive Summary

Build a shippable neurosymbolic knowledge graph reasoning application for business analysts. Combines LLM-powered extraction, Polanyi enrichment heuristics, neurosymbolic reasoning over FIBO financial ontology, LangGraph agent orchestration, multi-layer Neo4j memory, and MCP server integration — while also serving as a skill-creation workspace for domain-specific agent skills.

**Target audience**: Business analysts exploring financial relationships

**Core reference paper**: "Neurosymbolic graph enrichment for Grounded World Models" (Polanyi) — 11 enrichment heuristics for implicit knowledge

**Secondary reference paper**: Italian Legislation KG ETL pipeline — Neo4j property graph, LLM-assisted graph completion

### 1.1 Implementation Status

**[NEW]** Two documents track progress and they use *different, non-corresponding* phase numbers for different things — this has caused real confusion (an external review of this doc conflated the two). Read this before citing "Phase N" from either:

- **`MVP_PLAN.md` §9** — Phases 0–8, the actual as-built walking skeleton (what's really running today). **[UPDATED] All 10 items now done**, including Phase 6 (LangGraph wrap). This is the authoritative "what works right now" tracker.
- **This document's §16** — Phases 0–11, the aspirational full v1+ architecture (Redis/Postgres/MCP/multi-agent/5-memory-system). Written before execution started; most of it was deliberately deferred per `MVP_PLAN.md` §3 in favor of the lean walking skeleton. The matrix below is this document's status against *that* list — its "Phase 6" (LLM Integration) is not the same as `MVP_PLAN.md`'s "Phase 6" (LangGraph wrap).

| §16 Phase | Status | Evidence |
|---|---|---|
| 0. Scaffolding + Skills | **DONE** (scope reduced) | Backend/frontend trees, `.claude/skills/` (6 skills, not the original 4 sketched), `CLAUDE.md`. No Docker Compose — desktop apps instead (`MVP_PLAN.md` §8). |
| 1. Backend Skeleton | **PARTIAL, materially further** | FastAPI + `/health` + Neo4j driver: done. No Redis, no PostgreSQL. **[UPDATED]** A real LangGraph skeleton now exists (`backend/agents/graph.py`, `langgraph` wired in) — but it's the MVP's minimal linear `extractor→reasoner→responder`, not the full aspirational multi-node skeleton this row originally meant. |
| 2. Agent Layer | **DONE, all 7 nodes real** | **[UPDATED]** All 7 of the originally-sketched nodes are now real (`router`, `extractor`, `enricher`, `querier`, `reasoner`, `memory_agent`, `responder` — `backend/agents/graph.py`), each calling real, already-tested services, branching on a real LLM-classified intent (extract/enrich/query/reason/recall/visualize). **[UPDATED]** `memory_agent` is a dedicated node for the new "recall" intent: deterministic (non-LLM) keyword extraction from the user's question, then real cross-source search via `services/memory_service.py` (chat history + entity summaries), merged/deduped by id. No LangGraph `Store` wrapper. Live-verified end-to-end against the real server for all 6 intents, including a real router misclassification found and fixed via live verification (plain declarative text was misrouted to "enrich" instead of "extract" until few-shot examples were added). |
| 3. Memory Layer | **DONE (as natively-rebuilt alternative, not as originally speced)** | No Redis/Postgres/vector-index memory as originally speced. §20's native replacement: **all 5 items DONE** — provenance linking, bi-temporal facts, evolving summaries, chat session memory, and community detection (via real Neo4j GDS), see §20.4. |
| 4. MCP Layer | **DONE, all 4 servers real** | **[UPDATED]** All 4 originally-sketched servers now exist, same FastMCP pattern (official `mcp` SDK, stdio transport), each wrapping real, already-tested services -- no separate logic paths from the REST/agent layers. `backend/mcp_server.py`: custom KG MCP (`extract_entities`, `run_reasoning`, `run_enrichment`, `query_graph`, `ontology://schema` resource). **[UPDATED]** `backend/mcp_neo4j_server.py`: hand-rolled against the project's own `Neo4jClient` (not an official Neo4j MCP package, per this project's "rebuild natively" convention) -- `get_schema`, `read_cypher` (rejects write clauses via regex), `write_cypher`. **[UPDATED]** `backend/mcp_memory_server.py`: `search_memory` (wraps `services/memory_service.py`) and `save_preference` (wraps the new `services/preferences_store.py`, a general-purpose global key/value store). **[UPDATED]** `backend/mcp_skills_server.py`: `list_skills`, `load_skill`, `activate_skill` -- `activate_skill` has a real, persisted effect via the new `services/skill_activation_store.py` (`:ActiveSkill` Neo4j nodes), not a no-op. Tests: `test_mcp_server.py`, `test_mcp_neo4j_server.py`, `test_mcp_memory_server.py`, `test_mcp_skills_server.py` (all real Neo4j/GraphDB/LLM, no mocks). Verified live: each server's tools called directly via `mcp.call_tool(...)` against the real running Neo4j, plus the original JSON-RPC stdio handshake for `mcp_server.py`. |
| 5. Tool Layer | **DONE, standalone** | **[UPDATED]** `backend/agents/tools.py`: 4 formal `@tool`-decorated LangChain tools (`extract_entities`, `run_reasoning`, `run_enrichment`, `query_graph`), each wrapping the same real service functions the graph nodes and REST endpoints use, each with a real description an LLM could pick from. **Deliberately not wired into `agents/graph.py`'s nodes** — the graph's routing is deterministic (router classifies intent, fixed edges follow), not autonomous LLM tool-selection, and rewiring already-tested/live-verified nodes for architectural purity alone wasn't worth the regression risk. Available as a standalone surface for a future ReAct-style agent or MCP exposure. Tests: `test_agent_tools.py`, live-verified against the real running services. |
| 6. LLM Integration | **DONE, differently** | Single OpenAI-compatible `LLMClient` (§12.1), not the original GPT-4o/Claude-3.5 split — config-driven, not vendor-hardcoded. Better than as-planned, not a gap. |
| 7. Extraction + Enrichment | **DONE** | Extraction: DONE (`MVP_PLAN.md` Phase 2). Polanyi enrichment: all 11 heuristics DONE and live-verified running together, see §19.6 steps 1–5 (frontend now also done). |
| 8. Reasoning Engine | **DONE** | `reasoning/engine.py` matches §8.4 exactly, including the fixpoint/ontology-subclass-matching fix in `MVP_PLAN.md` §12. Now also reachable via the agent's reasoner node, sharing the same `services/reasoning_service.py`. **[UPDATED]** Engine now also emits a full `InferenceTraceEntry` per (rule, edge) evaluation — fired or skipped, with a human-readable skip reason (type mismatch / below threshold / already derived) — not just the facts that fired. `:DerivedFact` nodes persist their full proof-path JSON and a `fedBack` flag, enabling the loop's 3 steps to be driven independently across separate HTTP calls, not just atomically. New endpoints: `POST /reason/{graph_id}/spread`, `/infer`, `/feedback`, `GET /reason/{graph_id}/facts`, `POST /reason/{graph_id}/clear-activation`, `/clear-facts` — real, Neo4j-persisted, alongside the pre-existing atomic `POST /reason/{graph_id}`. Tests: `test_reasoning.py`, `test_graph_service.py`, `test_reasoning_service_manual_steps.py`, `test_api_reason_manual_steps.py` (240 backend tests passing). |
| 9. Frontend Overhaul | **PARTIAL** | Zustand + `api.ts`: done (`UI_PLAN.md` §8). No WebSocket. **[UPDATED]** `SkillManager` and `MemoryInspector` right-sidebar tabs now exist, both real/functional not demo: `SkillManager.tsx` lists the 6 real runtime skills with live active/inactive status (new `GET /skills` REST endpoint wrapping `agents/skill_store.py` + `services/skill_activation_store.py`), expands to show real `SKILL.md` content (`GET /skills/{name}/content`), and activates a skill for real (`POST /skills/{name}/activate`, persists a real `:ActiveSkill` Neo4j node -- the same effect as the Skills MCP server's tool). `MemoryInspector.tsx` searches real chat history + entity summaries (new `POST /memory/{graph_id}/search` wrapping `services/memory_service.py`) and manages real preferences (new `GET/PUT/DELETE /memory/preferences` wrapping `services/preferences_store.py`). Tests: `test_api_skills.py`, `test_api_memory.py` (real Neo4j, no mocks). Live-verified in the browser: activated `kg-extraction` and saw its status flip to Active, searched real chat history for "Credit Suisse" and got real matches, saved and deleted a real preference -- all test state cleaned up afterward. **[UPDATED]** `/agent` endpoint now has a UI — new "Agent" right-sidebar tab (`AgentPanel.tsx`), chat-style with intent badges (extract/enrich/query/reason/visualize), live-verified in the browser for visualize and query intents against the real running app + real graph. **[UPDATED]** Reason tab (`ReasoningPanel.tsx`) rebuilt for full parity with the prototype (`.claude/docs/src`): real 3-step manual loop (Spread Activation / Run Inference / Feed Back) each backed by the new endpoints above, inference trace display (fired/skipped + reasons), fedBack status + proof-path badges on derived facts, Clear Activation/Clear Facts controls, and a real Auto-Run Loop (async staged sequence through the same 3 real actions, self-stopping on convergence) — not a `setInterval`/mock loop. The pre-existing atomic "Run to Convergence" shortcut is kept alongside, not replaced. Live-verified end-to-end in the browser against the real running app: selected a real node, spread real activation, created a temporary custom rule to force a real fact to fire (seed rules' types didn't match this document's extracted vocabulary), ran inference (real trace + derived fact), fed back (activation boost persisted), cleared both facts and activation, and ran Auto-Run Loop to real convergence — all test data and the temporary rule cleaned up afterward. |
| 10. Skills + Eval Infra | **DONE** | Dev-time skills: 6 exist (exceeds the 5 originally sketched). **[UPDATED] All 6 runtime skills now real** (`kg-extraction` loaded by the extractor; `polanyi-enrichment`, `kg-query`, `neurosymbolic-reasoning`, `kg-visualization` loaded by the responder based on intent; `memory-recall` loaded by the new `memory_agent` node) — `backend/skills/*/SKILL.md` + `backend/agents/skill_store.py`'s Discovery→Activation→Execution, live-verified for all 6 router intents. **[UPDATED]** `evals/` directory now exists, adapted to Python rather than the originally-sketched `.js` harness (matches this project's actual stack, same adaptation pattern as the rest of §10-13): `evals/cases/<skill>/case-*.json` (§14.3 format, 2 cases per skill except `kg-visualization`'s 1, since it has no backend service of its own -- confirmed no visualization/export/layout service exists anywhere in `backend/`, per `backend/skills/kg-visualization/SKILL.md`'s own instruction that the agent must describe a visualization in text rather than render one; that case grades the same real `graph_service.get_graph` read a description would be based on). `evals/lib.py` dispatches each case to the real service function for its skill (real Neo4j/GraphDB/LLM, no mocks or fixture graphs), seeding and tearing down its own `graph_id` per case. `evals/run_evals.py` (full-suite CLI, writes timestamped JSON to `evals/results/`) and `evals/validate.py` (single-case CLI for the §14.2 RED/GREEN skill-authoring loop, non-zero exit on failure) replace the sketched `run-evals.js`/`validate-skills.js`. Live-verified: all 11 cases across all 6 skills pass against the real running backend; a deliberately-wrong assertion confirmed the RED/FAIL path (non-zero exit, per-assertion failure detail) works too. |
| 11. Polish + Deploy | **PARTIAL** | Error/loading states + provenance display: done (`MVP_PLAN.md` Phase 7). No Docker Compose full stack, no formal a11y/i18n pass. |

**Reading this table**: "DONE" phases needed no more design work, just verification they still hold. "NOT STARTED" phases (2, 4, 5) are gated behind the LangGraph wrap — building any of them before `MVP_PLAN.md` Phase 6 exists produces inert code with nothing to load it (see §13's dev-time-vs-runtime skill note for a concrete example of this trap).

---

## 2. How Agents Use Skills

### 2.1 The Critical Distinction: Development-Time vs Runtime Skills

Skills are **runtime artifacts** — structured Markdown files (SKILL.md with YAML frontmatter) loaded into an AI agent's context window on demand via **progressive disclosure**. They are a form of controlled, discoverable, composable domain knowledge.

There are two fundamentally different use cases, and this project uses **Option C: both**.

### 2.2 Progressive Disclosure (3 Tiers)

```
Tier 1 — Discovery (~100 tokens/session):
  Agent reads ONLY name + description YAML frontmatter from every SKILL.md
  50 skills × 100 tokens = ~5000 tokens total at startup (negligible)

Tier 2 — Activation (500-5000 tokens):
  When task matches skill description, agent reads full SKILL.md body
  Only 1-2 skills loaded per task = ~2000-5000 tokens (targeted)

Tier 3 — Resources (as needed):
  SKILL.md references scripts, templates, reference docs
  Agent loads selectively as task requires
```

### 2.3 Development-Time Skills (for Coding Agent: Claude Code / OpenCode)

These tell the coding agent how to build features in this project. They follow the Agent Skills open standard (agentskills.io).

**How they work:**
1. Session starts → Claude Code scans `~/.claude/skills/` and `.claude/skills/`
2. For each SKILL.md, extracts name + description (~100 tokens)
3. Agent receives user task → reads catalog → matches applicable skill
4. If match: agent reads full SKILL.md via Read tool → follows instructions
5. Instructions include TDD workflow, code patterns, project conventions

**Installation:**
```bash
# Personal skills (all projects)
~/.claude/skills/<skill-name>/SKILL.md

# Project skills (shared via git)
.claude/skills/<skill-name>/SKILL.md
```

**Example flow:**
```
User: "implement the extraction pipeline"
Agent reads kg-extraction SKILL.md which tells it to:
  1. Read the knowledge graph schema
  2. Write a failing test for extraction
  3. Implement the extractor
  4. Validate against known good examples
  5. Run mutation testing
```

### 2.4 Runtime Skills (for LangGraph Agents — End-User Facing)

These are domain knowledge loaded into the LangGraph agent's context at runtime. Same SKILL.md format, different loading mechanism.

**How they work at runtime:**
1. LangGraph agent has a `load_skill` tool
2. When user query involves extraction, agent calls `load_skill("kg-extraction")`
3. Gets domain instructions as tool response
4. Uses instructions to guide extraction reasoning

**Implementation pattern (from pessini/langgraph-skills-agent):**
```python
# SkillStore scans SKILL.md files at startup
store = SkillStore(skills_dir="./skills")
store.scan()  # Only parses YAML frontmatter (fast)

@tool
def load_skill(skill_name: str) -> str:
    parsed = store.load(skill_name)
    return json.dumps({
        "instructions": parsed.content,
        "available_files": store.list_supporting_files(skill_name),
    })
```

**Directory structure:**
```
runtime/skills/
  kg-extraction/
    SKILL.md          # "You are a knowledge graph extraction agent..."
    references/
      entity-types.md
      relationship-taxonomy.md
  polanyi-enrichment/
    SKILL.md          # "You are a Polanyi enrichment agent..."
    references/
      tacit-knowledge-patterns.md
```

### 2.5 Why Both Layers?

| Aspect | Development-Time Skills | Runtime Skills |
|--------|------------------------|----------------|
| **Consumer** | Claude Code / OpenCode (coding agent) | LangGraph agent (end-user facing) |
| **Purpose** | "How to build the extraction feature" | "How to do extraction on user data" |
| **Loaded by** | Agent Skills standard (filesystem scan) | Skill store (tool calls) |
| **Content** | TDD workflow, code patterns, conventions | Domain expertise, extraction rules, logic |
| **Updates** | Edit SKILL.md, no redeployment | Edit SKILL.md, no redeployment |
| **Observable** | In Claude Code traces | In Langfuse / tracing |

### 2.6 The Connection

Development-time skills reference runtime skills. When building the extraction pipeline, the development skill tells the coding agent: "The runtime skill for extraction should contain [X]. Read `runtime/skills/kg-extraction/SKILL.md` to understand what the agent needs to know at runtime."

This creates a **feedback loop**: runtime behavior informs development patterns, and development patterns encode the best runtime knowledge.

### 2.7 Skills vs Tools vs Agents

```
Agent (decides WHAT to do and WHEN)
  |
  | selects
  v
Skill (knows HOW to do it — process, judgment, domain expertise)
  |
  | invokes via
  v
Tool (executes one atomic action — API call, file read, database query)
```

| Dimension | Tool | Skill | Agent |
|-----------|------|-------|-------|
| **What it is** | Executable function with defined I/O | Structured knowledge package (Markdown + optional code) | Autonomous reasoning entity |
| **Analogy** | A wrench | A repair manual | A contractor |
| **Operates on** | Outside the model (external execution) | Inside the model's reasoning | The full loop (perceive, reason, act) |
| **State** | Stateless per call | Stateless per activation | Maintains memory across turns |
| **Autonomy** | Passive — waits to be called | Passive — waits to be loaded | Active — decides what to do |

### 2.8 Community Skills to Install

**Hybrid approach**: Keep 14 existing core skills + install from 4 repos.

**Core 4 repos:**
1. `obra/superpowers` — TDD methodology, process skills (brainstorming, executing-plans, systematic-debugging)
2. `addyosmani/agent-skills` — 24 production engineering skills (spec-driven-development, code-review, security, performance)
3. `mattpocock/skills` — Engineering discipline (16 skills)
4. `neo4j-contrib/neo4j-skills` — 24 Neo4j-specific skills (get-schema, read-cypher, write-cypher)

---

### 2.9 How Skills Are Actually Used at Runtime (Deep Dive)

This is the critical section: the exact mechanism by which SKILL.md files influence agent behavior at runtime.

#### 2.9.1 The Universal Pattern

Every skill-using agent follows the same three-phase cycle:

```
DISCOVERY          ACTIVATION           EXECUTION
(metadata in       (full content on     (LLM follows
 context, cheap)    demand, expensive)   instructions)
      │                   │                   │
      ▼                   ▼                   ▼
  ┌─────────┐       ┌──────────┐        ┌──────────┐
  │ Skill   │       │ load_    │        │ Agent    │
  │ Catalog │──────▶│ skill()  │───────▶│ follows  │
  │ in      │       │ tool     │        │ skill    │
  │ system  │       │ returns  │        │ instruc- │
  │ prompt  │       │ full     │        │ tions to │
  │         │       │ SKILL.md │        │ guide    │
  │ ~5000   │       │ body     │        │ tool     │
  │ tokens  │       │          │        │ calls    │
  └─────────┘       └──────────┘        └──────────┘
```

#### 2.9.2 SkillStore: The Discovery Engine

At startup, a `SkillStore` scans the skills directory and builds a metadata cache:

```python
class SkillStore:
    def __init__(self, skills_dir: str | Path) -> None:
        self._metadata_cache: dict[str, SkillMetadata] = {}  # Tier 1
        self._content_cache: dict[str, ParsedSkill] = {}     # Tier 2

    def scan(self) -> None:
        """Walk skills_dir, parse ONLY YAML frontmatter from each SKILL.md."""
        for skill_path in Path(self._skills_dir).rglob("SKILL.md"):
            metadata = parse_metadata_only(skill_path)  # name, description, tags
            self._metadata_cache[metadata.name] = metadata

    def load(self, skill_name: str) -> ParsedSkill:
        """Lazy-load full SKILL.md body on demand."""
        if skill_name not in self._content_cache:
            path = self._metadata_cache[skill_name].path
            self._content_cache[skill_name] = parse_full_skill(path)
        return self._content_cache[skill_name]

    def get_skill_catalog(self) -> str:
        """Render XML catalog from metadata cache for system prompt injection."""
        return "\n".join(
            f"<skill><name>{m.name}</name><description>{m.description}</description></skill>"
            for m in self._metadata_cache.values()
        )
```

**Key insight**: `scan()` is fast because it only parses YAML frontmatter (~100 tokens per skill). The full markdown body is loaded lazily only when `load()` is called.

#### 2.9.3 Tool Registration: How `load_skill` Gets Wired In

The `load_skill` tool is registered as a LangGraph tool via a factory function:

```python
def create_skill_tools(store: SkillStore) -> list[BaseTool]:
    @tool
    def load_skill(skill_name: str) -> str:
        """Load expert knowledge for a skill. Returns instructions and available files."""
        parsed = store.load(skill_name)
        return json.dumps({
            "skill_name": skill_name,
            "description": parsed.metadata.description,
            "instructions": parsed.content,          # THE FULL MARKDOWN BODY
            "available_files": store.list_supporting_files(skill_name),
        })

    @tool
    def read_skill_file(skill_name: str, filename: str) -> str:
        """Read a supporting file from a skill's references/ directory."""
        return store.read_file(skill_name, filename)

    # Overwrite docstring to include available skill names
    available = ", ".join(store._metadata_cache.keys())
    load_skill.__doc__ = (
        f"Load expert knowledge for a skill.\n\n"
        f"Available skills: {available}\n\n"
        f"Args:\n    skill_name: Exact name of the skill to load."
    )

    return [load_skill, read_skill_file]
```

**Critical detail**: The tool's docstring is dynamically rewritten to include the list of available skill names. This is how the LLM knows which skill names are valid arguments — it sees them in the tool description.

#### 2.9.4 System Prompt Injection: The Skill Catalog

The system prompt includes a lightweight skill catalog generated from metadata:

```python
SYSTEM_PROMPT = """You are a helpful AI assistant with access to domain-specific skills.

## How to Use Skills (Progressive Disclosure)
1. **Browse**: Review the skill summaries below
2. **Match**: When a task aligns with a skill's description, load that skill first
3. **Load**: Call `load_skill(skill_name)` to get detailed instructions
4. **Inspect**: Check `available_files` in the response for supporting documentation
5. **Reference**: Use `read_skill_file` for specific docs as needed
6. **Execute**: Apply the skill's guidance to complete the user's task

## Available Skills
{skill_catalog}

## Important Rules
- ALWAYS load a relevant skill before executing a task that matches a skill description
- Follow the skill's instructions step-by-step
- Do not skip steps or rationalize shortcuts
"""
```

The `skill_catalog` is rendered from the metadata cache — XML tags with name, description, tags, and supporting files. This costs ~5000 tokens for 50 skills.

#### 2.9.5 The Exact LangGraph Flow (ReAct Loop)

Here is the complete message flow through a LangGraph agent using skills:

```
Step 1: User sends message
  └─> messages = [HumanMessage("Extract entities from: Acme Corp issued stock")]

Step 2: agent_node runs
  └─> LLM sees system prompt with skill catalog + all messages
  └─> LLM decides: "This is an extraction task, I should load the kg-extraction skill"
  └─> LLM returns AIMessage with tool_calls=[load_skill("kg-extraction")]

Step 3: tool_node runs load_skill
  └─> SkillStore.load("kg-extraction") returns full SKILL.md content
  └─> ToolMessage returned with JSON containing:
      {
        "instructions": "You are a knowledge graph extraction agent...\n\n"
                        "## Entity Types\n- BusinessEntity: Companies, funds...\n"
                        "## Extraction Rules\n1. Always extract legal name...\n",
        "available_files": ["entity-types.md", "relationship-taxonomy.md"]
      }

Step 4: agent_node runs again
  └─> LLM now sees the skill instructions in its context window
  └─> LLM follows the instructions: "According to the skill, I need to extract
      BusinessEntity nodes. Acme Corp is a BusinessEntity..."
  └─> LLM returns AIMessage with tool_calls=[extract_entities(text="Acme Corp issued stock")]

Step 5: tool_node runs extract_entities
  └─> Extraction pipeline runs with skill-informed parameters
  └─> ToolMessage returned with extracted entities and relationships

Step 6: agent_node runs again
  └─> LLM has skill instructions + extraction results in context
  └─> LLM formats response following skill's output format guidelines
  └─> LLM returns final response to user
```

**The skill content flows through the standard tool-call → tool-result → next LLM call cycle.** It is never injected as a separate system message modification at load time. It persists in conversation history as a ToolMessage, so the agent can reference it in subsequent turns.

#### 2.9.6 How Skill Content Shapes Agent Behavior

Skill content influences the agent through **multiple channels**:

| Mechanism | When | Example |
|-----------|------|---------|
| **System prompt injection** | Every turn | Skill catalog (name+description) in system message |
| **Tool result** | On-demand | Full SKILL.md body returned from `load_skill` |
| **Message history** | Subsequent turns | Skill content persists as ToolMessage in conversation |
| **Prompt engineering** | In skill text | Anti-rationalization tables, mandatory checklists |
| **State injection** | Deep Agents only | `skills_metadata` in LangGraph state |

The skill content is **behavioral guidance** — it tells the LLM what to do, what NOT to do, what tools to call, what parameters to use, and what format to return results in.

#### 2.9.7 Concrete Example: kg-extraction Skill at Runtime

**User input**: "Extract entities from this financial text: 'Goldman Sachs issued 50,000 shares of Series B preferred stock to Sequoia Capital in exchange for $10M Series B investment.'"

**Without skill**: Agent might extract entities but miss financial-specific types, use wrong relationship types, or not handle the investment-to-security relationship.

**With skill loaded**:

```
1. LLM calls load_skill("kg-extraction")
2. Gets instructions including:
   - "Entity Types: BusinessEntity (companies, funds), Security (stocks, bonds),
      FinancialAmount (monetary values), InvestmentRound (Series A/B/C)"
   - "Relationship Rules: ISSUED for stock issuance, RECEIVED_INVESTMENT for
      funding, EXCHANGED_FOR for transaction relationships"
   - "Always extract the full legal name, not abbreviations"
   - "Map investment rounds to their security types"
3. LLM calls extract_entities with skill-informed parameters:
   - Entities: Goldman Sachs (BusinessEntity), Sequoia Capital (BusinessEntity),
     Series B preferred stock (Security), $10M (FinancialAmount),
     Series B (InvestmentRound)
   - Relationships: Goldman Sachs --[ISSUED]--> Series B preferred stock,
     Goldman Sachs --[RECEIVED_INVESTMENT]--> Sequoia Capital,
     Series B preferred stock --[EXCHANGED_FOR]--> $10M
4. LLM formats response following skill's output format guidelines
```

#### 2.9.8 Anti-Rationalization: Why Agents Don't Skip Skills

The key challenge: LLMs tend to rationalize skipping steps. Skills solve this with explicit anti-rationalization gates:

```markdown
## Common Rationalizations (YOU MUST NOT USE THESE)

| Rationalization | Refusal |
|----------------|---------|
| "This is just a simple extraction" | All extractions require the skill |
| "I already know how to extract" | The skill has project-specific rules |
| "Loading the skill will waste tokens" | Skill loading is mandatory |
| "The user is in a hurry" | Speed without accuracy is waste |
```

From obra/superpowers:
> "If you think there is even a 1% chance a skill might apply to what you are doing,
> you ABSOLUTELY MUST invoke the skill."

This is enforced by:
1. **Mandatory bootstrap** — session start injects "You have skills. Use them."
2. **Tool availability** — `load_skill` is always available as a tool
3. **Anti-rationalization** — skill content explicitly blocks shortcuts
4. **Observability** — every skill load is a traceable event (Langfuse/LangSmith)

#### 2.9.9 Three Architecture Variants

| Project | Discovery | Loading | Activation |
|---------|-----------|---------|------------|
| **pessini/langgraph-skills-agent** | `scan()` parses YAML → `_metadata_cache` | `load_skill` tool returns JSON with full instructions | LLM sees tool result in message history, follows instructions |
| **obra/superpowers** | Bootstrap hook injects `using-superpowers` into first message | Platform-native `Skill` tool returns SKILL.md text | Mandatory skill invocation protocol + anti-rationalization |
| **Deep Agents (LangChain)** | `SkillsMiddleware.before_agent` → `state["skills_metadata"]` | `read_file` tool on skill path | System prompt tells agent to read skill, follow instructions |

All three converge on the same pattern: **metadata in context (cheap) → full content on demand (expensive) → LLM follows instructions as behavioral guidance**.

#### 2.9.10 Skill Lifecycle in Our Project

```
┌─────────────────────────────────────────────────────────────────┐
│                    SKILL LIFECYCLE                               │
│                                                                 │
│  1. CREATION                                                    │
│     Developer writes SKILL.md + references/                     │
│     Tests in evals/cases/ → validate-skills.js → run-evals.js  │
│                                                                 │
│  2. INSTALLATION                                                 │
│     Development skills → .claude/skills/ (for coding agent)     │
│     Runtime skills → backend/skills/ (for LangGraph agent)      │
│                                                                 │
│  3. DISCOVERY                                                    │
│     SkillStore.scan() at backend startup                         │
│     → _metadata_cache populated (name + description)            │
│     → catalog rendered in system prompt                          │
│                                                                 │
│  4. ACTIVATION                                                   │
│     User sends message → Router classifies intent                │
│     → Agent sees matching skill in catalog                       │
│     → Agent calls load_skill("skill-name")                       │
│     → ToolNode executes, returns full SKILL.md content           │
│                                                                 │
│  5. EXECUTION                                                    │
│     LLM has skill instructions in context                        │
│     → Follows step-by-step workflow                              │
│     → Calls domain tools with skill-informed parameters          │
│     → Returns results in skill-specified format                  │
│                                                                 │
│  6. OBSERVABILITY                                                │
│     Every skill load → traceable ToolMessage                     │
│     Langfuse tracks: which skills loaded, when, how often       │
│     Metrics: skill usage frequency, accuracy per skill          │
│                                                                 │
│  7. EVOLUTION                                                    │
│     Monitor which skills improve accuracy                        │
│     A/B test skill variants                                      │
│     Update SKILL.md → no redeployment needed                    │
│     Add new skills → discovered on next scan()                   │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.9.11 Skills in Our LangGraph Agent Graph

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │ Router  │──── classify intent ────┐
                    └────┬────┘                         │
                         │                              │
         ┌───────────────┼───────────────┐              │
         │               │               │              │
    ┌────▼────┐    ┌─────▼─────┐   ┌─────▼─────┐       │
    │Extract  │    │  Enrich   │   │  Reason   │       │
    │         │    │           │   │           │       │
    │ load_   │    │ load_     │   │ load_     │       │
    │ skill() │    │ skill()   │   │ skill()   │       │
    │ →kg-    │    │ →polanyi- │   │ →neuro-   │       │
    │ extract │    │ enrichment│   │ symbolic  │       │
    │ ion     │    │           │   │ -reasoning│       │
    └────┬────┘    └─────┬─────┘   └─────┬─────┘       │
         │               │               │              │
         │          interrupt             │              │
         │          (user approves)       │              │
         │               │               │              │
         └───────────────┼───────────────┘              │
                         │                              │
                    ┌────▼────┐                    ┌────▼────┐
                    │Querier  │                    │Responder│
                    │         │                    │         │
                    │ load_   │                    │ load_   │
                    │ skill() │                    │ skill() │
                    │ →kg-    │                    │ →kg-    │
                    │ query   │                    │ visuali-│
                    │         │                    │ zation  │
                    └────┬────┘                    └────┬────┘
                         │                              │
                    ┌────▼──────────────────────────────▼────┐
                    │              Memory Agent               │
                    └────────────────────┬───────────────────┘
                                         │
                                    ┌────▼────┐
                                    │   END   │
                                    └─────────┘
```

Each agent node:
1. Receives the user message + skill catalog in its system prompt
2. Calls `load_skill()` to get domain-specific instructions
3. Follows the skill's step-by-step workflow
4. Calls domain tools (extract_entities, run_polanyi_heuristics, etc.) with skill-informed parameters
5. Returns results following the skill's output format

#### 2.9.12 What Happens If a Skill Is Missing or Wrong?

| Scenario | Behavior |
|----------|----------|
| **No skill loaded** | Agent uses general knowledge, may miss project-specific rules |
| **Wrong skill loaded** | Agent follows irrelevant instructions, may produce incorrect output |
| **Skill too vague** | Agent skips steps or invents its own workflow |
| **Skill too rigid** | Agent follows instructions literally even when they don't apply |
| **Skill outdated** | Agent uses stale rules, contradicts current codebase |

**Mitigations:**
- Router node ensures correct skill is loaded for each intent
- Skill descriptions are precise ("Use when extracting entities from financial text")
- Skills include "When NOT to use this skill" sections
- Eval tests verify skill accuracy against known-good outputs
- A/B testing compares skill-loaded vs skill-free performance

#### 2.9.13 Token Budget Analysis

| Component | Tokens | When |
|-----------|--------|------|
| Skill catalog in system prompt | ~5,000 | Every turn |
| load_skill() tool call + result | ~3,000 | On activation |
| read_skill_file() for references | ~1,000 | On demand |
| **Total per skill activation** | **~9,000** | **One-time** |
| **Total for 2 skills per conversation** | **~18,000** | **Spread across turns** |

Compared to:
- Typical LLM context window: 128,000 tokens
- System prompt without skills: ~2,000 tokens
- 10 conversation turns: ~20,000 tokens

**Skills add ~45% overhead to token usage** but provide structured domain knowledge that would otherwise require much larger prompts or multiple API calls.

#### 2.9.14 Neo4j Skill Metadata: Graph-Based Skill Discovery

**Problem**: Filesystem-based skill discovery is flat — the LLM sees a list of skills and must pattern-match against descriptions. For >10 skills, or when skills have complex relationships, this breaks down.

**Solution**: Store skill metadata in Neo4j as first-class graph entities. The LLM queries Neo4j to discover relevant skills, not just pattern-matches against a flat list.

##### Why Neo4j for Skills?

| Capability | Filesystem Only | Neo4j Metadata |
|------------|----------------|----------------|
| Basic discovery | ✅ Fast (in-memory) | ✅ Slightly slower (~18ms) |
| Relationship queries | ❌ Flat list | ✅ "Find skills that require extraction" |
| Domain connections | ❌ Manual matching | ✅ "Find skills that work with Security type" |
| Usage learning | ❌ No history | ✅ Track success/failure per skill |
| Multi-agent sharing | ❌ Per-process cache | ✅ Shared graph state |
| Dynamic routing | ❌ Static catalog | ✅ Context-aware selection |

##### Neo4j Skill Schema

```cypher
// Skill nodes
(:Skill {
  name: "kg-extraction",
  description: "Extract entities and relationships from financial text",
  version: "1.0.0",
  confidence: 0.92,          // updated based on usage
  token_cost: 3000,          // avg tokens when loaded
  tier: "runtime",           // "development" | "runtime" | "both"
  created_at: datetime(),
  updated_at: datetime()
})

// Skill-to-skill relationships
(:Skill)-[:REQUIRES {
  reason: "must extract before enriching",
  strength: 1.0             // hard prerequisite
}]->(:Skill)

(:Skill)-[:COMPLEMENTS {
  reason: "enrichment improves extraction quality",
  strength: 0.7             // soft complement
}]->(:Skill)

(:Skill)-[:CONFLICTS {
  reason: "cannot run extraction and reasoning simultaneously",
  strength: 1.0
}]->(:Skill)

// Skill-to-domain relationships
(:Skill)-[:WORKS_WITH {
  relevance: 0.95,
  entity_types: ["BusinessEntity", "Security"]
}]->(:EntityType)

(:Skill)-[:USED_IN {
  domain: "financial",
  subdomain: "equity-markets"
}]->(:Domain)

// Usage tracking (append-only)
(:SkillUsage {
  id: "usage-uuid",
  skill_name: "kg-extraction",
  session_id: "abc-123",
  user_id: "user-42",
  loaded_at: datetime(),
  completed_at: datetime(),
  success: true,
  accuracy: 0.87,
  tokens_used: 3200,
  tool_calls_made: 3,
  error: null
})

// Usage relationships
(:SkillUsage)-[:USED_IN_SESSION]->(:Session)
(:SkillUsage)-[:PRODUCED]->(:ExtractionResult)
(:SkillUsage)-[:LED_TO_SUCCESS {metric: "accuracy", value: 0.87}]->(:Outcome)
```

##### Skill Discovery Tool (Neo4j Query)

```python
@tool
def find_relevant_skills(
    task_description: str,
    domain: str = None,
    entity_types: list[str] = None,
    limit: int = 5
) -> str:
    """Query Neo4j to find skills relevant to a task.

    Uses graph traversal to find skills based on:
    - Description matching (full-text search)
    - Domain relevance (USED_IN relationships)
    - Entity type compatibility (WORKS_WITH relationships)
    - Historical success rate (confidence scores)
    """
    query = """
    // Full-text search on skill descriptions
    CALL db.index.fulltext.queryNodes('skill_description_index', $task_description)
    YIELD node as s, score as text_score

    // Boost by domain relevance
    OPTIONAL MATCH (s)-[d:USED_IN]->(dom:Domain)
    WHERE $domain IS NULL OR dom.name = $domain
    WITH s, text_score,
         CASE WHEN d IS NOT NULL THEN 0.2 ELSE 0.0 END as domain_boost

    // Boost by entity type compatibility
    OPTIONAL MATCH (s)-[w:WORKS_WITH]->(et:EntityType)
    WHERE $entity_types IS NULL OR et.name IN $entity_types
    WITH s, text_score, domain_boost,
         CASE WHEN w IS NOT NULL THEN 0.1 * w.relevance ELSE 0.0 END as entity_boost

    // Get prerequisites
    OPTIONAL MATCH (s)-[:REQUIRES]->(req:Skill)

    // Calculate final score
    WITH s,
         text_score + domain_boost + entity_boost as total_score,
         collect(DISTINCT req.name) as requires

    // Filter by minimum confidence
    WHERE s.confidence > 0.5

    RETURN s.name as name,
           s.description as description,
           s.confidence as confidence,
           s.token_cost as token_cost,
           total_score,
           requires
    ORDER BY total_score DESC
    LIMIT $limit
    """

    results = neo4j_driver.execute(
        query,
        task_description=task_description,
        domain=domain,
        entity_types=entity_types,
        limit=limit
    )

    return json.dumps([{
        "name": r["name"],
        "description": r["description"],
        "confidence": r["confidence"],
        "token_cost": r["token_cost"],
        "score": r["total_score"],
        "requires": r["requires"]
    } for r in results])
```

##### Usage Tracking Tool

```python
@tool
def record_skill_usage(
    skill_name: str,
    session_id: str,
    success: bool,
    accuracy: float = None,
    tokens_used: int = None,
    error: str = None
) -> str:
    """Record skill usage in Neo4j for learning and improvement."""
    query = """
    MERGE (s:Skill {name: $skill_name})
    CREATE (u:SkillUsage {
      id: randomUUID(),
      skill_name: $skill_name,
      session_id: $session_id,
      loaded_at: datetime(),
      success: $success,
      accuracy: $accuracy,
      tokens_used: $tokens_used,
      error: $error
    })
    CREATE (u)-[:USED_SKILL]->(s)

    // Update skill confidence (rolling average)
    WITH s
    OPTIONAL MATCH (u2:SkillUsage)-[:USED_SKILL]->(s)
    WHERE u2.success IS NOT NULL
    WITH s, avg(CASE WHEN u2.success THEN 1.0 ELSE 0.0 END) as new_confidence
    SET s.confidence = new_confidence,
        s.updated_at = datetime()

    RETURN s.confidence as updated_confidence
    """

    result = neo4j_driver.execute(
        query,
        skill_name=skill_name,
        session_id=session_id,
        success=success,
        accuracy=accuracy,
        tokens_used=tokens_used,
        error=error
    )

    return json.dumps({
        "status": "recorded",
        "new_confidence": result[0]["updated_confidence"]
    })
```

##### Updated LangGraph Flow with Neo4j Discovery

```
User: "Extract entities from this financial text"

Step 1: Router node
  ├─> Calls find_relevant_skills("extract entities", domain="financial")
  ├─> Neo4j returns: [
  │     {name: "kg-extraction", confidence: 0.92, score: 0.87, requires: []},
  │     {name: "polanyi-enrichment", confidence: 0.88, score: 0.65, requires: ["kg-extraction"]}
  │   ]
  ├─> Router selects: kg-extraction (highest score, no prerequisites)
  └─> Stores discovery context in state

Step 2: Extractor node
  ├─> Calls load_skill("kg-extraction")  (filesystem, fast)
  ├─> Gets full SKILL.md instructions
  ├─> Follows instructions to extract entities
  └─> Calls record_skill_usage("kg-extraction", success=True, accuracy=0.89)

Step 3: Post-extraction (if enrichment needed)
  ├─> Router checks: polanyi-enrichment requires kg-extraction ✅
  ├─> Loads polanyi-enrichment skill
  └─> Enriches extracted entities

Step 4: Background
  ├─> Neo4j updates kg-extraction confidence: 0.92 → 0.923
  └─> Usage history grows for future learning
```

##### Full-Text Index for Skill Search

```cypher
// Create full-text index on skill descriptions
CREATE FULLTEXT INDEX skill_description_index
FOR (s:Skill)
ON EACH [s.description, s.name];

// Query example: find skills related to "financial entity extraction"
CALL db.index.fulltext.queryNodes('skill_description_index', 'financial entity extraction')
YIELD node, score
RETURN node.name, node.description, score
ORDER BY score DESC;
```

##### Skill Relationship Queries

```cypher
// Find all skills that kg-extraction depends on
MATCH (s:Skill {name: "kg-extraction"})-[:REQUIRES]->(dep:Skill)
RETURN dep.name, dep.confidence;

// Find skills that work with BusinessEntity type
MATCH (s:Skill)-[:WORKS_WITH]->(et:EntityType {name: "BusinessEntity"})
RETURN s.name, s.confidence
ORDER BY s.confidence DESC;

// Find the skill chain for a complex task
MATCH path = (start:Skill)-[:REQUIRES*]->(end:Skill)
WHERE NOT (end)-[:REQUIRES]->()
RETURN [n IN nodes(path) | n.name] as skill_chain;

// Find most successful skills in financial domain
MATCH (s:Skill)-[:USED_IN]->(d:Domain {name: "financial"})
OPTIONAL MATCH (u:SkillUsage)-[:USED_SKILL]->(s)
WITH s, count(u) as usage_count,
     avg(CASE WHEN u.success THEN 1.0 ELSE 0.0 END) as success_rate
RETURN s.name, usage_count, success_rate, s.confidence
ORDER BY success_rate DESC, usage_count DESC;
```

##### Hybrid Discovery: Filesystem + Neo4j

```python
class HybridSkillDiscovery:
    """Combines fast filesystem cache with rich Neo4j queries."""

    def __init__(self, store: SkillStore, neo4j_driver):
        self.store = store
        self.neo4j = neo4j_driver

    def get_catalog(self) -> str:
        """Fast path: in-memory catalog for system prompt (always works)."""
        return self.store.get_skill_catalog()

    def find_skills(self, task: str, domain: str = None) -> list[dict]:
        """Rich path: Neo4j graph query for context-aware selection."""
        return find_relevant_skills(task, domain)

    def load_skill(self, name: str) -> str:
        """Load full SKILL.md content (filesystem, fast)."""
        return self.store.load(name)

    def record_usage(self, name: str, success: bool, **kwargs):
        """Track usage in Neo4j for learning."""
        record_skill_usage(name, success=success, **kwargs)
```

##### System Prompt with Hybrid Discovery

```python
SYSTEM_PROMPT = """You are a helpful AI assistant with access to domain-specific skills.

## How to Use Skills
1. **Quick Match**: Check the skill catalog below for obvious matches
2. **Deep Search**: If no obvious match, call `find_relevant_skills(task_description)`
   to query the skill graph for context-aware recommendations
3. **Load**: Call `load_skill(skill_name)` to get detailed instructions
4. **Execute**: Follow the skill's step-by-step workflow
5. **Record**: After completing the task, the system records usage automatically

## Quick Catalog (from filesystem)
{skill_catalog}

## For Complex Tasks
When the quick catalog doesn't have an obvious match, use `find_relevant_skills()`
which queries the skill knowledge graph for:
- Skills related to your specific domain
- Skills compatible with the entity types you're working with
- Skills with high historical success rates
- Skill prerequisites (what to load first)
"""
```

##### When Neo4j Is Unavailable (Fallback)

```python
class ResilientSkillDiscovery:
    """Falls back to filesystem-only if Neo4j is down."""

    def find_skills(self, task: str, domain: str = None) -> list[dict]:
        try:
            return self._neo4j_find(task, domain)
        except Neo4jError:
            # Fallback: pattern-match against filesystem catalog
            return self._filesystem_fallback(task)

    def _filesystem_fallback(self, task: str) -> list[dict]:
        """Simple keyword matching against cached metadata."""
        catalog = self.store._metadata_cache
        matches = []
        for name, meta in catalog.items():
            score = self._keyword_match(task, meta.description)
            if score > 0.3:
                matches.append({
                    "name": name,
                    "description": meta.description,
                    "confidence": 1.0,  # unknown, assume good
                    "score": score,
                    "requires": []
                })
        return sorted(matches, key=lambda x: x["score"], reverse=True)[:5]
```

##### Why This Approach Is Correct

1. **Resilient**: Filesystem works even if Neo4j is down
2. **Queryable**: Neo4j enables graph-based skill discovery (not just keyword matching)
3. **Learnable**: Usage tracking improves skill selection over time
4. **Shareable**: Multiple agents share skill knowledge through the same graph
5. **Observable**: Every skill load and usage is a traceable graph event
6. **Evolvable**: Add new skills by inserting nodes + edges, no code changes

##### Token Budget with Neo4j Discovery

| Component | Tokens | When |
|-----------|--------|------|
| Skill catalog in system prompt | ~5,000 | Every turn |
| find_relevant_skills() call + result | ~1,500 | On complex routing |
| load_skill() tool call + result | ~3,000 | On activation |
| read_skill_file() for references | ~1,000 | On demand |
| **Total per skill activation** | **~10,500** | **One-time** |
| **Total for 2 skills + discovery** | **~23,500** | **Spread across turns** |

The ~1,500 token overhead for Neo4j discovery is offset by:
- Better skill selection accuracy
- Avoiding loading wrong skills (saves 3,000-5,000 tokens)
- Usage learning that improves future selection

---

## 3. Agentic Memory Systems

### 3.1 Memory Taxonomy (CoALA Framework)

| Memory Type | Scope | Duration | Storage Backend | Retrieval Method |
|---|---|---|---|---|
| **Working Memory** | Single conversation | Current session | LLM context window (prompt) | Direct inclusion |
| **Episodic Memory** | User/agent history | Days to months | Vector DB + metadata or structured logs | Semantic search + recency |
| **Semantic Memory** | Facts, knowledge | Persistent | Vector DB / Graph DB / Document store | Semantic search + structured queries |
| **Procedural Memory** | How to do things | Persistent | Code / workflows / prompts / tool definitions | Routed by task type |

Some researchers add:
- **Reflective Memory** (Meta-cognition): Summarized insights triggered by patterns
- **Organizational Context Memory**: Governed definitions, data lineage, access policies

### 3.2 Framework Memory Patterns

**Letta (formerly MemGPT)** — "LLM-as-OS" paradigm:
```
Core Memory    = RAM (small block always in context, agent reads/writes each turn)
Recall Memory  = Disk cache (searchable conversation history, agent queries via tools)
Archival Memory = Cold storage (long-term vector-indexed, agent queries via tools)
```
When context overflows → agent receives "running out of context" signal → decides what to evict, summarize, or archive.

**CrewAI** — Unified Memory class:
```python
from crewai import Memory
memory = Memory()
memory.remember("We decided to use PostgreSQL for the user database.")
matches = memory.recall("What database did we choose?", limit=5)
```
LLM infers scope, categories, importance when saving. Retrieval uses composite scoring (semantic similarity + recency + importance).

**Mem0** — Dual-store model (vector DB + knowledge graph):
- Automatic fact extraction from conversations
- Two-phase pipeline (Extraction + Update)
- $24M Series A, AWS exclusive memory provider for Agent SDK
- 26% accuracy boost, 91% lower p95 latency, 90% token savings

### 3.3 LangGraph Memory Architecture

#### Layer 1: Short-Term Memory (Thread-Scoped Checkpointing)

Checkpointers save graph state after every node execution, organized into **threads**. Each `thread_id` represents one conversation/session.

**Checkpoint savers:**
| Saver | Package | Use Case |
|---|---|---|
| `InMemorySaver` | `langgraph-checkpoint` | Debugging/testing only |
| `PostgresSaver` | `langgraph-checkpoint-postgres` | Production workloads |
| `Neo4jSaver` | `langchain-neo4j` | Graph-native production |

```python
from langgraph.checkpoint.postgres import PostgresSaver
with PostgresSaver.from_conn_string("postgresql://user:pass@localhost/db") as checkpointer:
    checkpointer.setup()
    graph = builder.compile(checkpointer=checkpointer)
```

#### Layer 2: Long-Term Memory (BaseStore API — Cross-Thread)

The `BaseStore` interface provides **cross-thread, namespace-scoped persistent memory**.

**Core API:**
```python
# Hierarchical namespace-based storage
store.put(("memories", "user-42"), "preferences", {"theme": "dark"})
item = store.get(("memories", "user-42"), "preferences")

# Semantic vector search
results = store.search(
    ("memories", "user-42"),
    query="What UI theme does the user prefer?",
    limit=5
)
```

**Implementations:**
- `InMemoryStore` — development/testing
- `PostgresStore` — production (recommended)
- `EngramStore` — hybrid BM25 + vector + KG retrieval

**LangMem SDK (Higher-Level):**
```python
from langmem import create_manage_memory_tool, create_search_memory_tool
manage_memory = create_manage_memory_tool(namespace=("memories", "{langgraph_user_id}"))
search_memory = create_search_memory_tool(namespace=("memories", "{langgraph_user_id}"))
```

#### Checkpointing vs Store-Based Memory

| Aspect | Checkpointer (Short-Term) | BaseStore (Long-Term) |
|---|---|---|
| Scope | Thread-scoped (one conversation) | Cross-thread (any conversation) |
| Persistence | Every step auto-saved | Manual `store.put()` calls |
| Data | Full graph state snapshots | User-defined JSON documents |
| Time Travel | Yes (replay from any checkpoint) | No (key-value retrieval only) |

---

## 4. Neo4j Context Graphs + Memory

> **[HISTORICAL — DO NOT IMPLEMENT FROM THIS SECTION, SEE §20]** This section cites `neo4j-labs/agent-memory` and a "Neo4j Labs, June 2026" context-graph concept, one of the citations flagged elsewhere in this plan as unverifiable. §20 documents the actually-verified equivalent (Graphiti/Zep, real GitHub project + research paper) and is the one to build from. Kept here for history only.

### 4.1 What Are Context Graphs?

A **context graph** (Neo4j Labs, June 2026) extends a knowledge graph by adding three connected layers:

1. **Knowledge graph of short-term memory** (conversations, recent interactions)
2. **Knowledge graph of long-term memory** (entities, relationships, preferences)
3. **Knowledge graph of reasoning memory** (decision traces, tool usage, provenance)

All three layers exist in a **single connected graph** — giving agents "durable understanding of all knowledge, conversations, and decisions."

### 4.2 Context Graph vs Knowledge Graph

| Aspect | Knowledge Graph | Context Graph |
|---|---|---|
| Scope | Domain entities and relationships | Domain KG + conversation history + reasoning traces |
| Temporal | Mostly static snapshots | Temporal validity, versioning |
| Governance | May or may not have | Certified definitions, access policies, lineage |
| Agent use | Query for facts | Query for facts + recall past interactions + explain decisions |
| Update pattern | Batch/curated | Continuous, agent-driven writes |

### 4.3 Graph Memory vs Vector Memory

**Vector memory**: Stores every fact as a dense embedding, retrieves by cosine similarity. Good for fuzzy recall but cannot represent all task-relevant subsets of a growing memory store (proven lower bound by Google DeepMind 2025).

**Graph memory**: Stores facts as entities + typed relationships. Excels at multi-hop reasoning, entity resolution, temporal constraints, contradiction handling.

**The critical insight**: A single-vector retriever *cannot represent all task-relevant subsets* of a growing memory store, regardless of model size. Graph traversal is the architectural fix.

### 4.4 Neo4j Agent Memory Library (neo4j-labs/agent-memory)

Flagship open-source project (355+ stars, Apache-2.0, Python + TypeScript SDKs). Three memory tiers in a single knowledge graph:

| Memory Type | Schema | Query Pattern |
|---|---|---|
| **Short-Term** | Linear linked list of `:Message` nodes | "What did we just discuss?" |
| **Long-Term** | POLE+O entities with typed relationships | "What do I know about X?" |
| **Reasoning** | Trees: `Trace -> Steps -> ToolCalls` | "How did I solve similar problems?" |

**POLE+O Ontology**: Person, Organization, Location, Event + Other — the entity classification system for long-term memory.

**3-Stage Entity Extraction Pipeline:**
1. Fast statistical NER (GLiNER/spaCy) — handles 80-90% of entities, no API cost
2. Zero-shot models — handles ambiguous cases
3. LLM fallback — handles complex/financial entities

**SAME_AS Pattern**: Entity resolution/deduplication. When encountering "Bob" and later "Robert Smith," the system links them to the same entity node.

### 4.5 Combined Cypher Query Pattern

The graph advantage — combining vector similarity, graph traversal, and property filters in one query:

```cypher
// Semantic search + graph filter + property filter
CALL db.index.vector.queryNodes('message_embedding', 10, $embedding)
YIELD node as m, score
MATCH (m)-[:MENTIONS]->(e:Entity {type: "PERSON"})
WHERE m.created_at > datetime() - duration('P7D')
RETURN m.content, e.name, score
```

### 4.6 LangGraph + Neo4j Integration

**Three key packages:**

| Package | Purpose |
|---|---|
| `langchain-neo4j` (official) | `Neo4jGraph`, `Neo4jVector`, `Neo4jSaver` (checkpointer) |
| `langgraph-checkpoint-neo4j` (community) | Drop-in checkpointer with branching support |
| `neo4j-agent-memory` (Neo4j Labs) | High-level 3-tier memory API |

**Neo4jSaver graph-native data model:**
```
(:Thread)─[:HAS_CHECKPOINT]→(:Checkpoint)─[:PREVIOUS]→(:Checkpoint)
    │                           │
    └─[:HAS_BRANCH]→(:Branch)   ├─[:HAS_CHANNEL]→(:ChannelState)
                                └─[:HAS_WRITE]→(:PendingWrite)
```

**Performance (production):**
- Checkpoint persistence: +42ms to 5-step agent flow
- Graph context reads: 18ms p50
- LLM inference: 800ms (dominates)

### 4.7 GraphRAG Pattern

**Traditional RAG**: Embed chunks → vector similarity search → inject top-k chunks into prompt

**GraphRAG**: Embed chunks → vector search to find starting nodes → **multi-hop graph traversal** to find connected entities and relationships → inject richer context into prompt

**Official `neo4j-graphrag-python` package:**
```python
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.retrievers import HybridRetriever

retriever = HybridRetriever(
    driver,
    embedder=embedder,
    vector_index_name="vector",
    fulltext_index_name="keyword",
    return_properties=["text"],
)
rag = GraphRAG(retriever=retriever, llm=llm)
response = rag.search(query_text="Which researchers are studying immunotherapy?")
```

### 4.8 Memory Evolution: Merge, Update, Prune

**Entity Deduplication:**
- Exact name matching
- Fuzzy matching (Levenshtein)
- Semantic matching (>0.95 embedding similarity)
- `SAME_AS` relationships for ambiguous merges requiring human review

**Decay and Weighting:**
- Each fact/entity has `confidence` score and timestamps
- Access patterns reinforce relevance
- Background processes flag/remove nodes below thresholds

**Automated Compaction:**
- Alert on session node count exceeding 5,000
- Daily compaction removes orphaned nodes older than 30 days
- Enforce `max(entities)` per session in ingestion pipeline

### 4.9 Production Architecture (Markaicode, 2026)

```
User Request
    │
    v
LangGraph Orchestrator (StateGraph)
    │
    v
[Agent Node] ──queries──> Neo4j Read Replica (18ms p95)
    │                              ^
    v                              |
[Tool Node] ──writes──> Kafka (durable buffer)
                              │
                              v
                     Neo4j Consumer Group (batch writes, 22ms p95)
                              │
                              v
                     Neo4j Core (write leader)
```

**Key decisions:**
- Separate **read replicas** for agent retrieval from **write core** for mutations
- **Kafka as write-ahead log** to decouple agent writes from reads
- **Causal bookmarks** for eventual consistency between core and replicas

### 4.10 Reference Projects

| Project | Description | Stars |
|---|---|---|
| `neo4j-labs/agent-memory` | Core graph-native memory library | 355 |
| `neo4j-labs/create-context-graph` | CLI scaffolding for full-stack context graph apps | 670 |
| `neo4j/neo4j-genai-python` | Official GraphRAG package | - |
| `l4b4r4b4b4/langgraph-checkpoint-neo4j` | Community LangGraph checkpointer for Neo4j | - |
| `pessini/langgraph-skills-agent` | LangGraph runtime skills implementation | - |
| `lumetra-io/engram-langgraph` | Hybrid BM25 + vector + KG BaseStore replacement | - |

---

## 5. System Architecture

### 5.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React + TypeScript)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │GraphCanvas│ │Inspector │ │  LLM     │ │ Toolbar  │       │
│  │  (SVG)   │ │  Panel   │ │  Panel   │ │          │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                    Zustand State Management                   │
│                    Vite + Tailwind + shadcn/ui                │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + SSE + WebSocket
┌──────────────────────────┴──────────────────────────────────┐
│                    Backend (Python FastAPI)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              LangGraph Orchestrator                    │   │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐  │   │
│  │  │ Router  │→│Extractor │→│ Enricher │→│Reasoner │  │   │
│  │  └─────────┘ └──────────┘ └──────────┘ └─────────┘  │   │
│  │       ↓           ↓            ↓            ↓         │   │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐  │   │
│  │  │Querier  │ │Responder │ │  Memory  │ │  Tools  │  │   │
│  │  └─────────┘ └──────────┘ └──────────┘ └─────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────┐ ┌──────────────────┐                   │
│  │   Memory Layer   │ │    MCP Layer      │                   │
│  │ • Conversation   │ │ • Neo4j MCP       │                   │
│  │ • Working        │ │ • Custom KG MCP   │                   │
│  │ • Long-term      │ │ • Memory MCP      │                   │
│  │ • Episodic       │ │                   │                   │
│  │ • Semantic       │ │                   │                   │
│  └──────────────────┘ └──────────────────┘                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    Data Layer                                 │
│  ┌──────────────┐ ┌──────────┐ ┌──────────┐                │
│  │   Neo4j 5    │ │  Redis   │ │PostgreSQL│                │
│  │  (Graph DB)  │ │(Checkpoint│ │(Long-term│                │
│  │              │ │  Store)  │ │  Store)  │                │
│  └──────────────┘ └──────────┘ └──────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Directory Structure

```
neurosymbolic/
├── PLAN.md                          # This file
├── CLAUDE.md                        # Project-level agent instructions
├── AGENTS.md                        # Agent skill routing table
├── docker-compose.yml
├── .env.example
│
├── backend/
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app
│   │   ├── config.py                # Settings
│   │   └── dependencies.py          # DI
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py                 # AgentState TypedDict
│   │   ├── graph.py                 # LangGraph StateGraph
│   │   ├── memory.py                # LangGraph Store wrapper
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── router.py
│   │       ├── extractor.py
│   │       ├── enricher.py
│   │       ├── reasoner.py
│   │       ├── querier.py
│   │       ├── responder.py
│   │       └── memory_agent.py
│   │
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── conversation.py          # Checkpointing
│   │   ├── working.py               # Reasoning state
│   │   ├── long_term.py             # LangGraph Store
│   │   ├── episodic.py              # Reasoning traces
│   │   └── semantic.py              # Vector search
│   │
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── kg_server.py             # Custom KG MCP
│   │   ├── memory_server.py         # Memory MCP
│   │   └── skills_server.py         # Skills MCP
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── graph_tools.py           # Cypher queries
│   │   ├── extract_tools.py
│   │   ├── enrich_tools.py
│   │   ├── reasoning_tools.py
│   │   ├── memory_tools.py
│   │   └── export_tools.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── agent.py                 # /api/agent/* endpoints
│   │   ├── graph.py                 # /api/graph/* endpoints
│   │   ├── memory.py                # /api/memory/* endpoints
│   │   ├── export.py                # /api/export/* endpoints
│   │   └── skills.py                # /api/skills/* endpoints
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py                # LLM client wrapper
│   │   ├── extraction.py            # GPT-4o extraction
│   │   ├── enrichment.py            # Claude 3.5 enrichment
│   │   ├── nlp_query.py             # NL → Cypher
│   │   └── prompts.py               # Prompt templates
│   │
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── pipeline.py              # Extraction orchestrator
│   │   ├── entity_extractor.py
│   │   ├── relationship_extractor.py
│   │   └── offline_extractor.py     # Keyword-matching fallback
│   │
│   ├── enrichment/
│   │   ├── __init__.py
│   │   ├── polanyi.py               # 11 heuristics
│   │   ├── heuristics/
│   │   │   ├── presuppositions.py
│   │   │   ├── implicatures.py
│   │   │   ├── factual_impact.py
│   │   │   ├── image_schemas.py
│   │   │   ├── metonymy.py
│   │   │   ├── moral_values.py
│   │   │   ├── symbolic.py
│   │   │   ├── event_sequences.py
│   │   │   ├── causal.py
│   │   │   ├── future_events.py
│   │   │   └── non_events.py
│   │   └── scoring.py
│   │
│   ├── reasoning/
│   │   ├── __init__.py
│   │   ├── engine.py                # Spread activation (parameterized)
│   │   ├── proof_tracer.py
│   │   └── inference.py
│   │
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── fibo.py                  # FIBO ontology loader
│   │   ├── constraints.py           # Neo4j constraints/indexes
│   │   └── migration.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── graph_service.py         # Neo4j operations
│   │   ├── export_service.py        # JSON/NX/OWL export
│   │   └── session_service.py
│   │
│   ├── prompts/
│   │   ├── extraction.txt
│   │   ├── enrichment.txt
│   │   ├── nl2cypher.txt
│   │   ├── reasoning.txt
│   │   └── query_answering.txt
│   │
│   ├── skills/                      # RUNTIME skills (for LangGraph agents)
│   │   ├── kg-extraction/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   │       ├── entity-types.md
│   │   │       └── relationship-taxonomy.md
│   │   ├── polanyi-enrichment/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   │       └── tacit-knowledge-patterns.md
│   │   ├── kg-query/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   │       └── cypher-patterns.md
│   │   ├── neurosymbolic-reasoning/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   │       └── reasoning-patterns.md
│   │   └── kg-visualization/
│   │       ├── SKILL.md
│   │       └── references/
│   │           └── layout-algorithms.md
│   │
│   ├── evals/                       # Skill evaluation infrastructure
│   │   ├── cases/
│   │   ├── fixtures/
│   │   ├── results/
│   │   ├── validate-skills.js
│   │   └── run-evals.js
│   │
│   └── tests/
│       ├── test_extraction.py
│       ├── test_enrichment.py
│       ├── test_reasoning.py
│       ├── test_memory.py
│       └── test_agents.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css
│       ├── vite-env.d.ts
│       │
│       ├── stores/
│       │   ├── graphStore.ts
│       │   └── agentStore.ts
│       │
│       ├── components/
│       │   ├── GraphCanvas.tsx
│       │   ├── InspectorPanel.tsx
│       │   ├── LLMPanel.tsx
│       │   ├── Toolbar.tsx
│       │   ├── SkillManager.tsx      # NEW: skill browsing/activation
│       │   └── MemoryInspector.tsx   # NEW: memory visualization
│       │
│       ├── lib/
│       │   ├── types.ts
│       │   ├── engine.ts
│       │   ├── llm.ts               # Real LLM client
│       │   ├── fibo-data.ts
│       │   ├── api.ts               # NEW: backend API client
│       │   └── websocket.ts         # NEW: SSE/WS connection
│       │
│       └── hooks/
│           ├── useGraph.ts
│           └── useAgent.ts
│
└── .claude/
    └── skills/                      # DEVELOPMENT-TIME skills (for coding agent)
        ├── kg-extraction/
        │   └── SKILL.md
        ├── polanyi-enrichment/
        │   └── SKILL.md
        ├── graph-reasoning/
        │   └── SKILL.md
        └── neurosymbolic-patterns/
            └── SKILL.md
```

---

## 6. Frontend Architecture

### 6.1 Tech Stack

- React + TypeScript + Vite
- Tailwind CSS + shadcn/ui
- Zustand for state management
- SVG + d3-force for graph visualization

### 6.2 Components

| Component | Purpose |
|---|---|
| `GraphCanvas.tsx` | SVG canvas with drag, heatmap, proof path highlighting |
| `InspectorPanel.tsx` | ConstructionPanel, ReasoningPanel, QueryPanel, LlmPanel |
| `LLMPanel.tsx` | Standalone LLM chat panel with streaming |
| `Toolbar.tsx` | Header with stats badges |
| `SkillManager.tsx` | NEW: Browse and activate runtime skills |
| `MemoryInspector.tsx` | NEW: Visualize memory layers |

### 6.3 State Management

**graphStore (Zustand)**: nodes, edges, selectedNode, proofPath, heatmap mode, loading states

**agentStore (Zustand)**: conversation history, current agent state, skill activations, memory context

### 6.4 API Communication

- HTTP REST for CRUD operations
- SSE (Server-Sent Events) for agent streaming
- WebSocket for real-time graph updates

---

## 7. Backend Architecture

### 7.1 Tech Stack

- Python FastAPI
- LangGraph for agent orchestration
- Neo4j 5 driver
- Redis for checkpointing
- PostgreSQL for long-term memory
- OpenAI GPT-4o (extraction)
- Claude 3.5 Sonnet (enrichment)

### 7.2 API Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/agent/chat` | LangGraph streaming chat |
| `POST /api/agent/extract` | Extract entities/relationships |
| `POST /api/agent/enrich` | Polanyi enrichment |
| `POST /api/agent/reason` | Run reasoning over graph |
| `POST /api/agent/query` | NL → Cypher query |
| `GET /api/graphs` | List knowledge graphs |
| `GET /api/graph` | Get specific graph |
| `GET /api/memory` | Query memory layers |
| `POST /api/export` | Export graph (JSON/NX/OWL) |
| `GET /api/skills` | List available skills |
| `POST /api/skills/{name}/load` | Load runtime skill |

### 7.3 Human-in-the-Loop

LangGraph interrupts before:
- Enrichment (user approves/edits enrichment results)
- Export (user confirms export format and scope)

---

## 8. Agent Layer

### 8.1 AgentState TypedDict

```python
from typing import TypedDict, Annotated
from langgraph.graph import MessagesState

class AgentState(TypedDict):
    # Core
    messages: Annotated[list, "add_messages"]
    graph_id: str
    user_id: str

    # Extraction
    extracted_entities: list[dict]
    extracted_relationships: list[dict]

    # Enrichment
    enrichment_results: list[dict]
    enriched_facts: list[dict]

    # Reasoning
    activation_scores: dict[str, float]
    derived_facts: list[dict]
    proof_paths: list[list[str]]

    # Query
    current_query: str
    cypher_query: str
    query_results: list[dict]

    # Memory
    relevant_memories: list[dict]
    episodic_trace: list[dict]
```

### 8.2 LangGraph StateGraph

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │ Router  │──── classify intent ────┐
                    └────┬────┘                         │
                         │                              │
         ┌───────────────┼───────────────┐              │
         │               │               │              │
    ┌────▼────┐    ┌─────▼─────┐   ┌─────▼─────┐       │
    │Extract  │    │  Enrich   │   │  Reason   │       │
    │         │    │  (interrupt│   │           │       │
    └────┬────┘    └─────┬─────┘   └─────┬─────┘       │
         │               │               │              │
         └───────────────┼───────────────┘              │
                         │                              │
                    ┌────▼────┐                    ┌────▼────┐
                    │Querier  │                    │Responder│
                    └────┬────┘                    └────┬────┘
                         │                              │
                    ┌────▼──────────────────────────────▼────┐
                    │              Memory Agent               │
                    └────────────────────┬───────────────────┘
                                         │
                                    ┌────▼────┐
                                    │   END   │
                                    └─────────┘
```

### 8.3 Agent Nodes

| Node | Purpose |
|---|---|
| `router` | Classifies user intent (extract/enrich/reason/query/chat) |
| `extractor` | Runs extraction pipeline, updates graph |
| `enricher` | Applies Polanyi heuristics, human-in-the-loop |
| `reasoner` | Self-looping subgraph: spread activation → fire rules → feedback → repeat until fixpoint (§8.4). NOT a single pass. |
| `querier` | Converts NL to Cypher, executes query |
| `responder` | Formats response for user |
| `memory_agent` | Saves/loads from all memory layers |

### 8.4 Reasoning Semantics (correctness spec)

The prototype loop (`src/lib/engine.ts` + `src/App.tsx`) is neurosymbolic in name only: `spreadActivation` resets all activation to 0 each iteration, so `feedBackActivation` never influences rule firing, the loop always "converges" at iteration 2, and no multi-hop derivation occurs. The backend port MUST fix this, not reproduce it. Definitions:

- **Persistent activation**: activation accumulates across iterations. The feedback step's boost seeds the next spread; do NOT zero activation between rounds. This is what makes derived facts trigger further rules (genuine multi-hop reasoning).
- **Directed and consistent**: spreading follows directed out-edges (`source → target`), matching how rules read edges. The neural and symbolic layers must agree on edge direction (the prototype spreads undirected but reasons directed).
- **Well-defined spread**: relax to a max-activation fixpoint (repeat relaxation until stable), not a BFS-order-dependent single sweep. `newActivation = activation(source) · decay · edge.weight · target.salience`.
- **Reachable multi-hop**: choose decay/threshold so depth ≥ 2 nodes can cross rule thresholds (decay 0.45 alone yields ~1-hop-only reasoning).
- **Convergence**: iterate until (no new facts derived) AND (max activation delta < ε), capped at `MAX_ITERATIONS`. Report which condition stopped the loop; do not label a stop a "fixpoint" unless both hold.
- **One confidence calculus**: `fact.confidence = activation(premise) · rule.weight`; along a proof chain confidence is the bounded product of step confidences. This single notion propagates neural → symbolic → feedback → proof path and is the value surfaced to queries and the UI. (Extraction confidence is a separate, upstream notion — do not conflate.)
- **Rule language**: decide before implementing — single-premise pattern rules (as today) or Horn clauses with variables. `querier` already does conjunctive variable joins; the inference engine currently does not. Pick one target and state it.
- **LangGraph modeling**: the reasoner is a cyclic subgraph (`reasoner → conditional edge → reasoner` until the convergence predicate holds), not a DAG node. §8.2's diagram is illustrative; the compiled graph has this self-loop.

---

## 9. Memory Layer

### 9.1 Five Memory Systems

| System | Backend | Purpose |
|---|---|---|
| **Conversation** | LangGraph Checkpointer (Redis) | Thread-scoped message history, auto-saved per step |
| **Working** | AgentState (in-memory) | Current reasoning state, activation scores, derived facts |
| **Long-term** | LangGraph BaseStore (PostgreSQL) | Cross-session facts, preferences, user profile |
| **Episodic** | Neo4j nodes | Reasoning traces as graph nodes, linked to entities |
| **Semantic** | Neo4j vector index | Entity embeddings, OpenAI text-embedding-3-small |

### 9.2 Memory Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Context Graph (Neo4j)                 │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Short-Term  │  │  Long-Term   │  │  Reasoning    │  │
│  │ Memory      │←→│  Memory      │←→│  Memory       │  │
│  │ (Messages)  │  │ (Entities)   │  │ (Traces)      │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│         ↕                ↕                 ↕            │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Semantic (Vector Index)             │   │
│  │          Entity + Message Embeddings             │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           ↕
┌─────────────────────────────────────────────────────────┐
│              LangGraph Store (PostgreSQL)                │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  User       │  │  Session     │  │  Cross-Session │  │
│  │  Preferences│  │  State       │  │  Learnings    │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 9.3 Memory Retrieval Pattern

```python
# In a LangGraph node:
def load_memories(state, config, store):
    user_id = config["configurable"]["user_id"]
    query = state["messages"][-1].content

    # 1. Semantic search over Neo4j context graph
    neo4j_memories = neo4j_store.search(
        ("context", user_id),
        query=query,
        limit=5
    )

    # 2. Long-term facts from PostgreSQL
    pg_memories = store.search(
        ("memories", user_id),
        query=query,
        limit=5
    )

    # 3. Recent episodic traces
    episodic = neo4j_driver.execute(
        "MATCH (t:ReasoningTrace)-[:TRIGGERED_BY]->(m:Message) "
        "WHERE m.user_id = $user_id "
        "ORDER BY t.created_at DESC LIMIT 3",
        user_id=user_id
    )

    # 4. Combine into context
    memory_text = format_memories(neo4j_memories, pg_memories, episodic)
    return {"relevant_memories": memory_text}
```

---

## 10. MCP Layer

### 10.1 MCP Servers

| Server | Tools | Purpose |
|---|---|---|
| Neo4j Official MCP | `get-schema`, `read-cypher`, `write-cypher` | Direct graph access |
| Custom KG MCP | `extract_knowledge`, `enrich_graph`, `run_reasoning`, `query_nlp` | Domain-specific operations |
| Memory MCP | `search_memory`, `save_preference` | Memory layer access |
| Skills MCP | `load_skill`, `list_skills`, `activate_skill` | Runtime skill management |

### 10.2 MCP Integration Pattern

```python
# MCP server as FastAPI sub-app
from fastmcp import FastMCP

mcp = FastMCP("kg-server")

@mcp.tool()
async def extract_knowledge(text: str, graph_id: str) -> dict:
    """Extract entities and relationships from text."""
    pipeline = ExtractionPipeline(...)
    return await pipeline.extract(text, graph_id)

@app.mount("/mcp", mcp.sse_app())
```

---

## 11. Tool Layer

### 11.1 Tool Registry

All tools registered as LangGraph tools:

| Tool Category | Tools | Purpose |
|---|---|---|
| **Graph Tools** | `query_cypher`, `get_schema`, `get_neighbors`, `get_node_properties` | Direct graph access |
| **Extract Tools** | `extract_entities`, `extract_relationships`, `extract_from_text` | Knowledge extraction |
| **Enrich Tools** | `run_polanyi_heuristics`, `score_activation`, `derive_facts` | Polanyi enrichment |
| **Reasoning Tools** | `spread_activation`, `find_proof_path`, `run_inference` | Neurosymbolic reasoning |
| **Memory Tools** | `save_memory`, `search_memories`, `get_conversation_history` | Memory access |
| **Export Tools** | `export_json`, `export_networkx`, `export_owl` | Graph export |

---

## 12. LLM Integration

### 12.1 LLM Configuration

**[UPDATED — supersedes the vendor-specific table below]** No vendor is hardcoded. `llm/client.py` (`LLMClient`) talks to any OpenAI-compatible endpoint; model + base URL are config (`NVIDIA_MODEL`/`LLM_BASE_URL`). Confirmed working default: NVIDIA-hosted `meta/llama-3.1-8b-instruct` (see `MVP_PLAN.md` §11 for why — `z-ai/glm-5.2` hangs on real completions in this environment). Every call site — extraction, reasoning explanation, chat, and Polanyi enrichment (§19) — depends only on `LLMClient`, so swapping providers is a config change, not a code change. The GPT-4o/Claude-3.5-specific rows below are the original aspirational plan; kept for history, not current.

| Model | Provider | Use Case |
|---|---|---|
| GPT-4o | OpenAI | Entity/relationship extraction, NL → Cypher |
| Claude 3.5 Sonnet | Anthropic | Polanyi enrichment, reasoning explanation |
| text-embedding-3-small | OpenAI | Entity/message embeddings for semantic memory |
| Keyword-matching offline | Local fallback | No-API-cost testing and development |

### 12.2 Prompt Templates

| Prompt | Model | Purpose |
|---|---|---|
| `extraction.txt` | GPT-4o | Extract entities/relationships from text |
| `enrichment.txt` | Claude 3.5 | Apply Polanyi heuristics to graph |
| `nl2cypher.txt` | GPT-4o | Convert NL query to Cypher |
| `reasoning.txt` | Claude 3.5 | Explain reasoning chain |
| `query_answering.txt` | Claude 3.5 | Answer question from Cypher results |

---

## 13. Project-Specific Skills

> **[UPDATED — both layers now real]** Two layers, easy to conflate, kept deliberately separate:
> - **13.1 Dev-time** (`.claude/skills/`) — guides the *coding agent* (Claude Code)
>   while building this codebase. These exist today; the list below reflects the
>   actual current set, not the original sketch.
> - **13.2 Runtime** (`backend/skills/`) — guides the *product's own* LangGraph
>   agent while it serves a real user request, loaded via `backend/agents/
>   skill_store.py`'s `load()` per §2.9's Discovery→Activation→Execution
>   pattern. **1 of 6 sketched runtime skills is now real** (`kg-extraction`,
>   loaded by the extractor node in `backend/agents/graph.py`, MVP_PLAN.md
>   Phase 6) — the layer was unblocked once a real LangGraph agent existed to
>   load skills *into*. The other 5 (`polanyi-enrichment`, `kg-query`,
>   `neurosymbolic-reasoning`, `kg-visualization`, `memory-recall`) are still
>   just sketched below, not built — same mechanism, just not wired to a node
>   yet (no `enricher`/`querier` node exists).

### 13.1 Development-Time Skills (.claude/skills/)

Actual current set (six skills, superseding the four-skill sketch originally
drafted here — see each file for full content):

| Skill | Guides the coding agent on |
|---|---|
| `kg-extraction` | Ontology-driven extraction, no hardcoded domain types |
| `ontology-mapping` | GraphDB schema → Neo4j instance typing |
| `graph-reasoning` | Spread activation, proof tracing (older name) |
| `neurosymbolic-reasoning` | §8.4 persistent-activation fixpoint loop specifically |
| `polanyi-enrichment` | §19 — 11 heuristics, `:ImplicitFact`, domain-agnostic |
| `temporal-memory` | §20 — provenance linking, bi-temporal facts, chat sessions |

Original per-skill sketch below, kept for history (content superseded by the
actual files in `.claude/skills/`):

#### kg-extraction/SKILL.md
```
---
name: kg-extraction
description: Use when implementing knowledge graph extraction features.
  Follows TDD. Requires reading the knowledge graph schema first.
---
```
Tells the coding agent how to build extraction features with proper tests, schema validation, and offline fallback.

#### polanyi-enrichment/SKILL.md
```
---
name: polanyi-enrichment
description: Use when implementing Polanyi enrichment logic.
  Covers all 11 heuristics with scoring and confidence thresholds.
---
```
Tells the coding agent about the 11 enrichment heuristics and how to implement each one.

#### graph-reasoning/SKILL.md
```
---
name: graph-reasoning
description: Use when implementing reasoning over the knowledge graph.
  Covers spread activation, proof tracing, and inference.
---
```
Tells the coding agent how to implement parameterized spread activation and proof tracing.

#### neurosymbolic-patterns/SKILL.md
```
---
name: neurosymbolic-patterns
description: Use when working with the neurosymbolic reasoning architecture.
  Covers symbolic + neural integration patterns.
---
```
Tells the coding agent about the overall neurosymbolic architecture.

### 13.2 Runtime Skills (backend/skills/)

#### kg-extraction/SKILL.md — **[DONE, real]**
The sketch below was aspirational (FIBO-specific, contradicting this project's
domain-agnostic design). The actual shipped skill is domain-agnostic — see
`backend/skills/kg-extraction/SKILL.md` for the real content (precision-over-
recall guidance, honest confidence scoring, no fixed entity-type list since
that's already handled by the loaded ontology). Loaded for real by
`backend/agents/skill_store.py`'s `load()`, consumed by the extractor node
in `backend/agents/graph.py`, which threads it into `extraction/pipeline.py`'s
`extract(..., extra_guidance=...)`. Live-verified: the extractor node's actual
LLM call carries this skill's text in its system prompt.

Original sketch (kept for history, superseded by the above):
```
---
name: kg-extraction
description: Use when extracting entities and relationships from financial text.
  Activates on extraction requests.
---
```
Domain knowledge for extraction: FIBO entity types, relationship taxonomy, extraction rules.

#### polanyi-enrichment, kg-query, neurosymbolic-reasoning, kg-visualization, memory-recall — **[DONE, all real]**

The four sketches below (plus `memory-recall`, added this session, not
originally sketched here) are all now real — see `backend/skills/*/SKILL.md`
for actual content. Loaded by `backend/agents/graph.py`'s **responder** node
(not by dedicated `enricher`/`querier`/`reasoner` nodes, since the query
engine and reasoning engine are deterministic and LLM-free by design — the
skill has no LLM call to attach to in those nodes, so it attaches where the
LLM call that needs the guidance actually lives): `polanyi-enrichment` when
`intent == "enrich"`, `kg-query` when `intent == "query"`,
`neurosymbolic-reasoning` when `intent == "reason"`, `kg-visualization` when
`intent == "visualize"`. `memory-recall` loads *in addition* to whichever
primary skill is active, whenever the message contains a temporal keyword
("historical", "as of", "previously", ...), regardless of intent. Live-
verified for all 5 intents against the real running server.

Original sketches below, kept for history (content superseded by the actual files):

```
---
name: polanyi-enrichment
description: Use when enriching a knowledge graph with implicit knowledge.
  Activates on enrichment requests.
---
```
Domain knowledge for enrichment: 11 heuristics, scoring criteria, confidence thresholds.

```
---
name: kg-query
description: Use when answering natural language questions about the knowledge graph.
  Activates on query requests.
---
```
Domain knowledge for querying: Cypher patterns, common queries, result formatting.

```
---
name: neurosymbolic-reasoning
description: Use when running neurosymbolic reasoning over the knowledge graph.
  Activates on reasoning requests.
---
```
Domain knowledge for reasoning: Spread activation parameters, proof tracing, inference rules.

```
---
name: kg-visualization
description: Use when visualizing or exporting the knowledge graph.
  Activates on visualization requests.
---
```
Domain knowledge for visualization: Layout algorithms, color coding, export formats.

#### memory-recall/SKILL.md **[NEW — added with §20]**
```
---
name: memory-recall
description: Use when a user's question references prior conversation, "as of"
  a point in time, or how a fact has changed. Activates on temporal/historical
  requests, not current-state lookups.
---
```
Domain knowledge for temporal queries: how to query `validAt`/`invalidAt`
windows on `:RELATES` (point-in-time state, not just current), how to read
`:ChatSession`/`:ChatMessage` history for conversational continuity, how to
walk `IngestEvent-[:PRODUCED]->` for provenance ("which document said this").
Distinct from `kg-query`, which only knows current-state Cypher patterns —
without this skill the agent has no way to know invalidated facts exist at
all, since a naive `MATCH` on `:RELATES` returns current + historical edges
indistinguishably unless the query filters on validity window.

**Why a 6th skill and not folded into kg-query or memory-agent behavior**:
temporal reasoning is conditionally relevant (most questions are current-state
and shouldn't pay the context cost of temporal query patterns), which is
exactly the case skills exist for — narrow, activates on trigger, doesn't
bloat the default prompt. This entry didn't exist when §13.2 was first
drafted because §20 (the temporal memory layer) didn't exist yet.

---

## 14. Skill Testing Infrastructure

### 14.1 Structure

```
evals/
├── cases/
│   ├── kg-extraction/
│   │   ├── case-001-basic-extraction.json
│   │   ├── case-002-financial-entities.json
│   │   └── case-003-complex-relationships.json
│   ├── polanyi-enrichment/
│   │   ├── case-001-presuppositions.json
│   │   └── case-002-implicatures.json
│   ├── kg-query/
│   │   ├── case-001-simple-query.json
│   │   └── case-002-multi-hop-query.json
│   ├── neurosymbolic-reasoning/
│   │   ├── case-001-basic-spread.json
│   │   └── case-002-proof-path.json
│   └── kg-visualization/
│       └── case-001-basic-layout.json
├── fixtures/
│   ├── sample-texts.json
│   ├── expected-entities.json
│   └── expected-relationships.json
├── results/
│   └── (generated test results)
├── validate-skills.js
└── run-evals.js
```

### 14.2 TDD Workflow for Skills

```
RED:
  1. Write test case in evals/cases/<skill>/case-XXX.json
  2. Run validation → must FAIL (expected output != actual)

GREEN:
  1. Write minimal SKILL.md that passes the test
  2. Run validation → must PASS

REFACTOR:
  1. Close loopholes in test cases
  2. Strengthen test assertions
  3. Add edge cases
  4. Run validation → must still PASS

KILL MUTANTS:
  1. Try removing each instruction from SKILL.md
  2. Test must fail for each removal
  3. If test still passes → instruction is redundant or test is weak
```

### 14.3 Test Case Format

```json
{
  "id": "case-001-basic-extraction",
  "skill": "kg-extraction",
  "input": {
    "text": "Acme Corp issued 10,000 shares of Series A preferred stock.",
    "context": {
      "graph_id": "test-graph",
      "entity_types": ["BusinessEntity", "Security"]
    }
  },
  "expected": {
    "entities": [
      {"name": "Acme Corp", "type": "BusinessEntity", "confidence": "> 0.8"},
      {"name": "Series A preferred stock", "type": "Security", "confidence": "> 0.7"}
    ],
    "relationships": [
      {"source": "Acme Corp", "type": "ISSUED", "target": "Series A preferred stock"}
    ]
  },
  "assertions": [
    {"type": "entity_count", "value": 2},
    {"type": "relationship_count", "value": 1},
    {"type": "entity_type_match", "entity": "Acme Corp", "expected_type": "BusinessEntity"},
    {"type": "relationship_type_match", "source": "Acme Corp", "expected_type": "ISSUED"}
  ]
}
```

---

## 15. Infrastructure & Deployment

### 15.1 Docker Compose

```yaml
services:
  neo4j:
    image: neo4j:5.26-enterprise
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: neurosymbolic
      POSTGRES_USER: neurosymbolic
      POSTGRES_PASSWORD: password

  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [neo4j, redis, postgres]
    environment:
      NEO4J_URI: bolt://neo4j:7687
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://neurosymbolic:password@postgres:5432/neurosymbolic
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}

  frontend:
    build: ./frontend
    ports: ["3000:80"]
    depends_on: [backend]
```

### 15.2 Environment Variables

```bash
# LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Redis
REDIS_URL=redis://localhost:6379

# PostgreSQL
DATABASE_URL=postgresql://neurosymbolic:password@localhost:5432/neurosymbolic
```

---

## 16. Implementation Phases

### 16.0 Phase Dependency DAG

**[NEW]** Real blocking relationships between the phases below (not strict numeric order — several are independent and already done out of order relative to this list):

```
Phase 0 (Scaffolding) ── DONE
      │
Phase 1 (Backend Skeleton) ── PARTIAL (FastAPI+Neo4j done; minimal LangGraph skeleton DONE [UPDATED])
      │
      ├──▶ Phase 2 (Agent Layer) ── PARTIAL [UPDATED] (extractor/reasoner/responder real, live-verified;
      │         │                    router/enricher/querier/memory_agent still not started)
      │         │
      │         ├──▶ Phase 4 (MCP Layer) ── still NOT STARTED — needs agent nodes to expose tools to
      │         ├──▶ Phase 5 (Tool Layer) ── still NOT STARTED — the 3 real nodes call services
      │         │                            directly, no formal tool-registration layer yet
      │         └──▶ Phase 10 runtime skills ── PARTIAL [UPDATED]: 1 of 6 real (`kg-extraction`,
      │                   `backend/agents/skill_store.py`'s load_skill, loaded for real by the
      │                   extractor node). Unblocked now that Phase 2 has a real node to load into.
      │
      └──▶ Phase 3 (Memory Layer) ── DONE, was NOT blocked on Phase 2
                (§20's native rebuild only needed Neo4j + the existing services layer,
                 not an agent graph — this is why §20.5 recommended starting here, and it paid off)

Phase 6 (LLM Integration) ── DONE, independent of everything above (already shipped as LLMClient)
Phase 8 (Reasoning Engine) ── DONE, independent of everything above (already shipped, §8.4)
Phase 7 (Extraction) ── DONE, independent
Phase 7 (Enrichment/Polanyi, §19) ── DONE (all 11 heuristics + frontend), needed only Phase 7 Extraction
Phase 9 (Frontend) ── PARTIAL, tracks whichever backend phase it's surfacing (independent per-feature).
                       [UPDATED] UI for the Phase 6 /agent endpoint now exists (AgentPanel.tsx).
Phase 11 (Polish+Deploy) ── PARTIAL, last; Docker Compose full-stack piece needs nothing else to finish first
```

**Practical reading**: the only hard sequencing gate in the whole list is **Phase 1's LangGraph skeleton → Phase 2 Agent Layer → {Phase 4, Phase 5, runtime skills}**. Memory (Phase 3/§20), Enrichment (Phase 7/§19), Reasoning (Phase 8), and LLM Integration (Phase 6) are all independent of that chain and of each other — which is why §20.5 could recommend starting temporal memory now without waiting on the LangGraph wrap.

### Phase 0: Scaffolding + Skills Installation
- Install community skills from 4 repos
- Create `package.json`, `vite.config.ts`, `tsconfig.json` for frontend
- Create `pyproject.toml`, `requirements.txt` for backend
- Set up Docker Compose
- Create CLAUDE.md and AGENTS.md

### Phase 1: Backend Skeleton
- FastAPI app with health check
- LangGraph StateGraph skeleton (router → responder → end)
- Neo4j driver connection
- Redis connection for checkpointing
- PostgreSQL connection for long-term memory

### Phase 2: Agent Layer
- AgentState TypedDict
- All 7 agent nodes (router, extractor, enricher, reasoner, querier, responder, memory_agent)
- LangGraph Store wrapper
- Basic tool registration

### Phase 3: Memory Layer
- Conversation memory (LangGraph checkpointing via Redis)
- Working memory (AgentState)
- Long-term memory (LangGraph Store via PostgreSQL)
- Episodic memory (Neo4j reasoning trace nodes)
- Semantic memory (Neo4j vector index + OpenAI embeddings)

### Phase 4: MCP Layer
- Neo4j MCP server (get-schema, read-cypher, write-cypher)
- Custom KG MCP server (extract, enrich, reason, query)
- Memory MCP server (search, save)
- Skills MCP server (load, list, activate)

### Phase 5: Tool Layer
- All 6 tool categories registered as LangGraph tools
- Tool execution within agent nodes
- Tool result handling

### Phase 6: LLM Integration
- OpenAI GPT-4o extraction pipeline
- Claude 3.5 Sonnet enrichment pipeline
- NL → Cypher translation
- Keyword-matching offline fallback
- Prompt templates

### Phase 7: Extraction + Enrichment
- Entity extractor
- Relationship extractor
- Offline extractor (keyword-matching fallback)
- Polanyi 11 heuristics implementation
- Scoring and confidence thresholds

### Phase 8: Reasoning Engine (implement to §8.4, do NOT port the prototype loop verbatim)
- Persistent-activation spread: feedback seeds the next iteration; never reset activation to 0 between rounds
- Directed spreading consistent with rule evaluation (neural and symbolic layers agree on edge direction)
- Max-activation fixpoint relaxation (order-independent), not a single BFS sweep
- Parameterized decay/threshold chosen so depth ≥ 2 derivation is reachable (0.45 alone gives ~1-hop-only)
- Convergence predicate: no new facts AND activation delta < ε, capped at MAX_ITERATIONS; report which condition stopped it
- Single confidence calculus propagated neural → symbolic → feedback → proof path (§8.4)
- Reasoner as a cyclic LangGraph subgraph (self-loop until convergence), not a DAG node
- Proof tracer (carries premise proof paths into derived facts)
- Inference engine (decide single-premise vs Horn-clause rule language first — §8.4)

### Phase 9: Frontend Overhaul
- Zustand stores (graphStore, agentStore)
- API client (api.ts)
- WebSocket connection (websocket.ts)
- SkillManager component
- MemoryInspector component
- Updated GraphCanvas with new features
- Updated InspectorPanel with agent integration

### Phase 10: Skills + Eval Infrastructure
- 5 project-specific development-time skills (.claude/skills/)
- 5 project-specific runtime skills (backend/skills/)
- evals/ directory with cases, fixtures, results
- validate-skills.js
- run-evals.js

### Phase 11: Polish + Deploy
- Docker Compose full stack
- Error handling
- Loading states
- Accessibility
- Documentation

---

## 17. Reference Papers

### Primary: Polanyi "Neurosymbolic graph enrichment for Grounded World Models"
- 11 enrichment heuristics for implicit knowledge
- Applied to business analyst knowledge graph enrichment
- Source: `.firecrawl/paper1-polanyi-full.md`

### Secondary: Italian Legislation KG ETL Pipeline
- Neo4j property graph
- LLM-assisted graph completion
- Source: `.firecrawl/paper2-etl-full.md`

### Key External References
- MAGMA (ACL 2026): Multi-Graph based Agentic Memory Architecture
- A-MEM: Agentic Memory with Zettelkasten principles
- Letta/MemGPT: LLM-as-OS memory paradigm (NeurIPS 2023)
- Google DeepMind 2025: Lower bound proof for single-vector retrievers
- LoCoMo benchmark: 1,540 questions testing memory recall
- LongMemEval: Long-horizon memory evaluation
- Mem0: Dual-store model (vector + graph), 26% accuracy boost

---

## 18. Decision Record: Neo4j Skill Graph in v1

> **Added**: July 11, 2026
> **Decision**: The Neo4j-backed skill graph (specified in §2.9.14) is **in scope for v1**, not deferred.
> **Owner call**: Accepted despite the "premature for 10 skills" concern raised in review. Rationale below.

### 18.1 Scope

The graph-based skill discovery layer described in §2.9.14 ships in v1. This means the following are v1 deliverables, not future work:

- **Skill node schema** in Neo4j (`:Skill`, `:SkillUsage`, `:EntityType`, `:Domain`) with `REQUIRES` / `COMPLEMENTS` / `CONFLICTS` / `WORKS_WITH` / `USED_IN` relationships — per §2.9.14 "Neo4j Skill Schema".
- **`find_relevant_skills` tool** — Neo4j full-text + graph-boost query (§2.9.14 "Skill Discovery Tool").
- **`record_skill_usage` tool** — append-only usage nodes + rolling-average confidence update (§2.9.14 "Usage Tracking Tool").
- **`skill_description_index`** full-text index (§2.9.14 "Full-Text Index for Skill Search").
- **`HybridSkillDiscovery`** wrapper combining filesystem catalog + Neo4j queries (§2.9.14 "Hybrid Discovery").
- **`ResilientSkillDiscovery`** filesystem fallback when Neo4j is unavailable (§2.9.14 "When Neo4j Is Unavailable").

### 18.2 Rationale for v1 inclusion

- The skill graph is the project's differentiator, not incidental infrastructure — it doubles as a demonstrable feature of the skill-creation workspace, so it earns its place in the first release.
- Neo4j is already a v1 dependency (Phase 1 stands up the driver), so the marginal infra cost is a schema + two tools + one index, not a new service.
- Usage tracking from day one avoids a cold-start problem later: confidence scores need historical data to be meaningful, so recording must begin at launch even if querying stays simple.

### 18.3 Phase placement

| Work | Phase | Notes |
|---|---|---|
| Neo4j skill schema + constraints + `skill_description_index` | **Phase 3** (Memory Layer) | Runs alongside the semantic vector index setup; both are Neo4j index work. |
| `find_relevant_skills`, `record_skill_usage` tools | **Phase 4** (MCP Layer) — Skills MCP server | Extends the Skills MCP server (`load_skill`/`list_skills`/`activate_skill`) rather than adding a parallel surface. |
| `HybridSkillDiscovery` + `ResilientSkillDiscovery` wiring | **Phase 4** | Router node (Phase 2) is updated to call `find_relevant_skills` before `load_skill`. |
| `SkillManager.tsx` shows graph-driven recommendations + confidence | **Phase 9** (Frontend Overhaul) | Surfaces `confidence` and `requires` chains from the graph. |

### 18.4 v1 acceptance criteria

1. On backend startup, the 10 project skills are seeded as `:Skill` nodes with descriptions, `tier`, and initial `confidence` (default 1.0 until usage data exists).
2. `REQUIRES` edges are seeded for known prerequisites (e.g. `polanyi-enrichment -[:REQUIRES]-> kg-extraction`).
3. `find_relevant_skills("extract entities from financial text")` returns `kg-extraction` ranked first, using the full-text index.
4. After a skill runs, `record_skill_usage` appends a `:SkillUsage` node and updates the skill's rolling-average `confidence`.
5. With Neo4j stopped, `ResilientSkillDiscovery` falls back to filesystem keyword matching and the agent still completes tasks (degraded discovery, no crash) — covered by a test that kills the Neo4j connection mid-run.

### 18.5 Deferred out of v1 (still)

To keep the v1 skill graph bounded, these §2.9.14-adjacent ideas remain post-v1:

- A/B testing of skill variants and automated confidence-driven routing changes.
- `CONFLICTS`-based mutual-exclusion enforcement (schema modeled, not enforced in v1 routing).
- Cross-agent shared-graph learning beyond single-process usage recording.

---

## 19. Decision Record: Polanyi Enrichment Layer (v1)

> **Added**: July 11, 2026
> **Status**: **[UPDATED]** All 11 heuristics implemented, tested, and live-verified running together against a real graph — see §19.6 steps 1–4. Only frontend (§19.6 step 5) not started.
> **Reference**: `.firecrawl/paper1-polanyi-full.md` — "Neurosymbolic graph enrichment for Grounded World Models" (De Giorgis, Gangemi, Russo). This section documents the *actual* methodology read from the full paper (not the abstract), and two scoping decisions made against it.

### 19.1 What the paper actually specifies

The full pipeline (§3 of the paper):

```
(image → MLLM description) OR user-provided text
        ↓
Text2AMR2FRED:  SPRING (AMR parser) → BLINK (entity linking) → AMR2FRED
                (deterministic AMR→OWL/RDF, ~15 steps / 200+ rules) → eWiSeR (WSD)
                → aligned to DOLCE foundational ontology + Framester + PropBank/VerbNet
        ↓
"Base Graph" (OWL-RDF; e.g. fred:athlete_1 rdfs:subClassOf dul:Person)
        ↓
11 heuristic passes, each: prompt an LLM with
  [role: "expert ontology engineer"] + [input format/standards: OWL2, Turtle] +
  [heuristic definition + few-shot examples] + [output format rules: new triples only]
  → new triples anchored to Base Graph nodes → one XKG (Extended Knowledge Graph) per heuristic
        ↓
merge all 11 XKGs + Base Graph → final enriched graph
```

Text input is explicitly supported by the paper (not image-only) — "begins... with either user-provided text or an LLM-generated description of an input image."

**The 11 heuristics** (verbatim from §3.2, each is a general cognitive/pragmatic category, not domain-specific): **Presuppositions** (implicit assumptions needed for a statement to make sense), **Conversational Implicatures** (Gricean pragmatics — meaning beyond literal content), **Factual Impact** (physical/social/cognitive consequences of events on participants), **Image Schemas** (embodied cognitive structures — container, path, force, balance), **Metonymic Coercion** (part-whole sense-shift, e.g. "the White House announced"), **Moral-Value-Driven Coercion** (literal statement reinterpreted through a values lens), **Symbolic Coercion** (Peircean — literal meaning → symbolic interpretation), **Event Sequences** (implicit chronological ordering), **Causal Relations** (cause–effect, distinct from mere sequence or correlation), **Implied Future Events** (likely consequences not yet stated), **Implied Non-Events** (counterfactual alternatives the text implies were foreclosed).

### 19.2 Correction: this is domain-agnostic, not a "financial enrichment" feature

An earlier pass in this session scoped the heuristics against "is this relevant to financial documents" — that was wrong and has been corrected. The 11 heuristics operate on the **narrative/pragmatic structure of text itself**, independent of subject matter: a legal contract has causal relations and implied future events; a medical record has factual impact and presuppositions; a news article has all 11. They are not filtered by domain. **All 11 ship together**, exactly as the paper defines them, regardless of which domain ontology (§4 System Architecture; whatever repository is loaded in GraphDB) is active for entity typing.

This actually *strengthens* the domain-agnostic architecture: the heuristic layer is a second, permanently-fixed vocabulary (universal across every domain this product ever points at) sitting alongside the first, swappable vocabulary (the loaded ontology). Neither depends on the other.

### 19.3 Decision: adapt the Base Graph, do not replicate AMR/FRED/BLINK/eWiSeR

These four tools (SPRING AMR parser, AMR2FRED, BLINK entity linker, eWiSeR word-sense disambiguator) exist in the paper to solve one problem: *turn raw natural language into a structured graph with no prior domain schema*. This project already solves that problem differently — LLM structured-output extraction validated against whatever ontology is loaded (§5.2 `extraction/pipeline.py`, already shipped in the MVP). Adopting AMR/FRED/BLINK/eWiSeR alongside it would mean running two independent graph-construction pipelines against the same input, in two different type systems (FIBO-or-whatever vs. DOLCE/FrameNet/PropBank), that would need reconciliation to produce one coherent graph. It is also a genuinely large, largely orthogonal undertaking: SPRING and eWiSeR are GPU-hosted transformer models, AMR2FRED is a separate Java codebase (~15 conversion steps, 200+ condition checks), BLINK needs a Wikipedia entity index — weeks of polyglot tooling for output (generic `Person`/`Event`/image-schema structure) that isn't more useful to this product than the domain-typed graph it already produces.

**Decision: the already-extracted, ontology-typed graph (`:Entity`/`:RELATES`, real per PLAN.md §5.2) *is* the Base Graph.** The 11 heuristics run against it (plus the original source text for context) instead of against an AMR-derived graph.

### 19.4 Decision: DOLCE is a separate, optional, non-blocking consideration

DOLCE (Descriptive Ontology for Linguistic and Cognitive Engineering) is not a parser — it's a foundational/upper ontology meant to ground *any* domain ontology's classes under universal categories (`Person`, `Event`, `PhysicalObject`, `SocialObject`, `Quality`...). Unlike AMR/FRED/BLINK/eWiSeR, this is genuinely additive to the domain-agnostic goal: right now "domain-agnostic" means *config-swappable* (point GraphDB at a different repository, get a different vocabulary); a DOLCE alignment layer would make it *semantically grounded* — every loaded domain ontology's classes mapped to the same universal top-level via `rdfs:subClassOf`, enabling cross-domain comparison (e.g. an "organization" from FIBO and a "hospital" from a medical ontology both resolving to `dolce:SocialObject`).

**Decision: out of scope for the v1 enrichment work below.** It's a separate, smaller, later addition (consume DOLCE's public OWL file, map loaded-ontology classes to it) — not needed to ship the 11 heuristics, and not blocking them. Revisit once the heuristic layer is live and there's a concrete cross-domain use case that needs it.

### 19.5 Architecture

**Neo4j shape** (new node type, kept separate from both the ontology-typed `:Entity` graph and the rule-derived `:DerivedFact` graph — three distinct provenance layers, not conflated):
```
(:ImplicitFact {
  id, heuristicType,       // one of the 11 categories, e.g. "causal_relation"
  text,                    // the asserted implicit fact, natural language
  confidence,              // LLM-reported confidence for this assertion
  sourceDoc, graphId
})-[:ANCHORED_TO]->(:Entity)   // one or more anchor nodes in the Base Graph
```

**Prompt structure per heuristic** (following the paper's own §3.3.2 pattern, one prompt file per heuristic, e.g. `prompts/enrichment/causal_relations.txt`):
1. Role specification ("You are an expert ontology engineer...")
2. Input format/standards (the Base Graph subset in a compact textual form + the original source text)
3. Heuristic definition + 2-3 few-shot examples (ported from the paper's own examples per heuristic, §3.2)
4. Output format instructions: new `:ImplicitFact` assertions only, each naming its anchor node(s), confidence, and heuristic type — no free text outside the specified format

**Pipeline position**: after extraction (`:Entity`/`:RELATES` exist), independent of and parallel to reasoning (`:DerivedFact` — §8.4's rule-based loop). Human-in-the-loop approval before merge into the graph, per §7.3 (already speced: *"Enrichment (user approves/edits enrichment results)"*).

**Validation**: unlike domain extraction, `:ImplicitFact.heuristicType` is validated against the fixed 11-category enum (not the swappable ontology — these categories are Polanyi's own typology, not domain vocabulary). Anchor nodes must exist in the real graph (same anchoring-integrity check as extraction's ontology validation, applied to a different vocabulary).

### 19.6 Where to start implementing

Smallest real slice, TDD, one heuristic first to prove the pattern before building all 11:

1. **[DONE]** `enrichment/heuristics/base.py` — shared prompt-building + parsing (`HEURISTIC_TYPES` enum, `build_base_graph_text`, `run_heuristic`); `:ImplicitFact` persistence in `services/enrichment_service.py` (`save_pending_facts`, `list_pending_facts`, `list_approved_facts`, `set_fact_status`). Tests: `test_enrichment_base.py`, `test_enrichment_service.py`.
2. **[DONE] Causal Relations** first. `enrichment/heuristics/causal_relations.py` — prompt built per §19.5's 4-part structure, few-shot example ported verbatim from the paper's own §3.2 worked example ("The heavy rain forced the match to be postponed"). Tests: `test_causal_relations_heuristic.py`. Verified live against the running server with a real LLM and a real financial scenario ("Deutsche Bank AG postponed its planned bond issuance after regulatory scrutiny from FINMA increased sharply") — correctly produced `causal_relation` fact "regulatory scrutiny from FINMA caused Deutsche Bank AG to postpone its planned bond issuance", anchored to both real entities.
3. **[DONE]** `POST /enrich/{graphId}` + `GET /enrich/{graphId}/pending` + `GET /enrich/{graphId}/approved` + `POST /enrich/{graphId}/{factId}/approve` + `.../reject` (`api/enrich.py`). Rejected facts are kept with `status: "rejected"`, not deleted — audit trail of what an LLM proposed and a human declined. Tests: `test_api_enrich.py`. Verified live: pending → approve → moves from `/pending` to `/approved`.
4. **[DONE]** Remaining 10 heuristics, each following the pattern proven in step 2 — mechanical repetition, confirmed. Modules: `presuppositions.py`, `conversational_implicatures.py`, `factual_impact.py`, `image_schemas.py`, `metonymic_coercion.py`, `moral_value_coercion.py`, `symbolic_coercion.py`, `event_sequences.py`, `implied_future_events.py`, `implied_non_events.py` — each with a paper-sourced (§3.2) few-shot example. `enrichment/heuristics/__init__.py`'s `ALL_HEURISTIC_MODULES` registry + `services/enrichment_service.run_all_heuristics()` run all 11 together per a single `/enrich` call, matching §19.2's "all 11 ship together." Tests: `test_remaining_heuristics.py` (parametrized across all 10), `test_enrichment_registry.py`. **Live-verified** against the running server with a real financial scenario (Deutsche Bank AG / FINMA / bond issuance): 25 real facts across 10 of 11 heuristic types in one call (~13s, 11 sequential LLM calls). **One real finding from live verification, not a test**: `symbolic_coercion`'s first version leaked its few-shot example ("the Kangaroos") verbatim into the output for a scenario with no real symbolic coercion, instead of correctly returning an empty list — fixed by adding an explicit "the example is illustrative only, do not repeat it" instruction to that prompt, re-verified fixed. After the fix, `symbolic_coercion` still over-generates speculative, low-confidence associations on this scenario (e.g. "the Swiss Alps") rather than reporting none — an honest, expected limitation (the paper's own human evaluation found Symbolic Coercion among the lower-agreement heuristics across annotators), exactly the case human-in-the-loop approval exists to catch. Left as-is rather than over-tuned. **[UPDATED — recurrence found via the agent's `enrich` intent]** The same few-shot-leakage pattern reappeared in `moral_value_coercion` ("She always keeps her promises"), `event_sequences` (the flight/competition example), and `implied_non_events` ("She decided not to compete") — the same "illustrative only, don't repeat" instruction was applied to all three, confirmed fixed for two of the three; `symbolic_coercion`'s "the Kangaroos" leak persisted even after its own fix, on a second live run. This is a genuine local-model (llama-3.1-8b-instruct) instruction-following limitation with few-shot-heavy prompts, not a per-heuristic prompt-wording problem — chasing it further heuristic-by-heuristic has diminishing returns. The architectural answer stays the same: human-in-the-loop approval (`EnrichmentPanel.tsx`, confidence-sorted) is the real safeguard, not prompt perfection.
5. **Not started.** Frontend: an "Enrich" tab or section (left sidebar, alongside Construct/Reason/Ingest) showing pending `:ImplicitFact` assertions grouped by heuristic type, with approve/reject — spec already in `UI_PLAN.md` §9.3.

### 19.7 Explicitly deferred (not part of this decision)

- AMR/SPRING/AMR2FRED/BLINK/eWiSeR — redundant with existing extraction (§19.3).
- DOLCE/Framester foundational-ontology alignment — additive but separate (§19.4).
- The paper's image-input path (MLLM image→description) — this product's input is documents, not images; text path only.

---

## 20. Decision Record: Temporal Memory Layer (Graphiti/Zep-inspired, rebuilt natively)

> **Added**: July 11, 2026
> **Status**: Spec finalized, not implemented. Supersedes §4's memory-architecture references, which cited a less-verified project (see §20.1).
> **Scope**: rebuild the relevant concepts natively in this codebase — **not** a dependency on `graphiti-core` or the Zep API. No new Python package, no external service call. Same reasoning as §19.3 for Polanyi: reimplement the pattern against our own Neo4j, not bolt on someone else's library.

### 20.1 Why this supersedes §4

§4 ("Neo4j Context Graphs + Memory") cites `neo4j-labs/agent-memory` and a "Neo4j Labs, June 2026" context-graph concept — one of several citations flagged earlier in this session as unverifiable (future-dated, suspiciously precise star counts). Graphiti (`getzep/graphiti`) is different: real GitHub project, real research paper (arXiv:2501.13956, "Zep: A Temporal Knowledge Graph Architecture for Agent Memory"), and this project's own `.env` already has a provisioned `zep_API_KEY` — someone already scoped Zep as a candidate before this session. §4 is kept for history; this section is the one to build from.

### 20.2 Graphiti's actual data model (verified against source, not the abstract)

Read directly from `graphiti_core/nodes.py` and `graphiti_core/edges.py`:

```
EpisodicNode        — raw ingested data (message | json | text | fact_triple),
                       source_description, content, valid_at (doc time),
                       entity_edges (which EntityEdges this episode produced)
                       → the ground-truth provenance layer; every derived fact traces back here

EntityNode           — name, name_embedding, summary (natural-language, evolves
                       as new episodes reference it), attributes (label-specific)

EntityEdge           — name, fact (the assertion as text), fact_embedding,
                       episodes (provenance: which episodes support this fact),
                       valid_at / invalid_at / expired_at (bi-temporal —
                       "when information changes, old facts are invalidated,
                       not deleted"), reference_time, attributes

CommunityNode        — groups of related entities, name_embedding, summary
```

Zep (the product layer on top) adds session/user memory: `memory.add(session_id, messages)` appends chat turns; `memory.get(session_id)` returns a `context` string (built from the user's graph, not just that session) for injection into the next LLM call, plus recent raw messages.

### 20.3 The real gap this fixes in the current codebase

`services/graph_service.upsert_entity` (real, shipped) does a blind `MERGE ... SET` — if a second ingest asserts a fact that contradicts the first (e.g. doc 1 says "CEO: Jane Smith", doc 5 says "CEO: John Doe"), the old value is silently overwritten. There is no record that Jane Smith *was* CEO, no timestamp of when the fact changed, nothing queryable like "who was CEO in March." This is exactly the problem Graphiti's bi-temporal `EntityEdge` model solves, and it's a real, current gap — not speculative.

Separately: `POST /chat/{graphId}` (real, shipped, §"Backend spec" in `MVP_PLAN.md`) is stateless — every call rebuilds full graph context from scratch with no memory of prior turns in the same conversation. That's the gap Zep's session/user memory model solves.

Also: `:IngestEvent` (real, shipped — `services/history_service.py`) is *already* structurally close to Graphiti's `EpisodicNode` (raw text + timestamp + counts) — it just isn't linked to the entities/edges it produced, and isn't used for provenance queries. Extending it, not replacing it, is the natural path.

### 20.4 What to rebuild (native, no dependency)

1. **[DONE] Provenance linking** — `IngestEvent-[:PRODUCED]->Entity`, so "which document said this" is a graph traversal, not a guess from `sourceDoc` string matching. Also stamps `producedByEventId` on newly-created `:RELATES` edges. `services/history_service.py` (`record_ingest_event(entity_ids=...)`, `get_produced_entity_ids`, `get_entity_provenance`), wired in `services/ingest_service.py`. API: `GET /graph/{graphId}/nodes/{nodeId}/provenance` (`api/graph.py`). Tests: `test_history_service.py`, `test_ingest_service.py`, `test_api_provenance.py`.
2. **[DONE] Bi-temporal facts** — added `validAt`/`invalidAt` to `:RELATES` edges. On a new edge asserting a different target for the same (source, edge-type), the prior current edge is invalidated (`invalidAt = datetime()`), not overwritten — old facts stay queryable via the new `get_relationship_history()`. `get_graph()`/`load_triples()` stay current-only (`WHERE r.invalidAt IS NULL`) so existing callers are unaffected. `services/graph_service.py` (`upsert_relationship`, `get_relationship_history`). API: `EdgeResponse` now carries `validAt`/`invalidAt`/`producedByEventId` (`api/graph.py`). Tests: `test_graph_service.py`, `test_api_provenance.py`. **Known simplification** (documented in code): treats every relation type as single-valued per source (no ontology cardinality metadata to distinguish functional vs multi-valued predicates) — a genuinely multi-valued relation (e.g. "hasSubsidiary") would have its earlier targets incorrectly invalidated when a new one is asserted. Not hit by current rule/reasoning usage; flag if a real multi-valued case shows up. Frontend surfacing (superseded-fact badges, history view) is spec'd but not built — see `UI_PLAN.md` §9.1/9.2.
3. **[DONE] Evolving entity summaries** — `:Entity.summary`, regenerated by a real LLM call each time a new ingest references that entity, accumulating context across ingests (mirrors `EntityNode.summary`). `services/summary_service.py` (new, `generate_summary`), wired into `services/ingest_service.py` right after each entity upsert (reads the existing summary via `graph_service.get_entity_summary`, synthesizes with the new ingest's full source text, writes back via `graph_service.update_entity_summary`). Exposed on `NodeResponse.summary` in both `api/graph.py` and `api/ingest.py`. Tests: `test_summary_service.py`, `test_ingest_service.py`, `test_api_provenance.py`. Verified live against the running server with two separate real ingests about "Deutsche Bank AG" (Frankfurt/commercial-bank in doc 1, a EUR 500M bond in doc 2) — the resulting summary genuinely synthesized both, not just the latest.
4. **[DONE] Session memory for chat** — `:ChatSession`/`:ChatMessage` nodes (ordered via a `seq` property, not relying on same-millisecond `createdAt` ordering), linked `(:ChatSession)-[:HAS_MESSAGE]->(:ChatMessage)`. `POST /chat` now reads recent history into the system prompt alongside the existing graph-grounded context, then appends both the user turn and the reply — mirrors Zep's `memory.add`/`memory.get`. `services/chat_history_service.py` (new), wired into `services/chat_service.py`. API: `ChatRequest.session_id` is optional — omitting it defaults to one continuous session per graph (`{graphId}:default`), so existing callers get real memory for free without a frontend change. Verified live against the running dev server: told it "My favorite number is 42," then asked "What did I just tell you?" in a second call with no session_id — correctly replied "42." Tests: `test_chat_history_service.py`, `test_chat_service.py`, `test_api_chat.py`.
5. **[DONE]** Community detection — originally deferred as lowest priority/most speculative for this product's single-analyst usage pattern, then built on explicit direction using the **real Neo4j GDS plugin** (confirmed installed: `gds.version()` → `2026.03.0`), not a hand-rolled approximation. `services/community_service.py`: `detect_communities()` projects the graph_id-scoped `:Entity`/`:RELATES` subgraph into an in-memory GDS graph via `gds.graph.project.cypher` (deprecated in this GDS version in favor of the newer Cypher-projection-as-aggregation-function form, but confirmed still functional live — noted in code for future revisit), runs `gds.louvain.write` writing `communityId` onto each `:Entity`, drops the projection. `get_communities()` reads back without recomputing. API: `POST`/`GET /graph/{graphId}/communities` (`api/graph.py`), `NodeResponse`/`GraphNodeRecord` gained `communityId`. Tests: `test_community_service.py` (disconnected-cluster separation proof), `test_api_communities.py`. **Live-verified** against the real running server on the real `default` graph: Credit Suisse/FINMA/Zurich correctly clustered separately from UBS Group/Switzerland/Swiss regulator/HDFC — semantically sensible communities from real Louvain, not synthetic data.

### 20.5 Where this sits relative to §19 (Polanyi) and Phase 6 (LangGraph)

Three deferred-but-now-spec'd workstreams exist: Polanyi enrichment (§19), temporal memory (§20), LangGraph wrap (`MVP_PLAN.md` Phase 6). They're independent — no ordering dependency between them. **[UPDATED] Temporal memory items 1–4 are now done** (provenance linking, bi-temporal facts, evolving summaries, chat session memory — §20.4), each TDD'd and live-verified against the running server. Original recommendation (items 1–2 first, smallest slice, fixes a real correctness gap) held; items 3–4 followed the same pattern. Remaining: item 5 (community detection, deferred), and the two still-independent workstreams — Polanyi enrichment (§19, 0% implemented, `enrichment/heuristics/` doesn't exist) and the LangGraph wrap (`MVP_PLAN.md` Phase 6, the only remaining MVP item).

### 20.6 Explicitly deferred (not part of this decision)

- ~~Community detection~~ **[now DONE, see §20.4 item 5]** — implemented via real Neo4j GDS on explicit direction, superseding this deferral.
- Any dependency on `graphiti-core`, the Zep hosted API, or the `zep_API_KEY` already in `.env` — this is a from-scratch reimplementation of the concepts against this project's own Neo4j, per the "no need to integrate, just rebuild" direction. (GDS is different: it's a real Neo4j-native plugin already installed in this project's own database, not an external service dependency — using it isn't a violation of that direction.)
- Redis/PostgreSQL-backed checkpointing (§9.1) — still MVP-deferred, unrelated to this decision.
