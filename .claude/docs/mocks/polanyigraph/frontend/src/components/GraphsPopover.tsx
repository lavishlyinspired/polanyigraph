// Floating popover for switching/creating graphs. Same interaction pattern as
// HistoryPopover.tsx (anchored under a left-sidebar icon, closes on outside
// click / Escape) -- moved out of the Construct tab per explicit direction.
import { useEffect, useRef, useState } from 'react';
import { FolderOpen, ChevronRight, Plus, X } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';

interface GraphsPopoverProps {
  onClose: () => void;
}

export function GraphsPopover({ onClose }: GraphsPopoverProps) {
  const { graphs, graphId, switchGraph } = useGraphStore();
  const [newGraphName, setNewGraphName] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [onClose]);

  const handleCreate = async () => {
    const name = newGraphName.trim();
    if (!name) return;
    await switchGraph(name);
    setNewGraphName('');
    onClose();
  };

  return (
    <div
      ref={ref}
      className="absolute top-full left-0 mt-1 w-72 max-h-96 overflow-y-auto bg-zinc-900 border border-zinc-800 rounded shadow-xl z-50 flex flex-col"
    >
      <div className="h-8 px-2 border-b border-zinc-800 flex items-center justify-between shrink-0">
        <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
          <FolderOpen className="w-3 h-3" /> Graphs
        </span>
        <button onClick={onClose} className="text-zinc-600 hover:text-zinc-300 transition-colors">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="p-2 space-y-1.5">
        {graphs.length === 0 && <p className="text-[10px] text-zinc-600 py-2 text-center">No graphs yet.</p>}
        {graphs.map((g) => (
          <button
            key={g.graphId}
            onClick={() => {
              void switchGraph(g.graphId);
              onClose();
            }}
            className={`w-full text-left p-2 rounded-lg border text-[10px] transition-colors ${
              g.graphId === graphId ? 'border-white bg-white text-black font-semibold' : 'border-zinc-800 bg-zinc-950 text-zinc-400 hover:border-zinc-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="truncate">{g.graphId}</span>
              <ChevronRight className="w-3 h-3 shrink-0" />
            </div>
            <div className={g.graphId === graphId ? 'text-black/60' : 'text-zinc-600'}>
              {g.nodeCount} nodes · {g.edgeCount} edges
            </div>
          </button>
        ))}
      </div>

      <div className="p-2 border-t border-zinc-800 flex gap-2">
        <input
          value={newGraphName}
          onChange={(e) => setNewGraphName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void handleCreate()}
          placeholder="new-graph-name"
          className="flex-1 bg-zinc-950 border border-zinc-700 rounded text-[10px] text-white placeholder:text-zinc-600 px-2 h-7 focus:outline-none focus:border-zinc-600"
        />
        <button onClick={() => void handleCreate()} className="h-7 px-2 rounded bg-white text-black hover:bg-zinc-200 transition-colors" title="Switch to (or create) this graph">
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
