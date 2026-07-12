// Left sidebar "Construct" tab. Visual language ported from the prototype
// (.claude/docs/src/components/InspectorPanel.tsx ConstructionPanel), full
// capability set restored per explicit direction: Node Inspector (salience,
// properties, notes, proof path) -> Add Node -> Add Edge -> Rules Manager.
//
// Domain-agnostic adaptation of the prototype: no hardcoded FIBO modules or
// a fixed 6-edge-type list. Type/relation pickers are backed by GET /ontology
// (real class/property labels from whatever ontology is loaded), and every
// write is validated server-side against that same live ontology -- a
// non-existent type or relation is rejected, not silently accepted.
import { useEffect, useState } from 'react';
import { Layers, Cpu, Info, ChevronRight, Plus, GitBranch, GitFork, Trash2, X, Lightbulb } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';

const SELECT_CLS = 'w-full bg-zinc-900 border border-zinc-700 rounded text-xs text-white h-8 px-2 focus:outline-none focus:border-zinc-600 transition-colors appearance-none cursor-pointer';
const INPUT_CLS = 'w-full bg-zinc-900 border border-zinc-700 rounded text-xs text-white placeholder:text-zinc-600 h-8 px-2 focus:outline-none focus:border-zinc-600 transition-colors';

export function ConstructionPanel() {
  const {
    nodes, selectedNodeId, rules, facts, ontologyClasses, ontologyProperties,
    linkMode, addNode, setLinkMode, updateNodeMetadata, createRule, deleteRule,
  } = useGraphStore();
  const selected = nodes.find((n) => n.id === selectedNodeId) ?? null;

  const [newNodeLabel, setNewNodeLabel] = useState('');
  const [newNodeType, setNewNodeType] = useState('');
  const [newEdgeType, setNewEdgeType] = useState('');

  const [salienceDraft, setSalienceDraft] = useState(1);
  const [propsDraft, setPropsDraft] = useState<Record<string, string>>({});
  const [noteDraft, setNoteDraft] = useState('');
  const [newPropKey, setNewPropKey] = useState('');
  const [newPropValue, setNewPropValue] = useState('');

  useEffect(() => {
    setSalienceDraft(selected?.salience ?? 1);
    setPropsDraft(selected?.properties ?? {});
    setNoteDraft(selected?.note ?? '');
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleName, setRuleName] = useState('');
  const [ruleSourceType, setRuleSourceType] = useState('');
  const [ruleEdgeType, setRuleEdgeType] = useState('');
  const [ruleTargetType, setRuleTargetType] = useState('');
  const [ruleThreshold, setRuleThreshold] = useState('30');
  const [ruleDescription, setRuleDescription] = useState('{source} -> {target}');

  const nodeProofPath = selected
    ? facts.find((f) => f.targetId === selected.id)?.proofPath ?? []
    : [];

  const handleAddNode = async () => {
    if (!newNodeLabel.trim() || !newNodeType.trim()) return;
    await addNode(newNodeLabel.trim(), newNodeType.trim());
    setNewNodeLabel('');
    setNewNodeType('');
  };

  const handleSaveSalience = () => {
    if (!selected) return;
    void updateNodeMetadata(selected.id, { salience: salienceDraft });
  };

  const handleSaveProperties = () => {
    if (!selected) return;
    void updateNodeMetadata(selected.id, { properties: propsDraft });
  };

  const handleAddProperty = () => {
    if (!newPropKey.trim()) return;
    setPropsDraft({ ...propsDraft, [newPropKey.trim()]: newPropValue });
    setNewPropKey('');
    setNewPropValue('');
  };

  const handleSaveNote = () => {
    if (!selected) return;
    void updateNodeMetadata(selected.id, { note: noteDraft });
  };

  const handleAddRule = async () => {
    if (!ruleName.trim() || !ruleEdgeType.trim() || !ruleSourceType.trim() || !ruleTargetType.trim()) return;
    await createRule({
      name: ruleName.trim(),
      edgeType: ruleEdgeType.trim(),
      sourceType: ruleSourceType.trim(),
      targetType: ruleTargetType.trim(),
      threshold: (parseFloat(ruleThreshold) || 30) / 100,
      description: ruleDescription,
    });
    setRuleName('');
    setShowRuleForm(false);
  };

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      {/* Node Inspector */}
      <div className="p-4 border-b border-zinc-800">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5" /> Node Inspector
        </h3>
        {selected ? (
          <div className="space-y-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-semibold text-white">{selected.label}</span>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono">{selected.type}</div>
            </div>
            <div className="flex gap-2 flex-wrap">
              <span className="px-2 py-0.5 rounded text-[9px] border border-zinc-700 text-zinc-300 font-medium">
                {selected.type}
              </span>
              {selected.derived && (
                <span className="px-2 py-0.5 rounded text-[9px] bg-amber-400 text-black font-bold">DERIVED</span>
              )}
              {(selected.activation ?? 0) > 0.01 && (
                <span className="px-2 py-0.5 rounded text-[9px] border border-zinc-600 text-zinc-300">
                  {((selected.activation ?? 0) * 100).toFixed(0)}% active
                </span>
              )}
            </div>
            {selected.sourceDoc && (
              <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                <div className="text-[10px] text-zinc-500 flex items-center gap-1">
                  <Info className="w-3 h-3" /> Source document
                </div>
                <div className="text-[10px] text-zinc-300 mt-1 break-words">{selected.sourceDoc}</div>
              </div>
            )}

            {/* Salience */}
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Salience: {salienceDraft.toFixed(2)}</label>
              <input
                type="range" min={0.5} max={2} step={0.1} value={salienceDraft}
                onChange={(e) => setSalienceDraft(parseFloat(e.target.value))}
                onMouseUp={handleSaveSalience}
                onTouchEnd={handleSaveSalience}
                className="w-full mt-1 accent-white"
              />
              <p className="text-[9px] text-zinc-600 mt-0.5">Higher salience = receives more activation from neighbors.</p>
            </div>

            {/* Properties */}
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Properties</label>
              <div className="mt-1 space-y-1">
                {Object.entries(propsDraft).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-[10px] text-zinc-500 w-20 shrink-0 font-mono truncate">{key}</span>
                    <input
                      value={value}
                      onChange={(e) => setPropsDraft({ ...propsDraft, [key]: e.target.value })}
                      className="flex-1 bg-zinc-900 border border-zinc-700 rounded text-[10px] text-white h-7 px-1.5 focus:outline-none focus:border-zinc-600 transition-colors"
                    />
                    <button
                      onClick={() => {
                        const next = { ...propsDraft };
                        delete next[key];
                        setPropsDraft(next);
                      }}
                      className="text-zinc-600 hover:text-rose-400 transition-colors shrink-0"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                <div className="flex items-center gap-2">
                  <input
                    value={newPropKey}
                    onChange={(e) => setNewPropKey(e.target.value)}
                    placeholder="key"
                    className="w-20 shrink-0 bg-zinc-900 border border-zinc-700 rounded text-[10px] text-white placeholder:text-zinc-600 h-7 px-1.5 focus:outline-none focus:border-zinc-600 transition-colors"
                  />
                  <input
                    value={newPropValue}
                    onChange={(e) => setNewPropValue(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAddProperty()}
                    placeholder="value"
                    className="flex-1 bg-zinc-900 border border-zinc-700 rounded text-[10px] text-white placeholder:text-zinc-600 h-7 px-1.5 focus:outline-none focus:border-zinc-600 transition-colors"
                  />
                  <button onClick={handleAddProperty} className="text-zinc-500 hover:text-white transition-colors shrink-0">
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <button
                onClick={handleSaveProperties}
                className="mt-1.5 w-full h-6 rounded bg-zinc-800 hover:bg-zinc-700 text-[9px] font-bold text-zinc-300 transition-colors"
              >
                Save properties
              </button>
            </div>

            {/* Rule that derived this node */}
            {selected.derived && (
              <div className="p-2 rounded-lg bg-amber-400/10 border border-amber-400/30 text-[10px] text-amber-400">
                <Lightbulb className="w-3 h-3 inline mr-1" /> Derived — see Reason tab for the rule that fired.
              </div>
            )}

            {/* Proof path */}
            {nodeProofPath.length > 0 && (
              <div className="p-2 rounded-lg bg-sky-400/10 border border-sky-400/30">
                <div className="text-[10px] text-sky-400 font-bold mb-1.5 flex items-center gap-1">
                  <GitFork className="w-3 h-3" /> Proof Path ({nodeProofPath.length} hops)
                </div>
                {nodeProofPath.map((step, i) => (
                  <div key={i} className="text-[9px] text-zinc-400 ml-3 mb-1">
                    <span className="text-sky-400 font-bold">{i + 1}.</span> [{step.ruleName}] {step.sourceLabel} → {step.targetLabel}
                    <div className="text-zinc-600 ml-3">activation: {(step.premiseActivation * 100).toFixed(0)}% · iter {step.iteration}</div>
                    {step.typeResolution && <div className="text-sky-400 ml-3">ontology: {step.typeResolution}</div>}
                  </div>
                ))}
              </div>
            )}

            {/* Note */}
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Note</label>
              <textarea
                value={noteDraft}
                onChange={(e) => setNoteDraft(e.target.value)}
                onBlur={handleSaveNote}
                placeholder="Add a note..."
                className="mt-1 w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-xs text-white placeholder:text-zinc-600 min-h-[60px] resize-none focus:outline-none focus:border-zinc-600 transition-colors"
              />
            </div>
          </div>
        ) : (
          <p className="text-[11px] text-zinc-600">Click a node on the canvas to inspect.</p>
        )}
      </div>

      {/* Add Node */}
      <div className="p-4 border-b border-zinc-800">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <Plus className="w-3.5 h-3.5" /> Add Node
        </h3>
        <div className="space-y-2">
          <input
            value={newNodeLabel}
            onChange={(e) => setNewNodeLabel(e.target.value)}
            placeholder="Node label..."
            className={INPUT_CLS}
          />
          <div className="relative">
            <select
              value={newNodeType}
              onChange={(e) => setNewNodeType(e.target.value)}
              className={SELECT_CLS}
            >
              <option value="" disabled>Select type...</option>
              {ontologyClasses.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <ChevronRight className="w-3 h-3 text-zinc-600 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none rotate-90" />
          </div>
          <button
            onClick={() => void handleAddNode()}
            disabled={!newNodeLabel.trim() || !newNodeType.trim()}
            className="w-full h-8 bg-white text-black hover:bg-zinc-200 text-xs font-bold rounded flex items-center justify-center gap-1.5 disabled:opacity-40 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" /> Add Node
          </button>
        </div>
      </div>

      {/* Add Edge */}
      <div className="p-4 border-b border-zinc-800">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <GitBranch className="w-3.5 h-3.5" /> Add Edge
        </h3>
        <div className="space-y-2">
          <p className="text-[10px] text-zinc-600">Select edge type, then click source and target nodes.</p>
          <div className="relative">
            <select
              value={newEdgeType}
              onChange={(e) => setNewEdgeType(e.target.value)}
              className={SELECT_CLS}
            >
              <option value="" disabled>Select edge type...</option>
              {ontologyProperties.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <ChevronRight className="w-3 h-3 text-zinc-600 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none rotate-90" />
          </div>
          {linkMode ? (
            <button
              onClick={() => setLinkMode(null)}
              className="w-full h-8 rounded border border-zinc-700 text-zinc-400 hover:text-white text-xs flex items-center justify-center gap-1.5 transition-colors"
            >
              <X className="w-3.5 h-3.5" /> Cancel Link
            </button>
          ) : (
            <button
              onClick={() => newEdgeType.trim() && setLinkMode(newEdgeType.trim())}
              disabled={!newEdgeType.trim()}
              className="w-full h-8 bg-white text-black hover:bg-zinc-200 text-xs font-bold rounded flex items-center justify-center gap-1.5 disabled:opacity-40 transition-colors"
            >
              <GitBranch className="w-3.5 h-3.5" /> Start Linking
            </button>
          )}
        </div>
      </div>

      {/* Rules Manager */}
      <div className="p-4 flex-1">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5" /> Rules ({rules.length})
          </h3>
          <button
            onClick={() => setShowRuleForm(!showRuleForm)}
            className="w-6 h-6 rounded flex items-center justify-center text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors"
          >
            {showRuleForm ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
          </button>
        </div>

        {showRuleForm && (
          <div className="mb-3 p-3 rounded-lg border border-zinc-800 bg-zinc-900 space-y-2">
            <input
              value={ruleName}
              onChange={(e) => setRuleName(e.target.value)}
              placeholder="Rule name..."
              className="w-full bg-zinc-950 border border-zinc-700 rounded text-xs text-white placeholder:text-zinc-600 h-8 px-2 focus:outline-none focus:border-zinc-600 transition-colors"
            />
            <div className="grid grid-cols-2 gap-2">
              <div className="relative">
                <select
                  value={ruleSourceType}
                  onChange={(e) => setRuleSourceType(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded text-xs text-white h-8 px-2 pr-6 focus:outline-none focus:border-zinc-600 transition-colors appearance-none cursor-pointer"
                >
                  <option value="" disabled>Source type...</option>
                  {ontologyClasses.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <ChevronRight className="w-3 h-3 text-zinc-600 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none rotate-90" />
              </div>
              <div className="relative">
                <select
                  value={ruleTargetType}
                  onChange={(e) => setRuleTargetType(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded text-xs text-white h-8 px-2 pr-6 focus:outline-none focus:border-zinc-600 transition-colors appearance-none cursor-pointer"
                >
                  <option value="" disabled>Target type...</option>
                  {ontologyClasses.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <ChevronRight className="w-3 h-3 text-zinc-600 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none rotate-90" />
              </div>
            </div>
            <div className="relative">
              <select
                value={ruleEdgeType}
                onChange={(e) => setRuleEdgeType(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded text-xs text-white h-8 px-2 pr-6 focus:outline-none focus:border-zinc-600 transition-colors appearance-none cursor-pointer"
              >
                <option value="" disabled>Edge type (relation)...</option>
                {ontologyProperties.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <ChevronRight className="w-3 h-3 text-zinc-600 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none rotate-90" />
            </div>
            <div>
              <label className="text-[9px] text-zinc-500 uppercase tracking-wider">Threshold: {ruleThreshold}%</label>
              <input
                type="range" min={0} max={100} step={5} value={ruleThreshold}
                onChange={(e) => setRuleThreshold(e.target.value)}
                className="w-full accent-white"
              />
            </div>
            <input
              value={ruleDescription}
              onChange={(e) => setRuleDescription(e.target.value)}
              placeholder="Description with {source} and {target}"
              className="w-full bg-zinc-950 border border-zinc-700 rounded text-xs text-white placeholder:text-zinc-600 h-8 px-2 focus:outline-none focus:border-zinc-600 transition-colors"
            />
            <button
              onClick={() => void handleAddRule()}
              disabled={!ruleName.trim() || !ruleEdgeType.trim() || !ruleSourceType.trim() || !ruleTargetType.trim()}
              className="w-full h-8 bg-white text-black hover:bg-zinc-200 text-xs font-bold rounded flex items-center justify-center gap-1.5 disabled:opacity-40 transition-colors"
            >
              Add Rule
            </button>
          </div>
        )}

        <div className="space-y-2">
          {rules.map((rule) => (
            <div key={rule.id} className="p-2.5 rounded-lg border border-zinc-800 bg-zinc-900 group">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-semibold text-white truncate">{rule.name}</span>
                    {rule.source === 'custom' && (
                      <span className="px-1.5 py-0.5 rounded text-[8px] bg-zinc-800 text-zinc-300 border border-zinc-700/50 font-bold shrink-0">CUSTOM</span>
                    )}
                  </div>
                  <div className="text-[10px] text-zinc-500 mt-0.5 flex items-center gap-1 flex-wrap">
                    <span className="text-emerald-400">{rule.sourceType}</span>
                    <ChevronRight className="w-2.5 h-2.5 text-zinc-700" />
                    <span className="text-zinc-400 font-medium">{rule.edgeType}</span>
                    <ChevronRight className="w-2.5 h-2.5 text-zinc-700" />
                    <span className="text-sky-400">{rule.targetType}</span>
                  </div>
                  <div className="text-[10px] text-zinc-600 mt-1">
                    Threshold: {(rule.threshold * 100).toFixed(0)}%
                    {rule.description && rule.description !== '{source} -> {target}' && (
                      <span className="ml-1.5 text-zinc-700">· {rule.description.slice(0, 40)}</span>
                    )}
                  </div>
                </div>
                {rule.source === 'custom' && (
                  <button
                    onClick={() => void deleteRule(rule.id)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-600 hover:text-rose-400 shrink-0 p-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
          {rules.length === 0 && (
            <div className="text-center py-6">
              <Cpu className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
              <p className="text-[10px] text-zinc-600">No rules loaded.</p>
              <p className="text-[9px] text-zinc-700 mt-1">Add custom rules to derive new facts.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
