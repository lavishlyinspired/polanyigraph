import type { GraphNode, GraphEdge, Rule, NodeKind } from '../types';

export const NODE_KINDS: NodeKind[] = ['Entity', 'Concept', 'Class', 'Property', 'Literal'];

export const KIND_COLORS: Record<NodeKind, string> = {
  Entity: '#fbbf24',
  Concept: '#34d399',
  Class: '#a78bfa',
  Property: '#fb7185',
  Literal: '#38bdf8',
};

export const KIND_BG: Record<NodeKind, string> = {
  Entity: 'bg-amber-400',
  Concept: 'bg-emerald-400',
  Class: 'bg-violet-400',
  Property: 'bg-rose-400',
  Literal: 'bg-sky-400',
};

export const KIND_TEXT: Record<NodeKind, string> = {
  Entity: 'text-amber-400',
  Concept: 'text-emerald-400',
  Class: 'text-violet-400',
  Property: 'text-rose-400',
  Literal: 'text-sky-400',
};

export const KIND_BORDER: Record<NodeKind, string> = {
  Entity: 'border-amber-400',
  Concept: 'border-emerald-400',
  Class: 'border-violet-400',
  Property: 'border-rose-400',
  Literal: 'border-sky-400',
};

export const EDGE_LABELS = [
  'subClassOf',
  'type',
  'relatedTo',
  'partOf',
  'dependsOn',
  'hasProperty',
  'equivalentTo',
  'derivesFrom',
  'influences',
  'contains',
];

export const DEFAULT_NODES: GraphNode[] = [
  { id: 'n1', label: 'System', kind: 'Concept', x: 400, y: 80, activation: 0, depth: -1, note: 'Root system concept.', derived: false, properties: { version: '1.0' }, salience: 1.0 },
  { id: 'n2', label: 'Module A', kind: 'Concept', x: 200, y: 200, activation: 0, depth: -1, note: 'Core module.', derived: false, properties: {}, salience: 1.0 },
  { id: 'n3', label: 'Module B', kind: 'Concept', x: 600, y: 200, activation: 0, depth: -1, note: 'Secondary module.', derived: false, properties: {}, salience: 1.0 },
  { id: 'n4', label: 'Component 1', kind: 'Entity', x: 100, y: 350, activation: 0, depth: -1, note: 'Implementation unit.', derived: false, properties: { status: 'active' }, salience: 1.2 },
  { id: 'n5', label: 'Component 2', kind: 'Entity', x: 300, y: 350, activation: 0, depth: -1, note: 'Implementation unit.', derived: false, properties: { status: 'active' }, salience: 1.0 },
  { id: 'n6', label: 'Component 3', kind: 'Entity', x: 500, y: 350, activation: 0, depth: -1, note: 'Implementation unit.', derived: false, properties: { status: 'beta' }, salience: 0.9 },
  { id: 'n7', label: 'Component 4', kind: 'Entity', x: 700, y: 350, activation: 0, depth: -1, note: 'Implementation unit.', derived: false, properties: { status: 'active' }, salience: 1.1 },
  { id: 'n8', label: 'Reliability', kind: 'Property', x: 200, y: 480, activation: 0, depth: -1, note: 'Quality attribute.', derived: false, properties: {}, salience: 1.0 },
  { id: 'n9', label: 'Performance', kind: 'Property', x: 600, y: 480, activation: 0, depth: -1, note: 'Quality attribute.', derived: false, properties: {}, salience: 1.0 },
];

export const DEFAULT_EDGES: GraphEdge[] = [
  { id: 'e1', source: 'n2', target: 'n1', label: 'partOf', weight: 1 },
  { id: 'e2', source: 'n3', target: 'n1', label: 'partOf', weight: 1 },
  { id: 'e3', source: 'n4', target: 'n2', label: 'partOf', weight: 1 },
  { id: 'e4', source: 'n5', target: 'n2', label: 'partOf', weight: 1 },
  { id: 'e5', source: 'n6', target: 'n3', label: 'partOf', weight: 1 },
  { id: 'e6', source: 'n7', target: 'n3', label: 'partOf', weight: 1 },
  { id: 'e7', source: 'n4', target: 'n5', label: 'dependsOn', weight: 1 },
  { id: 'e8', source: 'n6', target: 'n7', label: 'dependsOn', weight: 1 },
  { id: 'e9', source: 'n4', target: 'n8', label: 'hasProperty', weight: 1 },
  { id: 'e10', source: 'n7', target: 'n9', label: 'hasProperty', weight: 1 },
  { id: 'e11', source: 'n2', target: 'n3', label: 'relatedTo', weight: 1 },
  { id: 'e12', source: 'n8', target: 'n9', label: 'relatedTo', weight: 1, symmetric: true },
];

export const DEFAULT_RULES: Rule[] = [
  { id: 'r1', name: 'Transitive Dependency', sourceKind: 'Entity', edgeLabel: 'dependsOn', targetKind: 'Entity', threshold: 0.15, description: '{source} transitively depends on {target}.' },
  { id: 'r2', name: 'Inherited Property', sourceKind: 'Entity', edgeLabel: 'hasProperty', targetKind: 'Property', threshold: 0.1, description: '{source} inherits property {target}.' },
  { id: 'r3', name: 'Related Concepts', sourceKind: 'Concept', edgeLabel: 'relatedTo', targetKind: 'Concept', threshold: 0.1, description: '{source} is related to {target}.' },
];