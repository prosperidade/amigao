/**
 * SaidasTab — Artefatos produzidos por etapa (CAM3WS-006 / Sprint J).
 *
 * Lista os StageOutputs do processo via `GET /processes/{id}/artifacts`.
 * Agrupa por macroetapa e mostra título, tipo, fonte (humano/agente) e
 * status de validação humana. Corresponde ao item "Saídas" do menu lateral
 * da sócia (Camada 3 — Workspace).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { PackageCheck, CheckCircle2, Clock, User, Bot } from 'lucide-react';
import { api } from '@/lib/api';
import { MACROETAPA_LABELS } from './quadro-types';

interface StageOutput {
  id: number;
  process_id: number;
  macroetapa: string;
  output_type: string;
  title: string;
  content: string | null;
  produced_by_agent: string | null;
  produced_by_user_id: number | null;
  needs_human_validation: boolean;
  validated_at: string | null;
  validated_by_user_id: number | null;
  created_at: string | null;
}

interface Props {
  processId: number;
  viewingStage?: string | null;   // quando stepper filtrar uma etapa
}

export default function SaidasTab({ processId, viewingStage }: Props) {
  const queryClient = useQueryClient();
  const { data: outputs = [], isLoading } = useQuery({
    queryKey: ['process-artifacts', processId, viewingStage ?? 'all'],
    queryFn: () => {
      const url = viewingStage
        ? `/processes/${processId}/artifacts?macroetapa=${viewingStage}`
        : `/processes/${processId}/artifacts`;
      return api.get<StageOutput[]>(url).then(r => r.data);
    },
    enabled: !!processId,
  });

  // CAM3WS-006 (Sprint K) — validar artefato pendente via POST /artifacts/{id}/validate
  const validateMutation = useMutation({
    mutationFn: (artifactId: number) =>
      api.post(`/processes/${processId}/artifacts/${artifactId}/validate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['process-artifacts', processId] });
      toast.success('Saída validada');
    },
    onError: () => toast.error('Falha ao validar saída'),
  });

  if (isLoading) {
    return <div className="animate-pulse space-y-2">{[1, 2, 3].map(i => <div key={i} className="h-16 rounded-xl bg-gray-100 dark:bg-white/5" />)}</div>;
  }
  if (outputs.length === 0) {
    return (
      <div className="text-center py-10 text-gray-500 dark:text-slate-400">
        <PackageCheck className="w-8 h-8 mx-auto mb-2 opacity-40" />
        <p className="text-sm">
          {viewingStage
            ? `Nenhuma saída registrada para ${MACROETAPA_LABELS[viewingStage] ?? viewingStage}.`
            : 'Nenhuma saída registrada. Artefatos produzidos por etapa aparecem aqui.'}
        </p>
      </div>
    );
  }

  // Agrupa por macroetapa na ordem em que aparecem
  const grouped = outputs.reduce<Record<string, StageOutput[]>>((acc, o) => {
    (acc[o.macroetapa] ??= []).push(o);
    return acc;
  }, {});

  return (
    <div className="space-y-5">
      {Object.entries(grouped).map(([etapa, items]) => (
        <section key={etapa}>
          <h3 className="text-xs uppercase tracking-wide text-gray-500 dark:text-slate-400 font-semibold mb-2">
            {MACROETAPA_LABELS[etapa] ?? etapa}
            <span className="ml-2 text-[10px] font-normal text-gray-400">({items.length})</span>
          </h3>
          <ul className="space-y-2">
            {items.map(o => {
              const validated = !!o.validated_at;
              const pendingValidation = o.needs_human_validation && !validated;
              return (
                <li
                  key={o.id}
                  className={`p-3 rounded-xl border flex items-start gap-3 ${
                    pendingValidation
                      ? 'border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/5'
                      : 'border-gray-100 dark:border-white/10 bg-white dark:bg-white/5'
                  }`}
                >
                  <div className="mt-0.5 shrink-0">
                    {o.produced_by_agent ? (
                      <Bot className="w-4 h-4 text-violet-500" />
                    ) : (
                      <User className="w-4 h-4 text-emerald-500" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm text-gray-900 dark:text-white truncate">{o.title}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-700 dark:bg-white/10 dark:text-slate-300">{o.output_type}</span>
                      {pendingValidation && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">
                          <Clock className="w-2.5 h-2.5 inline" /> Aguardando validação
                        </span>
                      )}
                      {validated && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                          <CheckCircle2 className="w-2.5 h-2.5 inline" /> Validado
                        </span>
                      )}
                    </div>
                    {o.content && (
                      <p className="text-xs text-gray-600 dark:text-slate-300 mt-1 line-clamp-2 whitespace-pre-line">{o.content}</p>
                    )}
                    <p className="text-[10px] text-gray-400 mt-1">
                      {o.produced_by_agent ? `Agente: ${o.produced_by_agent}` : 'Consultor'}
                      {o.created_at && ` · ${new Date(o.created_at).toLocaleDateString('pt-BR')}`}
                    </p>
                  </div>
                  {pendingValidation && (
                    <button
                      onClick={() => validateMutation.mutate(o.id)}
                      disabled={validateMutation.isPending}
                      className="shrink-0 text-xs px-2.5 py-1 rounded-md bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-white font-medium"
                    >
                      {validateMutation.isPending && validateMutation.variables === o.id ? '...' : 'Validar'}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
