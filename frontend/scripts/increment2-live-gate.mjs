// Real login, source association and extraction through DOM. No stored payloads/traces.
import { chromium, expect } from '@playwright/test';
const control = process.env.INC2_CONTROL;
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(control || '')) throw new Error('Loopback preparation required');
const state = await (await fetch(control)).json();
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(state.url)) throw new Error('Dev URL required');
const browser = await chromium.launch({ headless: true });
const associationOnly = process.env.INC2_ASSOCIATION_ONLY === '1';
const receipt = { association: [], executions: [], reload: [], new_session: [], reclassification: null };
async function login(page, caseId) {
  await page.goto(`${state.url}/login`);
  await page.locator('input[type=email]').fill(state.email);
  await page.locator('input[type=password]').fill('GateIncremento2!2026');
  await page.locator('button[type=submit]').click();
  await page.waitForURL('**/dashboard');
  await page.goto(`${state.url}/processes/${caseId}?tab=ai`);
  await expect(page.getByRole('heading', { name: 'Revisão das conclusões e retomada' })).toBeVisible({ timeout: 30000 });
}
async function evidence(page, caseId) {
  const token = await page.evaluate(() => JSON.parse(localStorage.getItem('auth-storage')).state.token);
  const result = await page.request.get(`${state.url}/api/v1/evidence/cases/${caseId}`, { headers: { Authorization: `Bearer ${token}` } });
  expect(result.status()).toBe(200);
  return result.json();
}
try {
  for (const caseId of Object.values(state.cases)) {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    page.setDefaultTimeout(30000);
    await login(page, caseId);
    for (const doc of Object.values(state.documents).filter(d => d.case === caseId)) {
      await page.getByLabel('Número do documento recebido').fill(String(doc.id));
      const [response] = await Promise.all([
        page.waitForResponse(r => r.url().endsWith(`/${doc.id}/associate`) && r.request().method() === 'POST'),
        page.getByRole('button', { name: 'Associar documento ao caso', exact: true }).click(),
      ]);
      expect(response.status()).toBe(200);
      receipt.association.push(doc.id);
      await expect(page.locator(`[data-document-id="${doc.id}"]`)).toBeVisible();
    }
    if (associationOnly) {
      await page.reload();
      for (const doc of Object.values(state.documents).filter(d => d.case === caseId)) {
        await expect(page.locator(`[data-document-id="${doc.id}"]`)).toBeVisible();
      }
      receipt.reload.push(caseId);
      await ctx.close();
      const fresh = await browser.newContext();
      const freshPage = await fresh.newPage();
      await login(freshPage, caseId);
      for (const doc of Object.values(state.documents).filter(d => d.case === caseId)) {
        await expect(freshPage.locator(`[data-document-id="${doc.id}"]`)).toBeVisible();
      }
      receipt.new_session.push(caseId);
      await fresh.close();
      continue; // No extraction request, provider call or reclassification in this mode.
    }
    await page.locator('select').filter({ has: page.locator('option[value=extrator]') }).first().selectOption('extrator');
    console.log(`EXTRACTION_STARTED case=${caseId}`);
    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().endsWith('/agents/run-async') && r.request().method() === 'POST', { timeout: 1200000 }),
      page.getByRole('button', { name: 'Executar', exact: true }).click(),
    ]);
    expect(response.status()).toBe(202);
    const run = await response.json();
    const data = await evidence(page, caseId);
    const execution = data.executions.find(e => e.id === run.id);
    receipt.executions.push({ case: caseId, id: run.id, status: execution?.status,
      steps: execution?.steps.map(s => ({ agent: s.agent, status: s.status, error: s.error ? 'present' : null })),
      observations: data.objects.filter(r => r.object.kind === 'observacao').length });
    console.log('CASE_RESULT=' + JSON.stringify(receipt.executions.at(-1)));
    await page.reload();
    await expect(page.getByText('Observações documentais', { exact: true })).toBeVisible();
    const after = await evidence(page, caseId);
    expect(after.objects.length).toBe(data.objects.length);
    receipt.reload.push(caseId);
    await ctx.close();
    const fresh = await browser.newContext();
    const freshPage = await fresh.newPage();
    await login(freshPage, caseId);
    const restored = await evidence(freshPage, caseId);
    expect(restored.objects.length).toBe(data.objects.length);
    receipt.new_session.push(caseId);
    await fresh.close();
  }
  if (!associationOnly) {
  const doc = state.documents['559'];
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await login(page, doc.case);
  const before = await evidence(page, doc.case);
  await page.getByLabel(`Espécie do documento ${doc.id}`).selectOption('escritura_publica');
  await page.getByLabel(`Motivo da reclassificação ${doc.id}`).fill('Revisão documental da espécie, com invalidação das extrações dependentes');
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith(`/${doc.id}/reclassify`) && r.request().method() === 'POST'),
    page.locator(`[data-document-id="${doc.id}"]`).getByRole('button', { name: 'Reclassificar documento' }).click(),
  ]);
  expect(response.status()).toBe(200);
  await page.reload();
  const after = await evidence(page, doc.case);
  const dependents = after.objects.filter(r => r.object.attributes.document_id === doc.id);
  receipt.reclassification = { document: doc.id, dependents: dependents.length,
    stale: dependents.filter(r => r.stale).length, before_objects: before.objects.length };
  }
  console.log('GATE_RECEIPT=' + JSON.stringify(receipt));
} finally {
  await browser.close();
}
