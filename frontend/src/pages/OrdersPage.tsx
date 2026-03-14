import { Fragment, useEffect, useState } from 'react';
import { api } from '../api/client';
import { RealTradesCharts } from '../components/RealTradesCharts';
import { runtimeConfig } from '../config/runtime';
import { useAuth } from '../hooks/useAuth';
import type { ExecutionOrder, MetaApiAccount, MetaApiDeal, MetaApiHistoryOrder, MetaApiOpenOrder, MetaApiPosition } from '../types';

const REFRESH_DEBOUNCE_MS = 1200;
const DEALS_PER_PAGE = 10;

function resolveTicket(value: Record<string, unknown>): string {
  const raw = value.ticket ?? value.orderId ?? value.id ?? value.positionId ?? null;
  if (raw == null) return '-';
  const text = String(raw).trim();
  return text || '-';
}

function formatDaysWindowLabel(days: number): string {
  if (days === 0) return "Aujourd'hui";
  if (days === 1) return '1 jour';
  return `${days} jours`;
}

function asText(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function failureReason(order: ExecutionOrder): string {
  const payload = asRecord(order.response_payload);
  const result = asRecord(payload?.result);
  return (
    asText(order.error) ??
    asText(payload?.reason) ??
    asText(payload?.message) ??
    asText(payload?.error) ??
    asText(result?.reason) ??
    asText(result?.message) ??
    asText(result?.error) ??
    'Aucune raison explicite fournie'
  );
}

function failureCode(order: ExecutionOrder): string {
  const payload = asRecord(order.response_payload);
  const result = asRecord(payload?.result);
  const stringCode = asText(result?.stringCode) ?? asText(payload?.stringCode);
  const numericCode = typeof result?.numericCode === 'number'
    ? String(result.numericCode)
    : (typeof payload?.numericCode === 'number' ? String(payload.numericCode) : null);
  if (stringCode && numericCode) return `${stringCode} (${numericCode})`;
  return stringCode ?? numericCode ?? '-';
}

export function OrdersPage() {
  const { token } = useAuth();
  const [orders, setOrders] = useState<ExecutionOrder[]>([]);
  const [accounts, setAccounts] = useState<MetaApiAccount[]>([]);
  const [accountRef, setAccountRef] = useState<number | null>(null);
  const [days, setDays] = useState(runtimeConfig.metaApiRealTradesDefaultDays);
  const [deals, setDeals] = useState<MetaApiDeal[]>([]);
  const [historyOrders, setHistoryOrders] = useState<MetaApiHistoryOrder[]>([]);
  const [openPositions, setOpenPositions] = useState<MetaApiPosition[]>([]);
  const [openOrders, setOpenOrders] = useState<MetaApiOpenOrder[]>([]);
  const [provider, setProvider] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [openPositionsError, setOpenPositionsError] = useState<string | null>(null);
  const [openPositionsProvider, setOpenPositionsProvider] = useState('');
  const [openOrdersError, setOpenOrdersError] = useState<string | null>(null);
  const [openOrdersProvider, setOpenOrdersProvider] = useState('');
  const [metaLoading, setMetaLoading] = useState(false);
  const [lastManualRefreshMs, setLastManualRefreshMs] = useState(0);
  const [expandedFailedOrderId, setExpandedFailedOrderId] = useState<number | null>(null);
  const [dealsPage, setDealsPage] = useState(1);
  const [metaFeatureDisabled, setMetaFeatureDisabled] = useState(!runtimeConfig.enableMetaApiRealTradesDashboard);

  const dealsTotalPages = Math.max(1, Math.ceil(deals.length / DEALS_PER_PAGE));
  const dealsPageStart = (dealsPage - 1) * DEALS_PER_PAGE;
  const pagedDeals = deals.slice(dealsPageStart, dealsPageStart + DEALS_PER_PAGE);

  const loadMetaTrading = async (selectedRef: number | null, source: 'auto' | 'manual' = 'auto') => {
    if (!token) return;
    if (metaLoading) return;
    if (source === 'manual') {
      const now = Date.now();
      if (now - lastManualRefreshMs < REFRESH_DEBOUNCE_MS) return;
      setLastManualRefreshMs(now);
    }
    setMetaLoading(true);
    try {
      setMetaError(null);
      const [dealsPayload, historyPayload] = await Promise.all([
        api.listMetaApiDeals(token, { account_ref: selectedRef, days, limit: runtimeConfig.metaApiRealTradesOrdersPageLimit }),
        api.listMetaApiHistoryOrders(token, { account_ref: selectedRef, days, limit: runtimeConfig.metaApiRealTradesOrdersPageLimit }),
      ]);
      const dealsData = dealsPayload as {
        deals?: MetaApiDeal[];
        synchronizing?: boolean;
        provider?: string;
        reason?: string;
      };
      const historyData = historyPayload as {
        history_orders?: MetaApiHistoryOrder[];
        synchronizing?: boolean;
        provider?: string;
        reason?: string;
      };
      setDeals(Array.isArray(dealsData.deals) ? dealsData.deals : []);
      setHistoryOrders(Array.isArray(historyData.history_orders) ? historyData.history_orders : []);
      setProvider(typeof dealsData.provider === 'string' ? dealsData.provider : (typeof historyData.provider === 'string' ? historyData.provider : ''));
      setSyncing(Boolean(dealsData.synchronizing || historyData.synchronizing));
      if (dealsData.reason || historyData.reason) {
        const reason = (dealsData.reason ?? historyData.reason) as string;
        setMetaError(reason);
        setMetaFeatureDisabled(reason.includes('ENABLE_METAAPI_REAL_TRADES_DASHBOARD'));
      }
      const [openOrdersResult, openPositionsResult] = await Promise.allSettled([
        api.listMetaApiOpenOrders(token, { account_ref: selectedRef }),
        api.listMetaApiPositions(token, { account_ref: selectedRef }),
      ]);

      if (openOrdersResult.status === 'fulfilled') {
        const openOrdersPayload = openOrdersResult.value as {
          open_orders?: MetaApiOpenOrder[];
          provider?: string;
          reason?: string;
        };
        setOpenOrders(Array.isArray(openOrdersPayload.open_orders) ? openOrdersPayload.open_orders : []);
        setOpenOrdersProvider(typeof openOrdersPayload.provider === 'string' ? openOrdersPayload.provider : '');
        setOpenOrdersError(openOrdersPayload.reason ?? null);
      } else {
        const message = openOrdersResult.reason instanceof Error ? openOrdersResult.reason.message : 'Unable to load MetaApi open orders';
        setOpenOrders([]);
        setOpenOrdersProvider('');
        setOpenOrdersError(message);
      }

      if (openPositionsResult.status === 'fulfilled') {
        const openPositionsPayload = openPositionsResult.value as {
          positions?: MetaApiPosition[];
          provider?: string;
          reason?: string;
        };
        setOpenPositions(Array.isArray(openPositionsPayload.positions) ? openPositionsPayload.positions : []);
        setOpenPositionsProvider(typeof openPositionsPayload.provider === 'string' ? openPositionsPayload.provider : '');
        setOpenPositionsError(openPositionsPayload.reason ?? null);
      } else {
        const message = openPositionsResult.reason instanceof Error ? openPositionsResult.reason.message : 'Unable to load MetaApi open positions';
        setOpenPositions([]);
        setOpenPositionsProvider('');
        setOpenPositionsError(message);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load MetaApi trades';
      setDeals([]);
      setHistoryOrders([]);
      setOpenPositions([]);
      setOpenOrders([]);
      setProvider('');
      setOpenPositionsProvider('');
      setOpenOrdersProvider('');
      setSyncing(false);
      setMetaError(message);
      setOpenPositionsError(null);
      setOpenOrdersError(null);
      setMetaFeatureDisabled(message.includes('ENABLE_METAAPI_REAL_TRADES_DASHBOARD'));
    } finally {
      setMetaLoading(false);
    }
  };

  useEffect(() => {
    if (!token) return;
    const load = async () => {
      try {
        const [ordersData, accountsData] = await Promise.all([
          api.listOrders(token),
          api.listMetaApiAccounts(token),
        ]);
        const data = ordersData as ExecutionOrder[];
        const accountList = accountsData as MetaApiAccount[];
        setOrders(data);
        setAccounts(accountList);
        const defaultAccount = accountList.find((item) => item.is_default && item.enabled) ?? accountList.find((item) => item.enabled) ?? accountList[0];
        const nextRef = defaultAccount?.id ?? null;
        setAccountRef(nextRef);
        if (!metaFeatureDisabled) {
          await loadMetaTrading(nextRef);
        }
      } catch (err) {
        setPageError(err instanceof Error ? err.message : 'Unable to load orders');
      }
    };
    void load();
  }, [token, metaFeatureDisabled]);

  useEffect(() => {
    if (!token) return;
    if (metaFeatureDisabled) return;
    void loadMetaTrading(accountRef);
  }, [token, accountRef, days, metaFeatureDisabled]);

  useEffect(() => {
    setDealsPage(1);
  }, [accountRef, days]);

  useEffect(() => {
    if (dealsPage > dealsTotalPages) {
      setDealsPage(dealsTotalPages);
    }
  }, [dealsPage, dealsTotalPages]);

  if (pageError) return <p className="alert">{pageError}</p>;

  return (
    <div className="dashboard-grid">
      <section className="card">
        <h2>Trades réels MT5 (MetaApi)</h2>
        {metaFeatureDisabled ? (
          <>
            <p className="model-source">
              Vue désactivée côté UI. Activer <code>VITE_ENABLE_METAAPI_REAL_TRADES_DASHBOARD=true</code>.
            </p>
            {metaError && <p className="alert">{metaError}</p>}
          </>
        ) : (
          <>
            <form
              className="form-grid inline"
              onSubmit={(e) => {
                e.preventDefault();
                void loadMetaTrading(accountRef, 'manual');
              }}
            >
              <label>
                Compte
                <select value={accountRef ?? ''} onChange={(e) => setAccountRef(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">Default</option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.label} ({account.region}){account.is_default ? ' [default]' : ''}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Fenêtre
                <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
                  {runtimeConfig.metaApiRealTradesDaysOptions.map((daysOption) => (
                    <option key={daysOption} value={daysOption}>
                      {formatDaysWindowLabel(daysOption)}
                    </option>
                  ))}
                </select>
              </label>
              <button disabled={metaLoading}>{metaLoading ? 'Rafraîchir...' : 'Rafraîchir'}</button>
            </form>
            <p className="model-source">
              Provider: <code>{provider || 'unknown'}</code> | Sync in progress: <code>{syncing ? 'yes' : 'no'}</code>
            </p>
            {metaError && <p className="alert">{metaError}</p>}
            <h3>Ordres ouverts MT5 (MetaApi)</h3>
            <p className="model-source">
              Provider positions: <code>{openPositionsProvider || 'unknown'}</code>
            </p>
            {openPositionsError && <p className="alert">{openPositionsError}</p>}
            <table>
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>Type</th>
                  <th>Volume</th>
                  <th>Open Price</th>
                  <th>Current Price</th>
                  <th>PnL</th>
                </tr>
              </thead>
              <tbody>
                {openPositions.length === 0 ? (
                  <tr>
                    <td colSpan={8}>Aucun ordre ouvert sur le compte sélectionné.</td>
                  </tr>
                ) : (
                  openPositions.map((position, idx) => (
                    <tr key={`${resolveTicket(position as Record<string, unknown>)}-${idx}`}>
                      <td>{resolveTicket(position as Record<string, unknown>)}</td>
                      <td>{String(position.time ?? position.brokerTime ?? '-')}</td>
                      <td>{String(position.symbol ?? '-')}</td>
                      <td>{String(position.type ?? '-')}</td>
                      <td>{typeof position.volume === 'number' ? position.volume.toFixed(2) : '-'}</td>
                      <td>{typeof position.openPrice === 'number' ? position.openPrice.toFixed(5) : '-'}</td>
                      <td>{typeof position.currentPrice === 'number' ? position.currentPrice.toFixed(5) : '-'}</td>
                      <td>{typeof position.profit === 'number' ? position.profit.toFixed(2) : '-'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            <h3>Ordres en attente MT5 MetaApi</h3>
            <p className="model-source">
              Provider ordres: <code>{openOrdersProvider || 'unknown'}</code>
            </p>
            {openOrdersError && <p className="alert">{openOrdersError}</p>}
            <table>
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>Type</th>
                  <th>State</th>
                  <th>Volume</th>
                  <th>Open Price</th>
                  <th>Current Price</th>
                </tr>
              </thead>
              <tbody>
                {openOrders.length === 0 ? (
                  <tr>
                    <td colSpan={8}>Aucun ordre en attente sur le compte sélectionné.</td>
                  </tr>
                ) : (
                  openOrders.map((order, idx) => (
                    <tr key={`${resolveTicket(order as Record<string, unknown>)}-${idx}`}>
                      <td>{resolveTicket(order as Record<string, unknown>)}</td>
                      <td>{String(order.time ?? order.brokerTime ?? '-')}</td>
                      <td>{String(order.symbol ?? '-')}</td>
                      <td>{String(order.type ?? '-')}</td>
                      <td>{String(order.state ?? '-')}</td>
                      <td>{typeof order.volume === 'number' ? order.volume.toFixed(2) : (typeof order.currentVolume === 'number' ? order.currentVolume.toFixed(2) : '-')}</td>
                      <td>{typeof order.openPrice === 'number' ? order.openPrice.toFixed(5) : '-'}</td>
                      <td>{typeof order.currentPrice === 'number' ? order.currentPrice.toFixed(5) : '-'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            <RealTradesCharts deals={deals} historyOrders={historyOrders} />
            <h3>Deals exécutés</h3>
            <table>
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>Type</th>
                  <th>Volume</th>
                  <th>Price</th>
                  <th>PnL</th>
                </tr>
              </thead>
              <tbody>
                {deals.length === 0 ? (
                  <tr>
                    <td colSpan={7}>Aucun deal remonté sur la fenêtre sélectionnée.</td>
                  </tr>
                ) : (
                  pagedDeals.map((deal, idx) => (
                    <tr key={`${resolveTicket(deal as Record<string, unknown>)}-${idx}`}>
                      <td>{resolveTicket(deal as Record<string, unknown>)}</td>
                      <td>{String(deal.time ?? deal.brokerTime ?? '-')}</td>
                      <td>{String(deal.symbol ?? '-')}</td>
                      <td>{String(deal.type ?? deal.entryType ?? '-')}</td>
                      <td>{typeof deal.volume === 'number' ? deal.volume.toFixed(2) : '-'}</td>
                      <td>{typeof deal.price === 'number' ? deal.price.toFixed(5) : '-'}</td>
                      <td>{typeof deal.profit === 'number' ? deal.profit.toFixed(2) : '-'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            {deals.length > 0 && (
              <div className="form-grid inline">
                <button type="button" disabled={dealsPage <= 1} onClick={() => setDealsPage((prev) => Math.max(1, prev - 1))}>
                  Précédent
                </button>
                <span>
                  Page {dealsPage} / {dealsTotalPages} ({DEALS_PER_PAGE} par page)
                </span>
                <button type="button" disabled={dealsPage >= dealsTotalPages} onClick={() => setDealsPage((prev) => Math.min(dealsTotalPages, prev + 1))}>
                  Suivant
                </button>
              </div>
            )}
          </>
        )}
      </section>

      <section className="card">
        <h2>Ordres plateforme</h2>
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
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => {
              const failed = String(order.status).toLowerCase() === 'failed';
              const expanded = expandedFailedOrderId === order.id;
              return (
                <Fragment key={order.id}>
                  <tr>
                    <td>{order.id}</td>
                    <td>{order.run_id}</td>
                    <td>{order.symbol}</td>
                    <td>{order.side}</td>
                    <td>{order.mode}</td>
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
                      <td colSpan={8}>
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
      </section>
    </div>
  );
}
