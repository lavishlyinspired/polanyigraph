# Neurosymbolic KG (domain-agnostic)

A domain-agnostic neurosymbolic knowledge-graph reasoning app. Ingest real
documents → extract an entity/relationship graph with a real LLM → reason over it
with a persistent-activation neurosymbolic loop → explore and query.

- **Ontology / symbolic layer** — Ontotext GraphDB (RDF/OWL/SPARQL). The loaded
  repository defines the type vocabulary; swap it to swap domains. No domain is
  hardcoded.
- **Instance / neural layer** — Neo4j (property graph): extracted instances,
  spread-activation reasoning, visualization, agent checkpointing.
- **LLM** — OpenAI-compatible; NVIDIA-hosted GLM (`z-ai/glm-5.2`) by default,
  configurable to any compatible provider.

## Layout
```
backend/    FastAPI + reasoning engine + ontology loader + LLM client + tests
frontend/   React + Vite + Tailwind (ported from the prototype, rewired to the API)
docs/       PLAN.md, MVP_PLAN.md, reference papers, original prototype (docs/src)
.claude/    project skills for the coding agent
```

## Prerequisites (local desktop)
- **Neo4j Desktop** running on `bolt://localhost:7687`.
- **Ontotext GraphDB** running on `http://localhost:7200` with a repository loaded
  (default `fibo`).
- An LLM API key (NVIDIA by default).

## Run
```bash
cp .env.example .env      # fill in credentials
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000/health

cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

## Test
```bash
cd backend && .venv/bin/pytest        # reasoning engine tests pass without any DB
```

See `docs/MVP_PLAN.md` for the vertical slice and acceptance criteria, and
`docs/PLAN.md` §8.4 for the reasoning-loop correctness spec.
# polanyigraph
