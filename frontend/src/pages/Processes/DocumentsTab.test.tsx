// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import type { Document } from './ProcessDetailTypes';

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn(), patch: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));
vi.mock('react-hot-toast', () => ({
  default: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));
// Upload e checklist não são o alvo deste teste — mockados fora para não
// arrastar dropzone/checklist para o setup.
vi.mock('@/components/DocumentUploadZone', () => ({ default: () => null }));
vi.mock('./ProcessChecklist', () => ({ default: () => null }));

import { api } from '@/lib/api';
import DocumentsTab from './DocumentsTab';

function withQuery(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

// Recorte real do doc 551 (dívida #223) — CNH-e cujo OCR leu só o boilerplate
// de assinatura digital, sem nome/CPF.
const docIlegivel: Document = {
  id: 551,
  filename: 'CNH-e.pdf.pdf',
  original_file_name: 'CNH-e.pdf.pdf',
  file_size_bytes: 284319,
  document_type: 'doc_pessoal',
  document_category: 'societarios',
  extraction_status:
    'recebido, não processado (doc_pessoal) — revisar: OCR não extraiu texto legível deste documento (provável PDF de imagem) — reprocessar o OCR; sem texto não há o que extrair',
  ocr_status: 'done',
  ocr_error: null,
  tem_texto: true,
  is_internal: false,
  created_at: '2026-09-08T00:54:57.693333+00:00',
};

const docNormal: Document = {
  id: 552,
  filename: 'certidao.pdf',
  original_file_name: 'certidao.pdf',
  file_size_bytes: 12345,
  document_type: 'certidao',
  document_category: 'registral',
  extraction_status: null,
  ocr_status: 'done',
  ocr_error: null,
  tem_texto: true,
  is_internal: false,
  created_at: '2026-09-08T00:54:57.693333+00:00',
};

function mockApiGet(documents: Document[]) {
  (api.get as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
    if (url.startsWith('/documents/?process_id=')) return Promise.resolve({ data: documents });
    if (url === '/ai/jobs') return Promise.resolve({ data: [] });
    return Promise.resolve({ data: null });
  });
}

describe('DocumentsTab — botão "Reprocessar OCR" para PDF ilegível (dívida #223)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('aparece só no documento com extraction_status de OCR ilegível', async () => {
    mockApiGet([docIlegivel, docNormal]);
    render(withQuery(<DocumentsTab processId={23} />));

    await screen.findByText('CNH-e.pdf.pdf');
    expect(screen.getByText('certidao.pdf')).toBeInTheDocument();

    expect(screen.getAllByRole('button', { name: /reprocessar ocr/i })).toHaveLength(1);
  });

  it('não aparece quando extraction_status é null', async () => {
    mockApiGet([docNormal]);
    render(withQuery(<DocumentsTab processId={23} />));

    await screen.findByText('certidao.pdf');
    expect(screen.queryByRole('button', { name: /reprocessar ocr/i })).not.toBeInTheDocument();
  });

  it('clicar chama POST /documents/{id}/reprocess-ocr e avisa por toast', async () => {
    const user = userEvent.setup();
    mockApiGet([docIlegivel]);
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { status: 'reprocessing' } });
    render(withQuery(<DocumentsTab processId={23} />));

    await user.click(await screen.findByRole('button', { name: /reprocessar ocr/i }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/documents/551/reprocess-ocr'));
  });
});
