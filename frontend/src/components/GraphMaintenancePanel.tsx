// Right sidebar "Automation" tab (Feature 7 follow-up, 2026-07-13): manual
// "run now" + real run history for the autonomous graph maintenance loop
// (backend/services/graph_maintenance_loop.py -- mine rule candidates,
// reason to convergence, backstop entity-resolution, report rule weights),
// plus scheduler configuration (backend/services/maintenance_scheduler.py).
// OFF by default per graph: nothing runs automatically until explicitly
// enabled here, since every automatic run spends real LLM + embedding API
// budget with no human watching.
import { useEffect, useState } from 'react';
import { Bot, Play, Loader, Clock, ChevronRight } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';
import type { LoopRun } from '../lib/api';

const MIN_INTERVAL_MINUTES = 5;

function RunCard({ run }: { run: LoopRun }) {
  return (
    <div className="p-2.5 rounded-lg border border-zinc-800 bg-zinc-900/50 space-y-1.5">
      <div className="text-[10px] text-zinc-300 leading-relaxed">{run.summaryText}</div>
      <div className="flex items-center gap-2 flex-wrap text-[8px] font-mono text-zinc-600">
        <span>{run.minedCandidateIds.length} mined</span>
        <span>·</span>
        <span>{run.duplicateCandidateIds.length} flagged dupes</span>
        {run.reasoningRan && (
          <>
            <span>·</span>
            <span>{run.reasoningNewFacts} new facts</span>
          </>
        )}
      </div>
    </div>
  );
}

export function GraphMaintenancePanel() {
  const {
    maintenanceRuns, maintenanceSchedule, maintenanceRunning,
    runGraphMaintenanceNow, loadMaintenanceRuns, loadMaintenanceSchedule, setMaintenanceSchedule,
  } = useGraphStore();
  const [intervalDraft, setIntervalDraft] = useState(String(MIN_INTERVAL_MINUTES * 12)); // 60m default

  useEffect(() => {
    void loadMaintenanceRuns();
    void loadMaintenanceSchedule();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (maintenanceSchedule) setIntervalDraft(String(maintenanceSchedule.intervalMinutes));
  }, [maintenanceSchedule?.intervalMinutes]); // eslint-disable-line react-hooks/exhaustive-deps

  const enabled = maintenanceSchedule?.enabled ?? false;
  const parsedInterval = Math.max(MIN_INTERVAL_MINUTES, parseInt(intervalDraft, 10) || MIN_INTERVAL_MINUTES);

  const handleToggle = async () => {
    await setMaintenanceSchedule(!enabled, parsedInterval);
  };

  const handleIntervalCommit = async () => {
    if (enabled) await setMaintenanceSchedule(true, parsedInterval);
  };

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Bot className="w-3.5 h-3.5" /> Automation
        </h3>
        <p className="text-[9px] text-zinc-600 mt-1">
          Real, recurring upkeep for this graph: mines rule candidates, runs reasoning to convergence, flags
          likely-duplicate entities, and reports rule weights. Every candidate still awaits your review --
          nothing auto-applies.
        </p>
      </div>

      <div className="p-3 border-b border-zinc-800 space-y-3 shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[10px] font-bold text-zinc-300">Autonomous schedule</div>
            <div className="text-[9px] text-zinc-600">{enabled ? `Running every ${maintenanceSchedule?.intervalMinutes}m` : 'Off — nothing runs on its own'}</div>
          </div>
          <button
            onClick={() => void handleToggle()}
            className={`relative w-9 h-5 rounded-full transition-colors shrink-0 ${enabled ? 'bg-emerald-500' : 'bg-zinc-700'}`}
            title={enabled ? 'Disable autonomous maintenance' : 'Enable autonomous maintenance'}
          >
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <Clock className="w-3 h-3 text-zinc-600 shrink-0" />
          <input
            type="number"
            min={MIN_INTERVAL_MINUTES}
            value={intervalDraft}
            onChange={(e) => setIntervalDraft(e.target.value)}
            onBlur={() => void handleIntervalCommit()}
            className="w-16 bg-zinc-900 border border-zinc-700 rounded text-[10px] text-white px-1.5 h-6 focus:outline-none focus:border-zinc-600"
          />
          <span className="text-[9px] text-zinc-600">minutes between runs (min {MIN_INTERVAL_MINUTES})</span>
        </div>

        {maintenanceSchedule?.lastRunAt && (
          <div className="text-[9px] text-zinc-600">Last automatic run: {maintenanceSchedule.lastRunAt}</div>
        )}

        <button
          onClick={() => void runGraphMaintenanceNow()}
          disabled={maintenanceRunning}
          className="w-full h-8 rounded bg-blue-600 text-onaccent hover:bg-blue-500 transition-colors disabled:opacity-40 flex items-center justify-center gap-1.5 text-[10px] font-bold uppercase tracking-wider"
        >
          {maintenanceRunning ? <Loader className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          Run Now
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        <div className="text-[9px] font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1">
          <ChevronRight className="w-3 h-3" /> Run History ({maintenanceRuns.length})
        </div>
        {maintenanceRuns.length === 0 ? (
          <div className="text-center text-[10px] text-zinc-600 mt-8">
            <Bot className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
            No maintenance runs yet for this graph.
          </div>
        ) : (
          maintenanceRuns.map((run) => <RunCard key={run.id} run={run} />)
        )}
      </div>
    </div>
  );
}
