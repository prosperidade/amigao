/**
 * AcaoCard — card de uma ação no workspace do caso (aba Ações, Ficha 07).
 *
 * Mostra: título (em linguagem de consultor — ver `humanizeAcaoTitulo`), origem
 * com fonte (#70), prioridade, prazo, status (editável), e os botões de triagem
 * (tarefa/escopo/dispensar — Princípio 1). Título e descrição são editáveis
 * inline (item 1): o consultor ajusta o texto e o PATCH grava. Responsável
 * aparece "—" no MVP (Bloco 0 não iniciado). Concluir NÃO altera o passivo.
 */
import { useState } from 'react';
import toast from 'react-hot-toast';
import { Check, Link2, Loader2, Pencil, X } from 'lucide-react';
import { useUpdateAcao, useTriarAcao } from '@/lib/acoes/hooks';
import { humanizeAcaoTitulo } from '@/lib/acoes/titulo';
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
  const tituloLegivel = humanizeAcaoTitulo(acao);

  // Item 1 — edição inline de título/descrição. O título abre com a versão
  // legível (item 2): confirmar "promove" o texto humanizado ao dado gravado.
  const [editing, setEditing] = useState(false);
  const [tituloDraft, setTituloDraft] = useState(tituloLegivel);
  const [descricaoDraft, setDescricaoDraft] = useState(acao.descricao ?? '');

  const startEdit = () => {
    setTituloDraft(tituloLegivel);
    setDescricaoDraft(acao.descricao ?? '');
    setEditing(true);
  };

  const saveEdit = () => {
    const titulo = tituloDraft.trim();
    if (!titulo) {
      toast.error('O título não pode ficar vazio.');
      return;
    }
    updateMut.mutate(
      { acaoId: acao.id, payload: { titulo, descricao: descricaoDraft.trim() || null } },
      {
        onSuccess: () => {
          setEditing(false);
          toast.success('Ação atualizada.');
        },
        onError: () => toast.error('Falha ao salvar a ação.'),
      },
    );
  };

  return (
    <div
      className={`rounded-xl border p-4 transition-colors ${
        isDispensada
          ? 'bg-gray-50/60 dark:bg-white/[0.02] border-gray-100 dark:border-white/5 opacity-70'
          : 'bg-white dark:bg-white/5 border-gray-200 dark:border-white/10'
      }`}
    >
      {editing ? (
        <div className="space-y-2">
          <input
            type="text"
            value={tituloDraft}
            onChange={e => setTituloDraft(e.target.value)}
            disabled={busy}
            aria-label="Título da ação"
            className="w-full rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-900 dark:text-white px-3 py-2 text-sm font-semibold focus:outline-none focus:border-emerald-500 transition-colors"
          />
          <textarea
            value={descricaoDraft}
            onChange={e => setDescricaoDraft(e.target.value)}
            disabled={busy}
            rows={3}
            placeholder="Descrição (opcional) — detalhe o que fazer…"
            aria-label="Descrição da ação"
            className="w-full rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200 placeholder-gray-400 dark:placeholder-slate-500 px-3 py-2 text-sm focus:outline-none focus:border-emerald-500 transition-colors resize-y"
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={saveEdit}
              disabled={busy || !tituloDraft.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-medium transition-colors"
            >
              {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              Salvar
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              disabled={busy}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 disabled:opacity-50 text-gray-600 dark:text-slate-300 text-xs font-medium transition-colors"
            >
              <X className="w-3.5 h-3.5" /> Cancelar
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-gray-900 dark:text-white">{tituloLegivel}</p>
            {acao.descricao && (
              <p className="mt-1 text-xs text-gray-600 dark:text-slate-300 whitespace-pre-wrap">{acao.descricao}</p>
            )}
            {acao.origem_descricao && (
              <p className="mt-1 flex items-start gap-1 text-xs text-gray-500 dark:text-slate-400">
                <Link2 className="w-3 h-3 mt-0.5 shrink-0" />
                <span className="min-w-0">Passivo de origem: {acao.origem_descricao}</span>
              </p>
            )}
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={startEdit}
              disabled={busy}
              aria-label="Editar ação"
              title="Editar título e descrição"
              className="text-gray-400 hover:text-gray-700 dark:hover:text-white p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
            >
              <Pencil className="w-3.5 h-3.5" />
            </button>
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${TRIAGEM_BADGE[acao.tipo_triagem]}`}>
              {acao.tipo_triagem === 'pendente' ? 'pendente' : acao.tipo_triagem}
            </span>
          </div>
        </div>
      )}

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
