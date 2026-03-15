import { Fragment, useState } from 'react';
import type { ExecutionOrder } from '../../types';
import { TableSkeletonRows } from './TableSkeletonRows';
import { displaySymbol, failureCode, failureReason } from './formatters';

interface PlatformOrdersTableProps {
  bootstrapLoading: boolean;
  orders: ExecutionOrder[];
}

export function PlatformOrdersTable({ bootstrapLoading, orders }: PlatformOrdersTableProps) {
  const [expandedFailedOrderId, setExpandedFailedOrderId] = useState<number | null>(null);

  return (
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Run</th>
          <th>Symbol</th>
          <th>Side</th>
          <th>Mode</th>
          <th>TF ouverture</th>
          <th>Volume</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {bootstrapLoading ? (
          <TableSkeletonRows prefix="platform-orders" columns={9} rows={5} />
        ) : orders.length === 0 ? (
          <tr>
            <td colSpan={9}>Aucun ordre plateforme pour le moment.</td>
          </tr>
        ) : orders.map((order) => {
          const failed = String(order.status).toLowerCase() === 'failed';
          const expanded = expandedFailedOrderId === order.id;
          return (
            <Fragment key={order.id}>
              <tr>
                <td>{order.id}</td>
                <td>{order.run_id}</td>
                <td>{displaySymbol(order.symbol)}</td>
                <td>{order.side}</td>
                <td>{order.mode}</td>
                <td>{order.timeframe ?? '-'}</td>
                <td>{order.volume}</td>
                <td><span className={`badge ${order.status}`}>{order.status}</span></td>
                <td>
                  {failed ? (
                    <button
                      type="button"
                      onClick={() => setExpandedFailedOrderId((prev) => (prev === order.id ? null : order.id))}
                    >
                      {expanded ? 'Masquer erreur' : 'Voir erreur'}
                    </button>
                  ) : (
                    '-'
                  )}
                </td>
              </tr>
              {failed && expanded && (
                <tr>
                  <td colSpan={9}>
                    <p className="model-source">
                      Raison: <code>{failureReason(order)}</code> | Code: <code>{failureCode(order)}</code>
                    </p>
                    <pre>{JSON.stringify(order.response_payload ?? {}, null, 2)}</pre>
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}
