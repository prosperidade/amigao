// Exercita correção de OBSERVAÇÃO (não conclusão) pela tela, real material do #25 (André, 21/09/2026).
// Login real, DOM real. Sem interceptação, sem token injetado. Só leitura/POST autenticados via UI.
import { chromium, expect } from '@playwright/test';
const control = process.env.INC2_CONTROL;
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(control || '')) throw new Error('Loopback preparation required');
const state = await (await fetch(control)).json();
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(state.url)) throw new Error('Dev URL required');
const caseId = state.cases['25'];
const browser = await chromium.launch({ headless: true });
const receipt = {};
try {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(`${state.url}/login`);
  await page.locator('input[type=email]').fill(state.email);
  await page.locator('input[type=password]').fill('GateIncremento2!2026');
  await page.locator('button[type=submit]').click();
  await page.waitForURL('**/dashboard');
  await page.goto(`${state.url}/processes/${caseId}?tab=ai`);
  await page.getByText('Observações documentais', { exact: true }).click();
  const card = page.locator('article').filter({ has: page.getByText('declaração extraída', { exact: false }) }).first();
  await expect(card).toBeVisible({ timeout: 30000 });
  receipt.before_text = await card.locator('p.whitespace-pre-wrap').first().innerText();
  await card.getByLabel('Justificativa da revisão').fill('Correção pela tela — exercício do gate, material real do #25.');
  await card.getByLabel('Texto corrigido').fill('Correção de teste — não substitui o trecho de origem.');
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/review') && r.request().method() === 'POST'),
    card.getByRole('button', { name: 'Criar correção', exact: true }).click(),
  ]);
  expect(response.status(), await response.text()).toBe(200);
  const corrected = await response.json();
  receipt.corrected_version = corrected.version;
  receipt.corrected_status = corrected.status;
  await page.reload();
  await page.getByText('Observações documentais', { exact: true }).click();
  await expect(page.locator('article').filter({ hasText: 'Correção de teste' })).toBeVisible({ timeout: 15000 });
  const token = await page.evaluate(() => JSON.parse(localStorage.getItem('auth-storage')).state.token);
  const original = await page.request.get(
    `${state.url}/api/v1/evidence/cases/${caseId}/sources/${encodeURIComponent(corrected.id)}/versions/1`,
    { headers: { Authorization: `Bearer ${token}` } });
  expect(original.status()).toBe(200);
  const originalBody = await original.json();
  receipt.original_recoverable = originalBody.object.attributes.literal === receipt.before_text;
  console.log('CORRECAO_PELA_TELA=' + JSON.stringify(receipt));
} finally {
  await browser.close();
}
