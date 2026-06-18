/**
 * QuadroAcoesGlobal — Quadro de Ações global (Ficha 07 §5).
 *
 * Kanban por **status** (a fazer · em andamento · concluída · bloqueada) com
 * ações de TODOS os casos do tenant. Cada card mostra o caso de origem
 * (cliente · imóvel · processo). Mover um card entre colunas muda o status
 * (PATCH) — implementado por seta "avançar/voltar" (ação equivalente ao
 * drag-and-drop, sem dependência extra).
 *
 * Distinto do board de *casos por macroetapa* (sidebar "Casos", `/processes`):
 * aqui o card é uma AÇÃO, lá é um CASO.
 */
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ChevronLeft, ChevronRight, ExternalLink, Loader2, Search } from 'lucide-react';
import { useAcoesKanban, useMoveAcaoStatus } from '@/lib/acoes/hooks';
import {
  ACAO_PRIORIDADE_LABELS,
  ACAO_STATUS_ORDER,
  ACAO_TRIAGEM_LABELS,
  type AcaoKanbanCard,
  type AcaoStatus,
} from '@/lib/acoes/types';

const COLUMN_STYLE: Record<AcaoStatus, { bar: string; chip: string }> = {
  a_fazer: { bar: 'bg-gray-400', chip: 'bg-gray-100 text-gray-700 dark:bg-white/10 dark:text-slate-300' },
  em_andamento: { bar: 'bg-blue-500', chip: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300' },
  concluida: { bar: 'bg-emerald-500', chip: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300' },
  bloqueada: { bar: 'bg-red-500', chip: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300' },
};

const TRIAGEM_DOT: Record<string, string> = {
  pendente: 'bg-amber-400',
  tarefa: 'bg-blue-400',
  escopo: 'bg-violet-400',
  dispensada: 'bg-gray-300',
};

function Card({
  card,
  onMove,
  busy,
}: {
  card: AcaoKanbanCard;
  onMove: (target: AcaoStatus) => void;
  busy: boolean;
}) {
  const navigate = useNavigate();
  const idx = ACAO_STATUS_ORDER.indexOf(card.status);
  const prev = idx > 0 ? ACAO_STATUS_ORDER[idx - 1] : null;
  const next = idx < ACAO_STATUS_ORDER.length - 1 ? ACAO_STATUS_ORDER[idx + 1] : null;

  const caseLabel = [card.client_name, card.property_name].filter(Boolean).join(' · ');

  return (
    <div className="rounded-xl bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 p-3 space-y-2 shadow-sm">
      <div className="flex items-start gap-2">
        <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${TRIAGEM_DOT[card.tipo_triagem] ?? 'bg-gray-300'}`}
          title={ACAO_TRIAGEM_LABELS[card.tipo_triagem]} />
        <p className="text-sm font-medium text-gray-900 dark:text-white min-w-0">{card.titulo}</p>
      </div>

      {/* Caso de origem */}
      <button
        type="button"
        onClick={() => navigate(`/processes/${card.process_id}`)}
        className="flex items-center gap-1 text-[11px] text-gray-500 dark:text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors min-w-0 max-w-full"
        title="Abrir o caso de origem"
      >
        <ExternalLink className="w-3 h-3 shrink-0" />
        <span className="truncate">{card.process_title ?? `Caso #${card.process_id}`}{caseLabel ? ` — ${caseLabel}` : ''}</span>
      </button>

      <div className="flex items-center justify-between gap-2 pt-1">
        <span className="text-[10px] text-gray-400 dark:text-slate-500">
          {ACAO_PRIORIDADE_LABELS[card.prioridade]}
          {card.prazo ? ` · ${card.prazo}` : ''}
        </span>
        {/* Mover de coluna (= mudar status) */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            disabled={!prev || busy}
            onClick={() => prev && onMove(prev)}
            className="p-1 rounded-md text-gray-400 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title={prev ? `Mover para "${prev}"` : undefined}
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            type="button"
            disabled={!next || busy}
            onClick={() => next && onMove(next)}
            className="p-1 rounded-md text-gray-400 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title={next ? `Mover para "${next}"` : undefined}
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function QuadroAcoesGlobal() {
  const { data, isLoading } = useAcoesKanban();
  const moveMut = useMoveAcaoStatus();
  const [search, setSearch] = useState('');

  const columns = useMemo(() => {
    const cols = data?.columns ?? [];
    if (!search.trim()) return cols;
    const term = search.toLowerCase();
    return cols.map(col => ({
      ...col,
      cards: col.cards.filter(c =>
        c.titulo.toLowerCase().includes(term) ||
        (c.process_title ?? '').toLowerCase().includes(term) ||
        (c.client_name ?? '').toLowerCase().includes(term) ||
        (c.property_name ?? '').toLowerCase().includes(term),
      ),
    }));
  }, [data, search]);

  const handleMove = (card: AcaoKanbanCard, target: AcaoStatus) => {
    moveMut.mutate(
      { processId: card.process_id, acaoId: card.id, status: target },
      { onError: () => toast.error('Falha ao mover a ação.') },
    );
  };

  return (
    <div className="h-full flex flex-col gap-4">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
            Quadro de Ações
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Ações de remediação de todos os casos — por status
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative w-72 hidden md:block">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar ação, caso, cliente ou imóvel…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 rounded-lg text-sm outline-none dark:text-zinc-200"
            />
          </div>
          <span className="text-sm text-gray-500 dark:text-gray-400 hidden lg:block">
            {data?.total ?? 0} ações
          </span>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-slate-400 p-4">
          <Loader2 className="w-4 h-4 animate-spin" /> Carregando quadro…
        </div>
      ) : (
        <div className="flex-1 overflow-x-auto overflow-y-hidden pb-4">
          <div className="flex gap-4 h-full min-w-max items-start">
            {columns.map(column => {
              const style = COLUMN_STYLE[column.status];
              return (
                <div
                  key={column.status}
                  className="w-80 flex flex-col h-full bg-gray-50/50 dark:bg-zinc-900/30 rounded-xl"
                >
                  <div className="p-3 rounded-t-xl border-b border-gray-200 dark:border-zinc-700 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`w-2.5 h-2.5 rounded-full ${style.bar}`} />
                      <span className="font-medium text-sm text-gray-700 dark:text-gray-200">{column.label}</span>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-xs ${style.chip}`}>{column.cards.length}</span>
                  </div>
                  <div className="p-3 flex-1 overflow-y-auto space-y-3 custom-scrollbar">
                    {column.cards.length === 0 ? (
                      <div className="text-center text-xs text-gray-400 py-8">Nenhuma ação</div>
                    ) : (
                      column.cards.map(card => (
                        <Card
                          key={card.id}
                          card={card}
                          busy={moveMut.isPending}
                          onMove={target => handleMove(card, target)}
                        />
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
