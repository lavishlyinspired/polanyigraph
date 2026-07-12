// Zustand store wiring the UI to the real backend. No demo data: state is
// populated only by ingest/graph/reason/query/chat API calls.
import { create } from 'zustand';
import { toast } from 'sonner';
import {
  api,
  type AgentIntent,
  type ApiEdge,
  type ApiNode,
  type DerivedFact,
  type GraphSummary,
  type ImplicitFact,
  type IngestEvent,
  type QueryResultRow,
  type Rule,
  type TraceEntry,
} from '../lib/api';

export interface LayoutNode extends ApiNode {
  x: number;
  y: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export interface AgentMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  intent?: AgentIntent;
}

const ACTIVE_GRAPH_KEY = 'neurosymbolic:activeGraphId';

function readStoredGraphId(): string {
  try {
    return localStorage.getItem(ACTIVE_GRAPH_KEY) || 'default';
  } catch {
    return 'default';
  }
}

function storeGraphId(graphId: string): void {
  try {
    localStorage.setItem(ACTIVE_GRAPH_KEY, graphId);
  } catch {
    // localStorage unavailable (private mode, etc.) -- graph still works, just doesn't persist.
  }
}

interface GraphState {
  graphId: string;
  nodes: LayoutNode[];
  edges: ApiEdge[];
  facts: DerivedFact[];
  trace: TraceEntry[];
  loopStep: 'idle' | 'neural' | 'symbolic' | 'feedback';
  loopIteration: number;
  selectedNodeId: string | null;
  convergedBy: 'fixpoint' | 'max_iterations' | null;
  iterations: number;
  loading: boolean;
  error: string | null;
  queryText: string;
  queryResults: QueryResultRow[];
  queryError: string | null;
  zoom: number;
  pan: { x: number; y: number };
  showHeatmap: boolean;
  showProofPath: boolean;
  history: IngestEvent[];
  rules: Rule[];
  graphs: GraphSummary[];
  autoRunning: boolean;
  chatMessages: ChatMessage[];
  chatLoading: boolean;
  agentMessages: AgentMessage[];
  agentLoading: boolean;
  ontologyClasses: string[];
  ontologyProperties: string[];
  linkMode: string | null;
  linkSourceId: string | null;
  pendingFacts: ImplicitFact[];
  approvedFacts: ImplicitFact[];
  enriching: boolean;
  showCommunities: boolean;
  detectingCommunities: boolean;

  loadGraph: () => Promise<void>;
  ingest: (text: string) => Promise<void>;
  reason: () => Promise<void>;
  spreadActivationStep: () => Promise<void>;
  runInferenceStep: () => Promise<void>;
  feedBackStep: () => Promise<void>;
  clearActivationStep: () => Promise<void>;
  clearFactsStep: () => Promise<void>;
  loadReasonFacts: () => Promise<void>;
  runQuery: (query: string) => Promise<void>;
  loadHistory: () => Promise<void>;
  loadRules: () => Promise<void>;
  loadGraphs: () => Promise<void>;
  loadOntology: () => Promise<void>;
  switchGraph: (graphId: string) => Promise<void>;
  startAutoRun: () => void;
  stopAutoRun: () => void;
  sendChatMessage: (text: string) => Promise<void>;
  sendAgentMessage: (text: string) => Promise<void>;
  selectNode: (id: string | null) => void;
  moveNode: (id: string, x: number, y: number) => void;
  setQueryText: (text: string) => void;
  setZoom: (z: number) => void;
  setPan: (p: { x: number; y: number }) => void;
  toggleHeatmap: () => void;
  toggleProofPath: () => void;
  addNode: (label: string, type: string) => Promise<void>;
  setLinkMode: (type: string | null) => void;
  handleCanvasNodeClick: (nodeId: string) => Promise<boolean>;
  updateNodeMetadata: (nodeId: string, patch: { salience?: number; properties?: Record<string, string>; note?: string }) => Promise<void>;
  createRule: (rule: { name: string; edgeType: string; sourceType: string; targetType: string; threshold: number; weight?: number; description?: string }) => Promise<void>;
  deleteRule: (ruleId: string) => Promise<void>;
  enrich: (text: string) => Promise<void>;
  loadPendingFacts: () => Promise<void>;
  loadApprovedFacts: () => Promise<void>;
  approveFact: (factId: string) => Promise<void>;
  rejectFact: (factId: string) => Promise<void>;
  detectCommunities: () => Promise<void>;
  toggleCommunities: () => void;
}

// Deterministic circular layout: the backend has no notion of position (it's
// a domain-agnostic reasoning store, not a layout engine), so the client owns
// it. Simple and predictable is preferable to a heavier force-layout dependency
// for the MVP.
function layoutNodes(nodes: ApiNode[], previous: LayoutNode[]): LayoutNode[] {
  const previousById = new Map(previous.map((n) => [n.id, n]));
  const radius = 220;
  const centerX = 400;
  const centerY = 300;
  return nodes.map((n, i) => {
    const existing = previousById.get(n.id);
    if (existing) return { ...existing, ...n };
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
    return { ...n, x: centerX + radius * Math.cos(angle), y: centerY + radius * Math.sin(angle) };
  });
}


export const useGraphStore = create<GraphState>((set, get) => ({
  graphId: readStoredGraphId(),
  nodes: [],
  edges: [],
  facts: [],
  trace: [],
  loopStep: 'idle',
  loopIteration: 0,
  selectedNodeId: null,
  convergedBy: null,
  iterations: 0,
  loading: false,
  error: null,
  queryText: '',
  queryResults: [],
  queryError: null,
  zoom: 1,
  pan: { x: 0, y: 0 },
  showHeatmap: false,
  showProofPath: false,
  history: [],
  rules: [],
  graphs: [],
  autoRunning: false,
  chatMessages: [],
  chatLoading: false,
  agentMessages: [],
  agentLoading: false,
  ontologyClasses: [],
  ontologyProperties: [],
  linkMode: null,
  linkSourceId: null,
  pendingFacts: [],
  approvedFacts: [],
  enriching: false,
  showCommunities: false,
  detectingCommunities: false,

  loadGraph: async () => {
    set({ loading: true, error: null });
    try {
      const graph = await api.getGraph(get().graphId);
      set({ nodes: layoutNodes(graph.nodes, get().nodes), edges: graph.edges, loading: false });
    } catch (e) {
      set({ error: String(e), loading: false });
    }
  },

  ingest: async (text: string) => {
    set({ loading: true, error: null });
    try {
      const graph = await api.ingestText(get().graphId, text);
      set({ nodes: layoutNodes(graph.nodes, get().nodes), edges: graph.edges, loading: false });
      toast.success(`Extracted ${graph.nodes.length} entities, ${graph.edges.length} relationships`);
      await Promise.all([get().loadHistory(), get().loadGraphs()]);
    } catch (e) {
      set({ error: String(e), loading: false });
      toast.error(String(e));
    }
  },

  loadHistory: async () => {
    try {
      const res = await api.getHistory(get().graphId);
      set({ history: res.events });
    } catch (e) {
      toast.error(String(e));
    }
  },

  loadRules: async () => {
    try {
      const res = await api.getRules();
      set({ rules: res.rules });
    } catch (e) {
      toast.error(String(e));
    }
  },

  loadGraphs: async () => {
    try {
      const res = await api.getGraphs();
      set({ graphs: res.graphs });
    } catch (e) {
      toast.error(String(e));
    }
  },

  loadOntology: async () => {
    try {
      const res = await api.getOntology();
      set({ ontologyClasses: res.classLabels, ontologyProperties: res.propertyLabels });
    } catch (e) {
      toast.error(String(e));
    }
  },

  switchGraph: async (graphId: string) => {
    get().stopAutoRun();
    storeGraphId(graphId);
    set({
      graphId, nodes: [], edges: [], facts: [], trace: [], loopStep: 'idle', loopIteration: 0,
      selectedNodeId: null, convergedBy: null, iterations: 0, history: [], chatMessages: [],
      pendingFacts: [], approvedFacts: [], showCommunities: false, agentMessages: [],
    });
    await Promise.all([get().loadGraph(), get().loadHistory(), get().loadPendingFacts(), get().loadApprovedFacts(), get().loadReasonFacts()]);
  },

  reason: async () => {
    const { graphId, selectedNodeId } = get();
    set({ loading: true, error: null });
    try {
      const result = await api.reason(graphId, selectedNodeId ?? undefined);
      set({
        facts: result.facts,
        convergedBy: result.convergedBy,
        iterations: result.iterations,
        loading: false,
      });
      await get().loadGraph(); // refresh activation/derived flags persisted server-side
      toast.success(`Derived ${result.facts.length} facts in ${result.iterations} iterations (${result.convergedBy})`);
    } catch (e) {
      set({ error: String(e), loading: false });
      toast.error(String(e));
    }
  },

  // --- Manual step-by-step mode (Reason tab prototype parity) -- each step
  // is a real call against real persisted Neo4j state, not client-side mock
  // computation like the prototype's engine.ts.
  spreadActivationStep: async () => {
    const { graphId, selectedNodeId } = get();
    if (!selectedNodeId) return;
    set({ loading: true, error: null });
    try {
      await api.spreadActivation(graphId, selectedNodeId);
      set({ loopStep: 'neural', loading: false });
      await get().loadGraph();
      toast.success('Activation spread from selected node');
    } catch (e) {
      set({ error: String(e), loading: false });
      toast.error(String(e));
    }
  },

  runInferenceStep: async () => {
    const { graphId } = get();
    set({ loading: true, error: null });
    try {
      const result = await api.runInferenceStep(graphId);
      set((s) => ({
        facts: [...s.facts, ...result.facts],
        trace: [...s.trace, ...result.trace],
        loopStep: 'symbolic',
        loopIteration: s.loopIteration + 1,
        loading: false,
      }));
      await get().loadGraph(); // refresh derived flags
      if (result.facts.length > 0) toast.success(`${result.facts.length} fact(s) derived`);
      else toast.info('No new facts derived. Try lowering rule thresholds or spreading more activation.');
    } catch (e) {
      set({ error: String(e), loading: false });
      toast.error(String(e));
    }
  },

  feedBackStep: async () => {
    const { graphId } = get();
    set({ loading: true, error: null });
    try {
      await api.feedBack(graphId);
      set({ loopStep: 'feedback', loading: false });
      await Promise.all([get().loadGraph(), get().loadReasonFacts()]);
      toast.success('Facts fed back to neural layer');
    } catch (e) {
      set({ error: String(e), loading: false });
      toast.error(String(e));
    }
  },

  clearActivationStep: async () => {
    const { graphId } = get();
    try {
      await api.clearActivation(graphId);
      set({ loopStep: 'idle' });
      await get().loadGraph();
    } catch (e) {
      toast.error(String(e));
    }
  },

  clearFactsStep: async () => {
    const { graphId } = get();
    try {
      await api.clearFacts(graphId);
      set({ facts: [], trace: [] });
      await get().loadGraph();
    } catch (e) {
      toast.error(String(e));
    }
  },

  loadReasonFacts: async () => {
    const { graphId } = get();
    try {
      const result = await api.getReasonFacts(graphId);
      set({ facts: result.facts });
    } catch (e) {
      toast.error(String(e));
    }
  },

  startAutoRun: () => {
    if (get().autoRunning) return;
    set({ autoRunning: true, loopIteration: 0 });
    void (async () => {
      // Real staged loop -- spread -> infer -> feed back, each a real call
      // against real persisted state (prototype parity), stopping when a
      // round derives no new facts (converged) or stopAutoRun() flips the
      // flag this loop polls between every step.
      const MAX_AUTO_ITERATIONS = 5;
      for (let i = 0; i < MAX_AUTO_ITERATIONS; i++) {
        if (!get().autoRunning) break;
        await get().spreadActivationStep();
        await new Promise((r) => setTimeout(r, 300));
        if (!get().autoRunning) break;

        const factsBefore = get().facts.length;
        await get().runInferenceStep();
        await new Promise((r) => setTimeout(r, 400));
        if (!get().autoRunning) break;
        const newFactsCount = get().facts.length - factsBefore;

        await get().feedBackStep();
        await new Promise((r) => setTimeout(r, 400));

        if (newFactsCount === 0) break; // converged: nothing new to spread further
      }
      set({ autoRunning: false });
    })();
  },

  stopAutoRun: () => set({ autoRunning: false }),

  sendChatMessage: async (text: string) => {
    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: 'user', content: text };
    set({ chatMessages: [...get().chatMessages, userMsg], chatLoading: true });
    try {
      const res = await api.chat(get().graphId, text);
      const assistantMsg: ChatMessage = { id: `a-${Date.now()}`, role: 'assistant', content: res.reply };
      set({ chatMessages: [...get().chatMessages, assistantMsg], chatLoading: false });
    } catch (e) {
      set({ chatLoading: false });
      toast.error(String(e));
    }
  },

  sendAgentMessage: async (text: string) => {
    const userMsg: AgentMessage = { id: `u-${Date.now()}`, role: 'user', content: text };
    set({ agentMessages: [...get().agentMessages, userMsg], agentLoading: true });
    try {
      const res = await api.runAgent(get().graphId, text);
      const assistantMsg: AgentMessage = { id: `a-${Date.now()}`, role: 'assistant', content: res.reply, intent: res.intent };
      set({ agentMessages: [...get().agentMessages, assistantMsg], agentLoading: false });
      // extract/enrich/reason intents mutate real Neo4j state -- refresh.
      await Promise.all([get().loadGraph(), get().loadPendingFacts(), get().loadHistory(), get().loadGraphs()]);
    } catch (e) {
      set({ agentLoading: false });
      toast.error(String(e));
    }
  },

  runQuery: async (query: string) => {
    set({ queryError: null });
    try {
      const res = await api.query(get().graphId, query);
      set({ queryResults: res.results, queryError: res.error });
      if (res.error) {
        toast.error(res.error);
      } else {
        toast.success(`Found ${res.results.length} results`);
      }
    } catch (e) {
      set({ queryError: String(e), queryResults: [] });
      toast.error(String(e));
    }
  },

  selectNode: (id) => set({ selectedNodeId: id }),
  moveNode: (id, x, y) => set({ nodes: get().nodes.map((n) => (n.id === id ? { ...n, x, y } : n)) }),
  setQueryText: (text) => set({ queryText: text }),
  setZoom: (z) => set({ zoom: Math.max(0.2, Math.min(3, z)) }),
  setPan: (p) => set({ pan: p }),
  toggleHeatmap: () => set({ showHeatmap: !get().showHeatmap }),
  toggleProofPath: () => set({ showProofPath: !get().showProofPath }),

  addNode: async (label: string, type: string) => {
    try {
      await api.addNode(get().graphId, label, type);
      toast.success(`Added "${label}" (${type})`);
      await Promise.all([get().loadGraph(), get().loadGraphs()]);
    } catch (e) {
      toast.error(String(e));
    }
  },

  setLinkMode: (type: string | null) => set({ linkMode: type, linkSourceId: null }),

  // Called by GraphCanvas on node click. Returns true if the click was
  // consumed by link-mode (source/target selection) so the canvas should NOT
  // also run its normal select/drag behavior.
  handleCanvasNodeClick: async (nodeId: string) => {
    const { linkMode, linkSourceId, graphId } = get();
    if (!linkMode) return false;

    if (!linkSourceId) {
      set({ linkSourceId: nodeId });
      toast.info('Now click the target node');
      return true;
    }
    if (linkSourceId === nodeId) {
      toast.error('Source and target must differ');
      return true;
    }
    try {
      await api.addEdge(graphId, linkSourceId, nodeId, linkMode);
      toast.success(`Edge "${linkMode}" created`);
      set({ linkMode: null, linkSourceId: null });
      await get().loadGraph();
    } catch (e) {
      toast.error(String(e));
      set({ linkMode: null, linkSourceId: null });
    }
    return true;
  },

  updateNodeMetadata: async (nodeId, patch) => {
    try {
      await api.updateNode(get().graphId, nodeId, patch);
      await get().loadGraph();
    } catch (e) {
      toast.error(String(e));
    }
  },

  createRule: async (rule) => {
    try {
      await api.createRule(rule);
      toast.success(`Rule "${rule.name}" added`);
      await get().loadRules();
    } catch (e) {
      toast.error(String(e));
    }
  },

  deleteRule: async (ruleId: string) => {
    try {
      await api.deleteRule(ruleId);
      await get().loadRules();
    } catch (e) {
      toast.error(String(e));
    }
  },

  enrich: async (text: string) => {
    set({ enriching: true });
    try {
      const res = await api.enrich(get().graphId, text);
      toast.success(`Found ${res.facts.length} implicit facts across ${new Set(res.facts.map((f) => f.heuristicType)).size} heuristics`);
      set({ enriching: false });
      await get().loadPendingFacts();
    } catch (e) {
      set({ enriching: false });
      toast.error(String(e));
    }
  },

  loadPendingFacts: async () => {
    try {
      const res = await api.getPendingFacts(get().graphId);
      set({ pendingFacts: res.facts });
    } catch (e) {
      toast.error(String(e));
    }
  },

  loadApprovedFacts: async () => {
    try {
      const res = await api.getApprovedFacts(get().graphId);
      set({ approvedFacts: res.facts });
    } catch (e) {
      toast.error(String(e));
    }
  },

  approveFact: async (factId: string) => {
    try {
      await api.approveFact(get().graphId, factId);
      await Promise.all([get().loadPendingFacts(), get().loadApprovedFacts()]);
    } catch (e) {
      toast.error(String(e));
    }
  },

  rejectFact: async (factId: string) => {
    try {
      await api.rejectFact(get().graphId, factId);
      await get().loadPendingFacts();
    } catch (e) {
      toast.error(String(e));
    }
  },

  detectCommunities: async () => {
    set({ detectingCommunities: true });
    try {
      const res = await api.detectCommunities(get().graphId);
      const communityCount = new Set(res.members.map((m) => m.communityId)).size;
      toast.success(`Found ${communityCount} communities across ${res.members.length} entities`);
      set({ detectingCommunities: false, showCommunities: true });
      await get().loadGraph(); // refresh so nodes carry the new communityId
    } catch (e) {
      set({ detectingCommunities: false });
      toast.error(String(e));
    }
  },

  toggleCommunities: () => set({ showCommunities: !get().showCommunities }),
}));
