import { useState } from 'react';
import { Sparkles, Terminal, Bot } from 'lucide-react';
import { LlmPanel } from '../LlmPanel';
import { AgentPanel } from '../AgentPanel';

export function AssistantPanel() {
  const [mode, setMode] = useState<'ask' | 'act'>('ask');

  return (
    <div className="h-full flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* Mode Selector */}
      <div className="p-3 border-b border-zinc-800 bg-zinc-900/10 flex flex-col gap-2 shrink-0">
        <div className="grid grid-cols-2 gap-1 p-0.5 rounded-lg bg-zinc-950 border border-zinc-800/80">
          <button
            onClick={() => setMode('ask')}
            className={`py-1.5 text-[10px] font-semibold rounded flex items-center justify-center gap-1.5 transition-all duration-150 ${
              mode === 'ask'
                ? 'bg-zinc-800 text-white shadow-sm'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Terminal className="w-3 h-3" />
            <span>Ask (Read-Only)</span>
          </button>
          <button
            onClick={() => setMode('act')}
            className={`py-1.5 text-[10px] font-semibold rounded flex items-center justify-center gap-1.5 transition-all duration-150 ${
              mode === 'act'
                ? 'bg-zinc-800 text-indigo-400 font-bold shadow-sm'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Bot className="w-3 h-3" />
            <span>Act (Agentic Mutate)</span>
          </button>
        </div>

        {/* Short info badge */}
        <div className="text-[9px] text-zinc-500 px-1 leading-relaxed flex items-center gap-1">
          <Sparkles className="w-2.5 h-2.5 text-indigo-400 shrink-0" />
          <span>
            {mode === 'ask'
              ? 'Query the knowledge graph in plain English without modifying state.'
              : 'Instruct LangGraph agent to extract, enrich, query, reason, or visualize.'}
          </span>
        </div>
      </div>

      {/* Content wrapper */}
      <div className="flex-1 overflow-hidden">
        {mode === 'ask' ? <LlmPanel /> : <AgentPanel />}
      </div>
    </div>
  );
}
