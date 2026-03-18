import { Fragment, useState } from 'react';
import type { ExecutionOrder } from '../../types';
import { TableSkeletonRows } from './TableSkeletonRows';
import { displaySymbol, failureCode, failureReason, formatExecutionDate, platformOrderTicket } from './formatters';

interface PlatformOrdersTableProps {
  bootstrapLoading: boolean;
  orders: ExecutionOrder[];
  pagedOrders: ExecutionOrder[];
  ordersPage: number;
  ordersTotalPages: number;
  ordersPerPage: number;
  onPreviousPage: () => void;
  onNextPage: () => void;
}

export function PlatformOrdersTable({
  bootstrapLoading,
  orders,
  pagedOrders,
  ordersPage,
  ordersTotalPages,
  ordersPerPage,
  onPreviousPage,
  onNextPage,
}: PlatformOrdersTableProps) {
  const [expandedFailedOrderId, setExpandedFailedOrderId] = useState<number | null>(null);
  const pageStart = orders.length === 0 ? 0 : (ordersPage - 1) * ordersPerPage + 1;
  const pageEnd = Math.min(orders.length, ordersPage * ordersPerPage);

  return (
    <>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Run</th>
            <th>Ticket</th>
            <th>Symbol</th>
            <th>Side</th>
            <th>Mode</th>
            <th>TF ouverture</th>
            <th>Date d&apos;exécution</th>
            <th>Volume</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {bootstrapLoading ? (
            <TableSkeletonRows prefix="platform-orders" columns={11} rows={5} />
          ) : orders.length === 0 ? (
            <tr>
              <td colSpan={11}>Aucun ordre plateforme pour le moment.</td>
            </tr>
          ) : pagedOrders.map((order) => {
            const failed = String(order.status).toLowerCase() === 'failed';
            const expanded = expandedFailedOrderId === order.id;
            return (
              <Fragment key={order.id}>
                <tr>
                  <td>{order.id}</td>
                  <td>{order.run_id}</td>
                  <td>{platformOrderTicket(order)}</td>
                  <td>{displaySymbol(order.symbol)}</td>
                  <td>{order.side}</td>
                  <td>{order.mode}</td>
                  <td>{order.timeframe ?? '-'}</td>
                  <td>{formatExecutionDate(order.created_at)}</td>
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
                    <td colSpan={11}>
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
      {orders.length > 0 && !bootstrapLoading && (
        <div className="table-pagination">
          <p className="table-pagination-meta">
            {pageStart}-{pageEnd} sur {orders.length}
          </p>
          <div className="table-pagination-actions">
            <button type="button" disabled={ordersPage <= 1} onClick={onPreviousPage}>
              Précédent
            </button>
            <span>
              Page {ordersPage} / {ordersTotalPages} ({ordersPerPage} par page)
            </span>
            <button type="button" disabled={ordersPage >= ordersTotalPages} onClick={onNextPage}>
              Suivant
            </button>
          </div>
        </div>
      )}
    </>
  );
}
