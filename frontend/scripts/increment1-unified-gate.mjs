import { chromium, expect } from '@playwright/test';

const base = process.env.EVIDENCE_URL;
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base || '')) throw new Error('Disposable loopback server required');
const caseId = Number(process.env.EVIDENCE_CASE);
const stagingId = Number(process.env.EVIDENCE_STAGING);
const browser = await chromium.launch({ headless: true });
const casePath = `/evidence/cases/${caseId}`;
const receipt = { case_id: caseId, authenticated_requests: 0 };

async function login(page) {
  await page.goto(`${base}/login`);
  await page.locator('input[type=email]').fill(process.env.EVIDENCE_EMAIL);
  await page.locator('input[type=password]').fill('ContractTest123!');
  await page.locator('button[type=submit]').click();
  await page.waitForURL('**/dashboard');
  await page.goto(`${base}/processes/${caseId}?tab=ai`);
  await expect(page.getByText('Revisão das conclusões e retomada')).toBeVisible();
}
// Real authenticated HTTP for operations not exercised as DOM gestures below.
// No interception, bypass route, injected token or mocked API response.
async function request(page, method, path, data, expected = 200) {
  const token = await page.evaluate(() => JSON.parse(localStorage.getItem('auth-storage')).state.token);
  expect(token).toBeTruthy();
  const response = await page.request.fetch(`${base}/api/v1${path}`, {
    method, headers: { Authorization: `Bearer ${token}` }, ...(data ? { data } : {}),
  });
  expect(response.status(), await response.text()).toBe(expected);
  receipt.authenticated_requests++;
  return response.json();
}
const state = page => request(page, 'GET', casePath);
const row = (data, id, version) => {
  const found = data.objects.find(r => r.object.id === id && r.object.version === version);
  expect(found, `${id}@${version} recoverable`).toBeDefined();
  return found;
};
const run = (page, agent_name, key, asynchronous = false) => request(page, 'POST',
  `/agents/${asynchronous ? 'run-async' : 'run'}`,
  { agent_name, process_id: caseId, idempotency_key: key }, asynchronous ? 202 : 200);
const review = (page, object, revision, action, correction) => request(page, 'POST',
  `${casePath}/objects/${encodeURIComponent(object.id)}/review`, {
    expected_version: object.version, expected_revision: revision, action,
    justification: `Gate autenticado: ${action}`, ...(correction ? { correction } : {}),
  });
async function reviewDom(page, statement, button, correction) {
  const card = page.locator('article').filter({ hasText: statement });
  await expect(card).toHaveCount(1);
  await card.getByLabel('Justificativa da revisão').fill(`Gate autenticado: ${button}`);
  if (correction) await card.getByLabel('Texto corrigido').fill(correction);
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/review') && r.request().method() === 'POST'),
    card.getByRole('button', { name: button, exact: true }).click(),
  ]);
  expect(response.status(), await response.text()).toBe(200);
  return response.json();
}
async function runDom(page) {
  await page.locator('select').filter({ has: page.locator('option[value=diagnostico]') }).first().selectOption('diagnostico');
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/agents/run-async') && r.request().method() === 'POST'),
    page.getByRole('button', { name: 'Executar', exact: true }).click(),
  ]);
  expect(response.status(), await response.text()).toBe(202);
  return response.json();
}
const stagingDecision = r => ({ status: r.status, value: r.decided_value,
  author: r.decided_by_user_id, at: r.decided_at });

try {
  const context = await browser.newContext();
  const page = await context.newPage();
  await login(page);
  // Human acceptance is performed through the authenticated endpoint, not pre-seeded.
  await request(page, 'POST', `/processes/${caseId}/staging-fields/${stagingId}/decidir`, { acao: 'editar', valor: 11 });
  receipt.staging_before = stagingDecision((await request(page, 'GET', `/processes/${caseId}/staging-fields`)).find(r => r.id === stagingId));
  expect(receipt.staging_before.status).toBe('aceito');
  expect(receipt.staging_before.author).toBeTruthy();
  expect(receipt.staging_before.at).toBeTruthy();
  const audit = await run(page, 'auditor_imovel', 'gate-auditor-before');
  expect(audit.steps[0].status).toBe('completed');
  const objects = audit.data.objects;
  const denomination = objects.find(o => o.kind === 'derivacao' && o.attributes.normalized.item === 'denominacao_imovel');
  expect(denomination).toBeDefined();
  const rejected = objects.find(o => o.kind === 'conclusao' && o.premises.some(p => p.id === denomination.id));
  const accepted = objects.filter(o => o.kind === 'conclusao' && o.id !== rejected.id);
  expect(accepted.length).toBeGreaterThan(0); // positive control: the gate is not just empty

  // G1: an AUDITOR conclusion is rejected before DIAGNOSTIC receives its actual prompt.
  await page.reload();
  await reviewDom(page, rejected.statement, 'Rejeitar');
  for (const obj of accepted) await review(page, obj, 0, 'aprovar');
  await page.reload();
  await expect(page.locator('article').filter({ hasText: rejected.statement }).getByText('Rejeitada', { exact: true })).toBeVisible();
  receipt.rejected = rejected;
  receipt.accepted_auditor = accepted.map(o => o.id);
  // ADR-074: the commercial chain no longer reruns the diagnosis; it runs as its own execution.
  const diagnostic = await request(page, 'POST', '/agents/chain',
    { chain_name: 'diagnostico', process_id: caseId, idempotency_key: 'gate-diagnostic' });
  const diagnosticExecution = await request(page, 'GET', `/evidence/executions/${diagnostic.id}`);
  expect(diagnosticExecution.status).toBe('awaiting_review');
  const proposed = (await state(page)).objects.find(r => r.object.statement === 'GATE_DIAGNOSTICO_PROPOSTO').object;
  await expect(page.locator('article').filter({ hasText: proposed.statement })).toBeVisible();

  // G2: correction creates v2; recover the complete v1 through the authorized endpoint.
  const corrected = await reviewDom(page, proposed.statement, 'Criar correção', 'GATE_DIAGNOSTICO_CORRIGIDO');
  expect(corrected.version).toBe(2);
  expect(corrected.status).toBe('pendente');
  const old = await request(page, 'GET', `${casePath}/sources/${encodeURIComponent(proposed.id)}/versions/1`);
  expect(old.object).toEqual(proposed);
  receipt.original = old.object;
  receipt.corrected = corrected;

  // G3: F5, new browser context and new login preserve decisions and version history.
  await page.reload();
  await expect(page.locator('article').filter({ hasText: 'GATE_DIAGNOSTICO_CORRIGIDO' })).toBeVisible();
  await context.close();
  const secondContext = await browser.newContext();
  const secondPage = await secondContext.newPage();
  await login(secondPage);
  await expect(secondPage.locator('article').filter({ hasText: rejected.statement }).getByText('Rejeitada', { exact: true })).toBeVisible();
  await expect(secondPage.locator('article').filter({ hasText: 'GATE_DIAGNOSTICO_CORRIGIDO' }).getByText('Pendente', { exact: true })).toBeVisible();
  await secondPage.getByLabel('Mostrar versões anteriores').check();
  await expect(secondPage.locator('article').filter({ hasText: 'GATE_DIAGNOSTICO_PROPOSTO' })).toBeVisible();
  const afterLogin = await state(secondPage);
  expect(row(afterLogin, rejected.id, 1).review.action).toBe('rejeitar');
  expect(row(afterLogin, proposed.id, 1).review.action).toBe('corrigir');
  expect(row(afterLogin, proposed.id, 2).review).toBeNull();
  await reviewDom(secondPage, 'GATE_DIAGNOSTICO_CORRIGIDO', 'Aprovar');
  receipt.approval_before = row(await state(secondPage), proposed.id, 2);

  // G4: resume a REAL partially executed production chain, not a finished one-step run.
  // gerar_proposta (ADR-074): without a validated Rota the Redator fails by name and the
  // orçamento waits for it; resuming records attempts and never produces a document.
  const partial = await request(secondPage, 'POST', '/agents/chain',
    { chain_name: 'gerar_proposta', process_id: caseId, idempotency_key: 'gate-partial-chain' });
  const partialExecution = await request(secondPage, 'GET', `/evidence/executions/${partial.id}`);
  expect(partialExecution.cursor).toBe(0);
  expect(partialExecution.steps.map(s => s.agent)).toEqual(['redator', 'orcamento']);
  expect(partialExecution.steps[0].status).toBe('failed');
  expect(partialExecution.steps[0].error).toContain('Rota validada ausente');
  expect(partialExecution.steps[1].status).toBe('awaiting_review');
  expect(partialExecution.steps[1].job_id).toBeUndefined();
  const resumed = await request(secondPage, 'POST', `/evidence/executions/${partial.id}/resume`,
    { expected_revision: partialExecution.revision });
  const resumedAgain = await request(secondPage, 'POST', `/evidence/executions/${partial.id}/resume`,
    { expected_revision: resumed.revision });
  expect(resumed.status).toBe('failed');
  expect(resumed.steps[0].job_id).toBeTruthy();
  expect(resumed.steps[0].job_id).not.toBe(partialExecution.steps[0].job_id);
  expect(resumedAgain.steps[1].job_id).toBeUndefined();
  expect(resumedAgain.cursor).toBe(partialExecution.cursor);
  // The completed diagnostic step, resumed after its approval, is never executed again.
  const diagnosticResumed = await request(secondPage, 'POST', `/evidence/executions/${diagnostic.id}/resume`,
    { expected_revision: diagnosticExecution.revision });
  expect(diagnosticResumed.steps[0]).toEqual(diagnosticExecution.steps[0]);
  expect(diagnosticResumed.completed).toBe(true);
  receipt.resume = { before: partialExecution, first: resumed, after: resumedAgain };
  receipt.diagnostic = { before: diagnosticExecution, after: diagnosticResumed };

  // G5: both real entrypoints; real task.delay uses Celery's eager test transport.
  const sync = await run(secondPage, 'diagnostico', 'gate-sync');
  const asynchronous = await run(secondPage, 'diagnostico', 'gate-async', true);
  receipt.transports = { sync: sync.id, async: asynchronous.id };

  // G6: Python removes the mandatory diagnostic skill for exactly this next call.
  const missing = await runDom(secondPage);
  const missingExecution = await request(secondPage, 'GET', `/evidence/executions/${missing.id}`);
  expect(missingExecution.status).toBe('capacidade_insuficiente');
  await expect(secondPage.getByText('diagnostico: CAPACIDADE INSUFICIENTE', { exact: true })).toBeVisible({ timeout: 20000 });
  receipt.missing = missingExecution.id;

  // G7: the controlled provider returns verified absence WITHOUT verification record.
  const invalid = await run(secondPage, 'diagnostico', 'gate-invalid-absence');
  expect(invalid.status).toBe('failed');
  receipt.invalid_absence = invalid.id;

  // G8: correction of a consumed premise invalidates v2 and preserves the SAME approval event.
  const beforeChange = await state(secondPage);
  const premise = beforeChange.objects.filter(r => r.object.id === `staging:${stagingId}`)
    .sort((a, b) => b.object.version - a.object.version)[0];
  expect(proposed.premises.some(p => p.id === premise.object.id && p.version === premise.object.version)).toBe(true);
  const correction = { ...premise.object, attributes: { ...premise.object.attributes, normalized: { value: 12 } } };
  await review(secondPage, premise.object, premise.revision, 'corrigir', correction);
  const afterChange = await state(secondPage);
  const dependent = row(afterChange, proposed.id, 2);
  expect(dependent.stale).toBe(true);
  expect(dependent.review).toEqual(receipt.approval_before.review);
  expect(dependent.history).toEqual(receipt.approval_before.history);
  expect(afterChange.envelope.conclusions.some(o => o.id === proposed.id)).toBe(false);
  receipt.approval_after = dependent;
  receipt.premise = { before: premise.object, after: row(afterChange, premise.object.id, premise.object.version + 1).object };

  // G9: new deterministic assessment; never replace staging acceptance or old approval.
  const auditAgain = await run(secondPage, 'auditor_imovel', 'gate-auditor-after');
  expect(auditAgain.steps[0].status).toBe('completed');
  const oldIds = objects.map(o => o.id);
  expect(auditAgain.data.objects.length).toBeGreaterThan(0);
  expect(auditAgain.data.objects.every(o => !oldIds.includes(o.id))).toBe(true);
  receipt.staging_after = stagingDecision((await request(secondPage, 'GET', `/processes/${caseId}/staging-fields`)).find(r => r.id === stagingId));
  expect(receipt.staging_after).toEqual(receipt.staging_before);
  expect(row(await state(secondPage), proposed.id, 2).history).toEqual(receipt.approval_before.history);
  receipt.auditor = { before: audit.id, after: auditAgain.id, old_ids: oldIds,
    new_ids: auditAgain.data.objects.map(o => o.id) };
  await secondContext.close();
  console.log(`GATE_RECEIPT=${JSON.stringify(receipt)}`);
} finally {
  await browser.close();
}
