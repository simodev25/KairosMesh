import type { EvolutionCampaign } from '../../types/evolution';

interface CampaignCardProps {
  campaign: EvolutionCampaign;
  selected: boolean;
  onSelect: (campaignId: number) => void;
}

const STATUS_CLASS: Record<string, string> = {
  pending: 'terminal-tag terminal-tag-blue',
  running: 'terminal-tag terminal-tag-blue',
  completed: 'terminal-tag terminal-tag-green',
  cancelled: 'terminal-tag terminal-tag-red',
  failed: 'terminal-tag terminal-tag-red',
  cancel_requested: 'terminal-tag terminal-tag-red',
};

export function CampaignCard({ campaign, selected, onSelect }: CampaignCardProps) {
  const progress = Math.min(
    100,
    Math.round((Number(campaign.consumed_iterations || 0) / Math.max(Number(campaign.max_iterations || 1), 1)) * 100),
  );

  return (
    <button
      type="button"
      onClick={() => onSelect(campaign.id)}
      className={`w-full text-left hw-surface p-4 transition-colors ${selected ? 'border-cyan-400/60' : 'hover:border-cyan-500/30'}`}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] font-bold text-text">{campaign.name}</div>
          <div className="text-[9px] text-text-dim">{campaign.agent_name}</div>
        </div>
        <span className={STATUS_CLASS[campaign.status] ?? 'terminal-tag terminal-tag-blue'}>{campaign.status.toUpperCase()}</span>
      </div>

      <div className="mt-3">
        <div className="micro-label">Progression</div>
        <div className="progress-track mt-1">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-[9px]">
        <div className="bg-surface-alt px-2 py-1 rounded border border-border">
          <div className="text-text-dim">Iter</div>
          <div className="text-text">{campaign.consumed_iterations}/{campaign.max_iterations}</div>
        </div>
        <div className="bg-surface-alt px-2 py-1 rounded border border-border">
          <div className="text-text-dim">Cand</div>
          <div className="text-text">{campaign.consumed_candidates}/{campaign.max_candidates}</div>
        </div>
        <div className="bg-surface-alt px-2 py-1 rounded border border-border">
          <div className="text-text-dim">Calls</div>
          <div className="text-text">{campaign.llm_calls_used}/{campaign.max_llm_calls}</div>
        </div>
      </div>
    </button>
  );
}
