import { request } from './client';

function token(): string | undefined {
  return localStorage.getItem('token') ?? undefined;
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

export function fetchGovernanceSettings(): Promise<GovernanceSettings> {
  return request<GovernanceSettings>('/governance/settings', {}, token());
}

export function updateGovernanceSettings(settings: Partial<GovernanceSettings>): Promise<GovernanceSettings> {
  return request<GovernanceSettings>('/governance/settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  }, token());
}

export function fetchGovernancePositions(): Promise<GovernancePosition[]> {
  return request<GovernancePosition[]>('/governance/positions', {}, token());
}

export function fetchGovernanceStream(): Promise<GovernanceStreamItem[]> {
  return request<GovernanceStreamItem[]>('/governance/stream', {}, token());
}

export function reevaluateAll(): Promise<{ created_runs: number; run_ids: number[] }> {
  return request<{ created_runs: number; run_ids: number[] }>('/governance/reevaluate', {
    method: 'POST',
  }, token());
}

export function reevaluatePosition(positionId: string): Promise<{ run_id: number }> {
  return request<{ run_id: number }>(`/governance/reevaluate/${positionId}`, {
    method: 'POST',
  }, token());
}

export function approveGovernanceAction(runId: number): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/governance/approve/${runId}`, {
    method: 'POST',
  }, token());
}

export function rejectGovernanceAction(runId: number): Promise<void> {
  return request<void>(`/governance/reject/${runId}`, {
    method: 'POST',
  }, token());
}
