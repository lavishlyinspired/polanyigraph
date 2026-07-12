import { useState } from 'react';
import { Zap, Sparkles, RefreshCw, Trash2, Plus, X, Brain, Cpu, Layers, GitBranch, ChevronRight, Flame, Play, Square, AlertCircle, CheckCircle2, Clock, Lightbulb, GitFork } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { NODE_KINDS, KIND_BG, KIND_TEXT, KIND_BORDER, EDGE_LABELS } from '../lib/graph-data';
import type { GraphNode, GraphEdge, Rule, DerivedFact, ActivationResult, NodeKind, InferenceTraceEntry, LoopStep } from '../types';

interface ConstructionPanelProps {
  selectedNode: GraphNode | null;
  rules: Rule[];
  edges: GraphEdge[];
  onAddNode: (label: string, kind: NodeKind) => void;
  onLinkMode: (label: string | null) => void;
  linkMode: string | null;
  onUpdateNote: (id: string, note: string) => void;
  onUpdateProperty: (id: string, key: string, value: string) => void;
  onUpdateSalience: (id: string, salience: number) => void;
  onAddRule: (rule: Rule) => void;
  onDeleteRule: (id: string) => void;
  onToggleEdgeSymmetric: (id: string) => void;
  onToggleEdgeTransitive: (id: string) => void;
}

export function ConstructionPanel({ selectedNode, rules, edges, onAddNode, onLinkMode, linkMode, onUpdateNote, onUpdateProperty, onUpdateSalience, onAddRule, onDeleteRule, onToggleEdgeSymmetric, onToggleEdgeTransitive }: ConstructionPanelProps) {
  const [newNodeLabel, setNewNodeLabel] = useState('');
  const [newNodeKind, setNewNodeKind] = useState<NodeKind>('Entity');
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleName, setRuleName] = useState('');
  const [ruleSourceKind, setRuleSourceKind] = useState<NodeKind>('Entity');
  const [ruleEdgeLabel, setRuleEdgeLabel] = useState('dependsOn');
  const [ruleTargetKind, setRuleTargetKind] = useState<NodeKind>('Entity');
  const [ruleThreshold, setRuleThreshold] = useState('0.15');
  const [ruleDescription, setRuleDescription] = useState('{source} depends on {target}.');
  const [propKey, setPropKey] = useState('');

  const handleAdd = () => {
    if (!newNodeLabel.trim()) return;
    onAddNode(newNodeLabel.trim(), newNodeKind);
    setNewNodeLabel('');
  };

  const handleAddRule = () => {
    if (!ruleName.trim()) return;
    onAddRule({
      id: `r${Date.now()}`,
      name: ruleName.trim(),
      sourceKind: ruleSourceKind,
      edgeLabel: ruleEdgeLabel,
      targetKind: ruleTargetKind,
      threshold: parseFloat(ruleThreshold) || 0.15,
      description: ruleDescription,
    });
    setRuleName('');
    setShowRuleForm(false);
  };

  const handleAddProperty = () => {
    if (!propKey.trim() || !selectedNode) return;
    onUpdateProperty(selectedNode.id, propKey.trim(), '');
    setPropKey('');
  };

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      <div className="p-4 border-b border-zinc-800">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5" /> Node Inspector
        </h3>
        {selectedNode ? (
          <div className="space-y-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-2.5 h-2.5 rounded-full ${KIND_BG[selectedNode.kind]}`} />
                <span className="text-sm font-semibold text-white">{selectedNode.label}</span>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono">kind: {selectedNode.kind}</div>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Badge variant="outline" className={`text-[9px] ${KIND_BORDER[selectedNode.kind]} ${KIND_TEXT[selectedNode.kind]}`}>{selectedNode.kind}</Badge>
              {selectedNode.derived && <Badge className="text-[9px] bg-amber-400 text-black">DERIVED ({selectedNode.derivedFrom?.length || 0})</Badge>}
              {selectedNode.activation > 0.01 && <Badge variant="outline" className="text-[9px] border-zinc-600 text-zinc-300">{(selectedNode.activation * 100).toFixed(0)}% active</Badge>}
              {selectedNode.depth > 0 && selectedNode.activation > 0.01 && <Badge variant="outline" className="text-[9px] border-zinc-600 text-zinc-500">depth {selectedNode.depth}</Badge>}
            </div>
            <div>
              <Label className="text-[10px] text-zinc-500 uppercase tracking-wider">Salience: {selectedNode.salience.toFixed(2)}</Label>
              <input type="range" min="0.5" max="2" step="0.1" value={selectedNode.salience} onChange={(e) => onUpdateSalience(selectedNode.id, parseFloat(e.target.value))} className="w-full mt-1 accent-white" />
              <p className="text-[9px] text-zinc-600 mt-0.5">Higher salience = receives more activation from neighbors.</p>
            </div>
            <div>
              <Label className="text-[10px] text-zinc-500 uppercase tracking-wider">Properties</Label>
              <div className="mt-1 space-y-1">
                {Object.keys(selectedNode.properties).map((key) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-[10px] text-zinc-600 w-20 shrink-0 font-mono">{key}</span>
                    <Input value={selectedNode.properties[key] || ''} onChange={(e) => onUpdateProperty(selectedNode.id, key, e.target.value)} placeholder="—" className="bg-zinc-900 border-zinc-700 text-[10px] h-7 text-white" />
                  </div>
                ))}
                <div className="flex items-center gap-2">
                  <Input value={propKey} onChange={(e) => setPropKey(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleAddProperty()} placeholder="New property key..." className="bg-zinc-900 border-zinc-700 text-[10px] h-7 text-white" />
                  <Button onClick={handleAddProperty} size="sm" variant="outline" className="text-[10px] h-7 px-2 border-zinc-700"><Plus className="w-3 h-3" /></Button>
                </div>
              </div>
            </div>
            {selectedNode.derived && selectedNode.derivedRuleName && (
              <div className="p-2 rounded-lg bg-amber-400/10 border border-amber-400/30 text-[10px] text-amber-400">
                <Lightbulb className="w-3 h-3 inline mr-1" /> Derived by rule: <span className="font-bold">{selectedNode.derivedRuleName}</span>
              </div>
            )}
            {selectedNode.proofPath && selectedNode.proofPath.length > 0 && (
              <div className="p-2 rounded-lg bg-violet-400/10 border border-violet-400/30">
                <div className="text-[10px] text-violet-400 font-bold mb-1.5 flex items-center gap-1">
                  <GitFork className="w-3 h-3" /> Proof Path ({selectedNode.proofPath.length} hops)
                </div>
                {selectedNode.proofPath.map((step, i) => (
                  <div key={i} className="text-[9px] text-zinc-400 ml-3 mb-1">
                    <span className="text-violet-400 font-bold">{step.step}.</span> [{step.ruleName}] {step.sourceLabel} → {step.targetLabel}
                    <div className="text-zinc-600 ml-3">activation: {(step.sourceActivation * 100).toFixed(0)}% ≥ threshold: {(step.threshold * 100).toFixed(0)}% · iter {step.iteration}</div>
                  </div>
                ))}
              </div>
            )}
            <div>
              <Label className="text-[10px] text-zinc-500 uppercase tracking-wider">Note</Label>
              <Textarea value={selectedNode.note} onChange={(e) => onUpdateNote(selectedNode.id, e.target.value)} placeholder="Add a note..." className="mt-1 bg-zinc-900 border-zinc-700 text-xs min-h-[60px] resize-none text-white" />
            </div>
          </div>
        ) : (
          <p className="text-[11px] text-zinc-600">Click a node on the canvas to inspect.</p>
        )}
      </div>

      <div className="p-4 border-b border-zinc-800">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <Plus className="w-3.5 h-3.5" /> Add Node
        </h3>
        <div className="space-y-2">
          <Input value={newNodeLabel} onChange={(e) => setNewNodeLabel(e.target.value)} placeholder="Node label..." className="bg-zinc-900 border-zinc-700 text-xs text-white placeholder:text-zinc-600" />
          <Select value={newNodeKind} onValueChange={(v) => setNewNodeKind(v as NodeKind)}>
            <SelectTrigger className="bg-zinc-900 border-zinc-700 text-xs text-white"><SelectValue /></SelectTrigger>
            <SelectContent>{NODE_KINDS.map((k) => <SelectItem key={k} value={k}>{k}</SelectItem>)}</SelectContent>
          </Select>
          <Button onClick={handleAdd} size="sm" className="w-full bg-white text-black hover:bg-zinc-200 text-xs">
            <Plus className="w-3.5 h-3.5 mr-1" /> Add Node
          </Button>
        </div>
      </div>

      <div className="p-4 border-b border-zinc-800">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <GitBranch className="w-3.5 h-3.5" /> Add Edge
        </h3>
        <div className="space-y-2">
          <p className="text-[10px] text-zinc-600">Select edge type, then click source and target nodes.</p>
          <Select value={linkMode ?? ''} onValueChange={(v) => onLinkMode(v || null)}>
            <SelectTrigger className="bg-zinc-900 border-zinc-700 text-xs text-white"><SelectValue placeholder="Select edge type..." /></SelectTrigger>
            <SelectContent>{EDGE_LABELS.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}</SelectContent>
          </Select>
          {linkMode && <Button onClick={() => onLinkMode(null)} variant="outline" size="sm" className="w-full text-xs border-zinc-700 text-zinc-400">Cancel Link</Button>}
        </div>
        {edges.length > 0 && (
          <div className="mt-3 space-y-1">
            <div className="text-[10px] text-zinc-500 mb-1">Edge semantics:</div>
            {edges.slice(0, 5).map((e) => (
              <div key={e.id} className="flex items-center gap-2 text-[9px] text-zinc-500">
                <span className="font-mono truncate flex-1">{e.label}</span>
                <button onClick={() => onToggleEdgeSymmetric(e.id)} className={`px-1.5 py-0.5 rounded border text-[8px] ${e.symmetric ? 'border-emerald-400 text-emerald-400' : 'border-zinc-700 text-zinc-600'}`}>sym</button>
                <button onClick={() => onToggleEdgeTransitive(e.id)} className={`px-1.5 py-0.5 rounded border text-[8px] ${e.transitive ? 'border-sky-400 text-sky-400' : 'border-zinc-700 text-zinc-600'}`}>trans</button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="p-4 flex-1">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5" /> Rules ({rules.length})
          </h3>
          <Button onClick={() => setShowRuleForm(!showRuleForm)} size="sm" variant="ghost" className="text-[10px] text-zinc-500 hover:text-white h-6 px-2">
            {showRuleForm ? <X className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
          </Button>
        </div>
        {showRuleForm && (
          <div className="mb-3 p-3 rounded-lg border border-zinc-800 bg-zinc-900 space-y-2">
            <Input value={ruleName} onChange={(e) => setRuleName(e.target.value)} placeholder="Rule name..." className="bg-zinc-950 border-zinc-700 text-xs text-white" />
            <div className="grid grid-cols-2 gap-2">
              <Select value={ruleSourceKind} onValueChange={(v) => setRuleSourceKind(v as NodeKind)}>
                <SelectTrigger className="bg-zinc-950 border-zinc-700 text-xs text-white"><SelectValue /></SelectTrigger>
                <SelectContent>{NODE_KINDS.map((k) => <SelectItem key={k} value={k}>{k}</SelectItem>)}</SelectContent>
              </Select>
              <Select value={ruleEdgeLabel} onValueChange={setRuleEdgeLabel}>
                <SelectTrigger className="bg-zinc-950 border-zinc-700 text-xs text-white"><SelectValue /></SelectTrigger>
                <SelectContent>{EDGE_LABELS.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <Select value={ruleTargetKind} onValueChange={(v) => setRuleTargetKind(v as NodeKind)}>
              <SelectTrigger className="bg-zinc-950 border-zinc-700 text-xs text-white"><SelectValue /></SelectTrigger>
              <SelectContent>{NODE_KINDS.map((k) => <SelectItem key={k} value={k}>{k}</SelectItem>)}</SelectContent>
            </Select>
            <Input value={ruleThreshold} onChange={(e) => setRuleThreshold(e.target.value)} placeholder="Threshold (0-1)" className="bg-zinc-950 border-zinc-700 text-xs text-white" />
            <Input value={ruleDescription} onChange={(e) => setRuleDescription(e.target.value)} placeholder="Description with {source} and {target}" className="bg-zinc-950 border-zinc-700 text-xs text-white" />
            <Button onClick={handleAddRule} size="sm" className="w-full bg-white text-black hover:bg-zinc-200 text-xs">Add Rule</Button>
          </div>
        )}
        <div className="space-y-2">
          {rules.map((rule) => (
            <div key={rule.id} className="p-2.5 rounded-lg border border-zinc-800 bg-zinc-900 group">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-white truncate">{rule.name}</div>
                  <div className="text-[10px] text-zinc-500 mt-0.5 flex items-center gap-1 flex-wrap">
                    <span className={KIND_TEXT[rule.sourceKind]}>{rule.sourceKind}</span>
                    <ChevronRight className="w-2.5 h-2.5" />
                    <span className="text-zinc-400">{rule.edgeLabel}</span>
                    <ChevronRight className="w-2.5 h-2.5" />
                    <span className={KIND_TEXT[rule.targetKind]}>{rule.targetKind}</span>
                  </div>
                  <div className="text-[10px] text-zinc-600 mt-1">Threshold: {(rule.threshold * 100).toFixed(0)}%</div>
                </div>
                <button onClick={() => onDeleteRule(rule.id)} className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-600 hover:text-rose-400">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
          {rules.length === 0 && <p className="text-[10px] text-zinc-600 text-center py-4">No rules defined.</p>}
        </div>
      </div>
    </div>
  );
}

interface ReasoningPanelProps {
  selectedNode: GraphNode | null;
  activationResult: ActivationResult | null;
  derivedFacts: DerivedFact[];
  trace: InferenceTraceEntry[];
  loopIteration: number;
  loopStep: LoopStep;
  autoRunning: boolean;
  heatmapOn: boolean;
  showProofPaths: boolean;
  onRunActivation: (id: string) => void;
  onClearActivation: () => void;
  onRunInference: () => void;
  onClearFacts: () => void;
  onFeedBack: () => void;
  onAutoRun: () => void;
  onStopAuto: () => void;
  onToggleHeatmap: () => void;
  onToggleProofPaths: () => void;
}

export function ReasoningPanel({ selectedNode, activationResult, derivedFacts, trace, loopIteration, loopStep, autoRunning, heatmapOn, showProofPaths, onRunActivation, onClearActivation, onRunInference, onClearFacts, onFeedBack, onAutoRun, onStopAuto, onToggleHeatmap, onToggleProofPaths }: ReasoningPanelProps) {
  const hasActivation = activationResult !== null;
  const hasFacts = derivedFacts.length > 0;
  const pendingFeedback = derivedFacts.filter((f) => !f.fedBack).length;
  const firedCount = trace.filter((t) => t.fired).length;
  const skippedCount = trace.filter((t) => !t.fired).length;

  const stepStatus = (step: LoopStep): 'done' | 'active' | 'pending' => {
    if (autoRunning) {
      if (step === loopStep) return 'active';
      const order = ['neural', 'symbolic', 'feedback'];
      const stepIdx = order.indexOf(step);
      const currentIdx = order.indexOf(loopStep);
      if (currentIdx === -1) return 'pending';
      return stepIdx < currentIdx ? 'done' : 'pending';
    }
    if (step === 'neural') return hasActivation ? 'done' : 'pending';
    if (step === 'symbolic') return hasFacts ? 'done' : 'pending';
    if (step === 'feedback') return pendingFeedback > 0 ? 'active' : (hasFacts ? 'done' : 'pending');
    return 'pending';
  };

  const stepIcon = (status: 'done' | 'active' | 'pending') => {
    if (status === 'done') return <CheckCircle2 className="w-3 h-3 text-white" />;
    if (status === 'active') return <Clock className="w-3 h-3 text-white animate-pulse" />;
    return <div className="w-3 h-3 rounded-full border border-zinc-700" />;
  };

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      <div className="p-4 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex gap-2">
          <Lightbulb className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-[10px] text-zinc-400 leading-relaxed">
            <span className="text-amber-400 font-bold">Activation</span> = neural attention spreading from a source node (decays 0.45 per hop, weighted by edge weight & node salience). <span className="text-emerald-400 font-bold">Derived</span> = a rule fired on an active node, producing a fact with a proof path. <span className="text-violet-400 font-bold">Proof paths</span> = multi-hop derivation chains. <span className="text-sky-400 font-bold">Feedback</span> = facts boost activation, triggering new rules.
          </div>
        </div>
      </div>

      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Brain className="w-3.5 h-3.5" /> Neurosymbolic Loop
          </h3>
          {loopIteration > 0 && <Badge className="text-[9px] bg-white text-black">Iteration {loopIteration}</Badge>}
        </div>
        <div className="flex items-center justify-between gap-1">
          <div className={`flex-1 rounded-lg border p-2.5 text-center transition-all ${stepStatus('neural') !== 'pending' ? 'border-white bg-white text-black' : 'border-zinc-800 bg-zinc-900 text-zinc-600'}`}>
            <div className="flex items-center justify-center mb-1">{stepIcon(stepStatus('neural'))}</div>
            <div className="text-[9px] font-bold uppercase">Neural</div>
          </div>
          <div className={`text-lg ${stepStatus('symbolic') !== 'pending' ? 'text-white' : 'text-zinc-700'}`}>→</div>
          <div className={`flex-1 rounded-lg border p-2.5 text-center transition-all ${stepStatus('symbolic') !== 'pending' ? 'border-white bg-white text-black' : 'border-zinc-800 bg-zinc-900 text-zinc-600'}`}>
            <div className="flex items-center justify-center mb-1">{stepIcon(stepStatus('symbolic'))}</div>
            <div className="text-[9px] font-bold uppercase">Symbolic</div>
          </div>
          <div className={`text-lg ${stepStatus('feedback') !== 'pending' ? 'text-white' : 'text-zinc-700'}`}>↺</div>
          <div className={`flex-1 rounded-lg border p-2.5 text-center transition-all ${stepStatus('feedback') !== 'pending' ? 'border-white bg-white text-black' : 'border-zinc-800 bg-zinc-900 text-zinc-600'}`}>
            <div className="flex items-center justify-center mb-1">{stepIcon(stepStatus('feedback'))}</div>
            <div className="text-[9px] font-bold uppercase">Feedback</div>
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          {autoRunning ? (
            <Button onClick={onStopAuto} size="sm" className="flex-1 bg-rose-500 text-white hover:bg-rose-600 text-xs">
              <Square className="w-3.5 h-3.5 mr-1" /> Stop Auto-Run
            </Button>
          ) : (
            <Button onClick={onAutoRun} size="sm" className="flex-1 bg-white text-black hover:bg-zinc-200 text-xs" disabled={!selectedNode}>
              <Play className="w-3.5 h-3.5 mr-1" /> Auto-Run Loop
            </Button>
          )}
          <Button onClick={onToggleHeatmap} size="sm" variant="outline" className={`text-xs border-zinc-700 ${heatmapOn ? 'bg-white text-black' : 'text-zinc-400'}`}>
            <Flame className="w-3.5 h-3.5" />
          </Button>
          <Button onClick={onToggleProofPaths} size="sm" variant="outline" className={`text-xs border-zinc-700 ${showProofPaths ? 'bg-violet-400 text-black border-violet-400' : 'text-zinc-400'}`}>
            <GitFork className="w-3.5 h-3.5" />
          </Button>
        </div>
        {!selectedNode && !autoRunning && <p className="text-[10px] text-zinc-600 mt-2 text-center">Select a node to start the loop.</p>}
      </div>

      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5" /> 1. Neural Activation
          </h3>
          {hasActivation && <button onClick={onClearActivation} className="text-[10px] text-zinc-600 hover:text-rose-400">Clear</button>}
        </div>
        {selectedNode ? (
          <div className="space-y-2">
            <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${KIND_BG[selectedNode.kind]}`} />
                <span className="text-xs text-white font-medium">{selectedNode.label}</span>
              </div>
            </div>
            <Button onClick={() => onRunActivation(selectedNode.id)} size="sm" className="w-full bg-white text-black hover:bg-zinc-200 text-xs" disabled={autoRunning}>
              <Zap className="w-3.5 h-3.5 mr-1" /> Spread Activation
            </Button>
          </div>
        ) : (
          <p className="text-[10px] text-zinc-600">Select a node on the canvas first.</p>
        )}
        {activationResult && (
          <div className="mt-3 space-y-1">
            <div className="text-[10px] text-zinc-500 mb-1">Activated nodes ({activationResult.ranked.length}):</div>
            {activationResult.ranked.slice(0, 6).map((r, i) => (
              <div key={r.nodeId} className="flex items-center gap-2 text-[10px]">
                <span className="text-zinc-600 w-4">{i + 1}.</span>
                <span className="text-zinc-300 flex-1 truncate">{r.nodeLabel}</span>
                <span className="text-zinc-600 text-[8px]">d{r.depth}</span>
                <div className="w-12 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                  <div className="h-full bg-white" style={{ width: `${r.activation * 100}%` }} />
                </div>
                <span className="text-zinc-500 w-7 text-right">{(r.activation * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" /> 2. Symbolic Inference
          </h3>
          {hasFacts && <button onClick={onClearFacts} className="text-[10px] text-zinc-600 hover:text-rose-400">Clear</button>}
        </div>
        <Button onClick={onRunInference} size="sm" className="w-full bg-white text-black hover:bg-zinc-200 text-xs" disabled={!hasActivation || autoRunning}>
          <Sparkles className="w-3.5 h-3.5 mr-1" /> Run Inference
        </Button>
        {!hasActivation && <p className="text-[10px] text-zinc-600 mt-2">Requires neural activation first.</p>}
        {trace.length > 0 && (
          <div className="mt-3 space-y-2">
            <div className="text-[10px] text-zinc-500 flex items-center gap-2">
              <span>Inference trace:</span>
              <Badge className="text-[8px] bg-emerald-500 text-white">{firedCount} fired</Badge>
              {skippedCount > 0 && <Badge variant="outline" className="text-[8px] border-zinc-700 text-zinc-500">{skippedCount} skipped</Badge>}
            </div>
            {trace.map((t, i) => (
              <div key={i} className={`p-2 rounded-lg border text-[10px] ${t.fired ? 'border-amber-400/40 bg-amber-400/5' : 'border-zinc-800 bg-zinc-900'}`}>
                <div className="flex items-start gap-2">
                  {t.fired ? <CheckCircle2 className="w-3 h-3 text-amber-400 mt-0.5 shrink-0" /> : <AlertCircle className="w-3 h-3 text-zinc-600 mt-0.5 shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <div className="text-zinc-300"><span className="font-medium">{t.ruleName}</span>: {t.sourceLabel} → {t.targetLabel}</div>
                    <div className="text-[9px] text-zinc-600 mt-0.5">
                      Edge: {t.edgeLabel} · Activation: {(t.sourceActivation * 100).toFixed(0)}% {t.fired ? '≥' : '<'} {(t.threshold * 100).toFixed(0)}%
                      {t.fired && t.iteration > 1 && ` · Iteration ${t.iteration}`}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        {derivedFacts.length > 0 && (
          <div className="mt-3 space-y-1.5">
            <div className="text-[10px] text-zinc-500 mb-1">Derived facts ({derivedFacts.length}):</div>
            {derivedFacts.map((f) => (
              <div key={f.id} className={`p-2 rounded-lg border ${f.fedBack ? 'border-zinc-800 bg-zinc-900' : 'border-amber-400/40 bg-amber-400/5'}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] text-zinc-300">{f.fact}</div>
                    <div className="text-[9px] text-zinc-600 mt-0.5">
                      {f.ruleName} · {(f.confidence * 100).toFixed(0)}% · iter {f.iteration}
                      {f.fedBack ? ' · ✓ fed back' : ' · ⏳ pending feedback'}
                    </div>
                    {f.proofPath.length > 1 && (
                      <div className="mt-1 text-[9px] text-violet-400 flex items-center gap-1">
                        <GitFork className="w-2.5 h-2.5" /> {f.proofPath.length}-hop proof
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="p-4">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <RefreshCw className="w-3.5 h-3.5" /> 3. Feedback to Neural
        </h3>
        <Button onClick={onFeedBack} size="sm" className="w-full bg-white text-black hover:bg-zinc-200 text-xs" disabled={!hasFacts || pendingFeedback === 0 || autoRunning}>
          <RefreshCw className="w-3.5 h-3.5 mr-1" /> Feed Back {pendingFeedback > 0 && `(${pendingFeedback})`}
        </Button>
        {!hasFacts && <p className="text-[10px] text-zinc-600 mt-2">Requires derived facts first.</p>}
        {hasFacts && pendingFeedback === 0 && !autoRunning && (
          <p className="text-[10px] text-zinc-600 mt-2">All facts fed back. Run inference again for cascading derivations, or use Auto-Run.</p>
        )}
        {hasFacts && pendingFeedback > 0 && (
          <p className="text-[10px] text-zinc-500 mt-2">Feeding back will boost activation on {pendingFeedback} target node(s), potentially triggering new rules.</p>
        )}
      </div>
    </div>
  );
}