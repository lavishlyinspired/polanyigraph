import { Network, Zap, RotateCcw, Cpu, Database, Brain, Activity, RefreshCw } from 'lucide-react';

interface ToolbarProps {
  nodeCount: number;
  edgeCount: number;
  ruleCount: number;
  factCount: number;
  activeCount: number;
  onRunInference: () => void;
  onClearActivation: () => void;
  onReset: () => void;
}

export function Toolbar({ nodeCount, edgeCount, ruleCount, factCount, activeCount, onRunInference, onClearActivation, onReset }: ToolbarProps) {
  const cpuLoad = Math.min(100, Math.round((activeCount / Math.max(1, nodeCount)) * 100));

  return (
    <header className="shrink-0 h-9 bg-black border-b border-zinc-800 px-4 flex items-center justify-between text-xs select-none">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 font-serif font-bold text-white tracking-tight">
          <Network className="w-4 h-4" />
          FIBO-OS
        </div>
        <span className="text-zinc-700">|</span>
        <span className="text-zinc-500 text-[11px]">Neurosymbolic Graph Operating System</span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 text-zinc-400">
          <Database className="w-3 h-3" />
          <span className="font-mono text-[11px]">{nodeCount} nodes · {edgeCount} edges</span>
        </div>
        <div className="flex items-center gap-1.5 text-zinc-400">
          <Brain className="w-3 h-3" />
          <span className="font-mono text-[11px]">{ruleCount} rules</span>
        </div>
        <div className="flex items-center gap-1.5 text-zinc-400">
          <Activity className="w-3 h-3" />
          <span className="font-mono text-[11px]">{factCount} facts</span>
        </div>
        <span className="text-zinc-800">|</span>
        <div className="flex items-center gap-1.5 text-zinc-400">
          <Cpu className="w-3 h-3" />
          <span className="font-mono text-[11px]">CPU {cpuLoad}%</span>
          <div className="w-12 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div className="h-full bg-white transition-all duration-500" style={{ width: `${cpuLoad}%` }} />
          </div>
        </div>
        <span className="text-zinc-800">|</span>
        <button onClick={onRunInference} className="text-white hover:text-zinc-300 flex items-center gap-1 text-[11px] font-medium">
          <Zap className="w-3 h-3" /> Infer
        </button>
        <button onClick={onClearActivation} className="text-zinc-400 hover:text-white text-[11px]">
          Clear
        </button>
        <button onClick={onReset} className="text-zinc-400 hover:text-white flex items-center gap-1 text-[11px]">
          <RotateCcw className="w-3 h-3" /> Reboot
        </button>
      </div>
    </header>
  );
}