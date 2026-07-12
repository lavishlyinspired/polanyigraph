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
  fedBack: boolean;
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

// Reason tab manual step-by-step mode (prototype parity, PLAN.md §16 Phase 9):
// Spread Activation / Run Inference / Feed Back as three separate real calls,
// each reading/writing real persisted Neo4j state -- not the prototype's
// client-side-only mock engine.
export interface TraceEntry {
  ruleName: string;
  edgeType: string;
  sourceLabel: string;
  targetLabel: string;
  sourceActivation: number;
  threshold: number;
  fired: boolean;
  iteration: number;
  skipReason: string | null;
  factId: string | null;
}

export interface SpreadResponse {
  activation: Record<string, number>;
}

export interface InferResponse {
  facts: DerivedFact[];
  trace: TraceEntry[];
}

export interface FeedbackResponse {
  activation: Record<string, number>;
}

export interface FactsListResponse {
  facts: DerivedFact[];
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

// Runtime skills (PLAN.md §13.2): the real Discovery/Activation skill store
// backend/agents/skill_store.py loads at inference time, plus real persisted
// "active" state (services/skill_activation_store.py) -- same data mcp_skills_server.py
// exposes to MCP clients, surfaced here for the SkillManager UI tab.
export interface SkillItem {
  name: string;
  description: string;
  active: boolean;
}

export interface SkillsResponse {
  skills: SkillItem[];
}

export interface SkillContentResponse {
  name: string;
  content: string;
}

// Cross-source memory search + preferences (PLAN.md §9): real chat history
// and entity-summary search (services/memory_service.py) plus a real
// key/value preferences store (services/preferences_store.py) -- same data
// mcp_memory_server.py exposes to MCP clients, surfaced here for MemoryInspector.
export type MemoryHitKind = 'chat_message' | 'entity_summary';

export interface MemoryHit {
  kind: MemoryHitKind;
  id: string;
  text: string;
  createdAt: string | null;
}

export interface MemorySearchResponse {
  hits: MemoryHit[];
}

export interface Preference {
  key: string;
  value: string;
}

export interface PreferencesResponse {
  preferences: Preference[];
}

export interface HealthResponse {
  status: string;
  profile: string;
  ontologyRepository: string;
  neo4j: { ok: boolean; error?: string };
  graphdb: { ok: boolean; error?: string };
  llm: { ok: boolean; model: string; error?: string };
}

// GET /settings/connections -- real, non-secret connection info for the
// Connection Center. Never includes passwords/API keys.
export interface ConnectionsResponse {
  profile: string;
  neo4j: { uri: string; database: string };
  graphdb: { baseUrl: string; repository: string };
  llm: { baseUrl: string; model: string };
  reasoning: { decay: number; epsilon: number; maxIterations: number; activationFloor: number; feedbackGain: number };
  provisionedNotWired: string[];
}

// GET/PUT /settings/memory-backend -- runtime memory-backend selection
// (GRAPHITI_INTEGRATION_PLAN.md §4). Never includes passwords/API keys.
export type MemoryBackend = 'native' | 'graphiti';

export interface MemoryBackendStatus {
  backend: MemoryBackend;
  graphitiConfigured: boolean;
  graphitiNeo4jUri: string;
  graphitiNeo4jDatabase: string;
  embeddingConfigured: boolean;
  embeddingBaseUrl: string;
  embeddingModel: string;
}

export interface ConnectionTestResult {
  ok: boolean;
  error: string | null;
  status: MemoryBackendStatus;
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

  getConnections: () => fetch(`${BASE}/settings/connections`).then(json<ConnectionsResponse>),

  getMemoryBackend: () => fetch(`${BASE}/settings/memory-backend`).then(json<MemoryBackendStatus>),

  setMemoryBackend: (backend: MemoryBackend) =>
    fetch(`${BASE}/settings/memory-backend`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ backend }),
    }).then(json<MemoryBackendStatus>),

  setGraphitiConnection: (uri: string, user: string, password: string, database: string) =>
    fetch(`${BASE}/settings/memory-backend/graphiti-connection`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ uri, user, password, database }),
    }).then(json<ConnectionTestResult>),

  setEmbeddingOverride: (baseUrl: string, model: string, apiKey: string) =>
    fetch(`${BASE}/settings/memory-backend/embedding`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ baseUrl, model, apiKey }),
    }).then(json<ConnectionTestResult>),

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

  // SSE stream: invokes onChunk as each token arrives, resolves once the
  // server sends its terminal [DONE] event.
  chatStream: async (graphId: string, message: string, onChunk: (chunk: string) => void): Promise<void> => {
    const res = await fetch(`${BASE}/chat/${graphId}/stream`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    if (!res.ok || !res.body) {
      throw new Error(`chat stream failed: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split('\n\n');
      buffer = events.pop() ?? '';
      for (const event of events) {
        const text = event
          .split('\n')
          .map((line) => line.replace(/^data: ?/, ''))
          .join('\n');
        if (text === '[DONE]') return;
        onChunk(text);
      }
    }
  },

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

  spreadActivation: (graphId: string, sourceId?: string) =>
    fetch(`${BASE}/reason/${graphId}/spread`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ sourceId: sourceId ?? null }),
    }).then(json<SpreadResponse>),

  runInferenceStep: (graphId: string) =>
    fetch(`${BASE}/reason/${graphId}/infer`, { method: 'POST' }).then(json<InferResponse>),

  feedBack: (graphId: string) =>
    fetch(`${BASE}/reason/${graphId}/feedback`, { method: 'POST' }).then(json<FeedbackResponse>),

  getReasonFacts: (graphId: string) => fetch(`${BASE}/reason/${graphId}/facts`).then(json<FactsListResponse>),

  clearActivation: (graphId: string) => fetch(`${BASE}/reason/${graphId}/clear-activation`, { method: 'POST' }).then(json<{ cleared: boolean }>),

  clearFacts: (graphId: string) => fetch(`${BASE}/reason/${graphId}/clear-facts`, { method: 'POST' }).then(json<{ cleared: boolean }>),

  getSkills: () => fetch(`${BASE}/skills`).then(json<SkillsResponse>),

  getSkillContent: (name: string) => fetch(`${BASE}/skills/${name}/content`).then(json<SkillContentResponse>),

  activateSkill: (name: string) =>
    fetch(`${BASE}/skills/${name}/activate`, { method: 'POST' }).then(json<SkillItem>),

  searchMemory: (graphId: string, query: string) =>
    fetch(`${BASE}/memory/${graphId}/search`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ query }),
    }).then(json<MemorySearchResponse>),

  getPreferences: () => fetch(`${BASE}/memory/preferences`).then(json<PreferencesResponse>),

  savePreference: (key: string, value: string) =>
    fetch(`${BASE}/memory/preferences/${key}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ value }),
    }).then(json<Preference>),

  deletePreference: (key: string) =>
    fetch(`${BASE}/memory/preferences/${key}`, { method: 'DELETE' }).then(json<{ deleted: boolean }>),
};
