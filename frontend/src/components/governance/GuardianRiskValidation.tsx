interface RuleRow {
  label: string;
  value: string;
  status: 'ok' | 'warn' | 'error';
}

interface Props {
  portfolioState?: {
    open_risk_total_pct?: number;
    daily_drawdown_pct?: number;
    margin_used_pct?: number;
  } | null;
  limits?: {
    max_drawdown_pct?: number;
    max_open_risk_pct?: number;
    min_free_margin_pct?: number;
  } | null;
  newsImpactBufferEnabled?: boolean;
}

function StatusDot({ status }: { status: 'ok' | 'warn' | 'error' }) {
  const colorMap = { ok: 'bg-success', warn: 'bg-warning', error: 'bg-danger' };
  return <span className={`w-2 h-2 rounded-full ${colorMap[status]} shadow-sm`} />;
}

export function GuardianRiskValidation({ portfolioState, limits, newsImpactBufferEnabled = true }: Props) {
  const openRisk = portfolioState?.open_risk_total_pct ?? 0;
  const dailyDD = portfolioState?.daily_drawdown_pct ?? 0;
  const marginUsed = portfolioState?.margin_used_pct ?? 0;

  const maxDD = limits?.max_drawdown_pct ?? 5.0;
  const maxRisk = limits?.max_open_risk_pct ?? 10.0;
  const minMargin = limits?.min_free_margin_pct ?? 20.0;

  function ruleStatus(value: number, warn: number, error: number): 'ok' | 'warn' | 'error' {
    if (value >= error) return 'error';
    if (value >= warn) return 'warn';
    return 'ok';
  }

  const rows: RuleRow[] = [
    {
      label: 'MAX_DRAWDOWN_PROTECTION',
      value: `${maxDD.toFixed(1)}%`,
      status: ruleStatus(dailyDD, maxDD * 0.7, maxDD),
    },
    {
      label: 'OPEN_RISK_LIMIT',
      value: `${openRisk.toFixed(1)}% / ${maxRisk.toFixed(1)}%`,
      status: ruleStatus(openRisk, maxRisk * 0.8, maxRisk),
    },
    {
      label: 'MARGIN_BUFFER',
      value: `${(100 - marginUsed).toFixed(1)}% free`,
      status: ruleStatus(marginUsed, 100 - minMargin - 10, 100 - minMargin),
    },
    {
      label: 'NEWS_IMPACT_BUFFER',
      value: newsImpactBufferEnabled ? 'ENABLED' : 'DISABLED',
      status: newsImpactBufferEnabled ? 'ok' : 'warn',
    },
  ];

  return (
    <div className="hw-surface p-4 flex flex-col gap-3">
      <span className="section-title">GUARDIAN_RISK_VALIDATION</span>
      <div className="flex flex-col gap-2">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
            <span className="micro-label text-text-muted">{row.label}</span>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono text-text">{row.value}</span>
              <StatusDot status={row.status} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
