import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle, Clock, ExternalLink, Shield, ShieldAlert, TrendingUp, XCircle } from 'lucide-react';
import { wsGovernanceUrl } from '../../api/client';

// ── Types ────────────────────────────────────────────────────────────────────

interface GovernanceRun {
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
}

interface GovernanceMonitorPanelProps {
  token: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000/api/v1';

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
}

function urgencyColor(urgency: string | null): string {
  switch (urgency) {
    case 'critical': return 'text-red-400';
    case 'high': return 'text-orange-400';
    case 'medium': return 'text-yellow-400';
    default: return 'text-text-muted';
  }
}

function actionBadge(action: string | null): { label: string; cls: string } {
  switch (action) {
    case 'CLOSE': return { label: 'CLOSE', cls: 'bg-red-500/20 text-red-400 border-red-500/40' };
    case 'ADJUST_SL_TP': return { label: 'ADJ_SL_TP', cls: 'bg-blue-500/20 text-blue-400 border-blue-500/40' };
    case 'ADJUST_SL': return { label: 'ADJ_SL', cls: 'bg-blue-400/20 text-blue-300 border-blue-400/40' };
    case 'ADJUST_TP': return { label: 'ADJ_TP', cls: 'bg-indigo-400/20 text-indigo-300 border-indigo-400/40' };
    case 'HOLD': return { label: 'HOLD', cls: 'bg-surface-alt text-text-muted border-border' };
    default: return { label: action ?? '?', cls: 'bg-surface-alt text-text-muted border-border' };
  }
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '-';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '-';
  return d.toLocaleString('en-US', { dateStyle: 'short', timeStyle: 'medium' });
}

// ── Component ─────────────────────────────────────────────────────────────────

export function GovernanceMonitorPanel({ token }: GovernanceMonitorPanelProps) {
  const [runs, setRuns] = useState<GovernanceRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionStates, setActionStates] = useState<Record<number, 'approving' | 'rejecting' | null>>({});
  const [pendingCount, setPendingCount] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);
  const [forcing, setForcing] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // ── Fetch recommendations ────────────────────────────────────────────────

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BASE_URL}/governance/recommendations?limit=20`, {
        headers: authHeaders(token),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: GovernanceRun[] = await res.json();
      setRuns(data);
      setPendingCount(data.filter((r) => r.status === 'completed' && r.approval_status === 'pending').length);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [token]);

  // ── WebSocket ────────────────────────────────────────────────────────────

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      const wsToken = token;
      ws = new WebSocket(wsGovernanceUrl(wsToken));
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
      };
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string) as {
            type: string;
            pending_approval_count?: number;
          };
          if (msg.pending_approval_count !== undefined) {
            setPendingCount(msg.pending_approval_count);
          }
          // Re-fetch on governance_update to get fresh data
          if (msg.type === 'governance_update') {
            void fetchRuns();
          }
        } catch {
          // ignore parse errors
        }
      };
      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimer = setTimeout(connect, 5000);
      };
      ws.onerror = () => {
        ws.close();
      };
    }

    connect();
    void fetchRuns();

    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [token, fetchRuns]);

  // ── Approve / Reject ─────────────────────────────────────────────────────

  const approveRun = useCallback(async (id: number) => {
    setActionStates((prev) => ({ ...prev, [id]: 'approving' }));
    try {
      const res = await fetch(`${BASE_URL}/governance/${id}/approve`, {
        method: 'POST',
        headers: authHeaders(token),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      await fetchRuns();
    } catch (err) {
      setError(String(err));
    } finally {
      setActionStates((prev) => ({ ...prev, [id]: null }));
    }
  }, [token, fetchRuns]);

  const forceGovernance = useCallback(async () => {
    setForcing(true);
    setError(null);
    try {
      const res = await fetch(`${BASE_URL}/governance/force`, {
        method: 'POST',
        headers: authHeaders(token),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      setTimeout(() => void fetchRuns(), 2000);
    } catch (err) {
      setError(String(err));
    } finally {
      setForcing(false);
    }
  }, [token, fetchRuns]);

  const rejectRun = useCallback(async (id: number) => {
    setActionStates((prev) => ({ ...prev, [id]: 'rejecting' }));
    try {
      const res = await fetch(`${BASE_URL}/governance/${id}/reject`, {
        method: 'POST',
        headers: authHeaders(token),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      await fetchRuns();
    } catch (err) {
      setError(String(err));
    } finally {
      setActionStates((prev) => ({ ...prev, [id]: null }));
    }
  }, [token, fetchRuns]);

  // ── Render ───────────────────────────────────────────────────────────────

  const pendingRuns = runs.filter((r) => r.status === 'completed' && r.approval_status === 'pending' && r.action !== 'HOLD');
  const recentRuns = runs.slice(0, 15);

  return (
    <div className="space-y-3">
      {/* Header stats */}
      <div className="flex items-center gap-4 text-[10px] font-mono">
        <div className="flex items-center gap-1.5">
          <Shield className="w-3 h-3 text-accent" />
          <span className="text-text-muted">SUPERVISED_MODE</span>
        </div>
        <span className="text-border">|</span>
        <span className={`flex items-center gap-1 ${wsConnected ? 'text-green-400' : 'text-text-muted'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-green-400' : 'bg-text-muted'}`} />
          {wsConnected ? 'WS live' : 'WS offline'}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => void forceGovernance()}
            disabled={forcing || loading}
            title="Force immediate governance evaluation (bypasses cooldown)"
            className="text-[10px] font-mono text-yellow-400 border border-yellow-400/40 px-2 py-0.5 rounded hover:bg-yellow-400/10 disabled:opacity-40"
          >
            {forcing ? 'Forcing…' : 'Force'}
          </button>
          <button
            type="button"
            onClick={() => void fetchRuns()}
            disabled={loading}
            className="text-[10px] font-mono text-accent border border-accent/40 px-2 py-0.5 rounded hover:bg-accent/10 disabled:opacity-40"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-[10px] text-red-400">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          <span>{error}</span>
        </div>
      )}


      {/* History table */}
      {recentRuns.length === 0 && !loading && (
        <p className="text-[10px] text-text-muted">No governance evaluations yet. Positions will be monitored automatically when open.</p>
      )}

      {recentRuns.length > 0 && (
        <div className="space-y-1">
          <span className="text-[10px] font-semibold tracking-widest text-text-muted uppercase block">
            RECENT_EVALUATIONS
          </span>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px] font-mono border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">ID</th>
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">Ticket</th>
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">#Run</th>
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">Symbol</th>
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">Side</th>
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">Action</th>
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">Urgency</th>
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">Conv.</th>
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">Approval</th>
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">Exec.</th>
                  <th className="text-left py-1.5 pr-3 text-text-muted font-medium">Created</th>
                  <th className="text-left py-1.5 text-text-muted font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => {
                  const badge = actionBadge(run.action);
                  return (
                    <tr key={run.id} className="border-b border-border/40 hover:bg-surface-alt/30">
                      <td className="py-1.5 pr-3 text-text-muted">#{run.id}</td>
                      <td className="py-1.5 pr-3 font-mono text-text-muted text-[9px]">{run.position_ticket || '-'}</td>
                      <td className="py-1.5 pr-3 text-text-muted">{run.origin_run_id != null ? `#${run.origin_run_id}` : '-'}</td>
                      <td className="py-1.5 pr-3 text-text font-semibold">{run.symbol}</td>
                      <td className={`py-1.5 pr-3 ${run.side === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>{run.side}</td>
                      <td className="py-1.5 pr-3">
                        <span className={`border rounded px-1.5 py-0.5 ${badge.cls}`}>{badge.label ?? '-'}</span>
                      </td>
                      <td className={`py-1.5 pr-3 ${urgencyColor(run.urgency)}`}>{run.urgency ?? '-'}</td>
                      <td className="py-1.5 pr-3 text-text-muted">
                        {run.conviction != null ? `${(run.conviction * 100).toFixed(0)}%` : '-'}
                      </td>
                      <td className="py-1.5 pr-3">
                        <ApprovalBadge
                          status={run.approval_status}
                          action={run.action}
                          runId={run.id}
                          isCompleted={run.status === 'completed'}
                          isActing={actionStates[run.id] != null}
                          onApprove={() => void approveRun(run.id)}
                          onReject={() => void rejectRun(run.id)}
                        />
                      </td>
                      <td className="py-1.5 pr-3">
                        {run.executed ? (
                          <span className="text-green-400 flex items-center gap-1">
                            <TrendingUp className="w-2.5 h-2.5" />done
                          </span>
                        ) : run.execution_error ? (
                          <span className="text-red-400">err</span>
                        ) : (
                          <span className="text-text-muted">-</span>
                        )}
                      </td>
                      <td className="py-1.5 pr-3 text-text-muted">{formatDateTime(run.created_at)}</td>
                      <td className="py-1.5">
                        <Link
                          to={`/governance/${run.id}`}
                          className="flex items-center gap-1 text-[9px] text-accent hover:text-accent/80"
                        >
                          <ExternalLink className="w-2.5 h-2.5" />
                          detail
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── ApprovalBadge sub-component ───────────────────────────────────────────────

function ApprovalBadge({
  status,
  action,
  runId,
  isCompleted,
  isActing,
  onApprove,
  onReject,
}: {
  status: string;
  action: string | null;
  runId: number;
  isCompleted: boolean;
  isActing: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  if (status === 'approved') {
    return <span className="text-green-400 flex items-center gap-1"><CheckCircle className="w-2.5 h-2.5" />approved</span>;
  }
  if (status === 'rejected') {
    return <span className="text-red-400 flex items-center gap-1"><XCircle className="w-2.5 h-2.5" />rejected</span>;
  }
  if (action === 'HOLD' || action == null) {
    return <span className="text-text-muted">n/a</span>;
  }
  if (!isCompleted) {
    return <span className="text-text-muted flex items-center gap-1"><Clock className="w-2.5 h-2.5" />pending run</span>;
  }
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={onApprove}
        disabled={isActing}
        title={`Approve #${runId}`}
        className="text-green-400 hover:text-green-300 disabled:opacity-40"
      >
        <CheckCircle className="w-3 h-3" />
      </button>
      <button
        type="button"
        onClick={onReject}
        disabled={isActing}
        title={`Reject #${runId}`}
        className="text-red-400 hover:text-red-300 disabled:opacity-40"
      >
        <XCircle className="w-3 h-3" />
      </button>
    </div>
  );
}
