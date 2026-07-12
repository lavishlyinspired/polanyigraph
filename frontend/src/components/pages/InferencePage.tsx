// Inference Lab (UI_REFACTOR_PLAN.md §3.3, nav label renamed from "Solver Lab"
// for clarity): canvas-free duplicate of the
// sidebar's Reason tab -- same real spread/infer/feedback store actions,
// visualizing real-time progress via a "Top Activated Entities" leaderboard
// and a diagnostic trace stream instead of canvas glow, which is why this
// page needs no canvas at all. Ported from .claude/docs/mocks/polanyigraph,
// fixed invalid Tailwind utilities (h-8.5, bg-zinc-750 aren't real classes)
// to bracket syntax / the nearest real shade.
import { useState } from 'react';
import { Brain, Zap, Sparkles, RefreshCw, Trash2, Play, Square, Layers, GitFork, ChevronRight, CheckCircle2, Info, ShieldAlert, Terminal, TerminalSquare, TrendingUp } from 'lucide-react';
import { useGraphStore } from '../../stores/graphStore';

export function InferencePage() {
  const {
    nodes, selectedNodeId, facts, trace, loopStep, loopIteration, convergedBy, iterations, loading,
    autoRunning, showHeatmap, showProofPath, selectNode,
    reason, spreadActivationStep, runInferenceStep, feedBackStep, clearActivationStep, clearFactsStep,
    startAutoRun, stopAutoRun, toggleHeatmap, toggleProofPath,
  } = useGraphStore();

  const [localSourceId, setLocalSourceId] = useState<string>('');

  const selectedNode = nodes.find((n) => n.id === (selectedNodeId || localSourceId)) ?? null;

  const hasActivation = nodes.some((n) => (n.activation ?? 0) > 0.01);
  const hasFacts = facts.length > 0;
  const pendingFeedback = facts.filter((f) => !f.fedBack).length;

  const topActivated = [...nodes]
    .filter((n) => (n.activation ?? 0) > 0.01)
    .sort((a, b) => (b.activation ?? 0) - (a.activation ?? 0))
    .slice(0, 10);

  const stepDone = (step: 'neural' | 'symbolic' | 'feedback') => {
    if (step === 'neural') return hasActivation;
    if (step === 'symbolic') return hasFacts;
    return hasFacts && pendingFeedback === 0;
  };
  const stepActive = (step: 'neural' | 'symbolic' | 'feedback') => loading && loopStep === step;

  const handleSourceSelect = (nodeId: string) => {
    setLocalSourceId(nodeId);
    selectNode(nodeId || null);
  };

  return (
    <div className="h-full flex-1 flex overflow-hidden bg-zinc-950">
      {/* NS-Loop Control Deck */}
      <div className="w-[360px] border-r border-zinc-800 flex flex-col min-w-0 bg-zinc-950/20">
        <div className="p-4 border-b border-zinc-800 bg-zinc-900/10 shrink-0">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
            <Brain className="w-4 h-4 text-blue-400" /> NS-Loop Control Deck
          </h3>
          <p className="text-[9px] text-zinc-500 mt-0.5">Control Spread-Activation &amp; Reasoning sequences</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
          <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-950/40 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono">Loop Status</span>
              <span className="px-2 py-0.5 rounded text-[9px] bg-white text-black font-bold font-mono">Iter {loopIteration}</span>
            </div>

            <div className="flex items-center justify-between gap-1">
              {(['neural', 'symbolic', 'feedback'] as const).map((step, i) => (
                <div key={step} className="flex items-center flex-1">
                  <div
                    className={`flex-1 rounded-lg border p-2 text-center transition-all flex flex-col items-center justify-center ${
                      stepActive(step)
                        ? 'border-white bg-white text-black font-semibold'
                        : stepDone(step)
                          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400 font-semibold'
                          : 'border-zinc-800 bg-zinc-900/60 text-zinc-600'
                    }`}
                  >
                    <div className="text-[8px] uppercase tracking-wider font-bold">{step}</div>
                  </div>
                  {i < 2 && <ChevronRight className={`w-3 h-3 shrink-0 mx-0.5 ${stepDone(step) ? 'text-zinc-600' : 'text-zinc-800'}`} />}
                </div>
              ))}
            </div>

            <div className="flex gap-2 pt-1.5">
              {autoRunning ? (
                <button onClick={stopAutoRun} className="flex-1 h-8 rounded bg-rose-600 text-onaccent hover:bg-rose-700 text-[11px] font-bold flex items-center justify-center gap-1.5 transition-colors">
                  <Square className="w-3 h-3" /> Stop Auto-Run
                </button>
              ) : (
                <button
                  onClick={startAutoRun}
                  disabled={!selectedNode}
                  className="flex-1 h-8 rounded bg-blue-600 text-onaccent hover:bg-blue-500 text-[11px] font-bold flex items-center justify-center gap-1.5 disabled:opacity-30 transition-all"
                >
                  <Play className="w-3 h-3 fill-onaccent" /> Auto-Run Loop
                </button>
              )}
              <button
                onClick={toggleHeatmap}
                className={`h-8 px-2.5 rounded border text-xs transition-colors ${showHeatmap ? 'bg-amber-400/15 border-amber-400/40 text-amber-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-white'}`}
                title="Toggle activation heatmap"
              >
                <Layers className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={toggleProofPath}
                className={`h-8 px-2.5 rounded border text-xs transition-colors ${showProofPath ? 'bg-sky-400/15 border-sky-400/40 text-sky-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-white'}`}
                title="Toggle proof-path highlight"
              >
                <GitFork className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-950/40 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1">
                <Zap className="w-3.5 h-3.5 text-amber-400" /> 1. Neural Activation
              </span>
              {hasActivation && (
                <button onClick={() => void clearActivationStep()} className="text-zinc-600 hover:text-rose-400 transition-colors" title="Clear activation">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <div className="space-y-1">
              <label className="text-[9px] font-mono text-zinc-500 uppercase tracking-wider">Select Activation Source concept</label>
              <div className="relative">
                <select
                  value={selectedNode?.id || ''}
                  onChange={(e) => handleSourceSelect(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-white h-9 px-3 pr-8 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all appearance-none cursor-pointer"
                >
                  <option value="" disabled>
                    Choose a node...
                  </option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label} ({n.type})
                    </option>
                  ))}
                </select>
                <ChevronRight className="w-3.5 h-3.5 text-zinc-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none rotate-90" />
              </div>
            </div>

            <button
              onClick={() => void spreadActivationStep()}
              disabled={!selectedNode || loading || autoRunning}
              className="w-full h-[34px] bg-blue-600 hover:bg-blue-500 text-onaccent text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 disabled:opacity-30 transition-all"
            >
              <Zap className="w-3.5 h-3.5" /> Spread Activation
            </button>
          </div>

          <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-950/40 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400" /> 2. Symbolic Inference
              </span>
              {hasFacts && (
                <button onClick={() => void clearFactsStep()} className="text-zinc-600 hover:text-rose-400 transition-colors" title="Clear derived facts">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <button
              onClick={() => void runInferenceStep()}
              disabled={!hasActivation || loading || autoRunning}
              className="w-full h-[34px] bg-blue-600 hover:bg-blue-500 text-onaccent text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 disabled:opacity-30 transition-all"
            >
              <Sparkles className="w-3.5 h-3.5" /> Run Logical Inference
            </button>
            {!hasActivation && (
              <p className="text-[9px] text-zinc-600 flex items-center gap-1">
                <Info className="w-3 h-3" /> Requires active spread activation levels first.
              </p>
            )}
          </div>

          <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-950/40 space-y-3">
            <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1">
              <RefreshCw className="w-3.5 h-3.5 text-sky-400" /> 3. Feedback Loop
            </span>

            <button
              onClick={() => void feedBackStep()}
              disabled={!hasFacts || pendingFeedback === 0 || loading || autoRunning}
              className="w-full h-[34px] bg-blue-600 hover:bg-blue-500 text-onaccent text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 disabled:opacity-30 transition-all"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Feed Back To Neural {pendingFeedback > 0 ? `(${pendingFeedback})` : ''}
            </button>
            {!hasFacts && (
              <p className="text-[9px] text-zinc-600 flex items-center gap-1">
                <Info className="w-3 h-3" /> Requires derived facts to feedback.
              </p>
            )}
          </div>

          <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-950/40 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1">
                <TerminalSquare className="w-3.5 h-3.5 text-blue-400" /> Run to Convergence
              </span>
              {convergedBy && <span className="text-[8px] font-mono text-zinc-500 bg-zinc-900 px-1 py-0.5 rounded border border-zinc-800">{convergedBy}</span>}
            </div>
            <p className="text-[9px] text-zinc-600 leading-relaxed">
              Runs Spread Activation, Symbolic Inference and Neural Feedback stages iteratively in a single backend call until fixed-point convergence.
            </p>
            <button
              onClick={() => void reason()}
              disabled={!selectedNode || loading || autoRunning}
              className="w-full h-9 bg-blue-600 hover:bg-blue-500 text-onaccent text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 disabled:opacity-30 transition-colors"
            >
              {loading ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-onaccent border-t-transparent rounded-full animate-spin" />
                  Running solver...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-onaccent" /> Compute Convergence Loop
                </>
              )}
            </button>
            {iterations > 0 && <p className="text-[8px] text-blue-400 font-mono text-right">Resolved in {iterations} rounds.</p>}
          </div>
        </div>
      </div>

      {/* Live Activation Metrics: Diagnostic Execution Tracer */}
      <div className="flex-1 border-r border-zinc-800 flex flex-col min-w-0">
        <div className="p-4 border-b border-zinc-800 bg-zinc-900/10 shrink-0 flex items-center justify-between">
          <div>
            <h2 className="text-[13px] font-bold text-white tracking-wider uppercase flex items-center gap-2">
              <Terminal className="w-4 h-4 text-blue-400" /> Cognitive Execution Tracer
            </h2>
            <p className="text-[10px] text-zinc-500 mt-0.5">Live execution diagnostics showing rule compilations, subclass resolutions, and activation weights</p>
          </div>
        </div>

        <div className="flex-1 p-4 flex flex-col gap-4 overflow-hidden min-h-0">
          <div className="flex-1 flex flex-col border border-zinc-800 rounded-xl bg-zinc-950 overflow-hidden">
            <div className="h-9 border-b border-zinc-800 bg-zinc-900/40 flex items-center justify-between px-3 shrink-0 font-mono text-[10px] text-zinc-500">
              <span className="flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-zinc-500" /> Diagnostic stdout trace
              </span>
              <span>{trace.length} logs captured</span>
            </div>

            <div className="flex-1 overflow-y-auto p-4 font-mono text-[11px] text-zinc-300 space-y-2.5 min-h-0 bg-zinc-950/40">
              {trace.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center text-zinc-600 font-mono py-10">
                  <Terminal className="w-10 h-10 text-zinc-800 mb-3" />
                  <p>&gt;_ Loop Tracer active. Spread activation or run inference step to populate diagnostic stream.</p>
                </div>
              ) : (
                trace.map((t, i) => (
                  <div key={i} className={`p-3 rounded-lg border text-[11px] flex items-start gap-3 transition-colors ${t.fired ? 'border-amber-500/20 bg-amber-500/5' : 'border-zinc-900 bg-zinc-900/20'}`}>
                    {t.fired ? <CheckCircle2 className="w-4 h-4 text-amber-400 shrink-0 mt-0.5 animate-pulse" /> : <ShieldAlert className="w-4 h-4 text-zinc-600 shrink-0 mt-0.5" />}
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-zinc-100">{t.ruleName}</span>
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-mono border border-zinc-800 text-zinc-500">step: {t.iteration}</span>
                        {t.fired ? (
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-amber-400 text-badgeink font-bold">FIRED</span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[9px] border border-zinc-800 text-zinc-600">SKIPPED</span>
                        )}
                      </div>
                      <div className="text-zinc-400 font-sans text-xs">
                        {t.sourceLabel} <span className="text-zinc-600 font-mono">→[{t.edgeType}]→</span> {t.targetLabel}
                      </div>
                      <div className="text-[10px] text-zinc-500 flex items-center gap-2.5 flex-wrap">
                        <span>
                          Premise Act: <strong>{(t.sourceActivation * 100).toFixed(1)}%</strong>
                        </span>
                        <span>
                          Threshold Limit: <strong>{(t.threshold * 100).toFixed(0)}%</strong>
                        </span>
                        <span>
                          Compiles: <strong className={t.fired ? 'text-emerald-400' : 'text-zinc-600'}>{t.fired ? 'SUCCESS' : 'FALSE'}</strong>
                        </span>
                      </div>
                      {!t.fired && t.skipReason && <div className="text-zinc-600 italic text-[10px] pt-1 border-t border-zinc-900/60 mt-1 font-sans">{t.skipReason}</div>}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Introspective Fact Trace: activation leaderboard + derived facts */}
      <div className="w-[400px] border-l border-zinc-800 flex flex-col min-w-0 bg-zinc-950/40">
        <div className="p-4 border-b border-zinc-800 bg-zinc-900/10 flex shrink-0 justify-between items-center">
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <TrendingUp className="w-4 h-4 text-blue-400" /> System State Metrics
            </h3>
            <p className="text-[9px] text-zinc-500 mt-0.5">Spread activation vectors &amp; logical derivations</p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
          <div className="space-y-2.5">
            <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-amber-400" /> Concept Activation Levels ({topActivated.length})
            </div>

            {topActivated.length === 0 ? (
              <div className="p-4 rounded-lg border border-zinc-800/80 bg-zinc-950/20 text-center text-zinc-600 font-mono text-[10px]">Vector space completely quiet. (0% active)</div>
            ) : (
              <div className="p-3.5 rounded-xl border border-zinc-800 bg-zinc-900/20 space-y-2">
                {topActivated.map((n, i) => {
                  const pct = Math.min((n.activation ?? 0) * 100, 100);
                  return (
                    <div key={n.id} className="flex items-center gap-3 text-xs">
                      <span className="text-zinc-600 font-mono w-4 shrink-0 text-[10px]">{i + 1}.</span>
                      <div className="flex-1 min-w-0">
                        <span className="text-zinc-200 font-semibold truncate block">{n.label}</span>
                        <span className="text-[9px] text-zinc-500 font-mono block">{n.type}</span>
                      </div>
                      <div className="w-16 h-1.5 rounded-full bg-zinc-900 overflow-hidden shrink-0">
                        <div className="h-full bg-blue-500" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-zinc-300 font-mono w-10 text-right text-[11px] shrink-0">{pct.toFixed(0)}%</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="space-y-2.5">
            <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400" /> Derived Triple Store ({facts.length})
            </div>

            {facts.length === 0 ? (
              <div className="p-6 rounded-lg border border-dashed border-zinc-800 text-center text-zinc-600 font-mono text-[10px]">No derived facts. Try lowering rule thresholds.</div>
            ) : (
              <div className="space-y-3">
                {facts.map((f) => (
                  <div key={f.id} className={`p-3.5 rounded-xl border space-y-2.5 ${!f.fedBack ? 'border-amber-400/25 bg-amber-400/5' : 'border-zinc-800 bg-zinc-900/30'}`}>
                    <div className="text-xs text-zinc-200 font-mono break-words leading-relaxed">{f.fact}</div>
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap border-b border-zinc-800/40 pb-2">
                      <span className="text-[9px] text-zinc-500 font-mono">{f.ruleName}</span>
                      <span>·</span>
                      <span className="text-[9px] text-zinc-300 font-mono font-bold">{(f.confidence * 100).toFixed(0)}% confidence</span>
                      <span>·</span>
                      <span className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold uppercase ${f.fedBack ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-400/10 text-amber-400 animate-pulse'}`}>
                        {f.fedBack ? '✓ Fed Back' : '⏳ Pending'}
                      </span>
                    </div>

                    {f.proofPath.length > 0 && (
                      <div className="space-y-2.5 pt-1">
                        <div className="text-[9px] text-zinc-500 uppercase tracking-wider font-bold font-mono flex items-center gap-1">
                          <GitFork className="w-3 h-3 text-sky-400" /> Multi-hop Derivation Path
                        </div>
                        <div className="space-y-2 pl-1 border-l border-zinc-800">
                          {f.proofPath.map((step, i) => (
                            <div key={i} className="text-[10px] text-zinc-400 pl-3 relative">
                              <div className="absolute left-0 top-1.5 w-1.5 h-1.5 rounded-full bg-sky-500 -translate-x-3.5" />
                              <div className="font-mono text-[9px] text-zinc-500">
                                Hop {i + 1} &middot; <strong className="text-zinc-400">{step.ruleName}</strong>
                              </div>
                              <div className="text-zinc-200 mt-0.5">
                                {step.sourceLabel} <span className="text-zinc-600 font-mono">→</span> {step.targetLabel}
                              </div>
                              <div className="text-[9px] text-zinc-500 font-mono mt-0.5 flex items-center gap-1.5">
                                <span>
                                  Activation: <strong>{(step.premiseActivation * 100).toFixed(0)}%</strong>
                                </span>
                                {step.typeResolution && (
                                  <>
                                    <span>·</span>
                                    <span className="text-sky-400">ontology: {step.typeResolution}</span>
                                  </>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
