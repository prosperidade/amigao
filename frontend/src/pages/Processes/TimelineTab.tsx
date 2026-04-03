import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Clock } from 'lucide-react';
import { TimelineEntry } from './ProcessDetailTypes';

interface TimelineTabProps {
  processId: number;
}

export default function TimelineTab({ processId }: TimelineTabProps) {
  const { data: timeline } = useQuery({
    queryKey: ['timeline', processId],
    queryFn: async () => {
      const res = await api.get(`/processes/${processId}/timeline`);
      return res.data as TimelineEntry[];
    },
    enabled: !!processId,
  });

  return (
    <div className="relative pl-6 border-l-2 border-gray-100 dark:border-white/10 space-y-5 py-1">
      {timeline?.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-slate-500">Nenhum evento registrado.</p>
      ) : (
        timeline?.map((log) => (
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
                  {' \u2192 '}
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
  );
}
