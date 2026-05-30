/**
 * DiagnosisAssinatura — bloco "Assinar diagnóstico" + badge de pendentes + modal do gate 422.
 *
 * Renderiza dentro do `DiagnosisTab`. Encadeia:
 *  - `useDiagnoses(processId)` → última versão
 *  - `useIssues(propertyId, 'open')` → críticas abertas
 *  - `useQueries` de `decision` por issue crítica → conta pendentes client-side
 *  - `useValidateDiagnosis(processId)` → PATCH .../validate
 *
 * O backend é a autoridade do gate: se o 422 da lista divergir do cálculo
 * client-side (ex.: cache stale), confiamos no 422 e mostramos o que veio.
 *
 * UX: clique no item do modal fecha o modal e leva o consultor à aba Alertas
 * com scroll para o card `#alerta-${issueId}` (via callback `onGoToAlerta`).
 */

import { useState } from 'react';
import { useQueries } from '@tanstack/react-query';
import type { AxiosError } from 'axios';
import toast from 'react-hot-toast';
import { CheckCircle2, FilePen, Loader2, X } from 'lucide-react';

import { api } from '@/lib/api';
import {
  regulatoryKeys,
  useDiagnoses,
  useIssues,
  useValidateDiagnosis,
} from '@/lib/regulatory/hooks';
import {
  FAMILIA_LABEL,
  SEVERITY_CLS,
  SEVERITY_LABEL,
} from '@/lib/regulatory/labels';
import type {
  DiagnosisGate422Detail,
  ProcessIssueDecision,
} from '@/lib/regulatory/types';

interface DiagnosisAssinaturaProps {
  processId: number;
  propertyId: number | null;
  /** Callback opcional para o ProcessDetail trocar pra aba 'alertas' e fazer scroll. */
  onGoToAlerta?: (issueId: number) => void;
}

export default function DiagnosisAssinatura({
  processId,
  propertyId,
  onGoToAlerta,
}: DiagnosisAssinaturaProps) {
  const { data: diagnoses, isLoading: loadingDiag } = useDiagnoses(processId);
  const { data: issues = [] } = useIssues(propertyId, 'open');
  const validate = useValidateDiagnosis(processId);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalAlertas, setModalAlertas] = useState<DiagnosisGate422Detail['alertas_pendentes']>([]);

  // Última versão (backend já devolve ordenado por version desc).
  const ultima = diagnoses && diagnoses.length > 0 ? diagnoses[0] : null;

  // Críticas abertas — base para o badge client-side.
  const criticasAbertas = issues.filter(
    i => i.severity === 'critico' && i.resolved_at === null,
  );

  // useQueries dinâmico para puxar a decisão de cada crítica (404 = null).
  const decisionResults = useQueries({
    queries: criticasAbertas.map(issue => ({
      queryKey: regulatoryKeys.decision(processId, issue.id),
      queryFn: async (): Promise<ProcessIssueDecision | null> => {
        try {
          const r = await api.get(`/processes/${processId}/issues/${issue.id}/decision`);
          return r.data as ProcessIssueDecision;
        } catch (err) {
          const ax = err as AxiosError;
          if (ax.response?.status === 404) return null;
          throw err;
        }
      },
      enabled: !!processId && !!issue.id,
      staleTime: 30_000,
    })),
  });

  const allDecisionsLoaded = decisionResults.every(r => !r.isLoading);
  // Pendente = crítica aberta sem decisão registrada.
  const pendentesCount = allDecisionsLoaded
    ? criticasAbertas.filter((_, i) => decisionResults[i].data === null).length
    : null;

  // ── Handlers ────────────────────────────────────────────────────────────
  function handleAssinar() {
    if (!ultima) return;
    validate.mutate(
      { version: ultima.version },
      {
        onSuccess: () => {
          toast.success(`Diagnóstico v${ultima.version} assinado.`);
        },
        onError: err => {
          const ax = err as AxiosError<{ detail?: DiagnosisGate422Detail | string }>;
          const detail = ax.response?.data?.detail;
          // Shape do gate camada 2: objeto com `alertas_pendentes`.
          if (
            detail &&
            typeof detail === 'object' &&
            Array.isArray(detail.alertas_pendentes)
          ) {
            setModalAlertas(detail.alertas_pendentes);
            setModalOpen(true);
          } else if (ax.response?.status === 409) {
            // Já validado — caso raro de race (alguém assinou em outro tab).
            toast.error(typeof detail === 'string' ? detail : 'Diagnóstico já validado.');
          } else {
            toast.error(typeof detail === 'string' ? detail : 'Falha ao assinar diagnóstico.');
          }
        },
      },
    );
  }

  function handleGoToAlerta(issueId: number) {
    setModalOpen(false);
    if (onGoToAlerta) {
      onGoToAlerta(issueId);
    }
  }

  // ── Renders parciais ────────────────────────────────────────────────────
  if (loadingDiag) {
    return (
      <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-4 flex items-center gap-2 text-sm text-gray-500">
        <Loader2 className="w-4 h-4 animate-spin" /> Carregando diagnóstico…
      </div>
    );
  }

  if (!ultima) {
    // Nenhum diagnóstico criado ainda — nada pra assinar.
    return null;
  }

  if (ultima.validated_at) {
    return (
      <div className="rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 p-4">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">
            Diagnóstico v{ultima.version} assinado
          </p>
        </div>
        <p className="text-xs text-emerald-700 dark:text-emerald-400 mt-1">
          em {new Date(ultima.validated_at).toLocaleString('pt-BR')}
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-4 space-y-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h3 className="text-sm font-semibold text-gray-800 dark:text-white flex items-center gap-2">
              <FilePen className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              Assinar diagnóstico v{ultima.version}
            </h3>
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
              Camada 2 do Princípio 1 — toda crítica precisa de decisão neste processo.
            </p>
          </div>
          <button
            type="button"
            onClick={handleAssinar}
            disabled={validate.isPending}
            className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
          >
            {validate.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                Assinar
                {pendentesCount !== null && pendentesCount > 0 && (
                  <span className="bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300 text-[10px] font-semibold rounded-full px-1.5 py-0.5">
                    {pendentesCount} pendente{pendentesCount === 1 ? '' : 's'}
                  </span>
                )}
              </>
            )}
          </button>
        </div>
        {pendentesCount !== null && pendentesCount > 0 && (
          <p className="text-[11px] text-amber-700 dark:text-amber-300">
            {pendentesCount} alerta(s) crítico(s) sem decisão. Vá para "Alertas" e
            decida cada um antes de assinar.
          </p>
        )}
      </div>

      {/* Modal — gate 422: lista de alertas_pendentes do backend.
          O backend é autoridade: se divergir do cálculo client-side
          (cache stale), confiamos no 422. */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-5 border-b border-gray-100 dark:border-white/10 flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                  Faltam decisões para assinar
                </h2>
                <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
                  {modalAlertas.length} alerta(s) crítico(s) sem decisão neste
                  processo. Decida cada um antes de assinar o diagnóstico.
                </p>
              </div>
              <button
                onClick={() => setModalOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-white/5"
                aria-label="Fechar"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <ul className="p-3 space-y-1 max-h-80 overflow-auto">
              {modalAlertas.map(a => (
                <li key={a.id}>
                  <button
                    type="button"
                    onClick={() => handleGoToAlerta(a.id)}
                    className="w-full text-left flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5"
                  >
                    <span
                      className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full font-semibold border ${SEVERITY_CLS[a.severity]} shrink-0`}
                    >
                      {SEVERITY_LABEL[a.severity]}
                    </span>
                    <span className="text-sm font-mono text-gray-800 dark:text-slate-200 truncate">
                      {a.codigo_alerta ?? '(sem código)'}
                    </span>
                    {a.familia && (
                      <span className="text-xs text-gray-500 dark:text-slate-400 ml-auto shrink-0">
                        {FAMILIA_LABEL[a.familia]}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
            <div className="p-4 border-t border-gray-100 dark:border-white/10 flex justify-end">
              <button
                onClick={() => setModalOpen(false)}
                className="px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-white/10 text-gray-700 dark:text-slate-200 text-sm hover:bg-gray-200 dark:hover:bg-white/20"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
