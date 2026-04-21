import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  X, CheckSquare, Square, FileText, Clock, Sparkles,
  AlertTriangle, Target, ArrowUpRight, TrendingUp, Scale,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { KanbanProcessCard, MacroetapaStatusResponse } from './quadro-types';
import { URGENCY_BADGES, DEMAND_TYPE_LABELS, MACROETAPA_STATE_BADGE } from './quadro-types';
import MacroetapaStepper from './MacroetapaStepper';
// CAM3PR-001 (Sprint N): side panel virou preview read-only.
// Upload de documento e toggle de ações vivem APENAS no Workspace (/processes/:id).

interface Props {
  card: KanbanProcessCard;
  onClose: () => void;
}

type TabId = 'preview' | 'checklist' | 'documents' | 'timeline';

interface ProcessDetail {
  id: number;
  title: string;
  description: string | null;
  initial_summary: string | null;
  initial_diagnosis: string | null;
  ai_summary: string | null;
  intake_notes: string | null;
  entry_type: string | null;
  demand_type: string | null;
  urgency: string | null;
  priority: string | null;
}

// QA-013 — resumo da última decisão registrada (Sprint E)
interface DecisionSummary {
  id: number;
  macroetapa: string;
  decision_type: string;
  decision_type_label: string;
  decision_text: string;
  status: string;
  status_label: string;
  decided_by_user_name: string | null;
  decided_at: string | null;
  created_at: string;
}

interface TimelineEntry {
  id: number;
  action: string;
  details?: string;
  old_value?: string;
  new_value?: string;
  created_at: string;
}

interface ProcessDocument {
  id: number;
  filename: string;
  file_size_bytes: number;
  created_at: string;
}

export default function MacroetapaSidePanel({ card, onClose }: Props) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabId>('preview');

  const { data: macroetapaStatus } = useQuery({
    queryKey: ['macroetapa-status', card.id],
    queryFn: () =>
      api.get<MacroetapaStatusResponse>(`/processes/${card.id}/macroetapa/status`).then(r => r.data),
  });

  const { data: processDetail } = useQuery({
    queryKey: ['process-detail', card.id],
    queryFn: () => api.get<ProcessDetail>(`/processes/${card.id}`).then(r => r.data),
    enabled: activeTab === 'preview',
  });

  // QA-013 — última decisão registrada (Sprint E)
  const { data: latestDecision } = useQuery({
    queryKey: ['decision-latest', card.id],
    queryFn: () =>
      api.get<DecisionSummary | null>(`/processes/${card.id}/decisions/latest`).then(r => r.data),
    enabled: activeTab === 'preview',
  });

  const { data: timeline } = useQuery({
    queryKey: ['timeline', card.id],
    queryFn: () => api.get<TimelineEntry[]>(`/processes/${card.id}/timeline`).then(r => r.data),
    enabled: activeTab === 'timeline',
  });

  const { data: documents } = useQuery({
    queryKey: ['documents', card.id],
    queryFn: () => api.get<ProcessDocument[]>(`/documents/?process_id=${card.id}`).then(r => r.data),
    enabled: activeTab === 'documents',
  });

  const currentStep = macroetapaStatus?.steps.find(s => s.status === 'active');

  const tabs: { id: TabId; label: string }[] = [
    { id: 'preview', label: 'Visão geral' },
    { id: 'checklist', label: 'Checklist' },
    { id: 'documents', label: 'Documentos' },
    { id: 'timeline', label: 'Timeline' },
  ];

  const urgencyKey = card.urgency ?? card.priority ?? '';
  const urgencyLabel = urgencyKey === 'critica' ? 'Urgente'
    : urgencyKey === 'alta' ? 'Alta'
    : urgencyKey === 'media' ? 'Média'
    : urgencyKey === 'baixa' ? 'Baixa' : null;
  const demandLabel = card.demand_type ? (DEMAND_TYPE_LABELS[card.demand_type] ?? card.demand_type) : null;
  const actionsDone = currentStep?.actions.filter(a => a.completed).length ?? 0;
  const actionsTotal = currentStep?.actions.length ?? 0;
  const stateBadge = card.macroetapa_state ? MACROETAPA_STATE_BADGE[card.macroetapa_state] : null;

  const openWorkspace = () => {
    onClose();
    navigate(`/processes/${card.id}`);
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white dark:bg-zinc-900 h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="p-5 border-b border-gray-100 dark:border-zinc-800">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                {card.client_name ?? card.title}
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                {card.property_name ?? ''} {card.demand_type ? `• ${card.demand_type}` : ''}
              </p>
              {card.macroetapa_label && (
                <span className="inline-block mt-2 text-xs px-2 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                  {card.macroetapa_label}
                </span>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-2 -mr-2 text-gray-400 hover:text-gray-900 dark:hover:text-white rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Stepper */}
        {macroetapaStatus && (
          <div className="px-5 py-4 border-b border-gray-100 dark:border-zinc-800 max-h-56 overflow-y-auto">
            <MacroetapaStepper steps={macroetapaStatus.steps} compact />
          </div>
        )}

        {/* Tabs */}
        <div className="px-5 border-b border-gray-100 dark:border-zinc-800 flex gap-6 text-sm font-medium text-gray-500 dark:text-gray-400">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-3 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* Preview tab — Visão geral (Regente Cam3: preview antes de abrir workspace) */}
          {activeTab === 'preview' && (
            <div className="space-y-5">
              {/* Barra de progresso da etapa ativa */}
              {currentStep && (
                <div>
                  <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1.5">
                    <span>Etapa ativa · {actionsDone}/{actionsTotal} ações concluídas</span>
                    {stateBadge && (
                      <span className={`px-2 py-0.5 rounded-full font-medium ${stateBadge.cls}`}>
                        {stateBadge.label}
                      </span>
                    )}
                  </div>
                  <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-1.5">
                    <div
                      className="bg-emerald-500 h-1.5 rounded-full transition-all"
                      style={{ width: `${Math.min(card.macroetapa_completion_pct, 100)}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Tags rápidas */}
              <div className="flex flex-wrap gap-1.5">
                {demandLabel && (
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                    {demandLabel}
                  </span>
                )}
                {urgencyLabel && URGENCY_BADGES[urgencyKey] && (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${URGENCY_BADGES[urgencyKey]}`}>
                    Urgência: {urgencyLabel}
                  </span>
                )}
              </div>

              {/* Resumo do caso */}
              <div className="space-y-3">
                {(processDetail?.ai_summary ?? processDetail?.initial_diagnosis) && (
                  <div>
                    <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider font-semibold text-gray-500 dark:text-gray-400 mb-1">
                      <TrendingUp className="w-3.5 h-3.5" />
                      Problema percebido
                    </div>
                    <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
                      {processDetail?.ai_summary ?? processDetail?.initial_diagnosis}
                    </p>
                  </div>
                )}
                {processDetail?.initial_summary && (
                  <div>
                    <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider font-semibold text-gray-500 dark:text-gray-400 mb-1">
                      <Target className="w-3.5 h-3.5" />
                      Objetivo real
                    </div>
                    <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
                      {processDetail.initial_summary}
                    </p>
                  </div>
                )}
                {!processDetail?.ai_summary && !processDetail?.initial_diagnosis && !processDetail?.initial_summary && (
                  <p className="text-xs text-gray-400 italic">
                    Resumo IA ainda não gerado para este caso.
                  </p>
                )}
              </div>

              {/* Lacunas detectadas (usa blockers da macroetapa) */}
              {card.blockers.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider font-semibold text-gray-500 dark:text-gray-400 mb-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    Lacunas detectadas
                  </div>
                  <ul className="space-y-1.5">
                    {card.blockers.map((blocker, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
                        <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                        <span>{blocker}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Próxima ação sugerida */}
              {card.next_action && (
                <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800/50 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider font-semibold text-emerald-700 dark:text-emerald-300 mb-1">
                    <ArrowUpRight className="w-3.5 h-3.5" />
                    Próxima ação sugerida
                  </div>
                  <p className="text-sm text-emerald-900 dark:text-emerald-100 leading-relaxed">
                    {card.next_action}
                  </p>
                </div>
              )}

              {/* QA-013 — Última decisão registrada (Sprint E) */}
              {latestDecision && (
                <div className="border border-emerald-200 dark:border-emerald-500/30 rounded-lg p-3 bg-emerald-50/50 dark:bg-emerald-500/5">
                  <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider font-semibold text-emerald-700 dark:text-emerald-300 mb-1.5">
                    <Scale className="w-3.5 h-3.5" />
                    Última decisão
                  </div>
                  <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                    <span className="text-[11px] px-1.5 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                      {latestDecision.decision_type_label}
                    </span>
                    <span className="text-[11px] text-emerald-700 dark:text-emerald-400">
                      · {latestDecision.status_label}
                    </span>
                  </div>
                  <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed line-clamp-3">
                    {latestDecision.decision_text}
                  </p>
                  <div className="flex items-center gap-3 mt-1.5 text-[11px] text-gray-500">
                    {latestDecision.decided_by_user_name && (
                      <span>{latestDecision.decided_by_user_name}</span>
                    )}
                    <span>
                      {new Date(latestDecision.decided_at ?? latestDecision.created_at).toLocaleDateString('pt-BR')}
                    </span>
                  </div>
                </div>
              )}

              {/* Preview do que existe no workspace completo */}
              <div className="border border-gray-200 dark:border-zinc-700 rounded-lg p-3 bg-gray-50 dark:bg-zinc-800/50">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  <Sparkles className="w-3.5 h-3.5" />
                  No workspace completo você verá
                </div>
                <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1 pl-5 list-disc">
                  <li>Checklist detalhado de ações da etapa</li>
                  <li>Documentos anexados e pendentes</li>
                  <li>Timeline completa de eventos</li>
                  <li>Agentes IA por etapa com apoio em tempo real</li>
                  <li>Botão para avançar para a próxima macroetapa</li>
                </ul>
              </div>

              {/* CTA grande — Abrir Workspace */}
              <button
                onClick={openWorkspace}
                className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-3.5 rounded-xl text-sm font-semibold transition-colors shadow-lg shadow-emerald-500/20"
              >
                <ArrowUpRight className="w-4 h-4" />
                Abrir workspace do caso
              </button>
              <p className="text-xs text-gray-500 text-center -mt-2">
                Acesse a página completa para continuar a execução desta etapa com apoio da IA
              </p>
            </div>
          )}

          {/* Checklist tab — CAM3PR-001 (Sprint N): read-only no side panel.
              Toggle de ações só acontece no Workspace. Side panel é preview. */}
          {activeTab === 'checklist' && currentStep && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                  Ações da Etapa
                </h3>
                <span className="text-xs text-gray-500">
                  {currentStep.actions.filter(a => a.completed).length}/{currentStep.actions.length}
                </span>
              </div>

              <div className="space-y-1.5">
                {currentStep.actions.map(action => (
                  <div
                    key={action.id}
                    className="flex items-start gap-3 p-3 rounded-lg text-left w-full"
                  >
                    {action.completed ? (
                      <CheckSquare className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                    ) : (
                      <Square className="w-5 h-5 text-gray-300 dark:text-zinc-600 shrink-0 mt-0.5" />
                    )}
                    <span
                      className={`text-sm ${
                        action.completed
                          ? 'text-gray-400 line-through'
                          : 'text-gray-800 dark:text-gray-200'
                      }`}
                    >
                      {action.label}
                    </span>
                  </div>
                ))}
              </div>

              <button
                type="button"
                onClick={openWorkspace}
                className="w-full flex items-center justify-center gap-2 border border-emerald-200 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors"
              >
                <ArrowUpRight className="w-4 h-4" />
                Concluir ações e rodar IA no Workspace
              </button>
            </div>
          )}

          {activeTab === 'checklist' && !currentStep && (
            <p className="text-sm text-gray-500 text-center py-8">
              Nenhuma etapa ativa. Inicialize as macroetapas do processo.
            </p>
          )}

          {/* Documents tab — CAM3PR-001 (Sprint N): read-only no side panel.
              Upload acontece só no Workspace (Cam3 princípio arquitetural). */}
          {activeTab === 'documents' && (
            <div className="space-y-4">
              {documents?.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-4">Nenhum documento anexado.</p>
              ) : (
                documents?.map(doc => (
                  <div
                    key={doc.id}
                    className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-zinc-800/50 rounded-lg border border-gray-100 dark:border-zinc-800"
                  >
                    <FileText className="w-4 h-4 text-gray-400 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {doc.filename}
                      </p>
                      <p className="text-xs text-gray-500">
                        {(doc.file_size_bytes / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                ))
              )}
              <button
                type="button"
                onClick={openWorkspace}
                className="w-full flex items-center justify-center gap-2 border border-emerald-200 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors"
              >
                <ArrowUpRight className="w-4 h-4" />
                Anexar documento no Workspace
              </button>
            </div>
          )}

          {/* Timeline tab */}
          {activeTab === 'timeline' && (
            <div className="relative pl-6 border-l-2 border-gray-100 dark:border-zinc-800 space-y-5 py-2">
              {timeline?.length === 0 && (
                <p className="text-sm text-gray-500 text-center">Nenhum evento registrado.</p>
              )}
              {timeline?.map(log => (
                <div key={log.id} className="relative">
                  <div className="absolute -left-[31px] bg-white dark:bg-zinc-900 p-1">
                    <div className="w-3 h-3 bg-primary rounded-full ring-4 ring-white dark:ring-zinc-900" />
                  </div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">
                    {log.action === 'status_changed'
                      ? 'Mudança de Status'
                      : log.action === 'macroetapa_changed'
                        ? 'Avanço de Macroetapa'
                        : log.details ?? log.action}
                  </p>
                  {log.old_value && log.new_value && (
                    <p className="text-xs text-gray-500 mt-0.5">
                      {log.old_value} → <span className="text-primary font-medium">{log.new_value}</span>
                    </p>
                  )}
                  <span className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(log.created_at).toLocaleString('pt-BR')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

