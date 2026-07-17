// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { Acao } from '@/lib/acoes/types';

const noopMut = { mutate: vi.fn(), isPending: false };
vi.mock('@/lib/acoes/hooks', () => ({
  useAcoes: vi.fn(),
  useGenerateAcoes: () => noopMut,
  useCreateAcao: () => noopMut,
  useUpdateAcao: () => noopMut,
  useTriarAcao: () => noopMut,
}));
vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

import { useAcoes } from '@/lib/acoes/hooks';
import AcoesTab from './AcoesTab';

function makeAcao(over: Partial<Acao>): Acao {
  return {
    id: 1, process_id: 1, titulo: '', descricao: null, origem: 'manual',
    origem_descricao: null, origem_fontes: [], vinculo_passivo: null,
    responsavel_id: null, prazo: null, prioridade: 'media', status: 'a_fazer',
    tipo_triagem: 'pendente', created_by_user_id: null, concluida_at: null,
    created_at: null, updated_at: null, ...over,
  };
}

const LISTA: Acao[] = [
  makeAcao({ id: 1, titulo: 'Tarefa ativa', tipo_triagem: 'tarefa' }),
  makeAcao({ id: 2, titulo: 'Ação dispensada', tipo_triagem: 'dispensada' }),
];

describe('AcoesTab (item 3 — dispensada some da visão default)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useAcoes as ReturnType<typeof vi.fn>).mockReturnValue({ data: LISTA, isLoading: false });
  });

  it('oculta a ação dispensada por padrão, mas mantém as demais', () => {
    render(<AcoesTab processId={1} />);
    expect(screen.getByText('Tarefa ativa')).toBeInTheDocument();
    expect(screen.queryByText('Ação dispensada')).not.toBeInTheDocument();
  });

  it('revela as dispensadas ao clicar em "Mostrar dispensadas" e volta a ocultar', async () => {
    const user = userEvent.setup();
    render(<AcoesTab processId={1} />);

    const toggle = screen.getByRole('button', { name: /mostrar dispensadas \(1\)/i });
    await user.click(toggle);
    expect(screen.getByText('Ação dispensada')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /ocultar dispensadas \(1\)/i }));
    expect(screen.queryByText('Ação dispensada')).not.toBeInTheDocument();
  });
});
