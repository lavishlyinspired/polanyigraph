// Real backend only, no demo data. An empty graph shows an ingest prompt
// (acceptance criterion #1 in docs/MVP_PLAN.md).
//
// Layout refactored to align with Google AI Studio UI principles:
// - Single right sidebar with a vertical activity bar/icon rail.
// - Clean header, with pings and status indicators moved to the footer.
// - Floating contextual node inspector overlay on the canvas.
import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import {
  Network,
  Zap,
  FolderOpen,
  ChevronDown,
  History,
  Sparkles,
  Play,
  Loader,
} from 'lucide-react';
import { GraphCanvas } from './components/GraphCanvas';
import { GraphsPopover } from './components/GraphsPopover';
import { HistoryPopover } from './components/HistoryPopover';
import { Sidebar } from './components/Sidebar';
import { StatusFooter } from './components/StatusFooter';
import { NodeInspectorCard } from './components/NodeInspectorCard';
import { LeftNavigation, type PageType } from './components/LeftNavigation';
import { DocumentsPage } from './components/pages/DocumentsPage';
import { LogicPage } from './components/pages/LogicPage';
import { InferencePage } from './components/pages/InferencePage';
import { QueryPage } from './components/pages/QueryPage';
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
  
  // Page routing
  const [activePage, setActivePage] = useState<PageType>('workspace');

  // Consolidated single sidebar and tab states
  const [activeTab, setActiveTab] = useState<'build' | 'reason' | 'query' | 'assistant' | 'tools'>('build');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR);
  const [resizing, setResizing] = useState(false);
  const [buildSection, setBuildSection] = useState<'ingest' | 'construct' | 'enrich'>('ingest');

  const [showHistory, setShowHistory] = useState(false);
  const [showGraphs, setShowGraphs] = useState(false);
  
  const {
    nodes, edges, facts, selectedNodeId, loading, autoRunning, graphId,
    loadGraph, loadHistory, loadRules, loadGraphs, loadOntology, selectNode, moveNode,
    loadPendingFacts, loadApprovedFacts, pendingFacts, loadReasonFacts, reason,
  } = useGraphStore();

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null;

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

  // Sidebar drag resize handler
  useEffect(() => {
    if (!resizing) return;
    const handleMove = (e: MouseEvent) => {
      setSidebarWidth(Math.min(MAX_SIDEBAR, Math.max(MIN_SIDEBAR, window.innerWidth - e.clientX)));
    };
    const handleUp = () => setResizing(false);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [resizing]);

  const handleRunLoop = async () => {
    try {
      await reason();
    } catch {
      // Errors are handled inside the Zustand store via toasts
    }
  };

  const empty = nodes.length === 0;

  return (
    <div className={`h-screen w-screen flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden ${resizing ? 'select-none cursor-col-resize' : ''}`}>
      <Toaster theme="dark" position="bottom-right" />

      {/* TOP HEADER - Minimal & Elegant Google AI Studio Style */}
      <header className="h-12 border-b border-zinc-800/80 bg-zinc-900/40 backdrop-blur flex items-center justify-between px-4 shrink-0 z-20">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded bg-blue-600 flex items-center justify-center shadow shadow-blue-500/20">
              <Network className="w-4 h-4 text-white" />
            </div>
            <div className="flex items-baseline gap-2">
              <h1 className="text-xs font-semibold tracking-tight text-white">
                ⬡ Neurosymbolic KG
              </h1>
              <span className="text-[9px] text-zinc-500 font-mono">
                {health ? `ontology: ${health.ontologyRepository}` : 'connecting...'}
              </span>
            </div>
          </div>

          <div className="h-4 w-[1px] bg-zinc-800" />

          {/* Graph Selector (Dropdown Trigger) */}
          <div className="relative">
            <button
              onClick={() => {
                setShowGraphs((v) => !v);
                setShowHistory(false);
              }}
              className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium rounded border border-zinc-800 bg-zinc-900/40 text-zinc-300 hover:bg-zinc-800/80 hover:text-white transition-all select-none"
            >
              <FolderOpen className="w-3.5 h-3.5 text-zinc-400" />
              <span>{graphId || 'default'}</span>
              <ChevronDown className="w-3 h-3 text-zinc-500" />
            </button>
            {showGraphs && <GraphsPopover onClose={() => setShowGraphs(false)} />}
          </div>

          {/* Ingest History Trigger */}
          <div className="relative">
            <button
              onClick={() => {
                setShowHistory((v) => !v);
                setShowGraphs(false);
              }}
              className={`p-1 rounded border transition-all ${
                showHistory 
                  ? 'border-zinc-700 bg-zinc-800 text-white' 
                  : 'border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:text-white hover:bg-zinc-800/80'
              }`}
              title="View Ingestion History"
            >
              <History className="w-3.5 h-3.5" />
            </button>
            {showHistory && <HistoryPopover onClose={() => setShowHistory(false)} />}
          </div>
        </div>

        {/* Header Actions & Badges */}
        <div className="flex items-center gap-3">
          {/* Pulsing Auto-run badge */}
          {autoRunning && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/25 text-amber-400 text-[10px] font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
              <span>AUTO-RUN ACTIVE</span>
            </div>
          )}

          {/* Pending Cognitive Review Notification Badge */}
          {pendingFacts.length > 0 && (
            <button
              onClick={() => {
                setActivePage('documents');
              }}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 hover:text-blue-300 text-[10px] font-medium transition-all"
              title="Click to review implicit facts"
            >
              <Sparkles className="w-3.5 h-3.5 text-blue-400" />
              <span>✦ {pendingFacts.length} Pending</span>
            </button>
          )}

          {/* Direct loop reasoning button */}
          <button
            onClick={handleRunLoop}
            disabled={loading || autoRunning}
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-[11px] font-medium transition-all"
          >
            <Play className="w-3 h-3 fill-white" />
            <span>Run Neurosymbolic Loop</span>
          </button>
        </div>
      </header>

      {/* MAIN VIEWPORT */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Navigation Icon Rail */}
        <LeftNavigation activePage={activePage} onPageChange={setActivePage} />

        {/* Content routing view container */}
        <div className="flex-1 flex overflow-hidden relative">
          {activePage === 'workspace' && (
            <div className="flex-1 flex overflow-hidden">
              {/* Canvas - Dominates Viewport */}
              <div className="flex-1 relative overflow-hidden bg-zinc-950">
                {empty && loading ? (
                  <LoadingSkeleton />
                ) : empty ? (
                  <div className="h-full flex flex-col items-center justify-center text-zinc-600 gap-4">
                    <Network className="w-12 h-12 text-zinc-800 animate-pulse" />
                    <div className="text-center select-none">
                      <p className="text-sm font-medium text-zinc-500">Empty Graph Canvas</p>
                      <p className="text-xs text-zinc-600 mt-1">Paste source documentation in the Build panel to begin</p>
                    </div>
                    <div className="flex gap-2 text-[10px] text-zinc-700 select-none">
                      <span className="px-2 py-1 rounded border border-zinc-900 bg-zinc-900/20">SEC 8-K filings</span>
                      <span className="px-2 py-1 rounded border border-zinc-900 bg-zinc-900/20">Press releases</span>
                      <span className="px-2 py-1 rounded border border-zinc-900 bg-zinc-900/20">Tacit contracts</span>
                    </div>
                  </div>
                ) : (
                  <>
                    <GraphCanvas 
                      nodes={nodes} 
                      edges={edges} 
                      selectedNodeId={selectedNodeId} 
                      onSelectNode={selectNode} 
                      onMoveNode={moveNode} 
                    />
                    
                    {/* Contextual Floating Node Inspector Overlay */}
                    {selectedNode && (
                      <NodeInspectorCard
                        node={selectedNode}
                        facts={facts}
                        onClose={() => selectNode(null)}
                        onEditShortcut={() => {
                          setActiveTab('build');
                          setBuildSection('construct');
                        }}
                      />
                    )}
                  </>
                )}
              </div>

              {/* Sidebar - Single Consolidated Panel */}
              <Sidebar
                activeTab={activeTab}
                setActiveTab={setActiveTab}
                collapsed={sidebarCollapsed}
                setCollapsed={setSidebarCollapsed}
                width={sidebarWidth}
                setWidth={setSidebarWidth}
                resizing={resizing}
                setResizing={setResizing}
                buildSection={buildSection}
                setBuildSection={setBuildSection}
              />
            </div>
          )}

          {activePage === 'documents' && <DocumentsPage />}
          {activePage === 'logic' && <LogicPage />}
          {activePage === 'inference' && <InferencePage />}
          {activePage === 'query' && <QueryPage />}
        </div>
      </div>

      {/* FOOTER - Relocated Telemetry & Status Indicators */}
      <StatusFooter health={health} />
    </div>
  );
}
