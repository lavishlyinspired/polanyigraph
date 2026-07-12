import type { GraphNode, GraphEdge, Rule, DerivedFact, ActivationResult, InferenceTraceEntry, ProofStep, QueryResult, PathResult } from '../types';

export function spreadActivation(
  sourceId: string,
  nodes: GraphNode[],
  edges: GraphEdge[]
): { nodes: GraphNode[]; result: ActivationResult } {
  const updated = nodes.map((n) => ({ ...n, activation: 0, depth: -1 }));
  const source = updated.find((n) => n.id === sourceId);
  if (!source) return { nodes: updated, result: { sourceId, sourceLabel: 'Unknown', ranked: [] } };

  source.activation = 1.0;
  source.depth = 0;
  const visited = new Set<string>([sourceId]);
  const queue: { id: string; depth: number }[] = [{ id: sourceId, depth: 0 }];

  while (queue.length > 0) {
    const { id, depth } = queue.shift()!;
    const current = updated.find((n) => n.id === id);
    if (!current) continue;

    const outEdges = edges.filter((e) => e.source === id || e.target === id);
    for (const edge of outEdges) {
      const neighborId = edge.source === id ? edge.target : edge.source;
      if (visited.has(neighborId) && depth >= 4) continue;

      const neighbor = updated.find((n) => n.id === neighborId);
      if (!neighbor) continue;

      const decay = 0.45;
      const newActivation = current.activation * decay * (edge.weight || 1) * (neighbor.salience || 1);

      if (newActivation > neighbor.activation) {
        neighbor.activation = newActivation;
        neighbor.depth = depth + 1;
      }

      if (!visited.has(neighborId)) {
        visited.add(neighborId);
        queue.push({ id: neighborId, depth: depth + 1 });
      }
    }
  }

  const ranked = updated
    .filter((n) => n.activation > 0.01)
    .sort((a, b) => b.activation - a.activation)
    .map((n) => ({ nodeId: n.id, nodeLabel: n.label, activation: n.activation, depth: n.depth }));

  return { nodes: updated, result: { sourceId, sourceLabel: source.label, ranked } };
}

export function runInference(
  nodes: GraphNode[],
  edges: GraphEdge[],
  rules: Rule[],
  existingFactIds: string[] = [],
  iteration: number = 1
): { facts: DerivedFact[]; updatedNodes: GraphNode[]; trace: InferenceTraceEntry[] } {
  const facts: DerivedFact[] = [];
  const trace: InferenceTraceEntry[] = [];
  const updatedNodes = nodes.map((n) => ({ ...n }));

  for (const rule of rules) {
    for (const edge of edges) {
      if (edge.label !== rule.edgeLabel) continue;

      const sourceNode = updatedNodes.find((n) => n.id === edge.source);
      const targetNode = updatedNodes.find((n) => n.id === edge.target);
      if (!sourceNode || !targetNode) continue;

      if (sourceNode.kind !== rule.sourceKind) continue;
      if (targetNode.kind !== rule.targetKind) continue;

      const fired = sourceNode.activation >= rule.threshold;
      const factId = `fact-${rule.id}-${edge.id}`;

      const proofStep: ProofStep = {
        step: 1,
        ruleName: rule.name,
        edgeLabel: edge.label,
        sourceLabel: sourceNode.label,
        targetLabel: targetNode.label,
        sourceActivation: sourceNode.activation,
        threshold: rule.threshold,
        iteration,
      };

      trace.push({
        iteration,
        ruleName: rule.name,
        edgeLabel: edge.label,
        sourceLabel: sourceNode.label,
        targetLabel: targetNode.label,
        sourceActivation: sourceNode.activation,
        threshold: rule.threshold,
        fired,
        factId: fired ? factId : undefined,
        proofPath: [proofStep],
      });

      if (!fired) continue;
      if (existingFactIds.includes(factId)) continue;

      const proofPath: ProofStep[] = [];
      if (sourceNode.proofPath && sourceNode.proofPath.length > 0) {
        proofPath.push(...sourceNode.proofPath.map((s) => ({ ...s, step: s.step })));
      }
      proofPath.push({ ...proofStep, step: proofPath.length + 1 });

      const fact: DerivedFact = {
        id: factId,
        ruleId: rule.id,
        ruleName: rule.name,
        sourceId: sourceNode.id,
        sourceLabel: sourceNode.label,
        targetId: targetNode.id,
        targetLabel: targetNode.label,
        fact: rule.description.replace('{source}', sourceNode.label).replace('{target}', targetNode.label),
        confidence: sourceNode.activation,
        fedBack: false,
        iteration,
        edgeLabel: edge.label,
        proofPath,
      };

      facts.push(fact);
      targetNode.derived = true;
      targetNode.derivedFrom = [...(targetNode.derivedFrom || []), factId];
      targetNode.derivedRuleName = rule.name;
      targetNode.proofPath = proofPath;
    }
  }

  return { facts, updatedNodes, trace };
}

export function feedBackActivation(
  nodes: GraphNode[],
  facts: DerivedFact[]
): { nodes: GraphNode[]; updatedFacts: DerivedFact[] } {
  const updatedNodes = nodes.map((n) => ({ ...n }));
  const updatedFacts = facts.map((f) => ({ ...f }));

  for (const fact of updatedFacts) {
    if (fact.fedBack) continue;
    const target = updatedNodes.find((n) => n.id === fact.targetId);
    if (!target) continue;

    const boost = fact.confidence * 0.5;
    target.activation = Math.min(1, target.activation + boost);
    fact.fedBack = true;
  }

  return { nodes: updatedNodes, updatedFacts };
}

export function executeQuery(
  query: string,
  nodes: GraphNode[],
  edges: GraphEdge[],
  facts: DerivedFact[]
): QueryResult {
  const trimmed = query.trim();
  if (!trimmed) return { query, results: [], error: 'Empty query.' };

  const parts = trimmed.split(',').map((p) => p.trim()).filter(Boolean);
  const parsed = parts.map((part) => {
    const m = part.match(/^(\w+)\s*\(\s*(?:"([^"]*)"|(\w+))\s*,\s*(?:"([^"]*)"|(\w+))\s*\)$/);
    if (!m) return null;
    return {
      predicate: m[1],
      subjectLiteral: m[2] || null,
      subjectVar: m[3] || null,
      objectLiteral: m[4] || null,
      objectVar: m[5] || null,
    };
  });

  if (parsed.some((p) => p === null)) {
    return {
      query,
      results: [],
      error: 'Invalid syntax. Use: predicate(subject, object) — e.g., partOf("Module A", X)',
    };
  }

  const allTriples: { subject: string; predicate: string; object: string; derived: boolean; confidence: number }[] = [];

  for (const edge of edges) {
    const sourceNode = nodes.find((n) => n.id === edge.source);
    const targetNode = nodes.find((n) => n.id === edge.target);
    if (!sourceNode || !targetNode) continue;
    allTriples.push({ subject: sourceNode.label, predicate: edge.label, object: targetNode.label, derived: false, confidence: 1.0 });
  }

  for (const fact of facts) {
    allTriples.push({ subject: fact.sourceLabel, predicate: fact.edgeLabel, object: fact.targetLabel, derived: true, confidence: fact.confidence });
  }

  if (parsed.length === 1) {
    const p = parsed[0]!;
    const results: QueryResult['results'] = [];
    for (const triple of allTriples) {
      if (triple.predicate !== p.predicate) continue;
      let subjectMatch = true;
      let objectMatch = true;
      if (p.subjectLiteral) subjectMatch = triple.subject.toLowerCase() === p.subjectLiteral.toLowerCase();
      else if (p.subjectVar && !['X', 'Y', 'Z', '_'].includes(p.subjectVar.toUpperCase())) subjectMatch = triple.subject.toLowerCase() === p.subjectVar.toLowerCase();
      if (p.objectLiteral) objectMatch = triple.object.toLowerCase() === p.objectLiteral.toLowerCase();
      else if (p.objectVar && !['X', 'Y', 'Z', '_'].includes(p.objectVar.toUpperCase())) objectMatch = triple.object.toLowerCase() === p.objectVar.toLowerCase();
      if (subjectMatch && objectMatch) {
        if (!results.some((r) => r.subject === triple.subject && r.object === triple.object && r.derived === triple.derived)) {
          results.push({ subject: triple.subject, predicate: triple.predicate, object: triple.object, derived: triple.derived, confidence: triple.confidence });
        }
      }
    }
    return { query, results };
  }

  const results: QueryResult['results'] = [];
  const bindings: Record<string, string>[] = [{}];

  for (const atom of parsed) {
    const newBindings: Record<string, string>[] = [];
    for (const binding of bindings) {
      for (const triple of allTriples) {
        if (triple.predicate !== atom!.predicate) continue;

        const subjectVal = atom!.subjectLiteral ?? (atom!.subjectVar && ['X', 'Y', 'Z', '_'].includes(atom!.subjectVar.toUpperCase()) ? (binding[atom!.subjectVar] ?? null) : atom!.subjectVar);
        const objectVal = atom!.objectLiteral ?? (atom!.objectVar && ['X', 'Y', 'Z', '_'].includes(atom!.objectVar.toUpperCase()) ? (binding[atom!.objectVar] ?? null) : atom!.objectVar);

        let subjectMatch = false;
        if (subjectVal === null) subjectMatch = true;
        else if (typeof subjectVal === 'string') subjectMatch = triple.subject.toLowerCase() === subjectVal.toLowerCase();

        let objectMatch = false;
        if (objectVal === null) objectMatch = true;
        else if (typeof objectVal === 'string') objectMatch = triple.object.toLowerCase() === objectVal.toLowerCase();

        if (subjectMatch && objectMatch) {
          const newBinding = { ...binding };
          if (atom!.subjectVar && ['X', 'Y', 'Z', '_'].includes(atom!.subjectVar.toUpperCase()) && !binding[atom!.subjectVar]) {
            newBinding[atom!.subjectVar] = triple.subject;
          }
          if (atom!.objectVar && ['X', 'Y', 'Z', '_'].includes(atom!.objectVar.toUpperCase()) && !binding[atom!.objectVar]) {
            newBinding[atom!.objectVar] = triple.object;
          }
          newBindings.push(newBinding);
        }
      }
    }
    bindings.length = 0;
    bindings.push(...newBindings);
    if (newBindings.length === 0) break;
  }

  for (const binding of bindings) {
    const subject = binding[parsed[0]!.subjectVar] ?? parsed[0]!.subjectLiteral ?? '';
    const object = binding[parsed[0]!.objectVar] ?? parsed[0]!.objectLiteral ?? '';
    const existing = allTriples.find((t) => t.subject === subject && t.predicate === parsed[0]!.predicate && t.object === object);
    if (subject && object) {
      results.push({ subject, predicate: parsed[0]!.predicate, object, derived: existing?.derived ?? false, confidence: existing?.confidence ?? 1.0 });
    }
  }

  return { query, results };
}

export function findPath(
  sourceLabel: string,
  targetLabel: string,
  nodes: GraphNode[],
  edges: GraphEdge[]
): PathResult {
  const source = nodes.find((n) => n.label.toLowerCase() === sourceLabel.toLowerCase());
  const target = nodes.find((n) => n.label.toLowerCase() === targetLabel.toLowerCase());

  if (!source) return { found: false, path: [], edges: [], proof: '', error: `Node "${sourceLabel}" not found.` };
  if (!target) return { found: false, path: [], edges: [], proof: '', error: `Node "${targetLabel}" not found.` };
  if (source.id === target.id) return { found: true, path: [source.label], edges: [], proof: 'Source and target are the same node.' };

  const queue: { id: string; path: string[]; edges: { source: string; target: string; label: string }[] }[] = [
    { id: source.id, path: [source.label], edges: [] },
  ];
  const visited = new Set<string>([source.id]);

  while (queue.length > 0) {
    const { id, path, edges: pathEdges } = queue.shift()!;
    if (id === target.id) {
      const proof = path.map((label, i) => {
        if (i === 0) return label;
        const edge = pathEdges[i - 1];
        return ` →[${edge.label}]→ ${label}`;
      }).join('');
      return { found: true, path, edges: pathEdges, proof };
    }

    const outEdges = edges.filter((e) => e.source === id || e.target === id);
    for (const edge of outEdges) {
      const neighborId = edge.source === id ? edge.target : edge.source;
      if (visited.has(neighborId)) continue;
      visited.add(neighborId);
      const neighbor = nodes.find((n) => n.id === neighborId);
      if (!neighbor) continue;
      queue.push({
        id: neighborId,
        path: [...path, neighbor.label],
        edges: [...pathEdges, { source: id, target: neighborId, label: edge.label }],
      });
    }
  }

  return { found: false, path: [], edges: [], proof: '', error: `No path found between "${sourceLabel}" and "${targetLabel}".` };
}