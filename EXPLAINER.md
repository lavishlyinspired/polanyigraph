# Neurosymbolic KG — End-to-End Explanation

This is a **neurosymbolic knowledge graph system** that ingests documents, extracts an entity-relationship graph using an LLM (validated against a real ontology), reasons over it with a persistent neural+symbolic loop, and lets you explore everything through a web UI.

---

## The Setup

You have two databases:
- **GraphDB** (RDF/OWL) — holds the **ontology** (the "vocabulary"). For finance, this is [FIBO](https://spec.edmcouncil.org/fibo/) — it defines types like `CommercialBank`, `Loan`, `InterestRate`, `Organization` and their relationships.
- **Neo4j** — holds the **instance graph** (the actual extracted facts about real companies, people, deals).

---

## Step 1: Ingest a Document

You paste this press release into the UI:

> *"Goldman Sachs reported Q4 net income of $2.1B, driven by strong investment banking fees. The bank raised its dividend by 12% and announced a $3B share buyback program."*

---

## Step 2: Extraction (Neural — LLM + Ontology Validation)

The extraction pipeline (`backend/extraction/pipeline.py`):

1. **Queries GraphDB via SPARQL** to load the ontology vocabulary — all entity types (`CommercialBank`, `Dividend`, `ShareBuyback`, `FinancialReport`) and relationship properties (`reportsEarnings`, `announcesDividend`, `hasShareBuyback`).

2. **Ranks** ontology types by token overlap with the text (top 60 classes, 40 properties) and builds an LLM prompt grounded in the ontology.

3. **LLM extracts** structured JSON:
   ```json
   {
     "entities": [
       {"name": "Goldman Sachs", "type": "CommercialBank", "confidence": 0.95},
       {"name": "Q4 2024", "type": "FinancialPeriod", "confidence": 0.90},
       {"name": "$2.1B", "type": "MonetaryAmount", "confidence": 0.88}
     ],
     "relationships": [
       {"source": "Goldman Sachs", "relation": "reportsEarnings", "target": "Q4 2024", "confidence": 0.92},
       {"source": "Goldman Sachs", "relation": "announcesDividendIncrease", "target": "12%", "confidence": 0.85}
     ]
   }
   ```

4. **Validates** against the full ontology — anything not in FIBO is dropped.

5. **Materialization policy** decides: `Goldman Sachs` → **Node** (important entity), `$2.1B` → **Property** (noise if it were a node), `12%` → **Property**.

6. **Writes to Neo4j** — `MERGE` entities (idempotent), upsert relationships with bi-temporal tracking (`validAt`/`invalidAt`), run entity resolution (dedup against previously extracted "Goldman Sachs" nodes).

---

## Step 3: The Graph (What's in Neo4j)

After ingesting several documents, your Neo4j graph might look like:

```
(Goldman Sachs) --[reportsEarnings]--> (Q4 2024)
(Goldman Sachs) --[isType]--> (CommercialBank)
(Goldman Sachs) --[hasSubsidiary]--> (GS Asset Management)
(Goldman Sachs) --[employs]--> (David Solomon)
(JPMorgan) --[isType]--> (CommercialBank)
(JPMorgan) --[competesWith]--> (Goldman Sachs)
(CommercialBank) --[subClassOf]--> (Organization)  ← from ontology
```

---

## Step 4: Reasoning (Neurosymbolic Loop)

This is the core innovation. You define rules like:

```json
{
  "edge_type": "competesWith",
  "source_type": "CommercialBank",
  "target_type": "CommercialBank",
  "threshold": 0.3,
  "weight": 0.7
}
```

The reasoning engine (`backend/reasoning/engine.py`) runs a **persistent loop**:

### Iteration 1

1. **Spread Activation (Neural):** Start from `Goldman Sachs` (activation=1.0). Spread through edges with `decay=0.45`:
   - `Goldman Sachs → Q4 2024`: activation = 1.0 × 0.45 × edge_weight
   - `Goldman Sachs → GS Asset Management`: activation = 1.0 × 0.45 × edge_weight
   - `Goldman Sachs → David Solomon`: activation = 1.0 × 0.45 × edge_weight
   - `JPMorgan → Goldman Sachs` (via competesWith): JPMorgan gets activation = 0.45 × edge_weight

2. **Rule Inference (Symbolic):** Check all rules against activated edges. The `competesWith` rule fires because both `JPMorgan` and `Goldman Sachs` have activation > threshold and their types match (`CommercialBank` IS-A `Organization` via ontology subclass).

3. **Feedback:** `JPMorgan`'s activation is boosted (persistent activation). This feeds back into the next iteration.

### Iteration 2

- Spread continues from `JPMorgan` with boosted activation, potentially reaching entities connected to JPMorgan but not to Goldman Sachs — **multi-hop discovery**.
- New rules may fire on these newly activated edges.

### Convergence

Loop stops when no new facts are derived AND activation delta < epsilon (0.001).

### Output

A `DerivedFact` node:

```
(DerivedFact {
  fact: "JPMorgan competes with Goldman Sachs in the CommercialBank sector",
  confidence: 0.87,
  ruleId: "competesWith_rule",
  proofPathJson: ["Goldman Sachs", "competesWith", "JPMorgan"]
}) --[DERIVED_FOR]--> (JPMorgan)
```

---

## Step 5: Enrichment (Polanyi Layer)

After extraction, the system runs **11 cognitive heuristics** in parallel — each an LLM call that looks at the graph and source text to find *implicit* knowledge. For example:

- **Factual Impact:** "Goldman Sachs raised dividend by 12%" → implicit fact: "Shareholder income increases"
- **Implied Future:** "announced $3B buyback" → implicit fact: "Goldman Sachs share count will decrease"
- **Presupposition:** "Q4 net income of $2.1B" → implicit fact: "Goldman Sachs was profitable in Q4"

These land as `:ImplicitFact` nodes with `pending` status, awaiting your human approval in the UI.

---

## Step 6: Query & Analytics

- **Natural Language Query:** "Which banks compete with Goldman Sachs?" → LLM translates to Cypher, executes against Neo4j.
- **Graph Analytics:** PageRank identifies `Goldman Sachs` as a central node. Betweenness centrality reveals `CommercialBank` as a bridge entity connecting different clusters.

---

## Step 7: UI

The React frontend (`frontend/`) lets you:

- **Workspace:** Visualize the graph with SVG, drag nodes, see heatmap overlays of activation values, view proof paths
- **Documents:** Ingest new text, review/approve enrichment facts
- **Logic:** Create rules, view mined rule candidates, manage the rule set
- **Inference:** Step through reasoning manually (Spread → Infer → Feedback), review derived facts
- **Query:** Run DSL or natural language queries
- **Analytics:** Run centrality algorithms, view projections

---

## The Key Insight

The system is **domain-agnostic**. Swap the FIBO ontology in GraphDB for a biomedical ontology (e.g., Gene Ontology) and the entire system — extraction, reasoning rules, enrichment — works for biology without code changes. The ontology *is* the domain knowledge; the code is the reasoning machinery.

The "neurosymbolic" part is the **tight loop** between:

- **Neural** (spread activation — fuzzy, graded, emergent)
- **Symbolic** (rules — crisp, logical, interpretable)

They feed each other iteratively until convergence, enabling multi-hop inference that neither approach alone could achieve.
