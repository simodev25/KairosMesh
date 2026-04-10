import { Target, TrendingUp, ShieldCheck, BarChart2 } from 'lucide-react';
import type { GovernancePosition } from '../../api/governance';

interface Props {
  positions: GovernancePosition[];
  portfolioState?: {
    equity?: number;
    margin_used_pct?: number;
    open_risk_total_pct?: number;
  } | null;
}

function KPICard({
  label, value, icon: Icon, valueClass = '',
}: { label: string; value: string; icon: React.ElementType; valueClass?: string }) {
  return (
    <div className="hw-surface flex-1 min-w-0 p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="micro-label">{label}</span>
        <Icon className="w-4 h-4 text-text-dim" />
      </div>
      <span className={`text-2xl font-bold font-mono tracking-tight ${valueClass}`}>
        {value}
      </span>
    </div>
  );
}

export function GovernanceKPIs({ positions, portfolioState }: Props) {
  const activeCount = positions.length;

  const totalPnl = positions.reduce((sum, p) => sum + (p.unrealizedProfit ?? 0), 0);
  const pnlStr = totalPnl >= 0 ? `+$${totalPnl.toFixed(2)}` : `-$${Math.abs(totalPnl).toFixed(2)}`;
  const pnlClass = totalPnl >= 0 ? 'text-success' : 'text-danger';

  const runsWithDecision = positions
    .map((p) => p.latest_governance_run?.decision?.risk_score)
    .filter((s): s is number => typeof s === 'number');
  const avgRiskScore = runsWithDecision.length
    ? runsWithDecision.reduce((a, b) => a + b, 0) / runsWithDecision.length
    : 0;
  const riskClass = avgRiskScore < 0.4 ? 'text-success' : avgRiskScore < 0.7 ? 'text-warning' : 'text-danger';

  const marginUsage = portfolioState?.margin_used_pct ?? 0;
  const marginClass = marginUsage < 50 ? 'text-success' : marginUsage < 80 ? 'text-warning' : 'text-danger';

  return (
    <div className="flex gap-3">
      <KPICard label="ACTIVE_POSITIONS" value={String(activeCount)} icon={Target} />
      <KPICard label="TOTAL_FLOATING_PNL" value={pnlStr} icon={TrendingUp} valueClass={pnlClass} />
      <KPICard
        label="GUARDIAN_RISK_SCORE"
        value={avgRiskScore.toFixed(2)}
        icon={ShieldCheck}
        valueClass={riskClass}
      />
      <KPICard
        label="LIVE_MARGIN_USAGE"
        value={`${marginUsage.toFixed(1)}%`}
        icon={BarChart2}
        valueClass={marginClass}
      />
    </div>
  );
}
