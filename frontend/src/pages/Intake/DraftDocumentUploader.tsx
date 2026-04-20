import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';

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

// CAM1-005 Parte B (Sprint L) — labels pt-BR dos campos comuns extraídos pelo agente.
const FIELD_LABELS: Record<string, string> = {
  cpf_cnpj: 'CPF / CNPJ',
  nome: 'Nome',
  razao_social: 'Razão social',
  matricula: 'Matrícula',
  car_code: 'Código CAR',
  car: 'CAR',
  ccir: 'CCIR',
  nirf: 'NIRF',
  area_ha: 'Área (ha)',
  area: 'Área',
  municipality: 'Município',
  municipio: 'Município',
  state: 'UF',
  uf: 'UF',
  property_name: 'Nome do imóvel',
  registry_number: 'Matrícula',
  endereco: 'Endereço',
};

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

interface Props {
  draftId: number;
  /** Quando os docs mudam (útil pra badges no step de confirmação). */
  onChange?: (docs: DraftDoc[]) => void;
  /** CAM1-005 Parte B — callback opcional quando o consultor aplica uma sugestão. */
  onApplySuggestion?: (field: string, value: unknown) => void;
}

export default function DraftDocumentUploader({ draftId, onChange, onApplySuggestion }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [docs, setDocs] = useState<DraftDoc[]>([]);
  const [uploading, setUploading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [pendingType, setPendingType] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [extraction, setExtraction] = useState<ExtractionResults | null>(null);
  const [appliedFields, setAppliedFields] = useState<Set<string>>(new Set());

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

  // Polling leve enquanto houver doc em 'processing' — refetch a cada 5s.
  useEffect(() => {
    if (!draftId) return;
    refreshExtraction();
    const hasProcessing = docs.some(d => d.ocr_status === 'processing');
    if (!hasProcessing) return;
    const timer = window.setInterval(() => {
      refresh();
      refreshExtraction();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [draftId, docs, refresh, refreshExtraction]);

  const uploadFiles = async (files: FileList) => {
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        // 1) Pedir presigned URL
        const { data: presigned } = await api.post(`/intake/drafts/${draftId}/upload-url`, {
          filename: file.name,
          content_type: file.type || 'application/octet-stream',
          document_type: pendingType || null,
        });
        // 2) PUT direto ao MinIO (fora do axios, sem auth)
        const putRes = await fetch(presigned.upload_url, {
          method: 'PUT',
          headers: { 'Content-Type': file.type || 'application/octet-stream' },
          body: file,
        });
        if (!putRes.ok) throw new Error(`Upload falhou (HTTP ${putRes.status})`);
        // 3) Confirmar no backend
        await api.post(`/intake/drafts/${draftId}/documents`, {
          storage_key: presigned.storage_key,
          filename: file.name,
          content_type: file.type || 'application/octet-stream',
          file_size_bytes: file.size,
          document_type: pendingType || null,
        });
      }
      await refresh();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (err as { message?: string })?.message
        ?? 'Erro no upload';
      setError(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const triggerImport = async () => {
    setImporting(true);
    setError(null);
    try {
      await api.post(`/intake/drafts/${draftId}/import`, {});
      await refresh();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Erro ao disparar leitura IA';
      setError(msg);
    } finally {
      setImporting(false);
    }
  };

  const badgeFor = (s: string | null) => {
    if (s === 'done') return { label: 'Lido', cls: 'bg-emerald-500/20 text-emerald-300' };
    if (s === 'processing') return { label: 'Em leitura', cls: 'bg-sky-500/20 text-sky-300' };
    if (s === 'failed') return { label: 'Falhou', cls: 'bg-red-500/20 text-red-300' };
    return { label: 'Enviado', cls: 'bg-slate-500/20 text-slate-300' };
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 text-sm">
          {error}
        </div>
      )}

      <div className="flex gap-2 items-end">
        <div className="flex-1">
          <label className="block text-xs font-medium text-slate-400 mb-1">Tipo do próximo upload</label>
          <select
            value={pendingType}
            onChange={e => setPendingType(e.target.value)}
            className="w-full rounded-lg bg-slate-800 border border-white/10 text-white px-3 py-2 text-sm focus:outline-none focus:border-emerald-400"
          >
            {DOCUMENT_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white text-sm font-medium flex items-center gap-2"
        >
          {uploading ? <><span className="animate-spin">⟳</span> Enviando...</> : '📎 Anexar arquivos'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={e => e.target.files && uploadFiles(e.target.files)}
        />
      </div>

      {docs.length === 0 ? (
        <div className="text-xs text-slate-500 italic">Nenhum documento anexado ainda. Upload é opcional — o card nasce mesmo sem docs.</div>
      ) : (
        <div className="space-y-2">
          {docs.map(d => {
            const b = badgeFor(d.ocr_status);
            return (
              <div key={d.id} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/5 border border-white/5 text-sm">
                <span className="text-lg">📄</span>
                <div className="flex-1 min-w-0">
                  <div className="truncate text-white">{d.filename}</div>
                  <div className="text-xs text-slate-500">
                    {d.document_type ?? 'sem tipo'}
                    {d.file_size_bytes > 0 && ` · ${Math.round(d.file_size_bytes / 1024)} KB`}
                  </div>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${b.cls}`}>{b.label}</span>
              </div>
            );
          })}

          <button
            onClick={triggerImport}
            disabled={importing || docs.length === 0}
            className="w-full mt-2 py-2.5 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 border border-sky-500/30 text-sky-200 text-sm font-medium disabled:opacity-40 flex items-center justify-center gap-2"
          >
            {importing ? <><span className="animate-spin">⟳</span> Disparando leitura IA...</> : '🤖 Ler documentos com IA'}
          </button>
        </div>
      )}

      {/* CAM1-005 Parte B (Sprint L) — Sugestões extraídas pelos agentes */}
      {extraction && extraction.docs_with_results > 0 && Object.keys(extraction.suggestions).length > 0 && (
        <div className="rounded-xl bg-violet-500/10 border border-violet-500/30 p-3 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-violet-200">
            <span>🤖</span>
            <span>Sugestões extraídas pela IA</span>
            <span className="text-[10px] font-normal text-violet-300/70">
              ({extraction.docs_with_results} de {extraction.docs_total} doc{extraction.docs_total > 1 ? 's' : ''})
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
            {Object.entries(extraction.suggestions).map(([field, value]) => {
              const applied = appliedFields.has(field);
              return (
                <div
                  key={field}
                  className={`flex items-center gap-2 p-2 rounded-lg text-xs border ${
                    applied
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                      : 'bg-white/5 border-white/10 text-slate-200'
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-[10px] uppercase tracking-wide text-slate-400">
                      {FIELD_LABELS[field] ?? field}
                    </div>
                    <div className="truncate font-medium">{String(value)}</div>
                  </div>
                  {onApplySuggestion && !applied && (
                    <button
                      onClick={() => {
                        onApplySuggestion(field, value);
                        setAppliedFields(new Set([...appliedFields, field]));
                      }}
                      className="shrink-0 text-[10px] px-2 py-0.5 rounded bg-violet-500/30 hover:bg-violet-500/50 text-violet-100 font-medium"
                    >
                      Aplicar
                    </button>
                  )}
                  {applied && <span className="text-[10px] text-emerald-300">✓ aplicado</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
