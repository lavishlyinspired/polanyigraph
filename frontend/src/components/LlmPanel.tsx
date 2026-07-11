// Right sidebar "LLM" tab. Visual language ported from the prototype
// (.claude/docs/src/components/InspectorPanel.tsx LlmPanel), but wired to a
// real LLM call (POST /chat/{graphId}) grounded in the real graph's entities,
// relationships, and derived facts -- not the prototype's random-pick from a
// fixed list of canned strings.
import { useState } from 'react';
import { Terminal, Send } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';

const SUGGESTIONS = ['What entities are in this graph?', 'Summarize the derived facts', 'What is regulated by whom?', 'Explain the last reasoning run'];

export function LlmPanel() {
  const { chatMessages, chatLoading, sendChatMessage } = useGraphStore();
  const [input, setInput] = useState('');

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    await sendChatMessage(text);
  };

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Terminal className="w-3.5 h-3.5" /> LLM Console
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {chatMessages.length === 0 ? (
          <div className="text-center text-[10px] text-zinc-600 mt-8">
            <Terminal className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
            Ask a real question about this graph.
            <div className="mt-3 space-y-1">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setInput(s)}
                  className="block w-full text-left p-1.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  "{s}"
                </button>
              ))}
            </div>
          </div>
        ) : (
          chatMessages.map((msg) => (
            <div
              key={msg.id}
              className={`p-2.5 rounded-lg text-[11px] ${
                msg.role === 'user' ? 'bg-white text-black ml-4' : 'bg-zinc-900 text-zinc-300 border border-zinc-800 mr-4'
              }`}
            >
              <div className="text-[9px] font-bold uppercase mb-1 opacity-50">{msg.role}</div>
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          ))
        )}
        {chatLoading && (
          <div className="p-2.5 rounded-lg text-[11px] bg-zinc-900 text-zinc-500 border border-zinc-800 mr-4 flex items-center gap-2">
            <div className="w-3 h-3 border-2 border-zinc-500 border-t-transparent rounded-full animate-spin" />
            Thinking…
          </div>
        )}
      </div>
      <div className="p-3 border-t border-zinc-800 shrink-0">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void handleSend()}
            placeholder="Ask about the graph state..."
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
