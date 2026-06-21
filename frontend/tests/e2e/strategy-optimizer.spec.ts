import { expect, test, type Page } from '@playwright/test';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function asJson(body: unknown, status = 200) {
  return {
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  };
}

const VALIDATED_STRATEGY = {
  id: 1,
  symbol: 'EURUSD.PRO',
  timeframe: 'H1',
  template: 'ema_crossover',
  status: 'VALIDATED',
  score: 65.0,
  params: { ema_fast: 9, ema_slow: 21, rsi_filter: 30 },
  metrics: { win_rate_pct: 45, profit_factor: 1.5 },
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
};

const BACKTESTING_STRATEGY = {
  ...VALIDATED_STRATEGY,
  id: 2,
  status: 'BACKTESTING',
};

function makeCampaign(overrides: Record<string, unknown> = {}) {
  return {
    id: 10,
    strategy_id: 1,
    status: 'PENDING',
    current_iteration: 0,
    max_iterations: 50,
    best_score: null,
    best_params: null,
    initial_params: { ema_fast: 9, ema_slow: 21, rsi_filter: 30 },
    initial_score: null,
    best_metrics: null,
    elapsed_seconds: null,
    error_message: null,
    created_at: '2026-01-15T10:00:00Z',
    completed_at: null,
    ...overrides,
  };
}

async function setupMockApi(page: Page, options: {
  strategies?: unknown[];
  campaign?: unknown | null;
  campaignSequence?: unknown[];
} = {}) {
  const strategies = options.strategies ?? [VALIDATED_STRATEGY];
  let campaignResponse = options.campaign ?? null;
  const campaignSequence = options.campaignSequence ?? [];
  let pollCount = 0;

  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token');
  });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const method = request.method();
    const url = new URL(request.url());
    const path = url.pathname;

    // Auth
    if (path.endsWith('/auth/me')) {
      return route.fulfill(asJson({ id: 1, email: 'admin@local.dev', role: 'admin', is_active: true }));
    }

    // Strategies list
    if (path.endsWith('/strategies') && method === 'GET') {
      return route.fulfill(asJson(strategies));
    }

    // Launch optimization
    if (path.match(/\/strategies\/\d+\/optimize$/) && method === 'POST') {
      campaignResponse = makeCampaign({ status: 'PENDING' });
      return route.fulfill(asJson(campaignResponse));
    }

    // Get campaign status (polling)
    if (path.match(/\/strategies\/\d+\/optimizer-campaign$/) && method === 'GET') {
      if (campaignSequence.length > 0 && pollCount < campaignSequence.length) {
        const resp = campaignSequence[pollCount];
        pollCount++;
        return route.fulfill(asJson(resp));
      }
      if (campaignResponse) {
        return route.fulfill(asJson(campaignResponse));
      }
      return route.fulfill({ status: 404, body: 'Not found' });
    }

    // Accept campaign
    if (path.match(/\/optimizer-campaign\/\d+\/accept$/) && method === 'POST') {
      campaignResponse = makeCampaign({ status: 'ACCEPTED' });
      return route.fulfill(asJson(campaignResponse));
    }

    // Reject campaign
    if (path.match(/\/optimizer-campaign\/\d+\/reject$/) && method === 'POST') {
      campaignResponse = makeCampaign({ status: 'REJECTED_BY_USER' });
      return route.fulfill(asJson(campaignResponse));
    }

    // Cancel campaign
    if (path.match(/\/optimizer-campaign\/\d+$/) && method === 'DELETE') {
      campaignResponse = makeCampaign({ status: 'CANCELLED' });
      return route.fulfill({ status: 204, body: '' });
    }

    // Fallback
    return route.fulfill({ status: 404, body: 'Not mocked' });
  });
}

// ---------------------------------------------------------------------------
// Test 1: "OPTIMISER" button visible only on VALIDATED strategies
// ---------------------------------------------------------------------------

test('OPTIMISER button visible only for VALIDATED strategies', async ({ page }) => {
  await setupMockApi(page, { strategies: [VALIDATED_STRATEGY, BACKTESTING_STRATEGY] });
  await page.goto('/strategies');

  // OPTIMISER button should be present for the VALIDATED strategy
  const optimiserButtons = page.getByRole('button', { name: /OPTIMISER/i });
  await expect(optimiserButtons).toHaveCount(1);
});

// ---------------------------------------------------------------------------
// Test 2: Click "OPTIMISER" opens config modal with inputs
// ---------------------------------------------------------------------------

test('click OPTIMISER opens config with max_iterations and time_budget inputs', async ({ page }) => {
  await setupMockApi(page);
  await page.goto('/strategies');

  await page.getByRole('button', { name: /OPTIMISER/i }).click();

  // Config panel should be visible with inputs
  await expect(page.getByText('OPTIMIZER_CONFIG')).toBeVisible();
  await expect(page.getByLabel(/Max Iterations/i)).toBeVisible();
  await expect(page.getByLabel(/Time Budget/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /LANCER/i })).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 3: Click "LANCER" calls POST /optimize and shows progress
// ---------------------------------------------------------------------------

test('click LANCER calls POST /optimize and shows progress indicator', async ({ page }) => {
  let optimizePostCalled = false;

  await setupMockApi(page, {
    campaign: null,
    campaignSequence: [
      makeCampaign({ status: 'RUNNING', current_iteration: 5, best_score: 52.0, initial_score: 45.0 }),
    ],
  });

  // Track the POST call
  await page.route('**/api/v1/strategies/1/optimize', async (route) => {
    optimizePostCalled = true;
    return route.fulfill(asJson(makeCampaign({ status: 'PENDING' })));
  });

  await page.goto('/strategies');
  await page.getByRole('button', { name: /OPTIMISER/i }).click();
  await page.getByRole('button', { name: /LANCER/i }).click();

  // Should show optimization progress indicator
  await expect(page.getByText('OPTIMISATION_EN_COURS')).toBeVisible({ timeout: 10000 });
  expect(optimizePostCalled).toBe(true);
});

// ---------------------------------------------------------------------------
// Test 4: Progress bar updates during polling
// ---------------------------------------------------------------------------

test('progress bar updates during polling', async ({ page }) => {
  await setupMockApi(page, {
    campaign: makeCampaign({ status: 'RUNNING', current_iteration: 25, max_iterations: 50, best_score: 55.0, initial_score: 45.0 }),
  });

  await page.goto('/strategies');

  // Wait for progress display
  await expect(page.getByText('OPTIMISATION_EN_COURS')).toBeVisible({ timeout: 10000 });

  // Progress indicator shows iteration count
  await expect(page.getByText('25/50')).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 5: Completed campaign shows score comparison
// ---------------------------------------------------------------------------

test('completed campaign shows score comparison (initial vs best)', async ({ page }) => {
  await setupMockApi(page, {
    campaign: makeCampaign({
      status: 'COMPLETED',
      initial_score: 45.0,
      best_score: 72.5,
      best_params: { ema_fast: 12, ema_slow: 30, rsi_filter: 25 },
      current_iteration: 50,
      max_iterations: 50,
    }),
  });

  await page.goto('/strategies');

  // Should show completion marker and scores
  await expect(page.getByText('OPTIMISATION_TERMINÉE')).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('45.00')).toBeVisible();  // initial score
  await expect(page.getByText('72.50')).toBeVisible();  // best score
});

// ---------------------------------------------------------------------------
// Test 6: Click "APPLIQUER" calls accept endpoint
// ---------------------------------------------------------------------------

test('click APPLIQUER calls accept endpoint', async ({ page }) => {
  let acceptCalled = false;

  await setupMockApi(page, {
    campaign: makeCampaign({
      status: 'COMPLETED',
      initial_score: 45.0,
      best_score: 72.5,
      best_params: { ema_fast: 12, ema_slow: 30, rsi_filter: 25 },
      current_iteration: 50,
    }),
  });

  await page.route('**/api/v1/strategies/optimizer-campaign/10/accept', async (route) => {
    acceptCalled = true;
    return route.fulfill(asJson(makeCampaign({ status: 'ACCEPTED' })));
  });

  await page.goto('/strategies');
  await expect(page.getByText('OPTIMISATION_TERMINÉE')).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /APPLIQUER/i }).click();

  // Wait a tick for the async call to complete
  await page.waitForTimeout(500);
  expect(acceptCalled).toBe(true);
});

// ---------------------------------------------------------------------------
// Test 7: Click "REJETER" calls reject endpoint
// ---------------------------------------------------------------------------

test('click REJETER calls reject endpoint', async ({ page }) => {
  let rejectCalled = false;

  await setupMockApi(page, {
    campaign: makeCampaign({
      status: 'COMPLETED',
      initial_score: 45.0,
      best_score: 72.5,
      best_params: { ema_fast: 12, ema_slow: 30, rsi_filter: 25 },
      current_iteration: 50,
    }),
  });

  await page.route('**/api/v1/strategies/optimizer-campaign/10/reject', async (route) => {
    rejectCalled = true;
    return route.fulfill(asJson(makeCampaign({ status: 'REJECTED_BY_USER' })));
  });

  await page.goto('/strategies');
  await expect(page.getByText('OPTIMISATION_TERMINÉE')).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /REJETER/i }).click();

  await page.waitForTimeout(500);
  expect(rejectCalled).toBe(true);
});

// ---------------------------------------------------------------------------
// Test 8: "ANNULER" button visible during RUNNING status
// ---------------------------------------------------------------------------

test('ANNULER button visible during RUNNING status', async ({ page }) => {
  await setupMockApi(page, {
    campaign: makeCampaign({ status: 'RUNNING', current_iteration: 10, max_iterations: 50, best_score: 50.0, initial_score: 45.0 }),
  });

  await page.goto('/strategies');

  await expect(page.getByText('OPTIMISATION_EN_COURS')).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole('button', { name: /ANNULER/i })).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 9: Failed campaign shows error message
// ---------------------------------------------------------------------------

test('failed campaign shows error message', async ({ page }) => {
  await setupMockApi(page, {
    campaign: makeCampaign({
      status: 'FAILED',
      error_message: 'Market data unavailable for EURUSD.PRO',
      current_iteration: 3,
      max_iterations: 50,
    }),
  });

  await page.goto('/strategies');

  await expect(page.getByText(/OPTIMISATION_ÉCHOUÉE/)).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/Market data unavailable/)).toBeVisible();
});
