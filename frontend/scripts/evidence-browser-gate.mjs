import { chromium, expect } from '@playwright/test';

const base = process.env.EVIDENCE_URL;
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base || '')) throw new Error('Disposable loopback test server required');
const browser = await chromium.launch({ headless: true });
const path = `/processes/${process.env.EVIDENCE_CASE}?tab=ai`;
async function login(page) {
  await page.goto(`${base}/login`);
  await page.locator('input[type=email]').fill(process.env.EVIDENCE_EMAIL);
  await page.locator('input[type=password]').fill('ContractTest123!');
  await page.locator('button[type=submit]').click();
  await page.waitForURL('**/dashboard');
  await page.goto(base + path);
  await expect(page.getByText('Revisão das conclusões e retomada')).toBeVisible();
}
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  await login(page);
  for (const name of ['atendimento', 'financeiro', 'marketing', 'acompanhamento', 'vigia']) {
    await expect(page.locator(`select option[value="${name}"]`)).toHaveCount(0);
  }
  await page.locator('select').filter({ has: page.locator('option[value=diagnostico]') }).first().selectOption('diagnostico');
  await page.getByRole('button', { name: 'Executar', exact: true }).click();
  const card = page.locator('article').filter({ hasText: 'Hipótese controlada do navegador' }).first();
  await expect(card).toBeVisible({ timeout: 20000 });
  await card.getByLabel('Justificativa da revisão').fill('Não sustentada pelas fontes');
  await card.getByRole('button', { name: 'Rejeitar', exact: true }).click();
  await expect(card.getByText('Rejeitada', { exact: true })).toBeVisible();
  await page.reload();
  await expect(card.getByText('Rejeitada', { exact: true })).toBeVisible();
  // The second effective prompt is asserted by the Python side of this same test.
  await page.locator('select').filter({ has: page.locator('option[value=diagnostico]') }).first().selectOption('diagnostico');
  await page.getByRole('button', { name: 'Executar', exact: true }).click();
  await expect(page.locator('article')).toHaveCount(2, { timeout: 20000 });
  await card.getByLabel('Justificativa da revisão').fill('Correção documentada pelo consultor');
  await card.getByLabel('Texto corrigido').fill('Hipótese corrigida na interface');
  await card.getByRole('button', { name: 'Criar correção' }).click();
  await expect(page.getByText('Hipótese corrigida na interface', { exact: false })).toBeVisible();
  await context.close();
  const secondContext = await browser.newContext();
  const secondPage = await secondContext.newPage();
  await login(secondPage);
  const corrected = secondPage.locator('article').filter({ hasText: 'Hipótese corrigida na interface' });
  await expect(corrected).toBeVisible();
  await expect(corrected.getByText('Pendente', { exact: true })).toBeVisible();
  await secondPage.getByLabel('Mostrar versões anteriores').check();
  await expect(secondPage.locator('article')).toHaveCount(3);
  await expect(secondPage.getByText('Substituída por correção', { exact: true }).first()).toBeVisible();
  await secondPage.getByRole('button', { name: 'Retomar execução', exact: true }).first().click();
  await expect(secondPage.locator('article')).toHaveCount(3);
  await secondPage.locator('select').filter({ has: secondPage.locator('option[value=extrator]') }).first().selectOption('extrator');
  await secondPage.getByRole('button', { name: 'Executar', exact: true }).click();
  await expect(secondPage.getByText('CAPACIDADE INSUFICIENTE', { exact: true })).toBeVisible({ timeout: 20000 });
  await secondContext.close();
  console.log('PASS: DOM reject, reload, correction, fresh login, version history, resume, missing capability');
} finally {
  await browser.close();
}
