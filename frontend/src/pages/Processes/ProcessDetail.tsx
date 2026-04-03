/**
 * ProcessDetail — Detalhe de um processo ambiental
 * Sprint 2 — aba Documentos com checklist integrado e upload categorizado
 */
import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  ArrowLeft, FileText, Clock, CheckCircle2, Circle, AlertCircle,
  Download, Plus, X, Zap, Building2, User, Stethoscope,
  LayoutGrid, GitBranch, Briefcase, ListChecks, FolderOpen,
  CalendarDays, Bot,
} from 'lucide-react';

import ProcessChecklist from './ProcessChecklist';
import DocumentUploadZone from '@/components/DocumentUploadZone';
import ProcessDossier from './ProcessDossier';
import WorkflowTimeline from './WorkflowTimeline';
import ProcessCommercial from './ProcessCommercial';
import AIPanel from '@/pages/AI/AIPanel';

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface Process {
  id: number;
  title: string;
  description: string;
  client_id: number;
  property_id: number | null;
  status: string;
  priority: string;
  urgency: string;
  process_type: string;
  demand_type: string | null;
  intake_source: string | null;
  initial_diagnosis: string | null;
  suggested_checklist_template: string | null;
  intake_notes: string | null;
  destination_agency: string | null;
  external_protocol_number: string | null;
  created_at: string;
  due_date: string | null;
  responsible_user_id: number | null;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; dot: string; badge: string }> = {
  lead:             { label: 'Lead',              dot: 'bg-gray-400',     badge: 'text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-500/10 border-gray-300 dark:border-gray-500/20' },
  triagem:          { label: 'Triagem',           dot: 'bg-blue-400',     badge: 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20' },
  diagnostico:      { label: 'Diagnóstico',       dot: 'bg-indigo-400',   badge: 'text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/10 border-indigo-200 dark:border-indigo-500/20' },
  planejamento:     { label: 'Planejamento',      dot: 'bg-purple-400',   badge: 'text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-500/10 border-purple-200 dark:border-purple-500/20' },
  execucao:         { label: 'Execução',          dot: 'bg-teal-400',     badge: 'text-teal-700 dark:text-teal-300 bg-teal-50 dark:bg-teal-500/10 border-teal-200 dark:border-teal-500/20' },
  protocolo:        { label: 'Protocolo',         dot: 'bg-orange-400',   badge: 'text-orange-700 dark:text-orange-300 bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/20' },
  aguardando_orgao: { label: 'Aguardando Órgão', dot: 'bg-yellow-400',   badge: 'text-yellow-700 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-500/10 border-yellow-200 dark:border-yellow-500/20' },
  pendencia_orgao:  { label: 'Pendência Órgão',  dot: 'bg-red-400',      badge: 'text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20' },
  concluido:        { label: 'Concluído',         dot: 'bg-emerald-400',  badge: 'text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20' },
  arquivado:        { label: 'Arquivado',         dot: 'bg-slate-400',    badge: 'text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-500/10 border-slate-300 dark:border-slate-500/20' },
  cancelado:        { label: 'Cancelado',         dot: 'bg-rose-400',     badge: 'text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20' },
};

const DEMAND_LABELS: Record<string, string> = {
  car: '🌿 CAR',
  retificacao_car: '📝 Retificação CAR',
  licenciamento: '📋 Licenciamento',
  regularizacao_fundiaria: '🏡 Reg. Fundiária',
  outorga: '💧 Outorga',
  defesa: '⚖️ Defesa',
  compensacao: '🌱 Compensação/PRAD',
  exigencia_bancaria: '🏦 Exigência Bancária',
  misto: '🔀 Misto',
  nao_identificado: '❓ Não identificado',
};

const URGENCY_CONFIG: Record<string, { label: string; cls: string }> = {
  baixa:   { label: '🟢 Baixa',   cls: 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20' },
  media:   { label: '🟡 Média',   cls: 'text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-500/10 border-yellow-200 dark:border-yellow-500/20' },
  alta:    { label: '🟠 Alta',    cls: 'text-orange-700 dark:text-orange-400 bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/20' },
  critica: { label: '🔴 Crítica', cls: 'text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20' },
};

const TASK_PROGRESS_ORDER = ['backlog', 'a_fazer', 'em_progresso', 'aguardando', 'revisao', 'concluida'];
const TASK_STATUS_LABELS: Record<string, string> = {
  backlog: 'Backlog', a_fazer: 'A Fazer', em_progresso: 'Em Progresso',
  aguardando: 'Aguardando', revisao: 'Revisão', concluida: 'Concluída', cancelada: 'Cancelada',
};

const TABS = [
  { key: 'diagnosis',  label: 'Diagnóstico', icon: Stethoscope },
  { key: 'dossier',    label: 'Dossiê',       icon: LayoutGrid },
  { key: 'workflow',   label: 'Trilha',        icon: GitBranch },
  { key: 'commercial', label: 'Comercial',     icon: Briefcase },
  { key: 'tasks',      label: 'Tarefas',       icon: ListChecks },
  { key: 'documents',  label: 'Documentos',    icon: FolderOpen },
  { key: 'timeline',   label: 'Timeline',      icon: CalendarDays },
  { key: 'ai',         label: 'IA',            icon: Bot },
];

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function ProcessDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  useQueryClient();
  const processId = parseInt(id ?? '0', 10);

  const [activeTab, setActiveTab] = useState<'diagnosis' | 'dossier' | 'workflow' | 'commercial' | 'tasks' | 'documents' | 'timeline' | 'ai'>('diagnosis');
  const [newTaskTitle, setNewTaskTitle] = useState('');

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
      return res.data;
    },
    enabled: !!process?.client_id,
  });

  const { data: tasks, refetch: refetchTasks } = useQuery({
    queryKey: ['tasks', processId],
    queryFn: async () => {
      const res = await api.get(`/tasks/?process_id=${processId}`);
      return res.data as any[];
    },
    enabled: !!processId,
  });

  const { data: documents, refetch: refetchDocuments } = useQuery({
    queryKey: ['documents', processId],
    queryFn: async () => {
      const res = await api.get(`/documents/?process_id=${processId}`);
      return res.data as any[];
    },
    enabled: !!processId,
  });

  const { data: timeline } = useQuery({
    queryKey: ['timeline', processId],
    queryFn: async () => {
      const res = await api.get(`/processes/${processId}/timeline`);
      return res.data as any[];
    },
    enabled: !!processId,
  });

  // ── Mutations ────────────────────────────────────────────────────────────────
  const createTaskMutation = useMutation({
    mutationFn: (title: string) => api.post('/tasks/', { title, process_id: processId }),
    onSuccess: () => { setNewTaskTitle(''); refetchTasks(); },
  });

  const toggleTaskMutation = useMutation({
    mutationFn: (task: any) => {
      const allowedTransitions = Array.isArray(task.allowed_transitions) ? task.allowed_transitions : [];
      const nextStatus = TASK_PROGRESS_ORDER.find(s => allowedTransitions.includes(s));
      if (!nextStatus) return api.patch(`/tasks/${task.id}/status`, { status: task.status });
      return api.patch(`/tasks/${task.id}/status`, { status: nextStatus });
    },
    onSuccess: () => refetchTasks(),
  });

  const handleDownload = async (docId: number, filename: string) => {
    try {
      const res = await api.get(`/documents/${docId}/download-url`);
      const link = document.createElement('a');
      link.href = res.data.download_url;
      link.target = '_blank';
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch {
      alert('Erro ao gerar link de download.');
    }
  };

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
        <p className="text-gray-500 dark:text-slate-400">Processo não encontrado.</p>
        <button onClick={() => navigate('/processes')} className="text-sm text-emerald-600 dark:text-emerald-400 underline">
          Voltar para processos
        </button>
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[process.status] ?? { label: process.status, dot: 'bg-gray-400', badge: 'text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-500/10 border-gray-300 dark:border-gray-500/20' };
  const urgencyCfg = URGENCY_CONFIG[process.urgency ?? 'media'];
  const demandLabel = process.demand_type ? DEMAND_LABELS[process.demand_type] : null;

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
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">O diagnóstico inicial e checklist foram gerados automaticamente.</p>
            </div>
          </div>
          <button onClick={() => setIntakeBanner(false)} className="p-1.5 rounded-lg text-gray-400 dark:text-slate-500 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/5 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Header card */}
      <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 overflow-hidden">
        {/* Accent strip */}
        <div className="h-1.5 bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-600" />
        <div className="p-5 flex items-start gap-4">
          <button
            onClick={() => navigate('/processes')}
            className="mt-0.5 p-2 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-500 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-200 dark:hover:bg-white/10 transition-all shrink-0"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex-1 min-w-0">
            {/* Badges */}
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${statusCfg.badge}`}>
                <span className={`w-2 h-2 rounded-full ${statusCfg.dot}`} />
                {statusCfg.label}
              </span>
              {demandLabel && (
                <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-300">
                  {demandLabel}
                </span>
              )}
              <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${urgencyCfg.cls}`}>
                {urgencyCfg.label}
              </span>
            </div>
            {/* Title */}
            <h1 className="text-xl font-bold text-gray-900 dark:text-white leading-tight">{process.title}</h1>
            {/* Meta row */}
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 mt-2.5 text-sm text-gray-500 dark:text-slate-400">
              {client && (
                <span className="flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5 text-gray-400 dark:text-slate-500" />
                  <span className="text-gray-700 dark:text-slate-300 font-medium">{client.full_name}</span>
                </span>
              )}
              {process.intake_source && (
                <span className="flex items-center gap-1.5">
                  <Building2 className="w-3.5 h-3.5 text-gray-400 dark:text-slate-500" />
                  via {process.intake_source}
                </span>
              )}
              <span className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-gray-400 dark:text-slate-500" />
                {new Date(process.created_at).toLocaleDateString('pt-BR', { dateStyle: 'long' })}
              </span>
              <span className="text-xs font-mono text-gray-400 dark:text-slate-500">#{process.id}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 overflow-hidden">
        <div className="border-b border-gray-100 dark:border-white/10 flex gap-0 overflow-x-auto">
          {TABS.map(tab => {
            const Icon = tab.icon;
            const active = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as typeof activeTab)}
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

          {/* ── Diagnóstico ──────────────────────────────────────────────────── */}
          {activeTab === 'diagnosis' && (
            <div className="space-y-4">

              {process.initial_diagnosis ? (
                <div className="rounded-xl bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-500/5 dark:to-teal-500/5 border border-emerald-100 dark:border-emerald-500/20 p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-7 h-7 rounded-lg bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center">
                      <Stethoscope className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <h2 className="text-sm font-semibold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider">
                      Diagnóstico Inicial — automático
                    </h2>
                  </div>
                  <p className="text-gray-700 dark:text-slate-200 leading-relaxed whitespace-pre-wrap text-sm">
                    {process.initial_diagnosis}
                  </p>
                </div>
              ) : (
                <div className="rounded-xl bg-gray-50 dark:bg-white/5 border border-dashed border-gray-200 dark:border-white/10 p-8 text-center">
                  <Stethoscope className="w-8 h-8 text-gray-300 dark:text-slate-600 mx-auto mb-2" />
                  <p className="text-gray-500 dark:text-slate-400 text-sm">Nenhum diagnóstico gerado ainda.</p>
                  <p className="text-gray-400 dark:text-slate-500 text-xs mt-1">
                    Use o{' '}
                    <button onClick={() => navigate('/intake')} className="text-emerald-600 dark:text-emerald-400 underline">
                      Intake Wizard
                    </button>{' '}
                    para gerar um diagnóstico automático.
                  </p>
                </div>
              )}

              {process.description && (
                <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
                  <h2 className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider mb-3">Descrição da Demanda</h2>
                  <p className="text-gray-700 dark:text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">{process.description}</p>
                </div>
              )}

              {process.intake_notes && (
                <div className="rounded-xl bg-amber-50 dark:bg-amber-500/5 border border-amber-200 dark:border-amber-500/20 p-5">
                  <h2 className="text-xs font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wider mb-3">📝 Notas do Intake</h2>
                  <p className="text-gray-700 dark:text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">{process.intake_notes}</p>
                </div>
              )}

              {/* Metadata grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {[
                  { label: 'ID do Processo',       value: `#${process.id}` },
                  { label: 'Tipo do Processo',     value: process.process_type ?? '—' },
                  { label: 'Tipo de Demanda',      value: process.demand_type ?? '—' },
                  { label: 'Canal de Entrada',     value: process.intake_source ?? '—' },
                  { label: 'Prioridade',           value: process.priority ?? '—' },
                  { label: 'Template Checklist',   value: process.suggested_checklist_template ?? '—' },
                ].map(m => (
                  <div key={m.label} className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 p-4">
                    <p className="text-xs text-gray-400 dark:text-slate-500 mb-1">{m.label}</p>
                    <p className="text-sm font-semibold text-gray-800 dark:text-white">{m.value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Dossiê ───────────────────────────────────────────────────────── */}
          {activeTab === 'dossier' && <ProcessDossier processId={processId} />}

          {/* ── Trilha ───────────────────────────────────────────────────────── */}
          {activeTab === 'workflow' && <WorkflowTimeline processId={processId} />}

          {/* ── Comercial ────────────────────────────────────────────────────── */}
          {activeTab === 'commercial' && <ProcessCommercial processId={processId} />}

          {/* ── Tarefas ──────────────────────────────────────────────────────── */}
          {activeTab === 'tasks' && (
            <div className="space-y-4">
              <form
                onSubmit={(e) => { e.preventDefault(); createTaskMutation.mutate(newTaskTitle); }}
                className="flex gap-2"
              >
                <input
                  required
                  type="text"
                  placeholder="Descreva a nova tarefa..."
                  value={newTaskTitle}
                  onChange={e => setNewTaskTitle(e.target.value)}
                  className="flex-1 rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 px-4 py-3 text-sm focus:outline-none focus:border-emerald-500 dark:focus:border-emerald-400 transition-colors"
                />
                <button
                  type="submit"
                  disabled={createTaskMutation.isPending}
                  className="px-4 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white font-medium text-sm transition-all flex items-center gap-1.5 shrink-0"
                >
                  <Plus className="w-4 h-4" /> Adicionar
                </button>
              </form>

              {tasks?.length === 0 ? (
                <div className="text-center py-12 text-gray-400 dark:text-slate-500 text-sm">
                  <ListChecks className="w-8 h-8 mx-auto mb-2 text-gray-300 dark:text-slate-600" />
                  Nenhuma tarefa criada ainda.
                </div>
              ) : (
                <div className="space-y-2">
                  {tasks?.map(task => {
                    const done = task.status === 'concluida' || task.status === 'done';
                    return (
                      <div key={task.id} className="flex items-center gap-3 p-4 rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 hover:border-gray-200 dark:hover:border-white/10 transition-colors">
                        <button onClick={() => toggleTaskMutation.mutate(task)} className="text-gray-400 dark:text-slate-500 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors shrink-0">
                          {done ? <CheckCircle2 className="w-5 h-5 text-emerald-500" /> : <Circle className="w-5 h-5" />}
                        </button>
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium ${done ? 'text-gray-400 dark:text-slate-500 line-through' : 'text-gray-800 dark:text-white'}`}>
                            {task.title}
                          </p>
                          <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
                            {TASK_STATUS_LABELS[task.status] ?? task.status}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ── Documentos ───────────────────────────────────────────────────── */}
          {activeTab === 'documents' && (
            <div className="space-y-5">
              <ProcessChecklist processId={processId} />

              <div className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-300 mb-3">Enviar Documento</h3>
                <DocumentUploadZone
                  processId={processId}
                  onUploadSuccess={() => refetchDocuments()}
                />
              </div>

              {(documents?.length ?? 0) > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider px-1">
                    Documentos Enviados
                  </p>
                  {documents?.map(doc => (
                    <div key={doc.id} className="flex items-center gap-4 p-4 rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 hover:border-gray-200 dark:hover:border-white/10 transition-colors">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-500/20 flex items-center justify-center shrink-0">
                        <FileText className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 dark:text-white truncate">{doc.filename || doc.original_file_name}</p>
                        <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
                          {(doc.file_size_bytes / 1024 / 1024).toFixed(2)} MB
                          {doc.document_type && ` · ${doc.document_type}`}
                          {' · '}{new Date(doc.created_at).toLocaleDateString('pt-BR')}
                        </p>
                      </div>
                      <button
                        onClick={() => handleDownload(doc.id, doc.filename || doc.original_file_name)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 text-sm transition-all"
                      >
                        <Download className="w-3.5 h-3.5" /> Baixar
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── IA ───────────────────────────────────────────────────────────── */}
          {activeTab === 'ai' && (
            <AIPanel
              processId={processId}
              processDemandType={process?.demand_type}
              processDescription={process?.description}
            />
          )}

          {/* ── Timeline ─────────────────────────────────────────────────────── */}
          {activeTab === 'timeline' && (
            <div className="relative pl-6 border-l-2 border-gray-100 dark:border-white/10 space-y-5 py-1">
              {timeline?.length === 0 ? (
                <p className="text-sm text-gray-400 dark:text-slate-500">Nenhum evento registrado.</p>
              ) : (
                timeline?.map((log: any) => (
                  <div key={log.id} className="relative">
                    <div className="absolute -left-[31px] bg-white dark:bg-slate-900 p-1">
                      <div className="w-3 h-3 bg-emerald-500 rounded-full ring-2 ring-emerald-100 dark:ring-emerald-500/20" />
                    </div>
                    <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/5 p-4 shadow-sm dark:shadow-none">
                      <p className="text-sm font-semibold text-gray-800 dark:text-white">
                        {log.action === 'status_changed' ? 'Mudança de Status' : log.details ?? log.action}
                      </p>
                      {log.action === 'status_changed' && (
                        <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
                          <span className="text-gray-600 dark:text-slate-300">{log.old_value}</span>
                          {' → '}
                          <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{log.new_value}</span>
                        </p>
                      )}
                      <p className="text-xs text-gray-400 dark:text-slate-500 mt-2 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(log.created_at).toLocaleString('pt-BR')}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

        </div>
      </div>

    </div>
  );
}
