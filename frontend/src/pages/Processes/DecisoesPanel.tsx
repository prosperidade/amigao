/**
 * DecisoesPanel — a Conferência por DECISÕES (Frente G, REC-001 + CONF-001,
 * ADR-067).
 *
 * A Conferência agrupava por CAMPO: 42 linhas na ELODI para 8 fatos do
 * domínio (spec Isis §3.3/§5). Este painel agrupa por FATO — a matrícula
 * citada pelo CAR e pela certidão vira UMA decisão ("Matrícula 3.181 integra
 * o imóvel"), com as duas evidências expansíveis, não dois campos a validar
 * em separado.
 *
 * Linha de staging sem regra de chave natural (`sem_agrupamento`) NÃO aparece
 * aqui — continua na lista campo a campo do `ConsolidacaoPanel`, que filtra
 * pelas mesmas `staging_ids` que este painel cobre. Ver ADR-067: aditivo, não
 * substitui a tela antiga.
 */

import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';
import {
  CheckCircle2, ChevronDown, ChevronRight, Database, Loader2, RotateCcw, Scale,
} from 'lucide-react';
import { api } from '@/lib/api';
import { humanizeValue } from '@/lib/labels/fieldLabels';
import { docTypeLabel } from '@/lib/labels/docLabels';

interface Evidencia {
  staging_id: number | null;
  documento_id: number | null;
  documento_tipo: string | null;
  campo: string | null;
  valor_bruto: unknown;
  valor_normalizado: unknown;
  unidade: string | null;
  vigencia: string | null;
  status: string;
  fonte_autoritativa: boolean;
}

interface Decisao {
  chave: { entidade: string; identificador: string; aspecto: string };
  chave_str: string;
  label: string;
  evidencias: Evidencia[];
  concordancia: 'concordam' | 'divergem' | 'fonte_unica';
  nivel_divergencia: 'informativo' | 'atencao' | 'alto' | 'critico' | null;
  delta: number | null;
  percentual: number | null;
  valor_proposto: unknown;
  fonte_autoritativa_doc: string | null;
  estado: 'pendente' | 'decidida' | 'gravada';
  staging_ids: number[];
}

export interface ReconciliationData {
  decisoes: Decisao[];
  sem_agrupamento: Array<{ staging_id: number; motivo: string | null }>;
  total_staging: number;
}

function errDetail(e: unknown, fallback: string): string {
  const ax = e as AxiosError<{ detail?: string }>;
  return ax?.response?.data?.detail ?? ax?.message ?? fallback;
}

export function decisoesQueryKey(processId: number) {
  return ['staging-decisions', processId];
}

const ESTADO_CLS: Record<string, string> = {
  pendente: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-white/10 dark:text-slate-300 dark:border-white/10',
  decidida: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-500/30',
  gravada: 'bg-emerald-600 text-white border-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-300 dark:border-emerald-500/40',
};
const ESTADO_LABEL: Record<string, string> = {
  pendente: 'Pendente', decidida: 'Decidida — aguardando gravação', gravada: 'Gravado na base',
};

const NIVEL_CLS: Record<string, string> = {
  informativo: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-white/10 dark:text-slate-300 dark:border-white/10',
  atencao: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30',
  alto: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-500/10 dark:text-orange-300 dark:border-orange-500/30',
  critico: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/30',
};

function concordanciaLabel(d: Decisao): string {
  if (d.concordancia === 'fonte_unica') return 'Fonte única';
  if (d.concordancia === 'concordam') return 'Fontes concordam';
  const pct = d.percentual != null ? ` (${(d.percentual * 100).toFixed(1)}%)` : '';
  return `Divergência${pct}`;
}

function concordanciaCls(d: Decisao): string {
  if (d.concordancia === 'divergem' && d.nivel_divergencia) {
    return NIVEL_CLS[d.nivel_divergencia] ?? NIVEL_CLS.atencao;
  }
  if (d.concordancia === 'concordam') {
    return 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30';
  }
  return 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-white/10 dark:text-slate-300 dark:border-white/10';
}

function DecisaoCard({ processId, decisao }: { processId: number; decisao: Decisao }) {
  const qc = useQueryClient();
  // Concordantes vêm recolhidas (CONF-001: "evidências concordantes ficam
  // recolhidas, mas acessíveis"); divergência ou fonte única já abrem, porque
  // é ali que a consultora precisa olhar primeiro.
  const [expandido, setExpandido] = useState(decisao.concordancia !== 'concordam');

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: decisoesQueryKey(processId) });
    qc.invalidateQueries({ queryKey: ['staging-fields', processId] });
  };

  const decidir = useMutation({
    mutationFn: (acao: 'aceitar' | 'reabrir') =>
      api.post(`/processes/${processId}/staging-decisions/decidir`, {
        entidade: decisao.chave.entidade,
        identificador: decisao.chave.identificador,
        aspecto: decisao.chave.aspecto,
        acao,
      }).then(r => r.data),
    onSuccess: invalidate,
    onError: (e) => toast.error(errDetail(e, 'Falha ao decidir.')),
  });

  return (
    <div className="rounded-lg border border-gray-100 dark:border-white/10 bg-gray-50 dark:bg-white/5 p-3 space-y-2">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <button
          onClick={() => setExpandido(v => !v)}
          className="flex items-center gap-1.5 text-sm font-medium text-gray-800 dark:text-slate-200 min-w-0"
        >
          {expandido ? <ChevronDown className="w-3.5 h-3.5 shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0" />}
          <span className="truncate">{decisao.label}</span>
        </button>
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className={`text-xs px-2 py-0.5 rounded border whitespace-nowrap ${concordanciaCls(decisao)}`}>
            {concordanciaLabel(decisao)}
          </span>
          <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded border whitespace-nowrap ${ESTADO_CLS[decisao.estado]}`}>
            {decisao.estado === 'gravada' && <Database className="w-3 h-3" />}
            {ESTADO_LABEL[decisao.estado]}
          </span>
        </div>
      </div>

      {expandido && (
        <div className="space-y-1 pl-5">
          {decisao.evidencias.map((e, i) => (
            <div key={e.staging_id ?? `calc-${i}`} className="flex items-center gap-2 flex-wrap text-xs text-gray-600 dark:text-slate-400">
              <span className="px-1.5 py-0.5 rounded bg-white dark:bg-white/10 border border-gray-200 dark:border-white/10">
                {docTypeLabel(e.documento_tipo)}
              </span>
              {e.campo && <span className="text-gray-400 dark:text-slate-500">{e.campo}</span>}
              <span className="font-medium text-gray-700 dark:text-slate-300">
                {humanizeValue(e.valor_normalizado)}{e.unidade ? ` ${e.unidade}` : ''}
              </span>
              {e.vigencia && (
                <span className="px-1.5 py-0.5 rounded bg-white dark:bg-white/10 border border-gray-200 dark:border-white/10">
                  {e.vigencia}
                </span>
              )}
              {e.fonte_autoritativa && (
                <span className="flex items-center gap-1 text-purple-600 dark:text-purple-300">
                  <Scale className="w-3 h-3" /> fonte autoritativa
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1.5 pt-1">
        {decisao.estado === 'pendente' ? (
          <button
            onClick={() => decidir.mutate('aceitar')}
            disabled={decidir.isPending}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white"
          >
            {decidir.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
            Aceitar proposta
          </button>
        ) : (
          <button
            onClick={() => decidir.mutate('reabrir')}
            disabled={decidir.isPending}
            title="Reabrir esta decisão (volta a pendente)"
            className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-white/10 disabled:opacity-40"
          >
            <RotateCcw className="w-3 h-3" /> Reabrir
          </button>
        )}
      </div>
    </div>
  );
}

export default function DecisoesPanel({ processId }: { processId: number }) {
  const { data, isLoading } = useQuery<ReconciliationData>({
    queryKey: decisoesQueryKey(processId),
    queryFn: () => api.get(`/processes/${processId}/staging-decisions`).then(r => r.data),
  });

  const decisoes = useMemo(() => data?.decisoes ?? [], [data]);

  if (isLoading) {
    return (
      <p className="text-sm text-gray-500 dark:text-slate-400 flex items-center gap-1.5">
        <Loader2 className="w-4 h-4 animate-spin" /> Carregando decisões…
      </p>
    );
  }
  if (decisoes.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider">
        Decisões ({decisoes.length})
      </p>
      {decisoes.map(d => (
        <DecisaoCard key={d.chave_str} processId={processId} decisao={d} />
      ))}
    </div>
  );
}
