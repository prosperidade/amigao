// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AxiosError, AxiosHeaders } from 'axios';

vi.mock('@/lib/api', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
  },
}));

import { api } from '@/lib/api';
import DraftDocumentUploader from './DraftDocumentUploader';

const mockedApi = api as unknown as {
  post: ReturnType<typeof vi.fn>;
  get: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

const DRAFT_ID = 7;

function okResponse(): Response {
  return { ok: true, status: 200 } as Response;
}

function makeAxios5xx(): AxiosError {
  return new AxiosError('boom', 'ERR_BAD_RESPONSE', undefined, undefined, {
    status: 503,
    statusText: 'Service Unavailable',
    data: {},
    headers: {},
    config: { headers: new AxiosHeaders() },
  });
}

function makeFiles(n: number): File[] {
  return Array.from(
    { length: n },
    (_, i) => new File(['content'], `doc-${i}.pdf`, { type: 'application/pdf' }),
  );
}

function selectFiles(files: File[]) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  Object.defineProperty(input, 'files', { value: files, configurable: true });
  fireEvent.change(input);
}

// presign resolve; confirm resolve; extraction-results vazio.
function defaultApiMocks() {
  mockedApi.get.mockResolvedValue({ data: [] });
  mockedApi.post.mockImplementation((url: string) => {
    if (url.includes('upload-url')) {
      return Promise.resolve({
        data: { upload_url: 'https://storage/put', storage_key: 'k' },
      });
    }
    return Promise.resolve({ data: {} }); // confirm / import
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  defaultApiMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('DraftDocumentUploader — pool de concorrência', () => {
  it('nunca ultrapassa 4 uploads simultâneos com 10 arquivos', async () => {
    let inFlight = 0;
    let maxInFlight = 0;
    const resolvers: Array<() => void> = [];

    // O PUT ao storage é via fetch — bloqueia até liberarmos manualmente.
    const fetchMock = vi.fn(() => {
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      return new Promise<Response>((resolve) => {
        resolvers.push(() => {
          inFlight -= 1;
          resolve(okResponse());
        });
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<DraftDocumentUploader draftId={DRAFT_ID} />);
    selectFiles(makeFiles(10));

    // O pool deve saturar exatamente os 4 slots.
    await waitFor(() => expect(resolvers.length).toBe(4));
    expect(maxInFlight).toBe(4);

    // Libera em ondas; nunca deve passar de 4 simultâneos.
    while (resolvers.length > 0 || inFlight > 0) {
      const batch = resolvers.splice(0, resolvers.length);
      batch.forEach((r) => r());
      await waitFor(() => expect(true).toBe(true));
    }

    expect(maxInFlight).toBe(4);
  });
});

describe('DraftDocumentUploader — retry com backoff', () => {
  it('re-tenta o confirm em 5xx e tem sucesso na 3ª tentativa', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(okResponse())),
    );

    let confirmCalls = 0;
    mockedApi.post.mockImplementation((url: string) => {
      if (url.includes('upload-url')) {
        return Promise.resolve({
          data: { upload_url: 'https://storage/put', storage_key: 'k' },
        });
      }
      if (url.endsWith('/documents')) {
        confirmCalls += 1;
        if (confirmCalls <= 2) return Promise.reject(makeAxios5xx());
        return Promise.resolve({ data: {} });
      }
      return Promise.resolve({ data: {} });
    });

    render(<DraftDocumentUploader draftId={DRAFT_ID} />);
    selectFiles(makeFiles(1));

    // 2 retries reais (backoff 1s + 2s) -> 3 chamadas de confirm no total.
    await waitFor(() => expect(confirmCalls).toBe(3), { timeout: 8000 });

    // Sucesso: o item de pending some.
    await waitFor(() => expect(screen.queryByText('doc-0.pdf')).not.toBeInTheDocument(), {
      timeout: 8000,
    });
  }, 15000);
});

describe('DraftDocumentUploader — remover', () => {
  it('botão remover aparece em qualquer estado (failed) e chama DELETE', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: [
        {
          id: 99,
          filename: 'falhou.pdf',
          document_type: 'car',
          document_category: null,
          ocr_status: 'failed',
          file_size_bytes: 10,
          created_at: '2026-05-31T00:00:00Z',
        },
      ],
    });
    mockedApi.delete.mockResolvedValue({ data: {} });

    render(<DraftDocumentUploader draftId={DRAFT_ID} />);

    await waitFor(() => expect(screen.getByText('falhou.pdf')).toBeInTheDocument());

    // botão "remover" existe mesmo em estado failed (guard canDelete removido).
    fireEvent.click(screen.getByText(/remover/));
    fireEvent.click(screen.getByText('Confirmar'));

    await waitFor(() => expect(mockedApi.delete).toHaveBeenCalledWith('/documents/99'));

    // refresh após DELETE -> lista vazia -> item some.
    mockedApi.get.mockResolvedValue({ data: [] });
    await waitFor(() => expect(screen.queryByText('falhou.pdf')).not.toBeInTheDocument());
  });
});

describe('DraftDocumentUploader — tentar novamente individual', () => {
  it('re-dispara apenas o item que falhou', async () => {
    // 1ª passada: PUT 400 (não-retryável) -> falha imediata.
    // retry manual: sucesso.
    let putCalls = 0;
    const fetchMock = vi.fn(() => {
      putCalls += 1;
      if (putCalls === 1) {
        return Promise.resolve({ ok: false, status: 400 } as Response);
      }
      return Promise.resolve(okResponse());
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<DraftDocumentUploader draftId={DRAFT_ID} />);
    selectFiles(makeFiles(1));

    await waitFor(() => expect(screen.getByText('Tentar novamente')).toBeInTheDocument());
    // 400 do storage é não-retryável: exatamente 1 PUT na 1ª passada.
    expect(putCalls).toBe(1);

    fireEvent.click(screen.getByText('Tentar novamente'));

    // O retry isolado re-dispara o PUT do item.
    await waitFor(() => expect(putCalls).toBeGreaterThanOrEqual(2));

    // sucesso -> item de pending some.
    await waitFor(() => expect(screen.queryByText('doc-0.pdf')).not.toBeInTheDocument());
  });
});

describe('DraftDocumentUploader — render base', () => {
  it('renderiza documento existente com badge', async () => {
    mockedApi.get.mockResolvedValue({
      data: [
        {
          id: 1,
          filename: 'a.pdf',
          document_type: 'car',
          document_category: null,
          ocr_status: 'done',
          file_size_bytes: 10,
          created_at: '2026-05-31T00:00:00Z',
        },
      ],
    });
    render(<DraftDocumentUploader draftId={DRAFT_ID} />);
    const row = await screen.findByText('a.pdf');
    // Badge "Lido" e o nome do arquivo coexistem na mesma linha do documento.
    expect(screen.getByText('Lido')).toBeInTheDocument();
    expect(row).toBeInTheDocument();
  });
});
