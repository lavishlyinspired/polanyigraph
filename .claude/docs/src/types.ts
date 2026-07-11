export type NodeKind = 'Entity' | 'Concept' | 'Class' | 'Property' | 'Literal';

export interface GraphNode {
  id: string;
  label: string;
  kind: NodeKind;
  x: number;
  y: number;
  activation: number;
  depth: number;
  note: string;
  derived: boolean;
  derivedFrom?: string[];
  derivedRuleName?: string;
  proofPath?: ProofStep[];
  properties: Record<string, string>;
  salience: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  weight: number;
  symmetric?: boolean;
  transitive?: boolean;
  inverseOf?: string;
  derived?: boolean;
}

export interface Rule {
  id: string;
  name: string;
  sourceKind: NodeKind;
  edgeLabel: string;
  targetKind: NodeKind;
  threshold: number;
  description: string;
}

export interface ProofStep {
  step: number;
  ruleName: string;
  edgeLabel: string;
  sourceLabel: string;
  targetLabel: string;
  sourceActivation: number;
  threshold: number;
  iteration: number;
}

export interface DerivedFact {
  id: string;
  ruleId: string;
  ruleName: string;
  sourceId: string;
  sourceLabel: string;
  targetId: string;
  targetLabel: string;
  fact: string;
  confidence: number;
  fedBack: boolean;
  iteration: number;
  edgeLabel: string;
  proofPath: ProofStep[];
}

export interface ActivationResult {
  sourceId: string;
  sourceLabel: string;
  ranked: { nodeId: string; nodeLabel: string; activation: number; depth: number }[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface InferenceTraceEntry {
  iteration: number;
  ruleName: string;
  edgeLabel: string;
  sourceLabel: string;
  targetLabel: string;
  sourceActivation: number;
  threshold: number;
  fired: boolean;
  factId?: string;
  proofPath?: ProofStep[];
}

export interface QueryResult {
  query: string;
  results: { subject: string; predicate: string; object: string; derived: boolean; confidence: number }[];
  error?: string;
}

export interface PathResult {
  found: boolean;
  path: string[];
  edges: { source: string; target: string; label: string }[];
  proof: string;
  error?: string;
}

export type LoopStep = 'idle' | 'neural' | 'symbolic' | 'feedback' | 'complete';