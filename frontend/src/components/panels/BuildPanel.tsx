// Sidebar "Build" tab (UI_REFACTOR_PLAN.md §2): accordion wrapping the
// existing, unchanged Ingest/Construct/Enrich panels -- pure composition,
// no new data or logic. Ported from .claude/docs/mocks/polanyigraph.
import { ChevronDown, ChevronRight, FileText, Layers, Sparkles } from 'lucide-react';
import { IngestPanel } from '../IngestPanel';
import { ConstructionPanel } from '../ConstructionPanel';
import { EnrichmentPanel } from '../EnrichmentPanel';
import { useGraphStore } from '../../stores/graphStore';

interface BuildPanelProps {
  section: 'ingest' | 'construct' | 'enrich' | null;
  setSection: (section: 'ingest' | 'construct' | 'enrich' | null) => void;
}

export function BuildPanel({ section, setSection }: BuildPanelProps) {
  const { pendingFacts } = useGraphStore();

  return (
    <div className="h-full flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden overflow-y-auto">
      <div className="border-b border-zinc-800">
        <button
          onClick={() => setSection(section === 'ingest' ? null : 'ingest')}
          className={`w-full px-4 py-3 flex items-center justify-between text-xs font-semibold uppercase tracking-wider transition-all duration-150 ${
            section === 'ingest' ? 'bg-zinc-900 text-white border-l-2 border-blue-500' : 'text-zinc-200 hover:text-white hover:bg-zinc-900/50'
          }`}
        >
          <div className="flex items-center gap-2">
            <FileText className={`w-3.5 h-3.5 ${section === 'ingest' ? 'text-blue-400' : 'text-zinc-300'}`} />
            <span>1. Ingest Source Text</span>
          </div>
          {section === 'ingest' ? <ChevronDown className="w-3.5 h-3.5 text-zinc-300" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-300" />}
        </button>
        {section === 'ingest' && (
          <div className="border-t border-zinc-800/50 max-h-[60vh] overflow-y-auto">
            <IngestPanel />
          </div>
        )}
      </div>

      <div className="border-b border-zinc-800">
        <button
          onClick={() => setSection(section === 'construct' ? null : 'construct')}
          className={`w-full px-4 py-3 flex items-center justify-between text-xs font-semibold uppercase tracking-wider transition-all duration-150 ${
            section === 'construct' ? 'bg-zinc-900 text-white border-l-2 border-blue-500' : 'text-zinc-200 hover:text-white hover:bg-zinc-900/50'
          }`}
        >
          <div className="flex items-center gap-2">
            <Layers className={`w-3.5 h-3.5 ${section === 'construct' ? 'text-blue-400' : 'text-zinc-300'}`} />
            <span>2. Construct &amp; Curate</span>
          </div>
          {section === 'construct' ? <ChevronDown className="w-3.5 h-3.5 text-zinc-300" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-300" />}
        </button>
        {section === 'construct' && (
          <div className="border-t border-zinc-800/50 max-h-[65vh] overflow-y-auto">
            <ConstructionPanel />
          </div>
        )}
      </div>

      <div className="border-b border-zinc-800">
        <button
          onClick={() => setSection(section === 'enrich' ? null : 'enrich')}
          className={`w-full px-4 py-3 flex items-center justify-between text-xs font-semibold uppercase tracking-wider transition-all duration-150 ${
            section === 'enrich' ? 'bg-zinc-900 text-white border-l-2 border-blue-500' : 'text-zinc-200 hover:text-white hover:bg-zinc-900/50'
          }`}
        >
          <div className="flex items-center justify-between w-full pr-1">
            <div className="flex items-center gap-2">
              <Sparkles className={`w-3.5 h-3.5 ${section === 'enrich' ? 'text-blue-400' : 'text-zinc-300'}`} />
              <span>3. Cognitive Enrichment</span>
            </div>
            <div className="flex items-center gap-2">
              {pendingFacts.length > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/25 text-blue-400 text-[9px] font-bold">
                  {pendingFacts.length} pending
                </span>
              )}
              {section === 'enrich' ? <ChevronDown className="w-3.5 h-3.5 text-zinc-300" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-300" />}
            </div>
          </div>
        </button>
        {section === 'enrich' && (
          <div className="border-t border-zinc-800/50 max-h-[60vh] overflow-y-auto">
            <EnrichmentPanel />
          </div>
        )}
      </div>
    </div>
  );
}
