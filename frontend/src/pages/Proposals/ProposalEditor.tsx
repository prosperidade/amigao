/**
 * ProposalEditor — Criar / editar proposta comercial (Sprint 4)
 * Suporta geração automática de rascunho via process_id.
 */
import { useState, useEffect } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  ArrowLeft, Zap, Plus, Trash2, Send, CheckCircle2, XCircle,
  FileText, Loader2, AlertCircle,
} from 'lucide-react';

interface ScopeItem {
  description: string;
  unit: string;
  qty: number;
  unit_price: number;
  total: number;
}

function fmt(v: number | null | undefined) {
  if (v == null) return '—';
  return `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
}

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  draft:    { label: 'Rascunho',  cls: 'text-slate-400 bg-slate-500/10 border-slate-500/20' },
  sent:     { label: 'Enviada',   cls: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
  accepted: { label: 'Aceita',    cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
  rejected: { label: 'Recusada', cls: 'text-red-400 bg-red-500/10 border-red-500/20' },
  expired:  { label: 'Expirada', cls: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' },
};

export default function ProposalEditor() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isNew = !id || id === 'new';
  const processIdParam = searchParams.get('process_id');

  // Form state
  const [title, setTitle] = useState('');
  const [clientId, setClientId] = useState('');
  const [processId, setProcessId] = useState(processIdParam ?? '');
  const [scopeItems, setScopeItems] = useState<ScopeItem[]>([]);
  const [totalValue, setTotalValue] = useState('');
  const [validityDays, setValidityDays] = useState('30');
  const [paymentTerms, setPaymentTerms] = useState('');
  const [notes, setNotes] = useState('');
  const [draftBanner, setDraftBanner] = useState<any>(null);
  const [saved, setSaved] = useState(false);

  // Buscar proposta existente
  const { data: proposal } = useQuery({
    queryKey: ['proposal', id],
    queryFn: async () => {
      const res = await api.get(`/proposals/${id}`);
      return res.data;
    },
    enabled: !isNew,
  });

  // Preencher form quando carregar
  useEffect(() => {
    if (proposal) {
      setTitle(proposal.title ?? '');
      setClientId(String(proposal.client_id ?? ''));
      setProcessId(String(proposal.process_id ?? ''));
      setScopeItems(proposal.scope_items ?? []);
      setTotalValue(proposal.total_value != null ? String(proposal.total_value) : '');
      setValidityDays(String(proposal.validity_days ?? 30));
      setPaymentTerms(proposal.payment_terms ?? '');
      setNotes(proposal.notes ?? '');
    }
  }, [proposal]);

  // Auto-draft ao montar se process_id passado na URL
  const { data: draftData, isLoading: draftLoading } = useQuery({
    queryKey: ['proposal-draft', processId],
    queryFn: async () => {
      const res = await api.get(`/proposals/generate-draft?process_id=${processId}`);
      return res.data;
    },
    enabled: isNew && !!processId,
  });

  useEffect(() => {
    if (draftData && isNew) {
      setTitle(draftData.title ?? '');
      setScopeItems(draftData.scope_items ?? []);
      setTotalValue(draftData.suggested_value != null ? String(draftData.suggested_value) : '');
      setValidityDays(String(30));
      setPaymentTerms(draftData.payment_terms ?? '');
      setNotes(draftData.notes ?? '');
      setDraftBanner(draftData);
    }
  }, [draftData, isNew]);

  // Mutations
  const saveMutation = useMutation({
    mutationFn: async () => {
      const body = {
        title,
        client_id: parseInt(clientId),
        process_id: processId ? parseInt(processId) : undefined,
        scope_items: scopeItems,
        total_value: totalValue ? parseFloat(totalValue) : undefined,
        validity_days: parseInt(validityDays),
        payment_terms: paymentTerms,
        notes,
      };
      if (isNew) return api.post('/proposals/', body);
      return api.patch(`/proposals/${id}`, body);
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      setSaved(true);
      if (isNew) navigate(`/proposals/${res.data.id}`, { replace: true });
    },
  });

  const sendMutation = useMutation({
    mutationFn: () => api.post(`/proposals/${id}/send`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['proposal', id] }),
  });

  const acceptMutation = useMutation({
    mutationFn: () => api.post(`/proposals/${id}/accept`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['proposal', id] }),
  });

  const rejectMutation = useMutation({
    mutationFn: () => api.post(`/proposals/${id}/reject`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['proposal', id] }),
  });

  const createContractMutation = useMutation({
    mutationFn: () => api.post('/contracts/', {
      client_id: parseInt(clientId),
      proposal_id: parseInt(id!),
      process_id: processId ? parseInt(processId) : undefined,
      title: `Contrato — ${title}`,
    }),
    onSuccess: (res) => navigate(`/contracts/${res.data.id}`),
  });

  const updateScopeItem = (idx: number, field: keyof ScopeItem, value: string | number) => {
    const items = [...scopeItems];
    (items[idx] as any)[field] = value;
    if (field === 'qty' || field === 'unit_price') {
      items[idx].total = items[idx].qty * items[idx].unit_price;
    }
    setScopeItems(items);
    const total = items.reduce((s, i) => s + (i.total || 0), 0);
    if (total > 0) setTotalValue(String(total));
  };

  const addScopeItem = () => {
    setScopeItems([...scopeItems, { description: '', unit: 'serv.', qty: 1, unit_price: 0, total: 0 }]);
  };

  const removeScopeItem = (idx: number) => {
    setScopeItems(scopeItems.filter((_, i) => i !== idx));
  };

  const statusCfg = proposal ? (STATUS_CONFIG[proposal.status] ?? STATUS_CONFIG.draft) : STATUS_CONFIG.draft;
  const isEditable = !proposal || proposal.status === 'draft';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/proposals')}
          className="p-2 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:text-white transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-white">
              {isNew ? 'Nova Proposta' : `Proposta #${id}`}
            </h1>
            {proposal && (
              <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${statusCfg.cls}`}>
                {statusCfg.label}
              </span>
            )}
          </div>
        </div>
        {/* Ações de status */}
        {proposal && proposal.status === 'draft' && (
          <button
            onClick={() => sendMutation.mutate()}
            disabled={sendMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-500 hover:bg-blue-400 text-white text-sm font-medium transition-all disabled:opacity-50"
          >
            {sendMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Enviar ao Cliente
          </button>
        )}
        {proposal && proposal.status === 'sent' && (
          <div className="flex gap-2">
            <button
              onClick={() => acceptMutation.mutate()}
              disabled={acceptMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-medium transition-all disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" /> Aceitar
            </button>
            <button
              onClick={() => rejectMutation.mutate()}
              disabled={rejectMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 text-sm font-medium transition-all disabled:opacity-50"
            >
              <XCircle className="w-4 h-4" /> Recusar
            </button>
          </div>
        )}
        {proposal && proposal.status === 'accepted' && (
          <button
            onClick={() => createContractMutation.mutate()}
            disabled={createContractMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-medium transition-all disabled:opacity-50"
          >
            {createContractMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            Gerar Contrato
          </button>
        )}
      </div>

      {/* Banner rascunho automático */}
      {draftBanner && (
        <div className="rounded-2xl bg-emerald-500/10 border border-emerald-500/25 p-4 flex items-start gap-3">
          <Zap className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-emerald-300">Rascunho gerado automaticamente</p>
            <p className="text-xs text-slate-400 mt-0.5">
              Complexidade: <strong>{draftBanner.complexity}</strong> ·
              Faixa sugerida: <strong>{fmt(draftBanner.suggested_value_min)} — {fmt(draftBanner.suggested_value_max)}</strong> ·
              Prazo: <strong>~{draftBanner.estimated_days} dias</strong>
            </p>
          </div>
        </div>
      )}

      {draftLoading && isNew && processId && (
        <div className="flex items-center gap-2 text-slate-400 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" /> Gerando rascunho automático...
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Coluna principal */}
        <div className="md:col-span-2 space-y-4">
          {/* Título */}
          <div className="rounded-2xl bg-white/5 border border-white/10 p-5 space-y-4">
            <h2 className="text-sm font-semibold text-slate-200">Informações Gerais</h2>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Título da Proposta</label>
              <input
                value={title}
                onChange={e => setTitle(e.target.value)}
                disabled={!isEditable}
                placeholder="Ex: Proposta — CAR Fazenda São João"
                className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-400 disabled:opacity-50 transition-colors"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">ID do Cliente</label>
                <input
                  value={clientId}
                  onChange={e => setClientId(e.target.value)}
                  disabled={!isEditable}
                  placeholder="client_id"
                  type="number"
                  className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-400 disabled:opacity-50 transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">ID do Processo (opcional)</label>
                <input
                  value={processId}
                  onChange={e => setProcessId(e.target.value)}
                  disabled={!isEditable}
                  placeholder="process_id"
                  type="number"
                  className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-400 disabled:opacity-50 transition-colors"
                />
              </div>
            </div>
          </div>

          {/* Escopo */}
          <div className="rounded-2xl bg-white/5 border border-white/10 p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200">Itens de Escopo</h2>
              {isEditable && (
                <button
                  onClick={addScopeItem}
                  className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" /> Adicionar item
                </button>
              )}
            </div>

            {scopeItems.length === 0 ? (
              <p className="text-xs text-slate-500 py-4 text-center">Nenhum item no escopo.</p>
            ) : (
              <div className="space-y-2">
                {/* Cabeçalho */}
                <div className="grid grid-cols-12 gap-2 text-xs text-slate-500 px-1">
                  <span className="col-span-6">Descrição</span>
                  <span className="col-span-2 text-center">Qtd</span>
                  <span className="col-span-2 text-right">Vlr Unit.</span>
                  <span className="col-span-2 text-right">Total</span>
                </div>
                {scopeItems.map((item, idx) => (
                  <div key={idx} className="grid grid-cols-12 gap-2 items-center bg-white/3 rounded-xl p-2">
                    <input
                      value={item.description}
                      onChange={e => updateScopeItem(idx, 'description', e.target.value)}
                      disabled={!isEditable}
                      placeholder="Descrição do serviço"
                      className="col-span-6 bg-transparent border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-emerald-400 disabled:opacity-50"
                    />
                    <input
                      value={item.qty}
                      onChange={e => updateScopeItem(idx, 'qty', parseFloat(e.target.value) || 0)}
                      disabled={!isEditable}
                      type="number"
                      min="0"
                      className="col-span-2 bg-transparent border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white text-center focus:outline-none focus:border-emerald-400 disabled:opacity-50"
                    />
                    <input
                      value={item.unit_price}
                      onChange={e => updateScopeItem(idx, 'unit_price', parseFloat(e.target.value) || 0)}
                      disabled={!isEditable}
                      type="number"
                      min="0"
                      className="col-span-2 bg-transparent border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white text-right focus:outline-none focus:border-emerald-400 disabled:opacity-50"
                    />
                    <div className="col-span-1 text-xs text-emerald-400 text-right font-medium">
                      {item.total > 0 ? item.total.toLocaleString('pt-BR', { minimumFractionDigits: 0 }) : '—'}
                    </div>
                    {isEditable && (
                      <button onClick={() => removeScopeItem(idx)} className="col-span-1 text-slate-600 hover:text-red-400 flex justify-center">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Observações */}
          <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
            <h2 className="text-sm font-semibold text-slate-200 mb-3">Observações</h2>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              disabled={!isEditable}
              rows={3}
              placeholder="Notas, ressalvas, condições especiais..."
              className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-3 text-sm focus:outline-none focus:border-emerald-400 resize-none disabled:opacity-50 transition-colors"
            />
          </div>
        </div>

        {/* Coluna lateral */}
        <div className="space-y-4">
          <div className="rounded-2xl bg-white/5 border border-white/10 p-5 space-y-4">
            <h2 className="text-sm font-semibold text-slate-200">Valores e Prazo</h2>

            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Valor Total (R$)</label>
              <input
                value={totalValue}
                onChange={e => setTotalValue(e.target.value)}
                disabled={!isEditable}
                type="number"
                min="0"
                placeholder="0,00"
                className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-400 disabled:opacity-50 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Validade (dias)</label>
              <input
                value={validityDays}
                onChange={e => setValidityDays(e.target.value)}
                disabled={!isEditable}
                type="number"
                min="1"
                className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-400 disabled:opacity-50 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Condições de Pagamento</label>
              <textarea
                value={paymentTerms}
                onChange={e => setPaymentTerms(e.target.value)}
                disabled={!isEditable}
                rows={3}
                className="w-full rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-400 resize-none disabled:opacity-50 transition-colors"
              />
            </div>

            {/* Total calculado */}
            {totalValue && (
              <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3 text-center">
                <p className="text-xs text-slate-400">Valor Total</p>
                <p className="text-xl font-bold text-emerald-400 mt-0.5">
                  {fmt(parseFloat(totalValue))}
                </p>
              </div>
            )}
          </div>

          {/* Salvar */}
          {isEditable && (
            <button
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || !title || !clientId}
              className="w-full py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-white font-medium text-sm transition-all flex items-center justify-center gap-2"
            >
              {saveMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {isNew ? 'Criar Proposta' : 'Salvar Alterações'}
            </button>
          )}

          {saved && !isNew && (
            <p className="text-xs text-emerald-400 text-center">✓ Salvo com sucesso</p>
          )}

          {saveMutation.isError && (
            <div className="flex items-center gap-2 text-red-400 text-xs">
              <AlertCircle className="w-3.5 h-3.5" /> Erro ao salvar proposta.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
