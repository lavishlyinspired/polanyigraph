# Plan: Add Major Neurosymbolic Graph OS Capabilities

## Context
The frontend app currently has working SPARQL-style pattern queries via the backend `execute_query()`. The reference prototype at `.claude/docs/src` has additional capabilities: path-finding with explainable proofs (`findPath()`), triple store view, and RDFS++ edge metadata. This plan adds these missing capabilities to the real backend + frontend.

## Changes

### 1. Backend: Add path-finding endpoint
**File**: `backend/services/path_engine.py` (new) + `backend/api/query.py` (extend)

Add a BFS path-finding algorithm (matching reference `findPath()` in `.claude/docs/src/lib/engine.ts:270-314`) that:
- Takes `sourceLabel`, `targetLabel`, graph nodes/edges
- Returns `PathResult`: `{ found, path: string[], edges: {source,target,label}[], proof: string, error? }`
- The `proof` string is the human-readable explainable path: `A →[edgeType]→ B →[edgeType]→ C`

Add `POST /query/{graph_id}/path` endpoint:
```python
class PathRequest(ApiModel):
    source: str
    target: str

class PathEdgeResponse(ApiModel):
    source: str
    target: str
    label: str

class PathResponse(ApiModel):
    found: bool
    path: list[str]
    edges: list[PathEdgeResponse]
    proof: str
    error: str | None = None
```

### 2. Backend: Add triples endpoint
**File**: `backend/api/query.py` (extend)

Add `GET /query/{graph_id}/triples` that returns all stored + derived triples:
```python
class TripleResponse(ApiModel):
    subject: str
    predicate: str
    object: str
    derived: bool
    confidence: float

class TriplesResponse(ApiModel):
    triples: list[TripleResponse]
    total: int
```

Uses existing `graph_service.load_triples()` + derived facts from reasoning.

### 3. Backend: Add ontology schema endpoint
**File**: `backend/api/ontology.py` (extend)

The existing `GET /ontology` returns only `classLabels` and `propertyLabels`. Extend to include subclass relationships:
```python
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
    child: str  # label
    parent: str  # label

class OntologySchemaResponse(ApiModel):
    classes: list[OntologyClassItem]
    properties: list[OntologyPropertyItem]
    subclass_of: list[SubclassRelation]
    class_count: int
    property_count: int
```

### 4. Frontend: Add path-finding API client
**File**: `frontend/src/lib/api.ts`

Add types and API function:
```typescript
export interface PathEdge { source: string; target: string; label: string; }
export interface PathResponse { found: boolean; path: string[]; edges: PathEdge[]; proof: string; error: string | null; }
export interface Triple { subject: string; predicate: string; object: string; derived: boolean; confidence: number; }
export interface TriplesResponse { triples: Triple[]; total: number; }
// ... etc
```

Add to `api`:
- `findPath(graphId, source, target)` → `POST /query/{graph_id}/path`
- `getTriples(graphId)` → `GET /query/{graph_id}/triples`
- `getOntologySchema()` → `GET /ontology` (extended)

### 5. Frontend: Enhance QueryPanel with path-finding
**File**: `frontend/src/components/QueryPanel.tsx`

Add a "Find Path" section below the query input:
- Two text inputs: Source label, Target label
- "Find Path" button
- Results showing: path chain with arrows, proof string, error state
- Reuse existing visual language (mono font, zinc/white palette, DERIVED badges)

### 6. Frontend: Add TripleStorePanel
**File**: `frontend/src/components/TripleStorePanel.tsx` (new)

New right sidebar tab showing all triples:
- Search/filter input
- Table-like list of (subject, predicate, object) triples
- Derived triples highlighted with amber badge
- Confidence shown as percentage
- Total count in header
- Uses `api.getTriples(graphId)`

### 7. Frontend: Add OntologyPanel
**File**: `frontend/src/components/OntologyPanel.tsx` (new)

New right sidebar tab showing ontology schema:
- Classes list with labels and URIs
- Properties list with domain/range
- Subclass relationships shown as tree or list
- Counts in header
- Uses `api.getOntologySchema()`

### 8. Frontend: Update sidebar tabs
**File**: `frontend/src/App.tsx`

Right sidebar tabs change from `[query, llm]` to `[query, triples, ontology, llm]`:
- `query` → QueryPanel (enhanced with path-finding)
- `triples` → TripleStorePanel (new)
- `ontology` → OntologyPanel (new)  
- `llm` → LlmPanel (existing)

Add icons: `Database` for triples, `BookOpen` for ontology.

## Files to modify
- `backend/services/path_engine.py` — new file
- `backend/api/query.py` — add path endpoint + triples endpoint
- `backend/api/ontology.py` — extend response schema
- `frontend/src/lib/api.ts` — add types + API calls
- `frontend/src/components/QueryPanel.tsx` — add path-finding UI
- `frontend/src/components/TripleStorePanel.tsx` — new file
- `frontend/src/components/OntologyPanel.tsx` — new file
- `frontend/src/App.tsx` — add new tabs + imports

## Verification
1. `cd /Users/akash/KG_Projects/neurosymbolic/backend && python -m pytest tests/ -x` — all existing tests pass
2. `cd /Users/akash/KG_Projects/neurosymbolic/frontend && npx tsc --noEmit` — TypeScript compiles
3. Manual: start backend + frontend, verify path-finding works with real graph data
4. Manual: verify triples tab shows all stored + derived triples
5. Manual: verify ontology tab shows classes, properties, subclass relationships
