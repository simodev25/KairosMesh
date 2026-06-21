import clsx from 'clsx';

interface AgentChipProps {
  agent: string;
  selected: boolean;
  onClick: (agent: string) => void;
}

const AGENT_LABELS: Record<string, string> = {
  'technical-analyst': 'TECH',
  'news-analyst': 'NEWS',
  'market-context-analyst': 'CTX',
  'bullish-researcher': 'BULL',
  'bearish-researcher': 'BEAR',
  'trader-agent': 'TRADER',
  'risk-manager': 'RISK',
  'execution-manager': 'EXEC',
  'governance-trader': 'GOV',
};

export function AgentChip({ agent, selected, onClick }: AgentChipProps) {
  return (
    <button
      type="button"
      onClick={() => onClick(agent)}
      className={clsx(
        'px-2.5 py-1.5 rounded-md border text-[10px] tracking-[0.12em] font-semibold transition-colors',
        selected
          ? 'border-cyan-300 bg-cyan-500/15 text-cyan-300'
          : 'border-border text-text-muted hover:text-cyan-200 hover:border-cyan-500/40',
      )}
      aria-pressed={selected}
    >
      {AGENT_LABELS[agent] ?? agent.toUpperCase()}
    </button>
  );
}
