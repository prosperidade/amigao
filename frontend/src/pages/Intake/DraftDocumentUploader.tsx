import { useCallback, useEffect, useRef, useState } from 'react';
import { AxiosError } from 'axios';
import { api } from '@/lib/api';
import { labelFor, humanizeValue } from '@/lib/labels/fieldLabels';

// Tipos documentais sugeridos pelo Regente Cam1 Bloco 3
const DOCUMENT_TYPES = [
  { value: '', label: 'Tipo (opcional)' },
  { value: 'matricula', label: 'Matrícula ou escritura' },
  { value: 'ccir', label: 'CCIR' },
  { value: 'car', label: 'CAR' },
  { value: 'cpf_cnpj', label: 'CPF / CNPJ' },
  { value: 'comprovante_endereco', label: 'Comprovante de endereço' },
  { value: 'contrato_societario', label: 'Contrato societário' },
  { value: 'kml_sigef', label: 'KML / croqui / SIGEF' },
] as const;

// Rótulos pt-BR dos campos extraídos vêm de @/lib/labels/fieldLabels (fonte única).

// ── Robustez de upload (auditoria uploads Isis #1) ───────────────────────────
// Timeout do PUT direto ao storage (presigned). Sem isso, se o R2/MinIO travar
// a UI fica presa pra sempre (fetch não tem timeout default). Mantém 45s.
const PUT_TIMEOUT_MS = 45_000;
// Timeout das chamadas ao backend (presign + confirm). Subiu de 20s -> 30s
// para cobrir cold start do Render e travamento em head_bucket.
const BACKEND_TIMEOUT_MS = 30_000;
const POLL_INTERVAL_MS = 5_000;
// Estados de OCR terminais — não há mais o que aguardar. 'not_required' cobre
// arquivos geoespaciais (geometria), que ficam armazenados sem leitura de texto.
const TERMINAL_OCR_STATUS = new Set(['done', 'failed', 'not_required']);
// Pool de uploads simultâneos — substitui o for-await sequencial do original.
const UPLOAD_CONCURRENCY = 4;
// 3 tentativas no total; backoff de 1s, 2s e 4s entre elas.
const RETRY_BACKOFFS_MS = [1_000, 2_000, 4_000];
const MAX_ATTEMPTS = RETRY_BACKOFFS_MS.length;

interface DraftDoc {
  id: number;
  filename: string;
  document_type: string | null;
  document_category: string | null;
  ocr_status: string | null;
  file_size_bytes: number;
  created_at: string | null;
}

interface ExtractedDoc {
  document_id: number;
  filename: string | null;
  document_type: string | null;
  ocr_status: string | null;
  extracted_fields: Record<string, unknown>;
  fields_count: number;
  extracted_at: string | null;
}

interface ExtractionResults {
  draft_id: number;
  docs_total: number;
  docs_with_results: number;
  by_document: ExtractedDoc[];
  suggestions: Record<string, unknown>;
}

interface PresignResponse {
  upload_url: string;
  storage_key: string;
}

interface Props {
  draftId: number;
  /** Quando os docs mudam (útil pra badges no step de confirmação). */
  onChange?: (docs: DraftDoc[]) => void;
  /** CAM1-005 Parte B — callback opcional quando o consultor aplica uma sugestão. */
  onApplySuggestion?: (field: string, value: unknown) => void;
  /** fix/extrator-por-processo — avisa o pai que a leitura IA foi disparada,
   *  para o IntakeWizard liberar o avanço do Step 4. */
  onImportTriggered?: () => void;
}

type PendingStatus = 'waiting' | 'uploading' | 'error';

interface PendingItem {
  localId: string;
  file: File;
  documentType: string;
  status: PendingStatus;
  attempt: number;
  error?: string;
}

// Erro do PUT ao storage que vale a pena re-tentar (timeout, rede, 5xx).
class StorageRetryableError extends Error {}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

/**
 * Decide se um erro de uma etapa de upload deve ser re-tentado.
 * Retryável: timeout (ECONNABORTED), 5xx, 408, 429, erro de rede (sem response),
 *            e StorageRetryableError (PUT via fetch).
 * Não retryável: demais 4xx -> falha imediata.
 */
function isRetryable(error: unknown): boolean {
  if (error instanceof StorageRetryableError) return true;
  if (error instanceof AxiosError) {
    if (error.code === 'ECONNABORTED') return true;
    const status = error.response?.status;
    if (status === undefined) return true; // erro de rede / sem resposta
    if (status === 408 || status === 429) return true;
    return status >= 500;
  }
  return false;
}

function errorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === 'string' && detail.length > 0) return detail;
    if (error.code === 'ECONNABORTED') return 'Tempo de envio esgotado.';
  }
  if (error instanceof Error) return error.message;
  return 'Erro ao enviar arquivo.';
}

export default function DraftDocumentUploader({
  draftId,
  onChange,
  onApplySuggestion,
  onImportTriggered,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [docs, setDocs] = useState<DraftDoc[]>([]);
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [importing, setImporting] = useState(false);
  const [pendingType, setPendingType] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [extraction, setExtraction] = useState<ExtractionResults | null>(null);
  const [appliedFields, setAppliedFields] = useState<Set<string>>(new Set());
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  // Liga o polling após disparar a leitura IA: o /import marca os docs como
  // 'pending' (fila), não 'processing', então sem essa flag o polling nunca
  // começava e o card congelava em "Aguardando" mesmo com o job concluído.
  const [awaitingOcr, setAwaitingOcr] = useState(false);
  // Espelho síncrono de `pending` — o handler de retry precisa ler o item atual
  // sem depender do timing do updater de setState.
  const pendingRef = useRef<PendingItem[]>([]);
  pendingRef.current = pending;

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get<DraftDoc[]>(`/intake/drafts/${draftId}/documents`);
      setDocs(data);
      onChange?.(data);
    } catch {
      // silent
    }
  }, [draftId, onChange]);

  // CAM1-005 Parte B (Sprint L) — busca sugestões extraídas pelos agentes.
  const refreshExtraction = useCallback(async () => {
    try {
      const { data } = await api.get<ExtractionResults>(
        `/intake/drafts/${draftId}/extraction-results`,
      );
      setExtraction(data);
    } catch {
      // silent — endpoint pode não ter resultados ainda
    }
  }, [draftId]);

  useEffect(() => {
    if (draftId) refresh();
  }, [draftId, refresh]);

  // Polling leve a cada 5s enquanto houver doc ATIVO. "Ativo" = 'processing'
  // (worker lendo agora) OU, após a leitura IA ter sido disparada nesta sessão,
  // qualquer status não-terminal ('pending' na fila). Antes a condição era só
  // 'processing' — mas o /import marca os docs como 'pending', então o polling
  // nunca iniciava e o card ficava preso em "Aguardando" mesmo o job concluindo.
  useEffect(() => {
    if (!draftId) return;
    refreshExtraction();
    const active =
      docs.some((d) => d.ocr_status === 'processing') ||
      (awaitingOcr && docs.some((d) => !TERMINAL_OCR_STATUS.has(d.ocr_status ?? 'pending')));
    if (!active) {
      // Tudo terminal — desliga a flag para não reabrir polling à toa.
      if (awaitingOcr) setAwaitingOcr(false);
      return;
    }
    const timer = window.setInterval(() => {
      refresh();
      refreshExtraction();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [draftId, docs, awaitingOcr, refresh, refreshExtraction]);

  const setItem = useCallback((localId: string, patch: Partial<PendingItem>) => {
    setPending((prev) => prev.map((p) => (p.localId === localId ? { ...p, ...patch } : p)));
  }, []);

  /**
   * Executa uma das 3 etapas com retry + backoff.
   * `onAttempt` é chamado a cada tentativa (1-based) para feedback de UI.
   */
  const withRetry = useCallback(
    async <T,>(fn: () => Promise<T>, onAttempt: (attempt: number) => void): Promise<T> => {
      let lastError: unknown;
      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
        onAttempt(attempt);
        try {
          return await fn();
        } catch (err) {
          lastError = err;
          if (!isRetryable(err) || attempt === MAX_ATTEMPTS) {
            throw err;
          }
          await sleep(RETRY_BACKOFFS_MS[attempt - 1]);
        }
      }
      throw lastError;
    },
    [],
  );

  // PUT direto ao storage (fora do interceptor de auth do axios — presigned URL).
  // Timeout via AbortController; converte falhas transitórias em
  // StorageRetryableError pra serem re-tentadas pelo withRetry.
  const putToStorage = useCallback(async (uploadUrl: string, file: File) => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), PUT_TIMEOUT_MS);
    let res: Response;
    try {
      res = await fetch(uploadUrl, {
        method: 'PUT',
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
        body: file,
        signal: controller.signal,
      });
    } catch (putErr: unknown) {
      const isAbort = (putErr as { name?: string })?.name === 'AbortError';
      throw new StorageRetryableError(
        isAbort
          ? `Tempo esgotado enviando "${file.name}" pro storage (${PUT_TIMEOUT_MS / 1000}s).`
          : `Falha de rede ao enviar "${file.name}" pro storage.`,
      );
    } finally {
      window.clearTimeout(timer);
    }
    if (!res.ok) {
      // 5xx do storage é transitório (retry); 4xx é definitivo (CORS/assinatura).
      if (res.status >= 500) {
        throw new StorageRetryableError(
          `Storage indisponível ao enviar "${file.name}" (HTTP ${res.status}).`,
        );
      }
      throw new Error(`Upload de "${file.name}" rejeitado pelo storage (HTTP ${res.status}).`);
    }
  }, []);

  const uploadOne = useCallback(
    async (item: PendingItem) => {
      const onAttempt = (attempt: number) => {
        setItem(item.localId, { status: 'uploading', attempt, error: undefined });
      };
      // 1. Solicita presigned URL ao backend.
      const { data: presign } = await withRetry(
        () =>
          api.post<PresignResponse>(
            `/intake/drafts/${draftId}/upload-url`,
            {
              filename: item.file.name,
              content_type: item.file.type || 'application/octet-stream',
              document_type: item.documentType || null,
            },
            { timeout: BACKEND_TIMEOUT_MS },
          ),
        onAttempt,
      );

      // 2. Envia o arquivo direto pro storage (presigned PUT).
      await withRetry(() => putToStorage(presign.upload_url, item.file), onAttempt);

      // 3. Confirma no backend (cria o registro Document).
      await withRetry(
        () =>
          api.post(
            `/intake/drafts/${draftId}/documents`,
            {
              storage_key: presign.storage_key,
              filename: item.file.name,
              content_type: item.file.type || 'application/octet-stream',
              file_size_bytes: item.file.size,
              document_type: item.documentType || null,
            },
            { timeout: BACKEND_TIMEOUT_MS },
          ),
        onAttempt,
      );
    },
    [draftId, setItem, withRetry, putToStorage],
  );

  // Processa um item: sucesso -> remove do pending; falha -> marca 'error'.
  const processItem = useCallback(
    async (item: PendingItem): Promise<boolean> => {
      try {
        await uploadOne(item);
        setPending((prev) => prev.filter((p) => p.localId !== item.localId));
        return true;
      } catch (err) {
        setItem(item.localId, { status: 'error', error: errorMessage(err) });
        return false;
      }
    },
    [uploadOne, setItem],
  );

  // Pool de concorrência limitada (UPLOAD_CONCURRENCY simultâneos).
  const runPool = useCallback(
    async (items: PendingItem[]) => {
      let cursor = 0;
      const worker = async () => {
        while (cursor < items.length) {
          const current = items[cursor];
          cursor += 1;
          await processItem(current);
        }
      };
      const workers = Array.from(
        { length: Math.min(UPLOAD_CONCURRENCY, items.length) },
        () => worker(),
      );
      await Promise.all(workers);
    },
    [processItem],
  );

  const uploadFiles = useCallback(
    async (files: FileList | File[]) => {
      const fileArr = Array.from(files);
      if (fileArr.length === 0) return;
      setError(null);

      const items: PendingItem[] = fileArr.map((file, idx) => ({
        localId: `${Date.now()}-${idx}-${file.name}`,
        file,
        documentType: pendingType,
        status: 'waiting',
        attempt: 0,
      }));
      setPending((prev) => [...prev, ...items]);

      await runPool(items);
      await refresh();

      if (fileInputRef.current) fileInputRef.current.value = '';
    },
    [pendingType, runPool, refresh],
  );

  // Re-dispara um único item que falhou (mesma máquina de retry).
  const retryItem = useCallback(
    async (localId: string) => {
      const target = pendingRef.current.find((p) => p.localId === localId);
      if (!target) return;
      setPending((prev) =>
        prev.map((p) =>
          p.localId === localId ? { ...p, status: 'waiting', attempt: 0, error: undefined } : p,
        ),
      );
      const ok = await processItem({
        ...target,
        status: 'waiting',
        attempt: 0,
        error: undefined,
      });
      if (ok) await refresh();
    },
    [processItem, refresh],
  );

  const triggerImport = async () => {
    setImporting(true);
    setError(null);
    try {
      const { data } = await api.post<{ docs_queued: number; docs_skipped_geo?: number }>(
        `/intake/drafts/${draftId}/import`,
        {},
      );
      await refresh();
      // Liga o polling só se algo foi de fato enfileirado pro OCR. Arquivos
      // geoespaciais entram como docs_skipped_geo (armazenados, sem leitura).
      if (data.docs_queued > 0) setAwaitingOcr(true);
      onImportTriggered?.();
    } catch (err: unknown) {
      setError(errorMessage(err) || 'Erro ao disparar leitura IA');
    } finally {
      setImporting(false);
    }
  };

  // Soft delete (DELETE /documents/{id}). Disponível em QUALQUER ocr_status
  // (auditoria uploads Isis #1.D — guard canDelete removido).
  const deleteDoc = useCallback(
    async (docId: number) => {
      setDeletingId(docId);
      setError(null);
      try {
        await api.delete(`/documents/${docId}`);
        setConfirmDeleteId(null);
        await refresh();
      } catch (err: unknown) {
        setConfirmDeleteId(null);
        setError(errorMessage(err) || 'Erro ao excluir documento.');
      } finally {
        setDeletingId(null);
      }
    },
    [refresh],
  );

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Tipo do próximo upload
          </label>
          <select
            value={pendingType}
            onChange={(e) => setPendingType(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
          >
            {DOCUMENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          📎 Anexar arquivos
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) void uploadFiles(e.target.files);
          }}
        />
      </div>

      {/* Itens em envio / com falha — feedback POR item (não caixa agregada) */}
      {pending.length > 0 && (
        <div className="space-y-2">
          {pending.map((p) => (
            <div
              key={p.localId}
              className="flex items-center gap-3 rounded-lg border border-border bg-card p-2.5 text-sm"
            >
              <span className="text-lg">📄</span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-foreground">{p.file.name}</div>
              </div>
              {p.status === 'error' ? (
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-xs text-destructive">{p.error ?? 'Falhou'}</span>
                  <button
                    type="button"
                    onClick={() => void retryItem(p.localId)}
                    className="text-xs font-medium text-primary hover:opacity-80"
                  >
                    Tentar novamente
                  </button>
                </div>
              ) : (
                <span className="shrink-0 text-xs text-muted-foreground">
                  {p.status === 'uploading'
                    ? `Enviando (tentativa ${p.attempt})…`
                    : 'Aguardando…'}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {docs.length === 0 && pending.length === 0 ? (
        <div className="text-xs italic text-muted-foreground">
          Nenhum documento anexado ainda. Upload é opcional — o card nasce mesmo sem docs.
        </div>
      ) : (
        docs.length > 0 && (
          <div className="space-y-2">
            {docs.map((d) => (
              <div
                key={d.id}
                className="flex items-center gap-3 rounded-lg border border-border bg-card p-2.5 text-sm"
              >
                <span className="text-lg">📄</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-foreground">{d.filename}</div>
                  <div className="text-xs text-muted-foreground">
                    {d.document_type ?? 'sem tipo'}
                    {d.file_size_bytes > 0 && ` · ${Math.round(d.file_size_bytes / 1024)} KB`}
                  </div>
                  {/* Mensagem honesta para arquivos geoespaciais (geometria):
                      armazenados sem leitura de texto; processamento geo é o gap D1. */}
                  {d.ocr_status === 'not_required' && (
                    <div className="mt-0.5 text-[11px] text-cyan-700">
                      🗺️ Geometria armazenada — processamento em breve (sem leitura de texto).
                    </div>
                  )}
                </div>
                <StatusPill status={d.ocr_status} />
                {/* Botão remover SEMPRE visível, qualquer ocr_status */}
                {confirmDeleteId === d.id ? (
                  <span className="flex shrink-0 items-center gap-2">
                    <button
                      type="button"
                      onClick={() => void deleteDoc(d.id)}
                      disabled={deletingId === d.id}
                      className="text-xs font-medium text-destructive hover:opacity-80 disabled:opacity-40"
                    >
                      {deletingId === d.id ? 'Removendo…' : 'Confirmar'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDeleteId(null)}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      Cancelar
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmDeleteId(d.id)}
                    title="Excluir este documento"
                    className="shrink-0 rounded-md px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                  >
                    🗑 remover
                  </button>
                )}
              </div>
            ))}

            <button
              type="button"
              onClick={triggerImport}
              disabled={importing || docs.length === 0}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary/10 py-2.5 text-sm font-medium text-primary hover:bg-primary/20 disabled:opacity-40"
            >
              {importing ? (
                <>
                  <span className="animate-spin">⟳</span> Disparando leitura IA...
                </>
              ) : (
                '🤖 Ler documentos com IA'
              )}
            </button>
          </div>
        )
      )}

      {/* CAM1-005 Parte B (Sprint L) — Sugestões extraídas pelos agentes */}
      {extraction &&
        extraction.docs_with_results > 0 &&
        Object.keys(extraction.suggestions).length > 0 && (
          <div className="space-y-2 rounded-xl border border-primary/30 bg-primary/5 p-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
              <span>🤖</span>
              <span>Sugestões extraídas pela IA</span>
              <span className="text-[10px] font-normal text-muted-foreground">
                ({extraction.docs_with_results} de {extraction.docs_total} doc
                {extraction.docs_total > 1 ? 's' : ''})
              </span>
            </div>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {Object.entries(extraction.suggestions).map(([field, value]) => {
                const applied = appliedFields.has(field);
                return (
                  <div
                    key={field}
                    className={`flex items-center gap-2 rounded-lg border p-2 text-xs ${
                      applied
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                        : 'border-border bg-card text-foreground'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                        {labelFor(field)}
                      </div>
                      <div className="truncate font-medium">{humanizeValue(value)}</div>
                    </div>
                    {onApplySuggestion && !applied && (
                      <button
                        type="button"
                        onClick={() => {
                          onApplySuggestion(field, value);
                          setAppliedFields(new Set([...appliedFields, field]));
                        }}
                        className="shrink-0 rounded bg-primary/20 px-2 py-0.5 text-[10px] font-medium text-primary hover:bg-primary/30"
                      >
                        Aplicar
                      </button>
                    )}
                    {applied && <span className="text-[10px] text-emerald-700">✓ aplicado</span>}
                  </div>
                );
              })}
            </div>
          </div>
        )}
    </div>
  );
}

function StatusPill({ status }: { status: string | null }) {
  const map: Record<string, { label: string; cls: string }> = {
    pending: { label: 'Aguardando', cls: 'bg-muted text-muted-foreground' },
    uploaded: { label: 'Enviado', cls: 'bg-muted text-muted-foreground' },
    processing: { label: 'Em leitura', cls: 'bg-yellow-50 text-yellow-700' },
    done: { label: 'Lido', cls: 'bg-emerald-50 text-emerald-700' },
    failed: { label: 'Falhou', cls: 'bg-red-50 text-red-700' },
    not_required: { label: 'Armazenado', cls: 'bg-cyan-50 text-cyan-700' },
  };
  const item = map[status ?? 'pending'] ?? map.pending;
  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${item.cls}`}>
      {item.label}
    </span>
  );
}
