// Floating, canvas-anchored contextual node inspector (UI_REFACTOR_PLAN.md
// §3.4/§5): a read-only summary of the selected node, plus a shortcut into
// the sidebar's Build > Construct section for full editing (salience,
// properties, note) -- that form stays exactly where it is in
// ConstructionPanel.tsx, unchanged. Ported from .claude/docs/mocks/polanyigraph,
// fixed to the real store's LayoutNode/DerivedFact types (the mock referenced
// nonexistent `Node`/`Fact` type aliases and a `.reason` field that isn't
// part of the real DerivedFact shape).
import { Edit3, X, GitBranch } from 'lucide-react';
import type { LayoutNode } from '../stores/graphStore';
import type { DerivedFact } from '../lib/api';

interface NodeInspectorCardProps {
  node: LayoutNode;
  facts: DerivedFact[];
  onClose: () => void;
  onEditShortcut: () => void;
}

export function NodeInspectorCard({ node, facts, onClose, onEditShortcut }: NodeInspectorCardProps) {
  const isDerived = node.derived ?? false;
  const activation = node.activation ?? 0;
  const isActive = activation > 0.01;
  const salience = node.salience ?? 1.0;

  const correspondingFact = facts.find((f) => f.targetId === node.id);
  const proofPath = correspondingFact?.proofPath ?? [];
  const sourceDoc = node.sourceDoc ?? correspondingFact?.fact ?? '';

  return (
    <div className="absolute top-4 right-4 z-10 w-72 p-4 rounded-lg bg-zinc-900/90 backdrop-blur-md border border-zinc-800 shadow-xl transition-all duration-200">
      <div className="flex items-start justify-between mb-3 pb-2 border-b border-zinc-800/60">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-xs font-semibold text-white truncate max-w-[180px]">{node.label}</h3>
            {isDerived && (
              <span className="text-[8px] font-mono font-bold px-1 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/25">
                derived
              </span>
            )}
          </div>
          <p className="text-[9px] font-mono text-zinc-500 mt-0.5 break-all">{node.type}</p>
        </div>
        <button onClick={onClose} className="p-1 rounded text-zinc-500 hover:bg-zinc-800 hover:text-white transition-colors shrink-0">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="space-y-3 text-[11px]">
        <div className="flex justify-between items-center text-zinc-400">
          <span>Activation Level</span>
          <div className="flex items-center gap-1.5 font-mono">
            <span className={isActive ? 'text-amber-400 font-bold' : 'text-zinc-500'}>{activation.toFixed(2)}</span>
            <div className="w-16 h-1.5 rounded bg-zinc-800 overflow-hidden">
              <div className={`h-full ${isActive ? 'bg-amber-400' : 'bg-zinc-700'}`} style={{ width: `${Math.min(100, activation * 100)}%` }} />
            </div>
          </div>
        </div>

        <div className="flex justify-between items-center text-zinc-400">
          <span>Salience Multiplier</span>
          <span className="font-mono text-zinc-200">{salience.toFixed(2)}</span>
        </div>

        {proofPath.length > 0 && (
          <div className="flex justify-between items-center text-zinc-400">
            <span>Proof Path Hops</span>
            <span className="font-mono text-sky-400 flex items-center gap-1">
              <GitBranch className="w-3 h-3" />
              {proofPath.length} step{proofPath.length === 1 ? '' : 's'}
            </span>
          </div>
        )}

        <div className="text-zinc-400 space-y-1">
          <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-wider block">Recent Source / Proof</span>
          {sourceDoc ? (
            <p className="text-[10px] text-zinc-300 leading-relaxed italic bg-zinc-950 p-2 rounded border border-zinc-800/40 max-h-24 overflow-y-auto break-words font-sans">
              "{sourceDoc}"
            </p>
          ) : (
            <p className="text-[10px] text-zinc-600 leading-relaxed italic bg-zinc-950/40 p-2 rounded border border-zinc-800/20">
              No source snippet registered.
            </p>
          )}
        </div>

        <button
          onClick={onEditShortcut}
          className="w-full mt-1.5 py-1.5 px-2.5 rounded bg-zinc-800 hover:bg-zinc-700 hover:text-white text-[10px] font-semibold flex items-center justify-center gap-1.5 border border-zinc-700/50 transition-colors"
        >
          <Edit3 className="w-3 h-3 text-blue-400" />
          <span>Edit full details in Build panel</span>
        </button>
      </div>
    </div>
  );
}
