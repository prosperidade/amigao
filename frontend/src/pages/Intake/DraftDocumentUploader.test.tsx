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

describe('DraftDocumentUploader — polling pós-import (fix/intake-geo-routing)', () => {
  it('inicia polling após import mesmo com docs em "pending" e reflete "done"', async () => {
    // Timers REAIS (como os testes de retry): o /import marca os docs como
    // 'pending' (não 'processing'). Antes do fix o polling só ligava em
    // 'processing', então nunca refazia o fetch e o card travava em "Aguardando".
    let docStatus = 'pending';
    let docGets = 0;
    mockedApi.get.mockImplementation((url: string) => {
      if (url.endsWith('/documents')) {
        docGets += 1;
        return Promise.resolve({
          data: [
            {
              id: 5,
              filename: 'matricula.pdf',
              document_type: 'car',
              document_category: null,
              ocr_status: docStatus,
              file_size_bytes: 10,
              created_at: '2026-06-05T00:00:00Z',
            },
          ],
        });
      }
      // extraction-results — irrelevante para este teste.
      return Promise.resolve({
        data: { draft_id: DRAFT_ID, docs_total: 1, docs_with_results: 0, by_document: [], suggestions: {} },
      });
    });
    mockedApi.post.mockImplementation((url: string) => {
      if (url.endsWith('/import')) {
        return Promise.resolve({
          data: { draft_id: DRAFT_ID, docs_queued: 1, task_ids: ['t'], docs_skipped_geo: 0 },
        });
      }
      return Promise.resolve({ data: {} });
    });

    render(<DraftDocumentUploader draftId={DRAFT_ID} />);
    await screen.findByText('Aguardando'); // carga inicial: doc pending

    // Dispara a leitura IA — backend deixa o doc 'pending' (na fila do worker).
    fireEvent.click(screen.getByText(/Ler documentos com IA/));
    // O refresh imediato do import roda, mas o doc segue 'pending'.
    await waitFor(() => expect(docGets).toBeGreaterThanOrEqual(2));
    expect(screen.getByText('Aguardando')).toBeInTheDocument();

    // O worker conclui no backend. Só o POLLING pode entregar isso ao card —
    // não há mais nenhum evento de UI. Um tick do intervalo (5s) deve refletir.
    const getsBeforeTick = docGets;
    docStatus = 'done';
    await waitFor(() => expect(screen.getByText('Lido')).toBeInTheDocument(), { timeout: 8000 });
    // Prova que houve refetch por polling (não só o refresh do import).
    expect(docGets).toBeGreaterThan(getsBeforeTick);
  }, 15000);
});

describe('DraftDocumentUploader — arquivo geoespacial (fix/intake-geo-routing)', () => {
  it('mostra "Armazenado" + mensagem honesta para doc not_required', async () => {
    mockedApi.get.mockResolvedValue({
      data: [
        {
          id: 8,
          filename: 'imovel.kml',
          document_type: 'geoespacial',
          document_category: 'espaciais',
          ocr_status: 'not_required',
          file_size_bytes: 12,
          created_at: '2026-06-05T00:00:00Z',
        },
      ],
    });
    render(<DraftDocumentUploader draftId={DRAFT_ID} />);
    await waitFor(() => expect(screen.getByText('imovel.kml')).toBeInTheDocument());
    expect(screen.getByText('Armazenado')).toBeInTheDocument();
    expect(screen.getByText(/Geometria armazenada/)).toBeInTheDocument();
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
