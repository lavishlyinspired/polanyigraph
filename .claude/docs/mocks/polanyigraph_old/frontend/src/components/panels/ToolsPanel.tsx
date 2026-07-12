import { useState } from 'react';
import { Wrench, Shield, Check, X, Search, Plus, Trash2, Code, Database, Eye } from 'lucide-react';

interface MockSkill {
  id: string;
  name: string;
  description: string;
  active: boolean;
  content: string;
}

const INITIAL_SKILLS: MockSkill[] = [
  {
    id: '1',
    name: 'Tactical Search Grounding',
    description: 'Enables real-time web search and groundings to resolve entity ambiguity during ingestion.',
    active: true,
    content: `# Tactical Search Grounding Skill\\n\\nAllows the neural-agent to ground entity recognition using live Google Search query logs.\\n\\n**Usage requirements:**\\n- Strict mode: Enabled\\n- Confidence cutoff: >= 75%\\n\\n**Heuristics targeted:**\\n- Presupposition resolution\\n- Implied future event verification`,
  },
  {
    id: '2',
    name: 'Ontology Mapping Coercion',
    description: 'Resolves structural mismatch during rule-matching via hierarchical subclass coercion.',
    active: true,
    content: `# Ontology Mapping Coercion\\n\\nMoves beyond exact string literal mapping. Translates source facts into parent/child ontology classes dynamically during Spread Activation phases.\\n\\n**Classes supported:**\\n- All FIBO core banking & investment schema classes`,
  },
  {
    id: '3',
    name: 'Implicit Fact Extraction',
    description: 'Drives Polanyi\'s tacit knowledge heuristics to extract implicit relationships from unstructured text.',
    active: true,
    content: `# Tacit Knowledge Extraction\\n\\nFires the 11 modular Polanyi cognitive filters over active node clusters to generate provisional implicit facts.`,
  },
  {
    id: '4',
    name: 'Neural Heatmap Activation',
    description: 'Calculates structural salience using multi-hop activation propagation over directed edges.',
    active: false,
    content: `# Neural Heatmap Activation\\n\\nCalculates continuous numeric activation levels for all connected nodes. Decays by 15% per hop, normalized to [0, 1.00] range.`,
  },
  {
    id: '5',
    name: 'Datalog Engine Optimizer',
    description: 'Compiles natural language questions into high-performance, validated Datalog pattern queries.',
    active: false,
    content: `# Datalog Engine Optimizer\\n\\nTranslates unstructured user intents into structured triple pattern matchers, bypassing standard semantic vector lookups.`,
  },
  {
    id: '6',
    name: 'Semantic Community Detection',
    description: 'Partitions complex, dense clusters using modularity-based Louvain community algorithms.',
    active: true,
    content: `# Louvain Community Detection\\n\\nDetects dense localized sub-structures in the graph canvas, writing back community ID badges onto node models.`,
  },
];

interface MemoryItem {
  key: string;
  value: string;
  source: string;
}

export function ToolsPanel() {
  const [tab, setTab] = useState<'skills' | 'memory'>('skills');

  // Skills State
  const [skills, setSkills] = useState<MockSkill[]>(INITIAL_SKILLS);
  const [expandedSkillId, setExpandedSkillId] = useState<string | null>(null);

  // Memory State
  const [memories, setMemories] = useState<MemoryItem[]>([
    { key: 'preferred_currency', value: 'Swiss Franc (CHF)', source: 'User profile conversation' },
    { key: 'strict_ontology_checking', value: 'true', source: 'OntologyPanel toggle' },
    { key: 'neural_activation_decay', value: '0.15', source: 'ReasoningPanel config' },
    { key: 'last_selected_graph', value: 'default_banking_ecosystem', source: 'Session state' },
  ]);
  const [searchQuery, setSearchQuery] = useState('');
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');

  const toggleSkill = (id: string) => {
    setSkills(prev =>
      prev.map(s => (s.id === id ? { ...s, active: !s.active } : s))
    );
  };

  const handleAddMemory = () => {
    if (!newKey.trim() || !newValue.trim()) return;
    setMemories(prev => [
      ...prev,
      { key: newKey.trim(), value: newValue.trim(), source: 'Manual entry' },
    ]);
    setNewKey('');
    setNewValue('');
  };

  const handleDeleteMemory = (key: string) => {
    setMemories(prev => prev.filter(m => m.key !== key));
  };

  const filteredMemories = memories.filter(
    m =>
      m.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.value.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="h-full flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* Tab Switcher */}
      <div className="p-3 border-b border-zinc-800 bg-zinc-900/10 flex shrink-0">
        <div className="w-full grid grid-cols-2 gap-1 p-0.5 rounded-lg bg-zinc-950 border border-zinc-800/80">
          <button
            onClick={() => setTab('skills')}
            className={`py-1 text-[10px] font-semibold rounded flex items-center justify-center gap-1.5 transition-all duration-150 ${
              tab === 'skills'
                ? 'bg-zinc-800 text-white shadow-sm'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Code className="w-3 h-3" />
            <span>Agent Skills</span>
          </button>
          <button
            onClick={() => setTab('memory')}
            className={`py-1 text-[10px] font-semibold rounded flex items-center justify-center gap-1.5 transition-all duration-150 ${
              tab === 'memory'
                ? 'bg-zinc-800 text-white shadow-sm'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Database className="w-3 h-3" />
            <span>Memory Inspector</span>
          </button>
        </div>
      </div>

      {/* Main Panel Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {tab === 'skills' ? (
          <div className="space-y-3">
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-bold">
              Active Agent Tools & Skills ({skills.filter(s => s.active).length} / {skills.length})
            </div>

            <div className="space-y-2">
              {skills.map(skill => {
                const isExpanded = expandedSkillId === skill.id;
                return (
                  <div
                    key={skill.id}
                    className="rounded-lg border border-zinc-800 bg-zinc-900/20 overflow-hidden transition-all"
                  >
                    <div className="p-3 flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-white">{skill.name}</span>
                          <span
                            className={`px-1.5 py-0.5 rounded-[4px] text-[8px] font-bold uppercase ${
                              skill.active
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'bg-zinc-800 text-zinc-500 border border-zinc-700/50'
                            }`}
                          >
                            {skill.active ? 'active' : 'inactive'}
                          </span>
                        </div>
                        <p className="text-[10px] text-zinc-400 mt-1 leading-relaxed">{skill.description}</p>
                      </div>

                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => setExpandedSkillId(isExpanded ? null : skill.id)}
                          className="p-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
                          title="View SKILL.md specs"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => toggleSkill(skill.id)}
                          className={`p-1 rounded text-xs font-bold transition-all ${
                            skill.active
                              ? 'bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 border border-rose-500/20'
                              : 'bg-blue-600 text-white hover:bg-blue-500'
                          }`}
                        >
                          {skill.active ? 'Disable' : 'Enable'}
                        </button>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="px-3 pb-3 pt-1 border-t border-zinc-800/50 bg-zinc-950/60 font-mono text-[9px] text-zinc-400 leading-normal whitespace-pre-line">
                        {skill.content}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Search Box */}
            <div className="space-y-1.5">
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider font-bold block">
                Search Cognitive Memory
              </label>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-zinc-600" />
                <input
                  type="text"
                  placeholder="Filter keys, values, or context..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-white placeholder:text-zinc-600 h-9 pl-8 pr-3 focus:outline-none focus:border-zinc-700 transition-colors"
                />
              </div>
            </div>

            {/* Memory List */}
            <div className="space-y-2">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-bold">
                Stored Agent State & Preferences ({filteredMemories.length})
              </div>

              {filteredMemories.length === 0 ? (
                <div className="p-4 rounded-lg border border-zinc-800 bg-zinc-900/10 text-center text-[10px] text-zinc-600">
                  No memory parameters match your query.
                </div>
              ) : (
                <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
                  {filteredMemories.map(m => (
                    <div
                      key={m.key}
                      className="p-2 rounded-lg bg-zinc-900/30 border border-zinc-800/80 flex items-start justify-between gap-3 text-[10px]"
                    >
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center gap-1.5 font-mono text-zinc-500">
                          <span className="text-zinc-300 font-bold break-all">{m.key}</span>
                          <span>•</span>
                          <span className="text-[9px] truncate">{m.source}</span>
                        </div>
                        <div className="text-zinc-400 font-mono break-all">{m.value}</div>
                      </div>
                      <button
                        onClick={() => handleDeleteMemory(m.key)}
                        className="p-1 rounded text-zinc-600 hover:text-rose-400 transition-colors shrink-0"
                        title="Forget memory key"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Add Memory Key Form */}
            <div className="p-3 rounded-lg border border-zinc-800/80 bg-zinc-900/10 space-y-2.5">
              <div className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider">
                Write State Parameter
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder="parameter_key"
                  value={newKey}
                  onChange={e => setNewKey(e.target.value)}
                  className="bg-zinc-950 border border-zinc-800 rounded text-xs text-white placeholder:text-zinc-700 h-8 px-2 focus:outline-none focus:border-zinc-700 font-mono"
                />
                <input
                  type="text"
                  placeholder="value"
                  value={newValue}
                  onChange={e => setNewValue(e.target.value)}
                  className="bg-zinc-950 border border-zinc-800 rounded text-xs text-white placeholder:text-zinc-700 h-8 px-2 focus:outline-none focus:border-zinc-700 font-mono"
                />
              </div>
              <button
                onClick={handleAddMemory}
                className="w-full py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-xs font-semibold text-white flex items-center justify-center gap-1.5 transition-colors border border-zinc-700/50"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Inject State Parameter</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
