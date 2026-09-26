// @vitest-environment jsdom
/**
 * Gestos das telas do motor jurídico (#278) e do fechamento comercial (#282).
 *
 * Cada teste exerce o gesto na tela e confere o que VAI ao servidor — o corpo
 * e a URL exatos da API (`app/api/v1/rotas.py`, `motor_juridico.py`,
 * `comercial.py`, `proposals.py`). A regra de negócio mora no backend e está
 * provada lá contra banco real (`tests/comercial/`, `tests/motor_juridico/`);
 * aqui a prova é que a tela não deixa de pedir o que a regra exige (motivo,
 * justificativa) nem de mostrar o que ela devolve (evidência por ID, motivos).
 * O percurso inteiro, no navegador contra o dev, está no registro do PR.
 */
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ComercialRotaPanel from './ComercialRotaPanel';
import RotaTab from './RotaTab';

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

const navegar = vi.fn();
vi.mock('react-router-dom', async orig => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useNavigate: () => navegar,
}));

import { api } from '@/lib/api';

function comQuery(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return (
    <MemoryRouter>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </MemoryRouter>
  );
}

const nao404 = () => Object.assign(new Error('404'), { response: { status: 404 } });

/** Responde cada GET pela URL; o que não está no mapa é 404. */
function servir(mapa: Record<string, unknown>) {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === '/versao') return { data: { commit: 'abc1234', ambiente: 'development' } };
    for (const [trecho, data] of Object.entries(mapa)) if (url.includes(trecho)) return { data };
    throw nao404();
  });
}

// ─── Motor ──────────────────────────────────────────────────────────────────

const PASSO_MOTOR = {
  id: 6,
  rota_id: 2,
  ordem: 1,
  titulo: 'Emitir ou regularizar o CCIR do imóvel',
  descricao: null,
  orgao: 'INCRA',
  prazo_estimado_dias: null,
  prazo_fonte: null,
  sources: [],
  norma_ref: 'Lei 5.868/1972, art. 2º',
  classificacao: 'item_proposta',
  origem: 'motor',
  origem_manual_nota: null,
  origem_avaliacao_id: 28,
  fundamento_fonte_versao_id: 1875,
  fundamento_dispositivo_id: 65677,
  status: 'validado',
  created_at: null,
  updated_at: null,
};

const ROTA = {
  id: 2,
  process_id: 66,
  demand_type: 'car',
  status: 'em_validacao',
  caminho_regulatorio: null,
  orgao_competente: null,
  source_ai_job_id: null,
  validated_by: null,
  validated_at: null,
  created_at: null,
  updated_at: null,
  passos: [PASSO_MOTOR],
};

const EXECUCAO = {
  execucao_id: 5,
  process_id: 66,
  conjunto_id: 1,
  conjunto_tenant_id: null,
  data_referencia: '2026-09-23',
  fatos: { 'ccir.no_dossie': { valor: false, estado: 'determinado' }, 'titular.falecimento_declarado': { valor: null, estado: 'nao_determinado' } },
  fatos_hash: 'f'.repeat(64),
  contagem: { aplicavel_disparou: 2, indeterminado: 1 },
  disparadas: 2,
  alertas_sem_ciencia: [29],
  avaliacoes: [
    {
      avaliacao_id: 28, rule_id: 'REG-FUN-002', regra_versao_id: 2, estado: 'aplicavel_disparou', faltantes: [],
      efeitos: [{ tipo: 'passo_rota' }],
      fundamento: { fonte_versao_id: 1875, dispositivo_id: 65677, caminho: 'Lei 5.868/1972, art. 2º', razao: null },
      alerta_critico_sem_ciencia: false, detalhe_erro: null,
    },
    {
      avaliacao_id: 29, rule_id: 'REG-FUN-012', regra_versao_id: 3, estado: 'aplicavel_disparou', faltantes: [],
      efeitos: [{ tipo: 'alerta_critico' }],
      fundamento: { fonte_versao_id: null, dispositivo_id: null, caminho: 'Código Civil, art. 1.784', razao: 'fonte_ausente' },
      alerta_critico_sem_ciencia: true, detalhe_erro: null,
    },
    {
      avaliacao_id: 30, rule_id: 'REG-GO-CAR-001', regra_versao_id: 4, estado: 'indeterminado',
      faltantes: ['imovel.natureza'], efeitos: [],
      fundamento: { fonte_versao_id: null, dispositivo_id: null, caminho: null, razao: 'sem_fundamento_declarado' },
      alerta_critico_sem_ciencia: false, detalhe_erro: null,
    },
  ],
};

const DISPOSITIVO = {
  tipo: 'dispositivo', id: 65677, titulo: 'Lei 5.868/1972 — art. 2º',
  texto: 'Art. 2º Ficam obrigados a prestar declaração de cadastro…', texto_cortado: false,
  campos: [{ rotulo: 'Versão da fonte', valor: '1875' }],
  refs: [{ tipo: 'fonte_versao', id: 1875, rotulo: 'Lei 5.868/1972 (versão 1875)' }], documento_id: null,
};

describe('Rota — motor jurídico (#278)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('passo do motor só sai com motivo, e o motivo vai ao servidor', async () => {
    const user = userEvent.setup();
    servir({ '/processes/66/rota': ROTA, '/motor/execucoes/ultima': EXECUCAO });
    vi.mocked(api.delete).mockResolvedValue({ data: null });

    render(comQuery(<RotaTab processId={66} />));
    await user.click(await screen.findByRole('button', { name: /remover passo 1: emitir ou regularizar o ccir/i }));

    const confirmar = screen.getByRole('button', { name: /remover da rota/i });
    expect(confirmar).toBeDisabled();

    await user.type(screen.getByLabelText(/motivo da remoção \(obrigatório/i), 'cliente apresentará o CCIR vigente');
    expect(confirmar).toBeEnabled();
    await user.click(confirmar);

    await waitFor(() =>
      expect(api.delete).toHaveBeenCalledWith('/rotas/2/passos/6', {
        params: { motivo: 'cliente apresentará o CCIR vigente' },
      }),
    );
  });

  it('o fundamento do passo abre pelo ID e segue a cadeia', async () => {
    const user = userEvent.setup();
    servir({
      '/processes/66/rota': ROTA,
      '/motor/execucoes/ultima': EXECUCAO,
      '/evidencias/dispositivo/65677': DISPOSITIVO,
      '/evidencias/fonte_versao/1875': { ...DISPOSITIVO, tipo: 'fonte_versao', id: 1875, titulo: 'Lei 5.868/1972', refs: [] },
    });

    render(comQuery(<RotaTab processId={66} />));
    const fonte = await screen.findByTestId('fonte-passo-6');
    await user.click(within(fonte).getByRole('button', { name: /lei 5\.868\/1972, art\. 2º/i }));

    const painel = await screen.findByRole('dialog', { name: /evidência/i });
    expect(await within(painel).findByText(/ficam obrigados a prestar declaração/i)).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/processes/66/evidencias/dispositivo/65677');

    await user.click(within(painel).getByRole('button', { name: /versão 1875/i }));
    expect(await within(painel).findByText('Lei 5.868/1972')).toBeInTheDocument();
    await user.click(within(painel).getByRole('button', { name: /voltar/i }));
    expect(await within(painel).findByText('Lei 5.868/1972 — art. 2º')).toBeInTheDocument();
  });

  it('relatório da execução: indeterminada com faltantes, fundamento ausente com razão, ciência com justificativa', async () => {
    const user = userEvent.setup();
    servir({ '/processes/66/rota': ROTA, '/motor/execucoes/ultima': EXECUCAO });
    vi.mocked(api.post).mockResolvedValue({ data: { id: 1 } });

    render(comQuery(<RotaTab processId={66} />));
    expect(await screen.findByTestId('motor-avaliadas')).toHaveTextContent('3 regra(s) avaliada(s)');
    expect(within(screen.getByTestId('avaliacao-REG-GO-CAR-001')).getByText(/fatos que faltaram: imovel\.natureza/i)).toBeInTheDocument();
    const alerta = screen.getByTestId('avaliacao-REG-FUN-012');
    expect(within(alerta).getByText(/norma fora do catálogo normativo/i)).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('1 alerta(s) crítico(s) sem ciência');

    const registrar = within(alerta).getByRole('button', { name: /registrar ciência/i });
    expect(registrar).toBeDisabled();
    await user.type(within(alerta).getByLabelText(/justificativa/i), 'cliente informado em reunião');
    await user.click(registrar);
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/processes/66/motor/alertas/29/ciencia', {
        justificativa: 'cliente informado em reunião',
      }),
    );
  });

  it('Rota já no cache (lida pelo ProcessDetail) aparece com os passos ao montar a aba', async () => {
    // Achado do gate de navegador: a lista nascia vazia e só se preenchia quando
    // os passos mudavam — com a Rota vinda do cache, nunca.
    servir({ '/processes/66/rota': ROTA, '/motor/execucoes/ultima': EXECUCAO });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    qc.setQueryData(['rota', 66], ROTA);
    render(
      <MemoryRouter>
        <QueryClientProvider client={qc}><RotaTab processId={66} /></QueryClientProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByText('Emitir ou regularizar o CCIR do imóvel')).toBeInTheDocument();
    expect(screen.getByTestId('fonte-passo-6')).toBeInTheDocument();
  });

  it('ciência herdada de execução de mesmo conteúdo aparece como tal, clicável (#289)', async () => {
    const semPendencia = {
      ...EXECUCAO,
      alertas_sem_ciencia: [],
      avaliacoes: EXECUCAO.avaliacoes.map(a =>
        a.avaliacao_id === 29
          ? { ...a, alerta_critico_sem_ciencia: false, ciencia: { id: 3, avaliacao_id: 12, herdada: true } }
          : { ...a, ciencia: null },
      ),
    };
    servir({ '/processes/66/rota': ROTA, '/motor/execucoes/ultima': semPendencia });
    render(comQuery(<RotaTab processId={66} />));
    const alerta = await screen.findByTestId('avaliacao-REG-FUN-012');
    expect(within(alerta).getByText(/ciência de execução anterior \(mesmos fatos e regras\)/)).toBeInTheDocument();
    expect(within(alerta).getByRole('button', { name: 'ciência #3' })).toHaveAttribute('data-evidencia', 'ciencia_alerta:3');
    expect(within(alerta).queryByRole('button', { name: /registrar ciência/i })).not.toBeInTheDocument();
  });

  it('Rota assinada: passo ainda sai, sempre com motivo', async () => {
    const user = userEvent.setup();
    const manual = { ...PASSO_MOTOR, id: 9, origem: 'manual', titulo: 'Protocolar ofício', fundamento_dispositivo_id: null, origem_avaliacao_id: null };
    servir({ '/processes/66/rota': { ...ROTA, status: 'validada', validated_at: '2026-09-23T00:00:00Z', passos: [PASSO_MOTOR, manual] }, '/motor/execucoes/ultima': EXECUCAO });
    vi.mocked(api.delete).mockResolvedValue({ data: null });
    render(comQuery(<RotaTab processId={66} />));
    await user.click(await screen.findByRole('button', { name: /remover passo 2: protocolar ofício/i }));
    expect(screen.getByLabelText(/obrigatório com a rota assinada/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /remover da rota/i })).toBeDisabled();
    expect(screen.queryByRole('button', { name: /validar passo/i })).not.toBeInTheDocument();
  });

  it('rodapé com o SHA está na tela da Rota', async () => {
    servir({ '/processes/66/rota': ROTA, '/motor/execucoes/ultima': EXECUCAO });
    render(comQuery(<RotaTab processId={66} />));
    const rodape = await screen.findByTestId('rodape-versao');
    await waitFor(() => expect(rodape).toHaveTextContent(/API abc1234 · desenvolvimento/));
  });
});

// ─── Comercial ──────────────────────────────────────────────────────────────

const VIGENTE = { estado: 'vigente', motivos: [] };
const revisao = { revisado_por_id: null, revisado_em: null, justificativa: null };

const RELATORIO = {
  id: 13, tipo: 'relatorio_preliminar', versao: 5, rota_id: 2, execucao_motor_id: 5, criado_por_id: 38,
  created_at: '2026-09-24T10:00:00Z', superada_em: null, estado_revisao: 'proposta', ...revisao, atualidade: VIGENTE,
  conteudo: {
    secoes: [{
      chave: 'situacao', titulo: 'Situação dos autos',
      afirmacoes: [{
        id: 'situacao:ccir.no_dossie', texto: 'Não consta CCIR nos autos.',
        evidencias: [{ tipo: 'avaliacao_regra', id: 28, rotulo: 'REG-FUN-002' }],
      }],
    }],
    limites: ['Relatório preliminar: não é parecer.'],
  },
};

const ESCOPO = {
  ...RELATORIO, id: 14, tipo: 'especificacao_escopo', estado_revisao: 'aprovada',
  conteudo: { secoes: [{ chave: 'incluido', titulo: 'O que será feito', afirmacoes: [] }] },
};

const ORCAMENTO = {
  id: 7, versao: 5, rota_id: 2, escopo_id: 14, total: '1800.00', created_at: '2026-09-24T10:00:00Z',
  criado_por_id: 38, superada_em: null, estado_revisao: 'aprovada', ...revisao,
  atualidade: { estado: 'desatualizado', motivos: ['O diagnóstico mudou'] },
  fora: [{ rota_passo_id: 6, titulo: 'Emitir ou regularizar o CCIR do imóvel', motivo: 'removido da Rota: cliente apresentará o CCIR' }],
  ressalvas: [{ tipo: 'diagnostico_em_revisao', texto: '1 conclusão do diagnóstico em revisão.', conclusoes: [5343] }],
  itens: [{
    id: 70, ordem: 1, rota_passo_id: 5, descricao: 'Verificar inscrição no CAR e inscrever o imóvel',
    fundamento: { caminho: 'Lei 12.651/2012, art. 29', rule_id: 'REG-BR-CAR-001', dispositivo_id: 41702, fonte_versao_id: 1313 },
    metodo: { id: 3, codigo: 'inscricao_car', versao: 1, nome: 'Inscrição no CAR' }, escolha: 'regra',
    unidade: 'fixo', quantidade: '1.00', valor_unitario: '1800.00', total: '1800.00', calculo: 'valor fixo R$ 1.800,00',
  }],
};

const METODOS = { correntes: [{ id: 3, codigo: 'inscricao_car', versao: 1, nome: 'Inscrição no CAR', unidade: 'fixo', valor_unitario: '1800.00', quantidade_padrao: '1.00', rule_ids: [], padrao: false, ativo: true }], versoes: [] };

function servirComercial(orcamento: unknown) {
  servir({
    '/comercial/redacao': { relatorio_preliminar: RELATORIO, especificacao_escopo: ESCOPO, versoes: [] },
    '/comercial/orcamento': { orcamento, versoes: [] },
    '/comercial/metodos': METODOS,
    '/processes/66': { id: 66, client_id: 40, title: 'Gate Inc2 caso 25' },
  });
}

describe('Comercial — relatório, escopo e orçamento (#282)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('afirmação mostra a evidência clicável; aprovar exige justificativa', async () => {
    const user = userEvent.setup();
    servirComercial(ORCAMENTO);
    vi.mocked(api.post).mockResolvedValue({ data: { ...RELATORIO, estado_revisao: 'aprovada' } });

    render(comQuery(<ComercialRotaPanel processId={66} />));
    const rel = await screen.findByTestId('redacao-relatorio_preliminar');
    expect(within(rel).getByText('Não consta CCIR nos autos.')).toBeInTheDocument();
    expect(within(rel).getByRole('button', { name: 'REG-FUN-002' })).toHaveAttribute('data-evidencia', 'avaliacao_regra:28');

    await user.click(within(rel).getByRole('button', { name: /aprovar relatório/i }));
    expect(api.post).not.toHaveBeenCalled();

    await user.type(within(rel).getByLabelText(/justificativa/i), 'confere com os autos');
    await user.click(within(rel).getByRole('button', { name: /aprovar relatório/i }));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/processes/66/comercial/redacao/13/revisar', {
        acao: 'aprovar',
        justificativa: 'confere com os autos',
      }),
    );
  });

  it('orçamento: item por passo, "fora" com motivo, desatualizado com motivos e proposta travada', async () => {
    servirComercial(ORCAMENTO);
    render(comQuery(<ComercialRotaPanel processId={66} />));

    const orc = await screen.findByTestId('orcamento');
    expect(within(orc).getByTestId('item-passo-5')).toHaveTextContent('Verificar inscrição no CAR');
    expect(within(orc).getByTestId('orcamento-total')).toHaveTextContent('1.800,00');
    expect(within(orc).getByTestId('orcamento-fora')).toHaveTextContent('cliente apresentará o CCIR');
    expect(within(orc).getByRole('alert')).toHaveTextContent('O diagnóstico mudou');
    expect(within(orc).getByRole('button', { name: /criar proposta deste orçamento/i })).toBeDisabled();
  });

  it('proposta nasce do orçamento aprovado e atual', async () => {
    const user = userEvent.setup();
    servirComercial({ ...ORCAMENTO, atualidade: VIGENTE });
    vi.mocked(api.post).mockResolvedValue({ data: { id: 91 } });

    render(comQuery(<ComercialRotaPanel processId={66} />));
    const botao = await screen.findByRole('button', { name: /criar proposta deste orçamento/i });
    await waitFor(() => expect(botao).toBeEnabled());
    await user.click(botao);

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/proposals/', {
        client_id: 40,
        process_id: 66,
        orcamento_id: 7,
        title: 'Gate Inc2 caso 25 — orçamento v5',
      }),
    );
    await waitFor(() => expect(navegar).toHaveBeenCalledWith('/proposals/91'));
  });

  it('trocar o método de um passo gera a versão seguinte pelo servidor', async () => {
    const user = userEvent.setup();
    servirComercial({ ...ORCAMENTO, estado_revisao: 'proposta', atualidade: VIGENTE });
    vi.mocked(api.patch).mockResolvedValue({ data: { ...ORCAMENTO, versao: 6 } });
    const metodos = { ...METODOS, correntes: [...METODOS.correntes, { ...METODOS.correntes[0], id: 1, codigo: 'hora_tecnica', nome: 'Hora técnica', unidade: 'hora' }] };
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url === '/comercial/metodos') return { data: metodos };
      if (url.includes('/comercial/redacao')) return { data: { relatorio_preliminar: RELATORIO, especificacao_escopo: ESCOPO, versoes: [] } };
      if (url.includes('/comercial/orcamento')) return { data: { orcamento: { ...ORCAMENTO, estado_revisao: 'proposta', atualidade: VIGENTE }, versoes: [] } };
      if (url.includes('/processes/66')) return { data: { id: 66, client_id: 40, title: 'x' } };
      throw nao404();
    });

    render(comQuery(<ComercialRotaPanel processId={66} />));
    const select = await screen.findByLabelText('Método do passo 5');
    await screen.findByRole('option', { name: 'Hora técnica' });
    await user.selectOptions(select, 'hora_tecnica');
    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/processes/66/comercial/orcamento/passos/5', {
        metodo_codigo: 'hora_tecnica',
        quantidade: null,
      }),
    );
  });
});
