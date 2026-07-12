import { useEffect, useState } from 'react';
import { 
  Cpu, Plus, Trash2, X, ChevronRight, GitBranch, AlertCircle, Info, 
  Layers, BookOpen, ChevronDown, Check, Sliders, HelpCircle, FileJson
} from 'lucide-react';
import { useGraphStore } from '../../stores/graphStore';
import { api, type OntologySchemaResponse } from '../../lib/api';

const SELECT_CLS = 'w-full bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-white h-9 px-3 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all appearance-none cursor-pointer';
const INPUT_CLS = 'w-full bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-white placeholder:text-zinc-700 h-9 px-3 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all';

export function LogicPage() {
  const {
    rules, ontologyClasses, ontologyProperties,
    addNode, createRule, deleteRule,
  } = useGraphStore();

  const [schema, setSchema] = useState<OntologySchemaResponse | null>(null);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [schemaError, setSchemaError] = useState<string | null>(null);

  // Form states for rule definition
  const [ruleName, setRuleName] = useState('');
  const [ruleSourceType, setRuleSourceType] = useState('');
  const [ruleEdgeType, setRuleEdgeType] = useState('');
  const [ruleTargetType, setRuleTargetType] = useState('');
  const [ruleThreshold, setRuleThreshold] = useState('35');
  const [ruleDescription, setRuleDescription] = useState('{source} matches {target} threshold');

  // Node additions
  const [newNodeLabel, setNewNodeLabel] = useState('');
  const [newNodeType, setNewNodeType] = useState('');

  // Expand categories
  const [expandSubclass, setExpandSubclass] = useState(true);
  const [expandClasses, setExpandClasses] = useState(true);
  const [expandProperties, setExpandProperties] = useState(true);

  useEffect(() => {
    setLoadingSchema(true);
    setSchemaError(null);
    api.getOntology()
      .then(setSchema)
      .catch((e) => setSchemaError(String(e)))
      .finally(() => setLoadingSchema(false));
  }, []);

  const handleAddRule = async (e: React.FormEvent) => {
    e.preventDefault();
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
    setRuleSourceType('');
    setRuleEdgeType('');
    setRuleTargetType('');
    setRuleThreshold('35');
    setRuleDescription('{source} matches {target} threshold');
  };

  const handleAddNode = async () => {
    if (!newNodeLabel.trim() || !newNodeType.trim()) return;
    await addNode(newNodeLabel.trim(), newNodeType.trim());
    setNewNodeLabel('');
    setNewNodeType('');
  };

  return (
    <div className="h-full flex-1 flex overflow-hidden bg-zinc-950">
      
      {/* 1. LEFT PANEL - Ontology Schema Explorer */}
      <div className="w-[420px] border-r border-zinc-800 flex flex-col min-w-0 bg-zinc-950/20">
        <div className="p-4 border-b border-zinc-800 bg-zinc-900/10 flex shrink-0 items-center gap-2">
          <BookOpen className="w-4 h-4 text-indigo-400" />
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Ontology Schema Registry
            </h3>
            <p className="text-[9px] text-zinc-500 mt-0.5">
              {schema ? `${schema.classCount} classes · ${schema.propertyCount} relationships loaded` : 'Loading registry...'}
            </p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
          {loadingSchema ? (
            <div className="h-48 flex items-center justify-center text-zinc-500 text-[11px] font-mono gap-1.5">
              <div className="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
              Loading schema constraints...
            </div>
          ) : schemaError ? (
            <div className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/5 text-xs text-rose-400 font-mono">
              <AlertCircle className="w-4 h-4 inline mr-1.5" /> {schemaError}
            </div>
          ) : schema ? (
            <div className="space-y-4">
              {/* Class Hierarchy Section */}
              {schema.subclassOf.length > 0 && (
                <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-950/40">
                  <button
                    onClick={() => setExpandSubclass(!expandSubclass)}
                    className="w-full px-3 py-2.5 flex items-center justify-between hover:bg-zinc-900/40 transition-colors"
                  >
                    <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
                      <GitBranch className="w-3.5 h-3.5 text-indigo-400" /> Subclass Hierarchies ({schema.subclassOf.length})
                    </span>
                    {expandSubclass ? <ChevronDown className="w-3.5 h-3.5 text-zinc-600" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />}
                  </button>
                  {expandSubclass && (
                    <div className="px-3.5 pb-3 pt-1.5 border-t border-zinc-800/40 space-y-1.5">
                      {schema.subclassOf.map((rel, i) => (
                        <div key={i} className="text-[11px] font-mono text-zinc-400 flex items-center gap-1.5">
                          <span className="text-indigo-400 font-semibold">{rel.child}</span>
                          <span className="text-zinc-600">is subclass of</span>
                          <span className="text-emerald-400 font-semibold">{rel.parent}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Classes Registry */}
              <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-950/40">
                <button
                  onClick={() => setExpandClasses(!expandClasses)}
                  className="w-full px-3 py-2.5 flex items-center justify-between hover:bg-zinc-900/40 transition-colors"
                >
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-zinc-400" /> Declared Classes ({schema.classCount})
                  </span>
                  {expandClasses ? <ChevronDown className="w-3.5 h-3.5 text-zinc-600" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />}
                </button>
                {expandClasses && (
                  <div className="px-3.5 pb-3 pt-1.5 border-t border-zinc-800/40 divide-y divide-zinc-850">
                    {schema.classes.map((cls, i) => (
                      <div key={i} className="py-2 first:pt-0 last:pb-0">
                        <div className="text-[11px] font-mono font-bold text-zinc-200">{cls.label}</div>
                        {cls.comment && (
                          <div className="text-[10px] text-zinc-500 mt-0.5 leading-relaxed">{cls.comment}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Properties domain / range constraints */}
              <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-950/40">
                <button
                  onClick={() => setExpandProperties(!expandProperties)}
                  className="w-full px-3 py-2.5 flex items-center justify-between hover:bg-zinc-900/40 transition-colors"
                >
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
                    <Sliders className="w-3.5 h-3.5 text-violet-400" /> Property Domains & Ranges ({schema.propertyCount})
                  </span>
                  {expandProperties ? <ChevronDown className="w-3.5 h-3.5 text-zinc-600" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />}
                </button>
                {expandProperties && (
                  <div className="px-3.5 pb-3 pt-1.5 border-t border-zinc-800/40 space-y-2.5">
                    {schema.properties.map((prop, i) => (
                      <div key={i} className="text-[11px]">
                        <div className="font-mono text-violet-400 font-bold">{prop.label}</div>
                        <div className="flex items-center gap-2 text-[9px] text-zinc-500 mt-0.5 font-mono">
                          {prop.domain && (
                            <span>domain: <strong className="text-zinc-400">{prop.domain}</strong></span>
                          )}
                          {prop.domain && prop.range && <span>·</span>}
                          {prop.range && (
                            <span>range: <strong className="text-zinc-400">{prop.range}</strong></span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center py-10 text-zinc-600 font-mono text-[10px]">
              No ontology registry details loaded.
            </div>
          )}
        </div>

        {/* Mini Manual Node Creator inside schema panel */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-900/10 space-y-2.5">
          <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1">
            <Plus className="w-3.5 h-3.5 text-zinc-400" /> Manual Concept Injector
          </div>
          <div className="space-y-2">
            <input
              value={newNodeLabel}
              onChange={(e) => setNewNodeLabel(e.target.value)}
              placeholder="Inject new node label..."
              className={INPUT_CLS}
            />
            <div className="relative">
              <select
                value={newNodeType}
                onChange={(e) => setNewNodeType(e.target.value)}
                className={SELECT_CLS}
              >
                <option value="" disabled>Select schema type...</option>
                {ontologyClasses.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-zinc-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
            <button
              onClick={() => void handleAddNode()}
              disabled={!newNodeLabel.trim() || !newNodeType.trim()}
              className="w-full h-8.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white border border-zinc-700/50 text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40"
            >
              <Plus className="w-3.5 h-3.5 text-indigo-400" /> Inject Concept to Store
            </button>
          </div>
        </div>
      </div>

      {/* 2. RIGHT PANEL - Logical Deduction Rules Management */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="p-4 border-b border-zinc-800 bg-zinc-900/10 shrink-0 flex items-center justify-between">
          <div>
            <h2 className="text-[13px] font-bold text-white tracking-wider uppercase flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-400" /> Logical Deduction Workspace
            </h2>
            <p className="text-[10px] text-zinc-500 mt-0.5">Define First-Order Horn Clauses and confidence bounds to resolve implicit triples</p>
          </div>
        </div>

        {/* Content split or stack */}
        <div className="flex-1 overflow-y-auto p-4 space-y-5 min-h-0">
          
          <div className="grid grid-cols-12 gap-5">
            {/* Rule builder form */}
            <form onSubmit={handleAddRule} className="col-span-12 lg:col-span-5 p-4 rounded-xl border border-zinc-800 bg-zinc-950/40 space-y-3">
              <div className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5 mb-1.5">
                <Plus className="w-4 h-4 text-emerald-400" /> Rule Composer
              </div>

              <div className="space-y-1">
                <label className="text-[9px] font-mono text-zinc-500 uppercase font-bold tracking-wider">Rule name / identifier</label>
                <input
                  value={ruleName}
                  onChange={(e) => setRuleName(e.target.value)}
                  placeholder="e.g. regulatory_oversight_bank"
                  required
                  className={INPUT_CLS}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[9px] font-mono text-zinc-500 uppercase font-bold tracking-wider">Premise Type (A)</label>
                  <div className="relative">
                    <select
                      value={ruleSourceType}
                      onChange={(e) => setRuleSourceType(e.target.value)}
                      required
                      className={SELECT_CLS}
                    >
                      <option value="" disabled>Select...</option>
                      {ontologyClasses.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <ChevronDown className="w-3.5 h-3.5 text-zinc-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[9px] font-mono text-zinc-500 uppercase font-bold tracking-wider">Consequent Type (B)</label>
                  <div className="relative">
                    <select
                      value={ruleTargetType}
                      onChange={(e) => setRuleTargetType(e.target.value)}
                      required
                      className={SELECT_CLS}
                    >
                      <option value="" disabled>Select...</option>
                      {ontologyClasses.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <ChevronDown className="w-3.5 h-3.5 text-zinc-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  </div>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[9px] font-mono text-zinc-500 uppercase font-bold tracking-wider">Assigned Relation Edge Type (A → B)</label>
                <div className="relative">
                  <select
                    value={ruleEdgeType}
                    onChange={(e) => setRuleEdgeType(e.target.value)}
                    required
                    className={SELECT_CLS}
                  >
                    <option value="" disabled>Select relation...</option>
                    {ontologyProperties.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                  <ChevronDown className="w-3.5 h-3.5 text-zinc-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>
              </div>

              <div className="space-y-1 pt-1">
                <div className="flex items-center justify-between text-[9px] font-mono text-zinc-500 uppercase font-bold tracking-wider">
                  <span>Activation Limit Bound</span>
                  <span className="text-indigo-400 font-bold">{ruleThreshold}%</span>
                </div>
                <input
                  type="range" min={0} max={100} step={5} value={ruleThreshold}
                  onChange={(e) => setRuleThreshold(e.target.value)}
                  className="w-full accent-indigo-500 cursor-pointer h-1.5 bg-zinc-800 rounded-lg appearance-none"
                />
                <p className="text-[8px] text-zinc-600">The premise node must meet this neural activation value to fire.</p>
              </div>

              <div className="space-y-1">
                <label className="text-[9px] font-mono text-zinc-500 uppercase font-bold tracking-wider">Explanation Template</label>
                <input
                  value={ruleDescription}
                  onChange={(e) => setRuleDescription(e.target.value)}
                  placeholder="e.g. {source} regulates universal system {target}"
                  className={INPUT_CLS}
                />
              </div>

              <button
                type="submit"
                className="w-full h-9.5 mt-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-lg flex items-center justify-center gap-1.5 transition-all shadow-md shadow-indigo-500/10"
              >
                <Plus className="w-4 h-4" /> Save & Deploy Rule
              </button>
            </form>

            {/* Explanation box on Horn clauses */}
            <div className="col-span-12 lg:col-span-7 p-4.5 rounded-xl border border-dashed border-zinc-800 flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex items-center gap-1.5 text-zinc-400 text-xs font-mono font-bold uppercase tracking-wider">
                  <HelpCircle className="w-4 h-4 text-indigo-400" /> Neurosymbolic Horn Clauses
                </div>
                <div className="text-[11px] text-zinc-400 space-y-2 leading-relaxed">
                  <p>In this architecture, logical deduction is formalized as a First-Order Horn Clause integrated with spreading activation thresholds:</p>
                  <div className="p-2.5 rounded border border-zinc-800 bg-zinc-950 font-mono text-[10px] text-zinc-300">
                    <span className="text-amber-400">hasActivation(S, Act)</span>, <span className="text-emerald-400">Act &gt; Threshold</span>, <span className="text-violet-400">predicate(S, T)</span> <br />
                    <span className="text-zinc-500">→</span> <span className="text-sky-400 font-bold">impliesRelation(S, T, edgeType)</span>
                  </div>
                  <p>When the neural spreading activation step floods nodes, if any concept of type <strong className="text-zinc-300">Premise Type</strong> passes the <strong className="text-indigo-400">Activation Limit Bound</strong>, the symbolic compiler fires this rule over matching ontology paths, creating derived edges and feeding back activation into targets.</p>
                </div>
              </div>
              
              <div className="p-3.5 rounded-lg border border-indigo-500/10 bg-indigo-500/5 flex gap-2.5 items-start mt-3">
                <FileJson className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                <div className="text-[10px] text-zinc-400 leading-relaxed font-sans">
                  <strong className="text-zinc-200">Ontology Resolution Support:</strong> The engine automatically matches subclasses. For example, if a rule is defined over <code className="text-emerald-400">fibo:FinancialInstitution</code>, any concept labeled as <code className="text-sky-400">fibo:Bank</code> (subclass of FinancialInstitution) will successfully fire, logging a multi-hop ontological proof trace.
                </div>
              </div>
            </div>
          </div>

          {/* Rules Grid */}
          <div className="space-y-3">
            <div className="text-xs font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-indigo-400" /> Active Rules Registry ({rules.length})
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {rules.map((rule) => (
                <div key={rule.id} className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/30 group relative hover:border-zinc-700 transition-all">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white truncate">{rule.name}</span>
                        {rule.source === 'custom' ? (
                          <span className="px-2 py-0.5 rounded text-[8px] bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-bold tracking-wider uppercase font-mono">
                            Custom
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[8px] bg-zinc-800 text-zinc-400 border border-zinc-700/50 font-bold tracking-wider uppercase font-mono">
                            Core
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] font-mono text-zinc-500 flex items-center gap-1.5 flex-wrap">
                        <span className="text-emerald-400 font-semibold">{rule.sourceType}</span>
                        <ChevronRight className="w-3 h-3 text-zinc-700 shrink-0" />
                        <span className="text-violet-400 font-bold">{rule.edgeType}</span>
                        <ChevronRight className="w-3 h-3 text-zinc-700 shrink-0" />
                        <span className="text-sky-400 font-semibold">{rule.targetType}</span>
                      </div>
                      <div className="text-[10px] text-zinc-400 leading-relaxed pt-1 border-t border-zinc-800/40">
                        {rule.description || '{source} → {target}'}
                      </div>
                      <div className="text-[10px] font-mono text-zinc-500 flex items-center gap-2 pt-1">
                        <span>Threshold: <strong className="text-zinc-300 font-bold">{(rule.threshold * 100).toFixed(0)}%</strong></span>
                        {rule.weight !== undefined && (
                          <>
                            <span>·</span>
                            <span>Weight: <strong className="text-zinc-300 font-bold">{rule.weight}</strong></span>
                          </>
                        )}
                      </div>
                    </div>

                    {rule.source === 'custom' && (
                      <button
                        onClick={() => void deleteRule(rule.id)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-500 hover:text-rose-400 p-1.5 rounded-lg hover:bg-rose-500/10 shrink-0 self-start"
                        title="Delete custom rule"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {rules.length === 0 && (
                <div className="col-span-2 text-center py-10 rounded-xl border border-dashed border-zinc-800 text-zinc-600">
                  <Cpu className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
                  <p className="text-[11px] font-mono">No rules deployed in active session memory.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
