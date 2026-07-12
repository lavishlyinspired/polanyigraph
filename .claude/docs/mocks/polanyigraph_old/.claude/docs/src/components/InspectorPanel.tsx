import { useState } from 'react';
import { Zap, Sparkles, RefreshCw, Trash2, Plus, X, Brain, Send, Terminal, Cpu, Layers, GitBranch, ChevronRight, Flame, Play, Square, AlertCircle, CheckCircle2, Clock, Lightbulb, Search, GitFork } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { ALL_MODULES, MODULE_LABELS, MODULE_COLORS, MODULE_TEXT_COLORS, MODULE_BORDER_COLORS, EDGE_OPTIONS, FIBO_CLASSES, PROPERTY_KEYS } from '../lib/fibo-data';
import { executeQuery } from '../lib/engine';
import type { GraphNode, Rule, DerivedFact, ActivationResult, ChatMessage, FiboModule, FiboEdgeType, InferenceTraceEntry, LoopStep, QueryResult } from '../types';

interface ConstructionPanelProps {
  selectedNode: GraphNode | null;
  rules: Rule[];
  onAddNode: (label: string, module: FiboModule, fiboClass: string) => void;
  onLinkMode: (type: FiboEdgeType | null) => void;
  linkMode: FiboEdgeType | null;
  onUpdateNote: (id: string, note: string) => void;
  onUpdateProperty: (id: string, key: string, value: string) => void;
  onUpdateSalience: (id: string, salience: number) => void;
  onAddRule: (rule: Rule) => void;
  onDeleteRule: (id: string) => void;
}

export function ConstructionPanel({ selectedNode, rules, onAddNode, onLinkMode, linkMode, onUpdateNote, onUpdateProperty, onUpdateSalience, onAddRule, onDeleteRule }: ConstructionPanelProps) {
  const [newNodeLabel, setNewNodeLabel] = useState('');
  const [newNodeModule, setNewNodeModule] = useState<FiboModule>('BusinessEntities');
  const [newNodeClass, setNewNodeClass] = useState('');
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleName, setRuleName] = useState('');
  const [ruleSourceModule, setRuleSourceModule] = useState<FiboModule>('Securities');
  const [ruleEdgeType, setRuleEdgeType] = useState<FiboEdgeType>('issuedBy');
  const [ruleTargetModule, setRuleTargetModule] = useState<FiboModule>('BusinessEntities');
  const [ruleThreshold, setRuleThreshold] = useState('0.2');
  const [ruleDescription, setRuleDescription] = useState('{source} is issued by {target}.');

  const handleAdd = () => {
    if (!newNodeLabel.trim()) return;
    onAddNode(newNodeLabel.trim(), newNodeModule, newNodeClass.trim());
    setNewNodeLabel('');
    setNewNodeClass('');
  };

  const handleAddRule = () => {
    if (!ruleName.trim()) return;
    onAddRule({
      id: `r${Date.now()}`,
      name: ruleName.trim(),
      sourceModule: ruleSourceModule,
      edgeType: ruleEdgeType,
      targetModule: ruleTargetModule,
      deriveTag: 'derived',
      threshold: parseFloat(ruleThreshold) || 0.2,
      description: ruleDescription,
    });
    setRuleName('');
    setShowRuleForm(false);
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
                <div className={`w-2.5 h-2.5 rounded-full ${MODULE_COLORS[selectedNode.module]}`} />
                <span className="text-sm font-semibold text-white">{selectedNode.label}</span>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono">{selectedNode.fiboClass}</div>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Badge variant="outline" className={`text-[9px] ${MODULE_BORDER_COLORS[selectedNode.module]} ${MODULE_TEXT_COLORS[selectedNode.module]}`}>
                {MODULE_LABELS[selectedNode.module]}
              </Badge>
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
                {PROPERTY_KEYS.map((key) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-[10px] text-zinc-600 w-20 shrink-0 font-mono">{key}</span>
                    <Input value={selectedNode.properties[key] || ''} onChange={(e) => onUpdateProperty(selectedNode.id, key, e.target.value)} placeholder="—" className="bg-zinc-900 border-zinc-700 text-[10px] h-7 text-white" />
                  </div>
                ))}
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
          <Select value={newNodeModule} onValueChange={(v) => { setNewNodeModule(v as FiboModule); setNewNodeClass(''); }}>
            <SelectTrigger className="bg-zinc-900 border-zinc-700 text-xs text-white"><SelectValue /></SelectTrigger>
            <SelectContent>{ALL_MODULES.map((m) => <SelectItem key={m} value={m}>{MODULE_LABELS[m]}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={newNodeClass} onValueChange={setNewNodeClass}>
            <SelectTrigger className="bg-zinc-900 border-zinc-700 text-xs text-white"><SelectValue placeholder="FIBO class (optional)" /></SelectTrigger>
            <SelectContent>{(FIBO_CLASSES[newNodeModule] || []).map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
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
          <Select value={linkMode ?? ''} onValueChange={(v) => onLinkMode(v as FiboEdgeType || null)}>
            <SelectTrigger className="bg-zinc-900 border-zinc-700 text-xs text-white"><SelectValue placeholder="Select edge type..." /></SelectTrigger>
            <SelectContent>{EDGE_OPTIONS.map((e) => <SelectItem key={e.value} value={e.value}>{e.label}</SelectItem>)}</SelectContent>
          </Select>
          {linkMode && <Button onClick={() => onLinkMode(null)} variant="outline" size="sm" className="w-full text-xs border-zinc-700 text-zinc-400">Cancel Link</Button>}
        </div>
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
              <Select value={ruleSourceModule} onValueChange={(v) => setRuleSourceModule(v as FiboModule)}>
                <SelectTrigger className="bg-zinc-950 border-zinc-700 text-xs text-white"><SelectValue /></SelectTrigger>
                <SelectContent>{ALL_MODULES.map((m) => <SelectItem key={m} value={m}>{MODULE_LABELS[m]}</SelectItem>)}</SelectContent>
              </Select>
              <Select value={ruleEdgeType} onValueChange={(v) => setRuleEdgeType(v as FiboEdgeType)}>
                <SelectTrigger className="bg-zinc-950 border-zinc-700 text-xs text-white"><SelectValue /></SelectTrigger>
                <SelectContent>{EDGE_OPTIONS.map((e) => <SelectItem key={e.value} value={e.value}>{e.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <Select value={ruleTargetModule} onValueChange={(v) => setRuleTargetModule(v as FiboModule)}>
              <SelectTrigger className="bg-zinc-950 border-zinc-700 text-xs text-white"><SelectValue /></SelectTrigger>
              <SelectContent>{ALL_MODULES.map((m) => <SelectItem key={m} value={m}>{MODULE_LABELS[m]}</SelectItem>)}</SelectContent>
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
                    <span className={MODULE_TEXT_COLORS[rule.sourceModule]}>{MODULE_LABELS[rule.sourceModule]}</span>
                    <ChevronRight className="w-2.5 h-2.5" />
                    <span className="text-zinc-400">{rule.edgeType}</span>
                    <ChevronRight className="w-2.5 h-2.5" />
                    <span className={MODULE_TEXT_COLORS[rule.targetModule]}>{MODULE_LABELS[rule.targetModule]}</span>
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
                <div className={`w-2 h-2 rounded-full ${MODULE_COLORS[selectedNode.module]}`} />
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
                      Edge: {t.edgeType} · Activation: {(t.sourceActivation * 100).toFixed(0)}% {t.fired ? '≥' : '<'} {(t.threshold * 100).toFixed(0)}%
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

interface QueryPanelProps {
  nodes: GraphNode[];
  edges: any[];
  derivedFacts: DerivedFact[];
}

export function QueryPanel({ nodes, edges, derivedFacts }: QueryPanelProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<QueryResult | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  const handleQuery = () => {
    if (!query.trim()) return;
    const result = executeQuery(query, nodes, edges, derivedFacts);
    setResults(result);
    setHistory((prev) => [query, ...prev.filter((h) => h !== query)].slice(0, 5));
  };

  const examples = [
    'regulates("FINMA", X)',
    'regulates(X, "Credit Suisse")',
    'issuedBy(X, "Credit Suisse")',
    'hasDomicile("Credit Suisse", X)',
    'denominatedIn("CS Atlas Bond I", X)',
    'regulates("FINMA", X), hasDomicile(X, "Zürich")',
  ];

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Search className="w-3.5 h-3.5" /> Query Console
        </h3>
        <p className="text-[9px] text-zinc-600 mt-1">Datalog-style: predicate(subject, object). Use X, Y for variables. Conjunctions with commas.</p>
      </div>
      <div className="p-3 border-b border-zinc-800 shrink-0">
        <div className="flex gap-2">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleQuery()} placeholder='e.g., regulates("FINMA", X)' className="bg-zinc-900 border-zinc-700 text-xs text-white placeholder:text-zinc-600 font-mono" />
          <Button onClick={handleQuery} size="sm" className="bg-white text-black hover:bg-zinc-200 text-xs px-3">
            <Search className="w-3.5 h-3.5" />
          </Button>
        </div>
        {history.length > 0 && (
          <div className="mt-2 flex gap-1 flex-wrap">
            {history.map((h, i) => (
              <button key={i} onClick={() => setQuery(h)} className="text-[9px] px-2 py-0.5 rounded border border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-colors font-mono truncate max-w-32">
                {h}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-3 min-h-0">
        {results ? (
          results.error ? (
            <div className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/5 text-[10px] text-rose-400">
              <AlertCircle className="w-3 h-3 inline mr-1" /> {results.error}
            </div>
          ) : results.results.length === 0 ? (
            <div className="text-center text-[10px] text-zinc-600 mt-8">
              <Search className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
              No results found for this query.
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-[10px] text-zinc-500">{results.results.length} result{results.results.length > 1 ? 's' : ''}</div>
              {results.results.map((r, i) => (
                <div key={i} className={`p-2.5 rounded-lg border ${r.derived ? 'border-amber-400/30 bg-amber-400/5' : 'border-zinc-800 bg-zinc-900'}`}>
                  <div className="text-[10px] font-mono text-zinc-300">
                    <span className="text-emerald-400">{r.subject}</span>
                    <span className="text-zinc-500"> .{r.predicate}(</span>
                    <span className="text-sky-400">{r.object}</span>
                    <span className="text-zinc-500">)</span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    {r.derived ? <Badge className="text-[8px] bg-amber-400 text-black">DERIVED</Badge> : <Badge variant="outline" className="text-[8px] border-zinc-700 text-zinc-500">BASE FACT</Badge>}
                    <span className="text-[9px] text-zinc-600">confidence: {(r.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          <div className="text-center text-[10px] text-zinc-600 mt-8">
            <Search className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
            <p className="mb-3">Query the graph + derived facts.</p>
            <div className="space-y-1 text-left max-w-56 mx-auto">
              <div className="text-[9px] text-zinc-700 uppercase tracking-wider mb-1">Examples:</div>
              {examples.map((ex, i) => (
                <button key={i} onClick={() => setQuery(ex)} className="block w-full text-left p-1.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors font-mono text-[9px] truncate">
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface LlmPanelProps {
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  nodes: GraphNode[];
  edges: any[];
  activationResult: ActivationResult | null;
  derivedFacts: DerivedFact[];
  selectedNode: GraphNode | null;
  trace: InferenceTraceEntry[];
  loopIteration: number;
}

export function LlmPanel({ messages, onMessagesChange, nodes, edges, activationResult, derivedFacts, selectedNode, trace, loopIteration }: LlmPanelProps) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim()) return;
    const userMsg = { id: `u-${Date.now()}`, role: 'user' as const, content: input.trim(), timestamp: Date.now() };
    onMessagesChange([...messages, userMsg]);
    setInput('');
    setTimeout(() => {
      const responses = [
        `Graph: ${nodes.length} nodes, ${edges.length} edges. ${activationResult ? `${activationResult.ranked.length} nodes active.` : 'No activation.'} ${derivedFacts.length} facts derived. Loop iteration: ${loopIteration}.`,
        selectedNode ? `Selected: ${selectedNode.label} (${selectedNode.module}). Activation: ${(selectedNode.activation * 100).toFixed(0)}%.${selectedNode.derived ? ` Derived from ${selectedNode.derivedFrom?.length || 0} fact(s).` : ''}` : 'No node selected.',
        derivedFacts.length > 0 ? `Latest fact: ${derivedFacts[derivedFacts.length - 1].fact}` : 'No facts yet. Run the neurosymbolic loop.',
        trace.length > 0 ? `Trace: ${trace.filter(t => t.fired).length} rules fired, ${trace.filter(t => !t.fired).length} skipped due to low activation.` : 'No inference trace yet.',
      ];
      const response = responses[Math.floor(Math.random() * responses.length)];
      onMessagesChange((prev) => [...prev, { id: `a-${Date.now()}`, role: 'assistant' as const, content: response, timestamp: Date.now() }]);
    }, 500);
  };

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Terminal className="w-3.5 h-3.5" /> LLM Console
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {messages.length === 0 ? (
          <div className="text-center text-[10px] text-zinc-600 mt-8">
            <Terminal className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
            Ask about the graph state.
            <div className="mt-3 space-y-1">
              <button onClick={() => setInput('summarize')} className="block w-full text-left p-1.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors">"summarize"</button>
              <button onClick={() => setInput('activation')} className="block w-full text-left p-1.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors">"activation"</button>
              <button onClick={() => setInput('inference')} className="block w-full text-left p-1.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors">"inference"</button>
              <button onClick={() => setInput('proof')} className="block w-full text-left p-1.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors">"proof"</button>
              <button onClick={() => setInput('help')} className="block w-full text-left p-1.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors">"help"</button>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`p-2.5 rounded-lg text-[11px] ${msg.role === 'user' ? 'bg-white text-black ml-4' : 'bg-zinc-900 text-zinc-300 border border-zinc-800 mr-4'}`}>
              <div className="text-[9px] font-bold uppercase mb-1 opacity-50">{msg.role}</div>
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          ))
        )}
      </div>
      <div className="p-3 border-t border-zinc-800 shrink-0">
        <div className="flex gap-2">
          <Input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSend()} placeholder="Ask about graph state..." className="bg-zinc-900 border-zinc-700 text-xs text-white placeholder:text-zinc-600" />
          <Button onClick={handleSend} size="sm" className="bg-white text-black hover:bg-zinc-200 text-xs px-3">
            <Send className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}