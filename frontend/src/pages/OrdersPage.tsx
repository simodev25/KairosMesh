import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { ExecutionOrder } from '../types';

export function OrdersPage() {
  const { token } = useAuth();
  const [orders, setOrders] = useState<ExecutionOrder[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    const load = async () => {
      try {
        const data = (await api.listOrders(token)) as ExecutionOrder[];
        setOrders(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load orders');
      }
    };
    void load();
  }, [token]);

  if (error) return <p className="alert">{error}</p>;

  return (
    <section className="card">
      <h2>Positions et ordres</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Run</th>
            <th>Symbol</th>
            <th>Side</th>
            <th>Mode</th>
            <th>Volume</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.id}>
              <td>{order.id}</td>
              <td>{order.run_id}</td>
              <td>{order.symbol}</td>
              <td>{order.side}</td>
              <td>{order.mode}</td>
              <td>{order.volume}</td>
              <td><span className={`badge ${order.status}`}>{order.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
