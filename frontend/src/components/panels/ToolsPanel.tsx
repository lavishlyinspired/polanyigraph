// Sidebar "Tools" tab (UI_REFACTOR_PLAN.md §2): pill switcher over the
// existing, unchanged SkillManager/MemoryInspector -- both real, backed by
// GET /skills, POST /skills/{name}/activate, POST /memory/{graphId}/search,
// GET/PUT/DELETE /memory/preferences. Same pattern as QueryExplorePanel.
// "Auto" tab added (Feature 7 follow-up, 2026-07-13): manual run + real
// recurring-schedule config for the autonomous graph maintenance loop.
import { useState } from 'react';
import { Wrench, BrainCircuit, Bot } from 'lucide-react';
import { SkillManager } from '../SkillManager';
import { MemoryInspector } from '../MemoryInspector';
import { GraphMaintenancePanel } from '../GraphMaintenancePanel';

export function ToolsPanel() {
  const [mode, setMode] = useState<'skills' | 'memory' | 'automation'>('skills');

  return (
    <div className="h-full flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden">
      <div className="p-3 border-b border-zinc-800 bg-zinc-900/10 flex shrink-0">
        <div className="w-full grid grid-cols-3 gap-1 p-0.5 rounded-lg bg-zinc-950 border border-zinc-800/80">
          <button
            onClick={() => setMode('skills')}
            className={`py-1 text-[10px] font-semibold rounded flex items-center justify-center gap-1.5 transition-all duration-150 ${
              mode === 'skills' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Wrench className="w-3 h-3" />
            <span>Skills</span>
          </button>
          <button
            onClick={() => setMode('memory')}
            className={`py-1 text-[10px] font-semibold rounded flex items-center justify-center gap-1.5 transition-all duration-150 ${
              mode === 'memory' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <BrainCircuit className="w-3 h-3" />
            <span>Memory</span>
          </button>
          <button
            onClick={() => setMode('automation')}
            className={`py-1 text-[10px] font-semibold rounded flex items-center justify-center gap-1.5 transition-all duration-150 ${
              mode === 'automation' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Bot className="w-3 h-3" />
            <span>Auto</span>
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        {mode === 'skills' ? <SkillManager /> : mode === 'memory' ? <MemoryInspector /> : <GraphMaintenancePanel />}
      </div>
    </div>
  );
}
