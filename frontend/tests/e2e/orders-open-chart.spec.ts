import { expect, test, type Page } from '@playwright/test';

interface MockTradingData {
  openOrders: Array<Record<string, unknown>>;
  positions: Array<Record<string, unknown>>;
  marketCandlesDelayMs?: number;
}

function asJson(body: unknown) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  };
}

async function mockOrdersApi(page: Page, data: MockTradingData) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token');
  });

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path.endsWith('/auth/me')) {
      return route.fulfill(asJson({
        id: 1,
        email: 'admin@local.dev',
        role: 'admin',
        is_active: true,
      }));
    }

    if (path.endsWith('/trading/orders')) {
      return route.fulfill(asJson([
        {
          id: 101,
          run_id: 77,
          timeframe: 'H1',
          mode: 'paper',
          side: 'BUY',
          symbol: 'EURUSD',
          volume: 0.2,
          status: 'submitted',
          request_payload: {},
          response_payload: {},
          error: null,
          created_at: '2026-03-14T10:00:00Z',
        },
      ]));
    }

    if (path.endsWith('/trading/accounts')) {
      return route.fulfill(asJson([
        {
          id: 11,
          label: 'Demo Account',
          account_id: 'acc-001',
          region: 'new-york',
          enabled: true,
          is_default: true,
          created_at: '2026-03-10T10:00:00Z',
          updated_at: '2026-03-10T10:00:00Z',
        },
      ]));
    }

    if (path.endsWith('/trading/deals')) {
      return route.fulfill(asJson({
        deals: [],
        synchronizing: false,
        provider: 'metaapi',
      }));
    }

    if (path.endsWith('/trading/history-orders')) {
      return route.fulfill(asJson({
        history_orders: [],
        synchronizing: false,
        provider: 'metaapi',
      }));
    }

    if (path.endsWith('/trading/open-orders')) {
      return route.fulfill(asJson({
        open_orders: data.openOrders,
        provider: 'metaapi',
      }));
    }

    if (path.endsWith('/trading/positions')) {
      return route.fulfill(asJson({
        positions: data.positions,
        provider: 'metaapi',
      }));
    }

    if (path.endsWith('/trading/market-candles')) {
      if (typeof data.marketCandlesDelayMs === 'number' && data.marketCandlesDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, data.marketCandlesDelayMs));
      }
      return route.fulfill(asJson({
        pair: 'EURUSD',
        timeframe: 'H1',
        provider: 'sdk',
        candles: [
          { time: '2026-03-14T08:00:00Z', open: 1.088, high: 1.09, low: 1.087, close: 1.089, volume: 1000 },
          { time: '2026-03-14T09:00:00Z', open: 1.089, high: 1.093, low: 1.088, close: 1.092, volume: 1200 },
          { time: '2026-03-14T10:00:00Z', open: 1.092, high: 1.095, low: 1.091, close: 1.094, volume: 1100 },
        ],
      }));
    }

    return route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ error: `Unhandled route in test: ${path}` }),
    });
  });
}

function ordersChartSection(page: Page) {
  return page.locator('#orders-chart');
}

test('orders page displays TradingView chart when prices are available', async ({ page }) => {
  test.setTimeout(60000);
  await mockOrdersApi(page, {
    positions: [
      {
        ticket: '4001',
        symbol: 'EURUSD',
        type: 'POSITION_TYPE_BUY',
        time: '2026-03-14T09:00:00Z',
        volume: 0.2,
        openPrice: 1.089,
        currentPrice: 1.094,
        stopLoss: 1.08123,
        takeProfit: 1.10456,
        profit: 23.4,
      },
    ],
    openOrders: [
      {
        ticket: '5001',
        symbol: 'EURUSD',
        type: 'ORDER_TYPE_BUY_LIMIT',
        state: 'ORDER_STATE_PLACED',
        time: '2026-03-14T09:30:00Z',
        volume: 0.1,
        openPrice: 1.087,
        currentPrice: 1.091,
      },
    ],
  });

  await page.goto('/orders');

  const chartSection = ordersChartSection(page);
  await expect(chartSection.getByText('LIVE_CHART')).toBeVisible();
  await expect(chartSection.getByLabel('TradingView chart for open orders')).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('columnheader', { name: 'S/L' })).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'T/P' })).toBeVisible();
  await expect(page.getByRole('cell', { name: '1.08123' })).toBeVisible();
  await expect(page.getByRole('cell', { name: '1.10456' })).toBeVisible();
});

test('orders page shows skeleton while market candles are loading', async ({ page }) => {
  test.setTimeout(60000);
  await mockOrdersApi(page, {
    positions: [
      {
        ticket: '7777',
        symbol: 'EURUSD',
        type: 'POSITION_TYPE_BUY',
        time: '2026-03-14T09:00:00Z',
        volume: 0.2,
        openPrice: 1.089,
        currentPrice: 1.094,
        profit: 23.4,
      },
    ],
    openOrders: [],
    marketCandlesDelayMs: 1200,
  });

  await page.goto('/orders');

  const chartSection = ordersChartSection(page);
  await expect(chartSection.getByText('LIVE_CHART')).toBeVisible();
  // Chart skeleton renders as a pulsing placeholder inside the chart section
  await expect(chartSection.getByRole('status')).toBeVisible({ timeout: 10000 });
});

test('orders page allows changing chart timeframe', async ({ page }) => {
  await mockOrdersApi(page, {
    positions: [
      {
        ticket: '4101',
        symbol: 'EURUSD',
        type: 'POSITION_TYPE_BUY',
        time: '2026-03-14T09:00:00Z',
        volume: 0.2,
        openPrice: 1.089,
        currentPrice: 1.094,
        profit: 23.4,
      },
    ],
    openOrders: [],
  });

  const requestedTimeframes: string[] = [];
  page.on('request', (request) => {
    const url = request.url();
    if (!url.includes('/api/v1/trading/market-candles')) return;
    const value = new URL(url).searchParams.get('timeframe');
    if (value) requestedTimeframes.push(value);
  });

  await page.goto('/orders');

  const chartSection = ordersChartSection(page);
  const timeframeGroup = chartSection.getByRole('group', { name: 'Chart timeframe' });
  await expect(timeframeGroup).toBeVisible();
  // Chart header shows symbol and timeframe — check the timeframe section
  await expect(chartSection.getByText('H1').first()).toBeVisible({ timeout: 10000 });

  await timeframeGroup.getByRole('button', { name: 'M15' }).click();

  // After selecting M15, the chart should display M15 timeframe
  await expect(chartSection.getByText('M15').first()).toBeVisible({ timeout: 10000 });
  await expect.poll(() => requestedTimeframes.includes('M15')).toBeTruthy();
});

test('orders page allows selecting a ticket from Ordres ouverts MT5', async ({ page }) => {
  test.setTimeout(60000);
  await mockOrdersApi(page, {
    positions: [
      {
        ticket: '4001',
        symbol: 'EURUSD',
        type: 'POSITION_TYPE_BUY',
        time: '2026-03-14T09:00:00Z',
        volume: 0.2,
        openPrice: 1.089,
        currentPrice: 1.094,
        profit: 23.4,
      },
      {
        ticket: '4002',
        symbol: 'GBPUSD',
        type: 'POSITION_TYPE_SELL',
        time: '2026-03-14T09:15:00Z',
        volume: 0.3,
        openPrice: 1.281,
        currentPrice: 1.279,
        profit: 12.1,
      },
    ],
    openOrders: [
      {
        ticket: '5001',
        symbol: 'EURUSD',
        type: 'ORDER_TYPE_BUY_LIMIT',
        state: 'ORDER_STATE_PLACED',
        time: '2026-03-14T09:30:00Z',
        volume: 0.1,
        openPrice: 1.087,
        currentPrice: 1.091,
      },
    ],
  });

  await page.goto('/orders');

  const chartSection = ordersChartSection(page);

  await expect(chartSection.getByTestId('open-orders-chart-filter')).toContainText('All orders');

  // Click "Show ticket 4001 on chart" button in the positions table
  const showBtn = page.getByRole('button', { name: 'Show ticket 4001 on chart' });
  await expect(showBtn).toBeVisible({ timeout: 10000 });
  await showBtn.click();
  await expect(chartSection.getByTestId('open-orders-chart-filter')).toContainText('4001');

  // Click again to reset
  await showBtn.click();
  await expect(chartSection.getByTestId('open-orders-chart-filter')).toContainText('All orders');
});

test('orders page keeps symbol curve when open orders have no price points', async ({ page }) => {
  test.setTimeout(60000);
  await mockOrdersApi(page, {
    positions: [
      {
        ticket: '9001',
        symbol: 'EURUSD',
        type: 'POSITION_TYPE_BUY',
        time: '2026-03-14T07:00:00Z',
        volume: 0.1,
      },
    ],
    openOrders: [
      {
        ticket: '9002',
        symbol: 'EURUSD',
        type: 'ORDER_TYPE_SELL_LIMIT',
        state: 'ORDER_STATE_PLACED',
        time: '2026-03-14T07:30:00Z',
        volume: 0.1,
      },
    ],
  });

  await page.goto('/orders');

  const chartSection = ordersChartSection(page);
  await expect(chartSection.getByText('LIVE_CHART')).toBeVisible();
  await expect(chartSection.getByLabel('TradingView chart for open orders')).toBeVisible({ timeout: 15000 });
});

test('orders page loads positions/open orders with selected account ref only', async ({ page }) => {
  test.setTimeout(60000);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token');
  });

  let openOrdersWithoutAccountRefCalls = 0;
  let positionsWithoutAccountRefCalls = 0;

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path.endsWith('/auth/me')) {
      return route.fulfill(asJson({
        id: 1,
        email: 'admin@local.dev',
        role: 'admin',
        is_active: true,
      }));
    }

    if (path.endsWith('/trading/orders')) {
      return route.fulfill(asJson([]));
    }

    if (path.endsWith('/trading/accounts')) {
      return route.fulfill(asJson([
        {
          id: 11,
          label: 'Demo Account',
          account_id: 'acc-001',
          region: 'new-york',
          enabled: true,
          is_default: true,
          created_at: '2026-03-10T10:00:00Z',
          updated_at: '2026-03-10T10:00:00Z',
        },
      ]));
    }

    if (path.endsWith('/trading/deals')) {
      return route.fulfill(asJson({
        deals: [],
        synchronizing: false,
        provider: 'metaapi',
      }));
    }

    if (path.endsWith('/trading/history-orders')) {
      return route.fulfill(asJson({
        history_orders: [],
        synchronizing: false,
        provider: 'metaapi',
      }));
    }

    if (path.endsWith('/trading/open-orders')) {
      if (!url.searchParams.get('account_ref')) {
        openOrdersWithoutAccountRefCalls += 1;
        return route.fulfill(asJson({
          open_orders: [],
          provider: 'unknown',
        }));
      }
      return route.fulfill(asJson({
        open_orders: [],
        provider: 'metaapi',
      }));
    }

    if (path.endsWith('/trading/positions')) {
      if (!url.searchParams.get('account_ref')) {
        positionsWithoutAccountRefCalls += 1;
        return route.fulfill(asJson({
          positions: [],
          provider: 'unknown',
        }));
      }
      return route.fulfill(asJson({
        positions: [],
        provider: 'metaapi',
      }));
    }

    return route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ error: `Unhandled route in test: ${path}` }),
    });
  });

  await page.goto('/orders');

  const chartSection = ordersChartSection(page);
  await expect(chartSection.getByText('LIVE_CHART')).toBeVisible({ timeout: 15000 });
  expect(openOrdersWithoutAccountRefCalls).toBe(0);
  expect(positionsWithoutAccountRefCalls).toBe(0);
});
