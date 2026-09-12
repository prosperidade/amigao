/**
 * Gate E2E da Frente J — o GESTO HUMANO, na UI real, contra a API real.
 *
 * A camada de payloads (`tests/e2e/frente_j/gate_api.py` + `gate_complemento.py`)
 * já atravessa o percurso inteiro. O que SÓ a tela prova é o que está aqui:
 * que os controles existem onde a consultora procura, que o clique faz o que
 * diz, e que o estado sobrevive a F5 e a logout/login com os MESMOS números.
 *
 * Trabalha sobre o processo que o gate da API já populou (6 documentos da
 * ELODI, texto real de produção, extração real) — repetir a extração aqui
 * custaria minutos e não provaria nada a mais.
 *
 * Pré-condição: a pilha do gate de pé e as variáveis:
 *   E2E_SEED_JSON   caminho do JSON impresso por setup_db.py
 *   E2E_API_URL     ex. http://127.0.0.1:8000
 *   E2E_PDFS_DIR    pasta com os PDFs (para o upload pela tela)
 *   E2E_PRINTS_DIR  onde salvar os prints colados no relatório
 */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const seed = JSON.parse(fs.readFileSync(process.env.E2E_SEED_JSON!, 'utf-8')) as {
  email: string; password: string; process_id: number; client_id: number; property_id: number;
};
const API = (process.env.E2E_API_URL ?? 'http://127.0.0.1:8000') + '/api/v1';
const PRINTS = process.env.E2E_PRINTS_DIR ?? path.join('e2e-results', 'prints');
const PDFS = process.env.E2E_PDFS_DIR ?? '';
fs.mkdirSync(PRINTS, { recursive: true });

const TABS = ['Visão geral', 'Documentos', 'Conferência', 'Dados', 'Ações', 'Saídas'];

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
  await page.screenshot({ path: path.join(PRINTS, `${nome}.png`), fullPage: true });
}

async function api<T>(page: Page, method: 'GET' | 'POST' | 'PATCH', p: string, body?: unknown): Promise<{ status: number; json: T }> {
  const raw = await page.evaluate(() => localStorage.getItem('auth-storage'));
  const token = raw ? (JSON.parse(raw)?.state?.token ?? '') : '';
  const r = await page.request.fetch(API + p, {
    method, data: body, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  });
  let json: unknown = null;
  try { json = await r.json(); } catch { json = null; }
  return { status: r.status(), json: json as T };
}

interface Decisao {
  chave: { entidade: string; identificador: string; aspecto: string };
  label: string; estado: string; concordancia: string;
  evidencias: Array<{ staging_id: number | null; tipo_observacao: string | null }>;
}
interface Reconciliacao { decisoes: Decisao[]; sem_agrupamento: unknown[]; total_staging: number }

/** Os SEIS números, cada um rotulado com a pergunta que responde. */
async function seisNumeros(page: Page) {
  const pid = seed.process_id;
  const rec = (await api<Reconciliacao>(page, 'GET', `/processes/${pid}/staging-decisions`)).json;
  const prog = (await api<{ checklist_documental: unknown; conferencia: Record<string, number> }>(
    page, 'GET', `/processes/${pid}/progresso`)).json;
  const checklist = (await api<{ completion_pct?: number; total?: number }>(page, 'GET', `/processes/${pid}/checklist`)).json;
  const dossier = (await api<{ checklist_summary?: unknown }>(page, 'GET', `/processes/${pid}/dossier`)).json;
  const docs = (await api<Array<{ id: number; lifecycle_status: string }>>(page, 'GET', `/documents/?process_id=${pid}`)).json;
  const staging = (await api<unknown[]>(page, 'GET', `/processes/${pid}/staging-fields`)).json;
  return {
    'quantos documentos entraram (checklist)': JSON.stringify(prog.checklist_documental),
    'quanto da Conferência está resolvido (decisões)': JSON.stringify(prog.conferencia),
    'quantas decisões a Conferência agrupa': `${rec.decisoes.length} decisões + ${rec.sem_agrupamento.length} sem agrupamento = ${rec.decisoes.length + rec.sem_agrupamento.length}`,
    'quantas linhas de staging existem': `${rec.total_staging} (staging-fields: ${staging.length})`,
    'estado de cada documento (DOC-001)': JSON.stringify(docs.map(d => d.lifecycle_status).sort()),
    'estado de cada decisão': JSON.stringify(rec.decisoes.map(d => d.estado).sort()),
    _checklist_bruto: JSON.stringify(checklist).slice(0, 200),
    _dossier_tem_resumo: dossier?.checklist_summary != null,
  };
}

test.describe.serial('Frente J — o gesto humano na Conferência', () => {
  test('1. a Conferência mostra as decisões na tela', async ({ page }) => {
    await login(page);
    await page.goto(`/processes/${seed.process_id}?tab=alertas`);
    await expect(page.getByRole('button', { name: /Gravar na base/ })).toBeVisible({ timeout: 60_000 });

    const rec = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;
    expect(rec.decisoes.length).toBeGreaterThan(0);
    // cada decisão tem um cartão com o seu rótulo na tela
    for (const d of rec.decisoes.slice(0, 5)) {
      await expect(page.getByRole('button', { name: d.label, exact: true }).first()).toBeVisible();
    }
    fs.writeFileSync(path.join(PRINTS, 'ui_conferencia.json'), JSON.stringify({
      decisoes: rec.decisoes.length, sem_agrupamento: rec.sem_agrupamento.length,
      total_staging: rec.total_staging,
      soma: `${rec.decisoes.length} + ${rec.sem_agrupamento.length} = ${rec.decisoes.length + rec.sem_agrupamento.length}`,
    }, null, 1));
    await print(page, 'ui_01_conferencia');
  });

  test('2. decidir pela tela: aceitar e EDITAR TIPO, depois gravar na base', async ({ page }) => {
    await login(page);
    await page.goto(`/processes/${seed.process_id}?tab=alertas`);
    await expect(page.getByRole('button', { name: /Gravar na base/ })).toBeVisible({ timeout: 60_000 });
    const antes = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;

    // (a) aceitar uma decisão pendente pelo cartão
    const pend = antes.decisoes.find(d => d.estado === 'pendente')!;
    const cardPend = page.getByTestId(`decisao-${pend.chave.entidade}-${pend.chave.identificador}-${pend.chave.aspecto}`);
    await cardPend.getByRole('button', { name: /Aceitar proposta/ }).first().click();
    await expect.poll(async () => {
      const r = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;
      return r.decisoes.find(d => d.label === pend.label)?.estado;
    }).not.toBe('pendente');

    // (b) EDITAR TIPO numa decisão com evidência tipada (CONF-002, item 5)
    // OUTRA decisão, não a que acabou de ser aceita em (a): editar tipo só
    // é oferecido em decisão PENDENTE, e a de (a) já não é mais.
    const tipada = antes.decisoes.find(d => d.estado === 'pendente' && d.chave.aspecto === 'gravames'
      && d.evidencias.some(e => e.tipo_observacao)
      && !(d.chave.entidade === pend.chave.entidade && d.chave.identificador === pend.chave.identificador
           && d.chave.aspecto === pend.chave.aspecto))!;
    expect(tipada, 'nenhuma decisão de gravames pendente com evidência tipada').toBeTruthy();
    const cardTipo = page.getByTestId(`decisao-${tipada.chave.entidade}-${tipada.chave.identificador}-${tipada.chave.aspecto}`);
    await cardTipo.getByRole('button', { name: tipada.label, exact: true }).click(); // expande
    const ev = tipada.evidencias.find(e => e.tipo_observacao)!;
    const novoTipo = ev.tipo_observacao === 'alienacao_fiduciaria' ? 'hipoteca' : 'alienacao_fiduciaria';
    await cardTipo.getByLabel('Evidência a editar').selectOption(String(ev.staging_id));
    await cardTipo.getByLabel('Tipo de observação decidido').selectOption(novoTipo);
    await print(page, 'ui_02_editar_tipo_antes');
    await cardTipo.getByRole('button', { name: 'Editar tipo' }).click();
    await expect.poll(async () => {
      const r = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;
      const d = r.decisoes.find(x => x.label === tipada.label);
      return d?.evidencias.find(e => e.staging_id === ev.staging_id)?.tipo_observacao;
    }).toBe(novoTipo);
    // o tipo ORIGINAL fica preservado na linha
    const linha = (await api<Array<{ id: number; atributos: Record<string, unknown> | null }>>(
      page, 'GET', `/processes/${seed.process_id}/staging-fields`)).json
      .find(s => s.id === ev.staging_id)!;
    expect(linha.atributos?.tipo_sugerido).toBe(ev.tipo_observacao);
    await print(page, 'ui_03_editar_tipo_depois');

    // (c) gravar na base
    await page.getByRole('button', { name: /Gravar na base/ }).click();
    await expect.poll(async () => {
      const r = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;
      return r.decisoes.filter(d => d.estado === 'gravada' || d.estado === 'parcialmente_gravada').length;
    }, { timeout: 120_000 }).toBeGreaterThan(0);
    await print(page, 'ui_04_gravado');
  });

  test('3. F5 e logout/login mantêm decisões, estados e os seis números', async ({ page }) => {
    await login(page);
    await page.goto(`/processes/${seed.process_id}?tab=alertas`);
    await expect(page.getByRole('button', { name: /Gravar na base/ })).toBeVisible({ timeout: 60_000 });
    const base = await seisNumeros(page);
    for (const aba of TABS) {
      await page.getByRole('button', { name: aba, exact: true }).first().click();
      await print(page, `ui_05_aba_${aba.replace(/\s/g, '_')}`);
    }

    await page.reload();
    await expect(page.getByRole('button', { name: 'Conferência', exact: true }).first()).toBeVisible();
    const recarregado = await seisNumeros(page);
    expect(recarregado).toEqual(base);
    await print(page, 'ui_06_recarregado');

    await logout(page);
    await login(page);
    await page.goto(`/processes/${seed.process_id}?tab=alertas`);
    await expect(page.getByRole('button', { name: /Gravar na base/ })).toBeVisible({ timeout: 60_000 });
    const novaSessao = await seisNumeros(page);
    expect(novaSessao).toEqual(base);
    for (const aba of TABS) {
      await page.getByRole('button', { name: aba, exact: true }).first().click();
      await print(page, `ui_07_sessao_nova_${aba.replace(/\s/g, '_')}`);
    }
    fs.writeFileSync(path.join(PRINTS, 'ui_seis_numeros.json'),
      JSON.stringify({ base, recarregado, nova_sessao: novaSessao }, null, 1));
  });

  test('4. proposta desatualizada: banner na tela e botão Aceitar bloqueado', async ({ page }) => {
    await login(page);
    const props = (await api<Array<{ id: number; status: string }>>(page, 'GET', `/proposals/?process_id=${seed.process_id}`)).json;
    const enviada = props.find(p => p.status === 'sent');
    test.skip(!enviada, 'nenhuma proposta enviada no processo (o gate da API cria uma)');

    await page.goto(`/proposals/${enviada!.id}`);
    await expect(page.getByText(/Proposta desatualizada/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('button', { name: /Aceitar/ })).toBeDisabled();
    await print(page, 'ui_08_proposta_bloqueada');

    // e pela API o bloqueio é real, não só visual
    const rec = await api<{ detail: string }>(page, 'POST', `/proposals/${enviada!.id}/accept`);
    expect(rec.status).toBe(422);
    expect(rec.json.detail).toContain('desatualizada');
    fs.writeFileSync(path.join(PRINTS, 'ui_aceite_recusado.json'), JSON.stringify(rec, null, 1));
    const final = (await api<{ status: string }>(page, 'GET', `/proposals/${enviada!.id}`)).json;
    expect(final.status).toBe('sent');
  });

  test('5. upload pela tela: o documento entra e mostra o estado (DOC-001)', async ({ page }) => {
    test.skip(!PDFS, 'E2E_PDFS_DIR não informado');
    await login(page);
    await page.goto(`/processes/${seed.process_id}?tab=documents`);
    const arquivo = 'CNH-e.pdf.pdf';
    const antes = (await api<unknown[]>(page, 'GET', `/documents/?process_id=${seed.process_id}`)).json.length;

    await page.locator('select').first().selectOption('doc_pessoal');
    await page.locator('input[type="file"]').first().setInputFiles(path.join(PDFS, arquivo));
    await expect.poll(async () =>
      (await api<unknown[]>(page, 'GET', `/documents/?process_id=${seed.process_id}`)).json.length,
    { timeout: 60_000 }).toBe(antes + 1);

    // o CNH-e tem 444 chars de boilerplate de assinatura digital: a projeção
    // NÃO pode dizer "lido" (item 6).
    await expect.poll(async () => {
      const docs = (await api<Array<{ id: number; original_file_name: string; ocr_status: string; lifecycle_status: string }>>(
        page, 'GET', `/documents/?process_id=${seed.process_id}`)).json;
      const novo = docs.filter(d => d.original_file_name === arquivo).pop();
      return novo?.ocr_status === 'done' ? novo?.lifecycle_status : 'aguardando';
    }, { timeout: 180_000 }).toBe('erro_leitura');
    await page.reload();
    await expect(page.getByText('Erro de leitura').first()).toBeVisible({ timeout: 30_000 });
    await print(page, 'ui_09_documento_erro_leitura');
  });
});
