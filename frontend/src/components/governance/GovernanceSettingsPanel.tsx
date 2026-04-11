import { useState } from 'react';
import { Info } from 'lucide-react';
import type { GovernanceSettings } from '../../api/governance';

const DEPTH_INFO: Record<'light' | 'full', { agents: string; time: string; desc: string }> = {
  light: {
    agents: 'technical-analyst · news-analyst · market-context',
    time: '~30–60s',
    desc: 'Phase 1 only. Fast scan — recommended for continuous automated monitoring.',
  },
  full: {
    agents: '+ bullish-researcher · bearish-researcher · structured debate',
    time: '~2–4 min',
    desc: 'Phase 1 + Phase 2 debate. Bull/bear thesis before decision — best for manual deep analysis.',
  },
};

interface Props {
  settings: GovernanceSettings | null;
  saving: boolean;
  onUpdate: (patch: Partial<GovernanceSettings>) => void;
}

export function GovernanceSettingsPanel({ settings, saving, onUpdate }: Props) {
  const [depthTooltip, setDepthTooltip] = useState(false);
  if (!settings) return null;

  return (
    <div className="hw-surface p-4 flex flex-col gap-4">
      <span className="section-title">GOVERNANCE_CONFIG</span>

      {/* Analysis depth */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-1.5">
          <span className="micro-label text-text-dim">ANALYSIS_DEPTH</span>
          <div className="relative">
            <button
              type="button"
              onMouseEnter={() => setDepthTooltip(true)}
              onMouseLeave={() => setDepthTooltip(false)}
              className="w-4 h-4 flex items-center justify-center text-text-dim hover:text-text-muted transition-colors"
            >
              <Info className="w-3 h-3" />
            </button>
            {depthTooltip && (
              <div className="absolute left-0 bottom-full mb-2 z-50 w-72 p-3 rounded-xl bg-surface border border-border shadow-xl text-[10px] leading-relaxed">
                {(['light', 'full'] as const).map((d) => (
                  <div key={d} className={`mb-2 last:mb-0 ${d === settings.analysis_depth ? 'text-accent' : 'text-text-muted'}`}>
                    <div className="font-bold tracking-widest mb-0.5">{d.toUpperCase()} · {DEPTH_INFO[d].time}</div>
                    <div className="text-text-dim font-mono mb-0.5">{DEPTH_INFO[d].agents}</div>
                    <div>{DEPTH_INFO[d].desc}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {(['light', 'full'] as const).map((depth) => (
            <button
              key={depth}
              onClick={() => onUpdate({ analysis_depth: depth })}
              disabled={saving}
              className={`flex-1 py-1.5 rounded-lg text-[10px] font-bold tracking-widest border transition-colors ${
                settings.analysis_depth === depth
                  ? 'bg-accent/15 border-accent/40 text-accent'
                  : 'bg-surface-raised border-border text-text-dim hover:text-text'
              }`}
            >
              {depth.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="text-[9px] text-text-dim leading-relaxed px-0.5">
          {DEPTH_INFO[settings.analysis_depth].desc}
        </div>
      </div>

      {/* Execution mode */}
      <div className="flex flex-col gap-2">
        <span className="micro-label text-text-dim">EXECUTION_MODE</span>
        <div className="flex items-center gap-3 py-1">
          <span className={`text-[10px] font-bold tracking-widest ${settings.execution_mode === 'confirmation' ? 'text-accent' : 'text-text-dim'}`}>
            CONFIRMATION
          </span>
          <button
            onClick={() => onUpdate({
              execution_mode: settings.execution_mode === 'auto' ? 'confirmation' : 'auto',
            })}
            disabled={saving}
            className={`relative w-10 h-5 rounded-full overflow-hidden transition-colors ${settings.execution_mode === 'auto' ? 'bg-success' : 'bg-surface-raised border border-border'}`}
          >
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${settings.execution_mode === 'auto' ? 'translate-x-[22px]' : 'translate-x-0.5'}`} />
          </button>
          <span className={`text-[10px] font-bold tracking-widest ${settings.execution_mode === 'auto' ? 'text-success' : 'text-text-dim'}`}>
            AUTO
          </span>
        </div>
        {settings.execution_mode === 'auto' && (
          <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-warning/10 border border-warning/20">
            <span className="text-[10px] text-warning">⚠ Auto mode executes without confirmation</span>
          </div>
        )}
      </div>

      {/* Interval */}
      <div className="flex flex-col gap-2">
        <span className="micro-label text-text-dim">SCAN_INTERVAL (minutes)</span>
        <div className="flex gap-2">
          {[5, 15, 30, 60].map((mins) => (
            <button
              key={mins}
              onClick={() => onUpdate({ interval_minutes: mins })}
              disabled={saving}
              className={`flex-1 py-1.5 rounded-lg text-[10px] font-bold tracking-widest border transition-colors ${
                settings.interval_minutes === mins
                  ? 'bg-accent/15 border-accent/40 text-accent'
                  : 'bg-surface-raised border-border text-text-dim hover:text-text'
              }`}
            >
              {mins}m
            </button>
          ))}
        </div>
      </div>

      {saving && <span className="micro-label text-accent animate-pulse">SAVING...</span>}
    </div>
  );
}
