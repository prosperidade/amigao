/**
 * ProcessCommercial — Aba Comercial do processo (Sprint 4)
 * Mostra propostas e contratos vinculados, com atalhos de ação.
 */
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Plus, FileText, ExternalLink, Send, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

interface ProcessCommercialProps {
  processId: number;
}

const PROPOSAL_STATUS: Record<string, { label: string; cls: string; icon: any }> = {
  draft:    { label: 'Rascunho',  cls: 'text-gray-500 dark:text-slate-400 bg-gray-100 dark:bg-slate-500/10 border-gray-300 dark:border-slate-500/20',       icon: FileText },
  sent:     { label: 'Enviada',   cls: 'text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20',           icon: Send },
  accepted: { label: 'Aceita',    cls: 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20', icon: CheckCircle2 },
  rejected: { label: 'Recusada', cls: 'text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20',                 icon: XCircle },
  expired:  { label: 'Expirada', cls: 'text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-500/10 border-yellow-200 dark:border-yellow-500/20', icon: AlertCircle },
};

const CONTRACT_STATUS: Record<string, { label: string; cls: string }> = {
  draft:     { label: 'Rascunho',  cls: 'text-gray-500 dark:text-slate-400 bg-gray-100 dark:bg-slate-500/10 border-gray-300 dark:border-slate-500/20' },
  sent:      { label: 'Enviado',   cls: 'text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20' },
  signed:    { label: 'Assinado', cls: 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20' },
  cancelled: { label: 'Cancelado', cls: 'text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20' },
};

function fmt(v: number | null | undefined) {
  if (v == null) return 'A combinar';
  return `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
}

export default function ProcessCommercial({ processId }: ProcessCommercialProps) {
  const navigate = useNavigate();

  const { data: proposals = [], isLoading: loadingProposals } = useQuery({
    queryKey: ['proposals', processId],
    queryFn: async () => {
      const res = await api.get(`/proposals/?process_id=${processId}`);
      return res.data as any[];
    },
  });

  const { data: contracts = [], isLoading: loadingContracts } = useQuery({
    queryKey: ['contracts', processId],
    queryFn: async () => {
      const res = await api.get(`/contracts/?process_id=${processId}`);
      return res.data as any[];
    },
  });

  const isLoading = loadingProposals || loadingContracts;

  if (isLoading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-8 rounded-xl bg-gray-100 dark:bg-white/5 w-32" />
        <div className="h-20 rounded-xl bg-gray-100 dark:bg-white/5" />
        <div className="h-20 rounded-xl bg-gray-100 dark:bg-white/5" />
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* ── Propostas ──────────────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200">Propostas</h2>
          <button
            onClick={() => navigate(`/proposals/new?process_id=${processId}`)}
            className="flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-300 px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 transition-all"
          >
            <Plus className="w-3.5 h-3.5" /> Nova Proposta
          </button>
        </div>

        {proposals.length === 0 ? (
          <div className="rounded-2xl bg-gray-50 dark:bg-white/5 border border-dashed border-gray-200 dark:border-white/10 p-8 text-center">
            <FileText className="w-8 h-8 text-gray-300 dark:text-slate-600 mx-auto mb-2" />
            <p className="text-gray-400 dark:text-slate-500 text-sm">Nenhuma proposta gerada ainda.</p>
            <button
              onClick={() => navigate(`/proposals/new?process_id=${processId}`)}
              className="mt-3 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-medium transition-all"
            >
              Gerar Proposta Automática
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {proposals.map((p: any) => {
              const cfg = PROPOSAL_STATUS[p.status] ?? PROPOSAL_STATUS.draft;
              const Icon = cfg.icon;
              return (
                <div
                  key={p.id}
                  className="flex items-center gap-4 p-4 rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/5 hover:border-gray-200 dark:hover:border-white/15 hover:shadow-sm dark:hover:shadow-none transition-all"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-800 dark:text-white truncate">{p.title}</p>
                    <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
                      #{p.id} · {new Date(p.created_at).toLocaleDateString('pt-BR')}
                      {p.complexity && ` · Complexidade: ${p.complexity}`}
                    </p>
                  </div>
                  <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400 shrink-0">{fmt(p.total_value)}</span>
                  <span className={`flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border shrink-0 ${cfg.cls}`}>
                    <Icon className="w-3 h-3" /> {cfg.label}
                  </span>
                  <button
                    onClick={() => navigate(`/proposals/${p.id}`)}
                    className="p-1.5 rounded-lg text-gray-400 dark:text-slate-400 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 transition-all shrink-0"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Contratos ──────────────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200">Contratos</h2>
        </div>

        {contracts.length === 0 ? (
          <div className="rounded-2xl bg-gray-50 dark:bg-white/5 border border-dashed border-gray-200 dark:border-white/10 p-6 text-center">
            <p className="text-gray-400 dark:text-slate-500 text-sm">Nenhum contrato gerado.</p>
            <p className="text-gray-300 dark:text-slate-600 text-xs mt-1">
              Aceite uma proposta e clique em "Gerar Contrato" para criar o contrato automaticamente.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {contracts.map((c: any) => {
              const cfg = CONTRACT_STATUS[c.status] ?? CONTRACT_STATUS.draft;
              return (
                <div
                  key={c.id}
                  className="flex items-center gap-4 p-4 rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/5 hover:border-gray-200 dark:hover:border-white/15 hover:shadow-sm dark:hover:shadow-none transition-all"
                >
                  <div className="w-9 h-9 rounded-lg bg-indigo-50 dark:bg-indigo-500/15 flex items-center justify-center shrink-0">
                    <FileText className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-800 dark:text-white truncate">{c.title}</p>
                    <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
                      #{c.id}
                      {c.proposal_id && ` · Proposta #${c.proposal_id}`}
                      {' · '}{new Date(c.created_at).toLocaleDateString('pt-BR')}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {c.has_pdf && (
                      <span className="text-xs text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 px-2 py-0.5 rounded-full">
                        PDF ✓
                      </span>
                    )}
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${cfg.cls}`}>
                      {cfg.label}
                    </span>
                    <button
                      onClick={() => navigate(`/contracts/${c.id}`)}
                      className="p-1.5 rounded-lg text-gray-400 dark:text-slate-400 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 transition-all"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
