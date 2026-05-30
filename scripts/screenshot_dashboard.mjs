/**
 * screenshot_dashboard.mjs
 *
 * Captura 4 screenshots do dashboard para o briefing de redesign:
 *   1. Dashboard Executivo — light
 *   2. Dashboard Executivo — dark
 *   3. Dashboard Operacional — light
 *   4. Dashboard Operacional — dark
 *
 * Uso:
 *   npx playwright install chromium
 *   node scripts/screenshot_dashboard.mjs
 *
 * Saída: docs/redesign/screenshots/*.png
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'fs';
import { join } from 'path';

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:5173';
const EMAIL = process.env.SEED_EMAIL || 'admin@amigao.com';
const PASSWORD = process.env.SEED_PASSWORD || 'Seed@2026';
const OUT_DIR = join(process.cwd(), 'docs', 'redesign', 'screenshots');

mkdirSync(OUT_DIR, { recursive: true });

async function setTheme(page, theme) {
  await page.evaluate((t) => {
    const root = document.documentElement;
    if (t === 'dark') root.classList.add('dark');
    else root.classList.remove('dark');
    localStorage.setItem('theme', t);
  }, theme);
  await page.waitForTimeout(400);
}

async function setView(page, label) {
  const btn = page.getByRole('button', { name: label, exact: true });
  await btn.click();
  await page.waitForLoadState('networkidle', { timeout: 25_000 }).catch(() => {});
  // Operacional faz várias queries (kpis, vigia-alerts, ai-jobs etc) — dá tempo
  await page.waitForTimeout(5000);
}

async function shot(page, name) {
  const path = join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path, fullPage: true });
  console.log(`saved ${path}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await ctx.newPage();

  // 1. Login
  console.log(`→ ${FRONTEND_URL}/login`);
  await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[type="email"], input[name="email"]', EMAIL);
  await page.fill('input[type="password"], input[name="password"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/dashboard/, { timeout: 15_000 });
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {});
  await page.waitForTimeout(2500);

  // 2. EXECUTIVO LIGHT (estado inicial — default)
  await setTheme(page, 'light');
  await page.waitForTimeout(500);
  await shot(page, '01_executivo_light');

  // 3. EXECUTIVO DARK
  await setTheme(page, 'dark');
  await shot(page, '02_executivo_dark');

  // 4. OPERACIONAL DARK (já está no dark)
  await setView(page, 'Operacional');
  // Seed data tem >30 dias — expandir filtro para popular KPIs
  await page.selectOption('select:has(option:has-text("Últimos 30 dias"))', '180').catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(3500);
  await shot(page, '03_operacional_dark');

  // 5. OPERACIONAL LIGHT
  await setTheme(page, 'light');
  await shot(page, '04_operacional_light');

  await browser.close();
  console.log('done.');
})().catch(err => {
  console.error('FAILED:', err);
  process.exit(1);
});
