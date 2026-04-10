import { useState, useEffect, useCallback } from 'react';
import { fetchGovernanceStream, type GovernanceStreamItem } from '../api/governance';

export function useGovernanceStream(intervalMs = 5000) {
  const [items, setItems] = useState<GovernanceStreamItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchGovernanceStream();
      setItems(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch stream');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { items, loading, error, refresh };
}
