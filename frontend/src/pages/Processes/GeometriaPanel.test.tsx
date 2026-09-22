// @vitest-environment jsdom
/**
 * GeometriaPanel — auto-oculta sem arquivo geoespacial; com arquivo, mostra
 * leitura, medição calculada, medições declaradas e o confronto com
 * denominador e tolerância declarados (ADR-072).
 */
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import GeometriaPanel from './GeometriaPanel';

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

const vazio = {
  process_id: 1, arquivos: [], medicoes: [], projecao: null,
  confronto: { estado: 'nao_verificado', execucao: null, executado_em: null, execucoes: 0, linhas: [] },
  parametros: { tolerancia_pct: 1.0, tolerancia_origem: 'provisoria_regua_onda_c_pendente_q_isis_04',
                denominador: 'referencia_documental', metodo_area: 'x', crs_calculo: 'EPSG:4674' },
  sobreposicao: { estado: 'nao_verificado', motivo: 'Nenhuma camada de sobreposição carregada.' },
};

/** Reproduz o caso de Jobson: 2,7250 ha calculados × 2,6893 ha documental. */
const jobson = {
  ...vazio,
  arquivos: [{
    documento_id: 130, nome: 'MEDIDA_POLIGONO.kmz', formato: 'kmz', estado: 'lido', leituras: 1,
    leitura: { id: 1, numero: 1, sha256: 'a'.repeat(64), membro: 'doc.kml', crs_origem: 'EPSG:4326',
              metodo_versao: '072.1', falha_codigo: null, falha_detalhe: null, lido_em: '2026-09-22T00:00:00Z' },
    feicoes: [{ id: 1, ordem: 1, identificador: 'Document/Placemark[1]', nome: 'Perimetro', tipo: 'poligono',
               valida: true, motivo_invalidade: null, aneis_internos: 0, medicao_id: 1, area_ha: '2.72502007',
               area_estado: 'determinado', area_motivo: null }],
  }],
  medicoes: [
    { id: 1, origem_tipo: 'feicao_calculada', estado: 'determinado', valor_ha: '2.72502007', motivo: null,
      metodo: 'postgis_st_area_geography_spheroid', fonte: 'MEDIDA_POLIGONO.kmz', predicado: null, literal: null },
    { id: 2, origem_tipo: 'registro', estado: 'determinado', valor_ha: '2.6893', motivo: null,
      metodo: 'literal_ancorado_parse_area_ha', fonte: 'matricula.pdf', predicado: 'area_total',
      literal: 'Área total: 2,6893.' },
  ],
  projecao: { feicao_id: 1, regra: 'feicao_poligonal_unica', autor_id: null,
             motivo: 'Única feição poligonal válida', criada_em: '2026-09-22T00:00:00Z', property_geom_gravada: true },
  confronto: {
    estado: 'avaliado', execucao: 'exec-1', executado_em: '2026-09-22T00:00:00Z', execucoes: 1,
    linhas: [{ id: 1, calculada_ha: '2.72502007', referencia_ha: '2.6893', referencia_fonte: 'matricula.pdf',
              referencia_origem: 'registro', delta_ha: '0.03572007', denominador_regra: 'referencia_documental',
              denominador_ha: '2.6893', percentual: '1.3282293', percentual_sobre_maior: '1.3106',
              tolerancia_pct: 1.0, tolerancia_origem: 'provisoria_regua_onda_c_pendente_q_isis_04',
              resultado: 'divergente', grau: 'atencao' }],
  },
};

describe('GeometriaPanel', () => {
  it('sem arquivo geoespacial no caso, não renderiza nada', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: vazio });
    const { container } = render(withQuery(<GeometriaPanel processId={1} />));
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('mostra a área calculada, a declarada e o confronto com denominador e tolerância', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: jobson });
    render(withQuery(<GeometriaPanel processId={1} />));

    await waitFor(() => expect(screen.getByText('MEDIDA_POLIGONO.kmz')).toBeInTheDocument());
    // Área calculada da feição (PostGIS geodésica) — aparece no card da feição
    // e de novo na linha do confronto.
    expect(screen.getAllByText(/2,725/).length).toBeGreaterThanOrEqual(2);
    // Área declarada, com a fonte e o literal ancorado (aparece na lista de
    // declaradas e de novo na linha do confronto).
    expect(screen.getAllByText(/matricula\.pdf/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Área total: 2,6893\./)).toBeInTheDocument();
    // Confronto: denominador documental, tolerância declarada, resultado.
    expect(screen.getByText(/1,33%/)).toBeInTheDocument();
    expect(screen.getByText(/tolerância 1%/)).toBeInTheDocument();
    expect(screen.getByText(/divergente/)).toBeInTheDocument();
    // Sobreposição nunca vira "sem sobreposição" quando não há camada.
    expect(screen.getByText(/Nenhuma camada de sobreposição carregada\./)).toBeInTheDocument();
  });

  it('geometria inválida mostra o motivo, não a área', async () => {
    const invalida = {
      ...vazio,
      arquivos: [{
        documento_id: 5, nome: 'bowtie.kml', formato: 'kml', estado: 'lido', leituras: 1,
        leitura: { id: 2, numero: 1, sha256: 'b'.repeat(64), membro: null, crs_origem: 'EPSG:4326',
                  metodo_versao: '072.1', falha_codigo: null, falha_detalhe: null, lido_em: '2026-09-22T00:00:00Z' },
        feicoes: [{ id: 2, ordem: 1, identificador: 'Placemark[1]', nome: null, tipo: 'poligono', valida: false,
                   motivo_invalidade: 'Self-intersection', aneis_internos: 0, medicao_id: 2, area_ha: null,
                   area_estado: 'nao_determinado', area_motivo: 'geometria inválida: Self-intersection' }],
      }],
    };
    vi.mocked(api.get).mockResolvedValue({ data: invalida });
    render(withQuery(<GeometriaPanel processId={1} />));
    await waitFor(() => expect(screen.getByText(/Não determinado/)).toBeInTheDocument());
    expect(screen.getByText(/Self-intersection/)).toBeInTheDocument();
    // Feição inválida não oferece o botão de projetar como geometria do imóvel.
    expect(screen.queryByText(/usar como geometria do imóvel/)).not.toBeInTheDocument();
  });

  it('arquivo com falha de leitura mostra o código, não "em breve"', async () => {
    const falhou = {
      ...vazio,
      arquivos: [{
        documento_id: 7, nome: 'imovel.shp', formato: 'shp', estado: 'falha', leituras: 1,
        leitura: { id: 3, numero: 1, sha256: null, membro: null, crs_origem: null, metodo_versao: '072.1',
                  falha_codigo: 'formato_nao_suportado', falha_detalhe: "formato 'shp' ainda não é lido (só KMZ e KML)",
                  lido_em: '2026-09-22T00:00:00Z' },
        feicoes: [],
      }],
    };
    vi.mocked(api.get).mockResolvedValue({ data: falhou });
    render(withQuery(<GeometriaPanel processId={1} />));
    await waitFor(() => expect(screen.getByText(/formato_nao_suportado/)).toBeInTheDocument());
    expect(screen.queryByText(/em breve/)).not.toBeInTheDocument();
  });
});
