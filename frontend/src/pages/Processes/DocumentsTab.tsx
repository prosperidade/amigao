import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { FileText, Download, Sparkles, Trash2, Info } from 'lucide-react';
import { Document } from './ProcessDetailTypes';
import type { AIJob } from '@/types/agent';
import ProcessChecklist from './ProcessChecklist';
import DocumentUploadZone from '@/components/DocumentUploadZone';
import { labelFor, isMetaField, humanizeValue } from '@/lib/labels/fieldLabels';
import {
  DOC_TYPE_NAO_CLASSIFICADO_AJUDA,
  docTypeLabel,
  isDocTypeNaoClassificado,
} from '@/lib/labels/docLabels';

/**
 * O documento é um áudio? (dívida #103)
 *
 * Reconhece pelas duas portas que existem hoje: o tipo declarado no upload do
 * caso (`audio_entrevista`) e a categoria vinda do intake (`audio`). Nome de
 * arquivo NÃO entra na conta — "reuniao.pdf" não é áudio e "gravacao" sem
 * extensão não prova nada.
 */
function ehAudio(doc: Document): boolean {
  return doc.document_type === 'audio_entrevista' || doc.document_category === 'audio';
}

interface DocumentsTabProps {
  processId: number;
}

export default function DocumentsTab({ processId }: DocumentsTabProps) {
  const queryClient = useQueryClient();
  const { data: documents, refetch: refetchDocuments } = useQuery({
    queryKey: ['documents', processId],
    queryFn: async () => {
      const res = await api.get(`/documents/?process_id=${processId}`);
      return res.data as Document[];
    },
    enabled: !!processId,
  });

  const deleteMutation = useMutation({
    mutationFn: async (docId: number) => {
      await api.delete(`/documents/${docId}`);
    },
    onSuccess: () => {
      toast.success('Documento excluido.');
      queryClient.invalidateQueries({ queryKey: ['documents', processId] });
      queryClient.invalidateQueries({ queryKey: ['checklist', processId] });
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Erro ao excluir documento.';
      toast.error(msg);
    },
  });

  const handleDelete = (docId: number, filename: string) => {
    const ok = window.confirm(
      `Excluir "${filename}"? O documento sera marcado como removido mas o arquivo original fica preservado no storage.`,
    );
    if (ok) deleteMutation.mutate(docId);
  };

  // Buscar jobs do extrator para mostrar badge de campos extraidos
  const { data: aiJobs = [] } = useQuery<AIJob[]>({
    queryKey: ['ai-jobs', processId],
    queryFn: () =>
      api.get('/ai/jobs', {
        params: { entity_type: 'process', entity_id: processId },
      }).then(r => r.data),
  });

  // Mapa docId -> campos extraídos (chave/valor). Excluimos document_id e
  // chaves de controle do extrator (campos sem valor de negócio para o consultor).
  const extractedFieldsByDoc = new Map<number, Array<[string, unknown]>>();
  const EXCLUDED_KEYS = new Set(['document_id', 'doc_type', 'tenant_id', 'process_id']);
  for (const j of aiJobs) {
    if (j.agent_name !== 'extrator' || j.status !== 'completed' || !j.result) continue;
    const docId = j.result.document_id;
    if (typeof docId !== 'number') continue;
    const fields = Object.entries(j.result).filter(
      ([k, v]) => !EXCLUDED_KEYS.has(k) && !isMetaField(k) && v !== null && v !== undefined && v !== '',
    );
    if (fields.length > 0) extractedFieldsByDoc.set(docId, fields);
  }
  const extractedDocIds = new Set(extractedFieldsByDoc.keys());

  const handleDownload = async (docId: number, filename: string) => {
    try {
      const res = await api.get(`/documents/${docId}/download-url`);
      const link = document.createElement('a');
      link.href = res.data.download_url;
      link.target = '_blank';
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch {
      toast.error('Erro ao gerar link de download.');
    }
  };

  return (
    <div className="space-y-5">
      <ProcessChecklist processId={processId} />

      <div className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-300 mb-3">Enviar Documento</h3>
        <DocumentUploadZone
          processId={processId}
          onUploadSuccess={() => refetchDocuments()}
        />
      </div>

      {(documents?.length ?? 0) > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider px-1">
            Documentos Enviados
          </p>
          {documents?.map(doc => {
            const fields = extractedFieldsByDoc.get(doc.id);
            return (
              <div key={doc.id} className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 hover:border-gray-200 dark:hover:border-white/10 transition-colors">
                <div className="flex items-center gap-4 p-4">
                  <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-500/20 flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 dark:text-white truncate">{doc.filename || doc.original_file_name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <p className="text-xs text-gray-400 dark:text-slate-500">
                        {(doc.file_size_bytes / 1024 / 1024).toFixed(2)} MB
                        {' · '}
                        <span
                          title={
                            isDocTypeNaoClassificado(doc.document_type)
                              ? DOC_TYPE_NAO_CLASSIFICADO_AJUDA
                              : undefined
                          }
                        >
                          {docTypeLabel(doc.document_type)}
                        </span>
                        {' · '}{new Date(doc.created_at).toLocaleDateString('pt-BR')}
                      </p>
                      {extractedDocIds.has(doc.id) && (
                        <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-purple-50 dark:bg-purple-500/10 text-purple-600 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30">
                          <Sparkles className="w-3 h-3" /> Campos extraidos
                        </span>
                      )}
                      {/* Dívida #103 — honestidade do áudio. A consultora sobe a
                          gravação da reunião achando que o sistema ouve; hoje o
                          arquivo fica guardado e ninguém o transcreve (não existe
                          pipeline de transcrição em lugar nenhum). Mesmo espírito
                          do aviso de geometria "sem leitura de texto": o arquivo
                          está salvo, e a tela diz o que ele NÃO é. */}
                      {ehAudio(doc) && (
                        <span
                          title="O arquivo está guardado no caso. A transcrição automática ainda não existe — registre os pontos da conversa à mão."
                          className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30"
                        >
                          🎙️ Áudio anexado — transcrição não disponível
                        </span>
                      )}
                    </div>
                    {/* Fase 1 (N1, item 3) — nota de processamento (P12: nenhum
                        documento mudo). Linha discreta, sem botões — mesmo
                        padrão visual da nota derivada espacial (ADR-020). */}
                    {doc.extraction_status && (
                      <p className="flex items-start gap-1.5 mt-1 text-xs text-gray-400 dark:text-slate-500">
                        <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                        <span>{doc.extraction_status}</span>
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleDownload(doc.id, doc.filename || doc.original_file_name || 'download')}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 text-sm transition-all"
                    >
                      <Download className="w-3.5 h-3.5" /> Baixar
                    </button>
                    <button
                      onClick={() => handleDelete(doc.id, doc.filename || doc.original_file_name || 'documento')}
                      disabled={deleteMutation.isPending}
                      title="Excluir documento"
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 text-red-500 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-500/10 hover:border-red-200 dark:hover:border-red-500/30 text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                {fields && fields.length > 0 && (
                  <div className="px-4 pb-3 -mt-1">
                    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-xs bg-white dark:bg-white/5 rounded-lg border border-purple-100 dark:border-purple-500/20 p-3">
                      {fields.map(([key, value]) => (
                        <div key={key} className="flex gap-2 min-w-0">
                          <dt className="text-gray-500 dark:text-slate-400 shrink-0">{labelFor(key)}:</dt>
                          <dd className="text-gray-800 dark:text-slate-200 truncate" title={humanizeValue(value)}>
                            {humanizeValue(value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
