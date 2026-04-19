/**
 * DecisionsTab — Aba de Decisões do Workspace (Regente Sprint E).
 *
 * Lista decisões críticas do caso + formulário de criar nova.
 * Baseado em `CAMADA 3 - WORKSPACE EDIT1.pdf` da sócia — transforma análise
 * em governança auditável.
 */
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';
import {
  Plus, Scale, User, Calendar, ArrowRight, Trash2, Edit3, X,
  AlertCircle, Save, ChevronDown, FileText,
} from 'lucide-react';
import { api } from '@/lib/api';
import { MACROETAPA_LABELS } from './quadro-types';

// ─── Tipos ────────────────────────────────────────────────────────────────────

type DecisionType =
  | 'triagem' | 'documental' | 'tecnica' | 'regulatoria'
  | 'comercial' | 'contratual' | 'bloqueio' | 'avanco_etapa';

type DecisionStatus = 'proposta' | 'validada' | 'revisada' | 'substituida';

interface Decision {
  id: number;
  tenant_id: number;
  process_id: number;
  macroetapa: string;
  decision_type: DecisionType | string;
  decision_text: string;
  justification: string | null;
  basis: Record<string, unknown> | null;
  decided_by_user_id: number | null;
  decided_by_user_name: string | null;
  decided_at: string | null;
  impact: string | null;
  next_step: string | null;
  status: DecisionStatus | string;
  supersedes_decision_id: number | null;
  created_at: string;
  updated_at: string | null;
}

interface CreatePayload {
  macroetapa: string;
  decision_type: DecisionType;
  decision_text: string;
  justification?: string;
  impact?: string;
  next_step?: string;
  status?: DecisionStatus;
}

// ─── Constantes (frontend-local — evita roundtrip) ───────────────────────────

const DECISION_TYPE_LABELS: Record<string, string> = {
  triagem: 'Triagem',
  documental: 'Documental',
  tecnica: 'T\u00e9cnica',
  regulatoria: 'Regulat\u00f3ria',
  comercial: 'Comercial',
  contratual: 'Contratual',
  bloqueio: 'Bloqueio',
  avanco_etapa: 'Avan\u00e7o de etapa',
};

const DECISION_TYPE_COLORS: Record<string, string> = {
  triagem:      'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300',
  documental:   'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  tecnica:      'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300',
  regulatoria:  'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
  comercial:    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  contratual:   'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300',
  bloqueio:     'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  avanco_etapa: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
};

const DECISION_STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  proposta:    { label: 'Proposta',    cls: 'bg-gray-100 text-gray-600 dark:bg-zinc-800 dark:text-gray-400' },
  validada:    { label: 'Validada',    cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
  revisada:    { label: 'Revisada',    cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  substituida: { label: 'Substitu\u00edda', cls: 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-400 line-through' },
};

const DECISION_TYPES: DecisionType[] = [
  'triagem', 'documental', 'tecnica', 'regulatoria',
  'comercial', 'contratual', 'bloqueio', 'avanco_etapa',
];

const MACROETAPAS: string[] = [
  'entrada_demanda', 'diagnostico_preliminar', 'coleta_documental',
  'diagnostico_tecnico', 'caminho_regulatorio', 'orcamento_negociacao',
  'contrato_formalizacao',
];

// ─── Componente ───────────────────────────────────────────────────────────────

interface Props {
  processId: number;
  /** Macroetapa atual do caso — pré-preenche o form. */
  currentMacroetapa?: string;
}

export default function DecisionsTab({ processId, currentMacroetapa }: Props) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [filterType, setFilterType] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');

  const { data: decisions = [], isLoading } = useQuery({
    queryKey: ['decisions', processId, filterType, filterStatus],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filterType) params.set('decision_type', filterType);
      if (filterStatus) params.set('status', filterStatus);
      const qs = params.toString();
      return api.get<Decision[]>(
        `/processes/${processId}/decisions${qs ? `?${qs}` : ''}`,
      ).then(r => r.data);
    },
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['decisions', processId] });
    queryClient.invalidateQueries({ queryKey: ['decision-latest', processId] });
    queryClient.invalidateQueries({ queryKey: ['kanban'] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: CreatePayload) =>
      api.post(`/processes/${processId}/decisions`, payload),
    onSuccess: () => {
      toast.success('Decis\u00e3o registrada');
      setCreating(false);
      invalidate();
    },
    onError: (err: AxiosError<{ detail?: string }>) => {
      toast.error(err.response?.data?.detail ?? 'Erro ao registrar decis\u00e3o');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<CreatePayload> }) =>
      api.patch(`/processes/${processId}/decisions/${id}`, payload),
    onSuccess: () => {
      toast.success('Decis\u00e3o atualizada');
      setEditingId(null);
      invalidate();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      api.delete(`/processes/${processId}/decisions/${id}`),
    onSuccess: () => {
      toast.success('Decis\u00e3o removida');
      invalidate();
    },
  });

  return (
    <div className="space-y-4">
      {/* Cabeçalho */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Scale className="w-5 h-5 text-emerald-600" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Decis\u00f5es do caso
          </h2>
          <span className="text-xs text-gray-500">{decisions.length} registrada{decisions.length !== 1 ? 's' : ''}</span>
        </div>
        <button
          type="button"
          onClick={() => setCreating(c => !c)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow-sm shadow-emerald-500/20 transition-colors"
        >
          {creating ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          {creating ? 'Cancelar' : 'Nova decis\u00e3o'}
        </button>
      </div>

      {/* Filtros */}
      {!creating && decisions.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 dark:text-zinc-200"
          >
            <option value="">Tipo (todos)</option>
            {DECISION_TYPES.map(t => (
              <option key={t} value={t}>{DECISION_TYPE_LABELS[t]}</option>
            ))}
          </select>
          <select
            value={filterStatus}
            onChange={e => setFilterStatus(e.target.value)}
            className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 dark:text-zinc-200"
          >
            <option value="">Status (todos)</option>
            {Object.keys(DECISION_STATUS_CONFIG).map(s => (
              <option key={s} value={s}>{DECISION_STATUS_CONFIG[s].label}</option>
            ))}
          </select>
        </div>
      )}

      {/* Formulário de criar */}
      {creating && (
        <DecisionForm
          defaultMacroetapa={currentMacroetapa ?? 'entrada_demanda'}
          onSubmit={p => createMutation.mutate(p)}
          onCancel={() => setCreating(false)}
          submitting={createMutation.isPending}
        />
      )}

      {/* Lista */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 bg-gray-100 dark:bg-zinc-800/50 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : decisions.length === 0 && !creating ? (
        <EmptyState onCreate={() => setCreating(true)} />
      ) : (
        <ul className="space-y-3">
          {decisions.map(d => (
            <DecisionCard
              key={d.id}
              decision={d}
              editing={editingId === d.id}
              onEdit={() => setEditingId(d.id)}
              onCancelEdit={() => setEditingId(null)}
              onSave={payload => updateMutation.mutate({ id: d.id, payload })}
              onDelete={() => {
                if (confirm('Remover esta decis\u00e3o? A a\u00e7\u00e3o pode ser desfeita manualmente pelo administrador.')) {
                  deleteMutation.mutate(d.id);
                }
              }}
              submitting={updateMutation.isPending || deleteMutation.isPending}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

// ─── Subcomponentes ───────────────────────────────────────────────────────────

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="text-center py-12 border-2 border-dashed border-gray-200 dark:border-zinc-700 rounded-xl">
      <Scale className="w-10 h-10 text-gray-300 dark:text-zinc-600 mx-auto mb-3" />
      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Nenhuma decis\u00e3o registrada ainda</p>
      <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
        Registre escolhas cr\u00edticas que mudam o rumo do caso: hip\u00f3tese validada, rota regulat\u00f3ria,
        ajustes de escopo, bloqueios e aceites formais.
      </p>
      <button
        type="button"
        onClick={onCreate}
        className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold"
      >
        <Plus className="w-4 h-4" /> Registrar primeira decis\u00e3o
      </button>
    </div>
  );
}

interface FormProps {
  defaultMacroetapa: string;
  initial?: Partial<CreatePayload>;
  onSubmit: (payload: CreatePayload) => void;
  onCancel: () => void;
  submitting: boolean;
}

function DecisionForm({ defaultMacroetapa, initial, onSubmit, onCancel, submitting }: FormProps) {
  const [macroetapa, setMacroetapa] = useState(initial?.macroetapa ?? defaultMacroetapa);
  const [decisionType, setDecisionType] = useState<DecisionType>(initial?.decision_type ?? 'tecnica');
  const [decisionText, setDecisionText] = useState(initial?.decision_text ?? '');
  const [justification, setJustification] = useState(initial?.justification ?? '');
  const [impact, setImpact] = useState(initial?.impact ?? '');
  const [nextStep, setNextStep] = useState(initial?.next_step ?? '');
  const [status, setStatus] = useState<DecisionStatus>(initial?.status ?? 'validada');

  const submit = () => {
    if (!decisionText.trim() || decisionText.trim().length < 3) {
      toast.error('Descreva a decis\u00e3o com ao menos 3 caracteres.');
      return;
    }
    onSubmit({
      macroetapa,
      decision_type: decisionType,
      decision_text: decisionText.trim(),
      justification: justification.trim() || undefined,
      impact: impact.trim() || undefined,
      next_step: nextStep.trim() || undefined,
      status,
    });
  };

  return (
    <div className="rounded-2xl border border-emerald-200 dark:border-emerald-500/30 bg-emerald-50/30 dark:bg-emerald-500/5 p-5 space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Field label="Etapa">
          <select
            value={macroetapa}
            onChange={e => setMacroetapa(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          >
            {MACROETAPAS.map(m => (
              <option key={m} value={m}>{MACROETAPA_LABELS[m] ?? m}</option>
            ))}
          </select>
        </Field>
        <Field label="Tipo">
          <select
            value={decisionType}
            onChange={e => setDecisionType(e.target.value as DecisionType)}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          >
            {DECISION_TYPES.map(t => (
              <option key={t} value={t}>{DECISION_TYPE_LABELS[t]}</option>
            ))}
          </select>
        </Field>
        <Field label="Status">
          <select
            value={status}
            onChange={e => setStatus(e.target.value as DecisionStatus)}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200"
          >
            <option value="proposta">Proposta (aguarda valida\u00e7\u00e3o)</option>
            <option value="validada">Validada</option>
          </select>
        </Field>
      </div>

      <Field label="Decis\u00e3o tomada" required>
        <textarea
          value={decisionText}
          onChange={e => setDecisionText(e.target.value)}
          placeholder="Ex: adotar licen\u00e7a corretiva como rota principal"
          rows={2}
          className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200 resize-y"
        />
      </Field>

      <Field label="Justificativa">
        <textarea
          value={justification}
          onChange={e => setJustification(e.target.value)}
          placeholder="Por que esta decis\u00e3o foi tomada? (evid\u00eancias, leituras IA, conversas)"
          rows={3}
          className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200 resize-y"
        />
      </Field>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="Impacto no caso">
          <textarea
            value={impact}
            onChange={e => setImpact(e.target.value)}
            placeholder="O que muda daqui pra frente?"
            rows={2}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200 resize-y"
          />
        </Field>
        <Field label="Pr\u00f3ximo passo gerado">
          <textarea
            value={nextStep}
            onChange={e => setNextStep(e.target.value)}
            placeholder="Ex: solicitar planta georreferenciada atualizada"
            rows={2}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-zinc-200 resize-y"
          />
        </Field>
      </div>

      <div className="flex items-center justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          disabled={submitting}
          className="px-4 py-2 rounded-lg text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-zinc-800"
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={submitting || !decisionText.trim()}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {submitting ? 'Salvando...' : 'Salvar decis\u00e3o'}
        </button>
      </div>
    </div>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
        {label} {required && <span className="text-red-500">*</span>}
      </span>
      {children}
    </label>
  );
}

interface CardProps {
  decision: Decision;
  editing: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSave: (payload: Partial<CreatePayload>) => void;
  onDelete: () => void;
  submitting: boolean;
}

function DecisionCard({ decision: d, editing, onEdit, onCancelEdit, onSave, onDelete, submitting }: CardProps) {
  const [expanded, setExpanded] = useState(false);

  if (editing) {
    return (
      <li>
        <DecisionForm
          defaultMacroetapa={d.macroetapa}
          initial={{
            macroetapa: d.macroetapa,
            decision_type: d.decision_type as DecisionType,
            decision_text: d.decision_text,
            justification: d.justification ?? undefined,
            impact: d.impact ?? undefined,
            next_step: d.next_step ?? undefined,
            status: d.status as DecisionStatus,
          }}
          onSubmit={onSave}
          onCancel={onCancelEdit}
          submitting={submitting}
        />
      </li>
    );
  }

  const typeColor = DECISION_TYPE_COLORS[d.decision_type] ?? 'bg-gray-100 text-gray-700';
  const statusBadge = DECISION_STATUS_CONFIG[d.status] ?? { label: d.status, cls: '' };
  const etapaLabel = MACROETAPA_LABELS[d.macroetapa] ?? d.macroetapa;
  const hasDetails = !!(d.justification || d.impact || d.next_step);

  return (
    <li className="rounded-2xl border border-gray-100 dark:border-zinc-800 bg-white dark:bg-white/5 p-4 hover:border-gray-200 dark:hover:border-zinc-700 transition-colors">
      {/* Topo */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${typeColor}`}>
              {DECISION_TYPE_LABELS[d.decision_type] ?? d.decision_type}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusBadge.cls}`}>
              {statusBadge.label}
            </span>
            <span className="text-xs text-gray-500">\u00b7</span>
            <span className="text-xs text-gray-500">{etapaLabel}</span>
          </div>
          <p className="mt-2 text-sm text-gray-900 dark:text-gray-100 leading-relaxed">
            {d.decision_text}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={onEdit}
            title="Editar"
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-zinc-800"
          >
            <Edit3 className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            title="Remover (soft delete)"
            className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Metadata */}
      <div className="mt-3 flex items-center gap-3 flex-wrap text-xs text-gray-500">
        {d.decided_by_user_name && (
          <span className="flex items-center gap-1"><User className="w-3 h-3" />{d.decided_by_user_name}</span>
        )}
        {d.decided_at && (
          <span className="flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            {new Date(d.decided_at).toLocaleDateString('pt-BR')}
          </span>
        )}
        {hasDetails && (
          <button
            type="button"
            onClick={() => setExpanded(e => !e)}
            className="flex items-center gap-1 text-emerald-600 hover:text-emerald-500"
          >
            <ChevronDown className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            {expanded ? 'Recolher' : 'Ver detalhes'}
          </button>
        )}
      </div>

      {/* Detalhes expandidos */}
      {expanded && hasDetails && (
        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-zinc-800 space-y-3 text-sm">
          {d.justification && (
            <DetailRow icon={FileText} label="Justificativa" value={d.justification} />
          )}
          {d.impact && (
            <DetailRow icon={AlertCircle} label="Impacto no caso" value={d.impact} />
          )}
          {d.next_step && (
            <DetailRow icon={ArrowRight} label="Pr\u00f3ximo passo" value={d.next_step} />
          )}
        </div>
      )}
    </li>
  );
}

function DetailRow({ icon: Icon, label, value }: { icon: typeof FileText; label: string; value: string }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider font-semibold text-gray-500 dark:text-gray-400 mb-1">
        <Icon className="w-3 h-3" />
        {label}
      </div>
      <p className="text-sm text-gray-700 dark:text-gray-200 leading-relaxed">{value}</p>
    </div>
  );
}
