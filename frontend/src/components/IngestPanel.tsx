// Left sidebar "Ingest" tab -- its own tab, separate from Construct (per
// explicit direction). Paste real text, extract into the real graph.
import { useState } from 'react';
import { AlertCircle, RefreshCw, Clock, ChevronRight, Zap, Info, Trash2 } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';

const DOC_HINTS = [
  { label: 'SEC Filing', example: '10-K, 8-K, proxy statement...' },
  { label: 'Press Release', example: 'earnings, M&A, product launch...' },
  { label: 'Contract', example: 'agreement, terms, obligations...' },
  { label: 'News Article', example: 'report, analysis, interview...' },
];

export function IngestPanel() {
  const { loading, error, ingest, loadGraph, history } = useGraphStore();
  const [text, setText] = useState('');

  const charCount = text.length;
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;

  const handleIngest = async () => {
    if (!text.trim()) return;
    await ingest(text);
    setText('');
  };

  const handleLoadHint = (hint: string) => {
    setText((prev) => prev + (prev ? '\n\n' : '') + `[${hint}] `);
  };

  const handleClear = () => {
    setText('');
  };

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      {/* Header / How it works */}
      <div className="p-4 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex gap-2">
          <Zap className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-[10px] text-zinc-400 leading-relaxed">
            Paste any document text below. The LLM extracts{' '}
            <span className="text-amber-400 font-bold">entities</span> and{' '}
            <span className="text-emerald-400 font-bold">relationships</span>, then stores them in
            the knowledge graph. Each ingest is a new source document in the graph.
          </div>
        </div>
      </div>

      {/* Document type hints */}
      <div className="px-4 pt-3 pb-2 border-b border-zinc-800">
        <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-bold mb-2 flex items-center gap-1.5">
          <Info className="w-3 h-3" /> Paste a document
        </div>
        <div className="flex flex-wrap gap-1.5">
          {DOC_HINTS.map((hint) => (
            <button
              key={hint.label}
              onClick={() => handleLoadHint(hint.label)}
              className="px-2.5 py-1 rounded border border-zinc-800 text-[10px] text-zinc-500 hover:text-blue-300 hover:border-blue-500/40 transition-colors"
              title={hint.example}
            >
              {hint.label}
            </button>
          ))}
        </div>
      </div>

      {/* Text input area */}
      <div className="flex-1 flex flex-col p-4 gap-2 min-h-0">
        <div className="relative flex-1 min-h-0">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste a document — SEC filing, press release, contract, article, or any structured text. The more context, the richer the extracted graph."
            className="w-full h-full min-h-[160px] bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-white placeholder:text-zinc-600 resize-none focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
          />
          {charCount > 0 && (
            <div className="absolute bottom-2 right-2 flex items-center gap-2 text-[9px] text-zinc-600">
              <span>{wordCount.toLocaleString()} words</span>
              <span>·</span>
              <span>{charCount.toLocaleString()} chars</span>
            </div>
          )}
        </div>

        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => void handleIngest()}
            disabled={loading || !text.trim()}
            className="flex-1 h-9 bg-blue-600 text-onaccent hover:bg-blue-500 text-xs font-bold rounded-lg flex items-center justify-center gap-2 disabled:opacity-40 transition-colors shadow shadow-blue-500/20"
          >
            {loading ? (
              <>
                <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Extracting → Storing
              </>
            ) : (
              <>
                <Zap className="w-3.5 h-3.5" /> Extract → Graph
              </>
            )}
          </button>
          {text.trim() && (
            <button
              onClick={handleClear}
              className="h-9 px-3 rounded-lg border border-zinc-700 text-zinc-400 hover:text-white text-xs flex items-center gap-1.5 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {error && (
          <div className="flex items-start gap-2 p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <div className="flex-1 break-words">{error}</div>
            <button onClick={() => void loadGraph()} className="shrink-0 p-1 rounded hover:bg-red-500/20 transition-colors" title="Retry">
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>

      {/* Recent ingests */}
      {history.length > 0 && (
        <div className="p-4 border-t border-zinc-800">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" /> Recent Ingests
          </h3>
          <div className="space-y-1.5">
            {history.slice(0, 4).map((event) => (
              <div
                key={event.id}
                className="p-2.5 rounded-lg border border-zinc-800 bg-zinc-900 group"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] text-zinc-300 line-clamp-2 break-words">
                      {event.text.slice(0, 120)}{event.text.length > 120 ? '...' : ''}
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-[9px] text-zinc-600">
                      <span className="text-emerald-400 font-bold">{event.entityCount} entities</span>
                      <span>·</span>
                      <span className="text-sky-400 font-bold">{event.relationshipCount} edges</span>
                      {event.droppedCount > 0 && (
                        <>
                          <span>·</span>
                          <span className="text-amber-400">{event.droppedCount} dropped</span>
                        </>
                      )}
                      <span>·</span>
                      <span>{new Date(event.createdAt).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-zinc-700 shrink-0 mt-1" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
