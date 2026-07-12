// Right sidebar "Query" tab. Structured triple query + path-finding over
// stored + derived facts. Visual language ported from the prototype's QueryPanel.
import { useState } from 'react';
import { Search, AlertCircle, GitFork } from 'lucide-react';
import { api, type PathResponse } from '../lib/api';
import { useGraphStore } from '../stores/graphStore';

const QUERY_EXAMPLES = [
  'regulates("FINMA", X)',
  'regulates(X, "Credit Suisse")',
  'hasDomicile("Credit Suisse", X)',
  'issuedBy(X, "CS Atlas Bond I")',
  'denominatedIn("CS Atlas Bond I", X)',
  'regulates("FINMA", X), hasDomicile(X, "Zurich")',
];

export function QueryPanel() {
  const { queryText, setQueryText, runQuery, queryResults, queryError, graphId } = useGraphStore();
  const [history, setHistory] = useState<string[]>([]);

  // Path-finding state
  const [pathSource, setPathSource] = useState('');
  const [pathTarget, setPathTarget] = useState('');
  const [pathResult, setPathResult] = useState<PathResponse | null>(null);
  const [pathLoading, setPathLoading] = useState(false);
  const [pathError, setPathError] = useState<string | null>(null);

  const handleRunQuery = async (q: string) => {
    if (!q.trim()) return;
    await runQuery(q);
    setHistory((prev) => [q, ...prev.filter((h) => h !== q)].slice(0, 5));
  };

  const handleFindPath = async () => {
    if (!pathSource.trim() || !pathTarget.trim()) return;
    setPathLoading(true);
    setPathError(null);
    setPathResult(null);
    try {
      const result = await api.findPath(graphId, pathSource.trim(), pathTarget.trim());
      setPathResult(result);
      if (result.error) setPathError(result.error);
    } catch (e) {
      setPathError(String(e));
    } finally {
      setPathLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      {/* Pattern Query Section */}
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Search className="w-3.5 h-3.5" /> Query Console
        </h3>
        <p className="text-[9px] text-zinc-600 mt-1">Datalog-style: predicate(subject, object). Use X, Y for variables. Conjunctions with commas.</p>
      </div>
      <div className="p-3 border-b border-zinc-800 shrink-0">
        <div className="flex gap-2">
          <input
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void handleRunQuery(queryText)}
            placeholder='e.g., regulates("FINMA", X)'
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded text-xs text-white placeholder:text-zinc-600 font-mono px-2 h-8 focus:outline-none focus:border-zinc-600"
          />
          <button onClick={() => void handleRunQuery(queryText)} className="h-8 px-3 rounded bg-white text-black hover:bg-zinc-200 transition-colors">
            <Search className="w-3.5 h-3.5" />
          </button>
        </div>
        {history.length > 0 && (
          <div className="mt-2 flex gap-1 flex-wrap">
            {history.map((h, i) => (
              <button
                key={i}
                onClick={() => {
                  setQueryText(h);
                  void handleRunQuery(h);
                }}
                className="text-[9px] px-2 py-0.5 rounded border border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-colors font-mono truncate max-w-32"
              >
                {h}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Find Path Section */}
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <GitFork className="w-3.5 h-3.5" /> Find Path
        </h3>
        <p className="text-[9px] text-zinc-600 mt-1">BFS shortest path with explainable proof.</p>
        <div className="mt-2 space-y-2">
          <input
            value={pathSource}
            onChange={(e) => setPathSource(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void handleFindPath()}
            placeholder="Source node label"
            className="w-full bg-zinc-900 border border-zinc-700 rounded text-xs text-white placeholder:text-zinc-600 font-mono px-2 h-8 focus:outline-none focus:border-zinc-600"
          />
          <input
            value={pathTarget}
            onChange={(e) => setPathTarget(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void handleFindPath()}
            placeholder="Target node label"
            className="w-full bg-zinc-900 border border-zinc-700 rounded text-xs text-white placeholder:text-zinc-600 font-mono px-2 h-8 focus:outline-none focus:border-zinc-600"
          />
          <button
            onClick={() => void handleFindPath()}
            disabled={pathLoading || !pathSource.trim() || !pathTarget.trim()}
            className="w-full h-8 rounded bg-white text-black text-[10px] font-bold uppercase tracking-wider hover:bg-zinc-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {pathLoading ? 'Finding...' : 'Find Path'}
          </button>
        </div>
      </div>

      {/* Path Results */}
      {pathResult && (
        <div className="p-3 border-b border-zinc-800 shrink-0">
          {pathResult.found ? (
            <div className="space-y-2">
              <div className="text-[10px] text-zinc-500">
                Path: {pathResult.path.length} node{pathResult.path.length !== 1 ? 's' : ''}
              </div>
              {/* Path chain */}
              <div className="flex flex-wrap items-center gap-1">
                {pathResult.path.map((label, i) => (
                  <span key={i} className="flex items-center gap-1">
                    {i > 0 && (
                      <span className="text-[9px] text-zinc-600 font-mono">
                        →[{pathResult.edges[i - 1]?.label}]→
                      </span>
                    )}
                    <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-zinc-300 font-mono">
                      {label}
                    </span>
                  </span>
                ))}
              </div>
              {/* Proof string */}
              <div className="p-2 rounded bg-sky-400/5 border border-sky-400/20">
                <div className="text-[8px] text-zinc-500 uppercase tracking-wider mb-1">Proof</div>
                <div className="text-[10px] text-zinc-300 font-mono leading-relaxed break-all">{pathResult.proof}</div>
              </div>
            </div>
          ) : (
            <div className="p-2 rounded border border-zinc-800 text-[10px] text-zinc-500">
              {pathResult.error || 'No path found.'}
            </div>
          )}
        </div>
      )}
      {pathError && (
        <div className="p-3 border-b border-zinc-800 shrink-0">
          <div className="p-2 rounded-lg border border-rose-500/30 bg-rose-500/5 text-[10px] text-rose-400">
            <AlertCircle className="w-3 h-3 inline mr-1" /> {pathError}
          </div>
        </div>
      )}

      {/* Query Results */}
      <div className="flex-1 overflow-y-auto p-3 min-h-0">
        {queryError ? (
          <div className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/5 text-[10px] text-rose-400">
            <AlertCircle className="w-3 h-3 inline mr-1" /> {queryError}
          </div>
        ) : queryResults.length > 0 ? (
          <div className="space-y-2">
            <div className="text-[10px] text-zinc-500">{queryResults.length} result{queryResults.length > 1 ? 's' : ''}</div>
            {queryResults.map((r, i) => (
              <div key={i} className={`p-2.5 rounded-lg border ${r.derived ? 'border-amber-400/30 bg-amber-400/5' : 'border-zinc-800 bg-zinc-900'}`}>
                <div className="text-[10px] font-mono text-zinc-300">
                  <span className="text-emerald-400">{r.subject}</span>
                  <span className="text-zinc-500"> .{r.predicate}(</span>
                  <span className="text-sky-400">{r.object}</span>
                  <span className="text-zinc-500">)</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {r.derived ? (
                    <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-400 text-black font-bold">DERIVED</span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded text-[8px] border border-zinc-700 text-zinc-500">BASE FACT</span>
                  )}
                  <span className="text-[9px] text-zinc-600">confidence: {(r.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-[10px] text-zinc-600 mt-8">
            <Search className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
            <p className="mb-3">Query the graph + derived facts.</p>
            <div className="space-y-1 text-left max-w-56 mx-auto">
              <div className="text-[9px] text-zinc-700 uppercase tracking-wider mb-1">Examples:</div>
              {QUERY_EXAMPLES.map((ex, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setQueryText(ex);
                    void handleRunQuery(ex);
                  }}
                  className="block w-full text-left p-1.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors font-mono text-[9px] truncate"
                >
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
