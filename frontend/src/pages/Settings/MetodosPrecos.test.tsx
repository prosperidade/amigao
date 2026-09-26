// @vitest-environment jsdom
/**
 * Gestos da tela de métodos e preços (#282): cada salvar vai ao servidor como a VERSÃO seguinte
 * do método (`POST /comercial/metodos`, mesmo código). A regra de versão e de "um padrão só" mora
 * no backend (`tests/comercial/`); aqui se prova o que a tela manda e o que ela mostra.
 */
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetodosPrecos from './MetodosPrecos';

vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));
vi.mock('@/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }));

import { api } from '@/lib/api';

const HORA = { id: 1, codigo: 'hora_tecnica', versao: 1, nome: 'Hora técnica', unidade: 'hora', valor_unitario: '250.00', quantidade_padrao: '8.00', rule_ids: [], padrao: true, ativo: true };
const CCIR = { id: 2, codigo: 'ccir', versao: 1, nome: 'Emissão de CCIR', unidade: 'fixo', valor_unitario: '900.00', quantidade_padrao: '1.00', rule_ids: ['REG-FUN-002'], padrao: false, ativo: true };

function servir(versoes: object[]) {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === '/comercial/metodos') return { data: { correntes: versoes, versoes } };
    if (url === '/motor-juridico/regras') return { data: [{ rule_id: 'REG-FUN-002' }, { rule_id: 'REG-BR-CAR-001' }] };
    if (url === '/versao') return { data: { commit: 'abc1234', ambiente: 'development' } };
    throw new Error(`GET inesperado ${url}`);
  });
}

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MetodosPrecos /></QueryClientProvider>);
}

describe('Métodos e preços do tenant', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lista os métodos com preço, unidade, regra e o padrão', async () => {
    servir([HORA, CCIR]);
    montar();
    expect(await screen.findByTestId('preco-hora_tecnica')).toHaveTextContent('250,00');
    expect(screen.getByTestId('preco-ccir')).toHaveTextContent('valor fixo');
    expect(screen.getByText(/Regras: REG-FUN-002/)).toBeInTheDocument();
    expect(screen.getByText('padrão')).toBeInTheDocument();
    expect(await screen.findByTestId('rodape-versao')).toBeInTheDocument();
  });

  it('mudar o preço salva a versão seguinte do mesmo código', async () => {
    const user = userEvent.setup();
    servir([HORA, CCIR]);
    vi.mocked(api.post).mockResolvedValue({ data: { ...CCIR, versao: 2, valor_unitario: '950.00' } });
    montar();
    await user.click(await screen.findByRole('button', { name: 'Editar Emissão de CCIR' }));
    const form = screen.getByTestId('form-metodo');
    const valor = within(form).getByLabelText('Valor unitário (R$)');
    await user.clear(valor);
    await user.type(valor, '950,00');
    await user.click(within(form).getByRole('button', { name: 'Salvar nova versão' }));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/comercial/metodos', {
        codigo: 'ccir', nome: 'Emissão de CCIR', unidade: 'fixo', valor_unitario: '950.00',
        quantidade_padrao: '1', rule_ids: ['REG-FUN-002'], padrao: false, ativo: true,
      }),
    );
  });

  it('método novo com regra do motor', async () => {
    const user = userEvent.setup();
    servir([HORA]);
    vi.mocked(api.post).mockResolvedValue({ data: { ...CCIR, id: 3, codigo: 'inscricao_car', versao: 1 } });
    montar();
    await user.click(await screen.findByRole('button', { name: /novo método/i }));
    const form = screen.getByTestId('form-metodo');
    expect(within(form).getByRole('button', { name: 'Criar método' })).toBeDisabled();
    await user.type(within(form).getByLabelText('Código'), 'inscricao_car');
    await user.type(within(form).getByLabelText('Nome'), 'Inscrição no CAR');
    await user.selectOptions(within(form).getByLabelText('Unidade'), 'fixo');
    await user.type(within(form).getByLabelText('Valor unitário (R$)'), '1800');
    await user.click(await within(form).findByLabelText('REG-BR-CAR-001'));
    await user.click(within(form).getByRole('button', { name: 'Criar método' }));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/comercial/metodos', {
        codigo: 'inscricao_car', nome: 'Inscrição no CAR', unidade: 'fixo', valor_unitario: '1800',
        quantidade_padrao: '1', rule_ids: ['REG-BR-CAR-001'], padrao: false, ativo: true,
      }),
    );
  });

  it('desativar é versão nova com ativo falso (e deixa de ser padrão)', async () => {
    const user = userEvent.setup();
    servir([HORA, CCIR]);
    vi.mocked(api.post).mockResolvedValue({ data: { ...HORA, versao: 2, ativo: false, padrao: false } });
    montar();
    await user.click(await screen.findByRole('button', { name: 'Desativar Hora técnica' }));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/comercial/metodos', expect.objectContaining({
        codigo: 'hora_tecnica', ativo: false, padrao: false,
      })),
    );
  });

  it('sem padrão ativo, a tela avisa que o orçamento será recusado', async () => {
    servir([CCIR]);
    montar();
    expect(await screen.findByRole('alert')).toHaveTextContent('Nenhum método padrão ativo');
  });
});
