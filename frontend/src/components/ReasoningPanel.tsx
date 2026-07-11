// Left sidebar "Reason" tab. Full prototype parity (.claude/docs/src
// InspectorPanel.tsx ReasoningPanel): manual Spread Activation / Run
// Inference / Feed Back as three separate steps, Clear buttons per phase,
// a fired+skipped inference trace, and a real staged Auto-Run loop --
// EVERY one of these is a real call against real persisted Neo4j state
// (backend/services/reasoning_service.py's manual-step functions), not the
// prototype's client-side-only mock engine (docs/src/lib/engine.ts).
//
// The atomic "Run Reasoning" button (spread+infer+feedback to convergence
// in one already-verified backend call, PLAN.md §8.4) is kept alongside the
// three manual steps as an additional convenience, not a replacement --
// both are real, this project just also offers the one-click path the
// prototype didn't have.
import {
  Brain, Zap, Lightbulb, Play, Square, Layers, GitFork, ChevronRight, Clock,
  TrendingUp, Sparkles, RefreshCw, CheckCircle2, AlertCircle, Trash2,
} from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';

export function ReasoningPanel() {
  const {
    nodes, selectedNodeId, facts, trace, loopStep, loopIteration, convergedBy, iterations, loading,
    autoRunning, showHeatmap, showProofPath,
    reason, spreadActivationStep, runInferenceStep, feedBackStep, clearActivationStep, clearFactsStep,
    startAutoRun, stopAutoRun, toggleHeatmap, toggleProofPath,
  } = useGraphStore();
  const selected = nodes.find((n) => n.id === selectedNodeId) ?? null;

  const hasActivation = nodes.some((n) => (n.activation ?? 0) > 0.01);
  const hasFacts = facts.length > 0;
  const pendingFeedback = facts.filter((f) => !f.fedBack).length;
  const firedCount = trace.filter((t) => t.fired).length;
  const skippedCount = trace.length - firedCount;

  const topActivated = [...nodes]
    .filter((n) => (n.activation ?? 0) > 0.01)
    .sort((a, b) => (b.activation ?? 0) - (a.activation ?? 0))
    .slice(0, 8);

  const stepDone = (step: 'neural' | 'symbolic' | 'feedback') => {
    if (step === 'neural') return hasActivation;
    if (step === 'symbolic') return hasFacts;
    return hasFacts && pendingFeedback === 0;
  };
  const stepActive = (step: 'neural' | 'symbolic' | 'feedback') => loading && loopStep === step;

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
          {loopIteration > 0 && <span className="px-2 py-0.5 rounded text-[9px] bg-white text-black font-bold">Iteration {loopIteration}</span>}
        </div>

        <div className="flex items-center justify-between gap-1">
          {(['neural', 'symbolic', 'feedback'] as const).map((step, i) => (
            <div key={step} className="flex items-center flex-1">
              <div
                className={`flex-1 rounded-lg border p-2.5 text-center transition-all flex items-center justify-center gap-1 ${
                  stepActive(step)
                    ? 'border-white bg-white text-black'
                    : stepDone(step)
                      ? 'border-white bg-white text-black'
                      : 'border-zinc-800 bg-zinc-900 text-zinc-600'
                }`}
              >
                {stepActive(step) ? (
                  <Clock className="w-2.5 h-2.5 animate-pulse" />
                ) : stepDone(step) ? (
                  <CheckCircle2 className="w-2.5 h-2.5" />
                ) : null}
                <div className="text-[9px] font-bold uppercase">{step}</div>
              </div>
              {i < 2 && <ChevronRight className={`w-3 h-3 shrink-0 mx-0.5 ${stepDone(step) ? 'text-zinc-400' : 'text-zinc-700'}`} />}
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

      {/* 1. Neural Activation */}
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5" /> 1. Neural Activation
          </h3>
          {hasActivation && (
            <button onClick={() => void clearActivationStep()} className="text-zinc-600 hover:text-rose-400 transition-colors" title="Clear activation">
              <Trash2 className="w-3 h-3" />
            </button>
          )}
        </div>

        {selected ? (
          <div className="flex items-center gap-2 p-2 rounded border border-zinc-800 bg-zinc-900 mb-2">
            <div className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
            <span className="text-[10px] text-zinc-300 truncate">{selected.label}</span>
          </div>
        ) : (
          <p className="text-[10px] text-zinc-600 mb-2">Select a node on the canvas first.</p>
        )}

        <button
          onClick={() => void spreadActivationStep()}
          disabled={!selected || loading || autoRunning}
          className="w-full h-8 bg-white text-black hover:bg-zinc-200 text-xs font-bold rounded flex items-center justify-center gap-2 disabled:opacity-40 transition-colors"
        >
          <Zap className="w-3.5 h-3.5" /> Spread Activation
        </button>

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

      {/* 2. Symbolic Inference */}
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" /> 2. Symbolic Inference
          </h3>
          {hasFacts && (
            <button onClick={() => void clearFactsStep()} className="text-zinc-600 hover:text-rose-400 transition-colors" title="Clear derived facts">
              <Trash2 className="w-3 h-3" />
            </button>
          )}
        </div>

        <button
          onClick={() => void runInferenceStep()}
          disabled={!hasActivation || loading || autoRunning}
          className="w-full h-8 bg-white text-black hover:bg-zinc-200 text-xs font-bold rounded flex items-center justify-center gap-2 disabled:opacity-40 transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5" /> Run Inference
        </button>
        {!hasActivation && <p className="text-[10px] text-zinc-600 mt-2">Requires neural activation first.</p>}

        {trace.length > 0 && (
          <div className="mt-3">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-[10px] text-zinc-500">Inference trace:</span>
              <span className="px-1.5 py-0.5 rounded text-[8px] bg-emerald-400 text-black font-bold">{firedCount} fired</span>
              {skippedCount > 0 && <span className="px-1.5 py-0.5 rounded text-[8px] border border-zinc-700 text-zinc-500">{skippedCount} skipped</span>}
            </div>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {trace.map((t, i) => (
                <div
                  key={i}
                  className={`p-1.5 rounded border text-[9px] flex items-start gap-1.5 ${
                    t.fired ? 'border-amber-400/40 bg-amber-400/5' : 'border-zinc-800 bg-zinc-900'
                  }`}
                >
                  {t.fired ? (
                    <CheckCircle2 className="w-3 h-3 text-amber-400 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-3 h-3 text-zinc-600 shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-zinc-300">
                      <span className="font-bold">{t.ruleName}</span>: {t.sourceLabel} → {t.targetLabel}
                    </div>
                    <div className="text-zinc-600">
                      {t.edgeType} · {(t.sourceActivation * 100).toFixed(0)}% {t.fired ? '≥' : '<'} {(t.threshold * 100).toFixed(0)}%
                      {t.fired && t.iteration > 1 && <> · iter {t.iteration}</>}
                    </div>
                    {!t.fired && t.skipReason && <div className="text-zinc-700 italic">{t.skipReason}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {facts.length > 0 && (
          <div className="mt-3">
            <div className="text-[10px] text-zinc-500 mb-1.5">Derived facts ({facts.length}):</div>
            <div className="space-y-2">
              {facts.map((f) => (
                <div key={f.id} className={`p-2.5 rounded-lg border ${!f.fedBack ? 'border-amber-400/40 bg-amber-400/5' : 'border-zinc-800 bg-zinc-900'}`}>
                  <div className="text-[10px] text-zinc-200">{f.fact}</div>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <span className="text-[9px] text-zinc-600">{f.ruleName} · {(f.confidence * 100).toFixed(0)}% · iter {f.iteration}</span>
                    <span className={`text-[9px] ${f.fedBack ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {f.fedBack ? '✓ fed back' : '⏳ pending feedback'}
                    </span>
                    {f.proofPath.length > 1 && (
                      <span className="text-[9px] text-violet-400 flex items-center gap-0.5">
                        <GitFork className="w-2.5 h-2.5" /> {f.proofPath.length}-hop proof
                      </span>
                    )}
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
          </div>
        )}
      </div>

      {/* 3. Feedback to Neural */}
      <div className="p-4 border-b border-zinc-800">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <RefreshCw className="w-3.5 h-3.5" /> 3. Feedback to Neural
        </h3>
        <button
          onClick={() => void feedBackStep()}
          disabled={!hasFacts || pendingFeedback === 0 || loading || autoRunning}
          className="w-full h-8 bg-white text-black hover:bg-zinc-200 text-xs font-bold rounded flex items-center justify-center gap-2 disabled:opacity-40 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Feed Back{pendingFeedback > 0 ? ` (${pendingFeedback})` : ''}
        </button>
        {!hasFacts && <p className="text-[10px] text-zinc-600 mt-2">Requires derived facts first.</p>}
        {hasFacts && pendingFeedback === 0 && !autoRunning && (
          <p className="text-[10px] text-zinc-600 mt-2">All facts fed back. Run inference again for cascading derivations, or use Auto-Run.</p>
        )}
        {hasFacts && pendingFeedback > 0 && (
          <p className="text-[10px] text-zinc-600 mt-2">
            Feeding back will boost activation on {pendingFeedback} target node(s), potentially triggering new rules.
          </p>
        )}
      </div>

      {/* Atomic convenience: spread+infer+feedback to convergence in one call */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5" /> Run to Convergence
          </h3>
          {convergedBy && (
            <span className="text-[9px] text-zinc-500 flex items-center gap-1">
              <Clock className="w-3 h-3" /> {convergedBy}
            </span>
          )}
        </div>
        <p className="text-[9px] text-zinc-600 mb-2">Runs all three steps in a loop until convergence, in one backend call — a shortcut alongside the manual steps above, not a replacement for them.</p>
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
        {iterations > 0 && <p className="text-[9px] text-zinc-600 mt-2">Last convergence run: {iterations} iteration{iterations !== 1 ? 's' : ''}.</p>}
      </div>
    </div>
  );
}
