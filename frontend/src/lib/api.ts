// Backend API client. Replaces the prototype's mock llm.ts and fibo-data.ts:
// all data here comes from the real backend (Neo4j instances + reasoning),
// never from a seeded demo graph. Wire contract is camelCase throughout,
// matching backend/app/schemas.py's ApiModel (alias_generator=to_camel).

export interface ApiNode {
  id: string;
  label: string;
  type: string;
  activation?: number;
  derived?: boolean;
  sourceDoc?: string;
  salience?: number;
  properties?: Record<string, string>;
  note?: string;
  communityId?: number | null;
}

export interface ApiEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight?: number;
}

export interface GraphResponse {
  nodes: ApiNode[];
  edges: ApiEdge[];
}

export interface IngestResponse extends GraphResponse {
  dropped: string[];
}

export interface DerivedFact {
  id: string;
  fact: string;
  confidence: number;
  iteration: number;
  sourceId: string;
  targetId: string;
  ruleName: string;
  proofPath: ProofStep[];
}

export interface ProofStep {
  ruleName: string;
  edgeType: string;
  sourceLabel: string;
  targetLabel: string;
  premiseActivation: number;
  iteration: number;
  // Set when the rule fired via ontology-aware subclass matching rather than
  // an exact type match, e.g. '"commercial bank" is-a "organization"'.
  typeResolution: string | null;
}

export interface ReasonResponse {
  activation: Record<string, number>;
  facts: DerivedFact[];
  iterations: number;
  convergedBy: 'fixpoint' | 'max_iterations';
}

export interface QueryResultRow {
  subject: string;
  predicate: string;
  object: string;
  derived: boolean;
  confidence: number;
}

export interface QueryResponse {
  query: string;
  results: QueryResultRow[];
  error: string | null;
}

export interface PathEdge {
  source: string;
  target: string;
  label: string;
}

export interface PathResponse {
  found: boolean;
  path: string[];
  edges: PathEdge[];
  proof: string;
  error: string | null;
}

export interface Triple {
  subject: string;
  predicate: string;
  object: string;
  derived: boolean;
  confidence: number;
}

export interface TriplesResponse {
  triples: Triple[];
  total: number;
}

export interface OntologyClassItem {
  label: string;
  uri: string;
  comment: string | null;
}

export interface OntologyPropertyItem {
  label: string;
  uri: string;
  domain: string | null;
  range: string | null;
}

export interface SubclassRelation {
  child: string;
  parent: string;
}

export interface OntologySchemaResponse {
  classLabels: string[];
  propertyLabels: string[];
  classes: OntologyClassItem[];
  properties: OntologyPropertyItem[];
  subclassOf: SubclassRelation[];
  classCount: number;
  propertyCount: number;
}

export interface IngestEvent {
  id: string;
  text: string;
  entityCount: number;
  relationshipCount: number;
  droppedCount: number;
  createdAt: string;
}

export interface HistoryResponse {
  events: IngestEvent[];
}

export interface Rule {
  id: string;
  name: string;
  edgeType: string;
  sourceType: string;
  targetType: string;
  threshold: number;
  weight: number;
  description: string;
  source: 'seed' | 'custom';
}

export interface RulesResponse {
  rules: Rule[];
}

export interface GraphSummary {
  graphId: string;
  nodeCount: number;
  edgeCount: number;
  lastIngestAt: string | null;
}

export interface GraphsResponse {
  graphs: GraphSummary[];
}

export interface ChatResponse {
  reply: string;
}

// Polanyi enrichment (PLAN.md §19): implicit facts inferred by 11 fixed
// cognitive/pragmatic heuristics, kept separate from ontology-typed entities
// and rule-derived facts. Pending until a human approves or rejects them.
export type HeuristicType =
  | 'presupposition'
  | 'conversational_implicature'
  | 'factual_impact'
  | 'image_schema'
  | 'metonymic_coercion'
  | 'moral_value_coercion'
  | 'symbolic_coercion'
  | 'event_sequence'
  | 'causal_relation'
  | 'implied_future_event'
  | 'implied_non_event';

export interface ImplicitFact {
  id: string;
  heuristicType: HeuristicType;
  text: string;
  confidence: number;
  status: 'pending' | 'approved' | 'rejected';
  anchorEntityIds: string[];
}

export interface ImplicitFactListResponse {
  facts: ImplicitFact[];
}

// Community detection (PLAN.md §20 item 5, Neo4j GDS Louvain).
export interface CommunityMember {
  entityId: string;
  label: string;
  communityId: number;
}

export interface CommunitiesResponse {
  members: CommunityMember[];
}

// LangGraph agent (MVP_PLAN.md Phase 6, PLAN.md §8): one message in, the
// agent classifies intent (extract/enrich/query/reason/visualize) and does
// real work -- unlike /chat, this can mutate the graph.
export type AgentIntent = 'extract' | 'enrich' | 'query' | 'reason' | 'visualize' | '';

export interface AgentResponse {
  reply: string;
  intent: AgentIntent;
  entitiesExtracted: number;
  relationshipsExtracted: number;
  factsDerived: number;
  enrichmentFactTexts: string[];
  queryResults: string[];
  queryError: string;
}

export interface HealthResponse {
  status: string;
  profile: string;
  ontologyRepository: string;
  neo4j: { ok: boolean; error?: string };
  graphdb: { ok: boolean; error?: string };
  llm: { ok: boolean; model: string; error?: string };
}

const BASE = '/api';

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}${body ? `: ${body}` : ''}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch(`${BASE}/health`).then(json<HealthResponse>),

  ingestText: (graphId: string, text: string) =>
    fetch(`${BASE}/ingest`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ graphId, source: { type: 'text', text } }),
    }).then(json<IngestResponse>),

  getGraph: (graphId: string) => fetch(`${BASE}/graph/${graphId}`).then(json<GraphResponse>),

  reason: (graphId: string, sourceId?: string) =>
    fetch(`${BASE}/reason/${graphId}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ sourceId: sourceId ?? null }),
    }).then(json<ReasonResponse>),

  query: (graphId: string, query: string) =>
    fetch(`${BASE}/query/${graphId}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ query }),
    }).then(json<QueryResponse>),

  findPath: (graphId: string, source: string, target: string) =>
    fetch(`${BASE}/query/${graphId}/path`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ source, target }),
    }).then(json<PathResponse>),

  getTriples: (graphId: string) =>
    fetch(`${BASE}/query/${graphId}/triples`).then(json<TriplesResponse>),

  getHistory: (graphId: string) => fetch(`${BASE}/history/${graphId}`).then(json<HistoryResponse>),

  getRules: () => fetch(`${BASE}/rules`).then(json<RulesResponse>),

  getGraphs: () => fetch(`${BASE}/graphs`).then(json<GraphsResponse>),

  chat: (graphId: string, message: string) =>
    fetch(`${BASE}/chat/${graphId}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ message }),
    }).then(json<ChatResponse>),

  getOntology: () => fetch(`${BASE}/ontology`).then(json<OntologySchemaResponse>),

  addNode: (graphId: string, label: string, type: string) =>
    fetch(`${BASE}/graph/${graphId}/nodes`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ label, type }),
    }).then(json<ApiNode>),

  addEdge: (graphId: string, sourceId: string, targetId: string, type: string) =>
    fetch(`${BASE}/graph/${graphId}/edges`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ sourceId, targetId, type }),
    }).then(json<ApiEdge>),

  updateNode: (graphId: string, nodeId: string, patch: { salience?: number; properties?: Record<string, string>; note?: string }) =>
    fetch(`${BASE}/graph/${graphId}/nodes/${nodeId}`, {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(patch),
    }).then(json<ApiNode>),

  createRule: (rule: { name: string; edgeType: string; sourceType: string; targetType: string; threshold: number; weight?: number; description?: string }) =>
    fetch(`${BASE}/rules`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(rule),
    }).then(json<Rule>),

  deleteRule: (ruleId: string) => fetch(`${BASE}/rules/${ruleId}`, { method: 'DELETE' }).then(json<{ deleted: boolean }>),

  enrich: (graphId: string, text: string) =>
    fetch(`${BASE}/enrich/${graphId}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text }),
    }).then(json<ImplicitFactListResponse>),

  getPendingFacts: (graphId: string) => fetch(`${BASE}/enrich/${graphId}/pending`).then(json<ImplicitFactListResponse>),

  getApprovedFacts: (graphId: string) => fetch(`${BASE}/enrich/${graphId}/approved`).then(json<ImplicitFactListResponse>),

  approveFact: (graphId: string, factId: string) =>
    fetch(`${BASE}/enrich/${graphId}/${factId}/approve`, { method: 'POST' }).then(json<ImplicitFactListResponse>),

  rejectFact: (graphId: string, factId: string) =>
    fetch(`${BASE}/enrich/${graphId}/${factId}/reject`, { method: 'POST' }).then(json<ImplicitFactListResponse>),

  detectCommunities: (graphId: string) =>
    fetch(`${BASE}/graph/${graphId}/communities`, { method: 'POST' }).then(json<CommunitiesResponse>),

  getCommunities: (graphId: string) => fetch(`${BASE}/graph/${graphId}/communities`).then(json<CommunitiesResponse>),

  runAgent: (graphId: string, text: string, sessionId?: string) =>
    fetch(`${BASE}/agent/${graphId}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text, sessionId: sessionId ?? null }),
    }).then(json<AgentResponse>),
};
