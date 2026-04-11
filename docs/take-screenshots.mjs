/**
 * Screenshot capture script for Kairos Mesh UI documentation.
 * Usage:  node docs/take-screenshots.mjs
 */

import pkg from '../frontend/node_modules/playwright/index.js';
const { chromium } = pkg;
import { existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR   = resolve(__dirname, 'screenshots');
const BASE_URL  = 'http://localhost:5173';
const VIEWPORT  = { width: 1440, height: 860 };

if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

// ---------------------------------------------------------------------------

async function shot(page, filename, scrollY = 0) {
  if (scrollY) {
    await page.evaluate(y => window.scrollTo(0, y), scrollY);
    await page.waitForTimeout(600);
  }
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT_DIR}/${filename}`, fullPage: false });
  console.log(`  ✓  ${filename}`);
}

async function goto(page, path) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1800);
}

// ---------------------------------------------------------------------------

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: VIEWPORT });
const page    = await context.newPage();

// ── 1. Login ────────────────────────────────────────────────────────────────
console.log('\n[1] Login');
await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(1500);
await shot(page, '00-login.png');

await page.fill('input[type="email"]', 'admin@local.dev');
await page.fill('input[type="password"]', 'admin1234');
await page.locator('button.btn-primary').click();
await page.waitForURL(`${BASE_URL}/**`, { timeout: 15_000 });
await page.waitForTimeout(1500);
console.log('  → logged in, at:', page.url());

// ── 2. Terminal ─────────────────────────────────────────────────────────────
console.log('\n[2] Terminal');
await goto(page, '/terminal');
await shot(page, '01-terminal-top.png');
await shot(page, '02-terminal-chart.png', 700);

// ── 3. Run Detail ───────────────────────────────────────────────────────────
console.log('\n[3] Run Detail');
await goto(page, '/runs/3');
await shot(page, '03-run-detail-header.png');
await shot(page, '04-run-detail-decision.png', 420);

// ── 4. Portfolio Dashboard ──────────────────────────────────────────────────
console.log('\n[4] Portfolio Dashboard');
await goto(page, '/');
await page.waitForTimeout(2500); // extra wait for WS stream
await shot(page, '05-portfolio-dashboard.png');

// ── 5. Orders ───────────────────────────────────────────────────────────────
console.log('\n[5] Orders');
await goto(page, '/orders');
await shot(page, '06-orders.png');

// ── 6. Strategies ───────────────────────────────────────────────────────────
console.log('\n[6] Strategies');
await goto(page, '/strategies');
await shot(page, '07-strategies.png');

// ── 7. Backtests ────────────────────────────────────────────────────────────
console.log('\n[7] Backtests');
await goto(page, '/backtests');
await shot(page, '08-backtests.png');

// ── 8. Connectors ───────────────────────────────────────────────────────────
console.log('\n[8] Connectors');
await goto(page, '/connectors');

// Connectors tab
await page.getByRole('tab', { name: 'Connectors' }).click().catch(() =>
  page.locator('text=Connectors').first().click());
await page.waitForTimeout(600);
await shot(page, '09-connectors-tab.png');

// AI Models tab
await page.getByRole('tab', { name: 'AI Models' }).click().catch(() =>
  page.locator('text=AI Models').first().click());
await page.waitForTimeout(800);
await shot(page, '10-connectors-ai-models.png');
await shot(page, '11-connectors-ai-models-agents.png', 500);

// Trading tab
await page.getByRole('tab', { name: 'Trading' }).click().catch(() =>
  page.locator('text=Trading').first().click());
await page.waitForTimeout(600);
await shot(page, '12-connectors-trading.png');

// Security tab
await page.getByRole('tab', { name: 'Security' }).click().catch(() =>
  page.locator('text=Security').first().click());
await page.waitForTimeout(600);
await shot(page, '13-connectors-security.png');

// ---------------------------------------------------------------------------
await browser.close();
console.log(`\nAll screenshots saved to: ${OUT_DIR}\n`);
