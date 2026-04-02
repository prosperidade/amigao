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
  Download, Plus, X, Zap, Building2, User,
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

const STATUS_CONFIG: Record<string, { label: string; dot: string }> = {
  lead:             { label: 'Lead',              dot: 'bg-gray-400' },
  triagem:          { label: 'Triagem',           dot: 'bg-blue-400' },
  diagnostico:      { label: 'Diagnóstico',       dot: 'bg-indigo-400' },
  planejamento:     { label: 'Planejamento',      dot: 'bg-purple-400' },
  execucao:         { label: 'Execução',          dot: 'bg-teal-400' },
  protocolo:        { label: 'Protocolo',         dot: 'bg-orange-400' },
  aguardando_orgao: { label: 'Aguardando Órgão', dot: 'bg-yellow-400' },
  pendencia_orgao:  { label: 'Pendência Órgão',  dot: 'bg-red-400' },
  concluido:        { label: 'Concluído',         dot: 'bg-emerald-400' },
  arquivado:        { label: 'Arquivado',         dot: 'bg-slate-400' },
  cancelado:        { label: 'Cancelado',         dot: 'bg-rose-400' },
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
  baixa:   { label: '🟢 Baixa',   cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
  media:   { label: '🟡 Média',   cls: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' },
  alta:    { label: '🟠 Alta',    cls: 'text-orange-400 bg-orange-500/10 border-orange-500/20' },
  critica: { label: '🔴 Crítica', cls: 'text-red-400 bg-red-500/10 border-red-500/20' },
};

const TASK_PROGRESS_ORDER = ['backlog', 'a_fazer', 'em_progresso', 'aguardando', 'revisao', 'concluida'];
const TASK_STATUS_LABELS: Record<string, string> = {
  backlog: 'Backlog', a_fazer: 'A Fazer', em_progresso: 'Em Progresso',
  aguardando: 'Aguardando', revisao: 'Revisão', concluida: 'Concluída', cancelada: 'Cancelada',
};

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function ProcessDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  useQueryClient();
  const processId = parseInt(id ?? '0', 10);

  const [activeTab, setActiveTab] = useState<'diagnosis' | 'dossier' | 'workflow' | 'commercial' | 'tasks' | 'documents' | 'timeline' | 'ai'>('diagnosis');
  const [newTaskTitle, setNewTaskTitle] = useState('');

  // Banner de boas-vindas do intake
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
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin text-3xl">⟳</div>
      </div>
    );
  }

  if (error || !process) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertCircle className="w-10 h-10 text-red-400" />
        <p className="text-gray-500">Processo não encontrado.</p>
        <button onClick={() => navigate('/processes')} className="text-sm text-primary underline">
          Voltar para processos
        </button>
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[process.status] ?? { label: process.status, dot: 'bg-gray-400' };
  const urgencyCfg = URGENCY_CONFIG[process.urgency ?? 'media'];
  const demandLabel = process.demand_type ? DEMAND_LABELS[process.demand_type] : null;

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-5xl mx-auto space-y-6">

      {/* Banner pós-intake */}
      {intakeBanner && (
        <div className="rounded-2xl bg-emerald-500/10 border border-emerald-500/30 p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Zap className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-emerald-300">Caso criado com sucesso!</p>
              <p className="text-xs text-slate-400 mt-0.5">O diagnóstico inicial e checklist foram gerados automaticamente.</p>
            </div>
          </div>
          <button onClick={() => setIntakeBanner(false)} className="text-slate-500 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => navigate('/processes')}
          className="mt-1 p-2 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border border-white/10 bg-white/5 text-slate-300`}>
              <span className={`w-2 h-2 rounded-full ${statusCfg.dot}`} />
              {statusCfg.label}
            </span>
            {demandLabel && (
              <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300">
                {demandLabel}
              </span>
            )}
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${urgencyCfg.cls}`}>
              {urgencyCfg.label}
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">{process.title}</h1>
          <div className="flex flex-wrap items-center gap-4 mt-2 text-sm text-slate-400">
            {client && (
              <span className="flex items-center gap-1.5">
                <User className="w-3.5 h-3.5" /> {client.full_name}
              </span>
            )}
            {process.intake_source && (
              <span className="flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5" /> via {process.intake_source}
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" /> {new Date(process.created_at).toLocaleDateString('pt-BR', { dateStyle: 'long' })}
            </span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-white/10 flex gap-1">
        {[
          { key: 'diagnosis', label: '🔍 Diagnóstico' },
          { key: 'dossier',     label: '📊 Dossiê' },
          { key: 'workflow',    label: '🗺️ Trilha' },
          { key: 'commercial',  label: '💼 Comercial' },
          { key: 'tasks',     label: '✅ Tarefas' },
          { key: 'documents', label: '📄 Documentos' },
          { key: 'timeline',  label: '📅 Timeline' },
          { key: 'ai',        label: '🤖 IA' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as typeof activeTab)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-all -mb-px ${
              activeTab === tab.key
                ? 'border-emerald-400 text-emerald-300'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Aba Diagnóstico ───────────────────────────────────────────────────── */}
      {activeTab === 'diagnosis' && (
        <div className="space-y-4">

          {/* Diagnóstico inicial */}
          {process.initial_diagnosis ? (
            <div className="rounded-2xl bg-white/5 border border-white/10 p-6">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
                🔍 Diagnóstico Inicial (automático)
              </h2>
              <p className="text-slate-200 leading-relaxed whitespace-pre-wrap text-sm">
                {process.initial_diagnosis}
              </p>
            </div>
          ) : (
            <div className="rounded-2xl bg-white/5 border border-dashed border-white/10 p-8 text-center">
              <p className="text-slate-500 text-sm">Nenhum diagnóstico gerado ainda.</p>
              <p className="text-slate-600 text-xs mt-1">
                Use o <button onClick={() => navigate('/intake')} className="text-emerald-400 underline">Intake Wizard</button> para gerar um diagnóstico automático.
              </p>
            </div>
          )}

          {/* Descrição */}
          {process.description && (
            <div className="rounded-2xl bg-white/5 border border-white/10 p-6">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">Descrição da Demanda</h2>
              <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">{process.description}</p>
            </div>
          )}

          {/* Notas do intake */}
          {process.intake_notes && (
            <div className="rounded-2xl bg-amber-500/5 border border-amber-500/20 p-6">
              <h2 className="text-sm font-semibold text-amber-300 uppercase tracking-wider mb-3">📝 Notas do Intake</h2>
              <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">{process.intake_notes}</p>
            </div>
          )}

          {/* Metadados */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { label: 'ID do Processo', value: `#${process.id}` },
              { label: 'Tipo do Processo', value: process.process_type ?? '—' },
              { label: 'Tipo de Demanda', value: process.demand_type ?? '—' },
              { label: 'Canal de Entrada', value: process.intake_source ?? '—' },
              { label: 'Prioridade', value: process.priority ?? '—' },
              { label: 'Template Checklist', value: process.suggested_checklist_template ?? '—' },
            ].map(m => (
              <div key={m.label} className="rounded-xl bg-white/5 border border-white/5 p-4">
                <p className="text-xs text-slate-500 mb-1">{m.label}</p>
                <p className="text-sm font-medium text-white">{m.value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Aba Dossiê ───────────────────────────────────────────────────────── */}
      {activeTab === 'dossier' && <ProcessDossier processId={processId} />}

      {/* ── Aba Trilha ───────────────────────────────────────────────────────── */}
      {activeTab === 'workflow' && <WorkflowTimeline processId={processId} />}

      {/* ── Aba Comercial ────────────────────────────────────────────────────── */}
      {activeTab === 'commercial' && <ProcessCommercial processId={processId} />}

      {/* ── Aba Tarefas ──────────────────────────────────────────────────────── */}
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
              className="flex-1 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-3 text-sm focus:outline-none focus:border-emerald-400 transition-colors"
            />
            <button
              type="submit"
              disabled={createTaskMutation.isPending}
              className="px-4 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white font-medium text-sm transition-all flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" /> Adicionar
            </button>
          </form>

          {tasks?.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-sm">Nenhuma tarefa criada ainda.</div>
          ) : (
            <div className="space-y-2">
              {tasks?.map(task => {
                const done = task.status === 'concluida' || task.status === 'done';
                return (
                  <div key={task.id} className="flex items-center gap-3 p-4 rounded-xl bg-white/5 border border-white/5 hover:border-white/10 transition-colors">
                    <button onClick={() => toggleTaskMutation.mutate(task)} className="text-slate-500 hover:text-emerald-400 transition-colors">
                      {done ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <Circle className="w-5 h-5" />}
                    </button>
                    <div className="flex-1">
                      <p className={`text-sm font-medium ${done ? 'text-slate-500 line-through' : 'text-white'}`}>
                        {task.title}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">
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

      {/* ── Aba Documentos ───────────────────────────────────────────────────── */}
      {activeTab === 'documents' && (
        <div className="space-y-6">

          {/* Checklist documental */}
          <ProcessChecklist processId={processId} />

          {/* Upload de documento */}
          <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Enviar Documento</h3>
            <DocumentUploadZone
              processId={processId}
              onUploadSuccess={() => refetchDocuments()}
            />
          </div>

          {/* Lista de documentos enviados */}
          {(documents?.length ?? 0) > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1">
                Documentos Enviados
              </p>
              {documents?.map(doc => (
                <div key={doc.id} className="flex items-center gap-4 p-4 rounded-xl bg-white/5 border border-white/5 hover:border-white/10 transition-colors">
                  <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-indigo-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{doc.filename || doc.original_file_name}</p>
                    <p className="text-xs text-slate-500">
                      {(doc.file_size_bytes / 1024 / 1024).toFixed(2)} MB
                      {doc.document_type && ` · ${doc.document_type}`}
                      {' · '}{new Date(doc.created_at).toLocaleDateString('pt-BR')}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDownload(doc.id, doc.filename || doc.original_file_name)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-300 hover:text-white hover:bg-white/10 text-sm transition-all"
                  >
                    <Download className="w-3.5 h-3.5" /> Baixar
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Aba IA ───────────────────────────────────────────────────────────── */}
      {activeTab === 'ai' && (
        <AIPanel
          processId={processId}
          processDemandType={process?.demand_type}
          processDescription={process?.description}
        />
      )}

      {/* ── Aba Timeline ─────────────────────────────────────────────────────── */}
      {activeTab === 'timeline' && (
        <div className="relative pl-6 border-l border-white/10 space-y-6 py-2">
          {timeline?.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum evento registrado.</p>
          ) : (
            timeline?.map((log: any) => (
              <div key={log.id} className="relative">
                <div className="absolute -left-[31px] bg-slate-900 p-1">
                  <div className="w-3 h-3 bg-emerald-500 rounded-full" />
                </div>
                <div className="rounded-xl bg-white/5 border border-white/5 p-4">
                  <p className="text-sm font-medium text-white">
                    {log.action === 'status_changed' ? 'Mudança de Status' : log.details ?? log.action}
                  </p>
                  {log.action === 'status_changed' && (
                    <p className="text-sm text-slate-400 mt-1">
                      <span className="text-slate-300">{log.old_value}</span>
                      {' → '}
                      <span className="text-emerald-400 font-medium">{log.new_value}</span>
                    </p>
                  )}
                  <p className="text-xs text-slate-500 mt-2">
                    <Clock className="w-3 h-3 inline mr-1" />
                    {new Date(log.created_at).toLocaleString('pt-BR')}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      )}

    </div>
  );
}
