// Thin status bar (UI_REFACTOR_PLAN.md §4): node/edge/rule/fact/iteration
// counts and neo4j/graphdb status, relocated out of the header. Ported from
// .claude/docs/mocks/polanyigraph, field names verified against the real
// graphStore.ts/api.ts (unchanged from the mock -- no fixes needed).
import { CircleDot, GitBranch, Database, Cpu, Brain, Zap } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';
import type { HealthResponse } from '../lib/api';

interface StatusFooterProps {
  health: HealthResponse | null;
}

export function StatusFooter({ health }: StatusFooterProps) {
  const { nodes, edges, facts, rules, iterations } = useGraphStore();

  return (
    <footer className="h-6 border-t border-zinc-800 bg-chrome px-4 flex items-center justify-between shrink-0 select-none text-[10px] text-zinc-500 font-mono">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <Database className="w-3 h-3 text-zinc-400" />
          <span>
            {nodes.length} nodes · {edges.length} edges
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Cpu className="w-3 h-3 text-zinc-400" />
          <span>{rules.length} rules</span>
        </div>
        {facts.length > 0 && (
          <div className="flex items-center gap-1.5 text-amber-500/80 font-bold">
            <Brain className="w-3 h-3 text-amber-500/60 animate-pulse" />
            <span>{facts.length} facts</span>
          </div>
        )}
        {iterations > 0 && (
          <div className="flex items-center gap-1.5 text-zinc-500">
            <Zap className="w-3 h-3 text-zinc-400" />
            <span>iter {iterations}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <CircleDot className={`w-2.5 h-2.5 ${health?.neo4j.ok ? 'text-emerald-500' : 'text-rose-500 animate-pulse'}`} />
          <span>neo4j: {health?.neo4j.ok ? 'online' : 'offline'}</span>
        </div>
        <div className="h-2 w-[1px] bg-zinc-800" />
        <div className="flex items-center gap-1">
          <GitBranch className={`w-2.5 h-2.5 ${health?.graphdb.ok ? 'text-emerald-500' : 'text-rose-500 animate-pulse'}`} />
          <span>graphdb: {health?.graphdb.ok ? 'online' : 'offline'}</span>
        </div>
        {health?.llm.model && (
          <>
            <div className="h-2 w-[1px] bg-zinc-800" />
            <span className="text-zinc-600">powered by {health.llm.model}</span>
          </>
        )}
      </div>
    </footer>
  );
}
