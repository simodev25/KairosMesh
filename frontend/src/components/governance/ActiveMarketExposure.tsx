import { Settings, Zap, RefreshCw } from 'lucide-react';
import type { GovernancePosition } from '../../api/governance';
import { reevaluateAll, reevaluatePosition } from '../../api/governance';
import { useState } from 'react';

interface Props {
  positions: GovernancePosition[];
  autoGuardian: boolean;
  onAutoGuardianToggle: (v: boolean) => void;
  onRefresh: () => void;
}

function TypeBadge({ type }: { type: string }) {
  const isLong = type.toUpperCase().includes('BUY');
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-widest ${
      isLong ? 'bg-success/15 text-success border border-success/30' : 'bg-danger/15 text-danger border border-danger/30'
    }`}>
      {isLong ? 'LONG' : 'SHORT'}
    </span>
  );
}

function DecisionBadge({ decision }: { decision: GovernancePosition['latest_governance_run'] }) {
  if (!decision?.status) return <span className="micro-label text-text-dim">—</span>;
  if (decision.status === 'running' || decision.status === 'pending') {
    return <span className="micro-label text-accent animate-pulse">ANALYZING...</span>;
  }
  const action = decision.decision?.action;
  if (!action || action === 'HOLD') return null;
  const colorMap: Record<string, string> = {
    ADJUST_SL: 'text-warning', ADJUST_TP: 'text-warning', ADJUST_BOTH: 'text-warning',
    CLOSE: 'text-danger',
  };
  return <span className={`micro-label font-bold ${colorMap[action] ?? 'text-text'}`}>{action}</span>;
}

export function ActiveMarketExposure({ positions, autoGuardian, onAutoGuardianToggle, onRefresh }: Props) {
  const [reevaluating, setReevaluating] = useState(false);

  async function handleReevaluateAll() {
    setReevaluating(true);
    try {
      await reevaluateAll();
      onRefresh();
    } finally {
      setReevaluating(false);
    }
  }

  async function handleReevaluateOne(positionId: string) {
    try {
      await reevaluatePosition(positionId);
      onRefresh();
    } catch {
      // error is swallowed — position may already have an active run (409)
    }
  }

  return (
    <div className="hw-surface">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="section-title">ACTIVE_MARKET_EXPOSURE</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => void handleReevaluateAll()}
            disabled={reevaluating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-accent/30 bg-accent/10 text-accent text-[10px] font-bold tracking-widest hover:bg-accent/20 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${reevaluating ? 'animate-spin' : ''}`} />
            REEVALUATE_ALL
          </button>
          <div className="flex items-center gap-2">
            <span className="micro-label">AUTO_GUARDIAN:</span>
            <input
              type="checkbox"
              className="ui-switch"
              checked={autoGuardian}
              onChange={(e) => onAutoGuardianToggle(e.target.checked)}
            />
            <span className={`micro-label font-bold ${autoGuardian ? 'text-accent' : 'text-text-dim'}`}>
              {autoGuardian ? 'ENABLED' : 'DISABLED'}
            </span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-[11px] font-mono">
          <thead>
            <tr className="border-b border-border">
              {['ID', 'ASSET', 'TYPE', 'ENTRY / CURRENT', 'PNL', 'SL / TP', 'DECISION', 'ACTIONS'].map((h) => (
                <th key={h} className="px-4 py-2 text-left micro-label text-text-dim font-normal">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-text-dim micro-label">
                  NO_OPEN_POSITIONS
                </td>
              </tr>
            )}
            {positions.map((pos) => {
              const pnl = pos.unrealizedProfit ?? 0;
              const pnlPct = pos.openPrice ? ((pos.currentPrice - pos.openPrice) / pos.openPrice * 100) : 0;
              const pnlClass = pnl >= 0 ? 'text-success' : 'text-danger';
              return (
                <tr key={pos.id} className="border-b border-border/50 hover:bg-surface-alt/30 transition-colors">
                  <td className="px-4 py-3 text-accent font-bold">{pos.id.slice(0, 8)}</td>
                  <td className="px-4 py-3 text-text font-bold">{pos.symbol}</td>
                  <td className="px-4 py-3"><TypeBadge type={pos.type} /></td>
                  <td className="px-4 py-3">
                    <div className="text-text font-bold">{pos.openPrice.toLocaleString()}</div>
                    <div className="text-text-dim text-[10px]">{pos.currentPrice.toLocaleString()}</div>
                  </td>
                  <td className={`px-4 py-3 ${pnlClass}`}>
                    <div className="font-bold">{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}</div>
                    <div className="text-[10px] opacity-70">{pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%</div>
                  </td>
                  <td className="px-4 py-3 text-danger text-[10px]">
                    <div>SL: {pos.stopLoss?.toLocaleString() ?? '—'}</div>
                    <div>TP: {pos.takeProfit?.toLocaleString() ?? '—'}</div>
                  </td>
                  <td className="px-4 py-3">
                    <DecisionBadge decision={pos.latest_governance_run} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button className="w-7 h-7 rounded-lg border border-border bg-surface-raised flex items-center justify-center hover:bg-surface-alt transition-colors" title="Position settings">
                        <Settings className="w-3.5 h-3.5 text-text-dim" />
                      </button>
                      <button
                        onClick={() => void handleReevaluateOne(pos.id)}
                        className="w-7 h-7 rounded-lg border border-accent/30 bg-accent/10 flex items-center justify-center hover:bg-accent/20 transition-colors"
                        title="Reevaluate this position"
                      >
                        <Zap className="w-3.5 h-3.5 text-accent" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
