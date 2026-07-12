// Documents Lab (UI_REFACTOR_PLAN.md §3.1): canvas-free, full-width
// duplicate of the sidebar's Build > Ingest/Enrich sections -- same real
// store actions, richer 3-column layout (full Source Registry instead of
// the sidebar's last-4, larger extraction textarea, full-height review
// queue). Ported from .claude/docs/mocks/polanyigraph, unchanged.
import { useState } from 'react';
import { Zap, Info, FileText, Check, X, Loader, ChevronDown, ChevronRight, Trash2, AlertCircle, Clock, BookOpen, Search, Sparkles } from 'lucide-react';
import { useGraphStore } from '../../stores/graphStore';
import { useThemeStore } from '../../stores/themeStore';
import type { HeuristicType } from '../../lib/api';

const HEURISTIC_LABELS: Record<HeuristicType, string> = {
  presupposition: 'Presupposition',
  conversational_implicature: 'Conversational Implicature',
  factual_impact: 'Factual Impact',
  image_schema: 'Image Schema',
  metonymic_coercion: 'Metonymic Coercion',
  moral_value_coercion: 'Moral-Value Coercion',
  symbolic_coercion: 'Symbolic Coercion',
  event_sequence: 'Event Sequence',
  causal_relation: 'Causal Relation',
  implied_future_event: 'Implied Future Event',
  implied_non_event: 'Implied Non-Event',
};

const DOC_HINTS = [
  { label: 'SEC Filing', example: '10-K, 8-K, proxy statement...' },
  { label: 'Press Release', example: 'earnings, M&A, product launch...' },
  { label: 'Contract', example: 'agreement, terms, obligations...' },
  { label: 'News Article', example: 'report, analysis, interview...' },
];

function heuristicHue(type: string): number {
  let hash = 0;
  for (let i = 0; i < type.length; i++) hash = (hash * 31 + type.charCodeAt(i)) >>> 0;
  return hash % 360;
}

export function DocumentsPage() {
  const { loading, error, ingest, history, pendingFacts, approvedFacts, enriching, enrich, approveFact, rejectFact, loadGraph } = useGraphStore();
  const isLight = useThemeStore((s) => s.theme === 'light');

  const [text, setText] = useState('');
  const [docFilter, setDocFilter] = useState('');
  const [selectedDoc, setSelectedDoc] = useState<(typeof history)[0] | null>(null);
  const [showApproved, setShowApproved] = useState(false);

  const charCount = text.length;
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;

  const handleIngest = async () => {
    if (!text.trim()) return;
    await ingest(text);
    setText('');
  };

  const handleLoadHint = (hint: string) => setText((prev) => prev + (prev ? '\n\n' : '') + `[${hint}] `);
  const handleClear = () => setText('');

  const filteredHistory = history.filter((event) => event.text.toLowerCase().includes(docFilter.toLowerCase()));
  const sortedPending = [...pendingFacts].sort((a, b) => b.confidence - a.confidence);

  return (
    <div className="h-full flex-1 flex overflow-hidden bg-zinc-950">
      {/* Source Registry */}
      <div className="w-80 border-r border-zinc-800 flex flex-col min-w-0 bg-zinc-950/20">
        <div className="p-4 border-b border-zinc-800 bg-zinc-900/10 flex shrink-0 justify-between items-center">
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-zinc-400" /> Source Registry
            </h3>
            <p className="text-[9px] text-zinc-500 mt-0.5">{history.length} Document{history.length !== 1 ? 's' : ''} Loaded</p>
          </div>
          <div className="text-[10px] font-mono text-blue-400 font-semibold px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20">
            {history.reduce((acc, h) => acc + h.entityCount, 0)} Entities
          </div>
        </div>

        <div className="p-3 border-b border-zinc-800 shrink-0">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-600" />
            <input
              type="text"
              placeholder="Search source logs..."
              value={docFilter}
              onChange={(e) => setDocFilter(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded pl-8 pr-2.5 py-1.5 text-[11px] text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
          {filteredHistory.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-center text-zinc-600">
              <FileText className="w-8 h-8 text-zinc-800 mb-2" />
              <p className="text-[10px]">No ingested sources match.</p>
            </div>
          ) : (
            filteredHistory.map((event) => (
              <div
                key={event.id}
                onClick={() => setSelectedDoc(event)}
                className={`p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedDoc?.id === event.id ? 'border-blue-500 bg-blue-500/5' : 'border-zinc-800 bg-zinc-900/40 hover:bg-zinc-900/80 hover:border-zinc-700'
                }`}
              >
                <div className="text-[11px] text-zinc-200 line-clamp-3 font-sans leading-relaxed">{event.text}</div>
                <div className="flex items-center gap-2 mt-2 pt-2 border-t border-zinc-800/60 text-[9px] text-zinc-500 flex-wrap">
                  <span className="text-emerald-400 font-bold font-mono">{event.entityCount} ent</span>
                  <span>·</span>
                  <span className="text-sky-400 font-bold font-mono">{event.relationshipCount} rel</span>
                  <span>·</span>
                  <span className="font-mono">{new Date(event.createdAt).toLocaleDateString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Ingestion & Extraction Lab */}
      <div className="flex-1 border-r border-zinc-800 flex flex-col min-w-0">
        <div className="p-4 border-b border-zinc-800 bg-zinc-900/10 shrink-0 flex items-center justify-between">
          <div>
            <h2 className="text-[13px] font-bold text-white tracking-wider uppercase flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" /> Ingestion &amp; Extraction Lab
            </h2>
            <p className="text-[10px] text-zinc-500 mt-0.5">Translate raw documents into formal knowledge-graph representations via LLM models</p>
          </div>
        </div>

        {selectedDoc ? (
          <div className="m-4 p-4 rounded-lg border border-blue-500/30 bg-blue-500/5 space-y-3 shrink-0">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-blue-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                <BookOpen className="w-3.5 h-3.5" /> Registered Source Detail
              </span>
              <button onClick={() => setSelectedDoc(null)} className="text-[9px] text-zinc-500 hover:text-white underline font-mono">
                Close Viewer
              </button>
            </div>
            <div className="text-xs text-zinc-300 leading-relaxed max-h-36 overflow-y-auto font-sans p-2 rounded bg-zinc-950/40 border border-zinc-800">{selectedDoc.text}</div>
            <div className="flex items-center gap-4 text-[10px] font-mono text-zinc-500">
              <span>
                Entities: <strong className="text-zinc-300">{selectedDoc.entityCount} nodes</strong>
              </span>
              <span>
                Relationships: <strong className="text-zinc-300">{selectedDoc.relationshipCount} edges</strong>
              </span>
              {selectedDoc.droppedCount > 0 && (
                <span className="text-amber-400">
                  Dropped: <strong>{selectedDoc.droppedCount}</strong>
                </span>
              )}
            </div>
          </div>
        ) : (
          <div className="m-4 p-3 rounded-lg border border-zinc-800 bg-zinc-900/40 flex items-start gap-2.5 shrink-0">
            <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
            <div className="text-[10px] text-zinc-400 leading-relaxed">
              <strong className="text-zinc-200">Ingestion Pipeline:</strong> Select a loaded document from the left list to view its registered
              extraction trace, or paste a new source segment below to trigger structured ontological processing.
            </div>
          </div>
        )}

        <div className="flex-1 flex flex-col p-4 gap-4 min-h-0">
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono">Document Context Buffer</label>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-zinc-500 font-mono">Load Preset:</span>
                <div className="flex gap-1.5">
                  {DOC_HINTS.map((hint) => (
                    <button
                      key={hint.label}
                      onClick={() => handleLoadHint(hint.label)}
                      className="px-2 py-0.5 rounded border border-zinc-800 text-[9px] text-zinc-400 hover:text-white hover:border-zinc-600 transition-colors"
                      title={hint.example}
                    >
                      {hint.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="relative flex-1 min-h-[250px]">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste SEC filings, financial bulletins, press releases, corporate charter elements, or any text segment you want formalized. The LLM parses it into logical triples matching the ontology classes."
                className="w-full h-full min-h-[240px] bg-zinc-950 border border-zinc-800 rounded-lg p-3.5 text-xs text-white placeholder:text-zinc-700 resize-none focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-sans leading-relaxed"
              />
              {charCount > 0 && (
                <div className="absolute bottom-3 right-3 flex items-center gap-2 text-[10px] text-zinc-600 font-mono">
                  <span>{wordCount.toLocaleString()} words</span>
                  <span>·</span>
                  <span>{charCount.toLocaleString()} chars</span>
                </div>
              )}
            </div>
          </div>

          <div className="flex gap-3 shrink-0">
            <button
              onClick={() => void handleIngest()}
              disabled={loading || !text.trim()}
              className="flex-1 h-10 bg-blue-600 text-onaccent hover:bg-blue-500 text-xs font-bold rounded-lg flex items-center justify-center gap-2 disabled:opacity-40 transition-all"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-onaccent border-t-transparent rounded-full animate-spin" />
                  Extracting Entity-Relationship Networks...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4 fill-onaccent" /> Run Document Knowledge Extraction
                </>
              )}
            </button>
            {text.trim() && (
              <button onClick={handleClear} className="h-10 px-4 rounded-lg border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-900 transition-colors" title="Clear content">
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>

          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1 break-words">{error}</div>
              <button onClick={() => void loadGraph()} className="shrink-0 p-1 rounded hover:bg-red-500/20 transition-colors" title="Retry">
                <Loader className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Polanyi Review Hub */}
      <div className="w-96 border-l border-zinc-800 flex flex-col min-w-0 bg-zinc-950/40">
        <div className="p-4 border-b border-zinc-800 bg-zinc-900/10 flex shrink-0 justify-between items-center">
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-sky-400" /> Implicit Facts Review
            </h3>
            <p className="text-[9px] text-zinc-500 mt-0.5">Polanyi Tacit Knowledge Heuristics</p>
          </div>
          <span className="px-2 py-0.5 rounded text-[9px] bg-sky-500/10 border border-sky-500/30 text-sky-400 font-mono font-bold">{pendingFacts.length} Pending</span>
        </div>

        <div className="p-3 border-b border-zinc-800 shrink-0 bg-zinc-950/20">
          <textarea
            value={text}
            placeholder="Review against source text context..."
            readOnly
            className="w-full h-16 bg-zinc-900/30 border border-zinc-800 rounded p-2 text-[10px] text-zinc-500 placeholder:text-zinc-600 resize-none focus:outline-none"
          />
          <button
            onClick={() => void enrich(text || (selectedDoc ? selectedDoc.text : ''))}
            disabled={enriching || (!text.trim() && !selectedDoc)}
            className="w-full mt-2 h-7 bg-zinc-800 text-zinc-200 hover:bg-zinc-700 text-[10px] font-bold rounded flex items-center justify-center gap-1.5 disabled:opacity-40 transition-colors border border-zinc-700/40"
          >
            {enriching ? (
              <>
                <Loader className="w-3 h-3 animate-spin" /> Mining implicit linkages...
              </>
            ) : (
              <>
                <Sparkles className="w-3 h-3 text-sky-400" /> Trigger Heuristic Enrichment
              </>
            )}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
          <div className="space-y-2">
            <div className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider font-mono">Pending Enrichment Queue ({sortedPending.length})</div>
            {sortedPending.length === 0 ? (
              <div className="p-8 rounded-lg border border-dashed border-zinc-800 text-center text-zinc-600">
                <Sparkles className="w-6 h-6 mx-auto mb-2 text-zinc-800" />
                <p className="text-[10px]">No pending review facts. Ingest a document and trigger enrichment above.</p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {sortedPending.map((fact) => {
                  const hue = heuristicHue(fact.heuristicType);
                  return (
                    <div
                      key={fact.id}
                      className="p-3 rounded-lg border space-y-2.5"
                      style={{
                        borderColor: `hsl(${hue}, 45%, ${isLight ? 78 : 25}%)`,
                        backgroundColor: `hsl(${hue}, 45%, ${isLight ? 93 : 6}%)`,
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="px-2 py-0.5 rounded text-[8px] font-mono font-bold uppercase tracking-wider" style={{ backgroundColor: `hsl(${hue}, 55%, 45%)`, color: '#000' }}>
                          {HEURISTIC_LABELS[fact.heuristicType]}
                        </span>
                        <span className="text-[9px] font-mono text-zinc-400">{(fact.confidence * 100).toFixed(0)}% Match</span>
                      </div>
                      <div className="text-[11px] text-zinc-200 font-sans leading-relaxed">{fact.text}</div>
                      {fact.anchorEntityIds.length > 0 && (
                        <div className="text-[9px] font-mono text-zinc-500 flex items-center gap-1">
                          <span className="w-1 h-1 rounded-full bg-blue-500" />
                          Anchored to: {fact.anchorEntityIds.join(', ')}
                        </div>
                      )}
                      <div className="flex gap-2 border-t border-zinc-800/40 pt-2 mt-1">
                        <button
                          onClick={() => void approveFact(fact.id)}
                          className="flex-1 h-7 rounded bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 text-[10px] font-bold flex items-center justify-center gap-1 hover:bg-emerald-500/25 transition-colors"
                        >
                          <Check className="w-3 h-3" /> Approve
                        </button>
                        <button
                          onClick={() => void rejectFact(fact.id)}
                          className="flex-1 h-7 rounded bg-rose-500/10 border border-rose-500/25 text-rose-400 text-[10px] font-bold flex items-center justify-center gap-1 hover:bg-rose-500/25 transition-colors"
                        >
                          <X className="w-3 h-3" /> Reject
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {approvedFacts.length > 0 && (
            <div className="border-t border-zinc-800/80 pt-4">
              <button
                onClick={() => setShowApproved((v) => !v)}
                className="w-full flex items-center justify-between text-[11px] font-bold text-zinc-500 uppercase tracking-wider hover:text-zinc-300 transition-colors"
              >
                <span className="flex items-center gap-1.5 font-mono">
                  <Check className="w-3.5 h-3.5 text-emerald-400" /> Approved Facts Store ({approvedFacts.length})
                </span>
                {showApproved ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>
              {showApproved && (
                <div className="space-y-2 mt-3">
                  {approvedFacts.map((fact) => (
                    <div key={fact.id} className="p-3 rounded-lg border space-y-1.5 bg-zinc-900/20 border-zinc-800/80">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono text-zinc-500 font-semibold uppercase tracking-wider">{HEURISTIC_LABELS[fact.heuristicType]}</span>
                        <span className="text-[9px] text-emerald-400 font-mono">✓ Approved</span>
                      </div>
                      <div className="text-[11px] text-zinc-300 font-sans leading-relaxed">{fact.text}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
