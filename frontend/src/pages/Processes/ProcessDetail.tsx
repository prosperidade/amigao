/**
 * ProcessDetail — Detalhe de um processo ambiental
 * Sprint 2 — aba Documentos com checklist integrado e upload categorizado
 */
import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { AlertCircle, Zap, X } from 'lucide-react';

import { Process, TABS } from './ProcessDetailTypes';
import ProcessHeader from './ProcessHeader';
import DiagnosisTab from './DiagnosisTab';
import TasksTab from './TasksTab';
import DocumentsTab from './DocumentsTab';
import TimelineTab from './TimelineTab';
import ProcessDossier from './ProcessDossier';
import WorkflowTimeline from './WorkflowTimeline';
import ProcessCommercial from './ProcessCommercial';
import AIPanel from '@/pages/AI/AIPanel';

type TabKey = 'diagnosis' | 'dossier' | 'workflow' | 'commercial' | 'tasks' | 'documents' | 'timeline' | 'ai';

export default function ProcessDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
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

  // ── Loading / Error ───────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto space-y-4 animate-pulse">
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

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-5xl mx-auto space-y-5">

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

      <ProcessHeader process={process} client={client} onBack={() => navigate('/processes')} />

      {/* Tabs */}
      <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 overflow-hidden">
        <div className="border-b border-gray-100 dark:border-white/10 flex gap-0 overflow-x-auto">
          {TABS.map(tab => {
            const Icon = tab.icon;
            const active = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as TabKey)}
                className={`flex items-center gap-1.5 px-4 py-3.5 text-sm font-medium border-b-2 transition-all -mb-px whitespace-nowrap shrink-0 ${
                  active
                    ? 'border-emerald-500 text-emerald-700 dark:text-emerald-400 bg-emerald-50/50 dark:bg-emerald-500/5'
                    : 'border-transparent text-gray-500 dark:text-slate-400 hover:text-gray-800 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-white/5'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        <div className="p-5">
          {activeTab === 'diagnosis' && <DiagnosisTab process={process} />}
          {activeTab === 'dossier' && <ProcessDossier processId={processId} />}
          {activeTab === 'workflow' && <WorkflowTimeline processId={processId} />}
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
        </div>
      </div>

    </div>
  );
}
