/**
 * WorkflowTimeline — Trilha regulatória do processo (Sprint 3)
 * Visualiza etapas, etapa atual, próximas e aplica o template de workflow.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { CheckCircle2, Circle, Clock, Play, Loader2, AlertCircle } from 'lucide-react';

interface WorkflowTimelineProps {
  processId: number;
}

const TASK_TYPE_LABELS: Record<string, string> = {
  documentacao: '📄 Documentação',
  campo: '🌿 Campo',
  analise: '🔍 Análise',
  elaboracao: '✏️ Elaboração',
  protocolo: '📮 Protocolo',
  acompanhamento: '👁 Acompanhamento',
  entrega: '📦 Entrega',
};

const STATUS_CONFIG: Record<string, { label: string; dotCls: string; textCls: string }> = {
  backlog:       { label: 'Pendente',     dotCls: 'bg-gray-400',    textCls: 'text-gray-500 dark:text-slate-400' },
  a_fazer:       { label: 'A Fazer',      dotCls: 'bg-blue-400',    textCls: 'text-blue-600 dark:text-blue-400' },
  em_progresso:  { label: 'Em Progresso', dotCls: 'bg-yellow-400 animate-pulse', textCls: 'text-yellow-600 dark:text-yellow-400' },
  aguardando:    { label: 'Aguardando',   dotCls: 'bg-orange-400',  textCls: 'text-orange-600 dark:text-orange-400' },
  revisao:       { label: 'Revisão',      dotCls: 'bg-purple-400',  textCls: 'text-purple-600 dark:text-purple-400' },
  concluida:     { label: 'Concluída',    dotCls: 'bg-emerald-400', textCls: 'text-emerald-600 dark:text-emerald-400' },
  cancelada:     { label: 'Cancelada',    dotCls: 'bg-red-400',     textCls: 'text-red-600 dark:text-red-400' },
};

export default function WorkflowTimeline({ processId }: WorkflowTimelineProps) {
  const queryClient = useQueryClient();

  const { data: ws, isLoading } = useQuery({
    queryKey: ['workflow-status', processId],
    queryFn: async () => {
      const res = await api.get(`/processes/${processId}/workflow-status`);
      return res.data;
    },
  });

  const applyMutation = useMutation({
    mutationFn: () => api.post(`/processes/${processId}/apply-workflow`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow-status', processId] });
      queryClient.invalidateQueries({ queryKey: ['tasks', processId] });
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-28 rounded-2xl bg-gray-100 dark:bg-white/5" />
        <div className="h-16 rounded-xl bg-gray-100 dark:bg-white/5" />
        <div className="h-16 rounded-xl bg-gray-100 dark:bg-white/5" />
        <div className="h-16 rounded-xl bg-gray-100 dark:bg-white/5" />
      </div>
    );
  }

  if (!ws) return null;

  const allSteps: any[] = ws.all_steps ?? [];
  const hasTemplate = !!ws.template_name;
  const isApplied = ws.is_applied;

  return (
    <div className="space-y-5">

      {/* Header / status geral */}
      <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-1">Trilha Regulatória</p>
            <p className="text-base font-semibold text-gray-900 dark:text-white">
              {ws.template_name ?? (ws.demand_type ? `Tipo: ${ws.demand_type}` : 'Sem trilha definida')}
            </p>
            {ws.demand_type && (
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">Tipo de demanda: {ws.demand_type}</p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{ws.completion_pct}%</p>
              <p className="text-xs text-gray-400 dark:text-slate-500">{ws.completed_steps}/{ws.total_steps} etapas</p>
            </div>
            <div className="w-12 h-12 rounded-full border-4 border-gray-100 dark:border-white/10 flex items-center justify-center relative">
              <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor" strokeWidth="3.5"
                  className="text-gray-100 dark:text-white/5" />
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor" strokeWidth="3.5"
                  strokeDasharray={`${ws.completion_pct} ${100 - ws.completion_pct}`}
                  strokeLinecap="round"
                  className="text-emerald-500 transition-all duration-500" />
              </svg>
            </div>
          </div>
        </div>

        {ws.total_steps > 0 && (
          <div className="mt-4 w-full bg-gray-100 dark:bg-white/5 rounded-full h-1.5">
            <div
              className="bg-emerald-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${ws.completion_pct}%` }}
            />
          </div>
        )}

        {hasTemplate && !isApplied && (
          <button
            onClick={() => applyMutation.mutate()}
            disabled={applyMutation.isPending}
            className="mt-4 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-white font-medium text-sm transition-all"
          >
            {applyMutation.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Play className="w-4 h-4" />
            }
            Aplicar trilha {ws.demand_type?.toUpperCase()}
          </button>
        )}

        {applyMutation.isError && (
          <div className="mt-3 flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
            <AlertCircle className="w-4 h-4" />
            Erro ao aplicar trilha. Verifique se o processo tem tipo de demanda definido.
          </div>
        )}

        {applyMutation.isSuccess && (
          <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">
            ✓ Trilha aplicada! As tarefas foram criadas na aba Tarefas.
          </p>
        )}
      </div>

      {/* Lista de etapas */}
      {allSteps.length === 0 ? (
        <div className="rounded-2xl bg-gray-50 dark:bg-white/5 border border-dashed border-gray-200 dark:border-white/10 p-10 text-center">
          <p className="text-gray-400 dark:text-slate-500 text-sm">
            {hasTemplate
              ? 'Clique em "Aplicar trilha" para criar as etapas do processo.'
              : 'Nenhuma trilha regulatória disponível para este tipo de demanda.'}
          </p>
        </div>
      ) : (
        <div className="relative pl-6 border-l-2 border-gray-100 dark:border-white/10 space-y-0">
          {allSteps.map((step: any, idx: number) => {
            const isDone = step.task_status === 'concluida';
            const isActive = step.task_status && step.task_status !== 'concluida' && step.task_status !== 'cancelada';
            const statusCfg = step.task_status ? (STATUS_CONFIG[step.task_status] ?? STATUS_CONFIG.backlog) : STATUS_CONFIG.backlog;
            const isLast = idx === allSteps.length - 1;

            return (
              <div key={step.order} className={`relative pb-5 ${isLast ? 'pb-0' : ''}`}>
                {/* Dot */}
                <div className="absolute -left-[31px] bg-white dark:bg-slate-950 p-0.5">
                  {isDone
                    ? <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    : isActive
                      ? <div className="w-5 h-5 rounded-full border-2 border-yellow-400 dark:border-yellow-400 flex items-center justify-center">
                          <div className="w-2 h-2 rounded-full bg-yellow-500 dark:bg-yellow-400 animate-pulse" />
                        </div>
                      : <Circle className="w-5 h-5 text-gray-300 dark:text-slate-600" />
                  }
                </div>

                {/* Card */}
                <div className={`ml-2 rounded-xl border p-4 transition-all ${
                  isDone
                    ? 'bg-emerald-50 dark:bg-emerald-500/5 border-emerald-100 dark:border-emerald-500/15'
                    : isActive
                      ? 'bg-yellow-50 dark:bg-yellow-500/5 border-yellow-200 dark:border-yellow-500/20'
                      : 'bg-gray-50 dark:bg-white/3 border-gray-100 dark:border-white/5'
                }`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-gray-400 dark:text-slate-500">#{step.order}</span>
                        {step.task_type && (
                          <span className="text-xs text-gray-500 dark:text-slate-500">
                            {TASK_TYPE_LABELS[step.task_type] ?? step.task_type}
                          </span>
                        )}
                      </div>
                      <p className={`text-sm font-semibold ${isDone ? 'text-gray-400 dark:text-slate-400 line-through' : 'text-gray-800 dark:text-white'}`}>
                        {step.title}
                      </p>
                      {step.description && !isDone && (
                        <p className="text-xs text-gray-500 dark:text-slate-500 mt-1 leading-relaxed">
                          {step.description.split('\n')[0]}
                        </p>
                      )}
                    </div>

                    <div className="flex flex-col items-end gap-1 shrink-0">
                      {step.task_status && (
                        <span className={`text-xs font-medium ${statusCfg.textCls}`}>
                          {statusCfg.label}
                        </span>
                      )}
                      {step.estimated_days > 0 && !isDone && (
                        <span className="flex items-center gap-1 text-xs text-gray-400 dark:text-slate-500">
                          <Clock className="w-3 h-3" /> ~{step.estimated_days}d
                        </span>
                      )}
                      {step.due_date && (
                        <span className="text-xs text-gray-400 dark:text-slate-500">
                          {new Date(step.due_date).toLocaleDateString('pt-BR')}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
