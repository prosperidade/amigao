// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: { post: vi.fn().mockResolvedValue({ data: {} }) } }));
import { api } from '@/lib/api';
import { ReviewCard } from './EvidencePanel';

function withQuery(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

const observationRow = {
  object: {
    id: 'obs:1', version: 1, kind: 'observacao', statement: null,
    attributes: { predicate: 'area_documental_ha', literal: 'Área: 10,3 ha', document_id: 546 },
    knowledge: { state: 'nao_determinado' }, premises: [{ id: 'document:546', version: 1 }],
  },
  revision: 0, stale: false, review: null,
};

// André, 21/09/2026: a correção pela tela não existia para observação (só conclusão) — o backend
// já aceitava (review_object aceita kind='observacao'), faltava só a UI.
describe('ReviewCard — observação', () => {
  it('shows the review actions and seeds the correction field from the literal, not the statement', () => {
    render(withQuery(<ReviewCard row={observationRow} latest processId={1} />));
    expect(screen.getByRole('button', { name: 'Criar correção' })).toBeInTheDocument();
    expect(screen.getByLabelText('Texto corrigido')).toHaveValue('Área: 10,3 ha');
  });

  it('sends a correction that only replaces attributes.literal, preserving the rest of the object', async () => {
    const user = userEvent.setup();
    render(withQuery(<ReviewCard row={observationRow} latest processId={7} />));
    await user.type(screen.getByLabelText('Justificativa da revisão'), 'Área conferida no documento');
    await user.clear(screen.getByLabelText('Texto corrigido'));
    await user.type(screen.getByLabelText('Texto corrigido'), 'Área: 12,3 ha');
    await user.click(screen.getByRole('button', { name: 'Criar correção' }));
    expect(api.post).toHaveBeenCalledWith('/evidence/cases/7/objects/obs%3A1/review', {
      expected_version: 1, expected_revision: 0, action: 'corrigir', justification: 'Área conferida no documento',
      correction: { ...observationRow.object, attributes: { ...observationRow.object.attributes, literal: 'Área: 12,3 ha' } },
    });
  });

  it('disables every action except correção when the observation is stale, same as for conclusão', async () => {
    const user = userEvent.setup();
    render(withQuery(<ReviewCard row={{ ...observationRow, stale: true }} latest processId={1} />));
    await user.type(screen.getByLabelText('Justificativa da revisão'), 'Justificativa presente');
    expect(screen.getByRole('button', { name: 'Aprovar' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Criar correção' })).not.toBeDisabled();
  });
});
