/**
 * ProcessDetail — Workspace do Caso (Regente Cam3 CAM3WS-001)
 *
 * Layout 6-áreas:
 *  1. Cabeçalho do caso (ProcessHeader)
 *  2. Barra horizontal das 7 etapas (HorizontalStepper inline)
 *  3. Menu lateral interno esquerdo (8 itens)
 *  4. Área central de trabalho (tab content)
 *  5. Painel lateral direito (WorkspaceRightPanel — Estado/Objetivo/Validação/Travas/Saída/Agente)
 *  6. Rodapé / timeline (WorkflowTimeline)
 */
import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { AlertCircle, Zap, X } from 'lucide-react';

import { Process, TABS } from './ProcessDetailTypes';
import { MACROETAPA_LABELS } from './quadro-types';
import ProcessHeader from './ProcessHeader';
import DiagnosisTab from './DiagnosisTab';
import TasksTab from './TasksTab';
import DocumentsTab from './DocumentsTab';
import TimelineTab from './TimelineTab';
import ProcessDossier from './ProcessDossier';
import WorkflowTimeline from './WorkflowTimeline';
import ProcessCommercial from './ProcessCommercial';
import WorkspaceRightPanel from './WorkspaceRightPanel';
import DecisionsTab from './DecisionsTab';
import AIPanel from '@/pages/AI/AIPanel';

type TabKey = 'diagnosis' | 'dossier' | 'workflow' | 'decisions' | 'commercial' | 'tasks' | 'documents' | 'timeline' | 'ai';

const STAGE_ORDER = [
  'entrada_demanda',
  'diagnostico_preliminar',
  'coleta_documental',
  'diagnostico_tecnico',
  'caminho_regulatorio',
  'orcamento_negociacao',
  'contrato_formalizacao',
] as const;

export default function ProcessDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const processId = parseInt(id ?? '0', 10);

  const [activeTab, setActiveTab] = useState<TabKey>('diagnosis');
  const fromIntake = location.state?.fromIntake;
  const [intakeBanner, setIntakeBanner] = useState(fromIntake ?? false);

  // ── Queries ──────────────────────────────────────────────────────────────────
  const { data: process, isLoading, error } = useQuery({
    queryKey: ['process', processId],
    queryFn: async () => {
      const res = await api.get(`/processes/${processId}`);
      return res.data as Process;
    },
    enabled: !!processId,
  });

  const { data: client } = useQuery({
    queryKey: ['client', process?.client_id],
    queryFn: async () => {
      const res = await api.get(`/clients/${process!.client_id}`);
      return res.data as { full_name: string };
    },
    enabled: !!process?.client_id,
  });

  // CAM3WS-005 — validar action via painel direito
  const validateActionMutation = useMutation({
    mutationFn: ({ etapa, actionId }: { etapa: string; actionId: string }) =>
      api.post(`/processes/${processId}/macroetapa/${etapa}/actions/validate`, { action_id: actionId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['process-macroetapa-status', processId] });
      queryClient.invalidateQueries({ queryKey: ['process-can-advance', processId] });
      toast.success('Ação validada');
    },
    onError: () => toast.error('Falha ao validar ação'),
  });

  // ── Loading / Error ───────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto space-y-4 animate-pulse">
        <div className="h-10 rounded-xl bg-gray-100 dark:bg-white/5 w-48" />
        <div className="h-32 rounded-2xl bg-gray-100 dark:bg-white/5" />
        <div className="h-12 rounded-xl bg-gray-100 dark:bg-white/5" />
        <div className="h-64 rounded-2xl bg-gray-100 dark:bg-white/5" />
      </div>
    );
  }

  if (error || !process) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertCircle className="w-10 h-10 text-red-400" />
        <p className="text-gray-500 dark:text-slate-400">{`Processo n\u00e3o encontrado.`}</p>
        <button onClick={() => navigate('/processes')} className="text-sm text-emerald-600 dark:text-emerald-400 underline">
          Voltar para processos
        </button>
      </div>
    );
  }

  const currentStage = process.macroetapa ?? 'entrada_demanda';
  const currentIndex = STAGE_ORDER.indexOf(currentStage as typeof STAGE_ORDER[number]);

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-7xl mx-auto space-y-4">

      {/* Banner pós-intake */}
      {intakeBanner && (
        <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center shrink-0">
              <Zap className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">Caso criado com sucesso!</p>
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">{`O diagn\u00f3stico inicial e checklist foram gerados automaticamente.`}</p>
            </div>
          </div>
          <button onClick={() => setIntakeBanner(false)} className="p-1.5 rounded-lg text-gray-400 dark:text-slate-500 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/5 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Área 1 — Cabeçalho do caso */}
      <ProcessHeader process={process} client={client} onBack={() => navigate('/processes')} />

      {/* Área 2 — Barra horizontal das 7 etapas (CAM3WS-008) */}
      <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 px-4 py-3">
        <div className="flex items-center gap-1 overflow-x-auto">
          {STAGE_ORDER.map((stage, i) => {
            const label = MACROETAPA_LABELS[stage];
            const isCurrent = stage === currentStage;
            const isDone = i < currentIndex;
            return (
              <div key={stage} className="flex items-center gap-1 shrink-0">
                <div
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs whitespace-nowrap ${
                    isCurrent
                      ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-semibold'
                      : isDone
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-gray-400 dark:text-slate-500'
                  }`}
                >
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                    isCurrent ? 'bg-emerald-500 text-white' : isDone ? 'bg-emerald-500 text-white' : 'bg-gray-200 dark:bg-zinc-700'
                  }`}>
                    {isDone ? '✓' : i + 1}
                  </span>
                  {label}
                </div>
                {i < STAGE_ORDER.length - 1 && (
                  <div className={`w-3 h-px ${i < currentIndex ? 'bg-emerald-500' : 'bg-gray-200 dark:bg-zinc-700'}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Layout 3 colunas: menu lateral + área central + painel direito */}
      <div className="grid grid-cols-1 lg:grid-cols-[200px_1fr_320px] gap-4">

        {/* Área 3 — Menu lateral interno (vertical) */}
        <aside className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-2 h-fit lg:sticky lg:top-4">
          <nav className="flex flex-row lg:flex-col gap-1 overflow-x-auto lg:overflow-x-visible">
            {TABS.map(tab => {
              const Icon = tab.icon;
              const active = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key as TabKey)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap shrink-0 ${
                    active
                      ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                      : 'text-gray-600 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-white/5 hover:text-gray-900 dark:hover:text-white'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Área 4 — Área central de trabalho */}
        <main className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5 min-w-0">
          {activeTab === 'diagnosis' && <DiagnosisTab process={process} />}
          {activeTab === 'dossier' && <ProcessDossier processId={processId} />}
          {activeTab === 'workflow' && <WorkflowTimeline processId={processId} />}
          {activeTab === 'decisions' && <DecisionsTab processId={processId} currentMacroetapa={currentStage} />}
          {activeTab === 'commercial' && <ProcessCommercial processId={processId} />}
          {activeTab === 'tasks' && <TasksTab processId={processId} />}
          {activeTab === 'documents' && <DocumentsTab processId={processId} />}
          {activeTab === 'timeline' && <TimelineTab processId={processId} />}
          {activeTab === 'ai' && (
            <AIPanel
              processId={processId}
              processDemandType={process?.demand_type}
              processDescription={process?.description}
            />
          )}
        </main>

        {/* Área 5 — Painel lateral direito (WorkspaceRightPanel) */}
        <aside className="lg:sticky lg:top-4 h-fit">
          <WorkspaceRightPanel
            processId={processId}
            onValidateAction={(etapa, actionId) =>
              validateActionMutation.mutate({ etapa, actionId })
            }
          />
        </aside>
      </div>

      {/* Área 6 — Rodapé / timeline */}
      <details className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-4 group">
        <summary className="cursor-pointer flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-slate-300">
          <span className="text-lg">📅</span>
          Timeline / Histórico de eventos
        </summary>
        <div className="mt-4">
          <WorkflowTimeline processId={processId} />
        </div>
      </details>

    </div>
  );
}
