/**
 * Gate E2E da Frente J — o gesto humano, na UI real, contra a API real.
 *
 * Pré-condição (fora deste arquivo): `tests/e2e/frente_j/setup_db.py` rodou
 * (banco descartável + seed), a API e o worker estão de pé apontando para
 * ele, o Vite está servindo o painel, e as variáveis abaixo estão no ambiente:
 *
 *   E2E_SEED_JSON   caminho do JSON impresso por setup_db.py
 *   E2E_PDFS_DIR    pasta com os 6 PDFs (texto real dos docs 546-551)
 *   E2E_API_URL     ex. http://127.0.0.1:8000
 *   E2E_PRINTS_DIR  onde salvar os prints (colados no relatório)
 *
 * O que este spec prova (a parte que só a UI prova — o `gate_api.py` cobre a
 * mesma sequência por payload):
 *   1. login → processo → aba Documentos → upload dos 6 PDFs pelo input real;
 *   2. extração termina → aba Conferência mostra decisões;
 *   3. decidir 3 na tela (uma com "Editar tipo"), "Gravar na base";
 *   4. recarregar (F5) → mesmas decisões/estados; logout/login → idem;
 *   5. proposta desatualizada: banner na tela, botão "Aceitar" bloqueado e,
 *      forçando o clique via API, o 422 vira toast com a razão.
 * Prints de cada uma das seis abas, antes e depois, em E2E_PRINTS_DIR.
 */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const seed = JSON.parse(fs.readFileSync(process.env.E2E_SEED_JSON!, 'utf-8')) as {
  email: string; password: string; process_id: number; client_id: number; property_id: number;
};
const PDFS = process.env.E2E_PDFS_DIR!;
const API = (process.env.E2E_API_URL ?? 'http://127.0.0.1:8000') + '/api/v1';
const PRINTS = process.env.E2E_PRINTS_DIR ?? path.join('e2e-results', 'prints');
fs.mkdirSync(PRINTS, { recursive: true });

const DOCS: Array<[string, string]> = [
  ['CAR FAZ B1 B2 B3 E BA - ELODI 2016.pdf', 'car'],
  ["B1 - M3.181 - FAZ. R. Olhos d'agua - Elodi 2013 926ha.pdf", 'matricula'],
  ['B2 - M3.313 - FAZ. NH 2 - Elodi 2014 725ha.pdf', 'matricula'],
  ['B3 - M3.673 - FAZ Posse G4 - Elodi 2016 212ha.pdf', 'matricula'],
  ['B4 - M4.387 - FAZ Posse G3 - Elodi 2020 316ha.pdf', 'matricula'],
  ['CNH-e.pdf.pdf', 'doc_pessoal'],
];
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

async function abrirAba(page: Page, aba: string) {
  await page.getByRole('button', { name: aba, exact: true }).first().click();
}

async function print(page: Page, nome: string) {
  await page.screenshot({ path: path.join(PRINTS, `${nome}.png`), fullPage: true });
}

async function token(page: Page): Promise<string> {
  // O painel guarda a sessão no zustand/persist (`auth-storage`).
  const raw = await page.evaluate(() => localStorage.getItem('auth-storage'));
  const parsed = raw ? JSON.parse(raw) : null;
  return parsed?.state?.token ?? '';
}

async function api<T>(page: Page, method: 'GET' | 'POST' | 'PATCH', p: string, body?: unknown): Promise<{ status: number; json: T }> {
  const t = await token(page);
  const r = await page.request.fetch(API + p, {
    method, data: body, headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' },
  });
  let json: unknown = null;
  try { json = await r.json(); } catch { json = null; }
  return { status: r.status(), json: json as T };
}

interface Decisao {
  chave: { entidade: string; identificador: string; aspecto: string };
  label: string; estado: string; concordancia: string;
  evidencias: Array<{ staging_id: number | null; tipo_observacao: string | null; campo: string | null }>;
}
interface Reconciliacao { decisoes: Decisao[]; sem_agrupamento: unknown[]; total_staging: number }

function resumo(rec: Reconciliacao) {
  return {
    total_staging: rec.total_staging,
    sem_agrupamento: rec.sem_agrupamento.length,
    decisoes: rec.decisoes.map(d => `${d.chave.entidade}:${d.chave.identificador}:${d.chave.aspecto}=${d.estado}`).sort(),
  };
}

test.describe.serial('Frente J — tela → decisão → consolidação → recarga → nova sessão', () => {
  test('1. login, upload dos 6 docs pela UI, extração real', async ({ page }) => {
    await login(page);
    await page.goto(`/processes/${seed.process_id}?tab=documents`);
    await expect(page.getByRole('button', { name: 'Documentos', exact: true }).first()).toBeVisible();

    for (const [arquivo, tipo] of DOCS) {
      await page.locator('select').first().selectOption(tipo);
      await page.locator('input[type="file"]').first().setInputFiles(path.join(PDFS, arquivo));
      await expect(page.getByText(arquivo, { exact: false }).first()).toBeVisible({ timeout: 60_000 });
    }
    await print(page, '01_documentos_enviados');

    // A extração é real (worker + LLM). Espera até nenhum doc estar em
    // pending/processing e os 5 legíveis terem staging.
    await expect.poll(async () => {
      const docs = (await api<Array<{ id: number; ocr_status: string; tem_texto: boolean }>>(page, 'GET', `/documents/?process_id=${seed.process_id}`)).json;
      const staging = (await api<Array<{ document_id: number }>>(page, 'GET', `/processes/${seed.process_id}/staging-fields`)).json;
      const com = new Set(staging.map(s => s.document_id));
      const pendentes = docs.filter(d => ['pending', 'processing'].includes(d.ocr_status) || (d.tem_texto && !com.has(d.id)));
      return pendentes.length;
    }, { timeout: 25 * 60 * 1000, intervals: [10_000] }).toBe(0);

    await page.reload();
    await print(page, '02_documentos_extraidos');
  });

  test('2. Conferência mostra decisões; decidir 3 (uma com edição de tipo); gravar', async ({ page }) => {
    await login(page);
    await page.goto(`/processes/${seed.process_id}?tab=alertas`);
    await expect(page.getByRole('button', { name: /Gravar na base/ })).toBeVisible();
    const antes = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;
    fs.writeFileSync(path.join(PRINTS, 'conferencia_antes.json'), JSON.stringify(resumo(antes), null, 1));
    expect(antes.decisoes.length).toBeGreaterThan(0);
    await print(page, '03_conferencia_antes');

    // (1) aceitar a composição de uma matrícula (REC-001 literal)
    const comp = antes.decisoes.find(d => d.chave.aspecto === 'composicao' && d.estado === 'pendente')!;
    const cardComp = page.locator('div', { has: page.getByRole('button', { name: comp.label }) }).last();
    await cardComp.getByRole('button', { name: /^Aceitar/ }).first().click();
    await expect(page.getByText('Decidida — aguardando gravação').first()).toBeVisible();

    // (2) EDIÇÃO DE TIPO numa decisão de gravames (CONF-002)
    const grav = antes.decisoes.find(d => d.chave.aspecto === 'gravames' && d.estado === 'pendente' && d.evidencias.some(e => e.tipo_observacao))!;
    const cardGrav = page.locator('div', { has: page.getByRole('button', { name: grav.label }) }).last();
    await cardGrav.getByRole('button', { name: grav.label }).click(); // expande
    const ev = grav.evidencias.find(e => e.tipo_observacao)!;
    const novoTipo = ev.tipo_observacao === 'alienacao_fiduciaria' ? 'hipoteca' : 'alienacao_fiduciaria';
    await cardGrav.getByLabel('Evidência a editar').selectOption(String(ev.staging_id));
    await cardGrav.getByLabel('Tipo de observação decidido').selectOption(novoTipo);
    await cardGrav.getByRole('button', { name: 'Editar tipo' }).click();
    await expect.poll(async () => {
      const r = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;
      const d = r.decisoes.find(x => x.chave.identificador === grav.chave.identificador && x.chave.aspecto === 'gravames');
      return d?.evidencias.find(e => e.staging_id === ev.staging_id)?.tipo_observacao;
    }).toBe(novoTipo);
    await cardGrav.getByRole('button', { name: /^Aceitar/ }).first().click();

    // (3) uma terceira decisão (área/CAR/RL)
    const outra = antes.decisoes.find(d => ['area', 'car', 'reserva_legal'].includes(d.chave.aspecto) && d.estado === 'pendente')!;
    const cardOutra = page.locator('div', { has: page.getByRole('button', { name: outra.label }) }).last();
    await cardOutra.getByRole('button', { name: /^Aceitar/ }).first().click();
    await print(page, '04_conferencia_decididas');

    await page.getByRole('button', { name: /Gravar na base/ }).click();
    await expect(page.getByText('Gravado na base').first()).toBeVisible({ timeout: 60_000 });
    await print(page, '05_conferencia_gravada');
    const depois = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;
    fs.writeFileSync(path.join(PRINTS, 'conferencia_depois.json'), JSON.stringify(resumo(depois), null, 1));
    expect(depois.decisoes.filter(d => d.estado === 'gravada').length).toBeGreaterThanOrEqual(3);
  });

  test('3. recarregar e sessão nova mostram os mesmos números nas seis telas', async ({ page }) => {
    await login(page);
    await page.goto(`/processes/${seed.process_id}`);
    const base = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;
    const progresso = (await api<unknown>(page, 'GET', `/processes/${seed.process_id}/progresso`)).json;
    for (const aba of TABS) { await abrirAba(page, aba); await print(page, `06_${aba}`); }

    await page.reload();
    const recarregado = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;
    expect(resumo(recarregado)).toEqual(resumo(base));
    expect((await api<unknown>(page, 'GET', `/processes/${seed.process_id}/progresso`)).json).toEqual(progresso);
    for (const aba of TABS) { await abrirAba(page, aba); await print(page, `07_recarregado_${aba}`); }

    await logout(page);
    await login(page);
    await page.goto(`/processes/${seed.process_id}`);
    const novaSessao = (await api<Reconciliacao>(page, 'GET', `/processes/${seed.process_id}/staging-decisions`)).json;
    expect(resumo(novaSessao)).toEqual(resumo(base));
    expect((await api<unknown>(page, 'GET', `/processes/${seed.process_id}/progresso`)).json).toEqual(progresso);
    for (const aba of TABS) { await abrirAba(page, aba); await print(page, `08_sessao_nova_${aba}`); }
    fs.writeFileSync(path.join(PRINTS, 'seis_telas_comparacao.json'), JSON.stringify({
      base: resumo(base), recarregado: resumo(recarregado), nova_sessao: resumo(novaSessao), progresso,
    }, null, 1));
  });

  test('4. documento novo → proposta desatualizada: banner, botão bloqueado, 422 com razão', async ({ page }) => {
    await login(page);
    // diagnóstico validado + proposta enviada (o chão que o doc novo invalida)
    const diag = await api<{ version: number }>(page, 'POST', `/processes/${seed.process_id}/diagnoses`, {
      content: { content: 'Diagnóstico preliminar — gate E2E Frente J (UI).', sources: [{ type: 'legislation', ref: 'gate-e2e' }],
                 hipoteses: ['CAR pendente'], lacunas: [], riscos: [], checklist_documental: ['Matrícula'] },
    });
    expect(diag.status).toBe(201);
    expect((await api(page, 'PATCH', `/processes/${seed.process_id}/diagnoses/${diag.json.version}/validate`)).status).toBe(200);
    const prop = await api<{ id: number }>(page, 'POST', '/proposals/', {
      client_id: seed.client_id, process_id: seed.process_id, title: 'Proposta — gate E2E (UI)',
      scope_items: [{ description: 'Retificação do CAR', unit: 'un', qty: 1, unit_price: 1000, total: 1000 }],
      total_value: 1000, validity_days: 30,
    });
    expect(prop.status).toBe(201);
    expect((await api(page, 'POST', `/proposals/${prop.json.id}/send`)).status).toBe(200);

    await page.goto(`/proposals/${prop.json.id}`);
    await expect(page.getByRole('button', { name: /Aceitar/ })).toBeEnabled();
    await print(page, '09_proposta_enviada_sem_aviso');

    // documento novo pela UI
    await page.goto(`/processes/${seed.process_id}?tab=documents`);
    await page.locator('select').first().selectOption('car');
    await page.locator('input[type="file"]').first().setInputFiles(path.join(PDFS, DOCS[0][0]));
    await expect(page.getByText(DOCS[0][0], { exact: false }).nth(1)).toBeVisible({ timeout: 60_000 });

    // diagnóstico e proposta avisam
    await page.goto(`/processes/${seed.process_id}?tab=diagnosis`);
    await expect(page.getByText(/pode estar desatualizado/)).toBeVisible();
    await print(page, '10_diagnostico_desatualizado');
    await page.goto(`/proposals/${prop.json.id}`);
    await expect(page.getByText(/Proposta desatualizada/)).toBeVisible();
    await expect(page.getByRole('button', { name: /Aceitar/ })).toBeDisabled();
    await print(page, '11_proposta_desatualizada_bloqueada');

    // forçando pela API (o que um clique sem o guard faria): 422 com a razão
    const rec = await api<{ detail: string }>(page, 'POST', `/proposals/${prop.json.id}/accept`);
    expect(rec.status).toBe(422);
    expect(rec.json.detail).toContain('desatualizada');
    fs.writeFileSync(path.join(PRINTS, 'aceite_recusado.json'), JSON.stringify(rec, null, 1));
    const final = await api<{ status: string; aviso_desatualizado: unknown }>(page, 'GET', `/proposals/${prop.json.id}`);
    expect(final.json.status).toBe('sent');
    expect(final.json.aviso_desatualizado).toBeTruthy();
  });
});
