// Prova em dev, no navegador, das telas do motor jurídico (#278) e do fechamento comercial (#282).
//
// Percurso completo PELA TELA nos casos #23 e #25 do gate (processos 65 e 66, tenant 33): gerar a
// Rota pelo motor, ler o relatório da execução, registrar ciência de alerta, abrir a fonte do passo
// por ID, remover passo com motivo, gerar relatório e escopo, abrir evidência, rejeitar/aprovar,
// gerar orçamento, trocar o método de um passo, aprovar, criar a proposta do orçamento, recarregar
// e abrir nova sessão. Cada gesto espera a resposta HTTP da API e registra status e IDs.
//
// Só dev: recusa rodar se a API não disser `development`. O registro guarda IDs, estados,
// contagens, totais e hashes — nunca o texto dos casos (texto de produção fica no banco de dev).
// Capturas de tela vão para PROVA_CAPTURAS (fora do repositório).
//
// Uso: PROVA_EMAIL=... PROVA_SENHA=... PROVA_BASE=http://127.0.0.1:5182 \
//      node scripts/provar_telas_282_278.mjs > registro.json
import { createHash } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');

const BASE = process.env.PROVA_BASE ?? 'http://127.0.0.1:5182';
const EMAIL = process.env.PROVA_EMAIL;
const SENHA = process.env.PROVA_SENHA;
const CAPTURAS = process.env.PROVA_CAPTURAS ?? null;
if (!EMAIL || !SENHA) throw new Error('PROVA_EMAIL e PROVA_SENHA são obrigatórios');
if (CAPTURAS) mkdirSync(CAPTURAS, { recursive: true });

const h = s => createHash('sha256').update(s ?? '').digest('hex').slice(0, 16);
const registro = { inicio: new Date().toISOString(), base: BASE, passos: [] };
const anotar = (caso, passo, dados = {}) => {
  registro.passos.push({ caso, passo, ...dados });
  process.stderr.write(`[${caso}] ${passo} ${JSON.stringify(dados)}\n`);
};

async function capturar(page, nome) {
  if (CAPTURAS) await page.screenshot({ path: `${CAPTURAS}/${nome}.png`, fullPage: true });
}

/** Clica e espera a resposta da API que o gesto dispara; devolve status e corpo. */
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

async function abrirRota(page, pid) {
  await page.goto(`${BASE}/processes/${pid}`);
  await page.getByRole('button', { name: /Caminho Regulatório/ }).first().click();
  await page.getByRole('button', { name: 'Ações', exact: true }).click();
  await page.getByText('Rota Regulatória', { exact: true }).waitFor();
}

/** Lê o painel da evidência na TELA (o detalhe pode vir do cache, sem requisição nova). */
async function lerPainel(painel) {
  const det = painel.getByTestId('evidencia-detalhe');
  await det.waitFor();
  const titulo = (await det.locator('p.font-semibold').first().textContent()).trim();
  const texto = det.locator('p.whitespace-pre-wrap');
  return {
    titulo_hash: h(titulo),
    texto_chars: (await texto.count()) ? (await texto.textContent()).length : 0,
    campos: await det.locator('dt').count(),
    refs: await det.locator('button[data-evidencia]').allTextContents(),
    abre_documento: (await det.getByRole('button', { name: 'Abrir o documento' }).count()) > 0,
  };
}

async function abrirEvidencia(page, caso, chip, rotulo) {
  const alvo = await chip.getAttribute('data-evidencia');
  const [tipo, id] = alvo.split(':');
  await chip.click();
  const painel = page.getByRole('dialog', { name: 'Evidência' });
  await painel.getByText(new RegExp(`#${id}$`)).first().waitFor();
  const dados = { tipo, id: Number(id), ...(await lerPainel(painel)) };
  // Segue a primeira referência que o próprio detalhe cita, e volta.
  const citas = painel.getByTestId('evidencia-detalhe').locator('button[data-evidencia]');
  if (await citas.count()) {
    await citas.first().click();
    await painel.getByRole('button', { name: /voltar/ }).waitFor();
    dados.seguiu = await lerPainel(painel);
    await painel.getByRole('button', { name: /voltar/ }).click();
    await painel.getByText(new RegExp(`#${id}$`)).first().waitFor();
  }
  await capturar(page, `${caso}-evidencia-${rotulo}`);
  await painel.getByRole('button', { name: 'Fechar evidência' }).click();
  anotar(caso, `evidência aberta (${rotulo})`, dados);
}

async function percursoRota(page, caso, pid, remover) {
  await abrirRota(page, pid);
  await rodape(page, caso, 'Rota');

  const motor = await gesto(page, 'POST', `/processes/${pid}/rota/gerar-motor`,
    () => page.getByRole('button', { name: 'Gerar pelo motor' }).first().click(), 201);
  const ex = motor.corpo.execucao;
  anotar(caso, 'Gerar pelo motor', { status: motor.status, execucao: ex.execucao_id, avaliadas: ex.avaliacoes.length,
    contagem: ex.contagem, alertas_sem_ciencia: ex.alertas_sem_ciencia, created: motor.corpo.rota.created,
    suprimidos: motor.corpo.rota.suprimidos, rota_status: motor.corpo.rota.rota.status });
  // A execução nova tem de chegar à tela (não a anterior, do cache): espera o chip dela.
  await page.locator(`[data-evidencia="execucao_motor:${ex.execucao_id}"]`).waitFor();
  await page.getByTestId('motor-avaliadas').filter({ hasText: `${ex.avaliacoes.length} regra(s)` }).waitFor();
  const indeterminadas = ex.avaliacoes.filter(a => a.estado === 'indeterminado')
    .map(a => ({ rule_id: a.rule_id, faltantes: a.faltantes }));
  const semFundamento = ex.avaliacoes.filter(a => !a.fundamento.dispositivo_id)
    .map(a => ({ rule_id: a.rule_id, razao: a.fundamento.razao }));
  anotar(caso, 'relatório da execução na tela', { indeterminadas, sem_fundamento: semFundamento });

  for (const avId of ex.alertas_sem_ciencia) {
    const linha = page.locator('li', { has: page.locator(`#ciencia-${avId}`) });
    const botao = linha.getByRole('button', { name: 'Registrar ciência' });
    if (!(await botao.isDisabled())) throw new Error('ciência sem justificativa habilitada');
    await page.locator(`#ciencia-${avId}`).fill(`PROVA #282/#278 — ciência registrada pela tela (${caso})`);
    const c = await gesto(page, 'POST', `/motor/alertas/${avId}/ciencia`, () => botao.click(), 201);
    anotar(caso, 'ciência do alerta crítico', { avaliacao: avId, ciencia: c.corpo.id });
  }
  await page.waitForFunction(() => !document.body.innerText.includes('sem ciência — a Rota não fecha'));
  await capturar(page, `${caso}-rota-motor`);

  const fonte = page.locator('[data-testid^="fonte-passo-"] [data-evidencia^="dispositivo:"]').first();
  await abrirEvidencia(page, caso, fonte, 'fundamento-do-passo');

  if (remover.titulo) {
    await page.getByRole('button', { name: new RegExp(`^Remover passo \\d+: ${remover.titulo}`) }).click();
    const confirmar = page.getByRole('button', { name: 'Remover da rota' });
    const bloqueado = await confirmar.isDisabled();
    await page.getByLabel(/Motivo da remoção/).fill(remover.motivo);
    const d = await gesto(page, 'DELETE', '/passos/', () => confirmar.click(), 204);
    anotar(caso, 'passo do motor removido com motivo', { titulo: remover.titulo, sem_motivo_bloqueado: bloqueado,
      status: d.status, motivo_hash: h(remover.motivo) });
  } else {
    // Só o gesto de travamento: o único passo cobrado não sai (o escopo ficaria vazio).
    const botao = page.getByRole('button', { name: /^Remover passo 1:/ });
    await botao.click();
    const bloqueado = await page.getByRole('button', { name: 'Remover da rota' }).isDisabled();
    await page.getByRole('button', { name: 'Cancelar' }).click();
    anotar(caso, 'remover passo do motor sem motivo fica bloqueado', { sem_motivo_bloqueado: bloqueado });
    if (!bloqueado) throw new Error('remoção de passo do motor sem motivo habilitada');
  }

  // Passos novos (se o motor trouxe) são classificados e validados; a Rota é reassinada se preciso.
  const pendentes = page.getByRole('button', { name: 'Validar passo' });
  while (await pendentes.count()) {
    const card = page.locator('li').filter({ has: pendentes.first() });
    await card.getByRole('button', { name: 'Item de proposta' }).click();
    await gesto(page, 'POST', '/validar', () => pendentes.first().click(), 200);
  }
  const fechar = page.getByRole('button', { name: 'Fechar rota' });
  if (await fechar.count()) {
    const f = await gesto(page, 'POST', '/fechar', () => fechar.click(), 200);
    anotar(caso, 'Rota reassinada', { status: f.corpo.status });
  }
  await page.getByText('Rota assinada — registrada na trilha de auditoria.').waitFor();
}

async function lerComercial(page) {
  const [red, orc] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/comercial/redacao') && r.request().method() === 'GET'),
    page.waitForResponse(r => r.url().includes('/comercial/orcamento') && r.request().method() === 'GET'),
  ]);
  return { red: await red.json(), orc: await orc.json() };
}

async function revisar(page, caso, card, rotulo, acao, justificativa, rota) {
  await card.getByLabel(new RegExp(`Revisão do ${rotulo}`)).fill(justificativa);
  const nome = `${acao === 'aprovar' ? 'Aprovar' : 'Rejeitar'} ${rotulo}`;
  const r = await gesto(page, 'POST', rota, () => card.getByRole('button', { name: nome }).click(), 200);
  anotar(caso, `${nome} (tela)`, { id: r.corpo.id, versao: r.corpo.versao, estado_revisao: r.corpo.estado_revisao,
    atualidade: r.corpo.atualidade.estado });
  return r.corpo;
}

async function percursoComercial(page, caso, pid, opcoes) {
  const leitura = lerComercial(page);
  await page.getByRole('button', { name: 'Relatório, escopo e orçamento →' }).click();
  const { orc } = await leitura;
  await page.getByTestId('comercial-rota').waitFor();
  await rodape(page, caso, 'Comercial');
  anotar(caso, 'orçamento antes (tela)', { id: orc.orcamento?.id, versao: orc.orcamento?.versao,
    atualidade: orc.orcamento?.atualidade, total: orc.orcamento?.total });
  if (orc.orcamento?.atualidade.estado === 'desatualizado') {
    await page.getByTestId('orcamento').getByRole('alert').waitFor();
  }
  await capturar(page, `${caso}-comercial-antes`);

  const gerarDocs = async () => {
    const g = await gesto(page, 'POST', `/processes/${pid}/comercial/redacao`,
      () => page.getByRole('button', { name: /^Gerar .*relatório e escopo$/ }).click(), 201);
    const rel = g.corpo.relatorio_preliminar, esc = g.corpo.especificacao_escopo;
    const afirmacoes = d => d.conteudo.secoes.flatMap(s => s.afirmacoes);
    anotar(caso, 'Gerar relatório e escopo (tela)', {
      relatorio: { id: rel.id, versao: rel.versao, afirmacoes: afirmacoes(rel).length,
        evidencias: afirmacoes(rel).reduce((n, a) => n + a.evidencias.length, 0) },
      escopo: { id: esc.id, versao: esc.versao, afirmacoes: afirmacoes(esc).length,
        fora: esc.conteudo.secoes.find(s => s.chave === 'fora').afirmacoes.length },
    });
    await page.getByTestId('redacao-relatorio_preliminar').getByText(`v${rel.versao} · #${rel.id}`).waitFor();
    return { rel, esc };
  };

  let { rel, esc } = await gerarDocs();
  const cardRel = () => page.getByTestId('redacao-relatorio_preliminar');
  const cardEsc = () => page.getByTestId('redacao-especificacao_escopo');
  await abrirEvidencia(page, caso, cardRel().locator('[data-evidencia^="avaliacao_regra:"]').first(), 'afirmação-do-relatório');
  const docChip = cardRel().locator('[data-evidencia^="documento:"]').first();
  if (await docChip.count()) await abrirEvidencia(page, caso, docChip, 'documento-do-relatório');
  await abrirEvidencia(page, caso, cardEsc().locator('[data-evidencia^="dispositivo:"]').first(), 'fundamento-do-escopo');

  if (opcoes.rejeitarRelatorio) {
    await revisar(page, caso, cardRel(), 'relatório', 'rejeitar',
      'PROVA #282: rejeitado pela tela para exercer a correção', `/redacao/${rel.id}/revisar`);
    await page.getByTestId('selos-relatorio_preliminar').getByText('Rejeitado').waitFor();
    ({ rel, esc } = await gerarDocs());
  }
  await revisar(page, caso, cardRel(), 'relatório', 'aprovar', 'PROVA #282: relatório conferido na tela',
    `/redacao/${rel.id}/revisar`);
  await revisar(page, caso, cardEsc(), 'escopo', 'aprovar', 'PROVA #282: escopo conferido na tela',
    `/redacao/${esc.id}/revisar`);
  await capturar(page, `${caso}-redacao-aprovada`);

  let o = (await gesto(page, 'POST', `/processes/${pid}/comercial/orcamento`,
    () => page.getByRole('button', { name: /^Gerar .*orçamento$/ }).click(), 201)).corpo;
  anotar(caso, 'Gerar orçamento (tela)', { id: o.id, versao: o.versao, total: o.total,
    itens: o.itens.map(i => ({ passo: i.rota_passo_id, metodo: i.metodo.codigo, escolha: i.escolha, total: i.total })),
    fora: o.fora.map(f => ({ passo: f.rota_passo_id, motivo_hash: h(f.motivo) })),
    ressalvas: o.ressalvas.map(r => ({ tipo: r.tipo, conclusoes: r.conclusoes?.length ?? 0 })) });
  const card = () => page.getByTestId('orcamento');
  await card().getByText(`v${o.versao} · #${o.id}`).waitFor();
  const foraNaTela = await card().getByTestId('orcamento-fora').locator('li').count();
  anotar(caso, '"fora" com motivo na tela', { itens_fora: foraNaTela });

  if (opcoes.trocarMetodo) {
    const passo = o.itens[0].rota_passo_id;
    const original = o.itens[0].metodo.codigo;
    for (const codigo of [opcoes.trocarMetodo, original]) {
      o = (await gesto(page, 'PATCH', `/orcamento/passos/${passo}`,
        () => card().getByLabel(`Método do passo ${passo}`).selectOption(codigo), 201)).corpo;
      await card().getByText(`v${o.versao} · #${o.id}`).waitFor();
      anotar(caso, 'método do passo trocado (tela)', { passo, metodo: codigo, versao: o.versao, total: o.total,
        escolha: o.itens.find(i => i.rota_passo_id === passo).escolha });
    }
  }
  const aprovado = await revisar(page, caso, card(), 'orçamento', 'aprovar', 'PROVA #282: preços conferidos na tela',
    `/orcamento/${o.id}/revisar`);
  await capturar(page, `${caso}-orcamento-aprovado`);

  const p = await gesto(page, 'POST', '/proposals/',
    () => card().getByRole('button', { name: 'Criar proposta deste orçamento' }).click(), 201);
  await page.waitForURL(`**/proposals/${p.corpo.id}`);
  anotar(caso, 'proposta criada do orçamento (tela)', { proposta: p.corpo.id, orcamento_id: p.corpo.orcamento_id,
    total_value: p.corpo.total_value, itens: p.corpo.scope_items.length, orcamento_total: aprovado.total });
  if (p.corpo.orcamento_id !== aprovado.id || Number(p.corpo.total_value) !== Number(aprovado.total)) {
    throw new Error('proposta não nasceu do orçamento aprovado');
  }
  await page.getByText(`do orçamento #${aprovado.id}`).waitFor();
  await capturar(page, `${caso}-proposta`);
  return { orcamento: aprovado, proposta: p.corpo.id, relatorio: rel.id, escopo: esc.id };
}

async function reler(page, caso, pid, esperado, rotulo) {
  const leitura = lerComercial(page);
  await page.goto(`${BASE}/processes/${pid}?tab=commercial`);
  const { red, orc } = await leitura;
  await page.getByTestId('orcamento').getByText(`v${orc.orcamento.versao} · #${orc.orcamento.id}`).waitFor();
  await rodape(page, caso, `Comercial (${rotulo})`);
  const lido = { orcamento: orc.orcamento.id, estado: orc.orcamento.estado_revisao,
    atualidade: orc.orcamento.atualidade.estado, total: orc.orcamento.total,
    relatorio: red.relatorio_preliminar.id, relatorio_estado: red.relatorio_preliminar.estado_revisao,
    escopo: red.especificacao_escopo.id, escopo_estado: red.especificacao_escopo.estado_revisao };
  anotar(caso, `${rotulo}: mesmo estado`, lido);
  if (lido.orcamento !== esperado.orcamento.id || lido.estado !== 'aprovada' || lido.atualidade !== 'vigente'
      || lido.relatorio !== esperado.relatorio || lido.escopo !== esperado.escopo) {
    throw new Error(`${rotulo} leu outro estado`);
  }
}

const CASOS = [
  { caso: '#23', pid: 65, remover: { titulo: 'Mapear os componentes do imóvel',
      motivo: 'PROVA #278: orientação já dada ao cliente na reunião de entrada; sai da Rota' },
    rejeitarRelatorio: true },
  { caso: '#25', pid: 66, remover: {}, trocarMetodo: 'hora_tecnica' },
];

const browser = await chromium.launch();
try {
  const api = await (await fetch(`${BASE}/api/v1/versao`)).json();
  registro.api = api;
  if (api.ambiente !== 'development') throw new Error(`API não é dev: ${api.ambiente}`);
  for (const c of CASOS) {
    const { ctx, page } = await entrar(browser);
    page.on('pageerror', e => anotar(c.caso, 'erro na página', { erro: String(e) }));
    await percursoRota(page, c.caso, c.pid, c.remover);
    const fim = await percursoComercial(page, c.caso, c.pid, c);
    await reler(page, c.caso, c.pid, fim, 'recarga');
    await ctx.close();
    const nova = await entrar(browser);
    await reler(nova.page, c.caso, c.pid, fim, 'nova sessão');
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
