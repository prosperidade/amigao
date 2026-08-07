// @vitest-environment jsdom
/**
 * GATE do PR — o gesto inteiro, na UI: consolidar → a linha muda de estado.
 *
 * A regra da casa: gate que exige gesto humano só merge com E2E do gesto. O
 * gesto aqui é o clique em "Gravar na base", e o que se prova é exatamente o
 * que faltava em produção — que a tela ADMITE ter gravado. Antes deste PR uma
 * linha gravada e uma linha recusada mostravam a mesma palavra ("Aceito"), e
 * foi assim que uma consolidação de 16 campos foi lida pela consultora como
 * "gravou apenas NIRF, CCIR e INCRA".
 *
 * O fixture reproduz a assimetria real do caso 16: `cartorio` pousa,
 * `rat_protocolo` é aceito e recusado (não tem destino na base).
 */
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ConsolidacaoPanel from './ConsolidacaoPanel';

vi.mock('react-hot-toast', () => ({
  // O caminho de sucesso COM ressalva chama `toast(...)` direto (âmbar), não
  // `toast.error` — ressalva não é erro (validação 30/07). O mock precisa ser
  // chamável e ter os dois métodos, senão o teste quebra no caminho certo.
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

/** Uma linha de staging já ACEITA — decidida, ainda não gravada. */
function linhaAceita(over: Record<string, unknown> = {}) {
  return {
    id: 1,
    source_doc_type: 'matricula',
    field_name: 'cartorio',
    field_value: { value: "CRI de São João d'Aliança" },
    confidence: 'high',
    target_entity: 'matricula',
    target_field: 'cartorio',
    matricula_hint: '6.776',
    status: 'aceito',
    decided_value: { value: "CRI de São João d'Aliança" },
    sem_casa: false,
    sem_casa_motivo: null,
    source_doc_nome: 'Certidão Mat. 6.776.pdf',
    gravado: false,
    gravado_em: null,
    ...over,
  };
}

/** Aceite que NÃO tem onde pousar — o contraexemplo que mantém o selo honesto. */
const LINHA_SEM_CASA = linhaAceita({
  id: 2,
  source_doc_type: 'rat',
  field_name: 'rat_protocolo',
  field_value: { value: 'GO-2024-99887' },
  target_entity: 'imovel',
  target_field: 'rat_protocolo',
  matricula_hint: null,
  decided_value: { value: 'GO-2024-99887' },
  sem_casa: true,
  sem_casa_motivo:
    'não entra na ficha: o número de protocolo identifica o RAT, não o imóvel',
  source_doc_nome: 'RAT 2024.pdf',
});

describe('ConsolidacaoPanel — "Aceito" não é "Gravado" (validações 30/07 e 02/08)', () => {
  /** Estado do servidor, mutável — o clique muda o que o GET seguinte devolve. */
  let stagingFields: Array<Record<string, unknown>>;

  beforeEach(() => {
    vi.clearAllMocks();
    stagingFields = [linhaAceita(), LINHA_SEM_CASA];
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url.includes('/staging-fields')) return Promise.resolve({ data: stagingFields });
      if (url.includes('/matriculas-rotulos')) return Promise.resolve({ data: {} });
      return Promise.resolve({ data: [] });
    });
  });

  it('antes de gravar, o aceite diz que ainda falta o clique', async () => {
    render(withQuery(<ConsolidacaoPanel processId={1} />));

    expect(await screen.findAllByText('Aceito')).toHaveLength(2);
    expect(screen.getAllByText('aguardando "Gravar na base"')).toHaveLength(2);
    expect(screen.queryByText('Gravado na base')).not.toBeInTheDocument();
    expect(screen.getByText(/2 campo\(s\) serão gravados/)).toBeInTheDocument();
  });

  it('o GESTO: clicar em "Gravar na base" muda o estado da linha que pousou — e só dela', async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockImplementation(async () => {
      // O servidor gravou o cartório e recusou o protocolo do RAT. O carimbo
      // (`gravado`) é do servidor, não da tela: quem responde "pousou?" é a
      // consolidação, nunca um palpite do frontend.
      stagingFields = [
        linhaAceita({ gravado: true, gravado_em: '2026-08-06T12:00:00Z' }),
        LINHA_SEM_CASA,
      ];
      return {
        data: {
          campos_gravados: 1,
          matriculas_criadas: 0,
          matriculas_atualizadas: 1,
          cliente_atualizado: false,
          imovel_atualizado: false,
          area_total_matriculas: 349.9022,
          acoes_criadas: 0,
          ignorados: [
            'imovel.rat_protocolo: não entra na ficha: o número de protocolo identifica o RAT, não o imóvel',
          ],
          divergencias_devolvidas: [],
        },
      };
    });

    render(withQuery(<ConsolidacaoPanel processId={1} />));
    await user.click(await screen.findByRole('button', { name: /Gravar na base/ }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/processes/1/consolidar', {});
    });

    // A linha que pousou passa a dizer isso — é a correção do "aceitei e não
    // gravou". A que não pousou continua aguardando: um selo que carimbasse as
    // duas seria pior que selo nenhum.
    expect(await screen.findByText('Gravado na base')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText('aguardando "Gravar na base"')).toHaveLength(1);
    });
    expect(screen.getByText('na base')).toBeInTheDocument();
    expect(screen.getByText(/1 já na base/)).toBeInTheDocument();

    // E o aceite recusado continua dizendo o motivo, sem virar alarme.
    expect(screen.getByText(/1 campo\(s\) aceito\(s\) não foram gravados/)).toBeInTheDocument();
  });

  it('decidir de novo apaga o "Gravado" — carimbo não sobrevive à decisão que o invalidou', async () => {
    const user = userEvent.setup();
    stagingFields = [linhaAceita({ gravado: true, gravado_em: '2026-08-06T12:00:00Z' })];
    vi.mocked(api.post).mockImplementation(async () => {
      stagingFields = [linhaAceita({ status: 'pendente', decided_value: null })];
      return { data: { field_id: 1, status: 'pendente' } };
    });

    render(withQuery(<ConsolidacaoPanel processId={1} />));
    expect(await screen.findByText('Gravado na base')).toBeInTheDocument();

    await user.click(screen.getByTitle('Reabrir esta decisão (volta a pendente)'));

    await waitFor(() => {
      expect(screen.queryByText('Gravado na base')).not.toBeInTheDocument();
    });
    expect(screen.getByText('Pendente')).toBeInTheDocument();
  });
});
