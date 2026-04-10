import { CheckCircle, XCircle, Info, Clock, RefreshCw } from 'lucide-react';
import type { GovernanceStreamItem } from '../../api/governance';
import { approveGovernanceAction, rejectGovernanceAction } from '../../api/governance';
import { useState } from 'react';

interface Props {
  items: GovernanceStreamItem[];
  executionMode: 'auto' | 'confirmation';
  onRefresh: () => void;
}

function statusConfig(item: GovernanceStreamItem): { label: string; className: string; icon: React.ElementType } {
  if (item.rejected) return { label: 'REJECTED', className: 'text-text-dim border-border/50', icon: XCircle };
  if (item.status === 'failed') return { label: 'FAILED', className: 'text-danger border-danger/30', icon: XCircle };
  if (item.status === 'completed') {
    const action = item.decision?.action;
    if (!action || action === 'HOLD') return { label: 'HOLD', className: 'text-text-dim border-border/50', icon: Info };
    return { label: 'APPROVED', className: 'text-accent border-accent/30', icon: CheckCircle };
  }
  if (item.status === 'pending' || item.status === 'running') {
    return { label: 'ANALYZING', className: 'text-warning border-warning/30', icon: Clock };
  }
  return { label: item.status.toUpperCase(), className: 'text-text-dim border-border/50', icon: Info };
}

function isPending(item: GovernanceStreamItem): boolean {
  return item.status === 'completed' && !item.rejected && (item.decision?.action ?? 'HOLD') !== 'HOLD';
}

export function GovernanceDecisionStream({ items, executionMode, onRefresh }: Props) {
  const [actioning, setActioning] = useState<number | null>(null);

  async function handleApprove(runId: number) {
    setActioning(runId);
    try {
      await approveGovernanceAction(runId);
      onRefresh();
    } finally {
      setActioning(null);
    }
  }

  async function handleReject(runId: number) {
    setActioning(runId);
    try {
      await rejectGovernanceAction(runId);
      onRefresh();
    } finally {
      setActioning(null);
    }
  }

  return (
    <div className="hw-surface flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="section-title">GUARDIAN_DECISION_STREAM</span>
        <button
          onClick={onRefresh}
          className="w-6 h-6 flex items-center justify-center text-text-dim hover:text-text transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {items.length === 0 && (
          <div className="px-4 py-8 text-center micro-label text-text-dim">
            AWAITING_DECISIONS
          </div>
        )}
        {items.map((item) => {
          const cfg = statusConfig(item);
          const showActions = executionMode === 'confirmation' && isPending(item);
          const action = item.decision?.action ?? 'HOLD';
          const riskScore = item.decision?.risk_score ?? 0;
          const riskClass = riskScore < 0.4 ? 'text-success' : riskScore < 0.7 ? 'text-warning' : 'text-danger';

          return (
            <div
              key={item.run_id}
              className="px-4 py-3 border-b border-border/50 last:border-0 flex flex-col gap-1.5"
            >
              {/* Header row */}
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] text-text-dim font-mono">
                  {new Date(item.updated_at).toLocaleTimeString()}
                </span>
                <span className={`text-[9px] font-bold tracking-widest border px-1.5 py-0.5 rounded ${cfg.className}`}>
                  {cfg.label}
                </span>
              </div>

              {/* Decision */}
              <div className="flex flex-col gap-0.5">
                <span className="text-[11px] font-bold text-text font-mono">{action}</span>
                <span className="text-[10px] text-text-dim">
                  {item.symbol} — {item.decision?.reasoning?.slice(0, 80) ?? ''}
                  {(item.decision?.reasoning?.length ?? 0) > 80 ? '...' : ''}
                </span>
                {item.decision?.new_sl && (
                  <span className="text-[10px] text-danger font-mono">
                    SL → {item.decision.new_sl.toLocaleString()}
                    {item.decision.new_tp ? ` | TP → ${item.decision.new_tp.toLocaleString()}` : ''}
                  </span>
                )}
              </div>

              {/* Risk score */}
              <div className="flex items-center gap-1.5">
                <span className="micro-label text-text-dim">RISK_SCORE</span>
                <span className={`text-[11px] font-bold font-mono ${riskClass}`}>
                  {riskScore.toFixed(2)}
                </span>
              </div>

              {/* Approve / Reject buttons for confirmation mode */}
              {showActions && (
                <div className="flex gap-2 mt-1">
                  <button
                    onClick={() => handleApprove(item.run_id)}
                    disabled={actioning === item.run_id}
                    className="flex-1 py-1 rounded-lg bg-success/15 border border-success/30 text-success text-[10px] font-bold tracking-widest hover:bg-success/25 transition-colors disabled:opacity-50"
                  >
                    {actioning === item.run_id ? '...' : 'APPROVE'}
                  </button>
                  <button
                    onClick={() => handleReject(item.run_id)}
                    disabled={actioning === item.run_id}
                    className="flex-1 py-1 rounded-lg bg-danger/15 border border-danger/30 text-danger text-[10px] font-bold tracking-widest hover:bg-danger/25 transition-colors disabled:opacity-50"
                  >
                    {actioning === item.run_id ? '...' : 'REJECT'}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
