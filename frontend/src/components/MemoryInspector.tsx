// Right sidebar "Memory" tab (PLAN.md §9). Searches the same real, already-
// persisted cross-source memory (chat history + entity evolving-summaries,
// services/memory_service.py) that mcp_memory_server.py exposes to MCP
// clients and agents/graph.py's memory_agent node uses for "recall" intent --
// plus a real key/value preferences store, not a demo/mock memory layer.
import { useEffect, useState } from 'react';
import { BrainCircuit, Search, MessageSquare, FileText, Loader, Settings, Trash2, Plus } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';
import type { MemoryHit } from '../lib/api';

function HitCard({ hit }: { hit: MemoryHit }) {
  const Icon = hit.kind === 'chat_message' ? MessageSquare : FileText;
  return (
    <div className="p-2.5 rounded-lg border border-zinc-800 bg-zinc-900/50">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className="w-3 h-3 text-sky-400 shrink-0" />
        <span className="text-[8px] font-bold uppercase tracking-wider text-zinc-500">
          {hit.kind === 'chat_message' ? 'Chat message' : 'Entity summary'}
        </span>
        {hit.createdAt && <span className="text-[8px] text-zinc-600 ml-auto">{hit.createdAt}</span>}
      </div>
      <div className="text-[10px] text-zinc-300 leading-relaxed">{hit.text}</div>
    </div>
  );
}

export function MemoryInspector() {
  const {
    memoryHits, memorySearching, memoryQuery, setMemoryQuery, searchMemory,
    preferences, loadPreferences, savePreference, deletePreference,
  } = useGraphStore();
  const [showPreferences, setShowPreferences] = useState(false);
  const [prefKey, setPrefKey] = useState('');
  const [prefValue, setPrefValue] = useState('');

  useEffect(() => {
    void loadPreferences();
  }, [loadPreferences]);

  const handleSearch = async () => {
    if (!memoryQuery.trim()) return;
    await searchMemory();
  };

  const handleAddPreference = async () => {
    if (!prefKey.trim() || !prefValue.trim()) return;
    await savePreference(prefKey.trim(), prefValue.trim());
    setPrefKey('');
    setPrefValue('');
  };

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <BrainCircuit className="w-3.5 h-3.5" /> Memory
        </h3>
        <p className="text-[9px] text-zinc-600 mt-1">
          Searches real chat history and entity summaries already persisted for this graph -- the same
          cross-source lookup the agent's "recall" intent uses.
        </p>
      </div>
      <div className="p-3 border-b border-zinc-800 space-y-2 shrink-0">
        <div className="flex gap-2">
          <input
            value={memoryQuery}
            onChange={(e) => setMemoryQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void handleSearch()}
            placeholder="Search past chat and entity summaries…"
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded text-xs text-white placeholder:text-zinc-600 px-2 h-8 focus:outline-none focus:border-zinc-600"
          />
          <button
            onClick={() => void handleSearch()}
            disabled={memorySearching || !memoryQuery.trim()}
            className="h-8 px-3 rounded bg-white text-black hover:bg-zinc-200 transition-colors disabled:opacity-40"
          >
            {memorySearching ? <Loader className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {memoryHits.length === 0 ? (
          <div className="text-center text-[10px] text-zinc-600 mt-8">
            <BrainCircuit className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
            Search to recall prior conversation or entity summaries.
          </div>
        ) : (
          memoryHits.map((hit) => <HitCard key={`${hit.kind}-${hit.id}`} hit={hit} />)
        )}
      </div>
      <div className="border-t border-zinc-800 shrink-0">
        <button
          onClick={() => setShowPreferences((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-2 text-[10px] font-bold text-zinc-500 uppercase tracking-wider hover:text-zinc-300 transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <Settings className="w-3 h-3" /> Preferences ({preferences.length})
          </span>
        </button>
        {showPreferences && (
          <div className="px-3 pb-3 space-y-2">
            <div className="flex gap-1.5">
              <input
                value={prefKey}
                onChange={(e) => setPrefKey(e.target.value)}
                placeholder="key"
                className="w-1/3 bg-zinc-900 border border-zinc-700 rounded text-[10px] text-white placeholder:text-zinc-600 px-1.5 h-6 focus:outline-none focus:border-zinc-600"
              />
              <input
                value={prefValue}
                onChange={(e) => setPrefValue(e.target.value)}
                placeholder="value"
                className="flex-1 bg-zinc-900 border border-zinc-700 rounded text-[10px] text-white placeholder:text-zinc-600 px-1.5 h-6 focus:outline-none focus:border-zinc-600"
              />
              <button
                onClick={() => void handleAddPreference()}
                disabled={!prefKey.trim() || !prefValue.trim()}
                className="w-6 h-6 rounded bg-white text-black hover:bg-zinc-200 flex items-center justify-center disabled:opacity-40 transition-colors"
              >
                <Plus className="w-3 h-3" />
              </button>
            </div>
            {preferences.map((pref) => (
              <div key={pref.key} className="flex items-center justify-between gap-2 text-[10px] px-1.5">
                <span className="text-zinc-400 truncate">
                  <span className="text-zinc-600">{pref.key}:</span> {pref.value}
                </span>
                <button onClick={() => void deletePreference(pref.key)} className="text-zinc-600 hover:text-rose-400 transition-colors shrink-0">
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
