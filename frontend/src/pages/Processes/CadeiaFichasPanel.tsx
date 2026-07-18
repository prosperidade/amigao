/**
 * CadeiaFichasPanel — Dívida #60: curadoria da cadeia de fichas na Conferência.
 *
 * Critério de domínio da Isis: "vigente = matrícula da última averbação; a ficha
 * anterior vira HISTÓRICO". O sistema DETECTA cadeias entre as matrículas do
 * imóvel e PROPÕE (pré-marcadas); o consultor confirma em 1 CLIQUE — substitui
 * N rejeições campo-a-campo. IA propõe, humano decide (Princípio 1). Reversível
 * em Dados. Sem cadeia detectada → o painel não aparece.
 */

import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';
import { GitBranch, Loader2, Check } from 'lucide-react';
import { api } from '@/lib/api';

interface ChainProposal {
  anterior_id: number;
  anterior_numero: string | null;
  vigente_id: number;
  vigente_numero: string | null;
  sinal: string;
  confianca: string;
  evidencia: string;
}

const CONFIANCA_CLS: Record<string, string> = {
  alta: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30',
  media: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30',
  baixa: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-white/10 dark:text-slate-300 dark:border-white/10',
};

function errDetail(e: unknown, fallback: string): string {
  const ax = e as AxiosError<{ detail?: string }>;
  return ax?.response?.data?.detail ?? ax?.message ?? fallback;
}

function pairKey(p: ChainProposal): string {
  return `${p.anterior_id}->${p.vigente_id}`;
}

export default function CadeiaFichasPanel({ processId }: { processId: number }) {
  const qc = useQueryClient();
  const { data: proposals = [], isLoading } = useQuery<ChainProposal[]>({
    queryKey: ['chain-proposals', processId],
    queryFn: () => api.get(`/processes/${processId}/chain-proposals`).then(r => r.data),
  });

  // Pré-marcadas por padrão (IA propõe → aceite é o caminho esperado); o
  // consultor pode desmarcar uma cadeia específica antes de confirmar.
  const [unchecked, setUnchecked] = useState<Set<string>>(new Set());
  const selected = useMemo(
    () => proposals.filter(p => !unchecked.has(pairKey(p))),
    [proposals, unchecked],
  );

  const aplicar = useMutation({
    mutationFn: () =>
      api.post(`/processes/${processId}/chain-proposals/aplicar`, {
        pairs: selected.map(p => ({ anterior_id: p.anterior_id, vigente_id: p.vigente_id })),
      }).then(r => r.data),
    onSuccess: (res: { count: number }) => {
      qc.invalidateQueries({ queryKey: ['chain-proposals', processId] });
      qc.invalidateQueries({ queryKey: ['staging-fields', processId] });
      toast.success(
        res.count > 0
          ? `Cadeia confirmada: ${res.count} ficha(s) marcada(s) como histórica(s).`
          : 'Nenhuma cadeia selecionada.',
      );
    },
    onError: (e) => toast.error(errDetail(e, 'Falha ao confirmar a cadeia.')),
  });

  if (isLoading || proposals.length === 0) return null;

  const toggle = (p: ChainProposal) => {
    setUnchecked(prev => {
      const next = new Set(prev);
      const k = pairKey(p);
      if (next.has(k)) next.delete(k); else next.add(k);
      return next;
    });
  };

  return (
    <div className="rounded-xl bg-white dark:bg-white/5 border border-indigo-100 dark:border-indigo-500/20 p-5 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-indigo-500" /> Cadeia de fichas detectada
        </h3>
        <span className="text-xs text-gray-400 dark:text-slate-500">
          {proposals.length} cadeia(s) — a ficha anterior vira histórica (não soma)
        </span>
      </div>

      <p className="text-xs text-gray-500 dark:text-slate-400">
        A ficha anterior de uma matrícula não é um segundo imóvel — é a mesma terra
        antes da última averbação. Confirme para tirá-la da soma e guardá-la como
        linhagem (reversível em Dados).
      </p>

      <div className="space-y-1.5">
        {proposals.map(p => {
          const checked = !unchecked.has(pairKey(p));
          return (
            <label
              key={pairKey(p)}
              className="flex items-start gap-3 p-2.5 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(p)}
                className="mt-0.5 accent-indigo-600"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-800 dark:text-slate-200">
                  Matrícula <strong>{p.anterior_numero ?? '—'}</strong> é ficha anterior de{' '}
                  <strong>{p.vigente_numero ?? '—'}</strong>
                </p>
                <p className="text-xs text-gray-400 dark:text-slate-500">{p.evidencia}</p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded border whitespace-nowrap ${CONFIANCA_CLS[p.confianca] ?? ''}`}>
                {p.confianca}
              </span>
            </label>
          );
        })}
      </div>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <span className="text-xs text-gray-500 dark:text-slate-400">
          {selected.length} de {proposals.length} selecionada(s)
        </span>
        <button
          onClick={() => aplicar.mutate()}
          disabled={aplicar.isPending || selected.length === 0}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium"
        >
          {aplicar.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
          Confirmar cadeia ({selected.length})
        </button>
      </div>
    </div>
  );
}
