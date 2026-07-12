import { useState, useRef } from 'react';
import { Network, Activity, Sparkles, X, GitBranch, Layers, Search, Terminal, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Toaster, toast } from 'sonner';
import { ConstructionPanel, ReasoningPanel, LlmPanel, QueryPanel } from './components/InspectorPanel';
import { GraphCanvas } from './components/GraphCanvas';
import { spreadActivation, runInference, feedBackActivation } from './lib/engine';
import { createUserMessage, createAssistantMessage, llmRespond } from './lib/llm';
import { ALL_MODULES, MODULE_LABELS, MODULE_COLORS } from './lib/fibo-data';
import type { GraphNode, GraphEdge, Rule, DerivedFact, ActivationResult, ChatMessage, FiboModule, FiboEdgeType, InferenceTraceEntry, LoopStep } from './types';

const DEFAULT_NODES: GraphNode[] = [
  { id: 'n1', label: 'Credit Suisse', module: 'BusinessEntities', fiboClass: 'fibo-be-ge-ge:Bank', x: 250, y: 200, activation: 0, depth: -1, tags: ['bank'], note: 'Global systemically important bank.', derived: false, properties: { lei: '529900LX67VQ8V3N7N11', jurisdiction: 'CH', sector: 'Banking' }, salience: 1.0 },
  { id: 'n2', label: 'Zürich', module: 'BusinessEntities', fiboClass: 'fibo-be-ge-ge:BusinessCenter', x: 450, y: 120, activation: 0, depth: -1, tags: ['city'], note: 'Swiss financial center.', derived: false, properties: { jurisdiction: 'CH' }, salience: 1.0 },
  { id: 'n3', label: 'CS Atlas Bond I', module: 'Securities', fiboClass: 'fibo-sec-sec-dbt:BondInstrument', x: 550, y: 320, activation: 0, depth: -1, tags: ['bond'], note: 'CHF-denominated corporate bond.', derived: false, properties: { isin: 'CH1234567890', currency: 'CHF', rating: 'A', maturity: '2030-12-31' }, salience: 1.2 },
  { id: 'n4', label: 'Swiss Franc', module: 'Securities', fiboClass: 'fibo-sec-sec-cls:Currency', x: 750, y: 250, activation: 0, depth: -1, tags: ['currency'], note: 'ISO CHF.', derived: false, properties: { currency: 'CHF' }, salience: 0.8 },
  { id: 'n5', label: 'FINMA', module: 'Regulatory', fiboClass: 'fibo-fbc-fct-fct:RegulatoryAgency', x: 350, y: 400, activation: 0, depth: -1, tags: ['regulator'], note: 'Swiss Financial Market Supervisory Authority.', derived: false, properties: { jurisdiction: 'CH' }, salience: 1.1 },
  { id: 'n6', label: 'UBS', module: 'BusinessEntities', fiboClass: 'fibo-be-ge-ge:Bank', x: 150, y: 350, activation: 0, depth: -1, tags: ['bank'], note: 'Swiss universal bank.', derived: false, properties: { lei: '529900LX67VQ8V3N7N12', jurisdiction: 'CH', sector: 'Banking' }, salience: 1.0 },
];

const DEFAULT_EDGES: GraphEdge[] = [
  { id: 'e1', source: 'n1', target: 'n2', type: 'hasDomicile', weight: 1 },
  { id: 'e2', source: 'n3', target: 'n1', type: 'issuedBy', weight: 1 },
  { id: 'e3', source: 'n3', target: 'n4', type: 'denominatedIn', weight: 1 },
  { id: 'e4', source: 'n5', target: 'n1', type: 'regulates', weight: 1 },
  { id: 'e5', source: 'n5', target: 'n6', type: 'regulates', weight: 1 },
  { id: 'e6', source: 'n6', target: 'n2', type: 'hasDomicile', weight: 1 },
];

const DEFAULT_RULES: Rule[] = [
  { id: 'r1', name: 'Issuer Domicile', sourceModule: 'Securities', edgeType: 'issuedBy', targetModule: 'BusinessEntities', deriveTag: 'issuerDomicile', threshold: 0.2, description: '{source} is issued by an entity domiciled in a jurisdiction tracked by {target}.' },
  { id: 'r2', name: 'Regulatory Oversight', sourceModule: 'Regulatory', edgeType: 'regulates', targetModule: 'BusinessEntities', deriveTag: 'regulatedEntity', threshold: 0.15, description: '{target} is under regulatory oversight by {source}.' },
];

export default function App() {
  const [nodes, setNodes] = useState<GraphNode[]>(DEFAULT_NODES);
  const [edges, setEdges] = useState<GraphEdge[]>(DEFAULT_EDGES);
  const [rules, setRules] = useState<Rule[]>(DEFAULT_RULES);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [linkMode, setLinkMode] = useState<FiboEdgeType | null>(null);
  const [linkSource, setLinkSource] = useState<string | null>(null);
  const [activationResult, setActivationResult] = useState<ActivationResult | null>(null);
  const [derivedFacts, setDerivedFacts] = useState<DerivedFact[]>([]);
  const [trace, setTrace] = useState<InferenceTraceEntry[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [activeTab, setActiveTab] = useState<'construction' | 'reasoning'>('reasoning');
  const [rightTab, setRightTab] = useState<'query' | 'llm'>('query');
  const [loopIteration, setLoopIteration] = useState(0);
  const [loopStep, setLoopStep] = useState<LoopStep>('idle');
  const [autoRunning, setAutoRunning] = useState(false);
  const [heatmapOn, setHeatmapOn] = useState(false);
  const [showProofPaths, setShowProofPaths] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const autoRunRef = useRef(false);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null;

  const handleAddNode = (label: string, module: FiboModule, fiboClass: string) => {
    const id = `n${Date.now()}`;
    const newNode: GraphNode = {
      id, label, module, fiboClass: fiboClass || 'fibo-be-le-lp:LegalEntity',
      x: 300 + Math.random() * 200, y: 200 + Math.random() * 150,
      activation: 0, depth: -1, tags: [], note: '', derived: false, properties: {}, salience: 1.0,
    };
    setNodes([...nodes, newNode]);
    toast.success(`Node "${label}" added`);
  };

  const handleLinkMode = (type: FiboEdgeType | null) => {
    setLinkMode(type);
    setLinkSource(null);
    if (type) toast.info(`Link mode: ${type}. Click source then target.`);
  };

  const handleSelectNode = (id: string) => {
    if (linkMode && id) {
      if (!linkSource) {
        setLinkSource(id);
        toast.info('Now click target node');
      } else {
        if (linkSource === id) { toast.error('Source and target must differ'); return; }
        const newEdge: GraphEdge = { id: `e${Date.now()}`, source: linkSource, target: id, type: linkMode, weight: 1 };
        setEdges([...edges, newEdge]);
        toast.success(`Edge ${linkMode} created`);
        setLinkSource(null);
        setLinkMode(null);
      }
      return;
    }
    setSelectedNodeId(id || null);
  };

  const handleMoveNode = (id: string, x: number, y: number) => {
    setNodes(nodes.map((n) => (n.id === id ? { ...n, x, y } : n)));
  };

  const handleUpdateNote = (id: string, note: string) => {
    setNodes(nodes.map((n) => (n.id === id ? { ...n, note } : n)));
  };

  const handleUpdateProperty = (id: string, key: string, value: string) => {
    setNodes(nodes.map((n) => (n.id === id ? { ...n, properties: { ...n.properties, [key]: value } } : n)));
  };

  const handleUpdateSalience = (id: string, salience: number) => {
    setNodes(nodes.map((n) => (n.id === id ? { ...n, salience } : n)));
  };

  const handleAddRule = (rule: Rule) => {
    setRules([...rules, rule]);
    toast.success(`Rule "${rule.name}" added`);
  };

  const handleDeleteRule = (id: string) => {
    setRules(rules.filter((r) => r.id !== id));
  };

  const handleRunActivation = (id: string) => {
    const { nodes: updatedNodes, result } = spreadActivation(id, nodes, edges);
    setNodes(updatedNodes);
    setActivationResult(result);
    setLoopStep('neural');
    toast.success(`Activation spread from ${result.sourceLabel}`);
  };

  const handleClearActivation = () => {
    setNodes(nodes.map((n) => ({ ...n, activation: 0, depth: -1 })));
    setActivationResult(null);
    setLoopStep('idle');
  };

  const handleRunInference = () => {
    const existingIds = derivedFacts.map((f) => f.id);
    const { facts, updatedNodes, trace: newTrace } = runInference(nodes, edges, rules, existingIds, loopIteration + 1);
    if (facts.length === 0) {
      toast.info('No new facts derived. Try lowering rule thresholds or spreading more activation.');
    } else {
      setNodes(updatedNodes);
      setDerivedFacts([...derivedFacts, ...facts]);
      setTrace([...trace, ...newTrace]);
      setLoopStep('symbolic');
      toast.success(`${facts.length} fact(s) derived`);
    }
  };

  const handleClearFacts = () => {
    setDerivedFacts([]);
    setTrace([]);
    setNodes(nodes.map((n) => ({ ...n, derived: false, derivedFrom: [], derivedRuleName: undefined, proofPath: undefined })));
    setLoopIteration(0);
    setLoopStep(activationResult ? 'neural' : 'idle');
  };

  const handleFeedBack = () => {
    const { nodes: updatedNodes, updatedFacts } = feedBackActivation(nodes, derivedFacts);
    setNodes(updatedNodes);
    setDerivedFacts(updatedFacts);
    setLoopStep('feedback');
    toast.success('Facts fed back to neural layer');
  };

  const handleAutoRun = () => {
    if (!selectedNodeId) { toast.error('Select a node first'); return; }
    setAutoRunning(true);
    autoRunRef.current = true;
    runAutoLoop(selectedNodeId, 1);
  };

  const runAutoLoop = (sourceId: string, iteration: number) => {
    if (!autoRunRef.current) return;
    setLoopIteration(iteration);
    setLoopStep('neural');

    setTimeout(() => {
      if (!autoRunRef.current) return;
      const { nodes: activatedNodes, result } = spreadActivation(sourceId, nodes, edges);
      setNodes(activatedNodes);
      setActivationResult(result);

      setTimeout(() => {
        if (!autoRunRef.current) return;
        setLoopStep('symbolic');
        const existingIds = derivedFacts.map((f) => f.id);
        const { facts, updatedNodes, trace: newTrace } = runInference(activatedNodes, edges, rules, existingIds, iteration);

        if (facts.length === 0) {
          setLoopStep('complete');
          setAutoRunning(false);
          autoRunRef.current = false;
          toast.success(`Converged at iteration ${iteration} — no new facts derived. Fixpoint reached at depth ${iteration}.`);
          return;
        }

        setNodes(updatedNodes);
        setDerivedFacts((prev) => [...prev, ...facts]);
        setTrace((prev) => [...prev, ...newTrace]);

        setTimeout(() => {
          if (!autoRunRef.current) return;
          setLoopStep('feedback');
          const { nodes: fedNodes, updatedFacts } = feedBackActivation(updatedNodes, [...derivedFacts, ...facts]);
          setNodes(fedNodes);
          setDerivedFacts(updatedFacts);

          setTimeout(() => {
            if (!autoRunRef.current) return;
            if (iteration >= 5) {
              setLoopStep('complete');
              setAutoRunning(false);
              autoRunRef.current = false;
              toast.info(`Max iterations (5) reached. ${derivedFacts.length + facts.length} total facts derived.`);
              return;
            }
            runAutoLoop(sourceId, iteration + 1);
          }, 600);
        }, 500);
      }, 500);
    }, 300);
  };

  const handleStopAuto = () => {
    autoRunRef.current = false;
    setAutoRunning(false);
    setLoopStep('idle');
    toast.info('Auto-run stopped');
  };

  const handleSendChat = (text: string) => {
    const userMsg = createUserMessage(text);
    const assistantContent = llmRespond(text, { nodes, edges, activationResult, derivedFacts, selectedNode, trace, loopIteration });
    const assistantMsg = createAssistantMessage(assistantContent);
    setChatMessages([...chatMessages, userMsg, assistantMsg]);
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden">
      <Toaster theme="dark" position="bottom-right" />
      <header className="h-14 border-b border-zinc-800 flex items-center justify-between px-4 shrink-0 bg-zinc-900/50 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white flex items-center justify-center">
            <Network className="w-5 h-5 text-black" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight">Neurosymbolic Graph OS</h1>
            <p className="text-[10px] text-zinc-500">FIBO-typed knowledge graph · spreading activation · rule inference</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">{nodes.length} nodes</Badge>
          <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">{edges.length} edges</Badge>
          <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">{rules.length} rules</Badge>
          {derivedFacts.length > 0 && <Badge className="text-[10px] bg-amber-400 text-black">{derivedFacts.length} facts</Badge>}
          {loopIteration > 0 && <Badge className="text-[10px] bg-white text-black">iter {loopIteration}</Badge>}
          <div className="flex items-center gap-1 ml-2">
            {ALL_MODULES.map((m) => (
              <div key={m} className="flex items-center gap-1">
                <div className={`w-2 h-2 rounded-full ${MODULE_COLORS[m]}`} />
                <span className="text-[9px] text-zinc-500">{MODULE_LABELS[m]}</span>
              </div>
            ))}
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Left sidebar */}
        <div className={`flex flex-col border-r border-zinc-800 bg-zinc-900/30 transition-all duration-300 ${leftCollapsed ? 'w-10' : 'w-80'}`}>
          {leftCollapsed ? (
            <button onClick={() => setLeftCollapsed(false)} className="h-full flex items-center justify-center hover:bg-zinc-800 transition-colors">
              <PanelLeftOpen className="w-4 h-4 text-zinc-500" />
            </button>
          ) : (
            <>
              <div className="h-9 border-b border-zinc-800 flex items-center shrink-0">
                <button onClick={() => setActiveTab('construction')} className={`flex-1 h-full text-[10px] font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1.5 ${activeTab === 'construction' ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-300'}`}>
                  <Layers className="w-3 h-3" /> Construct
                </button>
                <button onClick={() => setActiveTab('reasoning')} className={`flex-1 h-full text-[10px] font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1.5 ${activeTab === 'reasoning' ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-300'}`}>
                  <Activity className="w-3 h-3" /> Reason
                </button>
                <button onClick={() => setLeftCollapsed(true)} className="w-9 h-full flex items-center justify-center text-zinc-600 hover:text-zinc-300 transition-colors shrink-0">
                  <PanelLeftClose className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                {activeTab === 'construction' ? (
                  <ConstructionPanel selectedNode={selectedNode} rules={rules} onAddNode={handleAddNode} onLinkMode={handleLinkMode} linkMode={linkMode} onUpdateNote={handleUpdateNote} onUpdateProperty={handleUpdateProperty} onUpdateSalience={handleUpdateSalience} onAddRule={handleAddRule} onDeleteRule={handleDeleteRule} />
                ) : (
                  <ReasoningPanel selectedNode={selectedNode} activationResult={activationResult} derivedFacts={derivedFacts} trace={trace} loopIteration={loopIteration} loopStep={loopStep} autoRunning={autoRunning} heatmapOn={heatmapOn} showProofPaths={showProofPaths} onRunActivation={handleRunActivation} onClearActivation={handleClearActivation} onRunInference={handleRunInference} onClearFacts={handleClearFacts} onFeedBack={handleFeedBack} onAutoRun={handleAutoRun} onStopAuto={handleStopAuto} onToggleHeatmap={() => setHeatmapOn(!heatmapOn)} onToggleProofPaths={() => setShowProofPaths(!showProofPaths)} />
                )}
              </div>
            </>
          )}
        </div>

        {/* Canvas */}
        <div className="flex-1 relative overflow-hidden bg-zinc-950">
          <GraphCanvas nodes={nodes} edges={edges} selectedNodeId={selectedNodeId} linkMode={linkMode} linkSource={linkSource} heatmapOn={heatmapOn} showProofPaths={showProofPaths} onSelectNode={handleSelectNode} onMoveNode={handleMoveNode} />
          {linkMode && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full bg-white text-black text-xs font-medium flex items-center gap-2 shadow-lg">
              <GitBranch className="w-3.5 h-3.5" />
              {linkSource ? 'Click target node' : `Click source node (${linkMode})`}
              <button onClick={() => handleLinkMode(null)} className="ml-1 hover:opacity-70"><X className="w-3.5 h-3.5" /></button>
            </div>
          )}
          {autoRunning && (
            <div className="absolute top-4 right-4 px-3 py-1.5 rounded-full bg-white text-black text-[10px] font-bold flex items-center gap-1.5 shadow-lg animate-pulse">
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
              AUTO-RUN · ITER {loopIteration}
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <div className={`flex flex-col border-l border-zinc-800 bg-zinc-900/30 transition-all duration-300 ${rightCollapsed ? 'w-10' : 'w-80'}`}>
          {rightCollapsed ? (
            <button onClick={() => setRightCollapsed(false)} className="h-full flex items-center justify-center hover:bg-zinc-800 transition-colors">
              <PanelRightOpen className="w-4 h-4 text-zinc-500" />
            </button>
          ) : (
            <>
              <div className="h-9 border-b border-zinc-800 flex items-center shrink-0">
                <button onClick={() => setRightTab('query')} className={`flex-1 h-full text-[10px] font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1.5 ${rightTab === 'query' ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-300'}`}>
                  <Search className="w-3 h-3" /> Query
                </button>
                <button onClick={() => setRightTab('llm')} className={`flex-1 h-full text-[10px] font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1.5 ${rightTab === 'llm' ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-300'}`}>
                  <Terminal className="w-3 h-3" /> LLM
                </button>
                <button onClick={() => setRightCollapsed(true)} className="w-9 h-full flex items-center justify-center text-zinc-600 hover:text-zinc-300 transition-colors shrink-0">
                  <PanelRightClose className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                {rightTab === 'query' ? (
                  <QueryPanel nodes={nodes} edges={edges} derivedFacts={derivedFacts} />
                ) : (
                  <LlmPanel messages={chatMessages} onMessagesChange={setChatMessages} nodes={nodes} edges={edges} activationResult={activationResult} derivedFacts={derivedFacts} selectedNode={selectedNode} trace={trace} loopIteration={loopIteration} />
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}