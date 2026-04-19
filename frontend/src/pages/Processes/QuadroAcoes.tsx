import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Plus, Search, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import type { KanbanResponse, KanbanProcessCard } from './quadro-types';
import { MACROETAPA_COLORS, DEMAND_TYPE_LABELS } from './quadro-types';
import LeituraIA from './LeituraIA';
import QuadroProcessCard from './QuadroProcessCard';
import MacroetapaSidePanel from './MacroetapaSidePanel';

type ReadinessFilter = 'all' | 'blocked' | 'ready';

export default function QuadroAcoes() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCard, setSelectedCard] = useState<KanbanProcessCard | null>(null);
  const [filterResponsible, setFilterResponsible] = useState<string>('');
  const [filterUrgency, setFilterUrgency] = useState<string>('');
  const [filterDemandType, setFilterDemandType] = useState<string>('');
  const [filterReadiness, setFilterReadiness] = useState<ReadinessFilter>('all');

  const { data: kanbanData, isLoading } = useQuery({
    queryKey: ['kanban'],
    queryFn: () => api.get<KanbanResponse>('/processes/kanban').then(r => r.data),
    staleTime: 15_000,
  });

  // Regente Cam3: avanço de macroetapa NÃO ocorre via drag-and-drop no Quadro.
  // O gate formal acontece no Workspace do Caso (botão "Avançar etapa" com validação).
  // Quadro coordena, Workspace executa.

  const columns = kanbanData?.columns ?? [];
  const totalActive = kanbanData?.total_active ?? 0;

  // Listas únicas para os filtros (derivadas dos cards carregados).
  const { responsibleOptions, demandTypeOptions } = useMemo(() => {
    const responsibles = new Set<string>();
    const demandTypes = new Set<string>();
    for (const col of columns) {
      for (const card of col.cards) {
        if (card.responsible_user_name) responsibles.add(card.responsible_user_name);
        if (card.demand_type) demandTypes.add(card.demand_type);
      }
    }
    return {
      responsibleOptions: Array.from(responsibles).sort((a, b) => a.localeCompare(b)),
      demandTypeOptions: Array.from(demandTypes).sort((a, b) => a.localeCompare(b)),
    };
  }, [columns]);

  const hasActiveFilters =
    !!searchTerm || !!filterResponsible || !!filterUrgency || !!filterDemandType || filterReadiness !== 'all';

  const clearFilters = () => {
    setSearchTerm('');
    setFilterResponsible('');
    setFilterUrgency('');
    setFilterDemandType('');
    setFilterReadiness('all');
  };

  // Aplica filtros em cascata. Busca + responsável + urgência + tipo demanda + prontidão.
  const filteredColumns = columns.map(col => ({
    ...col,
    cards: col.cards.filter(c => {
      if (searchTerm) {
        const term = searchTerm.toLowerCase();
        const matches =
          c.client_name?.toLowerCase().includes(term) ||
          c.title.toLowerCase().includes(term) ||
          c.property_name?.toLowerCase().includes(term);
        if (!matches) return false;
      }
      if (filterResponsible && c.responsible_user_name !== filterResponsible) return false;
      if (filterUrgency) {
        const urg = c.urgency ?? c.priority ?? '';
        if (urg !== filterUrgency) return false;
      }
      if (filterDemandType && c.demand_type !== filterDemandType) return false;
      if (filterReadiness === 'blocked' && c.macroetapa_state !== 'travada') return false;
      if (filterReadiness === 'ready' && c.macroetapa_state !== 'pronta_para_avancar') return false;
      return true;
    }),
  }));

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
            Quadro de Ações
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Fluxo macro dos casos em andamento
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative w-72 hidden md:block">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar cliente, imóvel ou caso..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all dark:text-zinc-200"
            />
          </div>
          <span className="text-sm text-gray-500 dark:text-gray-400 hidden lg:block">
            {totalActive} casos ativos
          </span>
          <button
            onClick={() => navigate('/intake')}
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-colors shadow-lg shadow-emerald-500/20 flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Novo Caso
          </button>
        </div>
      </div>

      {/* Filtros operacionais (Regente Cam3 — Quadro de Ações) */}
      <div className="flex flex-wrap items-center gap-2 shrink-0">
        <select
          value={filterResponsible}
          onChange={e => setFilterResponsible(e.target.value)}
          className="text-xs px-3 py-1.5 border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 rounded-full dark:text-zinc-200 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
        >
          <option value="">Responsável (todos)</option>
          {responsibleOptions.map(r => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>

        <select
          value={filterUrgency}
          onChange={e => setFilterUrgency(e.target.value)}
          className="text-xs px-3 py-1.5 border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 rounded-full dark:text-zinc-200 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
        >
          <option value="">Urgência (todas)</option>
          <option value="critica">Urgente</option>
          <option value="alta">Alta</option>
          <option value="media">Média</option>
          <option value="baixa">Baixa</option>
        </select>

        <select
          value={filterDemandType}
          onChange={e => setFilterDemandType(e.target.value)}
          className="text-xs px-3 py-1.5 border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 rounded-full dark:text-zinc-200 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
        >
          <option value="">Tipo de demanda (todos)</option>
          {demandTypeOptions.map(d => (
            <option key={d} value={d}>{DEMAND_TYPE_LABELS[d] ?? d}</option>
          ))}
        </select>

        <div className="flex rounded-full overflow-hidden border border-gray-200 dark:border-zinc-700">
          <button
            type="button"
            onClick={() => setFilterReadiness('all')}
            className={`text-xs px-3 py-1.5 transition-colors ${filterReadiness === 'all' ? 'bg-primary text-white' : 'bg-white dark:bg-zinc-800 dark:text-zinc-200 hover:bg-gray-50'}`}
          >
            Todos
          </button>
          <button
            type="button"
            onClick={() => setFilterReadiness('blocked')}
            className={`text-xs px-3 py-1.5 transition-colors border-l border-gray-200 dark:border-zinc-700 ${filterReadiness === 'blocked' ? 'bg-red-500 text-white' : 'bg-white dark:bg-zinc-800 dark:text-zinc-200 hover:bg-gray-50'}`}
          >
            🚫 Travados
          </button>
          <button
            type="button"
            onClick={() => setFilterReadiness('ready')}
            className={`text-xs px-3 py-1.5 transition-colors border-l border-gray-200 dark:border-zinc-700 ${filterReadiness === 'ready' ? 'bg-emerald-500 text-white' : 'bg-white dark:bg-zinc-800 dark:text-zinc-200 hover:bg-gray-50'}`}
          >
            ✓ Prontos
          </button>
        </div>

        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-full text-gray-500 hover:text-gray-900 dark:hover:text-white transition-colors"
          >
            <X className="w-3 h-3" /> Limpar filtros
          </button>
        )}
      </div>

      {/* Leitura da IA */}
      <LeituraIA />

      {/* Kanban Board */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden pb-4">
        <div className="flex gap-4 h-full min-w-max items-start">
          {filteredColumns.map(column => {
            const colors = MACROETAPA_COLORS[column.macroetapa] ?? {
              bg: 'bg-gray-50',
              border: 'border-gray-200',
              text: 'text-gray-700',
            };

            return (
              <div
                key={column.macroetapa}
                className="w-80 flex flex-col h-full bg-gray-50/50 dark:bg-zinc-900/30 rounded-xl"
              >
                {/* Column header */}
                <div
                  className={`p-3 rounded-t-xl border-b font-medium text-sm ${colors.bg} ${colors.border} ${colors.text} dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200`}
                >
                  <div className="flex items-center justify-between">
                    <span className="truncate">{column.label}</span>
                    <span className="bg-white/50 dark:bg-black/20 px-2 py-0.5 rounded-full text-xs">
                      {column.count}
                    </span>
                  </div>
                  {/* CAM3FT-003 — counts agregados por estado */}
                  {(column.blocked_count > 0 || column.ready_to_advance_count > 0) && (
                    <div className="flex gap-2 mt-1.5 text-[10px]">
                      {column.blocked_count > 0 && (
                        <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300">
                          🚫 {column.blocked_count} travado{column.blocked_count > 1 ? 's' : ''}
                        </span>
                      )}
                      {column.ready_to_advance_count > 0 && (
                        <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                          ✓ {column.ready_to_advance_count} pronto{column.ready_to_advance_count > 1 ? 's' : ''}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Cards */}
                <div className="p-3 flex-1 overflow-y-auto space-y-3 custom-scrollbar">
                  {isLoading ? (
                    <div className="text-center text-xs text-gray-400 py-4">Carregando...</div>
                  ) : column.cards.length === 0 ? (
                    <div className="text-center text-xs text-gray-400 py-8">Nenhum caso</div>
                  ) : (
                    column.cards.map(card => (
                      <QuadroProcessCard
                        key={card.id}
                        card={card}
                        onClick={() => setSelectedCard(card)}
                      />
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Side panel */}
      {selectedCard && (
        <MacroetapaSidePanel card={selectedCard} onClose={() => setSelectedCard(null)} />
      )}
    </div>
  );
}
