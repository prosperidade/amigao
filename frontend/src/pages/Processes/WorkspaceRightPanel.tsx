/**
 * WorkspaceRightPanel — Painel lateral direito do Workspace do Caso (Regente Cam3 CAM3WS-001).
 *
 * Mostra:
 *  - Estado atual da etapa + badge
 *  - Objetivo da etapa
 *  - Próxima ação sugerida
 *  - Saída esperada (expected_outputs da etapa)
 *  - Validação humana necessária (actions completas mas não validadas)
 *  - Travas/blockers
 *  - Agente principal da etapa
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';
import { CheckCircle2, AlertTriangle, ArrowRight, Bot, Target, Lock, Loader2, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import { MACROETAPA_STATE_BADGE, MACROETAPA_LABELS } from './quadro-types';

// Mapeamento agentes principais por etapa (Regente Cam3)
const PRIMARY_AGENT_BY_STAGE: Record<string, string[]> = {
  entrada_demanda:        ['agent_atendimento'],
  diagnostico_preliminar: ['agent_atendimento', 'agent_diagnostico'],
  coleta_documental:      ['agent_extrator'],
  diagnostico_tecnico:    ['agent_diagnostico'],
  caminho_regulatorio:    ['agent_legislacao'],
  orcamento_negociacao:   ['agent_orcamento', 'agent_financeiro'],
  contrato_formalizacao:  ['agent_redator', 'agent_financeiro'],
};

interface CanAdvance {
  can_advance: boolean;
  current_macroetapa: string | null;
  current_state: string | null;
  next_macroetapa: string | null;
  blockers: string[];
  gaps: string[];                 // CAM3WS-005 (Sprint K) — lacunas informativas
  objective: string | null;
  expected_outputs: string[];
}

interface ActionItem {
  id: string;
  label: string;
  completed: boolean;
  needs_human_validation: boolean;
  validated_at: string | null;
}

interface MacroetapaStatus {
  current_macroetapa: string | null;
  next_action: string | null;
  steps: { macroetapa: string; actions: ActionItem[]; status: string }[];
}

interface Props {
  processId: number;
  /** Quando o usuário clica em validar uma action — pai pode reagir. */
  onValidateAction?: (etapa: string, actionId: string) => void;
}

export default function WorkspaceRightPanel({ processId, onValidateAction }: Props) {
  const queryClient = useQueryClient();
  const { data: gate } = useQuery({
    queryKey: ['process-can-advance', processId],
    queryFn: () => api.get<CanAdvance>(`/processes/${processId}/can-advance`).then(r => r.data),
    staleTime: 15_000,
  });
  const { data: status } = useQuery({
    queryKey: ['process-macroetapa-status', processId],
    queryFn: () => api.get<MacroetapaStatus>(`/processes/${processId}/macroetapa/status`).then(r => r.data),
    staleTime: 15_000,
  });

  // CAM3FT-005 — Gate formal de transição entre etapas (Regente Cam3).
  // Só o Workspace avança macroetapa. O Quadro de Ações apenas coordena.
  const advanceMutation = useMutation({
    mutationFn: (nextMacroetapa: string) =>
      api.post(`/processes/${processId}/macroetapa`, { macroetapa: nextMacroetapa }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['process', processId] });
      queryClient.invalidateQueries({ queryKey: ['process-can-advance', processId] });
      queryClient.invalidateQueries({ queryKey: ['process-macroetapa-status', processId] });
      queryClient.invalidateQueries({ queryKey: ['kanban'] });
      queryClient.invalidateQueries({ queryKey: ['kanban-insights'] });
      toast.success('Etapa avançada');
    },
    onError: (err: AxiosError<{ detail?: string }>) => {
      toast.error(err.response?.data?.detail ?? 'Erro ao avançar etapa');
    },
  });

  if (!gate) {
    return (
      <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-4 animate-pulse h-64" />
    );
  }

  const stateBadge = gate.current_state ? MACROETAPA_STATE_BADGE[gate.current_state] : null;
  const currentEtapa = gate.current_macroetapa ?? '';
  const agents = PRIMARY_AGENT_BY_STAGE[currentEtapa] ?? [];

  const currentStep = status?.steps.find(s => s.macroetapa === currentEtapa);
  const pendingValidations = (currentStep?.actions ?? []).filter(
    a => a.completed && a.needs_human_validation && !a.validated_at,
  );

  return (
    <div className="space-y-4">
      {/* Estado da etapa */}
      <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-4 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-slate-400 font-medium">
            Estado da etapa
          </span>
          {stateBadge && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${stateBadge.cls}`}>
              {stateBadge.label}
            </span>
          )}
        </div>
        {gate.objective && (
          <div className="flex gap-2 mt-1.5">
            <Target className="w-4 h-4 mt-0.5 shrink-0 text-emerald-500" />
            <p className="text-sm text-gray-700 dark:text-slate-200 leading-snug">
              {gate.objective}
            </p>
          </div>
        )}
      </div>

      {/* Botão Avançar etapa (Regente Cam3 CAM3FT-005 — gate formal) */}
      {gate.next_macroetapa && (
        <button
          type="button"
          onClick={() => gate.next_macroetapa && advanceMutation.mutate(gate.next_macroetapa)}
          disabled={!gate.can_advance || advanceMutation.isPending}
          className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-2xl text-sm font-semibold transition-colors ${
            gate.can_advance
              ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
              : 'bg-gray-100 dark:bg-white/5 text-gray-400 dark:text-slate-500 cursor-not-allowed border border-gray-200 dark:border-white/10'
          }`}
          title={
            gate.can_advance
              ? `Avançar para: ${MACROETAPA_LABELS[gate.next_macroetapa] ?? gate.next_macroetapa}`
              : 'Requisitos pendentes — veja as travas abaixo'
          }
        >
          {advanceMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : gate.can_advance ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <Lock className="w-4 h-4" />
          )}
          <span className="truncate">
            {gate.can_advance
              ? `Avançar → ${MACROETAPA_LABELS[gate.next_macroetapa] ?? gate.next_macroetapa}`
              : 'Aguardando requisitos'}
          </span>
        </button>
      )}

      {/* Caso encerrado (sem próxima etapa) */}
      {!gate.next_macroetapa && gate.current_macroetapa === 'contrato_formalizacao' && (
        <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 p-4 text-center">
          <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto mb-1.5" />
          <p className="text-sm font-semibold text-emerald-900 dark:text-emerald-100">
            Caso formalizado
          </p>
          <p className="text-xs text-emerald-700 dark:text-emerald-300 mt-0.5">
            Última etapa do fluxo concluída
          </p>
        </div>
      )}

      {/* Próxima ação */}
      {status?.next_action && (
        <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 p-4">
          <div className="flex items-center gap-2 mb-1">
            <ArrowRight className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span className="text-xs uppercase tracking-wide text-emerald-700 dark:text-emerald-300 font-semibold">
              Próxima ação
            </span>
          </div>
          <p className="text-sm text-emerald-900 dark:text-emerald-100 leading-snug">
            {status.next_action}
          </p>
        </div>
      )}

      {/* Validação humana pendente */}
      {pendingValidations.length > 0 && (
        <div className="rounded-2xl bg-violet-50 dark:bg-violet-500/10 border border-violet-200 dark:border-violet-500/30 p-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-4 h-4 text-violet-600 dark:text-violet-400" />
            <span className="text-xs uppercase tracking-wide text-violet-700 dark:text-violet-300 font-semibold">
              Validação humana necessária
            </span>
          </div>
          <ul className="space-y-1.5">
            {pendingValidations.map(a => (
              <li key={a.id} className="flex items-start gap-2 text-sm text-violet-900 dark:text-violet-100">
                <span className="flex-1 leading-snug">{a.label}</span>
                {onValidateAction && (
                  <button
                    onClick={() => onValidateAction(currentEtapa, a.id)}
                    className="text-xs px-2 py-0.5 rounded-md bg-violet-200 dark:bg-violet-500/30 text-violet-800 dark:text-violet-100 hover:bg-violet-300 dark:hover:bg-violet-500/50"
                  >
                    Validar
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Travas */}
      {gate.blockers.length > 0 && (
        <div className="rounded-2xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 p-4">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400" />
            <span className="text-xs uppercase tracking-wide text-red-700 dark:text-red-300 font-semibold">
              Travas para avançar
            </span>
          </div>
          <ul className="space-y-1 mt-2 text-sm text-red-900 dark:text-red-100">
            {gate.blockers.map((b, i) => (
              <li key={i}>• {b}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Lacunas (CAM3WS-005 / Sprint K) — informativas, não travam avanço */}
      {gate.gaps && gate.gaps.length > 0 && (
        <div className="rounded-2xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 p-4">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            <span className="text-xs uppercase tracking-wide text-amber-700 dark:text-amber-300 font-semibold">
              Lacunas a preencher
            </span>
            <span className="text-[10px] text-amber-700/70 dark:text-amber-300/70">(não bloqueiam)</span>
          </div>
          <ul className="space-y-1 mt-2 text-sm text-amber-900 dark:text-amber-100">
            {gate.gaps.map((g, i) => (
              <li key={i}>• {g}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Saída esperada */}
      {gate.expected_outputs.length > 0 && (
        <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-4">
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-slate-400 font-semibold">
            Saída esperada
          </span>
          <ul className="space-y-1 mt-2 text-sm text-gray-700 dark:text-slate-200">
            {gate.expected_outputs.map((o, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="text-emerald-500 mt-0.5">✓</span>
                <span className="leading-snug">{o}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Agente da etapa */}
      {agents.length > 0 && (
        <div className="rounded-2xl bg-sky-50 dark:bg-sky-500/10 border border-sky-200 dark:border-sky-500/30 p-4">
          <div className="flex items-center gap-2 mb-1">
            <Bot className="w-4 h-4 text-sky-600 dark:text-sky-400" />
            <span className="text-xs uppercase tracking-wide text-sky-700 dark:text-sky-300 font-semibold">
              Agente da etapa
            </span>
          </div>
          <p className="text-sm text-sky-900 dark:text-sky-100">
            {agents.join(', ')}
          </p>
        </div>
      )}
    </div>
  );
}
