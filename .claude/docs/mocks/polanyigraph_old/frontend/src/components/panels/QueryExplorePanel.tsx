import { useState } from 'react';
import { Search, Database, BookOpen } from 'lucide-react';
import { QueryPanel } from '../QueryPanel';
import { TripleStorePanel } from '../TripleStorePanel';
import { OntologyPanel } from '../OntologyPanel';

export function QueryExplorePanel() {
  const [mode, setMode] = useState<'pattern' | 'triples' | 'ontology'>('pattern');

  return (
    <div className="h-full flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* Segmented Control Pill Switcher */}
      <div className="p-3 border-b border-zinc-800 bg-zinc-900/10 flex shrink-0">
        <div className="w-full grid grid-cols-3 gap-1 p-0.5 rounded-lg bg-zinc-950 border border-zinc-800/80">
          <button
            onClick={() => setMode('pattern')}
            className={`py-1 text-[10px] font-semibold rounded flex items-center justify-center gap-1.5 transition-all duration-150 ${
              mode === 'pattern'
                ? 'bg-zinc-800 text-white shadow-sm'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Search className="w-3 h-3" />
            <span>Query</span>
          </button>
          <button
            onClick={() => setMode('triples')}
            className={`py-1 text-[10px] font-semibold rounded flex items-center justify-center gap-1.5 transition-all duration-150 ${
              mode === 'triples'
                ? 'bg-zinc-800 text-white shadow-sm'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Database className="w-3 h-3" />
            <span>Triples</span>
          </button>
          <button
            onClick={() => setMode('ontology')}
            className={`py-1 text-[10px] font-semibold rounded flex items-center justify-center gap-1.5 transition-all duration-150 ${
              mode === 'ontology'
                ? 'bg-zinc-800 text-white shadow-sm'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <BookOpen className="w-3 h-3" />
            <span>Ontology</span>
          </button>
        </div>
      </div>

      {/* Content wrapper */}
      <div className="flex-1 overflow-hidden">
        {mode === 'pattern' ? (
          <QueryPanel />
        ) : mode === 'triples' ? (
          <TripleStorePanel />
        ) : (
          <OntologyPanel />
        )}
      </div>
    </div>
  );
}
