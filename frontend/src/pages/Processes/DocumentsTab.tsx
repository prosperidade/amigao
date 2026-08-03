import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { useState } from 'react';
import {
  FileText, Download, Sparkles, Trash2, Info, Loader2, RefreshCw,
  AlertTriangle, EyeOff, Eye, X,
} from 'lucide-react';
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

/** Texto lido do documento — OCR de PDF ou transcrição de áudio (ADR-060). */
interface DocumentText {
  document_id: number;
  filename?: string | null;
  ocr_status?: string | null;
  ocr_error?: string | null;
  eh_transcricao: boolean;
  chars: number;
  text?: string | null;
}

interface DocumentsTabProps {
  processId: number;
}

/**
 * Estado da transcrição na tela (dívida #103).
 *
 * A Isis subia a gravação e a tela dizia "transcrição não disponível" — honesto
 * enquanto não existia pipeline, e mentiroso a partir de agora. O contrato aqui é
 * o mesmo do resto do sistema: **nunca silêncio**. Ou está processando, ou está
 * pronta, ou falhou COM O MOTIVO na cara e um botão para tentar de novo.
 *
 * `not_required` não aparece para áudio (nada dispensa a leitura de um áudio); se
 * aparecer, cai no ramo de "sem leitura" com o mesmo aviso do pendente.
 */
function estadoTranscricao(doc: Document): 'processando' | 'pronta' | 'falhou' {
  if (doc.ocr_status === 'failed') return 'falhou';
  if (doc.tem_texto && doc.ocr_status === 'done') return 'pronta';
  return 'processando';
}

export default function DocumentsTab({ processId }: DocumentsTabProps) {
  const queryClient = useQueryClient();
  const [textoAberto, setTextoAberto] = useState<DocumentText | null>(null);

  const { data: documents, refetch: refetchDocuments } = useQuery({
    queryKey: ['documents', processId],
    queryFn: async () => {
      const res = await api.get(`/documents/?process_id=${processId}`);
      return res.data as Document[];
    },
    enabled: !!processId,
    // Transcrição de uma reunião leva de segundos a alguns minutos. Sem este
    // polling o consultor fica olhando "Transcrevendo…" para sempre e precisa
    // dar F5 para descobrir que já acabou (o WebSocket cobre parte dos casos,
    // mas não a aba aberta antes do evento chegar).
    refetchInterval: (query) => {
      const docs = (query.state.data ?? []) as Document[];
      const emCurso = docs.some(
        d => d.ocr_status === 'pending' || d.ocr_status === 'processing',
      );
      return emCurso ? 5000 : false;
    },
  });

  // Transcrição pronta: abre o texto num painel. Buscado sob demanda — uma
  // reunião de 30 min tem dezenas de milhares de caracteres e não pode viajar
  // junto da listagem de documentos.
  const verTextoMutation = useMutation({
    mutationFn: async (docId: number) => {
      const res = await api.get(`/documents/${docId}/text`);
      return res.data as DocumentText;
    },
    onSuccess: (data) => setTextoAberto(data),
    onError: () => toast.error('Não foi possível abrir o texto do documento.'),
  });

  // "Tentar de novo" — mesma rota do reprocesso de OCR: para o consultor a ação
  // é uma só ("ler de novo"), independente de ser PDF ou áudio.
  const reprocessarMutation = useMutation({
    mutationFn: async (docId: number) => {
      await api.post(`/documents/${docId}/reprocess-ocr`);
    },
    onSuccess: () => {
      toast.success('Transcrição reenviada. Isso leva alguns minutos.');
      queryClient.invalidateQueries({ queryKey: ['documents', processId] });
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Não foi possível reenviar a transcrição.';
      toast.error(msg);
    },
  });

  const visibilidadeMutation = useMutation({
    mutationFn: async ({ docId, interno }: { docId: number; interno: boolean }) => {
      await api.patch(`/documents/${docId}`, { is_internal: interno });
    },
    onSuccess: (_data, vars) => {
      toast.success(
        vars.interno
          ? 'Marcado como material interno — o cliente não vê no portal.'
          : 'Desmarcado — volta a ser documento do caso.',
      );
      queryClient.invalidateQueries({ queryKey: ['documents', processId] });
    },
    onError: () => toast.error('Não foi possível alterar a visibilidade.'),
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
                      {/* Dívida #103 — o áudio agora é ouvido de verdade. A tela
                          mostra em que pé está a transcrição: processando, pronta
                          (com o texto a um clique) ou falhou COM O MOTIVO. O que
                          não pode voltar a existir é o silêncio: a consultora subia
                          a gravação achando que o sistema ouvia. */}
                      {ehAudio(doc) && estadoTranscricao(doc) === 'processando' && (
                        <span
                          title="A transcrição está na fila. Reunião de meia hora costuma levar poucos minutos."
                          className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-500/30"
                        >
                          <Loader2 className="w-3 h-3 animate-spin" /> Transcrevendo o áudio…
                        </span>
                      )}
                      {ehAudio(doc) && estadoTranscricao(doc) === 'pronta' && (
                        <button
                          onClick={() => verTextoMutation.mutate(doc.id)}
                          disabled={verTextoMutation.isPending}
                          title="Abrir a transcrição da reunião"
                          className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                        >
                          🎙️ Transcrição pronta — ver texto
                        </button>
                      )}
                      {ehAudio(doc) && estadoTranscricao(doc) === 'falhou' && (
                        <button
                          onClick={() => reprocessarMutation.mutate(doc.id)}
                          disabled={reprocessarMutation.isPending}
                          title={doc.ocr_error ?? 'A transcrição falhou. Clique para tentar de novo.'}
                          className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-500/30 hover:bg-red-100 dark:hover:bg-red-500/20 transition-colors disabled:opacity-50"
                        >
                          <RefreshCw className={`w-3 h-3 ${reprocessarMutation.isPending ? 'animate-spin' : ''}`} />
                          Transcrição falhou — tentar de novo
                        </button>
                      )}
                      {doc.is_internal && (
                        <span
                          title="Material interno do escritório — não aparece para o cliente no portal."
                          className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/10 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-white/15"
                        >
                          <EyeOff className="w-3 h-3" /> Material interno
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
                    {/* O motivo da falha em TEXTO, não só no tooltip do chip. A
                        pergunta que o consultor faz é "por que não leu?", e a
                        resposta não pode depender de ele passar o mouse no lugar
                        certo — nem de alguém abrir o log por ele. */}
                    {doc.ocr_status === 'failed' && doc.ocr_error && (
                      <p className="flex items-start gap-1.5 mt-1 text-xs text-red-600 dark:text-red-400">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                        <span>{doc.ocr_error}</span>
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {/* Visibilidade (ADR-060, decisão 3b): default é documento do
                        caso; esconder do cliente é ato explícito do consultor e
                        fica registrado no audit. */}
                    <button
                      onClick={() =>
                        visibilidadeMutation.mutate({ docId: doc.id, interno: !doc.is_internal })
                      }
                      disabled={visibilidadeMutation.isPending}
                      title={
                        doc.is_internal
                          ? 'Material interno — clique para voltar a exibir ao cliente no portal'
                          : 'Visível ao cliente no portal — clique para marcar como material interno'
                      }
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 text-sm transition-all disabled:opacity-40"
                    >
                      {doc.is_internal
                        ? <EyeOff className="w-3.5 h-3.5" />
                        : <Eye className="w-3.5 h-3.5" />}
                    </button>
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

      {/* Painel da transcrição. A reunião é fonte primária do caso — o consultor
          precisa poder LER o que foi dito, não só saber que existe um áudio. O
          texto vem com o cabeçalho de origem já embutido pelo backend, então a
          procedência viaja com o conteúdo mesmo se ele for copiado daqui. */}
      {textoAberto && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setTextoAberto(null)}
        >
          <div
            className="w-full max-w-3xl max-h-[80vh] flex flex-col rounded-xl bg-white dark:bg-slate-900 border border-gray-200 dark:border-white/10 shadow-xl"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 p-4 border-b border-gray-100 dark:border-white/10">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-gray-800 dark:text-white truncate">
                  {textoAberto.eh_transcricao ? 'Transcrição da reunião' : 'Texto do documento'}
                </p>
                <p className="text-xs text-gray-400 dark:text-slate-500 truncate">
                  {textoAberto.filename} · {textoAberto.chars.toLocaleString('pt-BR')} caracteres
                </p>
              </div>
              <button
                onClick={() => setTextoAberto(null)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="overflow-y-auto p-4">
              {textoAberto.text
                ? (
                  <pre className="whitespace-pre-wrap break-words text-sm text-gray-700 dark:text-slate-300 font-sans">
                    {textoAberto.text}
                  </pre>
                )
                : (
                  <p className="text-sm text-gray-500 dark:text-slate-400">
                    {textoAberto.ocr_error ?? 'Este documento ainda não tem texto lido.'}
                  </p>
                )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
