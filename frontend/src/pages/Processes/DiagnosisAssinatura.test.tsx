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
  api: { get: vi.fn(), patch: vi.fn(), post: vi.fn() },
}));

import { api } from '@/lib/api';
import DiagnosisAssinatura from './DiagnosisAssinatura';

function withQuery(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

const ISSUE_CRITICA = {
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
};

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
        return { data: [ISSUE_CRITICA] };
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

    const validar = await screen.findByRole('button', { name: /Validar diagnóstico/i });
    await user.click(validar);

    // Modal abre listando o alerta pendente
    await waitFor(() => {
      expect(screen.getByText(/Faltam decisões para validar/i)).toBeInTheDocument();
    });
    expect(screen.getByText('GEO_AUSENTE')).toBeInTheDocument();

    // Click no item dispara onGoToAlerta com o id correto
    await user.click(screen.getByText('GEO_AUSENTE'));
    expect(onGoToAlerta).toHaveBeenCalledWith(99);
  });

  it('renderiza card "validado" quando já validated_at', async () => {
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
      await screen.findByText(/Diagnóstico v2 validado/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Validar diagnóstico/i }),
    ).not.toBeInTheDocument();
  });
});

/**
 * E2E do GESTO (regra da casa, 26/07): gate que exige ato humano só mergeia com
 * teste do gesto na UI. Aqui o cenário exato do caso 15 — nenhum
 * `RegulatoryDiagnosis` criado, apenas a análise do agente. Antes deste PR a tela
 * não mostrava botão nenhum e o gate E2→E3 ficava intransponível.
 */
describe('DiagnosisAssinatura — maçaneta do gate E2→E3 (caso 15)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sem diagnóstico criado: um clique materializa da análise e valida', async () => {
    // Estado inicial: lista de diagnoses VAZIA (é o processo 15 medido em prod).
    let diagnoses: unknown[] = [];
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url.includes('/diagnoses')) return { data: diagnoses };
      return { data: [] }; // sem issues críticas
    });

    // POST /diagnoses/from-agent → materializa v1 (não validada)
    vi.mocked(api.post).mockImplementation(async (url: string) => {
      if (url.includes('/diagnoses/from-agent')) {
        const criada = {
          id: 10,
          process_id: 42,
          version: 1,
          validated_by_user_id: null,
          validated_at: null,
          created_at: null,
          updated_at: null,
        };
        diagnoses = [criada];
        return { data: criada };
      }
      throw new Error('URL não mapeada: ' + url);
    });

    // PATCH .../1/validate → assinada
    vi.mocked(api.patch).mockImplementation(async (url: string) => {
      if (url.includes('/validate')) {
        const validada = {
          id: 10,
          process_id: 42,
          version: 1,
          validated_by_user_id: 3,
          validated_at: '2026-07-27T12:00:00Z',
          created_at: null,
          updated_at: null,
        };
        diagnoses = [validada];
        return { data: validada };
      }
      throw new Error('URL não mapeada: ' + url);
    });

    const user = userEvent.setup();
    render(withQuery(<DiagnosisAssinatura processId={42} propertyId={7} />));

    // A maçaneta EXISTE mesmo sem diagnóstico criado.
    const validar = await screen.findByRole('button', { name: /Validar diagnóstico/i });
    await user.click(validar);

    // Um gesto → dois passos no backend, nessa ordem.
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/processes/42/diagnoses/from-agent');
    });
    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/processes/42/diagnoses/1/validate');
    });

    // Estado final na tela: validado (é o que libera o gate E2→E3).
    expect(await screen.findByText(/Diagnóstico v1 validado/i)).toBeInTheDocument();
  });

  it('sem análise do agente: 422 acionável, sem quebrar a tela', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [] });
    vi.mocked(api.post).mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail:
            'Nenhuma análise de diagnóstico concluída neste processo — rode o agente de diagnóstico antes de validar.',
        },
      },
    } as unknown as AxiosError);

    const toast = (await import('react-hot-toast')).default;
    const user = userEvent.setup();
    render(withQuery(<DiagnosisAssinatura processId={42} propertyId={7} />));

    await user.click(await screen.findByRole('button', { name: /Validar diagnóstico/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining('rode o agente de diagnóstico'),
      );
    });
    // Nunca chega a chamar o validate sem versão materializada.
    expect(api.patch).not.toHaveBeenCalled();
  });
});
