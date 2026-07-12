import { 
  Layers, Activity, Search, Bot, Wrench, PanelRightClose, PanelRightOpen, Terminal
} from 'lucide-react';
import { BuildPanel } from './panels/BuildPanel';
import { QueryExplorePanel } from './panels/QueryExplorePanel';
import { AssistantPanel } from './panels/AssistantPanel';
import { ToolsPanel } from './panels/ToolsPanel';
import { ReasoningPanel } from './ReasoningPanel';

interface SidebarProps {
  activeTab: 'build' | 'reason' | 'query' | 'assistant' | 'tools';
  setActiveTab: (tab: 'build' | 'reason' | 'query' | 'assistant' | 'tools') => void;
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
  width: number;
  setWidth: (width: number) => void;
  resizing: boolean;
  setResizing: (resizing: boolean) => void;
  buildSection: 'ingest' | 'construct' | 'enrich';
  setBuildSection: (section: 'ingest' | 'construct' | 'enrich') => void;
}

const TAB_INFO = [
  { key: 'build' as const, icon: Layers, label: 'Build' },
  { key: 'reason' as const, icon: Activity, label: 'Reason' },
  { key: 'query' as const, icon: Search, label: 'Query' },
  { key: 'assistant' as const, icon: Bot, label: 'Assistant' },
  { key: 'tools' as const, icon: Wrench, label: 'Tools' },
];

export function Sidebar({
  activeTab,
  setActiveTab,
  collapsed,
  setCollapsed,
  width,
  setWidth,
  resizing,
  setResizing,
  buildSection,
  setBuildSection,
}: SidebarProps) {

  // Map tabs to titles and icons for the header of the sidebar
  const getHeaderInfo = () => {
    switch (activeTab) {
      case 'build':
        return { title: 'Build & Curate', sub: 'Model & Ingestion Workspace', icon: Layers };
      case 'reason':
        return { title: 'Reasoning Engine', sub: 'Spread & Logic Solver', icon: Activity };
      case 'query':
        return { title: 'Explore & Query', sub: 'Pattern & Triples Inspector', icon: Search };
      case 'assistant':
        return { title: 'AI Assistant', sub: 'Tacit Knowledge Partner', icon: Bot };
      case 'tools':
        return { title: 'Developer Tools', sub: 'Skills & State Inspector', icon: Wrench };
    }
  };

  const headerInfo = getHeaderInfo();
  const HeaderIcon = headerInfo.icon;

  if (collapsed) {
    return (
      <div className="w-12 border-l border-zinc-800 bg-zinc-950 flex flex-col items-center py-4 shrink-0 justify-between">
        <button
          onClick={() => setCollapsed(false)}
          className="p-2 rounded bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-white transition-all shadow"
          title="Expand Sidebar"
        >
          <PanelRightOpen className="w-4 h-4" />
        </button>
        <div className="flex flex-col gap-4 text-zinc-600 font-mono text-[9px] uppercase tracking-widest writing-mode-vertical select-none py-10">
          workspace panel
        </div>
      </div>
    );
  }

  return (
    <aside
      id="sidebar"
      className="shrink-0 border-l border-zinc-800 bg-zinc-950 flex relative overflow-hidden"
      style={{ width, transition: resizing ? 'none' : 'width 300ms' }}
    >
      {/* Drag Resize Handle (Left edge) */}
      <div
        onMouseDown={() => setResizing(true)}
        className="absolute top-0 left-0 h-full w-1.5 cursor-col-resize hover:bg-zinc-700/50 active:bg-zinc-500 transition-colors z-20"
      />

      {/* 1. LEFT EDGE VERTICAL ICON RAIL */}
      <div className="w-16 shrink-0 border-r border-zinc-800/80 bg-zinc-950/40 flex flex-col items-center py-4 justify-between select-none">
        <div className="flex flex-col gap-6 items-center w-full">
          {TAB_INFO.map((tab) => {
            const Icon = tab.icon;
            const isSelected = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex flex-col items-center gap-1 group relative w-full py-1 transition-all ${
                  isSelected ? 'text-indigo-400' : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                <div
                  className={`p-1.5 rounded transition-colors ${
                    isSelected ? 'bg-indigo-500/10 text-indigo-400' : 'text-zinc-500 group-hover:text-zinc-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                </div>
                <span className="text-[9px] font-semibold tracking-tight">{tab.label}</span>
                {isSelected && (
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-[2px] h-6 bg-indigo-500 rounded-l" />
                )}
              </button>
            );
          })}
        </div>

        {/* Collapse button */}
        <button
          onClick={() => setCollapsed(true)}
          className="p-1.5 rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-900 transition-colors"
          title="Minimize Workspace"
        >
          <PanelRightClose className="w-4 h-4" />
        </button>
      </div>

      {/* 2. SIDEBAR PANEL CONTENTS */}
      <div className="flex-1 flex flex-col min-w-0 bg-zinc-950/20">
        {/* Active Panel Header */}
        <div className="h-11 border-b border-zinc-800/80 px-4 flex items-center justify-between bg-zinc-900/10 shrink-0 select-none">
          <h2 className="text-[11px] font-bold text-white tracking-wider uppercase flex items-center gap-2">
            <HeaderIcon className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span>{headerInfo.title}</span>
          </h2>
          <span className="text-[9px] font-mono text-zinc-500">{headerInfo.sub}</span>
        </div>

        {/* Body Panel Wrapper */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'build' && (
            <BuildPanel section={buildSection} setSection={setBuildSection} />
          )}
          {activeTab === 'reason' && <ReasoningPanel />}
          {activeTab === 'query' && <QueryExplorePanel />}
          {activeTab === 'assistant' && <AssistantPanel />}
          {activeTab === 'tools' && <ToolsPanel />}
        </div>
      </div>
    </aside>
  );
}
