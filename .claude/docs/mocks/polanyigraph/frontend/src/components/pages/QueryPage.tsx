import { useEffect, useState } from 'react';
import { 
  Search, AlertCircle, GitFork, Database, ListFilter, HelpCircle, 
  ArrowRight, ShieldCheck, HelpCircle as HelpIcon, Sparkles
} from 'lucide-react';
import { api, type Triple, type PathResponse } from '../../lib/api';
import { useGraphStore } from '../../stores/graphStore';

const QUERY_EXAMPLES = [
  'regulates("FINMA", X)',
  'regulates(X, "Credit Suisse")',
  'hasDomicile("Credit Suisse", X)',
  'issuedBy(X, "CS Atlas Bond I")',
  'denominatedIn("CS Atlas Bond I", X)',
  'regulates("FINMA", X), hasDomicile(X, "Zurich")',
];

export function QueryPage() {
  const { 
    queryText, setQueryText, runQuery, queryResults, queryError, graphId 
  } = useGraphStore();

  const [queryHistory, setQueryHistory] = useState<string[]>([]);
  
  // Tabular triple store data
  const [triples, setTriples] = useState<Triple[]>([]);
  const [totalTriples, setTotalTriples] = useState(0);
  const [loadingTriples, setLoadingTriples] = useState(false);
  const [triplesError, setTriplesError] = useState<string | null>(null);

  // Filters for Triple Store Tabular view
  const [subFilter, setSubFilter] = useState('');
  const [predFilter, setPredFilter] = useState('');
  const [objFilter, setObjFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'base' | 'derived'>('all');

  // Shortest path BFS router states
  const [bfsSource, setBfsSource] = useState('CS Atlas Bond I');
  const [bfsTarget, setBfsTarget] = useState('Zürich');
  const [bfsPathResult, setBfsPathResult] = useState<PathResponse | null>(null);
  const [bfsLoading, setBfsLoading] = useState(false);
  const [bfsError, setBfsError] = useState<string | null>(null);

  useEffect(() => {
    if (!graphId) return;
    setLoadingTriples(true);
    setTriplesError(null);
    api.getTriples(graphId)
      .then((res) => {
        setTriples(res.triples);
        setTotalTriples(res.total);
      })
      .catch((e) => setTriplesError(String(e)))
      .finally(() => setLoadingTriples(false));
  }, [graphId]);

  const handleRunQuery = async (q: string) => {
    if (!q.trim()) return;
    await runQuery(q);
    setQueryHistory((prev) => [q, ...prev.filter((h) => h !== q)].slice(0, 6));
  };

  const handleBfsPath = async () => {
    if (!bfsSource.trim() || !bfsTarget.trim()) return;
    setBfsLoading(true);
    setBfsError(null);
    setBfsPathResult(null);
    try {
      const result = await api.findPath(graphId, bfsSource.trim(), bfsTarget.trim());
      setBfsPathResult(result);
      if (result.error) setBfsError(result.error);
    } catch (e) {
      setBfsError(String(e));
    } finally {
      setBfsLoading(false);
    }
  };

  // Filter logic for high-density triples list
  const filteredTriples = triples.filter((t) => {
    const sMatch = t.subject.toLowerCase().includes(subFilter.toLowerCase());
    const pMatch = t.predicate.toLowerCase().includes(predFilter.toLowerCase());
    const oMatch = t.object.toLowerCase().includes(objFilter.toLowerCase());
    
    if (typeFilter === 'base') return sMatch && pMatch && oMatch && !t.derived;
    if (typeFilter === 'derived') return sMatch && pMatch && oMatch && t.derived;
    return sMatch && pMatch && oMatch;
  });

  return (
    <div className="h-full flex-1 flex overflow-hidden bg-zinc-950">
      
      {/* 1. LEFT COLUMN - Pattern Console & BFS Finder */}
      <div className="w-[420px] border-r border-zinc-800 flex flex-col min-w-0 bg-zinc-950/20">
        
        {/* Pattern Query Section Header */}
        <div className="p-4 border-b border-zinc-800 bg-zinc-900/10 shrink-0">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
            <Search className="w-4 h-4 text-indigo-400" /> Datalog Pattern Console
          </h3>
          <p className="text-[9px] text-zinc-500 mt-0.5">predicate(subject, object). Upper-case matches variables.</p>
        </div>

        {/* Query Input Deck */}
        <div className="p-4 border-b border-zinc-800 shrink-0 space-y-3">
          <div className="flex gap-2">
            <input
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void handleRunQuery(queryText)}
              placeholder='e.g., regulates("FINMA", X)'
              className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-white placeholder:text-zinc-700 font-mono px-3 h-9 focus:outline-none focus:border-indigo-500 transition-colors"
            />
            <button 
              onClick={() => void handleRunQuery(queryText)} 
              className="h-9 px-4 rounded-lg bg-white text-black hover:bg-zinc-200 font-bold text-xs flex items-center justify-center gap-1.5 transition-colors"
            >
              <Search className="w-3.5 h-3.5" /> Run
            </button>
          </div>

          {queryHistory.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[8px] font-mono text-zinc-600 uppercase font-bold tracking-wider block">History</span>
              <div className="flex gap-1.5 flex-wrap">
                {queryHistory.map((h, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setQueryText(h);
                      void handleRunQuery(h);
                    }}
                    className="text-[9px] px-2 py-0.5 rounded border border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-colors font-mono truncate max-w-[160px]"
                  >
                    {h}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Pattern matches output list */}
        <div className="flex-1 overflow-y-auto p-4 border-b border-zinc-800 min-h-0">
          <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider font-mono mb-2.5">
            Console Pattern Matches
          </div>

          {queryError ? (
            <div className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/5 text-xs text-rose-400 font-mono flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" /> 
              <div className="flex-1 break-words">{queryError}</div>
            </div>
          ) : queryResults.length > 0 ? (
            <div className="space-y-2">
              <div className="text-[9px] text-zinc-500 font-mono">{queryResults.length} bound tuples matched:</div>
              {queryResults.map((r, i) => (
                <div key={i} className={`p-3 rounded-lg border ${r.derived ? 'border-amber-400/20 bg-amber-400/5' : 'border-zinc-800 bg-zinc-900/40'}`}>
                  <div className="text-[11px] font-mono text-zinc-200 flex items-center gap-1 flex-wrap leading-relaxed">
                    <span className="text-emerald-400 font-bold">{r.subject}</span>
                    <span className="text-zinc-500">.{r.predicate}(</span>
                    <span className="text-sky-400 font-bold">{r.object}</span>
                    <span className="text-zinc-500">)</span>
                  </div>
                  <div className="flex items-center gap-2 mt-1.5 pt-1.5 border-t border-zinc-800/40">
                    {r.derived ? (
                      <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-400 text-black font-bold font-mono">DERIVED</span>
                    ) : (
                      <span className="px-1.5 py-0.5 rounded text-[8px] border border-zinc-700 text-zinc-500 font-mono">BASE</span>
                    )}
                    <span className="text-[9px] text-zinc-600 font-mono">Confidence bounds: {(r.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-zinc-600">
              <HelpCircle className="w-8 h-8 mx-auto mb-2 text-zinc-850" />
              <p className="text-[10px]">No bound results yet.</p>
              <p className="text-[9px] text-zinc-700 mt-1">Select an example below to query:</p>
              <div className="mt-3.5 space-y-1.5 text-left max-w-xs mx-auto">
                {QUERY_EXAMPLES.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setQueryText(ex);
                      void handleRunQuery(ex);
                    }}
                    className="block w-full text-left p-2 rounded border border-zinc-850 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors font-mono text-[10px] truncate"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* BFS Shortest Path Finder panel */}
        <div className="p-4 bg-zinc-900/10 space-y-3 shrink-0">
          <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
            <GitFork className="w-3.5 h-3.5 text-indigo-400" /> Explainable BFS Path Router
          </div>
          <p className="text-[9px] text-zinc-600 leading-relaxed">Runs breadth-first graph traversal to resolve shortest proof chains between concepts.</p>
          
          <div className="grid grid-cols-2 gap-2">
            <input
              value={bfsSource}
              onChange={(e) => setBfsSource(e.target.value)}
              placeholder="Source Concept"
              className="bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-white placeholder:text-zinc-700 px-2.5 h-8.5 focus:outline-none focus:border-indigo-500"
            />
            <input
              value={bfsTarget}
              onChange={(e) => setBfsTarget(e.target.value)}
              placeholder="Target Concept"
              className="bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-white placeholder:text-zinc-700 px-2.5 h-8.5 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <button
            onClick={() => void handleBfsPath()}
            disabled={bfsLoading || !bfsSource.trim() || !bfsTarget.trim()}
            className="w-full h-8.5 bg-zinc-800 hover:bg-zinc-750 text-zinc-200 border border-zinc-700 hover:text-white text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 transition-all disabled:opacity-30"
          >
            {bfsLoading ? 'Routing paths...' : 'Compute Shortest Path'}
          </button>

          {/* BFS Path Result detail */}
          {bfsPathResult && (
            <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-950 space-y-2.5">
              {bfsPathResult.found ? (
                <div className="space-y-2">
                  <div className="text-[9px] text-zinc-500 font-mono uppercase tracking-wider">Shortest proof sequence resolved:</div>
                  <div className="flex flex-wrap items-center gap-1">
                    {bfsPathResult.path.map((label, i) => (
                      <span key={i} className="flex items-center gap-1">
                        {i > 0 && (
                          <span className="text-[9px] text-zinc-600 font-mono flex items-center shrink-0">
                            <ArrowRight className="w-2.5 h-2.5 mx-0.5" />
                            <strong className="text-zinc-500">[{bfsPathResult.edges[i - 1]?.label}]</strong>
                            <ArrowRight className="w-2.5 h-2.5 mx-0.5" />
                          </span>
                        )}
                        <span className="px-2 py-0.5 rounded bg-zinc-900 text-[10px] text-zinc-300 font-mono border border-zinc-800">
                          {label}
                        </span>
                      </span>
                    ))}
                  </div>
                  <div className="p-2 rounded bg-violet-400/5 border border-violet-400/10 text-[10px] leading-relaxed text-zinc-300 font-sans">
                    <strong className="text-violet-400 font-mono text-[9px] block uppercase mb-0.5">Proof explanation</strong>
                    {bfsPathResult.proof}
                  </div>
                </div>
              ) : (
                <p className="text-[10px] text-zinc-500 font-mono">No explainable connection path resolved.</p>
              )}
            </div>
          )}
          {bfsError && (
            <div className="p-2.5 rounded border border-rose-500/20 bg-rose-500/5 text-[10px] text-rose-400 font-mono">
              <AlertCircle className="w-3.5 h-3.5 inline mr-1" /> {bfsError}
            </div>
          )}
        </div>
      </div>

      {/* 2. RIGHT PANEL - High density tabular Triple Store ledger */}
      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Header */}
        <div className="p-4 border-b border-zinc-800 bg-zinc-900/10 shrink-0 flex items-center justify-between">
          <div>
            <h2 className="text-[13px] font-bold text-white tracking-wider uppercase flex items-center gap-2">
              <Database className="w-4 h-4 text-indigo-400" /> Relational Triple Ledger
            </h2>
            <p className="text-[10px] text-zinc-500 mt-0.5">High-density catalog of all base triples and dynamically derived deductive assertions</p>
          </div>
          <span className="px-2.5 py-1 rounded text-[10px] bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-mono font-bold">
            {totalTriples} total facts
          </span>
        </div>

        {/* Tabular Filters Bar */}
        <div className="p-4 border-b border-zinc-800 bg-zinc-950/20 shrink-0 flex flex-wrap gap-3 items-center">
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-zinc-500 uppercase tracking-wider font-mono">
            <ListFilter className="w-3.5 h-3.5" /> Filters:
          </div>
          
          <input
            value={subFilter}
            onChange={(e) => setSubFilter(e.target.value)}
            placeholder="Subject..."
            className="bg-zinc-900 border border-zinc-800 rounded-lg text-[11px] text-white px-2.5 h-8 placeholder:text-zinc-700 w-36 focus:outline-none focus:border-indigo-500"
          />

          <input
            value={predFilter}
            onChange={(e) => setPredFilter(e.target.value)}
            placeholder="Predicate..."
            className="bg-zinc-900 border border-zinc-800 rounded-lg text-[11px] text-white px-2.5 h-8 placeholder:text-zinc-700 w-36 focus:outline-none focus:border-indigo-500"
          />

          <input
            value={objFilter}
            onChange={(e) => setObjFilter(e.target.value)}
            placeholder="Object..."
            className="bg-zinc-900 border border-zinc-800 rounded-lg text-[11px] text-white px-2.5 h-8 placeholder:text-zinc-700 w-36 focus:outline-none focus:border-indigo-500"
          />

          <div className="h-6 w-[1px] bg-zinc-800 mx-1" />

          <div className="flex p-0.5 rounded-lg bg-zinc-950 border border-zinc-850">
            {(['all', 'base', 'derived'] as const).map((type) => (
              <button
                key={type}
                onClick={() => setTypeFilter(type)}
                className={`px-3 py-1 text-[10px] font-mono uppercase font-bold rounded-md transition-all duration-150 ${
                  typeFilter === type
                    ? 'bg-zinc-850 text-white shadow-sm'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* High-density Tabular Grid */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {loadingTriples ? (
            <div className="h-48 flex items-center justify-center text-zinc-500 text-[11px] font-mono gap-1.5">
              <div className="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
              Loading triple ledger rows...
            </div>
          ) : triplesError ? (
            <div className="p-4 m-4 rounded-lg border border-rose-500/30 bg-rose-500/5 text-xs text-rose-400 font-mono">
              <AlertCircle className="w-4 h-4 inline mr-1.5" /> {triplesError}
            </div>
          ) : filteredTriples.length > 0 ? (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/30 text-[10px] font-bold text-zinc-500 uppercase tracking-wider font-mono">
                  <th className="p-3 pl-5">Subject (Entity)</th>
                  <th className="p-3">Predicate (Relationship)</th>
                  <th className="p-3">Object (Target)</th>
                  <th className="p-3 text-right pr-5">Type / Confidence</th>
                </tr>
              </thead>
              <tbody className="text-[11px] font-mono text-zinc-300 divide-y divide-zinc-850">
                {filteredTriples.map((t, i) => (
                  <tr key={i} className="hover:bg-zinc-900/35 transition-colors group">
                    <td className="p-3 pl-5 font-semibold text-emerald-400 max-w-xs truncate">{t.subject}</td>
                    <td className="p-3 text-violet-400 font-bold max-w-xs truncate">{t.predicate}</td>
                    <td className="p-3 text-sky-400 max-w-xs truncate">{t.object}</td>
                    <td className="p-3 text-right pr-5 shrink-0">
                      <div className="flex items-center justify-end gap-2.5">
                        {t.derived ? (
                          <>
                            <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-400/10 border border-amber-400/20 text-amber-400 font-bold tracking-wider uppercase flex items-center gap-0.5">
                              <Sparkles className="w-2 h-2" /> Derived
                            </span>
                            <span className="text-zinc-400 font-bold">{(t.confidence * 100).toFixed(0)}%</span>
                          </>
                        ) : (
                          <>
                            <span className="px-1.5 py-0.5 rounded text-[8px] bg-zinc-800 text-zinc-500 border border-zinc-700/30 font-bold tracking-wider uppercase flex items-center gap-0.5">
                              <ShieldCheck className="w-2.5 h-2.5" /> Base
                            </span>
                            <span className="text-zinc-500">{(t.confidence * 100).toFixed(0)}%</span>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="h-64 flex flex-col items-center justify-center text-center text-zinc-600 font-mono py-10">
              <Database className="w-10 h-10 text-zinc-850 mb-3" />
              <p className="text-sm">No triples matched the current filter vectors.</p>
              <p className="text-[10px] text-zinc-700 mt-1">Try clearing some query values to list everything.</p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
