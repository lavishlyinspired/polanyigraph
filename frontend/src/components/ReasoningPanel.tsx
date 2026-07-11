// Left sidebar "Reason" tab. Visual language ported from the prototype
// (.claude/docs/src/components/InspectorPanel.tsx ReasoningPanel) -- the
// 3-step Neural/Symbolic/Feedback loop indicator, auto-run, heatmap/proof
// toggles, activation ranking, and derived-facts list all carry over.
//
// One deliberate deviation from the prototype: the backend's /reason (PLAN.md
// section 8.4) runs spread -> fire -> feedback to convergence as ONE atomic,
// already-verified call -- not three separately-clickable manual steps. So
// "Spread Activation" / "Run Inference" / "Feed Back" collapse into a single
// "Run Reasoning" action; the 3-step visual still shows real progress.
import { Brain, Zap, Lightbulb, Play, Square, Layers, GitFork, ChevronRight, Clock, TrendingUp } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';

export function ReasoningPanel() {
  const {
    nodes, selectedNodeId, facts, convergedBy, iterations, loading,
    autoRunning, showHeatmap, showProofPath,
    reason, startAutoRun, stopAutoRun, toggleHeatmap, toggleProofPath,
  } = useGraphStore();
  const selected = nodes.find((n) => n.id === selectedNodeId) ?? null;

  const hasActivation = iterations > 0;
  const hasFacts = facts.length > 0;

  const topActivated = [...nodes]
    .filter((n) => (n.activation ?? 0) > 0.01)
    .sort((a, b) => (b.activation ?? 0) - (a.activation ?? 0))
    .slice(0, 8);

  const stepDone = (step: 'neural' | 'symbolic' | 'feedback') => {
    if (step === 'neural') return hasActivation;
    if (step === 'symbolic') return hasFacts;
    return hasFacts; // feedback is folded into the same atomic call as symbolic
  };

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      <div className="p-4 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex gap-2">
          <Lightbulb className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-[10px] text-zinc-400 leading-relaxed">
            <span className="text-amber-400 font-bold">Activation</span> spreads from a source node
            (directed, decays per hop, weighted by edge weight & node salience — persists across
            iterations). <span className="text-emerald-400 font-bold">Derived</span> = a rule fired on
            an active node. <span className="text-violet-400 font-bold">Proof paths</span> = the
            derivation chain, including <span className="text-sky-400 font-bold">ontology resolution</span>{' '}
            when a rule matched via a real subclass relationship, not an exact type.
          </div>
        </div>
      </div>

      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Brain className="w-3.5 h-3.5" /> Neurosymbolic Loop
          </h3>
          {iterations > 0 && <span className="px-2 py-0.5 rounded text-[9px] bg-white text-black font-bold">Iteration {iterations}</span>}
        </div>

        <div className="flex items-center justify-between gap-1">
          {(['neural', 'symbolic', 'feedback'] as const).map((step, i) => (
            <div key={step} className="flex items-center flex-1">
              <div
                className={`flex-1 rounded-lg border p-2.5 text-center transition-all ${
                  stepDone(step) ? 'border-white bg-white text-black' : 'border-zinc-800 bg-zinc-900 text-zinc-600'
                }`}
              >
                <div className="text-[9px] font-bold uppercase">{step}</div>
              </div>
              {i < 2 && <ChevronRight className="w-3 h-3 text-zinc-700 shrink-0 mx-0.5" />}
            </div>
          ))}
        </div>

        <div className="mt-3 flex gap-2">
          {autoRunning ? (
            <button
              onClick={stopAutoRun}
              className="flex-1 h-8 rounded bg-rose-500 text-white hover:bg-rose-600 text-xs font-bold flex items-center justify-center gap-1.5 transition-colors"
            >
              <Square className="w-3.5 h-3.5" /> Stop Auto-Run
            </button>
          ) : (
            <button
              onClick={startAutoRun}
              disabled={!selected}
              className="flex-1 h-8 rounded bg-white text-black hover:bg-zinc-200 text-xs font-bold flex items-center justify-center gap-1.5 disabled:opacity-40 transition-colors"
            >
              <Play className="w-3.5 h-3.5" /> Auto-Run Loop
            </button>
          )}
          <button
            onClick={toggleHeatmap}
            className={`h-8 px-3 rounded border text-xs transition-colors ${showHeatmap ? 'bg-amber-400/20 border-amber-400/40 text-amber-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-white'}`}
            title="Toggle activation heatmap"
          >
            <Layers className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={toggleProofPath}
            className={`h-8 px-3 rounded border text-xs transition-colors ${showProofPath ? 'bg-violet-400/20 border-violet-400/40 text-violet-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-white'}`}
            title="Toggle proof-path highlighting"
          >
            <GitFork className="w-3.5 h-3.5" />
          </button>
        </div>
        {!selected && !autoRunning && <p className="text-[10px] text-zinc-600 mt-2 text-center">Select a node to start the loop.</p>}
      </div>

      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5" /> Run Reasoning
          </h3>
          {convergedBy && (
            <span className="text-[9px] text-zinc-500 flex items-center gap-1">
              <Clock className="w-3 h-3" /> {convergedBy}
            </span>
          )}
        </div>
        <button
          onClick={() => void reason()}
          disabled={!selected || loading || autoRunning}
          className="w-full h-8 bg-white text-black hover:bg-zinc-200 text-xs font-bold rounded flex items-center justify-center gap-2 disabled:opacity-40 transition-colors"
        >
          {loading ? (
            <>
              <div className="w-3 h-3 border-2 border-black border-t-transparent rounded-full animate-spin" />
              Reasoning…
            </>
          ) : (
            <>
              <Zap className="w-3.5 h-3.5" /> Run reasoning from selected node
            </>
          )}
        </button>
        {!selected && <p className="text-[10px] text-zinc-600 mt-2">Select a node on the canvas first.</p>}

        {topActivated.length > 0 && (
          <div className="mt-3 space-y-1">
            <div className="text-[10px] text-zinc-500 mb-1 flex items-center gap-1">
              <TrendingUp className="w-3 h-3" /> Activated nodes ({topActivated.length}):
            </div>
            {topActivated.map((n, i) => {
              const pct = Math.min((n.activation ?? 0) * 100, 100);
              return (
                <div key={n.id} className="flex items-center gap-2 text-[10px]">
                  <span className="text-zinc-600 w-4">{i + 1}.</span>
                  <span className="text-zinc-300 flex-1 truncate">{n.label}</span>
                  <div className="w-12 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                    <div className="h-full bg-white" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-zinc-500 w-8 text-right">{pct.toFixed(0)}%</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="p-4">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <GitFork className="w-3.5 h-3.5" /> Derived Facts ({facts.length})
        </h3>
        {facts.length === 0 ? (
          <p className="text-[10px] text-zinc-600">No derived facts yet. Run reasoning from a node.</p>
        ) : (
          <div className="space-y-2">
            {facts.map((f) => (
              <div key={f.id} className="p-2.5 rounded-lg border border-amber-400/40 bg-amber-400/5">
                <div className="text-[10px] text-zinc-200">{f.fact}</div>
                <div className="text-[9px] text-zinc-600 mt-0.5">
                  {f.ruleName} · {(f.confidence * 100).toFixed(0)}% · iter {f.iteration}
                </div>
                {f.proofPath.length > 0 && (
                  <div className="mt-1.5 border-t border-zinc-800 pt-1.5">
                    {f.proofPath.map((step, i) => (
                      <div key={i} className="text-[9px] text-zinc-400 ml-1 mb-1">
                        <span className="text-violet-400 font-bold">{i + 1}.</span> [{step.ruleName}]{' '}
                        {step.sourceLabel} → {step.targetLabel}
                        <div className="text-zinc-600 ml-3">activation: {(step.premiseActivation * 100).toFixed(0)}%</div>
                        {step.typeResolution && (
                          <div className="text-sky-400 ml-3 flex items-start gap-1">
                            <span className="shrink-0">ontology:</span>
                            <span>{step.typeResolution}</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
