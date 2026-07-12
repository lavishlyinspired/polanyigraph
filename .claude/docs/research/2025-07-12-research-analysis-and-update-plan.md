# Research Analysis & Project Update Plan

> **Created**: July 12, 2026
> **Status**: Plan — not implemented
> **Scope**: End-to-end analysis of 8 research resources and how they apply to this project

---

## Table of Contents

1. [Resource Analysis](#1-resource-analysis)
2. [Gap Analysis](#2-gap-analysis)
3. [Implementation Plan](#3-implementation-plan)
4. [Benchmark Baseline](#4-benchmark-baseline)
5. [Architectural Decisions](#5-architectural-decisions)

---

## 1. Resource Analysis

### 1.1 DeLong et al. Survey (IEEE TNNLS 2024, arXiv:2302.07200)

**What it is**: The definitive taxonomy of neurosymbolic methods for KG reasoning. 34 tools surveyed, classified into 3 major categories with 10 subcategories.

**Taxonomy**:

| Category | Mechanism | Representative Tools |
|---|---|---|
| **Cat 1: Logically-Informed Embeddings** | Logic augments graph, then neural method runs on augmented graph | KALE, JEKR, LOGICA |
| **Cat 2: Learning with Logical Constraints** | Neural method training regularized by logic rules | KALE, RUGE, IterE, CPL |
| **Cat 3: Rule Learning** | Iterative feedback: embeddings -> rule weights -> embeddings | MINERVA, NeuralLP, RNNLogic, DRUM, ExpressGNN |

**Key findings relevant to this project**:
- The best-performing tools use **iterative feedback** between neural and symbolic components (Category 3) — this is exactly what the neurosymbolic loop does
- **GNN embeddings** are used in virtually every high-performing method as the neural backbone
- The survey identifies **end-to-end differentiability**, **multi-modal data**, **spatiotemporal reasoning**, and **few-shot learning** as underexplored directions
- No tool in the survey combines ontology-agnostic vocabulary swapping with Polanyi enrichment — this is genuinely novel

**What this project maps to**: A hybrid of Category 1 (logic augments the graph via rules -> facts) and Category 3 (iterative feedback loop between spread activation and rule firing). Missing the neural embedding backbone that Categories 1 and 2 use.

### 1.2 NeSymGraphs GitHub Organization

**What it is**: Curated forks of all 34 surveyed tools. Key repos:

| Repo | Relevance to This Project |
|---|---|
| **ExpressGNN** | Most directly applicable — combines GNN + Markov Logic Networks for probabilistic reasoning over KGs |
| **RNNLogic** | Neural rule learning — iteratively learns rule confidences |
| **walking-rdf-and-owl** | Feature learning over RDF/OWL — directly applicable to the GraphDB ontology layer |
| **reonto** | Neuro-symbolic relation extraction using ontologies + GNNs — extraction pipeline inspiration |
| **TFLEX** | Temporal feature-logic embeddings — applicable to the bi-temporal layer |
| **gekcs** | Turning KG embeddings into generative models — generative KG completion |

### 1.3 AIHub Blog Post

**What it is**: Accessible summary of the survey using a crime scene corkboard analogy.

**Key pedagogical insight**: The "detective (neural) + scientist (symbolic)" framing maps directly to this project:
- **Detective** = LLM extraction + spread activation (pattern recognition)
- **Scientist** = Ontology validation + rule inference (logical deduction)
- **The corkboard** = The knowledge graph itself

### 1.4 ExpressGNN (ICLR 2020)

**What it is**: Combines Markov Logic Networks (MLNs) with GNNs for scalable probabilistic logic reasoning.

**Core architecture**:
```
Knowledge Graph -> GNN Encoder -> Entity/Relation Embeddings
                                    |
Logic Rules -> MLN Potential Functions -> Joint Inference
                                    |
                          Variational EM Training
```

**Key technical details**:
- **ExpressGNN-E**: GNN-only variant (embedding + logic rules via variational lower bound)
- **ExpressGNN-EM**: Full variational EM — alternates between E-step (GNN inference) and M-step (parameter update)
- Uses **slice_dim** parameter to control the GNN's expressiveness vs. simplicity tradeoff
- Tested on Kinship (small), FB15K-237 (medium), and NELL-995 (large)
- **Key result**: Significantly outperforms pure GNN methods on sparse/long-tail relations because logic rules provide structural priors

**Direct applicability**: ExpressGNN's variational EM framework could replace the hand-tuned `decay`, `threshold`, and `weight` parameters in the reasoning engine with **learned parameters** optimized end-to-end.

### 1.5 MAGNet (arXiv:2012.09762)

**What it is**: Multi-agent RL using self-attention to build relevance graphs, then GNN message-passing for coordination.

**Key technique**: Agents as nodes, dynamically-constructed relevance graph via self-attention, message-generation for inter-agent communication.

**Applicability**: Relevant if/when the project moves to multi-agent architecture (Phase C of the update plan). The self-attention mechanism for agent-to-agent relevance scoring is directly useful.

### 1.6 Akash Goyal's MAGRL Article (Medium)

**What it is**: A vision piece proposing ontology-grounded multi-agent graph reinforcement learning for healthcare.

**Core proposal**: Agents as nodes in a KG, ontology constraints limit which agents handle which entity types, GNN message-passing for coordination.

**Direct relevance**: This is *your own vision* for extending the project. The current single-agent LangGraph architecture is the foundation; the MAGRL proposal is the multi-agent evolution.

### 1.7 ICML 2023 KLR Workshop Papers

**Key papers relevant to this project**:

| Paper | Relevance |
|---|---|
| **Deep Neuro-Symbolic Weight Learning in Neural PSL** (Pryor et al.) | Learnable rule weights — directly applicable to making `Rule.weight` a learned parameter |
| **Neuro-Symbolic Continual Learning** (Marconato et al.) | Concept rehearsal — relevant to the evolving entity summary system |
| **Semantic Conditioning at Inference** (Ledaguenel et al.) | Constraining neural outputs with logical background knowledge — the exact pattern of ontology validation in extraction |
| **Neurosymbolic AI for Reasoning on Biomedical KGs** (DeLong et al.) | Biomedical variant of the survey — validates the domain-agnostic approach |

### 1.8 MAGNet (arXiv:2012.09762) — Multi-agent Graph Network

Same as 1.5 — this is the MAGNet paper on multi-agent graph networks for deep MARL.

---

## 2. Gap Analysis

### Gap 1: No GNN Embedding Layer [HIGH IMPACT]

**Current state**: The reasoning engine uses hand-tuned scalar values for edge weights (default 1.0), node salience (default 1.0), and activation decay (default 0.45). There is no learned representation of the graph structure.

**What the literature shows**: Every Category 1 and 2 tool uses GNNs to learn entity/relation embeddings. ExpressGNN specifically demonstrates that combining GNN embeddings with logic rules dramatically outperforms either alone — especially on sparse/long-tail relations.

**Impact**: Without learned embeddings, the reasoning engine treats all edges equally (weight=1.0) unless manually overridden. It cannot discover that certain structural patterns (e.g., a specific path type) are more informative than others.

**Concrete gap in code**:
- `reasoning/engine.py:Node.salience` — always 1.0 unless manually set
- `reasoning/engine.py:Edge.weight` — always 1.0 unless manually set
- `reasoning/engine.py:spread_activation()` — uses fixed `decay` parameter
- No PyTorch/DGL/PyG dependency anywhere in the codebase

### Gap 2: No End-to-End Trainability [HIGH IMPACT]

**Current state**: The pipeline is a sequence of independent stages:
```
Document -> LLM Extract -> Graph Write -> Manual Rules -> Spread Activation -> Facts
```
Errors at any stage don't feed back to improve earlier stages. The LLM extraction prompt is static. Rule weights are static. The decay/threshold parameters are static.

**What the literature shows**: The best tools (ExpressGNN, RNNLogic, IterE) have differentiable pipelines where the reasoning output improves extraction and rule selection.

**Impact**: The system cannot improve over time without manual tuning.

### Gap 3: No Rule Learning [MEDIUM IMPACT]

**Current state**: Rules are hand-authored in `data/rules/fibo_rules.json` (4 rules). Custom rules can be added manually via the Construct tab, but there is no automatic rule discovery or weight learning.

**What the literature shows**: The survey's entire Category 3 (Rule Learning) — NeuralLP, RNNLogic, DRUM, MINERVA, RuLES — all automatically mine rules from data and learn their confidences. RNNLogic's iterative approach (train embeddings -> score rules -> update rule set -> repeat) is particularly relevant.

**Impact**: For each new domain, someone must manually author rules. The system cannot discover patterns like "organizations that are regulated by the same agency tend to be domiciled in the same jurisdiction."

### Gap 4: No KG Embedding Baseline [MEDIUM IMPACT]

**Current state**: No knowledge graph embedding model (TransE, RotatE, ComplEx, etc.) exists in the codebase. There is no way to predict missing relationships or score candidate facts.

**What the literature shows**: KG embeddings are the baseline against which all neurosymbolic methods are compared. They enable link prediction, relation scoring, and entity clustering.

**Impact**: Cannot predict missing facts, no comparison baseline, no embedding-based similarity search.

### Gap 5: No Multi-Agent Coordination [MEDIUM IMPACT]

**Current state**: Single LangGraph agent with 7 nodes. Each node calls a service sequentially. No inter-agent communication or parallel execution.

**What the literature shows**: MAGNet and MAGRL demonstrate that graph-structured agent coordination with GNN message-passing outperforms sequential or flat architectures.

**Impact**: Limited scalability for complex multi-step reasoning tasks. No specialization or parallel processing.

### Gap 6: No Probabilistic Reasoning [MEDIUM IMPACT]

**Current state**: Deterministic rule firing — a rule fires if `activation >= threshold`, doesn't fire otherwise. Confidence is `activation * rule.weight` (bounded product). No formal probability theory.

**What the literature shows**: ExpressGNN uses Markov Logic Networks for principled probabilistic inference. Rules have weights that define a probability distribution over possible worlds.

**Impact**: Cannot handle uncertainty formally. Two conflicting rules produce arbitrary results rather than a principled probability.

### Gap 7: No Temporal Reasoning [LOW-MEDIUM IMPACT]

**Current state**: Bi-temporal data model exists (`validAt`/`invalidAt` on edges), but no reasoning engine reasons about time. You can store *when* a fact was true, but cannot infer temporal consequences.

**What the literature shows**: TFLEX (NeurIPS 2023) in NeSymGraphs handles temporal KG reasoning — reasoning about how facts evolve over time.

**Impact**: Cannot answer questions like "Was entity A domiciled in Switzerland when it issued that security?"

### Gap 8: Evaluation Coverage [HIGH IMPACT for credibility]

**Current state**: 11 eval cases across 6 skills. No standard benchmark dataset. No comparison against published baselines.

**What the literature shows**: Every surveyed tool is evaluated on FB15K-237, WN18RR, Kinship, or NELL-995 with standard metrics (MRR, Hits@1/3/10).

**Impact**: Impossible to claim the system performs well relative to the state of the art. No reproducibility.

---

## 3. Implementation Plan

### Phase A: Foundation (2-3 weeks) — GNN Embeddings + Benchmarks

#### A1: Add PyTorch Geometric Dependency

**Files to change**:
- `backend/pyproject.toml` — add `torch`, `torch-geometric`, `torch-scatter`
- `backend/requirements.txt` — add dependencies

**Rationale**: PyG is the standard framework for GNNs. Already used by many of the surveyed tools.

#### A2: Implement a Relation-Aware GNN Module

**New file**: `backend/reasoning/gnn_embeddings.py`

**Architecture** (following ExpressGNN's approach):
```python
class KGEmbeddingGNN(nn.Module):
    """
    Relation-aware GCN that learns entity embeddings from graph structure.
    Input: Entity features (existing 1024-dim embeddings from NVIDIA) + graph adjacency
    Output: Entity embeddings that encode structural patterns
    """
    def __init__(self, input_dim=1024, hidden_dim=256, output_dim=128, num_relations=...):
        # R-GCN or similar relation-aware message passing
        # Each relation type has its own weight matrix

    def forward(self, x, edge_index, edge_type):
        # x: entity features [num_entities, input_dim]
        # edge_index: COO adjacency [2, num_edges]
        # edge_type: relation type indices [num_edges]
        # Returns: entity embeddings [num_entities, output_dim]
```

**Key design decisions**:
- Use the existing 1024-dim NVIDIA embeddings as input features (they're already on the `:Entity` nodes as `summaryEmbedding`)
- Output a lower-dimensional (128-dim) structural embedding that encodes graph patterns
- Relation-aware: different relation types get different message functions (like R-GCN or ExpressGNN's architecture)
- Trainable via the variational EM framework from ExpressGNN

#### A3: Wire GNN Into the Reasoning Engine

**Files to change**:
- `backend/reasoning/engine.py` — modify `spread_activation()` to use GNN-derived edge weights and node salience
- `backend/services/reasoning_service.py` — load and run GNN before spreading activation

**Concrete changes**:
```python
# In reasoning_service.py, before calling reason():
gnn = KGEmbeddingGNN.load(...)
entity_embeddings = gnn(entity_features, adjacency, relation_types)

# Pass learned weights to the engine:
for edge in edges:
    edge.weight = compute_edge_weight(edge, entity_embeddings)  # learned, not 1.0

for node in nodes:
    node.salience = compute_salience(node, entity_embeddings)   # learned, not 1.0
```

#### A4: Import Standard Benchmark Dataset

**New files**:
- `backend/data/benchmarks/fb15k237/` — train/dev/test splits
- `backend/tests/test_benchmark.py` — benchmark evaluation harness

**Dataset**: FB15K-237 (the most commonly used benchmark in the survey). 14,541 entities, 237 relations, 272,115 training triples.

**Metrics**: MRR (Mean Reciprocal Rank), Hits@1, Hits@3, Hits@10 — the standard metrics used by every surveyed tool.

#### A5: End-to-End Benchmark Pipeline

**New file**: `backend/benchmark/evaluate.py`

```python
def evaluate_benchmark(dataset, model):
    """
    1. Load benchmark triples
    2. Run extraction on benchmark text descriptions (if available)
    3. Run reasoning (GNN + rules) to predict missing triples
    4. Score against ground truth
    5. Report MRR, Hits@1/3/10
    """
```

This gives you a baseline number to beat and compare against ExpressGNN's published results.

### Phase B: Learning (1-2 months) — Learnable Rules + Probabilistic Reasoning

#### B1: Make Rule Weights Learnable

**Files to change**:
- `backend/reasoning/engine.py` — change `Rule.weight` from fixed to a parameter
- `backend/reasoning/rules_repo.py` — support loading rules with initial weights from data

**Concrete approach**:
```python
# In engine.py, Rule becomes:
@dataclass
class Rule:  # no longer frozen
    id: str
    name: str
    edge_type: str
    source_type: str
    target_type: str
    threshold: float
    weight: float = 1.0  # now learnable
    learnable: bool = True  # flag for training
```

Training signal: facts that are verified (approved by human or match known ground truth) increase the rule's weight; facts that are rejected decrease it.

#### B2: Implement Rule Mining (NeuralLP/RNNLogic-inspired)

**New file**: `backend/reasoning/rule_miner.py`

```python
class RuleMiner:
    """
    Mines candidate rules from the graph structure.
    Following NeuralLP's approach: differentiable rule discovery over relation paths.
    """
    def mine_candidates(self, graph, max_path_length=3):
        """
        For each relation r, find paths of length 1..max_path_length
        that connect entities of the expected types.
        Return candidate rules with initial weights.
        """

    def update_weights(self, verified_facts, rejected_facts):
        """
        Increase weight for rules that produced verified facts.
        Decrease weight for rules that produced rejected facts.
        """
```

#### B3: Probabilistic Rule Scoring

**Files to change**:
- `backend/reasoning/engine.py` — replace threshold-based firing with probabilistic scoring

**Concrete change**:
```python
# Current (deterministic):
fired = activation >= threshold

# Proposed (probabilistic):
fire_probability = sigmoid((activation - threshold) * temperature)
fact.confidence = fire_probability * rule.weight
```

This is a minimal change to the engine that makes rule firing stochastic rather than binary, enabling principled uncertainty handling.

#### B4: Iterative Rule-Embedding Co-Training

**New file**: `backend/reasoning/train.py`

Following ExpressGNN's variational EM framework:
```python
def train_epoch(graph, rules, gnn_model, llm_client):
    """
    E-step: Run GNN to get entity embeddings,
            score all candidate triples using embeddings + rules.
    M-step: Update GNN weights and rule weights
            using the scoring as a differentiable loss.
    """
```

### Phase C: Advanced (2-3 months) — Multi-Agent + End-to-End

#### C1: Multi-Agent Architecture

**Files to change**:
- `backend/agents/graph.py` — refactor from single-agent to multi-agent topology

**Architecture** (per your MAGRL proposal):
```
Orchestrator Agent
    |-- Extractor Agent (GNN-guided extraction)
    |-- Reasoner Agent (GNN + rules)
    |-- Enricher Agent (Polanyi heuristics)
    +-- Query Planner Agent (NL -> structured queries)
```

Each agent has:
- Its own GNN context (entity embeddings relevant to its specialty)
- Message-passing with other agents (following MAGNet's approach)
- Ontology constraints (which entity types it can handle)

#### C2: End-to-End Differentiable Pipeline

Make the extraction -> reasoning -> enrichment pipeline differentiable:
- Extraction quality metrics (entity F1, relation F1) backpropagate to improve extraction prompt strategy
- Reasoning accuracy (verified vs. derived facts) updates rule weights and GNN parameters
- Enrichment confidence calibration improves via human approval feedback

#### C3: Temporal Reasoning Engine

Extend the bi-temporal data model with reasoning:
- Temporal constraint propagation: "If A was true during period X, and A->B implies B, then B was also true during period X"
- Temporal conflict detection: "A says X was CEO in 2020, B says Y was CEO in 2020"
- History-aware queries: "What was the state of this entity as of date D?"

### Phase D: Publication-Ready (3-4 months)

#### D1: Full Benchmark Suite
- FB15K-237, WN18RR, Kinship, NELL-995
- Standard metrics: MRR, Hits@1/3/10
- Ablation studies: GNN alone, rules alone, GNN+rules, GNN+rules+enrichment

#### D2: Comparison Against Surveyed Tools
- ExpressGNN baseline numbers (from their paper)
- RNNLogic baseline numbers
- NeuralLP baseline numbers

#### D3: Paper-Ready Results
- Show the contribution of each component
- Demonstrate domain-agnosticism by running on multiple ontology domains
- Show Polanyi enrichment adds value beyond what GNN+rules achieve

---

## 4. Benchmark Baseline

### ExpressGNN Published Results (FB15K-237)

| Method | MRR | Hits@1 | Hits@3 | Hits@10 |
|---|---|---|---|---|
| TransE | 0.261 | 0.168 | 0.286 | 0.449 |
| NeuralLP | 0.262 | 0.172 | 0.293 | 0.444 |
| MINERVA | 0.293 | 0.201 | 0.322 | 0.480 |
| ExpressGNN-E | 0.336 | 0.248 | 0.368 | 0.517 |
| ExpressGNN-EM | 0.357 | 0.267 | 0.388 | 0.536 |

**Target**: Match or exceed ExpressGNN-EM's MRR of 0.357 on FB15K-237.

### Current Project Baseline (no GNN, no learned rules)

Not directly comparable (different task framing), but the reasoning engine currently:
- Produces deterministic facts with hand-tuned weights
- Has no link prediction capability
- Cannot rank candidate triples
- Has no MRR/Hits@k evaluation

---

## 5. Architectural Decisions

### D1: PyTorch Geometric over DGL

**Decision**: Use PyTorch Geometric (PyG).
**Rationale**: ExpressGNN, walking-rdf-and-owl, and most surveyed tools use PyG or have PyG ports. The NeSymGraphs organization has PyG-compatible repos. Better documentation and community.

### D2: Embedding Architecture — R-GCN over Vanilla GCN

**Decision**: Use Relational GCN (R-GCN) as the base GNN.
**Rationale**: The KG is multi-relational (different edge types). R-GCN has separate weight matrices per relation type, which is essential for capturing the semantics of different relationships. ExpressGNN uses a similar relation-aware architecture.

### D3: Feature Initialization — Use Existing NVIDIA Embeddings

**Decision**: Initialize GNN node features from the existing 1024-dim `summaryEmbedding` vectors already stored on `:Entity` nodes.
**Rationale**: These embeddings already capture semantic meaning from the entity summaries. Starting from them (rather than random initialization) gives the GNN a meaningful starting point and leverages work already done.

### D4: Training Signal — Human Approval as Ground Truth

**Decision**: Use human approval/rejection of `:ImplicitFact` nodes as training signal for rule weights and GNN parameters.
**Rationale**: The project already has a human-in-the-loop approval workflow for enrichment. Approved facts are positive examples; rejected facts are negative examples. This is a natural, already-built supervision signal.

### D5: Benchmark Approach — FB15K-237 First

**Decision**: Start benchmarking with FB15K-237.
**Rationale**: Most commonly used benchmark in the survey. ExpressGNN's published results are on this dataset. It's small enough (272K triples) to train on a single GPU in reasonable time.

### D6: Rule Mining — Start with Path Mining, Not NeuralLP

**Decision**: Start with simple path mining (AMIE-style) rather than full NeuralLP differentiable rule discovery.
**Rationale**: Path mining is simpler to implement, easier to debug, and produces interpretable rules. The output can be fed into the existing rule format. NeuralLP's differentiable approach can be added later for refinement.

---

## Priority Summary

| Priority | Phase | Impact | Effort | Dependencies |
|---|---|---|---|---|
| 1 | A1-A2: GNN Embeddings | HIGH | 1-2 weeks | PyG install, GPU access |
| 2 | A4-A5: Benchmark Evaluation | HIGH | 1 week | A1 (PyG for evaluation) |
| 3 | B1: Learnable Rule Weights | MEDIUM | 3-5 days | A2 (GNN for feature extraction) |
| 4 | B3: Probabilistic Rule Scoring | MEDIUM | 3-5 days | B1 |
| 5 | B2: Rule Mining | MEDIUM | 1-2 weeks | B1 |
| 6 | C1: Multi-Agent | MEDIUM | 2-3 weeks | A2, B1 |
| 7 | C2: End-to-End Training | HIGH | 2-3 weeks | A2, B1, B2 |
| 8 | D1-D3: Publication | HIGH | 2-3 weeks | All above |

---

## Files That Need to Change (Summary)

### New Files
| File | Purpose |
|---|---|
| `backend/reasoning/gnn_embeddings.py` | GNN module for entity/relation embeddings |
| `backend/reasoning/rule_miner.py` | Automatic rule discovery from graph structure |
| `backend/reasoning/train.py` | Training loop for GNN + rule weights |
| `backend/benchmark/evaluate.py` | Standard benchmark evaluation harness |
| `backend/data/benchmarks/fb15k237/` | FB15K-237 dataset splits |
| `backend/tests/test_gnn.py` | GNN module tests |
| `backend/tests/test_benchmark.py` | Benchmark evaluation tests |
| `backend/tests/test_rule_miner.py` | Rule mining tests |

### Modified Files
| File | Change |
|---|---|
| `backend/reasoning/engine.py` | Probabilistic scoring, learned weights, GNN-derived parameters |
| `backend/services/reasoning_service.py` | Load GNN, compute embeddings before spreading |
| `backend/services/ingest_service.py` | Optionally run GNN after ingestion |
| `backend/reasoning/rules_repo.py` | Support learnable weights, rule persistence format |
| `backend/agents/graph.py` | Multi-agent topology (Phase C) |
| `backend/pyproject.toml` | Add torch, torch-geometric dependencies |
| `backend/config.py` | GNN model path, training hyperparameters |
| `backend/dependencies.py` | GNN model singleton provider |
| `evals/cases/` | Add benchmark-style eval cases |

### Unchanged Files
All enrichment heuristics, MCP servers, frontend components, query engine, path engine, and ontology loading remain unchanged. The GNN layer is additive — it provides learned parameters to the existing reasoning engine without replacing it.

---

## Key Architectural Insight from the Literature

The survey makes clear that **the most powerful neurosymbolic systems are those where the neural and symbolic components are tightly coupled in a feedback loop** — not just "run neural, then run symbolic." Your current system has the feedback loop for reasoning (spread -> infer -> feedback), but it doesn't extend to extraction or enrichment. The tools that perform best (ExpressGNN, RNNLogic, IterE) all have the symbolic results feeding back to improve the neural component, and vice versa.

Your unique strengths — the dual-graph ontology architecture, the 11 Polanyi heuristics, the domain-agnostic vocabulary swap — are **not present in any surveyed tool**. These are genuine differentiators. The gaps are in the neural/learned components that the rest of the field uses as a matter of course.
