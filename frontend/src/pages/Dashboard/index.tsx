import { useState } from 'react';
import { Users, Briefcase, Frame, AlertCircle, FileText, Activity, Plus, CheckSquare, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/store/auth';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

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

interface DashboardSummary {
  active_processes: number;
  overdue_tasks: number;
  total_clients: number;
  total_properties: number;
  recent_activities: RecentActivity[];
  my_pending_tasks: PendingTask[];
}

type ViewMode = 'executivo' | 'operacional';

function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-gray-200 dark:bg-zinc-800", className)} />;
}

function SkeletonStatsCards() {
  return (
    <>
      {[0, 1, 2, 3].map(i => (
        <div
          key={i}
          className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm w-full"
        >
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

function SkeletonActivities() {
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

function SkeletonTasks() {
  return (
    <div className="space-y-2">
      {[0, 1, 2].map(i => (
        <div key={i} className="p-3 rounded-lg border border-gray-100 dark:border-zinc-800">
          <div className="flex items-start justify-between gap-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-5 w-14 rounded-full" />
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
  if (action === 'status_changed') return `Status alterado`;
  if (action === 'updated') return `${entity_type === 'process' ? 'Processo' : 'Item'} atualizado`;
  return action;
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  high: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  low: 'bg-gray-100 text-gray-600 dark:bg-zinc-800 dark:text-gray-400',
};

export default function Dashboard() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState<ViewMode>('executivo');

  const { data: summaryData, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats', viewMode],
    queryFn: () => api.get<DashboardSummary>('/dashboard/summary', { params: { view: viewMode } }).then(r => r.data),
    staleTime: 30_000,
  });

  const activities: RecentActivity[] = summaryData?.recent_activities ?? [];
  const tasks: PendingTask[] = summaryData?.my_pending_tasks ?? [];

  const activitiesLoading = statsLoading;
  const tasksLoading = statsLoading;

  const stats = [
    {
      title: 'Processos Ativos',
      value: statsLoading ? null : String(summaryData?.active_processes ?? 0),
      icon: Briefcase,
      color: 'text-blue-600',
      bg: 'bg-blue-100 dark:bg-blue-900/30',
      onClick: () => navigate('/processes'),
    },
    {
      title: 'Tarefas em Atraso',
      value: statsLoading ? null : String(summaryData?.overdue_tasks ?? 0),
      icon: AlertCircle,
      color: 'text-red-600',
      bg: 'bg-red-100 dark:bg-red-900/30',
      onClick: () => navigate('/processes'),
    },
    {
      title: 'Clientes Totais',
      value: statsLoading ? null : String(summaryData?.total_clients ?? 0),
      icon: Users,
      color: 'text-green-600',
      bg: 'bg-green-100 dark:bg-green-900/30',
      onClick: () => navigate('/clients'),
    },
    {
      title: 'Imóveis Cadastrados',
      value: statsLoading ? null : String(summaryData?.total_properties ?? 0),
      icon: Frame,
      color: 'text-amber-600',
      bg: 'bg-amber-100 dark:bg-amber-900/30',
      onClick: () => navigate('/properties'),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Olá, {user?.full_name?.split(' ')[0] ?? 'Administrador'} 👋
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Bem-vindo(a) ao painel de gestão ambiental.</p>
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
            Nova Demanda
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {statsLoading ? (
          <SkeletonStatsCards />
        ) : (
          stats.map((item, index) => (
            <button
              key={index}
              onClick={item.onClick}
              className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm transform transition-all hover:scale-[1.02] hover:border-gray-300 dark:hover:border-zinc-600 text-left w-full cursor-pointer"
            >
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{item.title}</p>
                  <h3 className="text-3xl font-bold text-gray-900 dark:text-white mt-2">{item.value}</h3>
                </div>
                <div className={`p-3 rounded-lg ${item.bg}`}>
                  <item.icon className={`w-6 h-6 ${item.color}`} />
                </div>
              </div>
            </button>
          ))
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">

        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm col-span-1 lg:col-span-2 p-6">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-emerald-600" />
            Atividades Recentes
          </h2>

          {activitiesLoading && <SkeletonActivities />}

          {!activitiesLoading && !activities.length && (
            <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
              Nenhuma atividade registrada ainda.
            </div>
          )}

          {!activitiesLoading && !!activities.length && (
            <div className="space-y-1">
              {activities.map(activity => (
                <div
                  key={activity.id}
                  className="flex gap-4 items-start p-3 hover:bg-gray-50 dark:hover:bg-zinc-800/50 rounded-lg transition-colors border border-transparent hover:border-gray-100 dark:hover:border-zinc-800 cursor-pointer"
                  onClick={() => activity.entity_type === 'process' && navigate(`/processes/${activity.entity_id}`)}
                >
                  <div className="bg-gray-100 dark:bg-zinc-800 p-2 rounded-full mt-0.5 shrink-0">
                    <FileText className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {actionLabel(activity.action, activity.entity_type)}
                      {activity.details ? ` — ${activity.details}` : ''}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {timeAgo(activity.created_at)}
                      {activity.actor_name ? ` • ${activity.actor_name}` : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm col-span-1 p-6">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
            <CheckSquare className="w-5 h-5 mr-2 text-emerald-600" />
            Minhas Tarefas
          </h2>

          {tasksLoading && <SkeletonTasks />}

          {!tasksLoading && !tasks.length && (
            <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
              Nenhuma tarefa urgente pra você hoje. Aproveite o café! ☕
            </div>
          )}

          {!tasksLoading && !!tasks.length && (
            <div className="space-y-2">
              {tasks.map(task => (
                <div
                  key={task.id}
                  className="p-3 rounded-lg border border-gray-100 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer"
                  onClick={() => task.process_id && navigate(`/processes/${task.process_id}`)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-gray-900 dark:text-white leading-snug line-clamp-2">
                      {task.title}
                    </p>
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
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
