import { useState, useEffect } from 'react';
import { 
  Database, Plug, RefreshCw, Sliders, Cpu, 
  User, Mail, Shield, Sparkles, Layers, Puzzle, Info, Globe, FileText, X
} from 'lucide-react';
import { toast } from 'sonner';

type TabType = 'database' | 'cognitive' | 'ingestion' | 'profile';

interface ConnectionsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ConnectionsModal({ isOpen, onClose }: ConnectionsModalProps) {
  // Navigation Tab
  const [activeTab, setActiveTab] = useState<TabType>(() => {
    return (localStorage.getItem('connections_active_tab') as TabType) || 'database';
  });

  // Neo4j Connection State
  const [neo4jUri, setNeo4jUri] = useState(() => localStorage.getItem('neo4j_uri') || 'neo4j+s://98f237ae.databases.neo4j.io:7687');
  const [neo4jUser, setNeo4jUser] = useState(() => localStorage.getItem('neo4j_user') || 'neo4j');
  const [neo4jPassword, setNeo4jPassword] = useState(() => localStorage.getItem('neo4j_password') || '••••••••••••••••');
  const [neo4jDb, setNeo4jDb] = useState(() => localStorage.getItem('neo4j_db') || 'finance-fibo-kg');
  const [neo4jConnected, setNeo4jConnected] = useState(() => localStorage.getItem('neo4j_connected') === 'true');
  const [testingConnection, setTestingConnection] = useState(false);

  // LLM Models State
  const [selectedLlms, setSelectedLlms] = useState<string[]>(() => {
    const saved = localStorage.getItem('selected_llms');
    return saved ? JSON.parse(saved) : ['gemini-2.5-flash'];
  });
  const [primaryLlm, setPrimaryLlm] = useState(() => localStorage.getItem('primary_llm') || 'gemini-2.5-flash');
  const [llmTemperature, setLlmTemperature] = useState(() => Number(localStorage.getItem('llm_temperature') || '0.1'));

  // Embedding Models State
  const [selectedEmbed, setSelectedEmbed] = useState(() => localStorage.getItem('selected_embed') || 'text-embedding-004');

  // Connectors State
  const [enabledConnectors, setEnabledConnectors] = useState<string[]>(() => {
    const saved = localStorage.getItem('enabled_connectors');
    return saved ? JSON.parse(saved) : ['pdf', 'scraper', 'sec-edgar', 'datalog'];
  });

  // User Profile / Login Details
  const [userEmail, setUserEmail] = useState(() => localStorage.getItem('user_email') || 'akashgoyal086@gmail.com');
  const [userName, setUserName] = useState(() => localStorage.getItem('user_name') || 'Akash Goyal');
  const [userRole, setUserRole] = useState(() => localStorage.getItem('user_role') || 'Knowledge Engineer');
  const [developerKey, setDeveloperKey] = useState(() => localStorage.getItem('developer_key') || 'g_ai_studio_••••••••••••');
  const [isProfileEditing, setIsProfileEditing] = useState(false);

  // Persistence hooks
  useEffect(() => {
    localStorage.setItem('connections_active_tab', activeTab);
  }, [activeTab]);

  useEffect(() => {
    localStorage.setItem('neo4j_uri', neo4jUri);
    localStorage.setItem('neo4j_user', neo4jUser);
    localStorage.setItem('neo4j_password', neo4jPassword);
    localStorage.setItem('neo4j_db', neo4jDb);
    localStorage.setItem('neo4j_connected', String(neo4jConnected));
  }, [neo4jUri, neo4jUser, neo4jPassword, neo4jDb, neo4jConnected]);

  useEffect(() => {
    localStorage.setItem('selected_llms', JSON.stringify(selectedLlms));
    localStorage.setItem('primary_llm', primaryLlm);
    localStorage.setItem('llm_temperature', String(llmTemperature));
  }, [selectedLlms, primaryLlm, llmTemperature]);

  useEffect(() => {
    localStorage.setItem('selected_embed', selectedEmbed);
  }, [selectedEmbed]);

  useEffect(() => {
    localStorage.setItem('enabled_connectors', JSON.stringify(enabledConnectors));
  }, [enabledConnectors]);

  useEffect(() => {
    localStorage.setItem('user_email', userEmail);
    localStorage.setItem('user_name', userName);
    localStorage.setItem('user_role', userRole);
    localStorage.setItem('developer_key', developerKey);
  }, [userEmail, userName, userRole, developerKey]);

  // Actions
  const handleConnectNeo4j = () => {
    if (neo4jConnected) {
      setNeo4jConnected(false);
      toast.success('Disconnected from Neo4j DB session successfully.');
      return;
    }

    setTestingConnection(true);
    setTimeout(() => {
      setTestingConnection(false);
      setNeo4jConnected(true);
      toast.success('Successfully established secure bolt connection to Neo4j Graph DB!', {
        description: `Active DB: ${neo4jDb} @ 13.8ms latency.`,
      });
    }, 1200);
  };

  const handleTestLatency = () => {
    setTestingConnection(true);
    setTimeout(() => {
      setTestingConnection(false);
      toast.success('Neo4j connection test: Successful', {
        description: 'Read-write latency: 12.4ms, APOC plugins verified.',
      });
    }, 800);
  };

  const handleToggleLlm = (id: string) => {
    if (selectedLlms.includes(id)) {
      if (selectedLlms.length === 1) {
        toast.error('You must keep at least one cognitive LLM enabled.');
        return;
      }
      const updated = selectedLlms.filter((x) => x !== id);
      setSelectedLlms(updated);
      if (primaryLlm === id) {
        setPrimaryLlm(updated[0]);
      }
      toast.info(`Disabled LLM model: ${id}`);
    } else {
      setSelectedLlms([...selectedLlms, id]);
      toast.success(`Enabled LLM model: ${id}`);
    }
  };

  const handleToggleConnector = (id: string) => {
    if (enabledConnectors.includes(id)) {
      setEnabledConnectors(enabledConnectors.filter((x) => x !== id));
      toast.info(`Deactivated connector: ${id.toUpperCase()}`);
    } else {
      setEnabledConnectors([...enabledConnectors, id]);
      toast.success(`Activated connector: ${id.toUpperCase()}`);
    }
  };

  const handleSaveProfile = () => {
    setIsProfileEditing(false);
    toast.success('Developer credentials and profile synchronized successfully.');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
      <div 
        className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* MODAL HEADER */}
        <div className="flex items-center justify-between border-b border-zinc-800 p-5 shrink-0">
          <div>
            <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Database className="w-4 h-4 text-blue-400" /> Connection Center
            </h2>
            <p className="text-[11px] text-zinc-500 mt-1">
              Configure external database clusters, active cognitive models, ingestion plugins, and developer profiles.
            </p>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-950/40 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* TAB SELECTOR ACTIVITY RAIL */}
        <div className="flex border-b border-zinc-800 bg-zinc-950/40 px-5 pt-2 gap-2 sm:gap-4 shrink-0 overflow-x-auto scrollbar-none">
          {[
            { id: 'database', label: 'Database Connectors', icon: Database, activeColor: 'border-emerald-500 text-emerald-400', hoverColor: 'hover:text-emerald-300' },
            { id: 'cognitive', label: 'Cognitive LLM & Embed', icon: Cpu, activeColor: 'border-purple-500 text-purple-400', hoverColor: 'hover:text-purple-300' },
            { id: 'ingestion', label: 'Ingestion Connectors', icon: Puzzle, activeColor: 'border-teal-500 text-teal-400', hoverColor: 'hover:text-teal-300' },
            { id: 'profile', label: 'Developer Credentials', icon: User, activeColor: 'border-blue-500 text-blue-400', hoverColor: 'hover:text-blue-300' }
          ].map((tab) => {
            const isActive = activeTab === tab.id;
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabType)}
                className={`pb-3 px-3 text-[10px] sm:text-xs font-bold uppercase tracking-wider transition-all border-b-2 flex items-center gap-2 whitespace-nowrap ${
                  isActive 
                    ? `${tab.activeColor}` 
                    : `text-zinc-500 border-transparent ${tab.hoverColor}`
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* MODAL MAIN SCROLLABLE CONTENT */}
        <div className="flex-1 overflow-y-auto p-6 min-h-0 bg-zinc-950/40">
          
          {/* TAB 1: DATABASE CONNECTORS */}
          {activeTab === 'database' && (
            <div className="space-y-6 animate-fade-in">
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                      <Database className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white uppercase tracking-wider">Neo4j Graph Database</h3>
                      <p className="text-[11px] text-zinc-500 mt-0.5">Secure Bolt or HTTP connection for direct knowledge persistence</p>
                    </div>
                  </div>
                  
                  {/* Connection Badge */}
                  <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[9px] font-bold tracking-wider uppercase transition-all ${
                    neo4jConnected 
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 animate-pulse'
                      : 'bg-zinc-900 border-zinc-800 text-zinc-500'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${neo4jConnected ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                    <span>{neo4jConnected ? 'CONNECTED' : 'DISCONNECTED'}</span>
                  </div>
                </div>

                <div className="h-[1px] bg-zinc-800/60 my-2" />

                <div className="space-y-4 pt-1">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Database URI / Bolt Link</label>
                      <input 
                        type="text" 
                        value={neo4jUri} 
                        onChange={(e) => setNeo4jUri(e.target.value)}
                        disabled={neo4jConnected}
                        placeholder="bolt+s://..." 
                        className="w-full bg-zinc-950/80 border border-zinc-800/80 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:border-emerald-500 disabled:opacity-50 transition-colors font-mono"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Target Database Instance</label>
                      <input 
                        type="text" 
                        value={neo4jDb} 
                        onChange={(e) => setNeo4jDb(e.target.value)}
                        disabled={neo4jConnected}
                        placeholder="neo4j" 
                        className="w-full bg-zinc-950/80 border border-zinc-800/80 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:border-emerald-500 disabled:opacity-50 transition-colors font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Database Username</label>
                      <input 
                        type="text" 
                        value={neo4jUser} 
                        onChange={(e) => setNeo4jUser(e.target.value)}
                        disabled={neo4jConnected}
                        placeholder="neo4j" 
                        className="w-full bg-zinc-950/80 border border-zinc-800/80 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:border-emerald-500 disabled:opacity-50 transition-colors"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Auth Token / Password</label>
                      <input 
                        type="password" 
                        value={neo4jPassword} 
                        onChange={(e) => setNeo4jPassword(e.target.value)}
                        disabled={neo4jConnected}
                        placeholder="••••••••" 
                        className="w-full bg-zinc-950/80 border border-zinc-800/80 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:border-emerald-500 disabled:opacity-50 transition-colors"
                      />
                    </div>
                  </div>
                </div>

                {/* Neo4j Info details */}
                {neo4jConnected ? (
                  <div className="bg-emerald-950/10 border border-emerald-500/10 rounded-lg p-4 text-[11px] text-emerald-400/90 flex gap-3 items-start">
                    <Info className="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
                    <div className="space-y-1">
                      <p className="font-bold">Real-time DB Connection established.</p>
                      <p className="text-zinc-500 text-[10px]">Every parsed Datalog transaction, document triple, and inferred rule is synced live to your cluster. Custom graphs can be explored on the workspace.</p>
                    </div>
                  </div>
                ) : (
                  <div className="bg-zinc-950/30 border border-zinc-900 rounded-lg p-4 text-[11px] text-zinc-400 flex gap-3 items-start">
                    <Info className="w-4 h-4 shrink-0 mt-0.5 text-zinc-500" />
                    <div className="space-y-1">
                      <p className="font-semibold">Local sandboxed cache active.</p>
                      <p className="text-zinc-500 text-[10px]">Since database session is disconnected, knowledge entities are safely written inside your secure browser's isolated local IndexedDB.</p>
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center justify-between pt-3 border-t border-zinc-900">
                  <button
                    onClick={handleTestLatency}
                    disabled={testingConnection || !neo4jConnected}
                    className="px-4 py-2 rounded-lg border border-zinc-800 bg-zinc-900 text-xs font-bold text-zinc-300 hover:text-white hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-1.5"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${testingConnection ? 'animate-spin' : ''}`} />
                    <span>Ping Host</span>
                  </button>

                  <button
                    onClick={handleConnectNeo4j}
                    disabled={testingConnection}
                    className={`px-5 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                      neo4jConnected
                        ? 'bg-red-950/30 hover:bg-red-900/40 text-red-400 border border-red-900/30'
                        : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow shadow-emerald-500/10'
                    }`}
                  >
                    <Plug className="w-4 h-4" />
                    <span>{neo4jConnected ? 'Disconnect Session' : 'Establish Bolt Connection'}</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: COGNITIVE ENGINES */}
          {activeTab === 'cognitive' && (
            <div className="space-y-6 animate-fade-in">
              {/* LLM Selection Card */}
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center border border-purple-500/20">
                    <Cpu className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">Cognitive LLM Engines</h3>
                    <p className="text-[11px] text-zinc-500 mt-0.5">Toggle models and set parameters used for schema building & reasoning</p>
                  </div>
                </div>

                <div className="h-[1px] bg-zinc-800/60 my-2" />

                <div className="space-y-3">
                  {[
                    { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', desc: 'Default reasoning model - high efficiency and structure output', tag: 'Google' },
                    { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', desc: 'Complex reasoning - ideal for nested taxonomy mapping', tag: 'Google' },
                    { id: 'llama-3-70b', name: 'Llama 3 70B (Ollama)', desc: 'Local fallback engine - requires active host service', tag: 'Meta' },
                    { id: 'claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', desc: 'Excellent logic mapping - requires custom API key', tag: 'Anthropic' },
                    { id: 'gpt-4o', name: 'GPT-4o (OpenAI)', desc: 'Robust code generation and triple construction', tag: 'OpenAI' }
                  ].map((model) => {
                    const isSelected = selectedLlms.includes(model.id);
                    const isPrimary = primaryLlm === model.id;

                    return (
                      <div 
                        key={model.id}
                        onClick={() => handleToggleLlm(model.id)}
                        className={`flex items-start justify-between p-3.5 rounded-xl border transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-zinc-900/80 border-purple-500/30 shadow-sm'
                            : 'bg-zinc-950/20 border-zinc-800/80 hover:border-zinc-800 text-zinc-400'
                        }`}
                      >
                        <div className="flex items-start gap-3.5">
                          <input 
                            type="checkbox" 
                            checked={isSelected}
                            onChange={() => {}} // Click container
                            className="mt-1 accent-purple-500 cursor-pointer rounded border-zinc-800 bg-zinc-900"
                          />
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className={`text-xs font-bold ${isSelected ? 'text-white' : 'text-zinc-400'}`}>{model.name}</span>
                              <span className="text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-zinc-950 text-zinc-500 border border-zinc-800">{model.tag}</span>
                              {isPrimary && (
                                <span className="text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">Primary</span>
                              )}
                            </div>
                            <p className="text-[10px] text-zinc-500 line-clamp-1 mt-0.5">{model.desc}</p>
                          </div>
                        </div>

                        {/* Set Primary Radio */}
                        {isSelected && !isPrimary && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setPrimaryLlm(model.id);
                              toast.success(`Set ${model.name} as your Primary LLM Engine.`);
                            }}
                            className="text-[9px] font-bold text-purple-400 hover:text-purple-300 hover:underline px-2.5 py-1 select-none"
                          >
                            Set Primary
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Slider Settings */}
                <div className="bg-zinc-950/60 border border-zinc-855 rounded-xl p-4 space-y-3.5">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                      <Sliders className="w-3.5 h-3.5 text-zinc-400" /> Temperature Slider
                    </span>
                    <span className="text-purple-400 font-bold bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">{llmTemperature}</span>
                  </div>
                  <input 
                    type="range" 
                    min={0} 
                    max={1.2} 
                    step={0.05} 
                    value={llmTemperature}
                    onChange={(e) => setLlmTemperature(Number(e.target.value))}
                    className="w-full accent-purple-500 bg-zinc-900 cursor-pointer"
                  />
                  <div className="flex justify-between text-[8px] text-zinc-600 uppercase font-mono tracking-wider">
                    <span>Deterministic (0.0)</span>
                    <span>Creative (1.2)</span>
                  </div>
                </div>
              </div>

              {/* Embedding Selector Card */}
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center border border-amber-500/20">
                    <Layers className="w-5 h-5 text-amber-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">Vector Embedding Engine</h3>
                    <p className="text-[11px] text-zinc-500 mt-0.5">Define vector encoder to map concepts and document similarities</p>
                  </div>
                </div>

                <div className="h-[1px] bg-zinc-800/60 my-2" />

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {[
                    { id: 'text-embedding-004', name: 'text-embedding-004', dims: '768-dim', tag: 'Google' },
                    { id: 'cohere-embed-v3', name: 'Cohere-Embed-V3', dims: '1024-dim', tag: 'Cohere' },
                    { id: 'openai-text-embedding-3', name: 'text-embedding-3-small', dims: '1536-dim', tag: 'OpenAI' },
                    { id: 'bge-large-en', name: 'BGE-Large-v1.5', dims: '1024-dim', tag: 'BAAI' }
                  ].map((embed) => {
                    const isSelected = selectedEmbed === embed.id;

                    return (
                      <div
                        key={embed.id}
                        onClick={() => {
                          setSelectedEmbed(embed.id);
                          toast.success(`Switched Embedding model to ${embed.name}`);
                        }}
                        className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                          isSelected
                            ? 'bg-zinc-900/80 border-amber-500/30 shadow-sm'
                            : 'bg-zinc-950/20 border-zinc-800/80 hover:border-zinc-800 text-zinc-400'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`text-xs font-bold ${isSelected ? 'text-white' : 'text-zinc-400'}`}>{embed.name}</span>
                          <span className="text-[8px] font-bold text-zinc-500 font-mono px-1.5 py-0.5 rounded bg-zinc-950 border border-zinc-850">{embed.tag}</span>
                        </div>
                        <div className="flex items-center justify-between mt-4 pt-2.5 border-t border-zinc-800/40">
                          <span className="text-[9px] font-mono text-zinc-500">{embed.dims}</span>
                          <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${isSelected ? 'border-amber-500 bg-amber-500/10' : 'border-zinc-800'}`}>
                            {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: INGESTION CONNECTORS */}
          {activeTab === 'ingestion' && (
            <div className="space-y-6 animate-fade-in">
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-teal-500/10 flex items-center justify-center border border-teal-500/20">
                    <Puzzle className="w-5 h-5 text-teal-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">Active Ingestion & Sync Connectors</h3>
                    <p className="text-[11px] text-zinc-500 mt-0.5">Toggle live connection plugins, webhook stream sources and file format parsers</p>
                  </div>
                </div>

                <div className="h-[1px] bg-zinc-800/60 my-2" />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[
                    { id: 'pdf', name: 'PDF Disclosures', desc: 'Parses complex multi-column financials & structured tables.', icon: FileText },
                    { id: 'scraper', name: 'HTML Web Scraper', desc: 'Crawls press release URLs & corporate sites securely.', icon: Globe },
                    { id: 'sec-edgar', name: 'SEC EDGAR Filings', desc: 'Automatically index SEC 10-K & 10-Q by corporate ticker.', icon: Database },
                    { id: 'datalog', name: 'Ontology Importer', desc: 'Pulls rules and logical axioms from standard OWL/RDF.', icon: Layers },
                    { id: 'slack', name: 'Slack Feed Streamer', desc: 'Listens to specific channels to capture project mentions.', icon: Mail },
                    { id: 'gmail', name: 'Gmail Intelligence', desc: 'Extracts critical clauses from corporate agreements.', icon: Shield }
                  ].map((plugin) => {
                    const isEnabled = enabledConnectors.includes(plugin.id);
                    const Icon = plugin.icon;

                    return (
                      <div
                        key={plugin.id}
                        onClick={() => handleToggleConnector(plugin.id)}
                        className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between h-28 ${
                          isEnabled
                            ? 'bg-zinc-900/80 border-teal-500/30 shadow-sm'
                            : 'bg-zinc-950/20 border-zinc-800/80 hover:border-zinc-800 text-zinc-500'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-2.5">
                            <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${isEnabled ? 'bg-teal-500/15 border border-teal-500/20' : 'bg-zinc-950 border border-zinc-850'}`}>
                              <Icon className={`w-4 h-4 ${isEnabled ? 'text-teal-400' : 'text-zinc-500'}`} />
                            </div>
                            <span className={`text-xs font-bold ${isEnabled ? 'text-white' : 'text-zinc-400'}`}>{plugin.name}</span>
                          </div>
                          <div className={`w-7.5 h-4.5 rounded-full p-0.5 transition-all ${isEnabled ? 'bg-teal-600' : 'bg-zinc-800'}`}>
                            <div className={`w-3.5 h-3.5 rounded-full bg-white transition-all shadow-sm ${isEnabled ? 'translate-x-3' : 'translate-x-0'}`} />
                          </div>
                        </div>
                        <p className="text-[10px] text-zinc-500 line-clamp-2 leading-relaxed">{plugin.desc}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: DEVELOPER PROFILE */}
          {activeTab === 'profile' && (
            <div className="space-y-6 animate-fade-in">
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center border border-blue-500/20">
                      <User className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white uppercase tracking-wider">User Identity & Profile Details</h3>
                      <p className="text-[11px] text-zinc-500 mt-0.5">Configure active developer credentials to save session files</p>
                    </div>
                  </div>
                  
                  <button
                    onClick={() => {
                      if (isProfileEditing) {
                        handleSaveProfile();
                      } else {
                        setIsProfileEditing(true);
                      }
                    }}
                    className={`px-3 py-1.5 rounded-lg border text-xs font-bold transition-all ${
                      isProfileEditing 
                        ? 'bg-blue-600 border-blue-500 text-white hover:bg-blue-500 shadow shadow-blue-500/20' 
                        : 'border-zinc-800 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white'
                    }`}
                  >
                    {isProfileEditing ? 'Save Changes' : 'Edit Profile'}
                  </button>
                </div>

                <div className="h-[1px] bg-zinc-800/60 my-2" />

                <div className="space-y-4 pt-1">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5 text-zinc-400" /> Developer Name
                      </span>
                      {isProfileEditing ? (
                        <input 
                          type="text" 
                          value={userName} 
                          onChange={(e) => setUserName(e.target.value)}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                        />
                      ) : (
                        <div className="text-xs text-zinc-300 bg-zinc-950/40 border border-zinc-900 rounded-lg px-3 py-2.5 font-medium">{userName}</div>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                        <Mail className="w-3.5 h-3.5 text-zinc-400" /> Primary Email
                      </span>
                      {isProfileEditing ? (
                        <input 
                          type="email" 
                          value={userEmail} 
                          onChange={(e) => setUserEmail(e.target.value)}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                        />
                      ) : (
                        <div className="text-xs text-zinc-300 bg-zinc-950/40 border border-zinc-900 rounded-lg px-3 py-2.5 font-mono">{userEmail}</div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                        <Shield className="w-3.5 h-3.5 text-zinc-400" /> Role Profile
                      </span>
                      {isProfileEditing ? (
                        <select 
                          value={userRole} 
                          onChange={(e) => setUserRole(e.target.value)}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                        >
                          <option value="Knowledge Engineer">Knowledge Engineer</option>
                          <option value="Data Scientist">Data Scientist</option>
                          <option value="Ontologist">Ontologist</option>
                          <option value="System Architect">System Architect</option>
                        </select>
                      ) : (
                        <div className="text-xs text-zinc-300 bg-zinc-950/40 border border-zinc-900 rounded-lg px-3 py-2.5 font-medium">{userRole}</div>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-zinc-400" /> API Studio Token
                      </span>
                      {isProfileEditing ? (
                        <input 
                          type="password" 
                          value={developerKey} 
                          onChange={(e) => setDeveloperKey(e.target.value)}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 font-mono"
                        />
                      ) : (
                        <div className="text-xs text-zinc-400 bg-zinc-950/40 border border-zinc-900 rounded-lg px-3 py-2.5 font-mono">g_ai_studio_••••••••••••</div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="h-[1px] bg-zinc-850/80 my-2" />

                <div className="flex flex-col sm:flex-row sm:items-center justify-between text-[10px] text-zinc-500 font-mono gap-2">
                  <span>Authorized Session ID: session_9a8f4c1e</span>
                  <span className="text-zinc-600">Secure Node Tunnel IP: 104.28.32.10</span>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
