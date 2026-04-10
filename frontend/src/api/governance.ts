const BASE = '/api/v1/governance';

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : {};
}

export interface GovernanceSettings {
  enabled: boolean;
  execution_mode: 'auto' | 'confirmation';
  analysis_depth: 'light' | 'full';
  interval_minutes: number;
  updated_at: string | null;
  updated_by: string | null;
}

export interface GovernanceDecision {
  action: 'HOLD' | 'ADJUST_SL' | 'ADJUST_TP' | 'ADJUST_BOTH' | 'CLOSE';
  new_sl: number | null;
  new_tp: number | null;
  reasoning: string;
  risk_score: number;
  confidence: number;
}

export interface GovernanceRunSummary {
  run_id: number | null;
  status: string | null;
  decision: GovernanceDecision | null;
  created_at: string | null;
}

export interface GovernancePosition {
  id: string;
  symbol: string;
  type: string;
  openPrice: number;
  currentPrice: number;
  stopLoss: number | null;
  takeProfit: number | null;
  unrealizedProfit: number;
  volume: number;
  time: string;
  latest_governance_run: GovernanceRunSummary;
}

export interface GovernanceStreamItem {
  run_id: number;
  position_id: string;
  symbol: string;
  status: string;
  decision: GovernanceDecision | null;
  created_at: string;
  updated_at: string;
  rejected: boolean;
}

export async function fetchGovernanceSettings(): Promise<GovernanceSettings> {
  const res = await fetch(`${BASE}/settings`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch governance settings: ${res.status}`);
  return res.json();
}

export async function updateGovernanceSettings(settings: Partial<GovernanceSettings>): Promise<GovernanceSettings> {
  const res = await fetch(`${BASE}/settings`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error(`Failed to update governance settings: ${res.status}`);
  return res.json();
}

export async function fetchGovernancePositions(): Promise<GovernancePosition[]> {
  const res = await fetch(`${BASE}/positions`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch governance positions: ${res.status}`);
  return res.json();
}

export async function fetchGovernanceStream(): Promise<GovernanceStreamItem[]> {
  const res = await fetch(`${BASE}/stream`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch governance stream: ${res.status}`);
  return res.json();
}

export async function reevaluateAll(): Promise<{ created_runs: number; run_ids: number[] }> {
  const res = await fetch(`${BASE}/reevaluate`, { method: 'POST', headers: authHeaders() });
  if (!res.ok) throw new Error(`Reevaluate failed: ${res.status}`);
  return res.json();
}

export async function reevaluatePosition(positionId: string): Promise<{ run_id: number }> {
  const res = await fetch(`${BASE}/reevaluate/${positionId}`, {
    method: 'POST', headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Reevaluate position failed: ${res.status}`);
  return res.json();
}

export async function approveGovernanceAction(runId: number): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/approve/${runId}`, { method: 'POST', headers: authHeaders() });
  if (!res.ok) throw new Error(`Approve failed: ${res.status}`);
  return res.json();
}

export async function rejectGovernanceAction(runId: number): Promise<void> {
  const res = await fetch(`${BASE}/reject/${runId}`, { method: 'POST', headers: authHeaders() });
  if (!res.ok) throw new Error(`Reject failed: ${res.status}`);
}
