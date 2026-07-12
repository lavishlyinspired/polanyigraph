// Right sidebar "Triples" tab. Shows all stored + derived triples in a
// searchable list. Visual language matches the reference prototype.
import { useEffect, useState } from 'react';
import { Database, Search, AlertCircle } from 'lucide-react';
import { api, type Triple } from '../lib/api';
import { useGraphStore } from '../stores/graphStore';

export function TripleStorePanel() {
  const { graphId } = useGraphStore();
  const [triples, setTriples] = useState<Triple[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    if (!graphId) return;
    setLoading(true);
    setError(null);
    api
      .getTriples(graphId)
      .then((res) => {
        setTriples(res.triples);
        setTotal(res.total);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [graphId]);

  const filtered = filter
    ? triples.filter(
        (t) =>
          t.subject.toLowerCase().includes(filter.toLowerCase()) ||
          t.predicate.toLowerCase().includes(filter.toLowerCase()) ||
          t.object.toLowerCase().includes(filter.toLowerCase()),
      )
    : triples;

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Database className="w-3.5 h-3.5" /> Triple Store
        </h3>
        <p className="text-[9px] text-zinc-600 mt-1">
          {total} triple{total !== 1 ? 's' : ''} (stored + derived)
        </p>
      </div>
      <div className="p-3 border-b border-zinc-800 shrink-0">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-zinc-600" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter triples..."
              className="w-full bg-zinc-900 border border-zinc-700 rounded text-xs text-white placeholder:text-zinc-600 font-mono pl-6 pr-2 h-8 focus:outline-none focus:border-zinc-600"
            />
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-3 min-h-0">
        {loading ? (
          <div className="text-center text-[10px] text-zinc-600 mt-8">Loading triples...</div>
        ) : error ? (
          <div className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/5 text-[10px] text-rose-400">
            <AlertCircle className="w-3 h-3 inline mr-1" /> {error}
          </div>
        ) : filtered.length > 0 ? (
          <div className="space-y-1">
            <div className="text-[10px] text-zinc-500 mb-2">
              {filtered.length} of {total} triple{total !== 1 ? 's' : ''}
            </div>
            {filtered.map((t, i) => (
              <div
                key={i}
                className={`p-2 rounded border text-[10px] font-mono ${
                  t.derived ? 'border-amber-400/30 bg-amber-400/5' : 'border-zinc-800 bg-zinc-900'
                }`}
              >
                <div className="flex items-center gap-1 text-zinc-300">
                  <span className="text-emerald-400">{t.subject}</span>
                  <span className="text-zinc-500"> .{t.predicate}(</span>
                  <span className="text-sky-400">{t.object}</span>
                  <span className="text-zinc-500">)</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {t.derived ? (
                    <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-400 text-badgeink font-bold">DERIVED</span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded text-[8px] border border-zinc-700 text-zinc-500">BASE</span>
                  )}
                  <span className="text-[9px] text-zinc-600">{(t.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-[10px] text-zinc-600 mt-8">
            <Database className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
            <p>No triples yet. Ingest a document to populate the graph.</p>
          </div>
        )}
      </div>
    </div>
  );
}
