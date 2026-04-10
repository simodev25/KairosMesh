import { useState, useEffect, useCallback } from 'react';
import { fetchGovernancePositions, type GovernancePosition } from '../api/governance';

export function useGovernancePositions(intervalMs = 10000) {
  const [positions, setPositions] = useState<GovernancePosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchGovernancePositions();
      setPositions(data);
      setError(null);
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
