// Real backend only, no demo data. An empty graph shows an ingest prompt
// (acceptance criterion #1 in docs/MVP_PLAN.md).
//
// Layout mirrors the prototype (.claude/docs/src/App.tsx): left sidebar
// Construct/Reason tabs (+ a separate Ingest tab, per explicit direction),
// right sidebar Query/LLM tabs, header badges. Sidebars are drag-resizable.
import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import {
  Network,
  Zap,
  PanelLeftOpen,
  PanelLeftClose,
  PanelRightOpen,
  PanelRightClose,
  CircleDot,
  GitBranch,
  Brain,
  Loader,
  History,
  FolderOpen,
  Layers,
  Activity,
  FileText,
  Search,
  Terminal,
  Cpu,
  Database,
  BookOpen,
  Sparkles,
  Bot,
} from 'lucide-react';
import { AgentPanel } from './components/AgentPanel';
import { ConstructionPanel } from './components/ConstructionPanel';
import { EnrichmentPanel } from './components/EnrichmentPanel';
import { GraphCanvas } from './components/GraphCanvas';
import { GraphsPopover } from './components/GraphsPopover';
import { HistoryPopover } from './components/HistoryPopover';
import { IngestPanel } from './components/IngestPanel';
import { LlmPanel } from './components/LlmPanel';
import { OntologyPanel } from './components/OntologyPanel';
import { QueryPanel } from './components/QueryPanel';
import { ReasoningPanel } from './components/ReasoningPanel';
import { TripleStorePanel } from './components/TripleStorePanel';
import { api, type HealthResponse } from './lib/api';
import { useGraphStore } from './stores/graphStore';

const MIN_SIDEBAR = 300;
const MAX_SIDEBAR = 640;
const DEFAULT_SIDEBAR = 400;

function LoadingSkeleton() {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 animate-pulse">
      <div className="flex items-center gap-2 text-zinc-500">
        <Loader className="w-4 h-4 animate-spin" />
        <span className="text-xs">Loading graph...</span>
      </div>
      <svg width={200} height={120} className="opacity-20">
        {[0, 1, 2, 3, 4].map((i) => {
          const cx = 100 + 70 * Math.cos((2 * Math.PI * i) / 5);
          const cy = 60 + 50 * Math.sin((2 * Math.PI * i) / 5);
          return (
            <g key={i}>
              <line x1={cx} y1={cy} x2={100 + 70 * Math.cos((2 * Math.PI * ((i + 1) % 5)) / 5)} y2={60 + 50 * Math.sin((2 * Math.PI * ((i + 1) % 5)) / 5)} stroke="#52525b" strokeWidth={1} />
              <circle cx={cx} cy={cy} r={10} fill="#27272a" stroke="#52525b" strokeWidth={1} />
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftWidth, setLeftWidth] = useState(DEFAULT_SIDEBAR);
  const [rightWidth, setRightWidth] = useState(DEFAULT_SIDEBAR);
  const [resizing, setResizing] = useState<'left' | 'right' | null>(null);
  const [leftTab, setLeftTab] = useState<'ingest' | 'construct' | 'reason' | 'enrich'>('ingest');
  const [rightTab, setRightTab] = useState<'query' | 'triples' | 'ontology' | 'llm' | 'agent'>('query');
  const [showHistory, setShowHistory] = useState(false);
  const [showGraphs, setShowGraphs] = useState(false);
  const {
    nodes, edges, facts, rules, selectedNodeId, loading, iterations, autoRunning,
    loadGraph, loadHistory, loadRules, loadGraphs, loadOntology, selectNode, moveNode,
    loadPendingFacts, loadApprovedFacts, pendingFacts, loadReasonFacts,
  } = useGraphStore();

  useEffect(() => {
    api.health().then(setHealth).catch(() => void 0);
    void loadGraph();
    void loadHistory();
    void loadRules();
    void loadGraphs();
    void loadOntology();
    void loadPendingFacts();
    void loadApprovedFacts();
    void loadReasonFacts();
  }, [loadGraph, loadHistory, loadRules, loadGraphs, loadOntology, loadPendingFacts, loadApprovedFacts, loadReasonFacts]);

  useEffect(() => {
    if (!resizing) return;
    const handleMove = (e: MouseEvent) => {
      if (resizing === 'left') setLeftWidth(Math.min(MAX_SIDEBAR, Math.max(MIN_SIDEBAR, e.clientX)));
      else setRightWidth(Math.min(MAX_SIDEBAR, Math.max(MIN_SIDEBAR, window.innerWidth - e.clientX)));
    };
    const handleUp = () => setResizing(null);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [resizing]);

  const empty = nodes.length === 0;

  return (
    <div className={`h-screen w-screen flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden ${resizing ? 'select-none cursor-col-resize' : ''}`}>
      <Toaster theme="dark" position="bottom-right" />

      {/* Header */}
      <header className="h-14 border-b border-zinc-800 flex items-center justify-between px-4 shrink-0 bg-zinc-900/50 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white flex items-center justify-center">
            <Network className="w-5 h-5 text-black" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight">Neurosymbolic KG</h1>
            <p className="text-[10px] text-zinc-500">{health ? `ontology: ${health.ontologyRepository}` : 'connecting...'}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-zinc-400">
            <Database className="w-3 h-3" />
            <span className="font-mono text-[11px]">{nodes.length} nodes · {edges.length} edges</span>
          </div>
          <div className="flex items-center gap-1.5 text-zinc-400">
            <Cpu className="w-3 h-3" />
            <span className="font-mono text-[11px]">{rules.length} rules</span>
          </div>
          {facts.length > 0 && (
            <div className="flex items-center gap-1.5 text-amber-400">
              <Brain className="w-3 h-3" />
              <span className="font-mono text-[11px]">{facts.length} facts</span>
            </div>
          )}
          {pendingFacts.length > 0 && (
            <button
              onClick={() => setLeftTab('enrich')}
              className="flex items-center gap-1.5 text-violet-400 hover:text-violet-300 transition-colors"
              title="Pending implicit facts awaiting review"
            >
              <Sparkles className="w-3 h-3" />
              <span className="font-mono text-[11px]">{pendingFacts.length} pending</span>
            </button>
          )}
          {iterations > 0 && (
            <div className="flex items-center gap-1.5 text-zinc-400">
              <Zap className="w-3 h-3" />
              <span className="font-mono text-[11px]">iter {iterations}</span>
            </div>
          )}
          {autoRunning && (
            <span className="px-2 py-0.5 rounded-full bg-white text-black text-[9px] font-bold flex items-center gap-1.5 animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" /> AUTO-RUN
            </span>
          )}
          <div className="flex items-center gap-2 ml-2">
            <div className="flex items-center gap-1">
              <CircleDot className="w-3 h-3 text-emerald-400" />
              <span className="text-[10px] text-zinc-500">neo4j {health?.neo4j.ok ? 'up' : 'down'}</span>
            </div>
            <div className="flex items-center gap-1">
              <GitBranch className="w-3 h-3 text-emerald-400" />
              <span className="text-[10px] text-zinc-500">graphdb {health?.graphdb.ok ? 'up' : 'down'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left sidebar: Ingest / Construct / Reason */}
        <div
          className="relative flex flex-col border-r border-zinc-800 bg-zinc-900/30 shrink-0"
          style={{ width: leftCollapsed ? 40 : leftWidth, transition: resizing ? 'none' : 'width 300ms' }}
        >
          {leftCollapsed ? (
            <button onClick={() => setLeftCollapsed(false)} className="h-full flex items-center justify-center hover:bg-zinc-800 transition-colors">
              <PanelLeftOpen className="w-4 h-4 text-zinc-500" />
            </button>
          ) : (
            <>
              <div className="h-9 border-b border-zinc-800 flex items-center shrink-0">
                {([
                  { key: 'ingest' as const, icon: FileText, label: 'Ingest' },
                  { key: 'construct' as const, icon: Layers, label: 'Construct' },
                  { key: 'reason' as const, icon: Activity, label: 'Reason' },
                  { key: 'enrich' as const, icon: Sparkles, label: 'Enrich' },
                ]).map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setLeftTab(tab.key)}
                    className={`flex-1 h-full text-[9px] font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1 ${
                      leftTab === tab.key ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-300'
                    }`}
                  >
                    <tab.icon className="w-2.5 h-2.5" /> {tab.label}
                  </button>
                ))}
                <div className="relative shrink-0">
                  <button
                    onClick={() => setShowGraphs((v) => !v)}
                    className={`w-8 h-full flex items-center justify-center transition-colors ${showGraphs ? 'text-white' : 'text-zinc-600 hover:text-zinc-300'}`}
                    title="Graphs"
                  >
                    <FolderOpen className="w-4 h-4" />
                  </button>
                  {showGraphs && <GraphsPopover onClose={() => setShowGraphs(false)} />}
                </div>
                <div className="relative shrink-0">
                  <button
                    onClick={() => setShowHistory((v) => !v)}
                    className={`w-8 h-full flex items-center justify-center transition-colors ${showHistory ? 'text-white' : 'text-zinc-600 hover:text-zinc-300'}`}
                    title="Ingest history"
                  >
                    <History className="w-4 h-4" />
                  </button>
                  {showHistory && <HistoryPopover onClose={() => setShowHistory(false)} />}
                </div>
                <button onClick={() => setLeftCollapsed(true)} className="w-8 h-full flex items-center justify-center text-zinc-600 hover:text-zinc-300 transition-colors shrink-0">
                  <PanelLeftClose className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                {leftTab === 'ingest' ? (
                  <IngestPanel />
                ) : leftTab === 'construct' ? (
                  <ConstructionPanel />
                ) : leftTab === 'reason' ? (
                  <ReasoningPanel />
                ) : (
                  <EnrichmentPanel />
                )}
              </div>
              <div
                onMouseDown={() => setResizing('left')}
                className="absolute top-0 -right-1 h-full w-2.5 cursor-col-resize hover:bg-zinc-600 active:bg-zinc-500 transition-colors z-10"
              />
            </>
          )}
        </div>

        {/* Canvas */}
        <div className="flex-1 relative overflow-hidden bg-zinc-950">
          {empty && loading ? (
            <LoadingSkeleton />
          ) : empty ? (
            <div className="h-full flex flex-col items-center justify-center text-zinc-600 gap-4">
              <Network className="w-12 h-12 text-zinc-800" />
              <div className="text-center">
                <p className="text-sm font-medium text-zinc-500">Empty graph</p>
                <p className="text-xs text-zinc-600 mt-1">Paste a document in the Ingest panel to populate it</p>
              </div>
              <div className="flex gap-2 text-[10px] text-zinc-700">
                <span className="px-2 py-1 rounded border border-zinc-800">8-K filing</span>
                <span className="px-2 py-1 rounded border border-zinc-800">Press release</span>
                <span className="px-2 py-1 rounded border border-zinc-800">Contract</span>
              </div>
            </div>
          ) : (
            <GraphCanvas nodes={nodes} edges={edges} selectedNodeId={selectedNodeId} onSelectNode={selectNode} onMoveNode={moveNode} />
          )}
        </div>

        {/* Right sidebar: Query / LLM */}
        <div
          className="relative flex flex-col border-l border-zinc-800 bg-zinc-900/30 shrink-0"
          style={{ width: rightCollapsed ? 40 : rightWidth, transition: resizing ? 'none' : 'width 300ms' }}
        >
          {rightCollapsed ? (
            <button onClick={() => setRightCollapsed(false)} className="h-full flex items-center justify-center hover:bg-zinc-800 transition-colors">
              <PanelRightOpen className="w-4 h-4 text-zinc-500" />
            </button>
          ) : (
            <>
              <div
                onMouseDown={() => setResizing('right')}
                className="absolute top-0 -left-1 h-full w-2.5 cursor-col-resize hover:bg-zinc-600 active:bg-zinc-500 transition-colors z-10"
              />
              <div className="h-9 border-b border-zinc-800 flex items-center shrink-0">
                <button
                  onClick={() => setRightTab('query')}
                  className={`flex-1 h-full text-[9px] font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1 ${
                    rightTab === 'query' ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <Search className="w-2.5 h-2.5" /> Query
                </button>
                <button
                  onClick={() => setRightTab('triples')}
                  className={`flex-1 h-full text-[9px] font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1 ${
                    rightTab === 'triples' ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <Database className="w-2.5 h-2.5" /> Triples
                </button>
                <button
                  onClick={() => setRightTab('ontology')}
                  className={`flex-1 h-full text-[9px] font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1 ${
                    rightTab === 'ontology' ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <BookOpen className="w-2.5 h-2.5" /> Ontology
                </button>
                <button
                  onClick={() => setRightTab('llm')}
                  className={`flex-1 h-full text-[9px] font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1 ${
                    rightTab === 'llm' ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <Terminal className="w-2.5 h-2.5" /> LLM
                </button>
                <button
                  onClick={() => setRightTab('agent')}
                  className={`flex-1 h-full text-[9px] font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1 ${
                    rightTab === 'agent' ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <Bot className="w-2.5 h-2.5" /> Agent
                </button>
                <button onClick={() => setRightCollapsed(true)} className="w-9 h-full flex items-center justify-center text-zinc-600 hover:text-zinc-300 transition-colors shrink-0">
                  <PanelRightClose className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                {rightTab === 'query' ? (
                  <QueryPanel />
                ) : rightTab === 'triples' ? (
                  <TripleStorePanel />
                ) : rightTab === 'ontology' ? (
                  <OntologyPanel />
                ) : rightTab === 'llm' ? (
                  <LlmPanel />
                ) : (
                  <AgentPanel />
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
