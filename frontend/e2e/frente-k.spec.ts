/**
 * Gate de NAVEGADOR ÚNICO — Frente K.
 *
 * A camada de UI da Frente J tinha 5 testes; cada um abria a sua sessão e
 * trabalhava sobre um processo que o gate de API já havia populado. Isso prova
 * cliques, não prova o PERCURSO: nada garantia que a consultora, sozinha,
 * partindo de um caso vazio, chegasse à base gravada.
 *
 * Aqui é UM teste, UMA sessão, e nenhum estado pré-produzido pela API:
 *
 *   login → checklist gerado PELA APLICAÇÃO → upload dos 6 pela TELA → extração
 *   real → Conferência → decidir (inclusive RECLASSIFICAR) → "Gravar na base"
 *   → F5 → logout/login → rota gerada → documento novo → rota desatualizada.
 *
 * E os seis números são lidos do DOM, nunca de `fetch`: a régua não é "o serviço
 * sabe", é "a tela mostra". Onde um número não existia na tela (o total de
 * linhas lidas), a tela passou a mostrá-lo — não o teste a buscá-lo por baixo.
 *
 * O único HTTP aqui é SINCRONIZAÇÃO (esperar a extração real terminar e ler a
 * macroetapa corrente), nunca medição.
 *
 * Pré-condição: pilha do gate de pé (API + worker + Redis + MinIO + Postgres
 * descartável) e as variáveis:
 *   E2E_SEED_JSON   caminho do JSON impresso por tests/e2e/frente_j/setup_db.py
 *   E2E_API_URL     ex. http://127.0.0.1:8010
 *   E2E_PDFS_DIR    pasta com os 6 PDFs da ELODI
 *   E2E_PRINTS_DIR  onde salvar prints e payloads do relatório
 */
import { expect, test, type Locator, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const seed = JSON.parse(fs.readFileSync(process.env.E2E_SEED_JSON!, 'utf-8')) as {
  email: string; password: string; process_id: number; client_id: number; property_id: number;
};
const API = (process.env.E2E_API_URL ?? 'http://127.0.0.1:8010') + '/api/v1';
const PRINTS = process.env.E2E_PRINTS_DIR ?? path.join('e2e-results', 'prints-k');
const PDFS = process.env.E2E_PDFS_DIR ?? '';
fs.mkdirSync(PRINTS, { recursive: true });

/** Os 6 da ELODI, com o tipo que a consultora escolhe no seletor da tela. */
const DOCS: Array<{ arquivo: string; tipo: string }> = [
  { arquivo: 'CAR FAZ B1 B2 B3 E BA - ELODI 2016.pdf', tipo: 'car' },
  { arquivo: "B1 - M3.181 - FAZ. R. Olhos d'agua - Elodi 2013 926ha.pdf", tipo: 'matricula' },
  { arquivo: 'B2 - M3.313 - FAZ. NH 2 - Elodi 2014 725ha.pdf', tipo: 'matricula' },
  { arquivo: 'B3 - M3.673 - FAZ Posse G4 - Elodi 2016 212ha.pdf', tipo: 'matricula' },
  { arquivo: 'B4 - M4.387 - FAZ Posse G3 - Elodi 2020 316ha.pdf', tipo: 'matricula' },
  { arquivo: 'CNH-e.pdf.pdf', tipo: 'doc_pessoal' },
];

/** Os rótulos que a tela usa (DecisoesPanel.ESTADO_LABEL) — a régua é a tela. */
const PENDENTE = 'Pendente';
const AGUARDANDO_GRAVACAO = 'Decidida — aguardando gravação';

const registro: Record<string, unknown> = {};

async function login(page: Page) {
  await page.goto('/login');
  await page.getByPlaceholder('seu@email.com').fill(seed.email);
  await page.getByPlaceholder('••••••••').fill(seed.password);
  await page.getByRole('button', { name: 'Acessar Plataforma' }).click();
  await page.waitForURL(/\/dashboard|\/processes/);
}

async function logout(page: Page) {
  await page.getByRole('button', { name: 'Sair do sistema' }).click();
  await page.waitForURL(/\/login/);
}

async function print(page: Page, nome: string) {
  await page.screenshot({ path: path.join(PRINTS, `k_${nome}.png`), fullPage: true });
}

async function abrirAba(page: Page, aba: string) {
  await page.getByRole('button', { name: aba, exact: true }).first().click();
}

/** Abre o cartão de decisão SE ele estiver fechado — o clique é um toggle, e
 *  o cartão nasce aberto quando as fontes não concordam. */
async function expandirCartao(cartao: Locator, alvo: Locator) {
  if (await alvo.count() === 0) await cartao.locator('button').first().click();
}

/** HTTP só para SINCRONIZAR — nunca para medir os seis números. */
async function http<T>(page: Page, p: string): Promise<T | null> {
  const raw = await page.evaluate(() => localStorage.getItem('auth-storage'));
  const token = raw ? (JSON.parse(raw)?.state?.token ?? '') : '';
  const r = await page.request.fetch(API + p, {
    method: 'GET', headers: { Authorization: `Bearer ${token}` },
  });
  try { return (await r.json()) as T; } catch { return null; }
}

/**
 * Os SEIS números, cada um lido de um elemento da tela.
 *
 * Se um deles deixar de existir no DOM o teste falha aqui — que é o ponto: a
 * tela tem de mostrar o que o serviço sabe.
 */
async function seisNumerosDoDOM(page: Page, documentos: number): Promise<Record<string, string>> {
  await abrirAba(page, 'Documentos');
  await expect(page.getByTestId('checklist-resumo')).toBeVisible({ timeout: 60_000 });
  const checklist = (await page.getByTestId('checklist-resumo').innerText()).trim();
  // `allInnerTexts()` não espera: numa lista ainda carregando ele devolve []
  // sem reclamar. Foi assim que a primeira comparação F5 acusou diferença que
  // não existia — "" antes, os 6 selos depois. Ler do DOM exige esperar o DOM.
  await expect.poll(async () => page.getByTestId('doc-lifecycle').count(),
    { timeout: 60_000, message: 'a lista de documentos não terminou de carregar' },
  ).toBe(documentos);
  const estadoDosDocumentos = (await page.getByTestId('doc-lifecycle').allInnerTexts())
    .map(t => t.trim()).sort().join(' · ');

  await abrirAba(page, 'Conferência');
  await expect(page.getByRole('button', { name: /Gravar na base/ })).toBeVisible({ timeout: 60_000 });
  const progresso = (await page.getByTestId('conferencia-progresso').innerText()).trim();
  const decisoes = (await page.getByTestId('decisoes-total').innerText()).trim();
  const linhas = (await page.getByTestId('conferencia-rodape').innerText()).trim();
  const estadoDasDecisoes = (await page.getByTestId('decisao-estado').allInnerTexts())
    .map(t => t.trim()).sort().join(' · ');

  return {
    'quantos documentos entraram (checklist)': checklist,
    'quanto da Conferência está resolvido': progresso,
    'quantas decisões a Conferência agrupa': decisoes,
    'quantas linhas de staging existem': linhas,
    'estado de cada documento (DOC-001)': estadoDosDocumentos,
    'estado de cada decisão': estadoDasDecisoes,
  };
}

test('Frente K — um navegador, uma sessão: da tela vazia à base gravada', async ({ page }) => {
  test.skip(!PDFS, 'E2E_PDFS_DIR não informado — o percurso sobe os 6 documentos pela tela');
  test.setTimeout(60 * 60 * 1000); // extração real (LLM) + rota real

  const pid = seed.process_id;

  // ── 1. login pela tela ────────────────────────────────────────────────
  await login(page);
  await page.goto(`/processes/${pid}?tab=documents`);
  await expect(page.getByRole('button', { name: 'Documentos', exact: true }).first())
    .toBeVisible({ timeout: 60_000 });

  // ── 2. o caso começa VAZIO (nada pré-produzido pela API) ──────────────
  await expect(page.getByTestId('doc-lifecycle')).toHaveCount(0);
  await print(page, '01_caso_vazio');

  // ── 3. o checklist nasce da APLICAÇÃO, não do seed ────────────────────
  // O gate da J declarou `checklist_documental: null` como fronteira: o
  // processo nascia do seed sem `ProcessChecklist`. Aqui a consultora clica.
  await page.getByRole('button', { name: 'Gerar Checklist' }).click();
  await expect(page.getByTestId('checklist-resumo')).toBeVisible({ timeout: 60_000 });
  registro.checklist_criado_pela_tela = (await page.getByTestId('checklist-resumo').innerText()).trim();
  await print(page, '02_checklist_gerado');

  // ── 4. os 6 documentos entram pela TELA, um a um, com o seu tipo ──────
  for (const [i, doc] of DOCS.entries()) {
    await page.locator('select').first().selectOption(doc.tipo);
    await page.locator('input[type="file"]').first().setInputFiles(path.join(PDFS, doc.arquivo));
    await expect.poll(
      async () => page.getByTestId('doc-lifecycle').count(),
      { timeout: 120_000, message: `documento ${doc.arquivo} não apareceu na lista` },
    ).toBe(i + 1);
  }
  await print(page, '03_seis_documentos');

  // ── 5. a extração real termina (sincronização, não medição) ───────────
  // OCR pronto NÃO é extração pronta: o OCR (pypdf) leva segundos e a extração
  // (LLM) leva minutos, em tarefa separada. Esperar só pelo `ocr_status` libera
  // a Conferência no meio do caminho — e aí a lista de decisões CRESCE durante
  // o teste, que é como a primeira versão deste gate falhou (17 → 19 cartões
  // pendentes entre um clique e a verificação seguinte). O critério é o mesmo
  // do gate da J: cada documento com texto tem de ter staging OU um
  // `extraction_status` dizendo por que não tem.
  await expect.poll(async () => {
    const docs = await http<Array<{
      id: number; ocr_status: string | null; tem_texto: boolean; extraction_status: string | null;
    }>>(page, `/documents/?process_id=${pid}`);
    if (!docs || docs.length !== DOCS.length) return false;
    const staging = await http<Array<{ document_id: number | null }>>(
      page, `/processes/${pid}/staging-fields`);
    const comStaging = new Set((staging ?? []).map(f => f.document_id));
    return docs.every(d =>
      !!d.ocr_status && !['pending', 'processing'].includes(d.ocr_status)
      && (!d.tem_texto || comStaging.has(d.id) || !!d.extraction_status));
  }, { timeout: 40 * 60 * 1000, intervals: [10_000] }).toBe(true);

  await abrirAba(page, 'Conferência');
  await expect(page.getByTestId('decisoes-total')).toBeVisible({ timeout: 10 * 60 * 1000 });
  registro.apos_extracao = await seisNumerosDoDOM(page, DOCS.length);
  await abrirAba(page, 'Conferência');
  await print(page, '04_conferencia');

  // ── 6. RECLASSIFICAR: a consultora corrige o tipo que o modelo sugeriu ─
  // Gravame → gravame: exercita o gesto sem inventar fato (ADR-065).
  const cartaoGravame = page.locator('[data-testid^="decisao-"][data-testid$="-gravames"]').first();
  await expect(cartaoGravame).toBeVisible();
  const testidGravame = await cartaoGravame.getAttribute('data-testid');
  const seletorEvidencia = cartaoGravame.getByLabel('Evidência a editar');
  await expandirCartao(cartaoGravame, seletorEvidencia);
  await expect(seletorEvidencia).toBeVisible();
  // A linha AGREGADA de ônus também é evidência desta decisão (Frente K) — mas
  // ela não é um ato, e reclassificar um consolidado não faria sentido.
  const evidencias = await seletorEvidencia.locator('option').all();
  let alvo: string | null = null;
  for (const opcao of evidencias) {
    const rotulo = (await opcao.innerText()).trim();
    if (!rotulo.includes('ônus vigentes')) { alvo = await opcao.getAttribute('value'); break; }
  }
  expect(alvo, 'nenhuma evidência de ATO na decisão de gravames').not.toBeNull();
  await seletorEvidencia.selectOption(alvo!);

  const seletorTipo = cartaoGravame.getByLabel('Tipo de observação decidido');
  const tipoAntes = await seletorTipo.inputValue();
  const tipoNovo = tipoAntes === 'alienacao_fiduciaria' ? 'hipoteca' : 'alienacao_fiduciaria';
  await seletorTipo.selectOption(tipoNovo);
  await print(page, '05_reclassificar_antes');
  await cartaoGravame.getByRole('button', { name: 'Editar tipo' }).click();

  // Prova pela TELA, não pelo estado local do componente: recarrega, reabre o
  // cartão e relê o tipo — que agora vem do servidor.
  await page.reload();
  await abrirAba(page, 'Conferência');
  const cartaoRelido = page.getByTestId(testidGravame!);
  await expect(cartaoRelido).toBeVisible({ timeout: 60_000 });
  await expandirCartao(cartaoRelido, cartaoRelido.getByLabel('Evidência a editar'));
  await cartaoRelido.getByLabel('Evidência a editar').selectOption(alvo!);
  await expect(cartaoRelido.getByLabel('Tipo de observação decidido')).toHaveValue(tipoNovo);
  registro.reclassificacao = { evidencia: alvo, tipo_antes: tipoAntes, tipo_decidido: tipoNovo };
  await print(page, '06_reclassificar_depois');

  // ── 7. decidir TODAS as decisões, pelo cartão ─────────────────────────
  // Sempre o PRIMEIRO cartão que ainda oferece "Aceitar proposta", e a espera é
  // pelo cartão sair de pendente — não pela contagem global cair. A contagem
  // global oscila para cima enquanto a lista termina de carregar, e uma volta
  // que confiasse nela falharia por motivo que não é o do teste.
  await expect(page.getByTestId('decisoes-total')).toBeVisible();
  const aceitar = page.getByRole('button', { name: 'Aceitar proposta' });
  for (let volta = 0; volta < 120; volta++) {
    if (await aceitar.count() === 0) break;
    const cartao = page.locator('[data-testid^="decisao-"]').filter({ has: aceitar }).first();
    const id = (await cartao.getAttribute('data-testid'))!;
    const alvo = page.getByTestId(id);
    await alvo.getByRole('button', { name: 'Aceitar proposta' }).click();
    try {
      // 90 s por cartão, e não 20: MEDIDO nesta pilha, aceitar a decisão de
      // gravames da matrícula 3.313 (15 membros, um `decide_field` por membro)
      // levou 19,4 s no servidor — mais o refetch da tela. Com janela curta o
      // teste acusava "decisão que não fecha" onde havia só espera.
      await expect(alvo.getByRole('button', { name: 'Aceitar proposta' }))
        .toHaveCount(0, { timeout: 90_000 });
    } catch {
      // Divergência que "Aceitar" não resolve sozinha: nenhuma evidência é
      // autoritativa, então a proposta não tem de onde sair e a decisão exige
      // escolha ativa. A tela oferece exatamente esse gesto — é ele que o
      // teste faz, não uma chamada por baixo.
      const escolher = alvo.getByRole('button', { name: 'Escolher esta fonte' });
      await expandirCartao(alvo, escolher);
      await expect(escolher.first(),
        `decisão ${id} não fecha com "Aceitar" e não oferece escolher a fonte`,
      ).toBeVisible({ timeout: 15_000 });
      await escolher.first().click();
      await expect(alvo.getByRole('button', { name: 'Aceitar proposta' }))
        .toHaveCount(0, { timeout: 60_000 });
    }
  }
  await expect(aceitar).toHaveCount(0);
  await expect(page.getByTestId('decisao-estado').filter({ hasText: PENDENTE })).toHaveCount(0);

  // e as linhas soltas (sem agrupamento), pelo botão em lote que a tela oferece
  const emLote = page.getByRole('button', { name: /Aceitar todos os consistentes/ });
  if (await emLote.count() > 0) {
    await emLote.click();
    await expect(emLote).toHaveCount(0, { timeout: 120_000 });
  }
  await print(page, '07_decidido');

  // ── 8. GRAVAR NA BASE ─────────────────────────────────────────────────
  const rodapeAntes = (await page.getByTestId('conferencia-rodape').innerText()).trim();
  expect(rodapeAntes).toMatch(/[1-9]\d* campo\(s\) serão gravados/);
  expect(rodapeAntes, 'nada podia estar na base antes do clique').not.toMatch(/já na base/);
  await page.getByRole('button', { name: /Gravar na base/ }).click();
  // "N campo(s) serão gravados" NÃO zera depois de gravar, e é de propósito: a
  // linha aceita continua aceita, e o rodapé conta as duas coisas separadas —
  // o que ainda vai pousar e o que já pousou. O sinal de que a base recebeu é
  // o segundo número aparecer.
  await expect.poll(
    async () => (await page.getByTestId('conferencia-rodape').innerText()).trim(),
    { timeout: 10 * 60 * 1000 },
  ).toMatch(/· [1-9]\d* já na base/);
  registro.rodape_antes_de_gravar = rodapeAntes;
  registro.rodape_depois_de_gravar = (await page.getByTestId('conferencia-rodape').innerText()).trim();
  await print(page, '08_gravado');

  // O que as decisões aceitas mandaram, a base recebeu: nenhuma decisão pode
  // ficar em "aguardando gravação" depois do clique que grava.
  await expect(page.getByTestId('decisao-estado').filter({ hasText: AGUARDANDO_GRAVACAO }))
    .toHaveCount(0);

  // ── 9. os seis números, do DOM ────────────────────────────────────────
  const base = await seisNumerosDoDOM(page, DOCS.length);

  // ── 10. F5 ────────────────────────────────────────────────────────────
  await page.reload();
  await expect(page.getByRole('button', { name: 'Conferência', exact: true }).first())
    .toBeVisible({ timeout: 60_000 });
  const recarregado = await seisNumerosDoDOM(page, DOCS.length);
  expect(recarregado).toEqual(base);
  await print(page, '09_apos_f5');

  // ── 11. logout / login — mesma corrida, sessão nova ───────────────────
  await logout(page);
  await login(page);
  await page.goto(`/processes/${pid}?tab=documents`);
  const sessaoNova = await seisNumerosDoDOM(page, DOCS.length);
  expect(sessaoNova).toEqual(base);
  await print(page, '10_sessao_nova');
  registro.seis_numeros = { base, recarregado, sessao_nova: sessaoNova };

  // ── 12. a ROTA e a sua invalidação ────────────────────────────────────
  // A Frente J não provou isto ("sem rota no processo", invalidacao.json): o
  // aviso de invalidação da rota nunca foi exercido porque não havia rota.
  //
  // Este gate mediu POR QUE não havia. A Rota só é oferecida na macroetapa E5,
  // e chegar lá pela tela exige fechar E1→E4 — trabalho de consultoria real
  // (assinar diagnóstico, completar o output mínimo de cada etapa), não gesto
  // de teste. O que ESTA frente consertou é o degrau que era invisível: um
  // caso sem macroetapa ficava travado em "Etapa não iniciada (sem checklist)"
  // e a tela não oferecia gesto nenhum para sair de lá. Agora o caso nasce na
  // E1 e o painel mostra o que falta.
  //
  // O teste vai até onde a TELA leva, e registra onde parou — inventar as
  // etapas para chegar à Rota seria fabricar estado, que é exatamente o que
  // este gate existe para não fazer.
  const travas = page.getByText(/TRAVAS PARA AVANÇAR/i);
  registro.etapa_apos_percurso =
    (await http<{ macroetapa: string | null }>(page, `/processes/${pid}`))?.macroetapa ?? null;
  registro.travas_na_tela = await travas.count() > 0
    ? (await travas.locator('xpath=..').first().innerText()).trim()
    : 'sem travas na tela';

  for (let passo = 0; passo < 8; passo++) {
    const avancar = page.getByRole('button', { name: /^Avançar →/ });
    if (await avancar.count() === 0) break;
    const antes = (await http<{ macroetapa: string }>(page, `/processes/${pid}`))?.macroetapa;
    await avancar.first().click();
    const confirmar = page.getByRole('button', { name: 'Avançar mesmo assim' });
    if (await confirmar.count() > 0) await confirmar.click();
    await expect.poll(async () =>
      (await http<{ macroetapa: string }>(page, `/processes/${pid}`))?.macroetapa,
    { timeout: 120_000 }).not.toBe(antes);
  }
  const etapaFinal = (await http<{ macroetapa: string | null }>(page, `/processes/${pid}`))?.macroetapa;
  registro.etapa_alcancada_pela_tela = etapaFinal ?? null;

  await abrirAba(page, 'Ações');
  const gerarRota = page.getByRole('button', { name: 'Gerar rota' });
  const rotaAlcancavel = await gerarRota.count() > 0;
  registro.rota_alcancavel_pela_tela = rotaAlcancavel;
  await print(page, '11_acoes');

  if (rotaAlcancavel) {
    await gerarRota.click();
    await expect(gerarRota).toHaveCount(0, { timeout: 15 * 60 * 1000 });
    await print(page, '12_rota_gerada');

    // documento novo entra pela tela → a rota fica desatualizada, e a tela diz
    await abrirAba(page, 'Documentos');
    await page.locator('select').first().selectOption('car');
    await page.locator('input[type="file"]').first()
      .setInputFiles(path.join(PDFS, 'CAR FAZ B1 B2 B3 E BA - ELODI 2016.pdf'));
    await expect.poll(async () => page.getByTestId('doc-lifecycle').count(),
      { timeout: 180_000 }).toBe(DOCS.length + 1);

    await expect.poll(async () => {
      await page.reload();
      await abrirAba(page, 'Ações');
      return page.getByText(/desatualizada/i).count();
    }, { timeout: 10 * 60 * 1000, intervals: [15_000] }).toBeGreaterThan(0);
    registro.rota_desatualizada = (await page.getByText(/desatualizada/i).first().innerText()).trim();
    await print(page, '13_rota_desatualizada');
  } else {
    // Sem rota não há invalidação de rota a provar. Fica DECLARADO — nem
    // fabricado nem escondido.
    test.info().annotations.push({
      type: 'nao provado',
      description: `Rota não alcançável pela tela: o caso parou em `
        + `"${etapaFinal ?? 'sem macroetapa'}" e a Rota só aparece na E5 `
        + `(caminho_regulatorio). Travas: ${registro.travas_na_tela}`,
    });
  }

  fs.writeFileSync(path.join(PRINTS, 'frente_k_percurso.json'), JSON.stringify(registro, null, 1));
});
