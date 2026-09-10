// @vitest-environment jsdom
/**
 * GATE do PR (Frente G, ADR-067) — a Conferência renderiza DECISÕES, não
 * campos: a matrícula 3.181 citada pelo CAR e pela certidão vira UMA decisão,
 * com as duas evidências expansíveis. Decidir grava as linhas que ela agrupa
 * (consolidated_at existente); recarregar mantém o estado — não é um flag
 * otimista que evapora ao trocar de tela.
 */
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DecisoesPanel from './DecisoesPanel';

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

import { api } from '@/lib/api';

function withQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>;
}

/** REC-001: matrícula 3.181 citada pelo CAR e pela certidão — uma decisão só. */
function decisaoComposicao(over: Record<string, unknown> = {}) {
  return {
    chave: { entidade: 'matricula', identificador: '3181', aspecto: 'composicao' },
    chave_str: 'matricula:3181:composicao',
    label: 'Matrícula 3181 integra o imóvel',
    evidencias: [
      {
        staging_id: 1, documento_id: 10, documento_tipo: 'car', campo: 'matricula_listada',
        valor_bruto: { numero: '3181' }, valor_normalizado: { numero: '3181' },
        unidade: null, vigencia: null, status: 'pendente', fonte_autoritativa: false,
      },
      {
        staging_id: 2, documento_id: 11, documento_tipo: 'matricula', campo: 'numero_matricula',
        valor_bruto: '3.181', valor_normalizado: '3.181',
        unidade: null, vigencia: null, status: 'pendente', fonte_autoritativa: true,
      },
    ],
    concordancia: 'concordam',
    nivel_divergencia: null,
    delta: null,
    percentual: null,
    valor_proposto: '3.181',
    fonte_autoritativa_doc: 'matricula',
    estado: 'pendente',
    staging_ids: [1, 2],
    ...over,
  };
}

describe('DecisoesPanel — a Conferência por decisões (REC-001 + CONF-001)', () => {
  let decisoes: Array<Record<string, unknown>>;

  beforeEach(() => {
    vi.clearAllMocks();
    decisoes = [decisaoComposicao()];
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url.includes('/staging-decisions')) {
        return Promise.resolve({ data: { decisoes, sem_agrupamento: [], total_staging: 2 } });
      }
      return Promise.resolve({ data: [] });
    });
  });

  it('agrupa CAR + certidão numa decisão só, não duas linhas', async () => {
    render(withQuery(<DecisoesPanel processId={23} />));

    expect(await screen.findByText('Matrícula 3181 integra o imóvel')).toBeInTheDocument();
    // uma decisão só na tela — não duas entradas de campo.
    expect(screen.getAllByText(/Matrícula 3181 integra o imóvel/)).toHaveLength(1);
  });

  it('evidências concordantes vêm recolhidas, mas acessíveis (CONF-001)', async () => {
    render(withQuery(<DecisoesPanel processId={23} />));
    await screen.findByText('Matrícula 3181 integra o imóvel');

    expect(screen.queryByText('numero_matricula')).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByText('Matrícula 3181 integra o imóvel'));
    expect(await screen.findByText('numero_matricula')).toBeInTheDocument();
    expect(screen.getByText('fonte autoritativa')).toBeInTheDocument();
  });

  it('divergência vem expandida por padrão, com o nível visível', async () => {
    decisoes = [decisaoComposicao({
      concordancia: 'divergem', nivel_divergencia: 'critico', percentual: 0.1119,
      label: 'Reserva Legal',
    })];
    render(withQuery(<DecisoesPanel processId={23} />));

    await screen.findByText('Reserva Legal');
    expect(screen.getByText(/Divergência/)).toBeInTheDocument();
    expect(screen.getByText('numero_matricula')).toBeInTheDocument(); // já expandida
  });

  it('o GESTO: decidir a decisão grava as linhas agrupadas — e recarregar mantém', async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockImplementation(async () => {
      decisoes = [decisaoComposicao({ estado: 'decidida' })];
      return { data: decisoes[0] };
    });

    render(withQuery(<DecisoesPanel processId={23} />));
    await screen.findByText('Pendente');

    await user.click(screen.getByRole('button', { name: /Aceitar proposta/ }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/processes/23/staging-decisions/decidir', {
        entidade: 'matricula', identificador: '3181', aspecto: 'composicao', acao: 'aceitar',
      });
    });
    expect(await screen.findByText('Decidida — aguardando gravação')).toBeInTheDocument();

    // "recarregar mantém": uma montagem NOVA (equivalente a trocar de aba e
    // voltar) lê o mesmo estado do servidor — não é um flag otimista do
    // componente anterior que evaporaria com ele.
    cleanup();
    render(withQuery(<DecisoesPanel processId={23} />));
    expect(await screen.findByText('Decidida — aguardando gravação')).toBeInTheDocument();
  });

  it('gravada mostra o selo "Gravado na base" (Aceito ≠ Gravado)', async () => {
    decisoes = [decisaoComposicao({ estado: 'gravada' })];
    render(withQuery(<DecisoesPanel processId={23} />));

    expect(await screen.findByText('Gravado na base')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reabrir/ })).toBeInTheDocument();
  });

  it('sem decisões, o painel não renderiza nada (sem_agrupamento continua na tela antiga)', async () => {
    decisoes = [];
    const { container } = render(withQuery(<DecisoesPanel processId={23} />));
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
