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
    let response;
    for (let attempt = 0; attempt < 3; attempt++) {
    await page.waitForLoadState('networkidle');
    [response] = await Promise.all([
      page.waitForResponse(r => r.url().endsWith('/agents/run-async') && r.request().method() === 'POST', { timeout: 1200000 }),
      page.getByRole('button', { name: 'Executar', exact: true }).click(),
    ]);
    if (response.status() !== 409) break;
    const conflict = await response.json();
    if (conflict.detail !== 'Execução ou revisão concorrente; recarregue o estado') break;
    console.log(`TRANSIENT_READ_CONFLICT case=${caseId} attempt=${attempt + 1}`);
    await page.reload();
    await page.locator('select').filter({ has: page.locator('option[value=extrator]') }).first().selectOption('extrator');
    }
    if (response.status() === 409) {
      const conflict = await response.json();
      const knownConflicts = [
        'Execução ou revisão concorrente; recarregue o estado',
        'Versão imutável já existe com outro conteúdo',
        'Execução atualizada por outra sessão',
      ];
      console.log('EXTRACTION_CONFLICT=' + (knownConflicts.includes(conflict.detail) ? conflict.detail : 'other'));
    }
    expect(response.status()).toBe(202);
    const run = await response.json();
    const data = await evidence(page, caseId);
    const execution = data.executions.find(e => e.id === run.id);
    // A success receipt must never be produced from an empty or failed extraction.
    if (execution?.status !== 'completed') {
      receipt.executions.push({ case: caseId, id: run.id, status: execution?.status || 'missing',
        observations: data.objects.filter(r => r.object.kind === 'observacao').length });
      console.log('CASE_FAILED=' + JSON.stringify(receipt.executions.at(-1)));
      await ctx.close();
      continue; // Measure the other case too; a failed case still fails the final gate.
    }
    const observations = data.objects.filter(r => r.object.kind === 'observacao');
    expect(observations.length).toBeGreaterThan(0);
    const identities = observations.map(r => `${r.object.id}:${r.object.version}`).sort();
    receipt.executions.push({ case: caseId, id: run.id, status: execution?.status,
      steps: execution?.steps.map(s => ({ agent: s.agent, status: s.status, error: s.error ? 'present' : null })),
      observations: data.objects.filter(r => r.object.kind === 'observacao').length });
    console.log('CASE_RESULT=' + JSON.stringify(receipt.executions.at(-1)));
    await page.reload();
    // Real cases carry ~200 observations; the evidence read is not instantaneous.
    await expect(page.getByText('Observações documentais', { exact: true })).toBeVisible({ timeout: 60000 });
    const after = await evidence(page, caseId);
    expect(after.objects.length).toBe(data.objects.length);
    expect(after.objects.filter(r => r.object.kind === 'observacao')
      .map(r => `${r.object.id}:${r.object.version}`).sort()).toEqual(identities);
    receipt.reload.push(caseId);
    await ctx.close();
    const fresh = await browser.newContext();
    const freshPage = await fresh.newPage();
    await login(freshPage, caseId);
    const restored = await evidence(freshPage, caseId);
    expect(restored.objects.length).toBe(data.objects.length);
    expect(restored.objects.filter(r => r.object.kind === 'observacao')
      .map(r => `${r.object.id}:${r.object.version}`).sort()).toEqual(identities);
    receipt.new_session.push(caseId);
    await fresh.close();
  }
  // The #25 cadastral/contractual cut carries no deed; nothing to reclassify there.
  if (!associationOnly && state.documents['559'] && receipt.executions.every(e => e.status === 'completed')) {
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
  expect(dependents.length).toBeGreaterThan(0);
  expect(dependents.every(r => r.stale)).toBe(true);
  receipt.reclassification = { document: doc.id, dependents: dependents.length,
    stale: dependents.filter(r => r.stale).length, before_objects: before.objects.length };
  }
  console.log('GATE_RECEIPT=' + JSON.stringify(receipt));
  if (receipt.executions.some(e => e.status !== 'completed')) process.exitCode = 1;
} finally {
  await browser.close();
}
