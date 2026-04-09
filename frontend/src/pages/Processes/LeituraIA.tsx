import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '@/lib/api';
import type { KanbanInsight } from './quadro-types';

export default function LeituraIA() {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('leitura-ia-collapsed') === 'true'; } catch { return false; }
  });

  const { data: insight } = useQuery({
    queryKey: ['kanban-insights'],
    queryFn: () => api.get<KanbanInsight>('/dashboard/kanban-insights').then(r => r.data),
    staleTime: 60_000,
  });

  if (!insight || (!insight.gargalo_macroetapa && insight.pendencias_criticas === 0)) return null;

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    try { localStorage.setItem('leitura-ia-collapsed', String(next)); } catch { /* noop */ }
  };

  return (
    <div className="bg-gradient-to-r from-amber-50 to-orange-50 dark:from-zinc-800 dark:to-zinc-800 rounded-xl border border-amber-200 dark:border-zinc-700 shadow-sm">
      <button
        type="button"
        onClick={toggle}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-lg">
            <Sparkles className="w-5 h-5 text-amber-600 dark:text-amber-400" />
          </div>
          <span className="font-semibold text-gray-900 dark:text-white">Leitura da IA</span>
        </div>
        {collapsed ? (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronUp className="w-5 h-5 text-gray-400" />
        )}
      </button>

      {!collapsed && (
        <div className="px-4 pb-4 -mt-1">
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
            {insight.mensagem.split('**').map((part, i) =>
              i % 2 === 1 ? <strong key={i}>{part}</strong> : <span key={i}>{part}</span>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
