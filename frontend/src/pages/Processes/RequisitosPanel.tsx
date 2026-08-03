/**
 * RequisitosPanel — os 6 documentos obrigatórios da base (Ficha 08 §2).
 *
 * Semântica honesta (P12 aplicado a requisitos): o consultor NUNCA lê "ausente"
 * com o documento visível na tela. A frase vem pronta do backend (`detalhe`) —
 * de propósito. Era a redação reimplementada em cada superfície que produzia as
 * respostas divergentes do caso 15 (checklist dizia "recebido", dossiê dizia
 * "ausente", verdade era "recebido, em processamento").
 *
 * Este painel NÃO decide nada: só mostra o que a fonte única respondeu.
 */

import { useQuery } from '@tanstack/react-query';
import {
  CheckCircle2, Clock, AlertTriangle, CircleDashed, Loader2, Link2,
} from 'lucide-react';
import { api } from '@/lib/api';

interface RequisitoDocumental {
  requisito: string;
  label: string;
  status: 'ausente' | 'recebido_em_processamento' | 'satisfeito_parcial' | 'satisfeito';
  detalhe: string;
  document_ids: number[];
  gaps: string[];
  alertas: string[];
  satisfeito_por: string | null;
  pendente: boolean;
}

interface DocumentoSemRequisito {
  id: number;
  filename: string | null;
  document_type: string | null;
  ocr_status: string | null;
}

interface RequisitosResponse {
  process_id: number;
  requisitos: RequisitoDocumental[];
  pendentes: number;
  total: number;
  nao_classificados: DocumentoSemRequisito[];
}

const STATUS_CFG: Record<
  RequisitoDocumental['status'],
  { icon: React.ReactNode; cls: string; chip: string; chipLabel: string }
> = {
  satisfeito: {
    icon: <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />,
    cls: 'border-emerald-200 dark:border-emerald-500/20 bg-emerald-50/60 dark:bg-emerald-500/5',
    chip: 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/20',
    chipLabel: 'Recebido',
  },
  satisfeito_parcial: {
    icon: <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />,
    cls: 'border-amber-200 dark:border-amber-500/20 bg-amber-50/60 dark:bg-amber-500/5',
    chip: 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/20',
    chipLabel: 'Incompleto',
  },
  recebido_em_processamento: {
    icon: <Clock className="w-4 h-4 text-blue-600 dark:text-blue-400" />,
    cls: 'border-blue-200 dark:border-blue-500/20 bg-blue-50/60 dark:bg-blue-500/5',
    chip: 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-500/20',
    chipLabel: 'Em processamento',
  },
  ausente: {
    icon: <CircleDashed className="w-4 h-4 text-gray-400 dark:text-slate-500" />,
    cls: 'border-gray-200 dark:border-white/10 bg-gray-50/60 dark:bg-white/3',
    chip: 'bg-gray-100 dark:bg-white/5 text-gray-600 dark:text-slate-400 border-gray-200 dark:border-white/10',
    chipLabel: 'Não recebido',
  },
};

export default function RequisitosPanel({ processId }: { processId: number }) {
  const { data, isLoading, error } = useQuery<RequisitosResponse>({
    queryKey: ['requisitos', processId],
    queryFn: () => api.get(`/processes/${processId}/requisitos`).then(r => r.data),
  });

  if (isLoading) {
    return (
      <p className="text-sm text-gray-500 dark:text-slate-400 flex items-center gap-1.5 p-1">
        <Loader2 className="w-4 h-4 animate-spin" /> Carregando requisitos…
      </p>
    );
  }

  // Radar-não-cancela: falha ao carregar os requisitos não derruba a aba inteira.
  if (error || !data) return null;

  const recebidos = data.total - data.pendentes;

  return (
    <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 dark:border-white/10">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
              Documentos obrigatórios da base
            </h3>
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
              {recebidos} de {data.total} recebidos · Ficha 08 §2
            </p>
          </div>
          {data.pendentes > 0 && (
            <span className="shrink-0 text-xs px-2 py-1 rounded-full bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-400">
              {data.pendentes} a coletar
            </span>
          )}
        </div>
      </div>

      <div className="divide-y divide-gray-100 dark:divide-white/5">
        {data.requisitos.map(req => {
          const cfg = STATUS_CFG[req.status];
          return (
            <div key={req.requisito} className={`px-5 py-3 border-l-2 ${cfg.cls}`}>
              <div className="flex items-start gap-3">
                <div className="mt-0.5 shrink-0">{cfg.icon}</div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium text-gray-800 dark:text-white">
                      {req.label}
                    </p>
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${cfg.chip}`}>
                      {cfg.chipLabel}
                    </span>
                    {req.satisfeito_por && (
                      <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded border bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/20">
                        <Link2 className="w-3 h-3" />
                        por equivalência
                      </span>
                    )}
                  </div>

                  {/* Frase pronta do backend — a tela não reescreve a semântica. */}
                  <p className="text-xs text-gray-600 dark:text-slate-400 mt-1">
                    {req.detalhe}
                  </p>

                  {/* Ficha §7.3 — vencimento: alerta, nunca trava. */}
                  {req.alertas.map((a, i) => (
                    <p
                      key={i}
                      className="text-xs text-amber-700 dark:text-amber-400 mt-1 flex items-start gap-1"
                    >
                      <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                      {a}
                    </p>
                  ))}
                </div>

                {req.document_ids.length > 0 && (
                  <span className="shrink-0 text-xs text-gray-400 dark:text-slate-500">
                    {req.document_ids.length} doc
                    {req.document_ids.length === 1 ? '' : 's'}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Validação 02/08 — o arquivo que o sistema não soube encaixar tem de
          aparecer mesmo assim. A consultora subiu o CAR e a Conferência seguiu
          dizendo que faltava: o documento existia, só não tinha `document_type`
          ainda (o OCR classifica depois) e sumia da conta em silêncio. Agora ele
          é nomeado, com o motivo, e o requisito continua honesto. */}
      {(data.nao_classificados?.length ?? 0) > 0 && (
        <div className="px-5 py-3 border-t border-gray-100 dark:border-white/10 bg-amber-50/40 dark:bg-amber-500/5">
          <p className="text-xs font-medium text-amber-800 dark:text-amber-300 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            {data.nao_classificados.length} documento
            {data.nao_classificados.length === 1 ? '' : 's'} anexado
            {data.nao_classificados.length === 1 ? '' : 's'} sem requisito reconhecido
          </p>
          <ul className="mt-1.5 space-y-1">
            {data.nao_classificados.map(doc => (
              <li key={doc.id} className="text-xs text-amber-700 dark:text-amber-400/90">
                {doc.filename ?? `documento #${doc.id}`}
                {' — '}
                {doc.ocr_status === 'pending' || doc.ocr_status === 'processing'
                  ? 'o sistema ainda está lendo o arquivo'
                  : doc.document_type
                    ? `classificado como "${doc.document_type}", que não é um dos 6`
                    : 'sem tipo reconhecido — informe o tipo em Documentos'}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
