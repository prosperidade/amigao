// Authenticated read-only verification against Ficha 08 and the Isis SPEC.
// No screenshots, traces, source files or response payloads are written.
import { chromium, expect } from '@playwright/test';
const control = process.env.INC2_CONTROL;
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(control || '')) throw new Error('Dev loopback required');
const state = await (await fetch(control)).json();
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(state.url)) throw new Error('Dev URL required');
const browser = await chromium.launch({ headless: true });
const report = [];
try {
  for (const origin of ['23', '25'].filter(o => state.cases[o])) {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    const caseId = state.cases[origin];
    await page.goto(`${state.url}/login`);
    await page.locator('input[type=email]').fill(state.email);
    await page.locator('input[type=password]').fill('GateIncremento2!2026');
    await page.locator('button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    await page.goto(`${state.url}/processes/${caseId}?tab=ai`);
    await expect(page.getByText('Observações documentais', { exact: true })).toBeVisible({ timeout: 60000 });
    const token = await page.evaluate(() => JSON.parse(localStorage.getItem('auth-storage')).state.token);
    const response = await page.request.get(`${state.url}/api/v1/evidence/cases/${caseId}`, { headers: { Authorization: `Bearer ${token}` } });
    expect(response.ok()).toBe(true);
    const data = await response.json();
    const latest = new Map();
    for (const row of data.objects) {
      if (!latest.has(row.object.id) || latest.get(row.object.id).object.version < row.object.version) latest.set(row.object.id, row);
    }
    const obs = [...latest.values()].filter(r => r.object.kind === 'observacao' && !r.superseded);
    const items = (doc, predicate) => obs.filter(r => r.object.attributes.document_id === state.documents[doc]?.id
      && r.object.attributes.predicate === predicate).map(r => r.object.attributes.normalized);
    const checks = { observations: obs.length, knowledge_unpromoted: obs.every(r => r.object.knowledge.state === 'nao_determinado'),
      human_review_separate: obs.every(r => r.review === null) };
    if (origin === '23') {
      checks.four_registry_identities = ['547', '548', '549', '550'].every((doc, i) =>
        items(doc, 'ato_registral').some(a => a.serventia && String(a.matricula).replace(/\D/g, '') === ['3181', '3313', '3673', '4387'][i]));
      await page.goto(`${state.url}/processes/${caseId}?tab=dossier`);
      await page.waitForLoadState('networkidle');
      checks.cnpj_visible_in_ficha = await page.getByText(/29\.091\.958\/0001-17|29091958000117/).first().isVisible();
      checks.pj_visible_in_ficha = await page.getByText(/ELODI/i).first().isVisible();
    } else {
      if (state.documents['559']) {
        const parties = new Map(items('559', 'parte').map(p => [p.chave, p]));
        const sellers = items('559', 'participacao').filter(p => p.papel === 'transmitente').map(p => parties.get(p.parte_chave)?.nome || '');
        checks.sellers_as_transmitentes = ['IVAIR', 'ELDA'].every(n => sellers.some(s => s.toUpperCase().includes(n)));
      }
      checks.estate_documented = items('558', 'parte').some(p => p.natureza === 'espolio' && p.falecido_chave);
      checks.inventariante_declared = items('558', 'participacao').some(p => p.papel === 'inventariante' && p.representado_chave && p.estado_confirmacao === 'declarado');
      checks.death_declaration = items('557', 'falecimento_declarado').length > 0;
      await page.getByText('Observações documentais', { exact: true }).click();
      if (state.documents['559']) checks.transmitente_visible = await page.getByText(/declaração extraída — transmitente/).first().isVisible();
      checks.inventariante_visible = await page.getByText(/declaração extraída — inventariante/).first().isVisible();
    }
    report.push({ origin, case: caseId, checks });
    await ctx.close();
  }
  console.log('ISIS_SEMANTIC_RECEIPT=' + JSON.stringify(report));
} finally {
  await browser.close();
}
