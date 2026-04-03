import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Plus, CheckCircle2, Circle, ListChecks } from 'lucide-react';
import { Task, TASK_PROGRESS_ORDER, TASK_STATUS_LABELS } from './ProcessDetailTypes';

interface TasksTabProps {
  processId: number;
}

export default function TasksTab({ processId }: TasksTabProps) {
  const [newTaskTitle, setNewTaskTitle] = useState('');

  const { data: tasks, refetch: refetchTasks } = useQuery({
    queryKey: ['tasks', processId],
    queryFn: async () => {
      const res = await api.get(`/tasks/?process_id=${processId}`);
      return res.data as Task[];
    },
    enabled: !!processId,
  });

  const createTaskMutation = useMutation({
    mutationFn: (title: string) => api.post('/tasks/', { title, process_id: processId }),
    onSuccess: () => { setNewTaskTitle(''); refetchTasks(); },
  });

  const toggleTaskMutation = useMutation({
    mutationFn: (task: Task) => {
      const allowedTransitions = Array.isArray(task.allowed_transitions) ? task.allowed_transitions : [];
      const nextStatus = TASK_PROGRESS_ORDER.find(s => allowedTransitions.includes(s));
      if (!nextStatus) return api.patch(`/tasks/${task.id}/status`, { status: task.status });
      return api.patch(`/tasks/${task.id}/status`, { status: nextStatus });
    },
    onSuccess: () => refetchTasks(),
  });

  return (
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
  );
}
