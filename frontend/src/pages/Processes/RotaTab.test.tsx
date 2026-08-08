// @vitest-environment jsdom
/**
 * GATE do PR — o gesto de reordenar, na UI, até o servidor e de volta.
 *
 * A regra da casa: funcionalidade que exige gesto humano só merge com E2E do
 * gesto. O gesto aqui é mover um passo de lugar; o que se prova é a queixa
 * inteira: a ordem VAI ao servidor (PATCH /reordenar com os ids na ordem nova),
 * a tela DIZ que salvou, e ao recarregar a ordem permaneceu.
 *
 * O gesto é exercido pelos botões ↑/↓ — a mesma ação do arrastar, mesmo
 * `salvarOrdem`, mesmo endpoint. Arrastar de verdade depende de layout e
 * pointer capture que o jsdom não tem; testar por ali provaria o framer-motion,
 * não a nossa regra. O que importa provar é que o gesto atravessa até o banco e
 * volta visível — e essa é exatamente a metade que faltava (#141: o sistema
 * gravava certo e a tela não mostrava).
 *
 * O segundo gate — passo removido não volta ao "Atualizar da IA" — vive aqui na
 * versão de TELA: prova que a UI honra o que o servidor devolve e que o consultor
 * é avisado da proposta recusada em seu nome. A garantia em si é do backend, onde
 * a regra realmente mora, e está provada contra banco real em
 * `tests/services/test_rota_materializer.py::test_passo_removido_nao_volta_na_regeneracao`
 * e `tests/api/test_rota_e5.py::test_passo_removido_nao_volta_ao_atualizar_da_ia`.
 * Aqui a API é mock; lá não é. Os dois níveis juntos fecham o gesto inteiro.
 */
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import RotaTab from './RotaTab';

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import { api } from '@/lib/api';
import toast from 'react-hot-toast';

function withQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>;
}

function passo(id: number, ordem: number, titulo: string) {
  return {
    id,
    ordem,
    titulo,
    descricao: null,
    orgao: null,
    prazo_estimado_dias: 30,
    prazo_fonte: 'norma',
    sources: [],
    norma_ref: 'Lei 12.651/2012',
    classificacao: 'item_proposta',
    origem: 'ia',
    origem_manual_nota: null,
    status: 'proposto',
  };
}

/** Rota do caso 16 reduzida ao que o gesto precisa: dois passos ordenáveis. */
function rota(passos: ReturnType<typeof passo>[]) {
  return {
    id: 2,
    process_id: 16,
    demand_type: 'nao_identificado',
    status: 'proposta',
    caminho_regulatorio: 'CAR → PRA → DAI',
    orgao_competente: null,
    validated_at: null,
    passos,
  };
}

const CAR = passo(40, 1, 'Inscrição e atualização do CAR');
const PRA = passo(41, 2, 'Elaboração e protocolo do PRA');

describe('RotaTab — reordenação persistida', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('mover um passo manda a ordem nova ao servidor e a tela confirma', async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({ data: rota([CAR, PRA]) });
    vi.mocked(api.patch).mockResolvedValue({ data: rota([PRA, CAR]) });

    render(withQuery(<RotaTab processId={16} />));
    await screen.findByText('Inscrição e atualização do CAR');

    // O gesto: descer o primeiro passo. É um <button> — logo, alcançável no
    // teclado, que era o buraco do arrastar sozinho.
    await user.click(screen.getByRole('button', { name: /descer passo 1 de 2/i }));

    await waitFor(() => expect(api.patch).toHaveBeenCalled());
    expect(api.patch).toHaveBeenCalledWith('/rotas/2/reordenar', {
      passo_ids: [41, 40],
    });

    // A tela ADMITE ter gravado — sem isto, ordem salva e ordem perdida ficam
    // indistinguíveis para quem está olhando (#141).
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Ordem salva.'));
  });

  it('ao recarregar, a ordem permaneceu', async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({ data: rota([CAR, PRA]) });
    vi.mocked(api.patch).mockResolvedValue({ data: rota([PRA, CAR]) });

    const { unmount } = render(withQuery(<RotaTab processId={16} />));
    await screen.findByText('Inscrição e atualização do CAR');
    await user.click(screen.getByRole('button', { name: /descer passo 1 de 2/i }));
    await waitFor(() => expect(api.patch).toHaveBeenCalled());

    // Recarregar de verdade: desmonta, zera o cache e sobe de novo lendo o que o
    // servidor passou a devolver. Ordem que só vive no estado local morreria aqui.
    unmount();
    vi.mocked(api.get).mockResolvedValue({ data: rota([PRA, CAR]) });
    render(withQuery(<RotaTab processId={16} />));

    await screen.findByText('Elaboração e protocolo do PRA');
    expect(
      screen.getByRole('button', { name: /descer passo 1 de 2/i }),
    ).toBeInTheDocument();
    // O PRA agora é o passo 1: não há para onde subir.
    expect(screen.getByRole('button', { name: /subir passo 1 de 2/i })).toBeDisabled();
  });

  it('falha ao salvar devolve a ordem anterior à tela', async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({ data: rota([CAR, PRA]) });
    vi.mocked(api.patch).mockRejectedValue(new Error('500'));

    render(withQuery(<RotaTab processId={16} />));
    await screen.findByText('Inscrição e atualização do CAR');
    await user.click(screen.getByRole('button', { name: /descer passo 1 de 2/i }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    // Mantida no lugar de origem: deixar na tela uma ordem que não foi gravada
    // seria contar a mentira que o #141 ensinou a não contar.
    const posicoes = screen
      .getAllByRole('button', { name: /descer passo/i })
      .map(b => b.getAttribute('aria-label'));
    expect(posicoes[0]).toMatch(/descer passo 1 de 2/i);
    expect(screen.getByText('Inscrição e atualização do CAR')).toBeInTheDocument();
  });

  it('GATE: passo removido não volta ao "Atualizar da IA"', async () => {
    const user = userEvent.setup();
    // Estado 1: rota cheia. Depois da remoção, o servidor passa a devolver só o
    // CAR — e continua devolvendo só o CAR depois da regeneração.
    vi.mocked(api.get).mockResolvedValue({ data: rota([CAR, PRA]) });
    vi.mocked(api.delete).mockResolvedValue({ data: null });
    vi.mocked(api.post).mockResolvedValue({
      data: {
        created: 0,
        matched: 1,
        is_diff: false,
        suprimidos: 1,
        rota: rota([CAR]),
      },
    });

    render(withQuery(<RotaTab processId={16} />));
    await screen.findByText('Elaboração e protocolo do PRA');

    // Gesto 1 — remover o PRA (o gesto que a consultora fez 4× em 11 segundos).
    vi.mocked(api.get).mockResolvedValue({ data: rota([CAR]) });
    await user.click(
      screen.getByRole('button', { name: /remover passo 2: elaboração e protocolo do PRA/i }),
    );
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/rotas/2/passos/41'));
    await waitFor(() =>
      expect(screen.queryByText('Elaboração e protocolo do PRA')).not.toBeInTheDocument(),
    );

    // Gesto 2 — "Atualizar da IA", com a IA repropondo o passo removido.
    await user.click(screen.getByRole('button', { name: /atualizar da ia/i }));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/processes/16/rota/gerar'),
    );

    // O passo NÃO voltou. Esta é a queixa de 02/08 fechada na tela.
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(screen.queryByText('Elaboração e protocolo do PRA')).not.toBeInTheDocument();
    expect(screen.getByText('Inscrição e atualização do CAR')).toBeInTheDocument();

    // E a tela DIZ que houve proposta recusada em nome do consultor: sem esta
    // frase ele leria "nenhum passo novo" e concluiria que nada rodou.
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.stringContaining('1 passo(s) que você removeu continuam fora'),
        expect.anything(),
      ),
    );
  });

  it('rota fechada não se reordena', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { ...rota([CAR, PRA]), status: 'validada' },
    });

    render(withQuery(<RotaTab processId={16} />));
    await screen.findByText('Inscrição e atualização do CAR');

    expect(screen.getByRole('button', { name: /descer passo 1 de 2/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /subir passo 2 de 2/i })).toBeDisabled();
  });
});
