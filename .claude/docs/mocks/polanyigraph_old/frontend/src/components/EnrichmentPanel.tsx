// Left sidebar "Enrich" tab (UI_PLAN.md §9.3, PLAN.md §19). Runs the 11
// Polanyi enrichment heuristics against the real graph + pasted text, then
// requires human approval before a pending :ImplicitFact counts as part of
// the graph (§7.3 human-in-the-loop) -- the backend won't filter weak
// heuristic output for you (see §19.6 step 4's symbolic_coercion finding).
import { useState } from 'react';
import { Sparkles, Info, Check, X, Loader, ChevronDown, ChevronRight } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';
import type { HeuristicType, ImplicitFact } from '../lib/api';

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

// Same deterministic hash-hue approach as GraphCanvas.tsx's domain-agnostic
// node type coloring, applied to the 11 fixed heuristic categories.
function heuristicHue(type: string): number {
  let hash = 0;
  for (let i = 0; i < type.length; i++) hash = (hash * 31 + type.charCodeAt(i)) >>> 0;
  return hash % 360;
}

function FactCard({ fact, onApprove, onReject }: { fact: ImplicitFact; onApprove?: () => void; onReject?: () => void }) {
  const hue = heuristicHue(fact.heuristicType);
  return (
    <div className="p-2.5 rounded-lg border" style={{ borderColor: `hsl(${hue}, 45%, 30%)`, backgroundColor: `hsl(${hue}, 45%, 12%)` }}>
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider" style={{ backgroundColor: `hsl(${hue}, 55%, 55%)`, color: '#000' }}>
          {HEURISTIC_LABELS[fact.heuristicType]}
        </span>
        <span className="text-[9px] text-zinc-500">{(fact.confidence * 100).toFixed(0)}%</span>
      </div>
      <div className="text-[10px] text-zinc-200 leading-relaxed">{fact.text}</div>
      {fact.anchorEntityIds.length > 0 && (
        <div className="text-[9px] text-zinc-600 mt-1">anchored to {fact.anchorEntityIds.length} entit{fact.anchorEntityIds.length === 1 ? 'y' : 'ies'}</div>
      )}
      {(onApprove || onReject) && (
        <div className="flex gap-1.5 mt-2">
          {onApprove && (
            <button onClick={onApprove} className="flex-1 h-6 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 text-[9px] font-bold flex items-center justify-center gap-1 hover:bg-emerald-500/30 transition-colors">
              <Check className="w-3 h-3" /> Approve
            </button>
          )}
          {onReject && (
            <button onClick={onReject} className="flex-1 h-6 rounded bg-rose-500/20 border border-rose-500/40 text-rose-400 text-[9px] font-bold flex items-center justify-center gap-1 hover:bg-rose-500/30 transition-colors">
              <X className="w-3 h-3" /> Reject
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function EnrichmentPanel() {
  const { pendingFacts, approvedFacts, enriching, enrich, approveFact, rejectFact } = useGraphStore();
  const [text, setText] = useState('');
  const [showApproved, setShowApproved] = useState(false);

  const handleEnrich = async () => {
    if (!text.trim()) return;
    await enrich(text);
  };

  // Confidence-sorted review queue (UI_PLAN.md §9.3.5): weakest facts --
  // most likely to need rejecting -- are easy to find, not buried at the
  // bottom of generation order.
  const sortedPending = [...pendingFacts].sort((a, b) => b.confidence - a.confidence);

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      <div className="p-4 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex gap-2">
          <Sparkles className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
          <div className="text-[10px] text-zinc-400 leading-relaxed">
            Runs all <span className="text-sky-400 font-bold">11 Polanyi heuristics</span> (Presuppositions,
            Implicatures, Causal Relations, ...) against the real graph + text below, inferring implicit
            knowledge no explicit edge captures. Every result is <span className="text-amber-400 font-bold">pending</span> until
            you approve or reject it -- nothing merges into the graph automatically.
          </div>
        </div>
      </div>

      <div className="p-4 border-b border-zinc-800 space-y-2 shrink-0">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste or reuse the text to enrich against (usually the same document you ingested)."
          className="w-full h-24 bg-zinc-900 border border-zinc-700 rounded-lg p-2.5 text-xs text-white placeholder:text-zinc-600 resize-none focus:outline-none focus:border-zinc-600 transition-colors"
        />
        <button
          onClick={() => void handleEnrich()}
          disabled={enriching || !text.trim()}
          className="w-full h-9 bg-white text-black hover:bg-zinc-200 text-xs font-bold rounded-lg flex items-center justify-center gap-2 disabled:opacity-40 transition-colors"
        >
          {enriching ? (
            <>
              <Loader className="w-3.5 h-3.5 animate-spin" /> Running 11 heuristics…
            </>
          ) : (
            <>
              <Sparkles className="w-3.5 h-3.5" /> Run Enrichment
            </>
          )}
        </button>
      </div>

      <div className="p-4 space-y-2">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5" /> Pending Review ({sortedPending.length})
        </h3>
        {sortedPending.length === 0 ? (
          <p className="text-[10px] text-zinc-600">No pending implicit facts. Run enrichment above.</p>
        ) : (
          <div className="space-y-2">
            {sortedPending.map((fact) => (
              <FactCard
                key={fact.id}
                fact={fact}
                onApprove={() => void approveFact(fact.id)}
                onReject={() => void rejectFact(fact.id)}
              />
            ))}
          </div>
        )}
      </div>

      {approvedFacts.length > 0 && (
        <div className="p-4 border-t border-zinc-800">
          <button
            onClick={() => setShowApproved((v) => !v)}
            className="w-full flex items-center justify-between text-[11px] font-bold text-zinc-400 uppercase tracking-wider hover:text-zinc-200 transition-colors"
          >
            <span className="flex items-center gap-1.5">
              <Check className="w-3.5 h-3.5 text-emerald-400" /> Approved ({approvedFacts.length})
            </span>
            {showApproved ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </button>
          {showApproved && (
            <div className="space-y-2 mt-2">
              {approvedFacts.map((fact) => (
                <FactCard key={fact.id} fact={fact} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
