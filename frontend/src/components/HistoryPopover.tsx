// Floating popover listing documents posted into the current graph, most
// recent first, with expandable full text. Anchored under the left sidebar's
// History icon button; closes on outside click or Escape.
import { useEffect, useRef, useState } from 'react';
import { Clock, FileText, History, ChevronRight, ChevronDown, X } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';

interface HistoryPopoverProps {
  onClose: () => void;
}

export function HistoryPopover({ onClose }: HistoryPopoverProps) {
  const { history } = useGraphStore();
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
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

  return (
    <div
      ref={ref}
      className="absolute top-full left-0 mt-1 w-80 max-h-96 overflow-y-auto bg-zinc-900 border border-zinc-800 rounded shadow-xl z-50 flex flex-col"
    >
      <div className="h-8 px-2 border-b border-zinc-800 flex items-center justify-between shrink-0">
        <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
          <History className="w-3 h-3" />
          Ingest history
        </span>
        <button onClick={onClose} className="text-zinc-600 hover:text-zinc-300 transition-colors">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="p-2 flex flex-col gap-2">
        {history.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-zinc-600 gap-2 py-6">
            <History className="w-6 h-6 text-zinc-800" />
            <p className="text-[10px]">No documents posted yet.</p>
          </div>
        ) : (
          history.map((e) => {
            const expanded = expandedEventId === e.id;
            const preview = e.text.length > 140 && !expanded ? `${e.text.slice(0, 140)}…` : e.text;
            let when = e.createdAt;
            const parsed = new Date(e.createdAt);
            if (!Number.isNaN(parsed.getTime())) when = parsed.toLocaleString();
            return (
              <div key={e.id} className="border border-zinc-800 rounded p-2">
                <div className="flex items-center justify-between text-[10px] text-zinc-500">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {when}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span>{e.entityCount} entities</span>
                    <span>·</span>
                    <span>{e.relationshipCount} rels</span>
                    {e.droppedCount > 0 && (
                      <>
                        <span>·</span>
                        <span className="text-amber-400">{e.droppedCount} dropped</span>
                      </>
                    )}
                  </span>
                </div>
                <div className="mt-1.5 flex items-start gap-1.5">
                  <FileText className="w-3 h-3 text-zinc-600 shrink-0 mt-0.5" />
                  <p className="text-[11px] text-zinc-300 whitespace-pre-wrap">{preview}</p>
                </div>
                {e.text.length > 140 && (
                  <button
                    onClick={() => setExpandedEventId(expanded ? null : e.id)}
                    className="mt-1 text-[9px] text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-0.5"
                  >
                    {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    {expanded ? 'Show less' : 'Show full text'}
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
