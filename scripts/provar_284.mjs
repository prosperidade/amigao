// Prova em dev, no navegador: a proposta só nasce do orçamento do tenant (#284, ADR-081).
//
// Pela tela, nos casos do gate (tenant 33):
//  - #22 (processo 69): Rota assinada sem passo cobrável e sem orçamento. "Gerar relatório e
//    escopo" é recusado com o motivo; a proposta nova fica bloqueada com a mensagem da API, o
//    salvar desabilitado e o atalho para o relatório, escopo e orçamento do caso.
//  - #23 (65) e #25 (66): orçamento aprovado. A proposta nova nasce dele (itens travados, total
//    do orçamento, `orcamento_id` gravado). No #25, enviar → recusar → nova versão: a renegociação
//    nasce do orçamento aprovado e atual.
//
// Só dev (recusa se a API não disser `development`). O registro guarda IDs, estados e totais.
// Uso: PROVA_EMAIL=... PROVA_SENHA=... node scripts/provar_284.mjs
import { mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');

const BASE = process.env.PROVA_BASE ?? 'http://127.0.0.1:5182';
const { PROVA_EMAIL: EMAIL, PROVA_SENHA: SENHA } = process.env;
const CAPTURAS = process.env.PROVA_CAPTURAS ?? null;
if (!EMAIL || !SENHA) throw new Error('PROVA_EMAIL e PROVA_SENHA são obrigatórios');
if (CAPTURAS) mkdirSync(CAPTURAS, { recursive: true });

const registro = { inicio: new Date().toISOString(), base: BASE, passos: [] };
const anotar = (caso, passo, dados = {}) => {
  registro.passos.push({ caso, passo, ...dados });
  process.stderr.write(`[${caso}] ${passo} ${JSON.stringify(dados)}\n`);
};
const capturar = async (page, nome) => { if (CAPTURAS) await page.screenshot({ path: `${CAPTURAS}/${nome}.png` }); };

async function gesto(page, metodo, trecho, acao, esperado) {
  const [resp] = await Promise.all([
    page.waitForResponse(r => r.request().method() === metodo && r.url().includes(trecho), { timeout: 120_000 }),
    acao(),
  ]);
  let corpo = null;
  try { corpo = await resp.json(); } catch { /* 204 */ }
  if (esperado && resp.status() !== esperado) {
    throw new Error(`${metodo} ${trecho}: esperado ${esperado}, veio ${resp.status()} ${JSON.stringify(corpo)}`);
  }
  return { status: resp.status(), corpo };
}

async function entrar(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
  const page = await ctx.newPage();
  page.setDefaultNavigationTimeout(180_000);
  page.setDefaultTimeout(60_000);
  await page.goto(`${BASE}/login`);
  await page.locator('input[type="email"]').fill(EMAIL);
  await page.locator('input[type="password"]').fill(SENHA);
  await gesto(page, 'POST', '/auth/login', () => page.locator('button[type="submit"]').click(), 200);
  await page.waitForURL(u => !u.pathname.startsWith('/login'));
  return { ctx, page };
}

async function rodape(page, caso, tela) {
  const r = page.getByTestId('rodape-versao').last();
  await r.waitFor();
  await page.waitForFunction(el => !el.textContent.includes('…'), await r.elementHandle());
  const texto = (await r.textContent()).trim();
  anotar(caso, `rodapé ${tela}`, { texto });
  if (!/API [0-9a-f]{7} · desenvolvimento/.test(texto)) throw new Error(`rodapé sem SHA: ${texto}`);
}

/** Abre a proposta nova do caso e devolve a resposta do rascunho (generate-draft). */
async function propostaNova(page, pid) {
  const [draft] = await Promise.all([
    page.waitForResponse(r => r.url().includes(`/proposals/generate-draft?process_id=${pid}`)),
    page.goto(`${BASE}/proposals/new?process_id=${pid}`),
  ]);
  let corpo = null;
  try { corpo = await draft.json(); } catch { /* sem corpo */ }
  return { status: draft.status(), corpo };
}

async function caso22(page) {
  const caso = '#22';
  await page.goto(`${BASE}/processes/69?tab=commercial`);
  await page.getByTestId('comercial-rota').waitFor();
  await rodape(page, caso, 'Comercial');
  const r = await gesto(page, 'POST', '/processes/69/comercial/redacao',
    () => page.getByRole('button', { name: /^Gerar relatório e escopo$/ }).click());
  anotar(caso, 'gerar relatório e escopo (tela)', { status: r.status, detalhe: r.corpo?.detail });
  if (r.status !== 422) throw new Error('escopo sem passo cobrável deveria ser recusado');
  await page.getByText(/item de proposta/).first().waitFor(); // o toast mostra o motivo
  await capturar(page, '22-escopo-recusado');

  const d = await propostaNova(page, 69);
  anotar(caso, 'proposta nova (rascunho)', { status: d.status, detalhe: d.corpo?.detail });
  if (d.status !== 422) throw new Error('rascunho sem orçamento deveria ser recusado');
  await page.getByText('Proposta ainda não pode ser gerada').waitFor();
  await page.getByText(d.corpo.detail).waitFor();
  const salvar = page.getByRole('button', { name: /salvar|criar proposta/i }).first();
  const bloqueado = await salvar.isDisabled();
  anotar(caso, 'salvar bloqueado na tela', { bloqueado });
  if (!bloqueado) throw new Error('salvar deveria estar bloqueado sem orçamento');
  await capturar(page, '22-proposta-bloqueada');
  await page.getByRole('button', { name: /Ir para relatório, escopo e orçamento/ }).click();
  await page.waitForURL('**/processes/69?tab=commercial');
  await page.getByTestId('comercial-rota').waitFor();
  anotar(caso, 'atalho para o Comercial do caso', { url: page.url().replace(BASE, '') });
}

async function casoComOrcamento(page, caso, pid) {
  const d = await propostaNova(page, pid);
  anotar(caso, 'proposta nova (rascunho)', { status: d.status, orcamento_id: d.corpo?.orcamento_id,
    total: d.corpo?.suggested_value, itens: d.corpo?.scope_items?.length });
  if (d.status !== 200 || !d.corpo.orcamento_id) throw new Error('rascunho deveria nascer do orçamento');
  await page.getByText(`do orçamento #${d.corpo.orcamento_id}`).waitFor();
  const itemEditavel = await page.locator('input[placeholder="Descrição do serviço"]').first().isEnabled();
  anotar(caso, 'itens travados no rascunho', { item_editavel: itemEditavel });
  if (itemEditavel) throw new Error('item do orçamento não deveria ser editável');
  const salvar = page.getByRole('button', { name: /salvar|criar proposta/i }).first();
  const p = await gesto(page, 'POST', '/proposals/', () => salvar.click(), 201);
  await page.waitForURL(`**/proposals/${p.corpo.id}`);
  anotar(caso, 'proposta criada (tela)', { proposta: p.corpo.id, orcamento_id: p.corpo.orcamento_id,
    total_value: p.corpo.total_value, itens: p.corpo.scope_items.length });
  if (p.corpo.orcamento_id !== d.corpo.orcamento_id || Number(p.corpo.total_value) !== Number(d.corpo.suggested_value)) {
    throw new Error('proposta não nasceu do orçamento');
  }
  await capturar(page, `${caso.slice(1)}-proposta-do-orcamento`);
  return p.corpo;
}

async function renegociar(page, caso, pid, proposta) {
  await page.goto(`${BASE}/processes/${pid}?tab=commercial`);
  await page.getByTestId('comercial-rota').waitFor();
  await rodape(page, caso, 'Comercial');
  const linha = page.locator('div').filter({ hasText: `#${proposta.id} ·` }).last();
  await gesto(page, 'POST', `/proposals/${proposta.id}/send`, () => linha.getByRole('button', { name: /Enviar/ }).click(), 200);
  await gesto(page, 'POST', `/proposals/${proposta.id}/reject`, () => linha.getByRole('button', { name: /Recusar/ }).click(), 200);
  const nv = await gesto(page, 'POST', `/proposals/${proposta.id}/nova-versao`,
    () => linha.getByRole('button', { name: /Nova versão/ }).click(), 201);
  anotar(caso, 'enviar → recusar → nova versão (tela)', { anterior: proposta.id, nova: nv.corpo.id,
    versao: nv.corpo.version_number, orcamento_id: nv.corpo.orcamento_id, total_value: nv.corpo.total_value });
  if (!nv.corpo.orcamento_id) throw new Error('nova versão deveria nascer do orçamento');
  await page.getByText(`renegociação de #${proposta.id}`).waitFor();
  await capturar(page, `${caso.slice(1)}-renegociacao`);
}

const browser = await chromium.launch();
try {
  registro.api = await (await fetch(`${BASE}/api/v1/versao`)).json();
  if (registro.api.ambiente !== 'development') throw new Error(`API não é dev: ${registro.api.ambiente}`);
  const { ctx, page } = await entrar(browser);
  page.on('pageerror', e => anotar('*', 'erro na página', { erro: String(e) }));
  await caso22(page);
  await casoComOrcamento(page, '#23', 65);
  const p25 = await casoComOrcamento(page, '#25', 66);
  await renegociar(page, '#25', 66, p25);
  await ctx.close();
  registro.resultado = 'ok';
} catch (e) {
  registro.resultado = 'falhou';
  registro.erro = String(e?.stack ?? e);
  process.exitCode = 1;
} finally {
  registro.fim = new Date().toISOString();
  await browser.close();
  process.stdout.write(JSON.stringify(registro, null, 2) + '\n');
}
