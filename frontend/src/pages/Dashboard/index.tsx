import { useState } from 'react';
import {
  Users, Briefcase, AlertCircle, FileText, Activity, Plus,
  CheckSquare, Clock, TrendingUp, DollarSign, AlertTriangle,
  Eye, Calendar, Shield, Bot,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/store/auth';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import DashboardRegente from './DashboardRegente';
import DashboardOperacionalRegente from './DashboardOperacionalRegente';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RecentActivity {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  details: string | null;
  actor_name: string | null;
  created_at: string;
}

interface PendingTask {
  id: number;
  title: string;
  status: string;
  priority: string;
  process_id: number | null;
  due_date: string | null;
}

interface StatusDistribution {
  status: string;
  count: number;
}

interface ProposalPipelineItem {
  status: string;
  count: number;
  total_value: number;
}

interface DocumentAlert {
  id: number;
  filename: string;
  document_type: string | null;
  process_id: number | null;
  expires_at: string | null;
  review_required: boolean;
}

interface ProcessAlert {
  id: number;
  title: string;
  status: string;
  priority: string | null;
  due_date: string | null;
  days_in_status: number | null;
}

interface ExecutivoDashboard {
  view: 'executivo';
  active_processes: number;
  overdue_tasks: number;
  total_clients: number;
  total_properties: number;
  conversion_rate: number;
  faturamento: number;
  risco_medio: number | null;
  processes_by_status: StatusDistribution[];
  processes_by_demand_type: StatusDistribution[];
  proposal_pipeline: ProposalPipelineItem[];
  recent_activities: RecentActivity[];
  my_pending_tasks: PendingTask[];
}

interface OperacionalDashboard {
  view: 'operacional';
  active_processes: number;
  overdue_tasks: number;
  total_clients: number;
  total_properties: number;
  my_pending_tasks_count: number;
  my_overdue_tasks_count: number;
  documents_needing_review: number;
  processes_aguardando_orgao: number;
  my_pending_tasks: PendingTask[];
  documents_for_review: DocumentAlert[];
  expiring_documents: DocumentAlert[];
  process_alerts: ProcessAlert[];
  recent_activities: RecentActivity[];
}

type DashboardData = ExecutivoDashboard | OperacionalDashboard;
type ViewMode = 'executivo' | 'operacional';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-gray-200 dark:bg-zinc-800", className)} />;
}

function SkeletonStatsCards() {
  return (
    <>
      {[0, 1, 2, 3].map(i => (
        <div key={i} className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm w-full">
          <div className="flex justify-between items-start">
            <div className="space-y-3 flex-1">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-8 w-16" />
            </div>
            <Skeleton className="h-12 w-12 rounded-lg shrink-0" />
          </div>
        </div>
      ))}
    </>
  );
}

function SkeletonSection() {
  return (
    <div className="space-y-2">
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} className="flex gap-4 items-start p-3">
          <Skeleton className="h-8 w-8 rounded-full shrink-0" />
          <div className="space-y-2 flex-1">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return 'Agora mesmo';
  if (diff < 3600) return `Há ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `Há ${Math.floor(diff / 3600)}h`;
  return `Há ${Math.floor(diff / 86400)} dia(s)`;
}

function actionLabel(action: string, entity_type: string): string {
  if (action === 'created') return `${entity_type === 'process' ? 'Processo' : 'Item'} criado`;
  if (action === 'status_changed') return 'Status alterado';
  if (action === 'updated') return `${entity_type === 'process' ? 'Processo' : 'Item'} atualizado`;
  return action;
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  high: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  low: 'bg-gray-100 text-gray-600 dark:bg-zinc-800 dark:text-gray-400',
};

const STATUS_LABELS: Record<string, string> = {
  lead: 'Lead',
  triagem: 'Triagem',
  diagnostico: 'Diagnóstico',
  planejamento: 'Planejamento',
  execucao: 'Execução',
  protocolo: 'Protocolo',
  aguardando_orgao: 'Aguardando Órgão',
  pendencia_orgao: 'Pendência Órgão',
  concluido: 'Concluído',
  arquivado: 'Arquivado',
  cancelado: 'Cancelado',
  draft: 'Rascunho',
  sent: 'Enviada',
  accepted: 'Aceita',
  rejected: 'Rejeitada',
  expired: 'Expirada',
};

const DEMAND_LABELS: Record<string, string> = {
  car: 'CAR',
  retificacao_car: 'Retificação CAR',
  licenciamento: 'Licenciamento',
  regularizacao_fundiaria: 'Reg. Fundiária',
  outorga: 'Outorga',
  defesa: 'Defesa',
  compensacao: 'Compensação',
  exigencia_bancaria: 'Exig. Bancária',
  prad: 'PRAD',
  misto: 'Misto',
  nao_identificado: 'Não Identificado',
};

function formatCurrency(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------

interface StatCardProps {
  title: string;
  value: string;
  icon: React.ElementType;
  color: string;
  bg: string;
  onClick?: () => void;
}

function StatCard({ title, value, icon: Icon, color, bg, onClick }: StatCardProps) {
  return (
    <button
      onClick={onClick}
      className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm transform transition-all hover:scale-[1.02] hover:border-gray-300 dark:hover:border-zinc-600 text-left w-full cursor-pointer"
    >
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          <h3 className="text-3xl font-bold text-gray-900 dark:text-white mt-2">{value}</h3>
        </div>
        <div className={`p-3 rounded-lg ${bg}`}>
          <Icon className={`w-6 h-6 ${color}`} />
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Section Components
// ---------------------------------------------------------------------------

function ActivitiesSection({ activities, loading, navigate }: {
  activities: RecentActivity[];
  loading: boolean;
  navigate: (path: string) => void;
}) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Activity className="w-5 h-5 mr-2 text-emerald-600" />
        Atividades Recentes
      </h2>
      {loading && <SkeletonSection />}
      {!loading && !activities.length && (
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhuma atividade registrada ainda.
        </div>
      )}
      {!loading && !!activities.length && (
        <div className="space-y-1">
          {activities.map(a => (
            <button
              type="button"
              key={a.id}
              className="flex gap-4 items-start p-3 hover:bg-gray-50 dark:hover:bg-zinc-800/50 rounded-lg transition-colors border border-transparent hover:border-gray-100 dark:hover:border-zinc-800 cursor-pointer text-left w-full"
              onClick={() => a.entity_type === 'process' && navigate(`/processes/${a.entity_id}`)}
            >
              <div className="bg-gray-100 dark:bg-zinc-800 p-2 rounded-full mt-0.5 shrink-0">
                <FileText className="w-4 h-4 text-gray-600 dark:text-gray-400" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {actionLabel(a.action, a.entity_type)}{a.details ? ` — ${a.details}` : ''}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {timeAgo(a.created_at)}{a.actor_name ? ` • ${a.actor_name}` : ''}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function TasksSection({ tasks, loading, navigate }: {
  tasks: PendingTask[];
  loading: boolean;
  navigate: (path: string) => void;
}) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <CheckSquare className="w-5 h-5 mr-2 text-emerald-600" />
        Minhas Tarefas
      </h2>
      {loading && <SkeletonSection />}
      {!loading && !tasks.length && (
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhuma tarefa pendente.
        </div>
      )}
      {!loading && !!tasks.length && (
        <div className="space-y-2">
          {tasks.map(task => (
            <button
              type="button"
              key={task.id}
              className="p-3 rounded-lg border border-gray-100 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer text-left w-full"
              onClick={() => task.process_id && navigate(`/processes/${task.process_id}`)}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-gray-900 dark:text-white leading-snug line-clamp-2">{task.title}</p>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${PRIORITY_COLORS[task.priority] ?? PRIORITY_COLORS.low}`}>
                  {task.priority}
                </span>
              </div>
              {task.due_date && (
                <p className="text-xs text-gray-400 mt-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(task.due_date).toLocaleDateString('pt-BR')}
                </p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Executivo Sections
// ---------------------------------------------------------------------------

function ProposalPipelineSection({ pipeline }: { pipeline: ProposalPipelineItem[] }) {
  if (!pipeline.length) {
    return (
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
          <DollarSign className="w-5 h-5 mr-2 text-emerald-600" />
          Pipeline de Propostas
        </h2>
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhuma proposta registrada ainda.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <DollarSign className="w-5 h-5 mr-2 text-emerald-600" />
        Pipeline de Propostas
      </h2>
      <div className="space-y-3">
        {pipeline.map(item => (
          <div key={item.status} className="flex items-center justify-between p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                {STATUS_LABELS[item.status] ?? item.status}
              </p>
              <p className="text-xs text-gray-500">{item.count} proposta{item.count !== 1 ? 's' : ''}</p>
            </div>
            <p className="text-sm font-bold text-gray-900 dark:text-white">{formatCurrency(item.total_value)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

const BAR_COLORS = [
  'bg-emerald-500', 'bg-blue-500', 'bg-amber-500', 'bg-purple-500',
  'bg-rose-500', 'bg-cyan-500', 'bg-indigo-500', 'bg-teal-500',
];

function DistributionSection({ title, icon: Icon, items, labelMap }: {
  title: string;
  icon: React.ElementType;
  items: StatusDistribution[];
  labelMap: Record<string, string>;
}) {
  if (!items.length) return null;
  const total = items.reduce((sum, i) => sum + i.count, 0);

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Icon className="w-5 h-5 mr-2 text-emerald-600" />
        {title}
      </h2>
      <div className="space-y-2">
        {items.map((item, index) => {
          const pct = total > 0 ? Math.round((item.count / total) * 100) : 0;
          return (
            <div key={item.status}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-gray-700 dark:text-gray-300">{labelMap[item.status] ?? item.status}</span>
                <span className="text-gray-500">{item.count} ({pct}%)</span>
              </div>
              <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-2">
                <div className={`${BAR_COLORS[index % BAR_COLORS.length]} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Operacional Sections
// ---------------------------------------------------------------------------

function DocumentsReviewSection({ docs, navigate }: { docs: DocumentAlert[]; navigate: (path: string) => void }) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Eye className="w-5 h-5 mr-2 text-amber-600" />
        Documentos para Revisão
      </h2>
      {!docs.length && (
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhum documento pendente de revisão.
        </div>
      )}
      {!!docs.length && (
        <div className="space-y-2">
          {docs.map(doc => (
            <button
              type="button"
              key={doc.id}
              className="flex items-center justify-between p-3 rounded-lg border border-gray-100 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer text-left w-full"
              onClick={() => doc.process_id && navigate(`/processes/${doc.process_id}`)}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{doc.filename}</p>
                <p className="text-xs text-gray-500">{doc.document_type ?? 'Tipo não definido'}</p>
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 shrink-0">
                Revisão
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function expiryUrgency(expiresAt: string): { label: string; className: string } {
  const days = Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 86_400_000);
  if (days <= 7) return { label: `${days}d`, className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' };
  if (days <= 14) return { label: `${days}d`, className: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' };
  return { label: `${days}d`, className: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' };
}

function ExpiringDocumentsSection({ docs, navigate }: { docs: DocumentAlert[]; navigate: (path: string) => void }) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Calendar className="w-5 h-5 mr-2 text-red-500" />
        Documentos Expirando
      </h2>
      {!docs.length && (
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhum documento expirando nos próximos 30 dias.
        </div>
      )}
      {!!docs.length && (
        <div className="space-y-2">
          {docs.map(doc => {
            const urgency = doc.expires_at ? expiryUrgency(doc.expires_at) : null;
            return (
              <button
                type="button"
                key={doc.id}
                className="flex items-center justify-between p-3 rounded-lg border border-gray-100 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer text-left w-full"
                onClick={() => doc.process_id && navigate(`/processes/${doc.process_id}`)}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{doc.filename}</p>
                  <p className="text-xs text-gray-500">{doc.document_type ?? 'Tipo não definido'}</p>
                </div>
                {urgency && (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${urgency.className}`}>
                    {new Date(doc.expires_at!).toLocaleDateString('pt-BR')} ({urgency.label})
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ProcessAlertsSection({ alerts, navigate }: { alerts: ProcessAlert[]; navigate: (path: string) => void }) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Shield className="w-5 h-5 mr-2 text-red-500" />
        Alertas de Processo
      </h2>
      {!alerts.length && (
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhum alerta no momento.
        </div>
      )}
      {!!alerts.length && (
        <div className="space-y-2">
          {alerts.map(a => (
            <button
              type="button"
              key={a.id}
              className="p-3 rounded-lg border border-gray-100 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer text-left w-full"
              onClick={() => navigate(`/processes/${a.id}`)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{a.title}</p>
                  <p className="text-xs text-gray-500">
                    {STATUS_LABELS[a.status] ?? a.status}
                    {a.days_in_status != null ? ` • ${a.days_in_status} dias` : ''}
                  </p>
                </div>
                {a.due_date && (
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 shrink-0">
                    {new Date(a.due_date).toLocaleDateString('pt-BR')}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Agent Metrics + Vigia Alerts
// ---------------------------------------------------------------------------

function AgentMetricsCard() {
  const { data: jobs = [] } = useQuery<{
    id: number; status: string; agent_name: string | null;
    cost_usd: number | null; created_at: string;
    result: Record<string, unknown> | null;
  }[]>({
    queryKey: ['ai-jobs-dashboard'],
    queryFn: () => api.get('/ai/jobs', { params: { limit: 100 } }).then(r => r.data),
    staleTime: 60_000,
  });

  const today = new Date().toDateString();
  const todayJobs = jobs.filter(j => new Date(j.created_at).toDateString() === today);
  const completed = todayJobs.filter(j => j.status === 'completed').length;
  const failed = todayJobs.filter(j => j.status === 'failed').length;
  const totalCost = todayJobs.reduce((s, j) => s + (j.cost_usd ?? 0), 0);
  const needsReview = todayJobs.filter(j => j.result?.requires_review === true).length;
  const successRate = todayJobs.length > 0 ? Math.round((completed / todayJobs.length) * 100) : 0;

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Bot className="w-5 h-5 mr-2 text-purple-600" />
        Agentes IA (hoje)
      </h2>
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">Execucoes</p>
          <p className="text-xl font-bold text-gray-900 dark:text-white">{todayJobs.length}</p>
        </div>
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">Taxa Sucesso</p>
          <p className={`text-xl font-bold ${successRate >= 80 ? 'text-emerald-600' : successRate >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
            {successRate}%
          </p>
        </div>
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">Custo</p>
          <p className="text-xl font-bold text-gray-900 dark:text-white">${totalCost.toFixed(4)}</p>
        </div>
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">Revisao Pendente</p>
          <p className={`text-xl font-bold ${needsReview > 0 ? 'text-amber-600' : 'text-gray-900 dark:text-white'}`}>
            {needsReview}
          </p>
        </div>
      </div>
      {failed > 0 && (
        <div className="mt-3 p-2 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-500/20">
          <p className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" /> {failed} execucao(oes) falharam hoje
          </p>
        </div>
      )}
    </div>
  );
}

function VigiaAlertsBanner({ navigate }: { navigate: (path: string) => void }) {
  const { data: jobs = [] } = useQuery<{
    id: number; agent_name: string | null; status: string;
    result: Record<string, unknown> | null; created_at: string;
  }[]>({
    queryKey: ['vigia-alerts'],
    queryFn: () => api.get('/ai/jobs', {
      params: { agent_name: 'vigia', limit: 1 },
    }).then(r => r.data),
    staleTime: 300_000,
  });

  const lastVigia = jobs.find(j => j.agent_name === 'vigia' && j.status === 'completed');
  const alerts = (lastVigia?.result?.alerts ?? []) as {
    type: string; severity: string; message: string; process_id?: number;
  }[];

  if (!alerts.length) return null;

  const severityStyles: Record<string, string> = {
    error: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-500/30 text-red-700 dark:text-red-300',
    warning: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-500/30 text-amber-700 dark:text-amber-300',
  };

  return (
    <div className="space-y-2">
      {alerts.slice(0, 5).map((alert, i) => (
        <button
          key={i}
          type="button"
          onClick={() => alert.process_id && navigate(`/processes/${alert.process_id}`)}
          className={`w-full text-left p-3 rounded-xl border text-sm flex items-center gap-2 transition-colors hover:opacity-80 ${severityStyles[alert.severity] ?? severityStyles.warning}`}
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span className="truncate">{alert.message}</span>
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState<ViewMode>('executivo');

  const { data: summaryData, isLoading } = useQuery({
    queryKey: ['dashboard-stats', viewMode],
    queryFn: () => api.get<DashboardData>('/dashboard/summary', { params: { view: viewMode } }).then(r => r.data),
    staleTime: 30_000,
  });

  const activities: RecentActivity[] = summaryData?.recent_activities ?? [];
  const tasks: PendingTask[] = summaryData?.my_pending_tasks ?? [];

  // Stats cards condicionais
  const stats: StatCardProps[] = (() => {
    if (!summaryData || isLoading) return [];

    if (viewMode === 'executivo' && summaryData.view === 'executivo') {
      const d = summaryData;
      return [
        { title: 'Processos Ativos', value: String(d.active_processes), icon: Briefcase, color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30', onClick: () => navigate('/processes') },
        { title: 'Taxa de Conversão', value: `${(d.conversion_rate * 100).toFixed(0)}%`, icon: TrendingUp, color: 'text-emerald-600', bg: 'bg-emerald-100 dark:bg-emerald-900/30' },
        { title: 'Faturamento', value: formatCurrency(d.faturamento), icon: DollarSign, color: 'text-green-600', bg: 'bg-green-100 dark:bg-green-900/30' },
        { title: 'Risco Médio', value: d.risco_medio != null ? d.risco_medio.toFixed(1) : '—', icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-900/30' },
      ];
    }

    if (viewMode === 'operacional' && summaryData.view === 'operacional') {
      const d = summaryData;
      return [
        { title: 'Minhas Pendentes', value: String(d.my_pending_tasks_count), icon: CheckSquare, color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30' },
        { title: 'Tarefas em Atraso', value: String(d.my_overdue_tasks_count), icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-900/30' },
        { title: 'Docs para Revisão', value: String(d.documents_needing_review), icon: FileText, color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-900/30' },
        { title: 'Aguardando Órgão', value: String(d.processes_aguardando_orgao), icon: Clock, color: 'text-purple-600', bg: 'bg-purple-100 dark:bg-purple-900/30' },
      ];
    }

    return [];
  })();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Olá, {user?.full_name?.split(' ')[0] ?? 'Administrador'}
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            {viewMode === 'executivo' ? 'Visão estratégica do negócio' : 'Visão operacional do dia a dia'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex rounded-xl bg-gray-100 dark:bg-zinc-800 p-1">
            <button
              onClick={() => setViewMode('executivo')}
              className={cn(
                "px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200",
                viewMode === 'executivo'
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
              )}
            >
              Executivo
            </button>
            <button
              onClick={() => setViewMode('operacional')}
              className={cn(
                "px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200",
                viewMode === 'operacional'
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
              )}
            >
              Operacional
            </button>
          </div>
          <button
            onClick={() => navigate('/intake')}
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-colors shadow-lg shadow-emerald-500/20 flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Novo Caso
          </button>
          {/* CAM2D-007 — Ação rápida: Fluxo de trabalho */}
          <button
            onClick={() => navigate('/processes')}
            className="bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200 hover:bg-gray-50 dark:hover:bg-white/10 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
          >
            <Briefcase className="w-4 h-4" />
            Fluxo
          </button>
        </div>
      </div>

      {/* Stats Cards — só na view executivo (operacional tem os 8 do Regente) */}
      {viewMode === 'executivo' && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {isLoading ? (
            <SkeletonStatsCards />
          ) : (
            stats.map((item, index) => <StatCard key={index} {...item} />)
          )}
        </div>
      )}

      {/* Regente Cam2 — Blocos 3/4/5/6 (CAM2D-001/002/003/004) */}
      {viewMode === 'executivo' && <DashboardRegente />}

      {/* === EXECUTIVO SECTIONS === */}
      {viewMode === 'executivo' && (
        <div className="space-y-6">
          {/* Row 1: Atividades + Pipeline */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="col-span-1 lg:col-span-2">
              <ActivitiesSection activities={activities} loading={isLoading} navigate={navigate} />
            </div>
            <div className="col-span-1">
              {summaryData?.view === 'executivo' && (
                <ProposalPipelineSection pipeline={summaryData.proposal_pipeline} />
              )}
            </div>
          </div>

          {/* Row 2: Distribuicoes */}
          {summaryData?.view === 'executivo' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <DistributionSection
                title="Processos por Status"
                icon={Briefcase}
                items={summaryData.processes_by_status}
                labelMap={STATUS_LABELS}
              />
              <DistributionSection
                title="Processos por Tipo de Demanda"
                icon={Users}
                items={summaryData.processes_by_demand_type}
                labelMap={DEMAND_LABELS}
              />
            </div>
          )}

          {/* Row 3: Tarefas */}
          <TasksSection tasks={tasks} loading={isLoading} navigate={navigate} />
        </div>
      )}

      {/* === OPERACIONAL SECTIONS === */}
      {viewMode === 'operacional' && (
        <div className="space-y-6">
          {/* Bloco 1 do Sprint F — 8 KPIs + Casos por Etapa + Funil Operacional */}
          <DashboardOperacionalRegente />

          {/* Vigia Alerts Banner */}
          <VigiaAlertsBanner navigate={navigate} />

          {/* Row 1: Tarefas + Docs Revisao + IA Metrics */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <TasksSection tasks={tasks} loading={isLoading} navigate={navigate} />
            {summaryData?.view === 'operacional' && (
              <DocumentsReviewSection docs={summaryData.documents_for_review} navigate={navigate} />
            )}
            <AgentMetricsCard />
          </div>

          {/* Row 2: Docs Expirando + Alertas */}
          {summaryData?.view === 'operacional' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ExpiringDocumentsSection docs={summaryData.expiring_documents} navigate={navigate} />
              <ProcessAlertsSection alerts={summaryData.process_alerts} navigate={navigate} />
            </div>
          )}

          {/* Row 3: Atividades */}
          <ActivitiesSection activities={activities} loading={isLoading} navigate={navigate} />
        </div>
      )}
    </div>
  );
}
