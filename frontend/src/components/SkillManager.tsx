// Right sidebar "Skills" tab (PLAN.md §13.2). Real, live view into the same
// backend/skills/*/SKILL.md Discovery/Activation store the LangGraph agent
// loads from at inference time, and the same real persisted "active" state
// (services/skill_activation_store.py) that mcp_skills_server.py exposes to
// MCP clients -- activating a skill here does the exact same Neo4j write.
import { useEffect, useState } from 'react';
import { Wrench, Zap, ChevronDown, ChevronRight, Loader } from 'lucide-react';
import { useGraphStore } from '../stores/graphStore';

export function SkillManager() {
  const { skills, skillsLoading, selectedSkillContent, activatingSkillName, loadSkills, loadSkillContent, activateSkill } = useGraphStore();
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    void loadSkills();
  }, [loadSkills]);

  const handleToggle = async (name: string) => {
    if (expanded === name) {
      setExpanded(null);
      return;
    }
    setExpanded(name);
    await loadSkillContent(name);
  };

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Wrench className="w-3.5 h-3.5" /> Skills
        </h3>
        <p className="text-[9px] text-zinc-600 mt-1">
          The real runtime skills the agent loads from <code className="text-zinc-500">backend/skills/</code>. Activating
          one persists a real <code className="text-zinc-500">:ActiveSkill</code> node in Neo4j -- not cosmetic.
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {skillsLoading ? (
          <div className="flex items-center gap-2 text-[10px] text-zinc-600 justify-center mt-8">
            <Loader className="w-3.5 h-3.5 animate-spin" /> Loading skills…
          </div>
        ) : skills.length === 0 ? (
          <p className="text-[10px] text-zinc-600 text-center mt-8">No runtime skills found.</p>
        ) : (
          skills.map((skill) => (
            <div key={skill.name} className="rounded-lg border border-zinc-800 overflow-hidden">
              <button
                onClick={() => void handleToggle(skill.name)}
                className="w-full flex items-center justify-between gap-2 p-2.5 hover:bg-zinc-900/50 transition-colors text-left"
              >
                <div className="flex items-center gap-1.5 min-w-0">
                  {expanded === skill.name ? (
                    <ChevronDown className="w-3 h-3 text-zinc-600 shrink-0" />
                  ) : (
                    <ChevronRight className="w-3 h-3 text-zinc-600 shrink-0" />
                  )}
                  <span className="text-[11px] font-bold text-zinc-200 truncate">{skill.name}</span>
                </div>
                <span
                  className={`shrink-0 px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider border ${
                    skill.active
                      ? 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10'
                      : 'text-zinc-500 border-zinc-700 bg-zinc-800/40'
                  }`}
                >
                  {skill.active ? 'Active' : 'Inactive'}
                </span>
              </button>
              {expanded === skill.name && (
                <div className="px-2.5 pb-2.5 space-y-2 border-t border-zinc-800 pt-2">
                  <p className="text-[10px] text-zinc-500 leading-relaxed">{skill.description}</p>
                  {selectedSkillContent !== null && (
                    <pre className="text-[9px] text-zinc-400 bg-zinc-900 rounded p-2 max-h-40 overflow-y-auto whitespace-pre-wrap">
                      {selectedSkillContent}
                    </pre>
                  )}
                  <button
                    onClick={() => void activateSkill(skill.name)}
                    disabled={skill.active || activatingSkillName === skill.name}
                    className="w-full h-7 rounded bg-blue-600 text-onaccent hover:bg-blue-500 text-[9px] font-bold flex items-center justify-center gap-1.5 disabled:opacity-40 transition-colors"
                  >
                    {activatingSkillName === skill.name ? (
                      <Loader className="w-3 h-3 animate-spin" />
                    ) : (
                      <Zap className="w-3 h-3" />
                    )}
                    {skill.active ? 'Already active' : 'Activate'}
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
