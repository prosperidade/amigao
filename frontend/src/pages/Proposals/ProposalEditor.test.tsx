// @vitest-environment jsdom
/**
 * #284 (ADR-081): proposta de um caso só nasce do orçamento aprovado do tenant.
 *
 * A recusa é do servidor (`/proposals/generate-draft` e `POST /proposals` devolvem 422 sem Rota
 * assinada ou sem orçamento — provado em `tests/api/test_proposal_rota_s5a.py`). Aqui se prova
 * que a tela não deixa o consultor digitar uma proposta por fora: sem orçamento, a mensagem da
 * API aparece, o criar fica desabilitado e há o atalho para o Comercial do caso; com orçamento,
 * os itens vêm travados e o `orcamento_id` vai no corpo.
 */
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProposalEditor from './ProposalEditor';

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));
vi.mock('@/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const navegar = vi.fn();
vi.mock('react-router-dom', async orig => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useNavigate: () => navegar,
}));

import { api } from '@/lib/api';

const RECUSA = 'A proposta nasce do orçamento: gere e aprove o relatório, o escopo e o orçamento da Rota assinada (aba Comercial) antes da proposta.';

function servir(draft: { status: number; data: unknown }) {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url.startsWith('/proposals/generate-draft')) {
      if (draft.status !== 200) throw Object.assign(new Error('422'), { response: { status: draft.status, data: draft.data } });
      return { data: draft.data };
    }
    if (url === '/clients/') return { data: [{ id: 40, full_name: 'Cliente', email: null }] };
    if (url === '/processes/69' || url === '/processes/66') return { data: { id: 66, client_id: 40, title: 'Caso' } };
    throw new Error(`GET inesperado ${url}`);
  });
}

function montar(pid: number) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={[`/proposals/new?process_id=${pid}`]}>
      <QueryClientProvider client={qc}>
        <Routes><Route path="/proposals/new" element={<ProposalEditor />} /></Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe('Proposta de caso nasce do orçamento (#284)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sem orçamento: mostra a recusa da API, bloqueia o criar e leva ao Comercial', async () => {
    const user = userEvent.setup();
    servir({ status: 422, data: { detail: RECUSA } });
    montar(69);
    expect(await screen.findByText(RECUSA)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Criar Proposta' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: /Ir para relatório, escopo e orçamento/ }));
    expect(navegar).toHaveBeenCalledWith('/processes/69?tab=commercial');
    expect(api.post).not.toHaveBeenCalled();
  });

  it('com orçamento: itens travados e o orçamento vai no corpo', async () => {
    const user = userEvent.setup();
    servir({
      status: 200,
      data: {
        title: 'Proposta — Caso', complexity: 'baixa', payment_terms: '50/50', notes: 'n', rota_id: 2,
        orcamento_id: 17, suggested_value: 1900, suggested_value_min: 1900, suggested_value_max: 1900,
        estimated_days: 0,
        scope_items: [{ description: 'Inscrição no CAR', unit: 'serv.', qty: 1, unit_price: 1900, total: 1900, rota_passo_id: 5 }],
      },
    });
    vi.mocked(api.post).mockResolvedValue({ data: { id: 91 } });
    montar(66);
    expect(await screen.findByText(/do orçamento #17/)).toBeInTheDocument();
    expect(screen.getByDisplayValue('Inscrição no CAR')).toBeDisabled();
    const criar = screen.getByRole('button', { name: 'Criar Proposta' });
    await waitFor(() => expect(criar).toBeEnabled());
    await user.click(criar);
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(vi.mocked(api.post).mock.calls[0][1]).toMatchObject({ process_id: 66, orcamento_id: 17 });
  });
});
