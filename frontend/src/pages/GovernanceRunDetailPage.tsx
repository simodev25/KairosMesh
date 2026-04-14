import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  AlertTriangle, ArrowLeft, CheckCircle, Clock,
  Globe, Newspaper, LineChart, Shield, ShieldAlert, XCircle,
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';

// ── Types ────────────────────────────────────────────────────────────────────

interface GovernanceRunDetail {
  id: number;
  position_ticket: string;
  symbol: string;
  side: string;
  origin_run_id: number | null;
  status: string;
  action: string | null;
  new_sl: number | null;
  new_tp: number | null;
  conviction: number | null;
  urgency: string | null;
  reasoning: string | null;
  requires_approval: boolean;
  approval_status: string;
  approved_by: string | null;
  approved_at: string | null;
  executed: boolean;
  executed_at: string | null;
  execution_error: string | null;
  error: string | null;
  created_at: string | null;
  updated_at: string | null;
  trace: Record<string, unknown>;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function actionBadge(action: string | null): { label: string; cls: string } {
  switch (action) {
    case 'CLOSE':       return { label: 'CLOSE',      cls: 'bg-red-500/20 text-red-400 border-red-500/40' };
    case 'ADJUST_SL_TP': return { label: 'ADJ SL+TP', cls: 'bg-blue-500/20 text-blue-400 border-blue-500/40' };
    case 'ADJUST_SL':   return { label: 'ADJ SL',     cls: 'bg-blue-400/20 text-blue-300 border-blue-400/40' };
    case 'ADJUST_TP':   return { label: 'ADJ TP',     cls: 'bg-indigo-400/20 text-indigo-300 border-indigo-400/40' };
    case 'HOLD':        return { label: 'HOLD',        cls: 'bg-surface-alt text-text-muted border-border' };
    default:            return { label: action ?? '?', cls: 'bg-surface-alt text-text-muted border-border' };
  }
}

function urgencyColor(urgency: string | null): string {
  switch (urgency) {
    case 'critical': return 'text-red-400';
    case 'high':     return 'text-orange-400';
    case 'medium':   return 'text-yellow-400';
    default:         return 'text-text-muted';
  }
}

function fmt(iso: string | null | undefined): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '-' : d.toLocaleString('en-US', { dateStyle: 'short', timeStyle: 'medium' });
}

function agentLabel(name: string): { icon: React.ReactNode; title: string } {
  switch (name) {
    case 'technical-analyst':      return { icon: <LineChart className="w-3.5 h-3.5 text-accent" />, title: 'Technical Analyst' };
    case 'news-analyst':           return { icon: <Newspaper className="w-3.5 h-3.5 text-yellow-400" />, title: 'News Analyst' };
    case 'market-context-analyst': return { icon: <Globe className="w-3.5 h-3.5 text-teal-400" />, title: 'Market Context' };
    default:                       return { icon: <Shield className="w-3.5 h-3.5 text-text-muted" />, title: name };
  }
}

function Phase1Card({ name, data }: { name: string; data: Record<string, unknown> }) {
  const { icon, title } = agentLabel(name);
  const summary = (data.summary as string) || (data.text as string) || '';
  const sentiment = data.sentiment as string | undefined;
  const trend = data.trend as string | undefined;
  const degraded = Boolean(data.degraded);

  return (
    <div className="border border-border rounded p-3 space-y-2">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-[11px] font-semibold text-text">{title}</span>
        {degraded && (
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20 ml-auto">
            DEGRADED
          </span>
        )}
        {sentiment && !degraded && (
          <span className={`text-[9px] font-mono ml-auto ${sentiment === 'bullish' ? 'text-green-400' : sentiment === 'bearish' ? 'text-red-400' : 'text-text-muted'}`}>
            {sentiment}
          </span>
        )}
        {trend && !sentiment && !degraded && (
          <span className="text-[9px] font-mono ml-auto text-text-muted">{trend}</span>
        )}
      </div>
      {summary ? (
        <p className="text-[10px] text-text-muted leading-relaxed">{summary}</p>
      ) : (
        <p className="text-[10px] text-text-dim italic">No output available</p>
      )}
      {/* Key signals */}
      {Array.isArray(data.key_signals) && (data.key_signals as string[]).length > 0 && (
        <ul className="space-y-0.5 pl-2 border-l border-border">
          {(data.key_signals as string[]).slice(0, 4).map((s, i) => (
            <li key={i} className="text-[10px] text-text-muted">• {s}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function GovernanceRunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [run, setRun] = useState<GovernanceRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRawTrace, setShowRawTrace] = useState(false);

  useEffect(() => {
    if (!token || !id) return;
    void api.getGovernanceRecommendation(token, Number(id))
      .then((data) => setRun(data as GovernanceRunDetail))
      .catch((err: unknown) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [token, id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 text-text-muted text-[11px] font-mono">
        Loading governance run…
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="space-y-4 p-4">
        <Link to="/terminal" className="flex items-center gap-1.5 text-[10px] text-text-muted hover:text-text">
          <ArrowLeft className="w-3 h-3" /> Back to Terminal
        </Link>
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded text-[11px] text-red-400">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error || 'Governance run not found'}
        </div>
      </div>
    );
  }

  const badge = actionBadge(run.action);
  const phase1Raw = (run.trace?.phase1 as Record<string, Record<string, unknown>> | undefined) ?? {};
  const phase1Agents = ['technical-analyst', 'news-analyst', 'market-context-analyst'];

  return (
    <div className="space-y-4 max-w-4xl mx-auto">
      {/* Back nav */}
      <div className="flex items-center gap-3">
        <Link to="/terminal" className="flex items-center gap-1.5 text-[10px] text-text-muted hover:text-text">
          <ArrowLeft className="w-3 h-3" /> Terminal
        </Link>
        <span className="text-border">/</span>
        <span className="text-[10px] text-text-muted font-mono">Governance #{run.id}</span>
      </div>

      {/* Header card */}
      <div className="border border-border rounded p-4 space-y-3">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-teal-400" />
              <span className="text-base font-bold text-text">{run.symbol}</span>
              <span className={`text-sm font-semibold ${run.side === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>{run.side}</span>
              <span className={`text-[10px] font-mono border rounded px-2 py-0.5 ${badge.cls}`}>{badge.label}</span>
            </div>
            <div className="flex items-center gap-3 text-[10px] font-mono text-text-muted flex-wrap">
              <span>Ticket: <strong className="text-text">{run.position_ticket}</strong></span>
              {run.origin_run_id != null && (
                <Link to={`/runs/${run.origin_run_id}`} className="text-accent hover:underline">
                  Origin run #{run.origin_run_id}
                </Link>
              )}
              <span>Created: {fmt(run.created_at)}</span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span className={`text-[11px] font-semibold font-mono ${urgencyColor(run.urgency)}`}>
              urgency: {run.urgency ?? '-'}
            </span>
            <span className="text-[11px] font-mono text-text-muted">
              conviction: {run.conviction != null ? `${(run.conviction * 100).toFixed(0)}%` : '-'}
            </span>
          </div>
        </div>

        {/* SL / TP adjustments */}
        {(run.new_sl != null || run.new_tp != null) && (
          <div className="flex items-center gap-4 text-[10px] font-mono border-t border-border pt-3">
            {run.new_sl != null && (
              <span className="text-text-muted">New SL → <strong className="text-text">{run.new_sl.toFixed(5)}</strong></span>
            )}
            {run.new_tp != null && (
              <span className="text-text-muted">New TP → <strong className="text-text">{run.new_tp.toFixed(5)}</strong></span>
            )}
          </div>
        )}
      </div>

      {/* Phase 1 — parallel agents */}
      <div className="space-y-2">
        <span className="text-[10px] font-semibold tracking-widest text-text-muted uppercase block">
          PHASE_1 — MARKET_ANALYSIS (parallel)
        </span>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {phase1Agents.map((agentName) => (
            <Phase1Card
              key={agentName}
              name={agentName}
              data={phase1Raw[agentName] ?? {}}
            />
          ))}
        </div>
      </div>

      {/* Governance decision reasoning */}
      {run.reasoning && (
        <div className="space-y-2">
          <span className="text-[10px] font-semibold tracking-widest text-text-muted uppercase block">
            GOVERNANCE_TRADER — DECISION_REASONING
          </span>
          <div className="border border-teal-500/30 bg-teal-500/5 rounded p-3">
            <p className="text-[11px] text-text-muted leading-relaxed whitespace-pre-wrap">{run.reasoning}</p>
          </div>
        </div>
      )}

      {/* Approval & execution */}
      <div className="space-y-2">
        <span className="text-[10px] font-semibold tracking-widest text-text-muted uppercase block">
          APPROVAL_&_EXECUTION
        </span>
        <div className="border border-border rounded p-3 grid grid-cols-2 md:grid-cols-4 gap-4 text-[10px] font-mono">
          <div>
            <span className="text-text-muted block mb-0.5">Approval</span>
            {run.approval_status === 'approved' ? (
              <span className="flex items-center gap-1 text-green-400"><CheckCircle className="w-3 h-3" />approved</span>
            ) : run.approval_status === 'rejected' ? (
              <span className="flex items-center gap-1 text-red-400"><XCircle className="w-3 h-3" />rejected</span>
            ) : (
              <span className="flex items-center gap-1 text-yellow-400"><Clock className="w-3 h-3" />{run.approval_status}</span>
            )}
          </div>
          <div>
            <span className="text-text-muted block mb-0.5">Approved by</span>
            <span className="text-text">{run.approved_by ?? '-'}</span>
          </div>
          <div>
            <span className="text-text-muted block mb-0.5">Approved at</span>
            <span className="text-text">{fmt(run.approved_at)}</span>
          </div>
          <div>
            <span className="text-text-muted block mb-0.5">Executed</span>
            {run.executed ? (
              <span className="flex items-center gap-1 text-green-400"><CheckCircle className="w-3 h-3" />{fmt(run.executed_at)}</span>
            ) : run.execution_error ? (
              <span className="text-red-400" title={run.execution_error}>error</span>
            ) : (
              <span className="text-text-muted">-</span>
            )}
          </div>
        </div>
        {run.execution_error && (
          <div className="flex items-start gap-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-[10px] text-red-400">
            <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
            {run.execution_error}
          </div>
        )}
      </div>

      {/* Raw trace (collapsible) */}
      <div className="space-y-1">
        <button
          type="button"
          onClick={() => setShowRawTrace((v) => !v)}
          className="text-[10px] font-mono text-text-muted hover:text-text border border-border rounded px-2 py-1"
        >
          {showRawTrace ? 'Hide' : 'Show'} raw trace
        </button>
        {showRawTrace && (
          <pre className="text-[9px] font-mono text-text-muted bg-surface-alt rounded p-3 overflow-x-auto max-h-96 overflow-y-auto border border-border">
            {JSON.stringify(run.trace, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
