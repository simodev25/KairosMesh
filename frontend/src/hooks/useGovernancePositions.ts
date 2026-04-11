import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import { fetchGovernanceStream, type GovernancePosition, type GovernanceStreamItem } from '../api/governance';
import type { MetaApiPosition } from '../types';

function toStr(v: unknown): string {
  return String(v ?? '').trim();
}

function toNum(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function toNullableNum(v: unknown): number | null {
  const n = Number(v);
  return Number.isFinite(n) && n !== 0 ? n : null;
}

/** Map a raw MetaApiPosition to a GovernancePosition, attaching the latest governance run. */
function buildGovernancePositions(
  metaPositions: MetaApiPosition[],
  streamItems: GovernanceStreamItem[],
): GovernancePosition[] {
  // Keep the most-recent stream item per position_id
  const byPositionId = new Map<string, GovernanceStreamItem>();
  for (const item of streamItems) {
    const existing = byPositionId.get(item.position_id);
    if (!existing || item.created_at > existing.created_at) {
      byPositionId.set(item.position_id, item);
    }
  }

  return metaPositions.map((pos) => {
    const posId = toStr(pos.id ?? pos.ticket ?? pos.positionId);
    const streamItem = byPositionId.get(posId);
    const sl = toNullableNum(pos.stopLoss) ?? toNullableNum(pos.stopLossPrice) ?? toNullableNum(pos.sl);
    const tp = toNullableNum(pos.takeProfit) ?? toNullableNum(pos.takeProfitPrice) ?? toNullableNum(pos.tp);
    return {
      id: posId,
      symbol: toStr(pos.symbol),
      type: toStr(pos.type),
      openPrice: toNum(pos.openPrice),
      currentPrice: toNum(pos.currentPrice),
      stopLoss: sl,
      takeProfit: tp,
      unrealizedProfit: toNum(pos.profit),
      volume: toNum(pos.volume),
      time: toStr(pos.brokerTime ?? pos.time),
      latest_governance_run: streamItem
        ? {
            run_id: streamItem.run_id,
            status: streamItem.status,
            decision: streamItem.decision,
            created_at: streamItem.created_at,
          }
        : { run_id: null, status: null, decision: null, created_at: null },
    };
  });
}

export function useGovernancePositions(intervalMs = 10000) {
  const [positions, setPositions] = useState<GovernancePosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    try {
      const [rawResult, streamItems] = await Promise.all([
        api.listMetaApiPositions(token) as Promise<{
          positions?: MetaApiPosition[];
          degraded?: boolean;
          reason?: string;
        }>,
        fetchGovernanceStream().catch(() => [] as GovernanceStreamItem[]),
      ]);
      const metaPositions = Array.isArray(rawResult?.positions) ? rawResult.positions : [];
      setPositions(buildGovernancePositions(metaPositions, streamItems));
      setError(rawResult?.reason ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch positions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { positions, loading, error, refresh };
}
