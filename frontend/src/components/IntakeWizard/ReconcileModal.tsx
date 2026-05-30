/**
 * ReconcileModal — reconciliação cliente × IA (Opção A, decisão Isis 2026-05-28).
 *
 * Abre quando o PreviewPanel detecta divergência entre o valor digitado pelo
 * consultor e o extraído pela IA. O consultor escolhe qual origem mantém;
 * POST /intake/drafts/{id}/reconcile grava a decisão em field_sources.
 */
import { useState } from 'react';
import { api } from '@/lib/api';

interface Props {
  draftId: number;
  field: string;
  fieldLabel: string;
  manualValue: unknown;
  extractedValue: unknown;
  onClose: () => void;
  onReconciled: () => void;
}

function display(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  return String(v);
}

export default function ReconcileModal({
  draftId,
  field,
  fieldLabel,
  manualValue,
  extractedValue,
  onClose,
  onReconciled,
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const choose = async (source: 'manual' | 'extracted') => {
    setSubmitting(true);
    setError(null);
    try {
      const value = source === 'manual' ? manualValue : extractedValue;
      await api.post(`/intake/drafts/${draftId}/reconcile`, { field, source, value });
      onReconciled();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Erro ao reconciliar. Tente novamente.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="p-5 border-b border-white/10">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            ⚠️ Reconciliar <span className="text-emerald-300">{fieldLabel}</span>
          </h3>
          <p className="text-sm text-slate-400 mt-1">
            O valor digitado difere do que a IA extraiu dos documentos. Qual mantemos?
          </p>
        </div>

        <div className="p-5 grid grid-cols-2 gap-3">
          <button
            onClick={() => choose('manual')}
            disabled={submitting}
            className="text-left p-4 rounded-xl border border-white/10 bg-white/5 hover:border-emerald-400 hover:bg-emerald-500/10 transition-all disabled:opacity-40"
          >
            <span className="text-xs uppercase tracking-wide text-slate-400 block mb-1">✍️ Valor digitado</span>
            <span className="text-sm text-white font-medium break-words">{display(manualValue)}</span>
          </button>

          <button
            onClick={() => choose('extracted')}
            disabled={submitting}
            className="text-left p-4 rounded-xl border border-white/10 bg-white/5 hover:border-emerald-400 hover:bg-emerald-500/10 transition-all disabled:opacity-40"
          >
            <span className="text-xs uppercase tracking-wide text-slate-400 block mb-1">🤖 Extraído pela IA</span>
            <span className="text-sm text-white font-medium break-words">{display(extractedValue)}</span>
          </button>
        </div>

        {error && (
          <div className="px-5 pb-2 text-sm text-red-300">{error}</div>
        )}

        <div className="p-4 border-t border-white/10 flex justify-end">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white transition-colors disabled:opacity-40"
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
