// Right sidebar "Agent" tab (MVP_PLAN.md Phase 6, PLAN.md §8). Unlike the
// LLM tab (POST /chat, read-only Q&A grounded in graph state), this hits
// POST /agent -- a real LangGraph agent that classifies intent and can
// mutate the graph for real: extract new entities, run reasoning, run
// Polanyi enrichment, answer a structured query, or describe a
// visualization, depending on what the message asks for.
import { useState } from 'react';
import { Bot, Send, Sparkles, Search, Brain, Eye, FileText } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';
import type { AgentIntent } from '../lib/api';

const SUGGESTIONS = [
  'Deutsche Bank AG issued a bond and is regulated by the European Central Bank.',
  'Run reasoning over the graph.',
  'Enrich the graph with implicit knowledge.',
  'Show me an overview of the graph.',
];

const INTENT_META: Record<Exclude<AgentIntent, ''>, { label: string; icon: typeof Bot; color: string }> = {
  extract: { label: 'Extract', icon: FileText, color: 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10' },
  enrich: { label: 'Enrich', icon: Sparkles, color: 'text-sky-400 border-sky-400/40 bg-sky-400/10' },
  query: { label: 'Query', icon: Search, color: 'text-sky-400 border-sky-400/40 bg-sky-400/10' },
  reason: { label: 'Reason', icon: Brain, color: 'text-amber-400 border-amber-400/40 bg-amber-400/10' },
  visualize: { label: 'Visualize', icon: Eye, color: 'text-sky-400 border-sky-400/40 bg-sky-400/10' },
};

function IntentBadge({ intent }: { intent?: AgentIntent }) {
  if (!intent) return null;
  const meta = INTENT_META[intent];
  if (!meta) return null;
  const Icon = meta.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider border ${meta.color}`}>
      <Icon className="w-2.5 h-2.5" /> {meta.label}
    </span>
  );
}

export function AgentPanel() {
  const { agentMessages, agentLoading, sendAgentMessage } = useGraphStore();
  const [input, setInput] = useState('');

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    await sendAgentMessage(text);
  };

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Bot className="w-3.5 h-3.5" /> Agent
        </h3>
        <p className="text-[9px] text-zinc-600 mt-1">
          One message, real work. A router classifies your intent and does it for real: extract, enrich, query,
          reason, or visualize -- unlike LLM chat, this can change the graph.
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {agentMessages.length === 0 ? (
          <div className="text-center text-[10px] text-zinc-600 mt-8">
            <Bot className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
            Tell the agent what to do.
            <div className="mt-3 space-y-1">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setInput(s)}
                  className="block w-full text-left p-1.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors truncate"
                  title={s}
                >
                  "{s}"
                </button>
              ))}
            </div>
          </div>
        ) : (
          agentMessages.map((msg) => (
            <div
              key={msg.id}
              className={`p-2.5 rounded-lg text-[11px] ${
                msg.role === 'user' ? 'bg-white text-black ml-4' : 'bg-zinc-900 text-zinc-300 border border-zinc-800 mr-4'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[9px] font-bold uppercase opacity-50">{msg.role}</span>
                <IntentBadge intent={msg.intent} />
              </div>
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          ))
        )}
        {agentLoading && (
          <div className="p-2.5 rounded-lg text-[11px] bg-zinc-900 text-zinc-500 border border-zinc-800 mr-4 flex items-center gap-2">
            <div className="w-3 h-3 border-2 border-zinc-500 border-t-transparent rounded-full animate-spin" />
            Routing and working…
          </div>
        )}
      </div>
      <div className="p-3 border-t border-zinc-800 shrink-0">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void handleSend()}
            placeholder="Paste text to extract, ask a query, or say 'run reasoning'..."
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded text-xs text-white placeholder:text-zinc-600 px-2 h-8 focus:outline-none focus:border-zinc-600"
          />
          <button onClick={() => void handleSend()} className="h-8 px-3 rounded bg-white text-black hover:bg-zinc-200 transition-colors">
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
