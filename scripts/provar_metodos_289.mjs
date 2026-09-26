// Prova em dev, no navegador: métodos e preços do tenant (#282) e o motor comparado pelo conteúdo (#289).
//
// Nos casos #23 e #25 do gate (processos 65 e 66, tenant 33), pela tela:
//  1. #289 — "Gerar pelo motor" de novo, sem fato novo: execução nova, e o escopo e o orçamento
//     aprovados CONTINUAM atuais; no #25 o alerta crítico sai com a ciência herdada, sem pedir outra.
//  2. #282 — em Configurações › Métodos e preços, muda o preço do método que o caso usa (versão
//     nova); o orçamento do caso sai desatualizado com o motivo; gera a versão nova com o preço novo,
//     aprova, cria a proposta; recarga e nova sessão leem o mesmo estado.
//  Os preços novos ficam no dev (devolvê-los desatualizaria de novo o orçamento aprovado).
//
// Só dev (recusa se a API não disser `development`). O registro guarda IDs, estados, totais e
// hashes, nunca texto dos casos. Uso: PROVA_EMAIL=... PROVA_SENHA=... node scripts/provar_metodos_289.mjs
import { createHash } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');

const BASE = process.env.PROVA_BASE ?? 'http://127.0.0.1:5182';
const { PROVA_EMAIL: EMAIL, PROVA_SENHA: SENHA } = process.env;
const CAPTURAS = process.env.PROVA_CAPTURAS ?? null;
if (!EMAIL || !SENHA) throw new Error('PROVA_EMAIL e PROVA_SENHA são obrigatórios');
if (CAPTURAS) mkdirSync(CAPTURAS, { recursive: true });

const h = s => createHash('sha256').update(s ?? '').digest('hex').slice(0, 16);
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

async function comercial(page, pid) {
  const leitura = Promise.all([
    page.waitForResponse(r => r.url().includes(`/processes/${pid}/comercial/redacao`) && r.request().method() === 'GET'),
    page.waitForResponse(r => r.url().includes(`/processes/${pid}/comercial/orcamento`) && r.request().method() === 'GET'),
  ]);
  await page.goto(`${BASE}/processes/${pid}?tab=commercial`);
  const [red, orc] = await leitura;
  await page.getByTestId('comercial-rota').waitFor();
  return { red: await red.json(), orc: (await orc.json()).orcamento };
}

/** Parte 1 (#289): motor de novo sem fato novo; nada desatualiza, ciência herdada. */
async function motorSemFatoNovo(page, caso, pid) {
  const antes = await comercial(page, pid);
  await page.goto(`${BASE}/processes/${pid}`);
  await page.getByRole('button', { name: /Caminho Regulatório/ }).first().click();
  await page.getByRole('button', { name: 'Ações', exact: true }).click();
  await page.getByText('Rota Regulatória', { exact: true }).waitFor();
  const m = await gesto(page, 'POST', `/processes/${pid}/rota/gerar-motor`,
    () => page.getByRole('button', { name: 'Gerar pelo motor' }).first().click(), 201);
  const ex = m.corpo.execucao;
  await page.locator(`[data-evidencia="execucao_motor:${ex.execucao_id}"]`).waitFor();
  const alertas = ex.avaliacoes.filter(a => a.efeitos.some(e => e.tipo === 'alerta_critico'))
    .map(a => ({ rule_id: a.rule_id, avaliacao: a.avaliacao_id, ciencia: a.ciencia }));
  anotar(caso, 'Gerar pelo motor sem fato novo', { execucao: ex.execucao_id, fatos_hash: ex.fatos_hash.slice(0, 16),
    alertas_sem_ciencia: ex.alertas_sem_ciencia, alertas });
  if (ex.alertas_sem_ciencia.length) throw new Error('ciência reaberta sem mudança de conteúdo');
  for (const a of alertas) {
    await page.getByTestId(`avaliacao-${a.rule_id}`).getByText(/ciência de execução anterior|ciência registrada/).waitFor();
  }
  await capturar(page, `${caso}-motor-sem-fato-novo`);

  const depois = await comercial(page, pid);
  const estados = {
    escopo: depois.red.especificacao_escopo.atualidade, relatorio: depois.red.relatorio_preliminar.atualidade,
    orcamento: depois.orc.atualidade,
  };
  anotar(caso, 'cadeia comercial depois (tela)', { orcamento: depois.orc.id, escopo: depois.red.especificacao_escopo.id,
    antes_orcamento: antes.orc.id, estados });
  if (Object.values(estados).some(a => a.estado !== 'vigente')) throw new Error('reexecução desatualizou a cadeia');
  await page.getByTestId('selos-orcamento').getByText('Atual').waitFor();
  await rodape(page, caso, 'Comercial');
  return depois;
}

async function mudarPreco(page, caso, codigo, nome, valor) {
  await page.goto(`${BASE}/settings?tab=metodos`);
  await page.getByTestId('metodos-precos').waitFor();
  await rodape(page, caso, 'Métodos e preços');
  await page.getByRole('button', { name: `Editar ${nome}` }).click();
  const form = page.getByTestId('form-metodo');
  await form.getByLabel('Valor unitário (R$)').fill(valor);
  const r = await gesto(page, 'POST', '/comercial/metodos',
    () => form.getByRole('button', { name: 'Salvar nova versão' }).click(), 201);
  await page.getByTestId(`preco-${codigo}`).filter({ hasText: Number(valor).toLocaleString('pt-BR', { minimumFractionDigits: 2 }) }).waitFor();
  anotar(caso, 'preço mudado na tela', { codigo, versao: r.corpo.versao, valor: r.corpo.valor_unitario });
  await capturar(page, `${caso}-metodos-${codigo}-v${r.corpo.versao}`);
  return r.corpo;
}

async function orcamentoComPrecoNovo(page, caso, pid, codigo) {
  const { orc } = await comercial(page, pid);
  anotar(caso, 'orçamento depois do preço novo (tela)', { id: orc.id, versao: orc.versao, atualidade: orc.atualidade });
  if (orc.atualidade.estado !== 'desatualizado' || !orc.atualidade.motivos.some(m => m.includes(`"${codigo}"`))) {
    throw new Error('orçamento não saiu desatualizado pelo método');
  }
  await page.getByTestId('orcamento').getByRole('alert').filter({ hasText: codigo }).waitFor();
  const card = page.getByTestId('orcamento');
  const o = (await gesto(page, 'POST', `/processes/${pid}/comercial/orcamento`,
    () => page.getByRole('button', { name: /^Gerar .*orçamento$/ }).click(), 201)).corpo;
  await card.getByText(`v${o.versao} · #${o.id}`).waitFor();
  anotar(caso, 'orçamento regerado com o preço novo (tela)', { id: o.id, versao: o.versao, total: o.total,
    itens: o.itens.map(i => ({ passo: i.rota_passo_id, metodo: `${i.metodo.codigo} v${i.metodo.versao}`, total: i.total })) });
  await card.getByLabel(/Revisão do orçamento/).fill('PROVA #282: preço novo conferido na tela');
  const ap = await gesto(page, 'POST', `/orcamento/${o.id}/revisar`,
    () => card.getByRole('button', { name: 'Aprovar orçamento' }).click(), 200);
  const p = await gesto(page, 'POST', '/proposals/',
    () => card.getByRole('button', { name: 'Criar proposta deste orçamento' }).click(), 201);
  await page.waitForURL(`**/proposals/${p.corpo.id}`);
  anotar(caso, 'proposta do orçamento com preço novo (tela)', { orcamento: ap.corpo.id, estado: ap.corpo.estado_revisao,
    proposta: p.corpo.id, total_value: p.corpo.total_value, orcamento_total: ap.corpo.total });
  if (Number(p.corpo.total_value) !== Number(ap.corpo.total) || p.corpo.orcamento_id !== ap.corpo.id) {
    throw new Error('proposta não nasceu do orçamento');
  }
  await capturar(page, `${caso}-proposta-preco-novo`);
  return ap.corpo;
}

async function reler(page, caso, pid, orc, rotulo) {
  const { orc: lido } = await comercial(page, pid);
  await rodape(page, caso, `Comercial (${rotulo})`);
  anotar(caso, `${rotulo}: mesmo estado`, { orcamento: lido.id, estado: lido.estado_revisao,
    atualidade: lido.atualidade.estado, total: lido.total });
  if (lido.id !== orc.id || lido.estado_revisao !== 'aprovada' || lido.atualidade.estado !== 'vigente') {
    throw new Error(`${rotulo} leu outro estado`);
  }
}

const CASOS = [
  { caso: '#23', pid: 65, codigo: 'ccir', nome: 'Emissão/regularização de CCIR', novo: '950.00' },
  { caso: '#25', pid: 66, codigo: 'inscricao_car', nome: 'Inscrição no CAR', novo: '1900.00' },
];

const browser = await chromium.launch();
try {
  registro.api = await (await fetch(`${BASE}/api/v1/versao`)).json();
  if (registro.api.ambiente !== 'development') throw new Error(`API não é dev: ${registro.api.ambiente}`);
  for (const c of CASOS) {
    const { ctx, page } = await entrar(browser);
    page.on('pageerror', e => anotar(c.caso, 'erro na página', { erro: String(e) }));
    await motorSemFatoNovo(page, c.caso, c.pid);
    await mudarPreco(page, c.caso, c.codigo, c.nome, c.novo);
    const orc = await orcamentoComPrecoNovo(page, c.caso, c.pid, c.codigo);
    await reler(page, c.caso, c.pid, orc, 'recarga');
    await ctx.close();
    const nova = await entrar(browser);
    await reler(nova.page, c.caso, c.pid, orc, 'nova sessão');
    await nova.ctx.close();
  }
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
