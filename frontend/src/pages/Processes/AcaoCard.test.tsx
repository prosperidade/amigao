// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import type { Acao } from '@/lib/acoes/types';

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn(), patch: vi.fn(), put: vi.fn(), post: vi.fn() },
}));
vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

import { api } from '@/lib/api';
import AcaoCard from './AcaoCard';

function withQuery(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

const baseAcao: Acao = {
  id: 55,
  process_id: 42,
  titulo: 'Resolver divergência de total_area_ha (matrícula 4698)',
  descricao: null,
  origem: 'diagnostico',
  origem_descricao: 'Divergência: CCIR=349,90 vs SIGEF=350,00',
  origem_fontes: [
    { tipo: 'documento', descricao: 'CCIR', valor: '349,90' },
    { tipo: 'documento', descricao: 'SIGEF', valor: '350,00' },
  ],
  vinculo_passivo: { tipo: 'divergencia' },
  responsavel_id: null,
  prazo: null,
  prioridade: 'media',
  status: 'a_fazer',
  tipo_triagem: 'pendente',
  created_by_user_id: null,
  concluida_at: null,
  created_at: null,
  updated_at: null,
};

describe('AcaoCard (item 1 — ação editável)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('mostra o título legível (não o achado cru) e abre a edição já com ele', async () => {
    const user = userEvent.setup();
    render(withQuery(<AcaoCard acao={baseAcao} processId={42} />));

    // item 2: título humanizado na tela, não a string de máquina
    expect(
      screen.getByText('Padronizar Área total (ha) (matrícula 4698): CCIR: "349,90" vs SIGEF: "350,00"'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Resolver divergência de total_area_ha/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /editar ação/i }));

    const titulo = screen.getByLabelText('Título da ação') as HTMLInputElement;
    expect(titulo.value).toBe(
      'Padronizar Área total (ha) (matrícula 4698): CCIR: "349,90" vs SIGEF: "350,00"',
    );
  });

  it('salva título e descrição via PATCH no endpoint de ações', async () => {
    const user = userEvent.setup();
    (api.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { ...baseAcao } });
    render(withQuery(<AcaoCard acao={baseAcao} processId={42} />));

    await user.click(screen.getByRole('button', { name: /editar ação/i }));

    const titulo = screen.getByLabelText('Título da ação');
    await user.clear(titulo);
    await user.type(titulo, 'Atualizar área no SIGEF para 350,00 ha');

    const descricao = screen.getByLabelText('Descrição da ação');
    await user.type(descricao, 'Confirmar com o cartório e corrigir o CCIR.');

    await user.click(screen.getByRole('button', { name: /salvar/i }));

    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1));
    expect(api.patch).toHaveBeenCalledWith('/processes/42/acoes/55', {
      titulo: 'Atualizar área no SIGEF para 350,00 ha',
      descricao: 'Confirmar com o cartório e corrigir o CCIR.',
    });
  });

  it('não deixa salvar título vazio (botão desabilitado, sem PATCH)', async () => {
    const user = userEvent.setup();
    render(withQuery(<AcaoCard acao={baseAcao} processId={42} />));

    await user.click(screen.getByRole('button', { name: /editar ação/i }));
    await user.clear(screen.getByLabelText('Título da ação'));

    expect(screen.getByRole('button', { name: /salvar/i })).toBeDisabled();
    expect(api.patch).not.toHaveBeenCalled();
  });
});
