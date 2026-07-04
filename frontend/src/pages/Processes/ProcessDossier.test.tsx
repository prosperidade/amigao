// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProcessDossier from './ProcessDossier';

vi.mock('react-hot-toast', () => ({
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
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

const DOSSIER_FIXTURE = {
  process_id: 1,
  process: { id: 1, title: 'Caso', status: 'triagem' },
  client: null,
  property: {
    id: 10,
    name: 'Fazenda Selo',
    registry_number: null,
    ccir: null,
    nirf: null,
    car_code: 'GO-123-ABC',
    car_status: 'ativo',
    total_area_ha: null,
    municipality: 'Uirapuru',
    state: 'GO',
    biome: 'Cerrado',
    has_embargo: false,
    has_geom: false,
    field_sources: { car_code: 'pendente_oficializacao' },
    matriculas: [
      {
        id: 5,
        numero_matricula: '4.698',
        geo_certificacao_codigo: 'SIGEF-XYZ',
        geo_certificacao_status: 'certificada',
        codigo_incra_sncr: null,
        nirf_cib: '1234567-8',
        area_ha: 660.6561,
        field_sources: {},
      },
    ],
    areas: {
      area_documental_ha: null,
      area_grafica_ha: 1010.71,
      area_total_matriculas_ha: 660.6561,
    },
  },
  documents: [],
  checklist_summary: null,
  tasks_summary: {},
  previous_processes: [],
  inconsistencies: [],
};

describe('ProcessDossier — selo de 3 estados (Ficha 07 §3.4)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.get).mockResolvedValue({ data: DOSSIER_FIXTURE });
  });

  it('exibe o rótulo COMPLETO "Correto, pendente de oficialização" (sem abreviar)', async () => {
    render(withQuery(<ProcessDossier processId={1} />));

    // badge do campo selado + opção do seletor — rótulo integral, decisão travada
    const completos = await screen.findAllByText('Correto, pendente de oficialização');
    expect(completos.length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/^Pendente$/)).not.toBeInTheDocument();
  });

  it('exibe os campos-chave copiáveis (SIGEF, CAR, NIRF)', async () => {
    render(withQuery(<ProcessDossier processId={1} />));

    expect(await screen.findByText('SIGEF-XYZ')).toBeInTheDocument();
    expect(screen.getByText('1234567-8')).toBeInTheDocument();
    expect(screen.getByTitle('Copiar Nº SIGEF')).toBeInTheDocument();
    expect(screen.getByTitle('Copiar CAR')).toBeInTheDocument();
    // INCRA/SNCR ausente → sem botão de copiar (não há o que copiar)
    expect(screen.queryByTitle('Copiar INCRA/SNCR')).not.toBeInTheDocument();
  });

  it('área documental sem fonte mostra "—" honesto com nota', async () => {
    render(withQuery(<ProcessDossier processId={1} />));

    await screen.findByText('Áreas');
    expect(screen.getByText('Sem fonte no staging — dado ausente, não erro.')).toBeInTheDocument();
    expect(screen.getByText('1010.71 ha')).toBeInTheDocument();
    expect(screen.getByText('Derivada da soma das matrículas')).toBeInTheDocument();
  });

  it('trocar o selo chama POST /processes/{pid}/field-selo com o destino do campo', async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({ data: { acao_criada: true } });
    render(withQuery(<ProcessDossier processId={1} />));

    const select = await screen.findByLabelText('Selo de Nº SIGEF');
    await user.selectOptions(select, 'pendente_oficializacao');

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/processes/1/field-selo', {
        entity: 'matricula',
        entity_id: 5,
        field: 'geo_certificacao_codigo',
        selo: 'pendente_oficializacao',
      });
    }, { timeout: 5000 });
  });
});
