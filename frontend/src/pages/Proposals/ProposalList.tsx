/**
 * ProposalList — Lista de propostas comerciais (Sprint 4)
 */
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Plus, FileText, CheckCircle2, XCircle, Send, AlertCircle } from 'lucide-react';

const STATUS_CONFIG: Record<string, { label: string; cls: string; icon: any }> = {
  draft:    { label: 'Rascunho',  cls: 'text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-500/10 border-slate-300 dark:border-slate-500/20', icon: FileText },
  sent:     { label: 'Enviada',   cls: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20', icon: Send },
  accepted: { label: 'Aceita',    cls: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20', icon: CheckCircle2 },
  rejected: { label: 'Recusada', cls: 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20', icon: XCircle },
  expired:  { label: 'Expirada', cls: 'text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-500/10 border-yellow-200 dark:border-yellow-500/20', icon: AlertCircle },
};

function fmt(value: number | null | undefined) {
  if (value == null) return 'A combinar';
  return `R$ ${value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function ProposalList() {
  const navigate = useNavigate();

  const { data: proposals = [], isLoading } = useQuery({
    queryKey: ['proposals'],
    queryFn: async () => {
      const res = await api.get('/proposals/?limit=100');
      return res.data as any[];
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const stats = {
    total: proposals.length,
    draft: proposals.filter(p => p.status === 'draft').length,
    sent: proposals.filter(p => p.status === 'sent').length,
    accepted: proposals.filter(p => p.status === 'accepted').length,
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Propostas Comerciais</h1>
          <p className="text-gray-500 dark:text-slate-400 text-sm mt-1">{stats.total} proposta(s) no total</p>
        </div>
        <button
          onClick={() => navigate('/proposals/new')}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white font-medium text-sm transition-all"
        >
          <Plus className="w-4 h-4" /> Nova Proposta
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Total',      value: stats.total,    cls: 'text-gray-900 dark:text-white' },
          { label: 'Rascunhos',  value: stats.draft,    cls: 'text-gray-500 dark:text-slate-400' },
          { label: 'Enviadas',   value: stats.sent,     cls: 'text-blue-600 dark:text-blue-400' },
          { label: 'Aceitas',    value: stats.accepted, cls: 'text-emerald-600 dark:text-emerald-400' },
        ].map(s => (
          <div key={s.label} className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/5 p-4 text-center">
            <p className={`text-2xl font-bold ${s.cls}`}>{s.value}</p>
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Lista */}
      {proposals.length === 0 ? (
        <div className="rounded-2xl bg-white dark:bg-white/5 border border-dashed border-gray-200 dark:border-white/10 p-12 text-center">
          <FileText className="w-10 h-10 text-gray-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-slate-400 text-sm">Nenhuma proposta criada ainda.</p>
          <button
            onClick={() => navigate('/proposals/new')}
            className="mt-4 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-medium transition-all"
          >
            Criar primeira proposta
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {proposals.map((p: any) => {
            const cfg = STATUS_CONFIG[p.status] ?? STATUS_CONFIG.draft;
            const Icon = cfg.icon;
            return (
              <div
                key={p.id}
                onClick={() => navigate(`/proposals/${p.id}`)}
                className="flex items-center gap-4 p-4 rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/5 hover:border-gray-300 dark:hover:border-white/15 hover:shadow-sm cursor-pointer transition-all"
              >
                <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center shrink-0">
                  <FileText className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{p.title}</p>
                  <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
                    #{p.id}
                    {p.process_id && ` · Processo #${p.process_id}`}
                    {' · '}{new Date(p.created_at).toLocaleDateString('pt-BR')}
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">{fmt(p.total_value)}</span>
                  <span className={`flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${cfg.cls}`}>
                    <Icon className="w-3 h-3" /> {cfg.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
