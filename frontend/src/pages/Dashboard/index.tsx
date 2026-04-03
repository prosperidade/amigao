import { Users, Briefcase, Frame, AlertCircle, FileText, Activity, Plus, CheckSquare, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/store/auth';
import { api } from '@/lib/api';

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

  const { data, isLoading } = useQuery<DashboardSummary>({
    queryKey: ['dashboard-summary'],
    queryFn: () => api.get('/dashboard/summary').then(r => r.data),
    staleTime: 30_000,
  });

  const stats = [
    {
      title: 'Processos Ativos',
      value: isLoading ? '…' : String(data?.active_processes ?? 0),
      icon: Briefcase,
      color: 'text-blue-600',
      bg: 'bg-blue-100 dark:bg-blue-900/30',
      onClick: () => navigate('/processes'),
    },
    {
      title: 'Tarefas em Atraso',
      value: isLoading ? '…' : String(data?.overdue_tasks ?? 0),
      icon: AlertCircle,
      color: 'text-red-600',
      bg: 'bg-red-100 dark:bg-red-900/30',
      onClick: () => navigate('/processes'),
    },
    {
      title: 'Clientes Totais',
      value: isLoading ? '…' : String(data?.total_clients ?? 0),
      icon: Users,
      color: 'text-green-600',
      bg: 'bg-green-100 dark:bg-green-900/30',
      onClick: () => navigate('/clients'),
    },
    {
      title: 'Imóveis Cadastrados',
      value: isLoading ? '…' : String(data?.total_properties ?? 0),
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
        <button
          onClick={() => navigate('/intake')}
          className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-colors shadow-lg shadow-emerald-500/20 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nova Demanda
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {stats.map((item, index) => (
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
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">

        {/* Atividades Recentes */}
        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm col-span-1 lg:col-span-2 p-6">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-emerald-600" />
            Atividades Recentes
          </h2>

          {isLoading && (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-14 bg-gray-100 dark:bg-zinc-800 rounded-lg animate-pulse" />
              ))}
            </div>
          )}

          {!isLoading && (!data?.recent_activities?.length) && (
            <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
              Nenhuma atividade registrada ainda.
            </div>
          )}

          {!isLoading && !!data?.recent_activities?.length && (
            <div className="space-y-1">
              {data.recent_activities.map(activity => (
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

        {/* Minhas Tarefas Hoje */}
        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm col-span-1 p-6">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
            <CheckSquare className="w-5 h-5 mr-2 text-emerald-600" />
            Minhas Tarefas
          </h2>

          {isLoading && (
            <div className="space-y-2">
              {[1, 2].map(i => (
                <div key={i} className="h-12 bg-gray-100 dark:bg-zinc-800 rounded-lg animate-pulse" />
              ))}
            </div>
          )}

          {!isLoading && !data?.my_pending_tasks?.length && (
            <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
              Nenhuma tarefa urgente pra você hoje. Aproveite o café! ☕
            </div>
          )}

          {!isLoading && !!data?.my_pending_tasks?.length && (
            <div className="space-y-2">
              {data.my_pending_tasks.map(task => (
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
