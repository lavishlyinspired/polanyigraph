import type { GraphNode, GraphEdge, ActivationResult, DerivedFact, ChatMessage, InferenceTraceEntry } from '../types';

export function createUserMessage(content: string): ChatMessage {
  return { id: `u-${Date.now()}-${Math.random()}`, role: 'user', content, timestamp: Date.now() };
}

export function createAssistantMessage(content: string): ChatMessage {
  return { id: `a-${Date.now()}-${Math.random()}`, role: 'assistant', content, timestamp: Date.now() };
}

interface LlmContext {
  nodes: GraphNode[];
  edges: GraphEdge[];
  activationResult: ActivationResult | null;
  derivedFacts: DerivedFact[];
  selectedNode: GraphNode | null;
  trace: InferenceTraceEntry[];
  loopIteration: number;
}

export function llmRespond(userText: string, ctx: LlmContext): string {
  const text = userText.toLowerCase();

  if (text.includes('summar') || text.includes('overview') || text.includes('status')) {
    const active = ctx.activationResult?.ranked ?? [];
    const facts = ctx.derivedFacts;
    const derivedNodes = ctx.nodes.filter((n) => n.derived);
    let response = `Graph: ${ctx.nodes.length} nodes, ${ctx.edges.length} edges, ${ctx.trace.length} rule evaluations.\nLoop iteration: ${ctx.loopIteration}\n\n`;
    if (active.length > 0) {
      response += `Neural: ${active.length} nodes active from "${ctx.activationResult!.sourceLabel}".\nTop: ${active.slice(0, 3).map((a) => `${a.nodeLabel} (${(a.activation * 100).toFixed(0)}%)`).join(', ')}.\n`;
    } else {
      response += 'Neural: idle.\n';
    }
    if (facts.length > 0) {
      response += `\nSymbolic: ${facts.length} facts derived.\nDerived nodes: ${derivedNodes.map((n) => n.label).join(', ')}\n`;
      response += facts.slice(0, 3).map((f) => `  • [${f.ruleName}] ${f.fact}`).join('\n');
    } else {
      response += '\nSymbolic: idle.';
    }
    return response;
  }

  if (text.includes('activ') || text.includes('neural')) {
    if (!ctx.activationResult) return 'No neural activation yet. Select a node and spread activation.';
    const ranked = ctx.activationResult.ranked;
    if (ranked.length === 0) return 'Activation ran but no nodes were activated.';
    return `Neural activation from "${ctx.activationResult.sourceLabel}":\n\n${ranked.slice(0, 8).map((r, i) => `${i + 1}. ${r.nodeLabel} — ${(r.activation * 100).toFixed(1)}% (depth ${r.depth})`).join('\n')}`;
  }

  if (text.includes('infer') || text.includes('rule') || text.includes('symbol') || text.includes('trace')) {
    if (ctx.derivedFacts.length === 0 && ctx.trace.length === 0) return 'No inference has run yet. Spread activation first, then run inference.';
    let response = '';
    if (ctx.derivedFacts.length > 0) {
      response += `Derived facts (${ctx.derivedFacts.length}):\n\n${ctx.derivedFacts.map((f, i) => {
        const proofStr = f.proofPath.map((s) => `  ${s.step}. [${s.ruleName}] ${s.sourceLabel} → ${s.targetLabel} (${(s.sourceActivation * 100).toFixed(0)}% ≥ ${(s.threshold * 100).toFixed(0)}%)`).join('\n');
        return `${i + 1}. ${f.fact}\n   Proof:\n${proofStr}`;
      }).join('\n\n')}`;
    }
    if (ctx.trace.length > 0) {
      const fired = ctx.trace.filter((t) => t.fired);
      const skipped = ctx.trace.filter((t) => !t.fired);
      response += `\n\nInference trace:\n  ${fired.length} rules fired, ${skipped.length} skipped (low activation).\n`;
      if (skipped.length > 0) {
        response += `\nSkipped:\n${skipped.slice(0, 3).map((t) => `  • ${t.ruleName}: ${t.sourceLabel} (${(t.sourceActivation * 100).toFixed(0)}%) < ${(t.threshold * 100).toFixed(0)}%`).join('\n')}`;
      }
    }
    return response || 'No inference data available.';
  }

  if (text.includes('proof') || text.includes('why')) {
    const derivedNodes = ctx.nodes.filter((n) => n.derived && n.proofPath && n.proofPath.length > 0);
    if (derivedNodes.length === 0) return 'No derived nodes with proof paths. Run inference first.';
    return `Proof trees:\n\n${derivedNodes.map((n) => {
      const proofStr = n.proofPath!.map((s) => `  ${s.step}. [${s.ruleName}] ${s.sourceLabel} → ${s.targetLabel} (${(s.sourceActivation * 100).toFixed(0)}% ≥ ${(s.threshold * 100).toFixed(0)}%)`).join('\n');
      return `${n.label}:\n${proofStr}`;
    }).join('\n\n')}`;
  }

  if (text.includes('feedback') || text.includes('loop') || text.includes('cascade')) {
    const pending = ctx.derivedFacts.filter((f) => !f.fedBack);
    const fed = ctx.derivedFacts.filter((f) => f.fedBack);
    if (ctx.derivedFacts.length === 0) return 'No facts to feed back. Run inference first.';
    return `Feedback status:\n  ${fed.length} facts fed back (boosted neural activation)\n  ${pending.length} facts pending feedback\n\nLoop iteration: ${ctx.loopIteration}\n\nThe neurosymbolic loop:\n1. Neural activation spreads through the graph\n2. Symbolic rules fire on activated nodes → derive facts\n3. Facts feed back, boosting activation → new rules fire\n4. Repeat until convergence (no new facts)`;
  }

  if (text.includes('selected') || text.includes('detail')) {
    if (!ctx.selectedNode) return 'No node selected. Click a node on the canvas.';
    const n = ctx.selectedNode;
    let response = `Node: ${n.label}\nKind: ${n.kind}\nActivation: ${(n.activation * 100).toFixed(1)}%\nDepth: ${n.depth >= 0 ? n.depth : 'N/A'}\nSalience: ${n.salience}\nDerived: ${n.derived ? `Yes (${n.derivedFrom?.length || 0} facts, rule: ${n.derivedRuleName || 'unknown'})` : 'No'}`;
    if (n.proofPath && n.proofPath.length > 0) {
      response += `\n\nProof path:\n${n.proofPath.map((s) => `  ${s.step}. [${s.ruleName}] ${s.sourceLabel} → ${s.targetLabel} (${(s.sourceActivation * 100).toFixed(0)}% ≥ ${(s.threshold * 100).toFixed(0)}%)`).join('\n')}`;
    }
    if (n.note) response += `\n\nNote: ${n.note}`;
    return response;
  }

  if (text.includes('help') || text.includes('what') || text.includes('how')) {
    return `Synapse — Neurosymbolic Graph OS\n\nThe system combines neural spreading activation with symbolic rule inference:\n\n1. NEURAL: Pick a node → activation spreads to neighbors with decay (0.45 per hop). This is "attention" flowing through the graph. Depth tracks how far each node is from the source.\n\n2. SYMBOLIC: Rules fire on edges where the source node is activated above a threshold. Each rule derives a fact with a proof path showing the full derivation chain. Only rules on active nodes fire — neural guides symbolic.\n\n3. FEEDBACK: Derived facts boost activation on target nodes. This can cause NEW rules to fire on those nodes — symbolic guides neural. This creates cascading multi-hop inference.\n\n4. AUTO-RUN: Chains the loop automatically until convergence (no new facts).\n\n5. QUERY: Use the query console with Datalog-style syntax: predicate(subject, object). Use X or Y for variables. e.g., partOf("Module A", X) or dependsOn(X, "Component 1")\n\n6. PATH: Find shortest paths between nodes with full edge-by-edge proof.\n\n7. TRIPLES: View all base and derived triples in the triple store.\n\n8. SCHEMA: Manage node kinds and edge labels with semantic properties (transitive, symmetric).\n\nCommands: "summarize", "activation", "inference", "proof", "feedback", "selected node", "help"`;
  }

  return `Try: "summarize", "activation", "inference", "proof", "feedback", "selected node", or "help" for the full explanation.`;
}