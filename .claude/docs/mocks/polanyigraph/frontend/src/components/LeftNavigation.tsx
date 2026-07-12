import { 
  Network, FileText, Cpu, Brain, Terminal, Activity, HelpCircle, Settings 
} from 'lucide-react';

export type PageType = 'workspace' | 'documents' | 'logic' | 'inference' | 'query';

interface LeftNavigationProps {
  activePage: PageType;
  onPageChange: (page: PageType) => void;
}

interface NavItem {
  id: PageType;
  label: string;
  subLabel: string;
  icon: typeof Network;
  accent: string;
}

const NAV_ITEMS: NavItem[] = [
  { 
    id: 'workspace', 
    label: 'Canvas', 
    subLabel: 'Visual KG', 
    icon: Network, 
    accent: 'text-blue-400 bg-blue-500/10 border-blue-500/20' 
  },
  { 
    id: 'documents', 
    label: 'Documents', 
    subLabel: 'Ingest Lab', 
    icon: FileText, 
    accent: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' 
  },
  { 
    id: 'logic', 
    label: 'Logic Lab', 
    subLabel: 'FIBO Schema', 
    icon: Cpu, 
    accent: 'text-sky-400 bg-sky-500/10 border-sky-500/20' 
  },
  { 
    id: 'inference', 
    label: 'Inference Lab', 
    subLabel: 'NS-Solver', 
    icon: Brain, 
    accent: 'text-amber-400 bg-amber-500/10 border-amber-400/20' 
  },
  { 
    id: 'query', 
    label: 'Query Lab', 
    subLabel: 'Datalog', 
    icon: Terminal, 
    accent: 'text-sky-400 bg-sky-500/10 border-sky-500/20' 
  },
];

export function LeftNavigation({ activePage, onPageChange }: LeftNavigationProps) {
  return (
    <div className="w-[72px] border-r border-zinc-800 bg-zinc-950 flex flex-col items-center py-4 justify-between shrink-0 z-30">
      
      {/* Primary Actions Group */}
      <div className="w-full flex flex-col items-center gap-4">
        
        {/* Navigation Actions */}
        <div className="w-full flex flex-col items-center gap-3">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isSelected = activePage === item.id;
            
            return (
              <button
                key={item.id}
                onClick={() => onPageChange(item.id)}
                className={`w-13 h-13 rounded-xl flex flex-col items-center justify-center relative group transition-all duration-200 select-none border ${
                  isSelected
                    ? `${item.accent} border border-blue-500/30 scale-102`
                    : 'border-transparent text-zinc-200 hover:text-white hover:bg-zinc-900/60 hover:scale-102'
                }`}
                title={`${item.label} - ${item.subLabel}`}
              >
                {/* Active indicator bar */}
                {isSelected && (
                  <span className="absolute left-0 top-3 bottom-3 w-[3px] bg-blue-500 rounded-r" />
                )}

                <Icon className={`w-5 h-5 ${isSelected ? '' : 'group-hover:scale-105 transition-transform'}`} />
                <span className="text-[8px] font-bold uppercase tracking-wider mt-1 scale-95 font-sans">
                  {item.label}
                </span>

                {/* Tooltip on hover */}
                <div className="absolute left-16 px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-800 text-[10px] text-zinc-300 font-medium font-sans opacity-0 pointer-events-none group-hover:opacity-100 group-hover:translate-x-1 transition-all duration-150 shadow-xl whitespace-nowrap z-50">
                  <div className="font-bold text-white">{item.label}</div>
                  <div className="text-[9px] text-zinc-500 mt-0.5">{item.subLabel}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* System Telemetry Accent Indicators */}
      <div className="flex flex-col items-center gap-4">
        <div className="h-[1px] w-8 bg-zinc-850" />
        
        {/* Pulse status indicator representing active system readiness */}
        <div className="flex flex-col items-center gap-1.5">
          <div className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </div>
          <span className="text-[8px] font-bold tracking-wider text-zinc-600 font-mono">SYS</span>
        </div>
      </div>

    </div>
  );
}
