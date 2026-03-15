import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ExecutionOrder } from '../types';

export function usePlatformOrders(token: string | null) {
  const [orders, setOrders] = useState<ExecutionOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setOrders([]);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;

    const loadOrders = async () => {
      setLoading(true);
      setError(null);
      try {
        const payload = await api.listOrders(token);
        if (cancelled) return;
        setOrders(Array.isArray(payload) ? payload as ExecutionOrder[] : []);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Unable to load orders');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadOrders();

    return () => {
      cancelled = true;
    };
  }, [token]);

  return {
    orders,
    loading,
    error,
  };
}
