/**
 * AlertaCard — um card por `RegulatoryIssue`.
 *
 * Cabeçalho: severidade + família + código de alerta.
 * Dois controles:
 *   1. Status do achado (perene) — `PATCH /properties/{prop}/issues/{id}`.
 *      Os 5 valores estão expostos via select. Regra A (coerência) é validada no
 *      backend sobre o estado RESULTANTE; o 422 aparece inline perto do controle.
 *   2. Decisão neste processo (contextual ao processo, ADR-012) — `PUT
 *      /processes/{pid}/issues/{iid}/decision`. Cinco radios + textarea de
 *      justificativa.
 *
 * Detalhe crítico (Regra B): enquanto `status_achado === 'suspeita'`, os
 * controles de decisão ficam DESABILITADOS com hint claro — o consultor adjudica
 * o achado primeiro, aí a decisão libera. Isso é o que evita travar no gate sem
 * caminho — não basta tratar o 422 depois, previne desabilitando.
 *
 * Justificativa obrigatória (#19) é validada client-side pra `ignorar_justificado`
 * e `fora_escopo`; o 422 do backend é rede de segurança.
 */

import { useEffect, useState } from 'react';
import type { AxiosError } from 'axios';
import { AlertCircle, Loader2 } from 'lucide-react';

import {
  useDecision,
  useUpdateIssue,
  useUpsertDecision,
} from '@/lib/regulatory/hooks';
import {
  DECISAO_HINT,
  DECISAO_LABEL,
  FAMILIA_LABEL,
  SEVERITY_CLS,
  SEVERITY_LABEL,
  STATUS_ACHADO_HINT,
  STATUS_ACHADO_LABEL,
  STATUS_SANEAMENTO_LABEL,
} from '@/lib/regulatory/labels';
import {
  ACHADOS_QUE_HABILITAM_DECISAO,
  DECISAOS_QUE_EXIGEM_JUSTIFICATIVA,
  type DecisaoConsultor,
  type RegulatoryIssue,
  type StatusAchado,
  type StatusSaneamento,
} from '@/lib/regulatory/types';

const STATUS_ACHADO_VALUES: StatusAchado[] = [
  'suspeita',
  'confirmada',
  'descartada',
  'resolvida',
  'ignorada',
];

const STATUS_SANEAMENTO_VALUES: StatusSaneamento[] = [
  'pendente',
  'em_validacao',
  'saneado',
  'descartado',
  'nao_aplicavel',
];

const DECISAO_VALUES: DecisaoConsultor[] = [
  'corrigir_antes',
  'seguir_com_ressalva',
  'solicitar_doc',
  'fora_escopo',
  'ignorar_justificado',
];

function extractDetail(err: unknown, fallback: string): string {
  const ax = err as AxiosError<{ detail?: string | { message?: string } }>;
  const d = ax?.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (d && typeof d === 'object' && typeof d.message === 'string') return d.message;
  return fallback;
}

interface AlertaCardProps {
  issue: RegulatoryIssue;
  processId: number;
}

export default function AlertaCard({ issue, processId }: AlertaCardProps) {
  // ── Estado local do card ────────────────────────────────────────────────
  const decisaoExigida = ACHADOS_QUE_HABILITAM_DECISAO.has(issue.status_achado);
  // Regra B em UI: enquanto suspeita, decisão fica congelada.
  const decisaoBloqueada = !decisaoExigida;

  // ── Mutations ───────────────────────────────────────────────────────────
  const updateIssue = useUpdateIssue(issue.property_id);
  const upsertDecision = useUpsertDecision(processId, issue.id);

  // ── Decisão atual neste processo ────────────────────────────────────────
  const decisionQuery = useDecision(processId, issue.id, decisaoExigida);

  // ── Form da decisão ─────────────────────────────────────────────────────
  const [decisaoSelecionada, setDecisaoSelecionada] = useState<DecisaoConsultor | null>(null);
  const [justificativa, setJustificativa] = useState('');
  const [decisaoTouched, setDecisaoTouched] = useState(false);

  // Sincroniza com o estado servidor quando a query carrega/muda.
  useEffect(() => {
    if (decisionQuery.data) {
      setDecisaoSelecionada(decisionQuery.data.decisao);
      setJustificativa(decisionQuery.data.justificativa ?? '');
    } else if (decisionQuery.data === null) {
      setDecisaoSelecionada(null);
      setJustificativa('');
    }
  }, [decisionQuery.data]);

  // ── Validação client-side da justificativa (#19) ────────────────────────
  const exigeJustificativa =
    decisaoSelecionada !== null && DECISAOS_QUE_EXIGEM_JUSTIFICATIVA.has(decisaoSelecionada);
  const justificativaVazia = justificativa.trim().length === 0;
  const justificativaInvalida = exigeJustificativa && justificativaVazia;

  // ── Erros inline ────────────────────────────────────────────────────────
  const issueError = updateIssue.error
    ? extractDetail(updateIssue.error, 'Falha ao atualizar status.')
    : null;
  const decisionError = upsertDecision.error
    ? extractDetail(upsertDecision.error, 'Falha ao registrar decisão.')
    : null;

  // ── Handlers ────────────────────────────────────────────────────────────
  function handleAchadoChange(value: StatusAchado) {
    updateIssue.mutate({ issueId: issue.id, payload: { status_achado: value } });
  }
  function handleSaneamentoChange(value: StatusSaneamento) {
    updateIssue.mutate({ issueId: issue.id, payload: { status_saneamento: value } });
  }
  function handleSubmitDecisao() {
    setDecisaoTouched(true);
    if (!decisaoSelecionada) return;
    if (justificativaInvalida) return;
    upsertDecision.mutate({
      decisao: decisaoSelecionada,
      justificativa: justificativa.trim() || null,
    });
  }

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div
      id={`alerta-${issue.id}`}
      className="rounded-2xl border border-gray-100 dark:border-white/10 bg-white dark:bg-white/5 p-5 space-y-4 scroll-mt-24"
    >
      {/* Cabeçalho */}
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full font-semibold border ${SEVERITY_CLS[issue.severity]}`}
            >
              {SEVERITY_LABEL[issue.severity]}
            </span>
            {issue.familia && (
              <span className="text-xs text-gray-500 dark:text-slate-400">
                {FAMILIA_LABEL[issue.familia]}
              </span>
            )}
          </div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mt-1.5 font-mono">
            {issue.codigo_alerta ?? '(sem código)'}
          </h3>
          {issue.documentos_cruzados && issue.documentos_cruzados.length > 0 && (
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
              Documentos: {issue.documentos_cruzados.join(' × ')}
            </p>
          )}
        </div>
      </header>

      {/* Status perenes do achado */}
      <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-slate-300 mb-1">
            Status do achado
          </label>
          <select
            value={issue.status_achado}
            onChange={e => handleAchadoChange(e.target.value as StatusAchado)}
            disabled={updateIssue.isPending}
            className="w-full text-sm rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-zinc-900 px-2.5 py-1.5 disabled:opacity-60"
            aria-label="Status do achado"
          >
            {STATUS_ACHADO_VALUES.map(v => (
              <option key={v} value={v}>
                {STATUS_ACHADO_LABEL[v]}
              </option>
            ))}
          </select>
          <p className="text-[11px] text-gray-400 dark:text-slate-500 mt-1">
            {STATUS_ACHADO_HINT[issue.status_achado]}
          </p>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-slate-300 mb-1">
            Status do saneamento
          </label>
          <select
            value={issue.status_saneamento}
            onChange={e => handleSaneamentoChange(e.target.value as StatusSaneamento)}
            disabled={updateIssue.isPending}
            className="w-full text-sm rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-zinc-900 px-2.5 py-1.5 disabled:opacity-60"
            aria-label="Status do saneamento"
          >
            {STATUS_SANEAMENTO_VALUES.map(v => (
              <option key={v} value={v}>
                {STATUS_SANEAMENTO_LABEL[v]}
              </option>
            ))}
          </select>
        </div>
      </section>

      {issueError && (
        <div className="rounded-lg bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 p-3 text-xs text-red-700 dark:text-red-300 flex items-start gap-2">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>{issueError}</span>
        </div>
      )}

      {/* Decisão neste processo (camada 2) */}
      <section className="border-t border-gray-100 dark:border-white/10 pt-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-semibold text-gray-700 dark:text-slate-200 uppercase tracking-wider">
            Decisão neste processo
          </h4>
          {decisionQuery.isLoading && decisaoExigida && (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400" />
          )}
        </div>

        {decisaoBloqueada && (
          <div className="rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 p-3 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2">
            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span>Confirme ou descarte o achado para poder decidir.</span>
          </div>
        )}

        <fieldset
          disabled={decisaoBloqueada || upsertDecision.isPending}
          className={decisaoBloqueada ? 'opacity-50 pointer-events-none mt-3' : 'mt-3'}
        >
          <div className="space-y-1.5">
            {DECISAO_VALUES.map(v => (
              <label
                key={v}
                className="flex items-start gap-2 text-sm cursor-pointer p-1.5 -mx-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5"
              >
                <input
                  type="radio"
                  name={`decisao-${issue.id}`}
                  value={v}
                  checked={decisaoSelecionada === v}
                  onChange={() => setDecisaoSelecionada(v)}
                  className="mt-0.5"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-gray-800 dark:text-slate-200">{DECISAO_LABEL[v]}</div>
                  <div className="text-[11px] text-gray-400 dark:text-slate-500">
                    {DECISAO_HINT[v]}
                  </div>
                </div>
              </label>
            ))}
          </div>

          {/* Textarea de justificativa */}
          <div className="mt-3">
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-300 mb-1">
              Justificativa{' '}
              {exigeJustificativa && (
                <span className="text-red-600 dark:text-red-400">*obrigatória</span>
              )}
            </label>
            <textarea
              value={justificativa}
              onChange={e => setJustificativa(e.target.value)}
              rows={2}
              placeholder={
                exigeJustificativa
                  ? 'Explique o motivo da decisão (obrigatório para ignorar / fora do escopo)'
                  : 'Opcional — registre o raciocínio se quiser'
              }
              aria-invalid={decisaoTouched && justificativaInvalida}
              className={`w-full text-sm rounded-lg border bg-white dark:bg-zinc-900 px-2.5 py-1.5 ${
                decisaoTouched && justificativaInvalida
                  ? 'border-red-300 dark:border-red-500/50'
                  : 'border-gray-200 dark:border-white/10'
              }`}
            />
            {decisaoTouched && justificativaInvalida && (
              <p className="text-[11px] text-red-600 dark:text-red-400 mt-1">
                Justificativa é obrigatória para esta decisão.
              </p>
            )}
          </div>

          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={handleSubmitDecisao}
              disabled={
                !decisaoSelecionada ||
                upsertDecision.isPending ||
                (exigeJustificativa && justificativaVazia)
              }
              className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
            >
              {upsertDecision.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {decisionQuery.data ? 'Atualizar decisão' : 'Registrar decisão'}
            </button>
            {decisionQuery.data && (
              <span className="text-[11px] text-gray-400 dark:text-slate-500">
                Última alteração:{' '}
                {new Date(decisionQuery.data.decided_at).toLocaleString('pt-BR')}
              </span>
            )}
          </div>
        </fieldset>

        {decisionError && (
          <div className="mt-3 rounded-lg bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 p-3 text-xs text-red-700 dark:text-red-300 flex items-start gap-2">
            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span>{decisionError}</span>
          </div>
        )}
      </section>
    </div>
  );
}
