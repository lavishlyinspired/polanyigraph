// Real Connection Center (adapted from .claude/docs/mocks/polanyigraph's
// ConnectionsModal). That mock's version is entirely fake -- localStorage-backed
// state, setTimeout "connect" animations, a 5-model LLM picker and embedding
// picker wired to nothing. This version shows only what's real: GET
// /settings/connections + /health, so every value here is live backend state,
// not a fabricated settings editor.
import { useEffect, useState } from 'react';
import { Database, Cpu, Puzzle, ShieldAlert, X, Plug, BrainCircuit, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import type { ConnectionsResponse, HealthResponse, MemoryBackend, MemoryBackendStatus } from '../lib/api';
import { api } from '../lib/api';

type TabType = 'database' | 'cognitive' | 'memory' | 'ingestion' | 'system';

interface ConnectionCenterProps {
  onClose: () => void;
  health: HealthResponse | null;
}

const TABS: { id: TabType; label: string; icon: typeof Database; accent: string }[] = [
  { id: 'database', label: 'Database Connectors', icon: Database, accent: 'border-emerald-500 text-emerald-400' },
  { id: 'cognitive', label: 'Cognitive Engine', icon: Cpu, accent: 'border-blue-500 text-blue-400' },
  { id: 'memory', label: 'Memory Backend', icon: BrainCircuit, accent: 'border-purple-500 text-purple-400' },
  { id: 'ingestion', label: 'Ingestion Path', icon: Puzzle, accent: 'border-sky-500 text-sky-400' },
  { id: 'system', label: 'System Status', icon: ShieldAlert, accent: 'border-amber-500 text-amber-400' },
];

function StatusBadge({ ok }: { ok: boolean | undefined }) {
  return (
    <div
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[9px] font-bold tracking-wider uppercase ${
        ok ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-rose-500/10 border-rose-500/30 text-rose-400 animate-pulse'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-emerald-400' : 'bg-rose-500'}`} />
      <span>{ok ? 'Connected' : 'Unreachable'}</span>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1.5">
      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">{label}</label>
      <div className="w-full bg-zinc-950/80 border border-zinc-800/80 rounded-lg px-3 py-2 text-xs text-zinc-200 font-mono truncate">{value}</div>
    </div>
  );
}

const SERVICE_LABELS: Record<string, string> = {
  auth0: 'Auth0 (authentication)',
  qdrant: 'Qdrant (vector database)',
  falkordb: 'FalkorDB',
  zep: 'Zep (memory)',
  huggingface: 'Hugging Face',
};

function TextField({
  label, value, onChange, type = 'text', placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-zinc-950/80 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 font-mono placeholder:text-zinc-700 focus:outline-none focus:border-purple-500 transition-colors"
      />
    </div>
  );
}

function TestResultBanner({ result }: { result: { ok: boolean; error: string | null } | null }) {
  if (!result) return null;
  return (
    <div
      className={`flex items-start gap-2 p-3 rounded-lg border text-[11px] ${
        result.ok ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/5 border-rose-500/20 text-rose-400'
      }`}
    >
      {result.ok ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" /> : <XCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />}
      <span className="font-mono break-all">{result.ok ? 'Connected successfully.' : result.error}</span>
    </div>
  );
}

export function ConnectionCenter({ onClose, health }: ConnectionCenterProps) {
  const [activeTab, setActiveTab] = useState<TabType>('database');
  const [connections, setConnections] = useState<ConnectionsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const [memoryStatus, setMemoryStatus] = useState<MemoryBackendStatus | null>(null);
  const [switchingBackend, setSwitchingBackend] = useState(false);

  const [graphitiUri, setGraphitiUri] = useState('bolt://localhost:7687');
  const [graphitiUser, setGraphitiUser] = useState('neo4j');
  const [graphitiPassword, setGraphitiPassword] = useState('');
  const [graphitiDatabase, setGraphitiDatabase] = useState('graphiti-memory');
  const [graphitiTesting, setGraphitiTesting] = useState(false);
  const [graphitiResult, setGraphitiResult] = useState<{ ok: boolean; error: string | null } | null>(null);

  const [embeddingBaseUrl, setEmbeddingBaseUrl] = useState('');
  const [embeddingModel, setEmbeddingModel] = useState('nvidia/nv-embedqa-e5-v5');
  const [embeddingApiKey, setEmbeddingApiKey] = useState('');
  const [embeddingTesting, setEmbeddingTesting] = useState(false);
  const [embeddingResult, setEmbeddingResult] = useState<{ ok: boolean; error: string | null } | null>(null);

  useEffect(() => {
    api
      .getConnections()
      .then(setConnections)
      .finally(() => setLoading(false));
    api.getMemoryBackend().then((status) => {
      setMemoryStatus(status);
      if (status.embeddingBaseUrl) setEmbeddingBaseUrl(status.embeddingBaseUrl);
      if (status.embeddingModel) setEmbeddingModel(status.embeddingModel);
      if (status.graphitiNeo4jUri) setGraphitiUri(status.graphitiNeo4jUri);
      if (status.graphitiNeo4jDatabase) setGraphitiDatabase(status.graphitiNeo4jDatabase);
    });
  }, []);

  const handleSwitchBackend = async (backend: MemoryBackend) => {
    setSwitchingBackend(true);
    try {
      setMemoryStatus(await api.setMemoryBackend(backend));
    } finally {
      setSwitchingBackend(false);
    }
  };

  const handleTestGraphiti = async () => {
    setGraphitiTesting(true);
    setGraphitiResult(null);
    try {
      const result = await api.setGraphitiConnection(graphitiUri, graphitiUser, graphitiPassword, graphitiDatabase);
      setGraphitiResult({ ok: result.ok, error: result.error });
      setMemoryStatus(result.status);
    } catch (e) {
      setGraphitiResult({ ok: false, error: String(e) });
    } finally {
      setGraphitiTesting(false);
    }
  };

  const handleTestEmbedding = async () => {
    setEmbeddingTesting(true);
    setEmbeddingResult(null);
    try {
      const result = await api.setEmbeddingOverride(embeddingBaseUrl, embeddingModel, embeddingApiKey);
      setEmbeddingResult({ ok: result.ok, error: result.error });
      setMemoryStatus(result.status);
    } catch (e) {
      setEmbeddingResult({ ok: false, error: String(e) });
    } finally {
      setEmbeddingTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 p-5 shrink-0">
          <div>
            <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Plug className="w-4 h-4 text-blue-400" /> Connection Center
            </h2>
            <p className="text-[11px] text-zinc-500 mt-1">Live status for this deployment's real data stores, LLM, and ingestion path.</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-950/40 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex border-b border-zinc-800 bg-zinc-950/40 px-5 pt-2 gap-4 shrink-0 overflow-x-auto">
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`pb-3 px-1 text-[10px] font-bold uppercase tracking-wider transition-all border-b-2 flex items-center gap-2 whitespace-nowrap ${
                  isActive ? tab.accent : 'text-zinc-500 border-transparent hover:text-zinc-300'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        <div className="flex-1 overflow-y-auto p-6 min-h-0 bg-zinc-950/40">
          {loading || !connections ? (
            <div className="text-center text-xs text-zinc-500 py-8">Loading live connection state...</div>
          ) : (
            <>
              {activeTab === 'database' && (
                <div className="space-y-5">
                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                          <Database className="w-5 h-5 text-emerald-400" />
                        </div>
                        <div>
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Neo4j Graph Database</h3>
                          <p className="text-[11px] text-zinc-500 mt-0.5">Instance graph, spread-activation reasoning, visualization</p>
                        </div>
                      </div>
                      <StatusBadge ok={health?.neo4j.ok} />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <InfoRow label="Bolt URI" value={connections.neo4j.uri} />
                      <InfoRow label="Database" value={connections.neo4j.database} />
                    </div>
                    {health && !health.neo4j.ok && health.neo4j.error && (
                      <p className="text-[10px] text-rose-400 font-mono">{health.neo4j.error}</p>
                    )}
                  </div>

                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-sky-500/10 flex items-center justify-center border border-sky-500/20">
                          <Database className="w-5 h-5 text-sky-400" />
                        </div>
                        <div>
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Ontotext GraphDB</h3>
                          <p className="text-[11px] text-zinc-500 mt-0.5">Ontology (RDF/OWL) via SPARQL -- source of entity types</p>
                        </div>
                      </div>
                      <StatusBadge ok={health?.graphdb.ok} />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <InfoRow label="Base URL" value={connections.graphdb.baseUrl} />
                      <InfoRow label="Repository" value={connections.graphdb.repository} />
                    </div>
                    {health && !health.graphdb.ok && health.graphdb.error && (
                      <p className="text-[10px] text-rose-400 font-mono">{health.graphdb.error}</p>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'cognitive' && (
                <div className="space-y-5">
                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center border border-blue-500/20">
                          <Cpu className="w-5 h-5 text-blue-400" />
                        </div>
                        <div>
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider">LLM Engine</h3>
                          <p className="text-[11px] text-zinc-500 mt-0.5">OpenAI-compatible endpoint used by extraction, enrichment, reasoning explanations, and chat</p>
                        </div>
                      </div>
                      <StatusBadge ok={health?.llm.ok} />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <InfoRow label="Base URL" value={connections.llm.baseUrl} />
                      <InfoRow label="Model" value={connections.llm.model} />
                    </div>
                  </div>

                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">Reasoning Tunables</h3>
                    <div className="grid grid-cols-3 gap-3 text-center">
                      {[
                        ['Decay', connections.reasoning.decay],
                        ['Epsilon', connections.reasoning.epsilon],
                        ['Max Iterations', connections.reasoning.maxIterations],
                        ['Activation Floor', connections.reasoning.activationFloor],
                        ['Feedback Gain', connections.reasoning.feedbackGain],
                      ].map(([label, value]) => (
                        <div key={label} className="bg-zinc-950/60 border border-zinc-800 rounded-lg p-3">
                          <div className="text-blue-400 font-bold font-mono text-sm">{value}</div>
                          <div className="text-[9px] text-zinc-500 uppercase tracking-wider mt-1">{label}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="bg-zinc-950/30 border border-zinc-900 rounded-lg p-4 text-[11px] text-zinc-400">
                    Embedding model: <span className="text-zinc-200 font-mono">nvidia/nv-embedqa-e5-v5</span> on this same NVIDIA endpoint. Used for
                    memory search and Graphiti (see Memory Backend tab) -- configurable there.
                  </div>
                </div>
              )}

              {activeTab === 'memory' && (
                <div className="space-y-5">
                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center border border-purple-500/20">
                        <BrainCircuit className="w-5 h-5 text-purple-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Active Memory Backend</h3>
                        <p className="text-[11px] text-zinc-500 mt-0.5">
                          Native: Neo4j vector search, no new dependency. Graphiti: real graphiti-core, isolated database.
                        </p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      {(['native', 'graphiti'] as const).map((backend) => {
                        const isActive = memoryStatus?.backend === backend;
                        return (
                          <button
                            key={backend}
                            onClick={() => void handleSwitchBackend(backend)}
                            disabled={switchingBackend}
                            className={`p-3 rounded-lg border text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50 ${
                              isActive
                                ? 'bg-purple-500/10 border-purple-500/40 text-purple-400'
                                : 'bg-zinc-950/40 border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300'
                            }`}
                          >
                            {switchingBackend && isActive ? <Loader2 className="w-3.5 h-3.5 animate-spin mx-auto" /> : backend}
                          </button>
                        );
                      })}
                    </div>
                    {memoryStatus?.backend === 'graphiti' && !memoryStatus.graphitiConfigured && (
                      <p className="text-[10px] text-amber-400">
                        Graphiti selected but no connection saved yet -- search falls back to the native path until you connect below.
                      </p>
                    )}
                  </div>

                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-white uppercase tracking-wider">Graphiti Neo4j Database</h3>
                      {memoryStatus?.graphitiConfigured && <StatusBadge ok={true} />}
                    </div>
                    <p className="text-[11px] text-zinc-500">
                      A separate, isolated Neo4j database (never the graphos database's :Entity/:RELATES schema). Created automatically if it
                      doesn't exist yet.
                    </p>
                    <div className="grid grid-cols-2 gap-4">
                      <TextField label="Bolt URI" value={graphitiUri} onChange={setGraphitiUri} placeholder="bolt://localhost:7687" />
                      <TextField label="Database name" value={graphitiDatabase} onChange={setGraphitiDatabase} placeholder="graphiti-memory" />
                      <TextField label="Username" value={graphitiUser} onChange={setGraphitiUser} placeholder="neo4j" />
                      <TextField label="Password" type="password" value={graphitiPassword} onChange={setGraphitiPassword} placeholder="••••••••" />
                    </div>
                    <button
                      onClick={() => void handleTestGraphiti()}
                      disabled={graphitiTesting || !graphitiUri || !graphitiDatabase}
                      className="w-full h-9 bg-purple-600 hover:bg-purple-500 text-onaccent text-xs font-bold rounded-lg flex items-center justify-center gap-2 disabled:opacity-40 transition-colors"
                    >
                      {graphitiTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plug className="w-3.5 h-3.5" />}
                      Test &amp; Save Connection
                    </button>
                    <TestResultBanner result={graphitiResult} />
                  </div>

                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-white uppercase tracking-wider">Embedding Model</h3>
                      {memoryStatus?.embeddingConfigured && <StatusBadge ok={true} />}
                    </div>
                    <p className="text-[11px] text-zinc-500">
                      Used by native vector search and by Graphiti's entity/fact dedup. Defaults to the same NVIDIA endpoint as the LLM if left
                      blank.
                    </p>
                    <div className="grid grid-cols-2 gap-4">
                      <TextField label="Base URL" value={embeddingBaseUrl} onChange={setEmbeddingBaseUrl} placeholder={connections.llm.baseUrl} />
                      <TextField label="Model" value={embeddingModel} onChange={setEmbeddingModel} placeholder="nvidia/nv-embedqa-e5-v5" />
                    </div>
                    <TextField label="API Key (optional override)" type="password" value={embeddingApiKey} onChange={setEmbeddingApiKey} placeholder="Leave blank to reuse the LLM key" />
                    <button
                      onClick={() => void handleTestEmbedding()}
                      disabled={embeddingTesting || !embeddingModel}
                      className="w-full h-9 bg-purple-600 hover:bg-purple-500 text-onaccent text-xs font-bold rounded-lg flex items-center justify-center gap-2 disabled:opacity-40 transition-colors"
                    >
                      {embeddingTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plug className="w-3.5 h-3.5" />}
                      Test &amp; Save Embedding Model
                    </button>
                    <TestResultBanner result={embeddingResult} />
                  </div>
                </div>
              )}

              {activeTab === 'ingestion' && (
                <div className="space-y-5">
                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-sky-500/10 flex items-center justify-center border border-sky-500/20">
                        <Puzzle className="w-5 h-5 text-sky-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Document Ingest</h3>
                        <p className="text-[11px] text-zinc-500 mt-0.5">The one real ingestion path: paste text, LLM extracts entities/relationships against the loaded ontology</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {['SEC Filing', 'Press Release', 'Contract', 'News Article'].map((tag) => (
                        <div key={tag} className="px-3 py-2 rounded-lg border border-zinc-800/80 bg-zinc-950/20 text-[10px] text-zinc-400 text-center">
                          {tag}
                        </div>
                      ))}
                    </div>
                    <p className="text-[10px] text-zinc-600">
                      These are prompt-context tags in the Build panel, not separate connectors -- there is no PDF parser, web scraper, or SEC EDGAR
                      integration in this codebase.
                    </p>
                  </div>
                </div>
              )}

              {activeTab === 'system' && (
                <div className="space-y-5">
                  <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center border border-amber-500/20">
                        <ShieldAlert className="w-5 h-5 text-amber-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Provisioned, Not Wired</h3>
                        <p className="text-[11px] text-zinc-500 mt-0.5">Credentials present in .env with no code path reading them</p>
                      </div>
                    </div>
                    {connections.provisionedNotWired.length === 0 ? (
                      <p className="text-[11px] text-zinc-500">None -- every configured credential is in active use.</p>
                    ) : (
                      <div className="space-y-2">
                        {connections.provisionedNotWired.map((service) => (
                          <div key={service} className="flex items-center justify-between px-3 py-2 rounded-lg border border-amber-500/20 bg-amber-500/5">
                            <span className="text-xs text-zinc-200">{SERVICE_LABELS[service] ?? service}</span>
                            <span className="text-[9px] font-bold uppercase tracking-wider text-amber-400">Unwired</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <p className="text-[10px] text-zinc-600">
                      No authentication exists in this app -- every endpoint is open. This project's convention is to rebuild capabilities natively
                      (e.g. the memory layer lives in Neo4j, not Zep) rather than reach for these unless a concrete need justifies it.
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
