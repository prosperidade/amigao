// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CredentialsTab from './index';

vi.mock('react-hot-toast', () => ({
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

vi.mock('@/lib/api', () => ({
  api: {
    delete: vi.fn(),
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
  },
}));

import { api } from '@/lib/api';

function withQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>;
}

describe('CredentialsTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renderiza lista vazia', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [] });

    render(withQuery(<CredentialsTab clientId={7} />));

    expect(screen.getByText('Credenciais de Portal')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Nenhuma credencial cadastrada/i)).toBeInTheDocument();
    });
    expect(api.get).toHaveBeenCalledWith('/credentials?client_id=7');
  });

  it('renderiza credencial com senha protegida e sem revelar senha', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: [
        {
          id: 1,
          client_id: 7,
          portal: 'sema',
          label: 'SEMA-GO',
          login: 'usuario.portal',
          url: 'https://portal.example.test',
          notes: 'Acesso do cliente',
          has_password: true,
          created_at: '2026-05-31T12:00:00Z',
        },
      ],
    });

    render(withQuery(<CredentialsTab clientId={7} />));

    expect(await screen.findByText('SEMA-GO')).toBeInTheDocument();
    expect(screen.getByText('Senha protegida')).toBeInTheDocument();
    expect(screen.getByText('usuario.portal')).toBeInTheDocument();
    expect(screen.queryByText(/Ver senha/i)).not.toBeInTheDocument();
  });

  it('abre modal de adicionar e envia POST com client_id', async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({ data: [] });
    vi.mocked(api.post).mockResolvedValue({ data: {} });

    render(withQuery(<CredentialsTab clientId={7} />));

    await user.click(screen.getByRole('button', { name: /Adicionar/i }));
    await user.type(screen.getByLabelText(/Nome amigavel/i), 'SEMA-GO');
    await user.type(screen.getByLabelText(/^Login$/i), 'usuario.portal');
    await user.type(screen.getByLabelText(/^Senha$/i), 'senha-super-secreta');
    await user.click(screen.getAllByRole('button', { name: /^Adicionar$/i })[1]);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/credentials', expect.objectContaining({
        client_id: 7,
        label: 'SEMA-GO',
        login: 'usuario.portal',
        password: 'senha-super-secreta',
        portal: 'sema',
      }));
      // timeout de parede: sob a suíte cheia (13 arquivos em paralelo) o worker
      // sofre contenção de CPU e o default de 1s flakeia — medido no Sprint 3.
    }, { timeout: 5000 });
  });

  it('preserva senha no PATCH quando campo fica vazio no modo editar', async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      data: [
        {
          id: 1,
          client_id: 7,
          portal: 'sema',
          label: 'SEMA-GO',
          login: 'usuario.portal',
          url: null,
          notes: null,
          has_password: true,
          created_at: null,
        },
      ],
    });
    vi.mocked(api.patch).mockResolvedValue({ data: {} });

    render(withQuery(<CredentialsTab clientId={7} />));

    await screen.findByText('SEMA-GO');
    await user.click(screen.getByRole('button', { name: /Editar credencial/i }));
    await user.clear(screen.getByLabelText(/Nome amigavel/i));
    await user.type(screen.getByLabelText(/Nome amigavel/i), 'SEMA-MT');
    await user.click(screen.getByRole('button', { name: /^Salvar$/i }));

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/credentials/1', expect.not.objectContaining({
        password: expect.any(String),
      }));
      expect(api.patch).toHaveBeenCalledWith('/credentials/1', expect.objectContaining({
        label: 'SEMA-MT',
      }));
    }, { timeout: 5000 });
  });
});
