# Neurosymbolic Knowledge Graph Reasoning Application — Complete Plan

> **Last Updated**: July 11, 2026
> **Status**: Architecture finalized, awaiting execution

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
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

### 13.1 Development-Time Skills (.claude/skills/)

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

#### kg-extraction/SKILL.md
```
---
name: kg-extraction
description: Use when extracting entities and relationships from financial text.
  Activates on extraction requests.
---
```
Domain knowledge for extraction: FIBO entity types, relationship taxonomy, extraction rules.

#### polanyi-enrichment/SKILL.md
```
---
name: polanyi-enrichment
description: Use when enriching a knowledge graph with implicit knowledge.
  Activates on enrichment requests.
---
```
Domain knowledge for enrichment: 11 heuristics, scoring criteria, confidence thresholds.

#### kg-query/SKILL.md
```
---
name: kg-query
description: Use when answering natural language questions about the knowledge graph.
  Activates on query requests.
---
```
Domain knowledge for querying: Cypher patterns, common queries, result formatting.

#### neurosymbolic-reasoning/SKILL.md
```
---
name: neurosymbolic-reasoning
description: Use when running neurosymbolic reasoning over the knowledge graph.
  Activates on reasoning requests.
---
```
Domain knowledge for reasoning: Spread activation parameters, proof tracing, inference rules.

#### kg-visualization/SKILL.md
```
---
name: kg-visualization
description: Use when visualizing or exporting the knowledge graph.
  Activates on visualization requests.
---
```
Domain knowledge for visualization: Layout algorithms, color coding, export formats.

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
