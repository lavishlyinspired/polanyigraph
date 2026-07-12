// Consolidated right sidebar (UI_REFACTOR_PLAN.md §2): 5 tabs (Build/Reason/
// Query/Assistant/Tools) via an icon rail embedded at the sidebar's own left
// margin, replacing the old 4-tab left sidebar + 7-tab right sidebar.
// Ported from .claude/docs/mocks/polanyigraph, unchanged.
import { Layers, Activity, Search, Bot, Wrench, PanelRightClose, PanelRightOpen } from 'lucide-react';
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
  buildSection: 'ingest' | 'construct' | 'enrich' | null;
  setBuildSection: (section: 'ingest' | 'construct' | 'enrich' | null) => void;
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
  resizing,
  setResizing,
  buildSection,
  setBuildSection,
}: SidebarProps) {
  const getHeaderInfo = () => {
    switch (activeTab) {
      case 'build':
        return { title: 'Build & Curate', sub: 'Ingest, Construct, Enrich', icon: Layers };
      case 'reason':
        return { title: 'Reasoning Engine', sub: 'Spread & Logic Solver', icon: Activity };
      case 'query':
        return { title: 'Explore & Query', sub: 'Pattern & Triples Inspector', icon: Search };
      case 'assistant':
        return { title: 'AI Assistant', sub: 'Ask or Act on the Graph', icon: Bot };
      case 'tools':
        return { title: 'Developer Tools', sub: 'Skills & Memory Inspector', icon: Wrench };
    }
  };

  const headerInfo = getHeaderInfo();
  const HeaderIcon = headerInfo.icon;

  if (collapsed) {
    return (
      <div className="w-12 border-l border-zinc-800 bg-chrome flex flex-col items-center py-4 shrink-0 justify-between">
        <button
          onClick={() => setCollapsed(false)}
          className="p-2 rounded bg-zinc-900 hover:bg-zinc-800 text-zinc-200 hover:text-white transition-all shadow"
          title="Expand Sidebar"
        >
          <PanelRightOpen className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <aside
      className="shrink-0 border-l border-zinc-800 bg-chrome flex relative overflow-hidden"
      style={{ width, transition: resizing ? 'none' : 'width 300ms' }}
    >
      <div onMouseDown={() => setResizing(true)} className="absolute top-0 left-0 h-full w-1.5 cursor-col-resize hover:bg-zinc-700/50 active:bg-zinc-500 transition-colors z-20" />

      <div className="w-16 shrink-0 border-r border-zinc-800/80 bg-zinc-950/40 flex flex-col items-center py-4 justify-between select-none">
        <div className="flex flex-col gap-6 items-center w-full">
          {TAB_INFO.map((tab) => {
            const Icon = tab.icon;
            const isSelected = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex flex-col items-center gap-1 group relative w-full py-1 transition-all ${isSelected ? 'text-blue-400' : 'text-zinc-200 hover:text-white'}`}
              >
                <div className={`p-1.5 rounded transition-colors ${isSelected ? 'bg-blue-500/10 text-blue-400' : 'text-zinc-200 group-hover:text-white'}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <span className="text-[9px] font-semibold tracking-tight">{tab.label}</span>
                {isSelected && <div className="absolute right-0 top-1/2 -translate-y-1/2 w-[2px] h-6 bg-blue-500 rounded-l" />}
              </button>
            );
          })}
        </div>

        <button onClick={() => setCollapsed(true)} className="p-1.5 rounded text-zinc-200 hover:text-white hover:bg-zinc-900 transition-colors" title="Minimize Workspace">
          <PanelRightClose className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 flex flex-col min-w-0 bg-zinc-950/20">
        <div className="h-11 border-b border-zinc-800/80 px-4 flex items-center justify-between bg-zinc-900/10 shrink-0 select-none">
          <h2 className="text-[11px] font-bold text-white tracking-wider uppercase flex items-center gap-2">
            <HeaderIcon className="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span>{headerInfo.title}</span>
          </h2>
          <span className="text-[9px] font-mono text-zinc-500">{headerInfo.sub}</span>
        </div>

        <div className="flex-1 overflow-hidden">
          {activeTab === 'build' && <BuildPanel section={buildSection} setSection={setBuildSection} />}
          {activeTab === 'reason' && <ReasoningPanel />}
          {activeTab === 'query' && <QueryExplorePanel />}
          {activeTab === 'assistant' && <AssistantPanel />}
          {activeTab === 'tools' && <ToolsPanel />}
        </div>
      </div>
    </aside>
  );
}
