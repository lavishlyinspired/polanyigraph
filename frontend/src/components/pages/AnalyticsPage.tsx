// Analytics Lab (plans/analytical-engine.md Slice 9): run a graph algorithm
// and see ranked results, structured like QueryPage.tsx -- page-level state,
// direct api.ts calls, no separate panel component.
import { useEffect, useState } from 'react';
import { api, type AlgorithmInfo, type SuggestedChart } from '../../lib/api';
import { useGraphStore } from '../../stores/graphStore';

export function AnalyticsPage() {
  const { graphId } = useGraphStore();

  const [algorithms, setAlgorithms] = useState<AlgorithmInfo[]>([]);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nodeScores, setNodeScores] = useState<Record<string, number> | null>(null);
  const [suggestedChart, setSuggestedChart] = useState<SuggestedChart>(null);
  const [persisting, setPersisting] = useState(false);
  const [persisted, setPersisted] = useState(false);

  useEffect(() => {
    api
      .listAlgorithms()
      .then((res) => {
        setAlgorithms(res.algorithms);
        setSelectedAlgorithm((current) => current || res.algorithms[0]?.name || '');
      })
      .catch((e) => setError(String(e)));
  }, []);

  const handleRun = async () => {
    if (!selectedAlgorithm) return;
    setRunning(true);
    setError(null);
    setPersisted(false);
    try {
      await api.createProjection(graphId);
      const result = await api.runAlgorithm(graphId, selectedAlgorithm);
      setNodeScores(result.nodeScores);
      setSuggestedChart(result.suggestedChart);
    } catch (e) {
      setError(String(e));
      setNodeScores(null);
    } finally {
      setRunning(false);
    }
  };

  const handlePersist = async () => {
    if (!nodeScores) return;
    setPersisting(true);
    try {
      // Fixed property name (not per-algorithm) -- GraphCanvas.tsx's
      // showCentrality mode and get_graph()'s centralityScore field both
      // read this one property, matching communityId's shared convention.
      await api.persistAlgorithmResult(graphId, selectedAlgorithm, 'centralityScore');
      setPersisted(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setPersisting(false);
    }
  };

  const ranked = nodeScores
    ? Object.entries(nodeScores).sort(([, a], [, b]) => b - a)
    : [];
  const maxScore = ranked.length > 0 ? Math.max(...ranked.map(([, score]) => score)) : 0;

  return (
    <div className="p-6 text-sm text-zinc-300">
      <h1 className="text-lg font-bold text-white mb-4">Analytics Lab</h1>

      <div className="flex items-center gap-2 mb-4">
        <select
          className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1"
          value={selectedAlgorithm}
          onChange={(e) => setSelectedAlgorithm(e.target.value)}
        >
          {algorithms.map((a) => (
            <option key={a.name} value={a.name}>
              {a.name}
            </option>
          ))}
        </select>
        <button
          className="bg-cyan-600 hover:bg-cyan-500 text-white rounded px-3 py-1 disabled:opacity-50"
          onClick={handleRun}
          disabled={running || !selectedAlgorithm}
        >
          {running ? 'Running...' : 'Run'}
        </button>
        {nodeScores && (
          <button
            className="bg-zinc-700 hover:bg-zinc-600 text-white rounded px-3 py-1 disabled:opacity-50"
            onClick={handlePersist}
            disabled={persisting}
          >
            {persisted ? 'Written back' : persisting ? 'Writing back...' : 'Write back to graph'}
          </button>
        )}
      </div>

      {error && <div className="text-red-400 mb-4">{error}</div>}

      {ranked.length > 0 && (
        <table className="w-full">
          <thead>
            <tr className="text-left text-zinc-500">
              <th>Entity</th>
              <th>Score</th>
              {suggestedChart === 'bar' && <th />}
            </tr>
          </thead>
          <tbody>
            {ranked.map(([nodeId, score]) => (
              <tr key={nodeId}>
                <td>{nodeId}</td>
                <td>{score.toFixed(3)}</td>
                {suggestedChart === 'bar' && (
                  <td>
                    <div
                      className="h-2 bg-cyan-500 rounded"
                      style={{ width: `${maxScore > 0 ? (score / maxScore) * 100 : 0}%` }}
                    />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
