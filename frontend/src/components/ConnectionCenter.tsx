// Real Connection Center (adapted from .claude/docs/mocks/polanyigraph's
// ConnectionsModal). That mock's version is entirely fake -- localStorage-backed
// state, setTimeout "connect" animations, a 5-model LLM picker and embedding
// picker wired to nothing. This version shows only what's real: GET
// /settings/connections + /health, so every value here is live backend state,
// not a fabricated settings editor.
import { useEffect, useState } from 'react';
import { Database, Cpu, Puzzle, ShieldAlert, X, Plug } from 'lucide-react';
import type { ConnectionsResponse, HealthResponse } from '../lib/api';
import { api } from '../lib/api';

type TabType = 'database' | 'cognitive' | 'ingestion' | 'system';

interface ConnectionCenterProps {
  onClose: () => void;
  health: HealthResponse | null;
}

const TABS: { id: TabType; label: string; icon: typeof Database; accent: string }[] = [
  { id: 'database', label: 'Database Connectors', icon: Database, accent: 'border-emerald-500 text-emerald-400' },
  { id: 'cognitive', label: 'Cognitive Engine', icon: Cpu, accent: 'border-blue-500 text-blue-400' },
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

export function ConnectionCenter({ onClose, health }: ConnectionCenterProps) {
  const [activeTab, setActiveTab] = useState<TabType>('database');
  const [connections, setConnections] = useState<ConnectionsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getConnections()
      .then(setConnections)
      .finally(() => setLoading(false));
  }, []);

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
                    No embedding model is configured. Search (memory, entity lookup) uses Neo4j text-substring matching, not vector similarity.
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
