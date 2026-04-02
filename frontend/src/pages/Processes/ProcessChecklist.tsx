/**
 * ProcessChecklist — Sprint 2
 * Painel de checklist documental de um processo.
 * Mostra status por item, permite marcar como recebido / dispensado.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  CheckCircle2, Clock, XCircle, AlertTriangle, RefreshCw,
  ChevronDown, ChevronUp, FileCheck,
} from 'lucide-react';

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface ChecklistItem {
  id: string;
  label: string;
  doc_type: string;
  category: string;
  required: boolean;
  status: 'pending' | 'received' | 'waived';
  document_id: number | null;
  waiver_reason: string | null;
}

interface ChecklistSummary {
  total: number;
  received: number;
  pending: number;
  waived: number;
  completion_pct: number;
  has_required_gaps: boolean;
}

interface Checklist {
  id: number;
  process_id: number;
  template_id: number | null;
  items: ChecklistItem[];
  summary: ChecklistSummary;
  completed_at: string | null;
  created_at: string;
}

interface ProcessChecklistProps {
  processId: number;
}

// ─── Config visual por status ─────────────────────────────────────────────────

const ITEM_STATUS: Record<string, { icon: React.ReactNode; label: string; cls: string }> = {
  received: {
    icon: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
    label: 'Recebido',
    cls: 'border-emerald-500/20 bg-emerald-500/5',
  },
  pending: {
    icon: <Clock className="w-4 h-4 text-yellow-400" />,
    label: 'Pendente',
    cls: 'border-yellow-500/20 bg-yellow-500/5',
  },
  waived: {
    icon: <XCircle className="w-4 h-4 text-slate-500" />,
    label: 'Dispensado',
    cls: 'border-white/5 bg-white/3',
  },
};

const CATEGORY_LABELS: Record<string, string> = {
  ambiental: '🌿 Ambiental',
  fundiario: '🏡 Fundiário',
  pessoal: '👤 Pessoal',
  geoespacial: '🗺️ Geoespacial',
  administrativo: '📋 Administrativo',
  tecnico: '🔧 Técnico',
  bancario: '🏦 Bancário',
};

// ─── Componente ──────────────────────────────────────────────────────────────

export default function ProcessChecklist({ processId }: ProcessChecklistProps) {
  const queryClient = useQueryClient();
  const [waiverItemId, setWaiverItemId] = useState<string | null>(null);
  const [waiverReason, setWaiverReason] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['ambiental', 'fundiario', 'pessoal']));

  // ── Buscar checklist ────────────────────────────────────────────────────────
  const {
    data: checklist,
    isLoading,
    error,
    refetch,
  } = useQuery<Checklist>({
    queryKey: ['checklist', processId],
    queryFn: async () => {
      const res = await api.get(`/processes/${processId}/checklist`);
      return res.data;
    },
    retry: false,
  });

  // ── Gerar checklist ─────────────────────────────────────────────────────────
  const generateMutation = useMutation({
    mutationFn: (force = false) =>
      api.post(`/processes/${processId}/checklist/generate?force=${force}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['checklist', processId] });
    },
  });

  // ── Atualizar item ──────────────────────────────────────────────────────────
  const updateItemMutation = useMutation({
    mutationFn: (payload: { item_id: string; action: string; waiver_reason?: string }) =>
      api.patch(`/processes/${processId}/checklist/items/${payload.item_id}`, {
        action: payload.action,
        waiver_reason: payload.waiver_reason,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['checklist', processId] });
      setWaiverItemId(null);
      setWaiverReason('');
    },
  });

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleReceived = (itemId: string) => {
    updateItemMutation.mutate({ item_id: itemId, action: 'received' });
  };

  const handleWaive = (itemId: string) => {
    if (!waiverReason.trim()) return;
    updateItemMutation.mutate({ item_id: itemId, action: 'waived', waiver_reason: waiverReason });
  };

  const handleRevertPending = (itemId: string) => {
    updateItemMutation.mutate({ item_id: itemId, action: 'pending' });
  };

  const toggleCategory = (cat: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      next.has(cat) ? next.delete(cat) : next.add(cat);
      return next;
    });
  };

  // ── Estado de carregamento ──────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-slate-500 gap-2 text-sm">
        <div className="w-4 h-4 border-2 border-slate-500 border-t-transparent rounded-full animate-spin" />
        Carregando checklist...
      </div>
    );
  }

  // Checklist ainda não foi gerado
  if (error || !checklist) {
    return (
      <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center space-y-4">
        <FileCheck className="w-10 h-10 text-slate-600 mx-auto" />
        <div>
          <p className="text-slate-300 font-medium">Nenhum checklist gerado</p>
          <p className="text-slate-500 text-sm mt-1">
            Gere o checklist baseado no tipo de demanda do processo.
          </p>
        </div>
        <button
          onClick={() => generateMutation.mutate(false)}
          disabled={generateMutation.isPending}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white text-sm font-medium transition-all"
        >
          <RefreshCw className={`w-4 h-4 ${generateMutation.isPending ? 'animate-spin' : ''}`} />
          Gerar Checklist
        </button>
      </div>
    );
  }

  // ── Agrupar itens por categoria ─────────────────────────────────────────────
  const byCategory: Record<string, ChecklistItem[]> = {};
  for (const item of checklist.items) {
    const cat = item.category || 'outros';
    if (!byCategory[cat]) byCategory[cat] = [];
    byCategory[cat].push(item);
  }

  const { summary } = checklist;

  return (
    <div className="space-y-4">

      {/* Header com progresso */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold text-white">Checklist Documental</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {summary.received} de {summary.total} documentos recebidos
              {summary.waived > 0 && ` · ${summary.waived} dispensado(s)`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {summary.has_required_gaps && (
              <span className="flex items-center gap-1 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-1 rounded-full">
                <AlertTriangle className="w-3 h-3" />
                Docs obrigatórios pendentes
              </span>
            )}
            <button
              onClick={() => generateMutation.mutate(true)}
              disabled={generateMutation.isPending}
              title="Regenerar checklist do zero"
              className="p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-white/10 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${generateMutation.isPending ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Barra de progresso */}
        <div className="w-full bg-white/10 rounded-full h-2">
          <div
            className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${summary.completion_pct}%` }}
          />
        </div>
        <p className="text-xs text-slate-500 text-right mt-1">{summary.completion_pct}% completo</p>
      </div>

      {/* Itens agrupados por categoria */}
      {Object.entries(byCategory).map(([category, items]) => (
        <div key={category} className="rounded-2xl bg-white/5 border border-white/10 overflow-hidden">

          {/* Header da categoria */}
          <button
            onClick={() => toggleCategory(category)}
            className="w-full flex items-center justify-between px-5 py-3 hover:bg-white/5 transition-colors"
          >
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              {CATEGORY_LABELS[category] ?? category}
            </span>
            <span className="flex items-center gap-2">
              <span className="text-xs text-slate-500">
                {items.filter(i => i.status === 'received').length}/{items.length}
              </span>
              {expandedCategories.has(category)
                ? <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
                : <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
              }
            </span>
          </button>

          {/* Lista de itens */}
          {expandedCategories.has(category) && (
            <div className="divide-y divide-white/5">
              {items.map(item => {
                const cfg = ITEM_STATUS[item.status];
                const isWaiving = waiverItemId === item.id;

                return (
                  <div key={item.id} className={`px-5 py-3 border-l-2 ${cfg.cls}`}>
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 shrink-0">{cfg.icon}</div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className={`text-sm font-medium ${item.status === 'waived' ? 'text-slate-500 line-through' : 'text-white'}`}>
                            {item.label}
                          </p>
                          {item.required && item.status === 'pending' && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/10 border border-red-500/20 text-red-400">
                              obrigatório
                            </span>
                          )}
                        </div>

                        {item.status === 'waived' && item.waiver_reason && (
                          <p className="text-xs text-slate-600 mt-0.5">Dispensado: {item.waiver_reason}</p>
                        )}

                        {/* Formulário de dispensa inline */}
                        {isWaiving && (
                          <div className="mt-2 flex gap-2">
                            <input
                              autoFocus
                              type="text"
                              placeholder="Motivo da dispensa..."
                              value={waiverReason}
                              onChange={e => setWaiverReason(e.target.value)}
                              className="flex-1 rounded-lg bg-white/5 border border-white/10 text-white placeholder-slate-500 px-3 py-1.5 text-xs focus:outline-none focus:border-yellow-400"
                            />
                            <button
                              onClick={() => handleWaive(item.id)}
                              disabled={!waiverReason.trim() || updateItemMutation.isPending}
                              className="px-3 py-1.5 rounded-lg bg-yellow-500/20 border border-yellow-500/30 text-yellow-300 text-xs font-medium disabled:opacity-40 hover:bg-yellow-500/30 transition-all"
                            >
                              Confirmar
                            </button>
                            <button
                              onClick={() => { setWaiverItemId(null); setWaiverReason(''); }}
                              className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-400 text-xs hover:text-white transition-all"
                            >
                              Cancelar
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Ações */}
                      {!isWaiving && (
                        <div className="flex items-center gap-1.5 shrink-0">
                          {item.status === 'pending' && (
                            <>
                              <button
                                onClick={() => handleReceived(item.id)}
                                disabled={updateItemMutation.isPending}
                                className="px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-medium hover:bg-emerald-500/20 disabled:opacity-40 transition-all"
                              >
                                Recebido
                              </button>
                              <button
                                onClick={() => { setWaiverItemId(item.id); setWaiverReason(''); }}
                                className="px-2.5 py-1 rounded-lg bg-white/5 border border-white/10 text-slate-400 text-xs hover:text-white transition-all"
                              >
                                Dispensar
                              </button>
                            </>
                          )}
                          {(item.status === 'received' || item.status === 'waived') && (
                            <button
                              onClick={() => handleRevertPending(item.id)}
                              disabled={updateItemMutation.isPending}
                              className="px-2.5 py-1 rounded-lg bg-white/5 border border-white/10 text-slate-500 text-xs hover:text-slate-300 disabled:opacity-40 transition-all"
                            >
                              Reverter
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}

    </div>
  );
}
