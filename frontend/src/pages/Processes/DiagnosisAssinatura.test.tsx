// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import type { AxiosError } from 'axios';

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));
vi.mock('@/lib/api', () => ({
  api: { get: vi.fn(), patch: vi.fn() },
}));

import { api } from '@/lib/api';
import DiagnosisAssinatura from './DiagnosisAssinatura';

function withQuery(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

describe('DiagnosisAssinatura — gate camada 2 (modal 422)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('422 do gate abre modal com alertas_pendentes; click no item chama onGoToAlerta', async () => {
    // Diagnoses → 1 versão não validada
    // Issues → 1 crítica aberta
    // Decision → 404 (sem decisão)
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url.includes('/diagnoses')) {
        return {
          data: [
            {
              id: 1,
              process_id: 42,
              version: 3,
              validated_by_user_id: null,
              validated_at: null,
              created_at: null,
              updated_at: null,
            },
          ],
        };
      }
      if (url.endsWith('/issues') || url.includes('/issues?')) {
        return {
          data: [
            {
              id: 99,
              property_id: 7,
              document_id: null,
              codigo_alerta: 'GEO_AUSENTE',
              familia: 'geo_incra',
              severity: 'critico',
              status_achado: 'suspeita',
              status_saneamento: 'pendente',
              type: null,
              payload: null,
              detected_by: null,
              detected_at: '2026-05-26T00:00:00Z',
              resolved_at: null,
              muda_rota_regulatoria: null,
              muda_escopo_preco_prazo: null,
              documentos_cruzados: null,
            },
          ],
        };
      }
      if (url.includes('/issues/') && url.includes('/decision')) {
        throw { response: { status: 404 } } as unknown as AxiosError;
      }
      throw new Error('URL não mapeada: ' + url);
    });

    // PATCH /validate → 422 com alertas_pendentes (shape do gate camada 2)
    vi.mocked(api.patch).mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail: {
            message: '1 alerta(s) crítico(s) sem decisão neste processo',
            alertas_pendentes: [
              {
                id: 99,
                codigo_alerta: 'GEO_AUSENTE',
                familia: 'geo_incra',
                severity: 'critico',
              },
            ],
          },
        },
      },
    } as unknown as AxiosError);

    const onGoToAlerta = vi.fn();
    const user = userEvent.setup();

    render(
      withQuery(
        <DiagnosisAssinatura processId={42} propertyId={7} onGoToAlerta={onGoToAlerta} />,
      ),
    );

    // Botão "Assinar" aparece após carregar diagnoses
    const assinar = await screen.findByRole('button', { name: /Assinar/i });
    await user.click(assinar);

    // Modal abre listando o alerta pendente
    await waitFor(() => {
      expect(screen.getByText(/Faltam decisões para assinar/i)).toBeInTheDocument();
    });
    expect(screen.getByText('GEO_AUSENTE')).toBeInTheDocument();

    // Click no item dispara onGoToAlerta com o id correto
    await user.click(screen.getByText('GEO_AUSENTE'));
    expect(onGoToAlerta).toHaveBeenCalledWith(99);
  });

  it('renderiza card "assinado" quando já validated_at', async () => {
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url.includes('/diagnoses')) {
        return {
          data: [
            {
              id: 1,
              process_id: 42,
              version: 2,
              validated_by_user_id: 5,
              validated_at: '2026-05-26T15:00:00Z',
              created_at: null,
              updated_at: null,
            },
          ],
        };
      }
      // Sem issues
      return { data: [] };
    });

    render(withQuery(<DiagnosisAssinatura processId={42} propertyId={7} />));

    expect(
      await screen.findByText(/Diagnóstico v2 assinado/i),
    ).toBeInTheDocument();
    // Não há botão "Assinar"
    expect(screen.queryByRole('button', { name: /Assinar/i })).not.toBeInTheDocument();
  });

  it('renderiza nada quando ainda não há diagnóstico (silencioso)', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [] });

    const { container } = render(
      withQuery(<DiagnosisAssinatura processId={42} propertyId={7} />),
    );

    await waitFor(() => {
      expect(container.querySelector('button')).toBeNull();
    });
    expect(screen.queryByText(/Assinar/i)).not.toBeInTheDocument();
  });
});
