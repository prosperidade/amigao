/**
 * AcaoCard — card de uma ação no workspace do caso (aba Ações, Ficha 07).
 *
 * Mostra: título, origem com fonte (#70), prioridade, prazo, status (editável),
 * e os botões de triagem (tarefa/escopo/dispensar — Princípio 1). Responsável
 * aparece "—" no MVP (Bloco 0 não iniciado). Concluir NÃO altera o passivo.
 */
import { Link2, Loader2 } from 'lucide-react';
import { useUpdateAcao, useTriarAcao } from '@/lib/acoes/hooks';
import {
  ACAO_PRIORIDADE_LABELS,
  ACAO_STATUS_LABELS,
  ACAO_STATUS_ORDER,
  type Acao,
  type AcaoFonte,
  type AcaoPrioridade,
  type AcaoStatus,
} from '@/lib/acoes/types';

const TRIAGEM_BADGE: Record<string, string> = {
  pendente: 'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300',
  tarefa: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  escopo: 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300',
  dispensada: 'bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-slate-400 line-through',
};

function FonteChip({ fonte }: { fonte: AcaoFonte }) {
  if (fonte.sem_fonte) {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300 border border-amber-200 dark:border-amber-500/20">
        ⚠ sem fonte
      </span>
    );
  }
  const label = fonte.descricao || fonte.ref || fonte.tipo || 'fonte';
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/20"
      title={fonte.tipo ? `${fonte.tipo}${fonte.ref ? ` · ${fonte.ref}` : ''}` : undefined}
    >
      {fonte.tipo ? `${fonte.tipo}: ` : ''}{label}
    </span>
  );
}

interface AcaoCardProps {
  acao: Acao;
  processId: number;
}

export default function AcaoCard({ acao, processId }: AcaoCardProps) {
  const updateMut = useUpdateAcao(processId);
  const triarMut = useTriarAcao(processId);
  const busy = updateMut.isPending || triarMut.isPending;

  const isDispensada = acao.tipo_triagem === 'dispensada';

  return (
    <div
      className={`rounded-xl border p-4 transition-colors ${
        isDispensada
          ? 'bg-gray-50/60 dark:bg-white/[0.02] border-gray-100 dark:border-white/5 opacity-70'
          : 'bg-white dark:bg-white/5 border-gray-200 dark:border-white/10'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-gray-900 dark:text-white">{acao.titulo}</p>
          {acao.origem_descricao && (
            <p className="mt-1 flex items-start gap-1 text-xs text-gray-500 dark:text-slate-400">
              <Link2 className="w-3 h-3 mt-0.5 shrink-0" />
              <span className="min-w-0">Passivo de origem: {acao.origem_descricao}</span>
            </p>
          )}
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0 ${TRIAGEM_BADGE[acao.tipo_triagem]}`}>
          {acao.tipo_triagem === 'pendente' ? 'pendente' : acao.tipo_triagem}
        </span>
      </div>

      {/* Fontes (#70) */}
      {acao.origem_fontes.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {acao.origem_fontes.map((f, i) => (
            <FonteChip key={i} fonte={f} />
          ))}
        </div>
      )}

      {/* Meta + controles */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {/* Status */}
        <select
          value={acao.status}
          disabled={busy}
          onChange={e =>
            updateMut.mutate({ acaoId: acao.id, payload: { status: e.target.value as AcaoStatus } })
          }
          className="text-xs px-2 py-1 rounded-lg border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/5 dark:text-slate-200"
        >
          {ACAO_STATUS_ORDER.map(s => (
            <option key={s} value={s}>{ACAO_STATUS_LABELS[s]}</option>
          ))}
        </select>

        {/* Prioridade */}
        <select
          value={acao.prioridade}
          disabled={busy}
          onChange={e =>
            updateMut.mutate({ acaoId: acao.id, payload: { prioridade: e.target.value as AcaoPrioridade } })
          }
          className="text-xs px-2 py-1 rounded-lg border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/5 dark:text-slate-200"
        >
          {(['alta', 'media', 'baixa'] as AcaoPrioridade[]).map(p => (
            <option key={p} value={p}>{ACAO_PRIORIDADE_LABELS[p]}</option>
          ))}
        </select>

        {/* Prazo */}
        <input
          type="date"
          value={acao.prazo ?? ''}
          disabled={busy}
          onChange={e =>
            updateMut.mutate({ acaoId: acao.id, payload: { prazo: e.target.value || null } })
          }
          className="text-xs px-2 py-1 rounded-lg border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/5 dark:text-slate-200"
        />

        {/* Responsável — MVP: sem atribuição (Bloco 0 pendente) */}
        <span className="text-xs text-gray-400 dark:text-slate-500" title="Responsável — disponível quando o multi-tenant de usuários (Bloco 0) entrar">
          Responsável: —
        </span>

        {busy && <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400" />}
      </div>

      {/* Triagem (Princípio 1 — o consultor decide) */}
      <div className="mt-3 flex items-center gap-2 border-t border-gray-100 dark:border-white/5 pt-3">
        <span className="text-[11px] text-gray-400 dark:text-slate-500 mr-1">Triar:</span>
        <button
          type="button"
          disabled={busy}
          onClick={() => triarMut.mutate({ acaoId: acao.id, decisao: 'tarefa' })}
          className={`text-xs px-2.5 py-1 rounded-lg font-medium transition-colors ${
            acao.tipo_triagem === 'tarefa'
              ? 'bg-blue-600 text-white'
              : 'bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-500/10 dark:text-blue-300'
          }`}
        >
          Tarefa
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => triarMut.mutate({ acaoId: acao.id, decisao: 'escopo' })}
          className={`text-xs px-2.5 py-1 rounded-lg font-medium transition-colors ${
            acao.tipo_triagem === 'escopo'
              ? 'bg-violet-600 text-white'
              : 'bg-violet-50 text-violet-700 hover:bg-violet-100 dark:bg-violet-500/10 dark:text-violet-300'
          }`}
          title="Marca como candidata a item da proposta/Orçamento (apenas marca — não constrói o Orçamento)"
        >
          Escopo de venda
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => triarMut.mutate({ acaoId: acao.id, decisao: 'dispensar' })}
          className={`text-xs px-2.5 py-1 rounded-lg font-medium transition-colors ${
            acao.tipo_triagem === 'dispensada'
              ? 'bg-gray-500 text-white'
              : 'bg-gray-50 text-gray-600 hover:bg-gray-100 dark:bg-white/5 dark:text-slate-300'
          }`}
        >
          Dispensar
        </button>
      </div>
    </div>
  );
}
