/**
 * ProcessCommercial — Aba Comercial do processo (Sprint 4)
 * Mostra propostas e contratos vinculados, com atalhos de ação.
 */
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { Plus, FileText, ExternalLink, Send, CheckCircle2, XCircle, AlertCircle, RotateCcw } from 'lucide-react';

interface Proposal {
  id: number;
  title: string;
  status: string;
  effective_status?: string;
  version_number?: number;
  previous_version_id?: number | null;
  created_at: string;
  complexity?: string;
  total_value?: number | null;
}

function errDetail(e: unknown, fallback: string): string {
  const ax = e as AxiosError<{ detail?: string }>;
  return ax?.response?.data?.detail ?? ax?.message ?? fallback;
}

interface Contract {
  id: number;
  title: string;
  status: string;
  created_at: string;
  proposal_id?: number | null;
  has_pdf?: boolean;
}

interface ProcessCommercialProps {
  processId: number;
}

const PROPOSAL_STATUS: Record<string, { label: string; cls: string; icon: typeof FileText }> = {
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
  const qc = useQueryClient();

  const { data: proposals = [], isLoading: loadingProposals } = useQuery({
    queryKey: ['proposals', processId],
    queryFn: async () => {
      const res = await api.get(`/proposals/?process_id=${processId}`);
      return res.data as Proposal[];
    },
  });

  // S5-A — ações da máquina de estados direto na aba Comercial (funcional).
  const refresh = () => qc.invalidateQueries({ queryKey: ['proposals', processId] });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: number; action: string }) =>
      api.post(`/proposals/${id}/${action}`, action === 'reject' ? {} : undefined).then(r => r.data),
    onSuccess: (_d, v) => {
      refresh();
      const msg: Record<string, string> = {
        send: 'Proposta enviada ao cliente.',
        accept: 'Proposta aceita — libera a geração do contrato (E7).',
        reject: 'Proposta recusada.',
        'nova-versao': 'Nova versão criada em rascunho (renegociação).',
      };
      toast.success(msg[v.action] ?? 'Feito.');
    },
    onError: (e) => toast.error(errDetail(e, 'Não foi possível concluir a ação.')),
  });
  const doAct = (id: number, action: string) => act.mutate({ id, action });

  // S5-B — gera o contrato a partir da proposta ACEITA, direto na aba (mesmo
  // POST /contracts/gerar do ProposalEditor). 422 = bloqueio honesto (perfil do
  // tenant incompleto, valores/ matrícula) — vem como toast, não some calado.
  const gerarContrato = useMutation({
    mutationFn: (proposalId: number) =>
      api.post('/contracts/gerar', { proposal_id: proposalId }).then(r => r.data),
    onSuccess: (data: { contract: { id: number } }) => {
      qc.invalidateQueries({ queryKey: ['contracts', processId] });
      toast.success('Contrato gerado a partir da proposta.');
      navigate(`/contracts/${data.contract.id}`);
    },
    onError: (e) => toast.error(errDetail(e, 'Não foi possível gerar o contrato.')),
  });

  const { data: contracts = [], isLoading: loadingContracts } = useQuery({
    queryKey: ['contracts', processId],
    queryFn: async () => {
      const res = await api.get(`/contracts/?process_id=${processId}`);
      return res.data as Contract[];
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
            {proposals.map((p) => {
              // S5-A — o badge reflete o estado EFETIVO (expirada é derivada no read).
              const eff = p.effective_status ?? p.status;
              const cfg = PROPOSAL_STATUS[eff] ?? PROPOSAL_STATUS.draft;
              const Icon = cfg.icon;
              const busy = act.isPending;
              return (
                <div
                  key={p.id}
                  className="flex items-center gap-4 p-4 rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/5 hover:border-gray-200 dark:hover:border-white/15 hover:shadow-sm dark:hover:shadow-none transition-all"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-800 dark:text-white truncate">
                      {p.title}
                      {(p.version_number ?? 1) > 1 && (
                        <span className="ml-1.5 text-xs font-normal text-gray-400">v{p.version_number}</span>
                      )}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
                      #{p.id} · {new Date(p.created_at).toLocaleDateString('pt-BR')}
                      {p.complexity && ` · Complexidade: ${p.complexity}`}
                      {p.previous_version_id && ` · renegociação de #${p.previous_version_id}`}
                    </p>
                  </div>
                  <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400 shrink-0">{fmt(p.total_value)}</span>
                  <span className={`flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border shrink-0 ${cfg.cls}`}>
                    <Icon className="w-3 h-3" /> {cfg.label}
                  </span>
                  {/* Ações da máquina de estados (S5-A) */}
                  <div className="flex items-center gap-1 shrink-0">
                    {eff === 'draft' && (
                      <button disabled={busy} onClick={() => doAct(p.id, 'send')}
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white">
                        <Send className="w-3 h-3" /> Enviar
                      </button>
                    )}
                    {eff === 'sent' && (
                      <>
                        <button disabled={busy} onClick={() => doAct(p.id, 'accept')}
                          className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white">
                          <CheckCircle2 className="w-3 h-3" /> Aceitar
                        </button>
                        <button disabled={busy} onClick={() => doAct(p.id, 'reject')}
                          className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-red-200 dark:border-red-500/30 text-red-600 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-500/10">
                          <XCircle className="w-3 h-3" /> Recusar
                        </button>
                      </>
                    )}
                    {eff === 'accepted' && (
                      <button disabled={gerarContrato.isPending} onClick={() => gerarContrato.mutate(p.id)}
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white">
                        <FileText className="w-3 h-3" /> Gerar Contrato
                      </button>
                    )}
                    {(eff === 'rejected' || eff === 'expired') && (
                      <button disabled={busy} onClick={() => doAct(p.id, 'nova-versao')}
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-200 dark:border-white/10 text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-white/10">
                        <RotateCcw className="w-3 h-3" /> Nova versão
                      </button>
                    )}
                  </div>
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
            {contracts.map((c) => {
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
