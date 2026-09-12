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
  CheckCircle2, ChevronDown, ChevronRight, Database, Loader2, Pencil, RotateCcw, Scale,
} from 'lucide-react';
import { api } from '@/lib/api';
import { humanizeValue, OBSERVACAO_LABELS } from '@/lib/labels/fieldLabels';
import { docTypeLabel } from '@/lib/labels/docLabels';
import { decisoesQueryKey, progressoConferenciaKey, type Decisao, type ReconciliationData } from '@/lib/reconciliation';

function errDetail(e: unknown, fallback: string): string {
  const ax = e as AxiosError<{ detail?: string }>;
  return ax?.response?.data?.detail ?? ax?.message ?? fallback;
}

const ESTADO_CLS: Record<string, string> = {
  pendente: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-white/10 dark:text-slate-300 dark:border-white/10',
  decidida: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-500/30',
  parcialmente_gravada: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30',
  gravada: 'bg-emerald-600 text-white border-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-300 dark:border-emerald-500/40',
};
const ESTADO_LABEL: Record<string, string> = {
  pendente: 'Pendente', decidida: 'Decidida — aguardando gravação',
  parcialmente_gravada: 'Parcialmente gravada', gravada: 'Gravado na base',
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
  const primeira = decisao.evidencias.find(e => e.staging_id != null);
  const temTipo = decisao.evidencias.some(e => e.staging_id != null && !!e.tipo_observacao);
  const [stagingId, setStagingId] = useState<number | null>(primeira?.staging_id ?? null);
  const [valorEditado, setValorEditado] = useState(
    typeof primeira?.valor_bruto === 'string' || typeof primeira?.valor_bruto === 'number'
      ? String(primeira.valor_bruto) : '',
  );
  const [tipoEditado, setTipoEditado] = useState(primeira?.tipo_observacao ?? '');

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: decisoesQueryKey(processId) });
    qc.invalidateQueries({ queryKey: ['staging-fields', processId] });
    // STATE-001/ADR-068 (Frente H, achado do code review) — decidir AQUI é o
    // gesto que muda `progresso_conferencia`; sem isto o banner canônico do
    // `ConsolidacaoPanel` (acima deste painel, na mesma tela) ficava com a
    // contagem velha até um reload.
    qc.invalidateQueries({ queryKey: progressoConferenciaKey(processId) });
  };

  const decidir = useMutation({
    mutationFn: (payload: {
      acao: 'aceitar' | 'reabrir' | 'escolher_fonte' | 'editar' | 'reclassificar';
      staging_id?: number | null;
      valor?: unknown;
      tipo_observacao?: string;
    }) =>
      api.post(`/processes/${processId}/staging-decisions/decidir`, {
        entidade: decisao.chave.entidade,
        identificador: decisao.chave.identificador,
        aspecto: decisao.chave.aspecto,
        ...payload,
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
              {decisao.concordancia === 'divergem' && decisao.estado === 'pendente' && e.staging_id != null && (
                <button
                  onClick={() => decidir.mutate({ acao: 'escolher_fonte', staging_id: e.staging_id })}
                  disabled={decidir.isPending}
                  className="text-purple-700 dark:text-purple-300 underline disabled:opacity-40"
                >
                  Escolher esta fonte
                </button>
              )}
            </div>
          ))}
          {/* Frente J (item 5, CONF-002): dois gestos que o cartão não tinha.
              (a) divergência → escolher a fonte ou editar o VALOR de uma
              evidência (antes só "aceitar", que aplica a fonte autoritativa,
              ou "reabrir"); (b) qualquer decisão pendente com evidência
              TIPADA (ADR-065) → corrigir o TIPO que o modelo sugeriu — o
              padrão medido no #23 é "valor certo, tipo errado", e isso não
              depende de haver divergência. O original fica em
              `atributos.tipo_sugerido`; a reconciliação consome o decidido. */}
          {decisao.estado === 'pendente' && primeira && (decisao.concordancia === 'divergem' || temTipo) && (
            <div className="mt-2 rounded border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-2 space-y-2">
              <label className="block text-xs text-gray-600 dark:text-slate-300">
                Evidência a editar
                <select
                  aria-label="Evidência a editar"
                  value={stagingId ?? ''}
                  onChange={(event) => {
                    const id = Number(event.target.value);
                    const escolhida = decisao.evidencias.find(e => e.staging_id === id);
                    setStagingId(id);
                    setValorEditado(
                      typeof escolhida?.valor_bruto === 'string' || typeof escolhida?.valor_bruto === 'number'
                        ? String(escolhida.valor_bruto) : '',
                    );
                    setTipoEditado(escolhida?.tipo_observacao ?? '');
                  }}
                  className="mt-1 w-full rounded border border-gray-200 dark:border-white/10 bg-white dark:bg-slate-900 px-2 py-1"
                >
                  {decisao.evidencias.filter(e => e.staging_id != null).map(e => (
                    <option key={e.staging_id!} value={e.staging_id!}>
                      {docTypeLabel(e.documento_tipo)} — {e.campo ?? `linha ${e.staging_id}`}
                    </option>
                  ))}
                </select>
              </label>
              {decisao.concordancia === 'divergem' && (
              <div className="flex gap-1.5 flex-wrap">
                <input
                  aria-label="Valor decidido"
                  value={valorEditado}
                  onChange={event => setValorEditado(event.target.value)}
                  className="min-w-48 flex-1 rounded border border-gray-200 dark:border-white/10 bg-white dark:bg-slate-900 px-2 py-1 text-xs"
                />
                <button
                  onClick={() => decidir.mutate({ acao: 'editar', staging_id: stagingId, valor: valorEditado })}
                  disabled={decidir.isPending || stagingId == null || valorEditado.trim() === ''}
                  className="flex items-center gap-1 rounded border border-gray-200 dark:border-white/10 px-2 py-1 text-xs disabled:opacity-40"
                >
                  <Pencil className="w-3 h-3" /> Editar valor
                </button>
              </div>
              )}
              {temTipo && (
              <div className="flex gap-1.5 flex-wrap">
                <select
                  aria-label="Tipo de observação decidido"
                  value={tipoEditado}
                  onChange={event => setTipoEditado(event.target.value)}
                  className="min-w-48 flex-1 rounded border border-gray-200 dark:border-white/10 bg-white dark:bg-slate-900 px-2 py-1 text-xs"
                >
                  <option value="">Escolher tipo de observação</option>
                  {Object.entries(OBSERVACAO_LABELS).filter(([tipo]) => tipo !== 'nao_classificado').map(([tipo, label]) => (
                    <option key={tipo} value={tipo}>{label}</option>
                  ))}
                </select>
                <button
                  onClick={() => decidir.mutate({ acao: 'reclassificar', staging_id: stagingId, tipo_observacao: tipoEditado })}
                  disabled={decidir.isPending || stagingId == null || !tipoEditado}
                  className="flex items-center gap-1 rounded border border-gray-200 dark:border-white/10 px-2 py-1 text-xs disabled:opacity-40"
                >
                  <Pencil className="w-3 h-3" /> Editar tipo
                </button>
              </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-1.5 pt-1">
        {decisao.estado === 'pendente' ? (
          <button
            onClick={() => decidir.mutate({ acao: 'aceitar' })}
            disabled={decidir.isPending}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white"
          >
            {decidir.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
            Aceitar proposta
          </button>
        ) : (
          <button
            onClick={() => decidir.mutate({ acao: 'reabrir' })}
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
