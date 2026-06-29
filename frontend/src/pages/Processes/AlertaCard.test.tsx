// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import type { AxiosError } from 'axios';

import type { RegulatoryIssue, StatusAchado } from '@/lib/regulatory/types';

vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

import { api } from '@/lib/api';
import AlertaCard from './AlertaCard';

function withQuery(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

function makeIssue(overrides: Partial<RegulatoryIssue> = {}): RegulatoryIssue {
  return {
    id: 1,
    property_id: 10,
    document_id: null,
    codigo_alerta: 'AREA_MATRICULA_X_CAR',
    familia: 'area',
    muda_rota_regulatoria: null,
    muda_escopo_preco_prazo: null,
    documentos_cruzados: null,
    severity: 'critico',
    status_achado: 'suspeita',
    status_saneamento: 'pendente',
    type: null,
    payload: null,
    detected_by: null,
    detected_at: '2026-05-26T12:00:00Z',
    resolved_at: null,
    ...overrides,
  };
}

// Hook `useDecision` chama `api.get(...)` quando a decisão é exigida;
// 404 é o caminho esperado pra "sem decisão registrada".
function mock404Decision() {
  vi.mocked(api.get).mockRejectedValue({
    response: { status: 404 },
  } as unknown as AxiosError);
}

describe('AlertaCard — Regra B preventiva', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mock404Decision();
  });

  it('desabilita a decisão enquanto status_achado é suspeita', () => {
    render(withQuery(<AlertaCard issue={makeIssue()} processId={42} />));

    // Hint do desabilitar visível
    expect(
      screen.getByText(/Confirme ou descarte o achado para poder decidir/i),
    ).toBeInTheDocument();

    // Botão "Registrar decisão" disabled — fieldset com disabled propaga.
    const submit = screen.getByRole('button', { name: /Registrar decisão/i });
    expect(submit).toBeDisabled();

    // Radios da decisão também devem estar disabled.
    const radioCorrigir = screen.getByRole('radio', { name: /Corrigir antes/i });
    expect(radioCorrigir).toBeDisabled();
  });

  it.each(['confirmada', 'descartada', 'resolvida', 'ignorada'] as StatusAchado[])(
    'habilita a decisão quando status_achado é %s',
    (status) => {
      render(
        withQuery(
          <AlertaCard issue={makeIssue({ status_achado: status })} processId={42} />,
        ),
      );

      // Hint do desabilitar não aparece
      expect(
        screen.queryByText(/Confirme ou descarte o achado/i),
      ).not.toBeInTheDocument();

      // Radio "Corrigir antes" habilitado
      const radioCorrigir = screen.getByRole('radio', { name: /Corrigir antes/i });
      expect(radioCorrigir).not.toBeDisabled();
    },
  );
});

describe('AlertaCard — justificativa obrigatória (#19)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mock404Decision();
  });

  it('desabilita o submit enquanto justificativa vazia em ignorar_justificado', async () => {
    const user = userEvent.setup();
    render(
      withQuery(
        <AlertaCard
          issue={makeIssue({ status_achado: 'confirmada' })}
          processId={42}
        />,
      ),
    );

    // Selecionar "Ignorar (justificado)" — exige justificativa
    await user.click(screen.getByRole('radio', { name: /Ignorar.*justificado/i }));

    const submit = screen.getByRole('button', { name: /Registrar decisão/i });
    expect(submit).toBeDisabled();

    // Preencher textarea → submit libera. `fireEvent.change` é um evento
    // só (vs `userEvent.type` que dispara um keystroke por caractere e fica
    // lento em CI compartilhado).
    const textarea = screen.getByPlaceholderText(/Explique o motivo/i);
    fireEvent.change(textarea, { target: { value: 'Falso positivo: nome histórico.' } });
    expect(submit).not.toBeDisabled();

    // Só espaços → volta a bloquear (str_strip_whitespace no Pydantic).
    fireEvent.change(textarea, { target: { value: '   ' } });
    expect(submit).toBeDisabled();
  });

  it('NÃO exige justificativa pra corrigir_antes', async () => {
    const user = userEvent.setup();
    render(
      withQuery(
        <AlertaCard
          issue={makeIssue({ status_achado: 'confirmada' })}
          processId={42}
        />,
      ),
    );

    await user.click(screen.getByRole('radio', { name: /Corrigir antes/i }));

    const submit = screen.getByRole('button', { name: /Registrar decisão/i });
    expect(submit).not.toBeDisabled();
  });
});

describe('AlertaCard — botão "→ Ações" (Sprint 0)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mock404Decision();
  });

  it('cria uma Ação no processo a partir do alerta', async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({ data: { id: 99 } });
    render(
      withQuery(
        <AlertaCard
          issue={makeIssue({ codigo_alerta: 'AREA_MATRICULA_X_CAR', familia: 'area', severity: 'critico' })}
          processId={42}
        />,
      ),
    );

    await user.click(screen.getByRole('button', { name: /Ações/i }));

    expect(api.post).toHaveBeenCalledTimes(1);
    const [url, payload] = vi.mocked(api.post).mock.calls[0];
    expect(url).toBe('/processes/42/acoes');
    expect((payload as { titulo: string }).titulo).toContain('AREA_MATRICULA_X_CAR');
  });
});
