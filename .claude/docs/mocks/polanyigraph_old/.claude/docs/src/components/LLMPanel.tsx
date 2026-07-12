import { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Sparkles, Send, Brain } from 'lucide-react';
import type { ChatMessage, GraphNode, GraphEdge, DerivedFact, ActivationResult } from '../types';
import { llmRespond, createUserMessage, createAssistantMessage } from '../lib/llm';

interface LLMPanelProps {
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  nodes: GraphNode[];
  edges: GraphEdge[];
  activationResult: ActivationResult | null;
  derivedFacts: DerivedFact[];
  selectedNode: GraphNode | null;
}

const SUGGESTED_QUERIES = [
  "What securities are in the graph?",
  "What are the disclosure obligations?",
  "What derivatives have underlier risk?",
  "What's missing?",
  "Summarize the derived facts",
];

export function LLMPanel({
  messages, onMessagesChange, nodes, edges, activationResult, derivedFacts, selectedNode,
}: LLMPanelProps) {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = (text?: string) => {
    const content = (text ?? input).trim();
    if (!content) return;

    const userMsg = createUserMessage(content);
    const response = llmRespond(content, { nodes, edges, activationResult, derivedFacts, selectedNode });
    const assistantMsg = createAssistantMessage(response);

    onMessagesChange([...messages, userMsg, assistantMsg]);
    setInput('');
  };

  return (
    <Card className="border-violet-200 bg-gradient-to-br from-violet-50/50 to-white flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-serif text-violet-900 flex items-center gap-1.5">
          <Brain className="w-4 h-4" />
          LLM Reasoning
        </CardTitle>
        <CardDescription className="text-xs text-violet-700/70">
          Ask the FIBO graph questions — it reasons over activation + inference.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 p-3">
        <div ref={scrollRef} className="overflow-y-auto space-y-2 min-h-0 max-h-48">
          {messages.length === 0 ? (
            <div className="text-center py-4">
              <Sparkles className="w-6 h-6 text-violet-300 mx-auto mb-2" />
              <p className="text-xs text-slate-400 italic">Ask me about the FIBO graph…</p>
            </div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-lg px-3 py-2 text-xs whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-violet-600 text-white'
                    : 'bg-white border border-violet-200 text-slate-700'
                }`}>
                  {msg.content}
                </div>
              </div>
            ))
          )}
        </div>

        {messages.length === 0 && (
          <div className="flex flex-wrap gap-1">
            {SUGGESTED_QUERIES.map((q) => (
              <button key={q} onClick={() => handleSend(q)}
                className="text-[10px] rounded-full bg-violet-100 text-violet-700 px-2.5 py-1 hover:bg-violet-200 transition-colors">
                {q}
              </button>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask the FIBO graph…"
            rows={1}
            className="text-xs bg-white resize-none border-violet-200 focus:ring-violet-400"
          />
          <Button size="sm" className="bg-violet-600 hover:bg-violet-700 text-white shrink-0"
            onClick={() => handleSend()}>
            <Send className="w-3.5 h-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}