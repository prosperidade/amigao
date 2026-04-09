import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Plus, Search } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { api } from '@/lib/api';
import type { KanbanResponse, KanbanProcessCard } from './quadro-types';
import { MACROETAPA_COLORS } from './quadro-types';
import LeituraIA from './LeituraIA';
import QuadroProcessCard from './QuadroProcessCard';
import MacroetapaSidePanel from './MacroetapaSidePanel';

export default function QuadroAcoes() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCard, setSelectedCard] = useState<KanbanProcessCard | null>(null);

  const { data: kanbanData, isLoading } = useQuery({
    queryKey: ['kanban'],
    queryFn: () => api.get<KanbanResponse>('/processes/kanban').then(r => r.data),
    staleTime: 15_000,
  });

  const advanceMutation = useMutation({
    mutationFn: (data: { id: number; macroetapa: string }) =>
      api.post(`/processes/${data.id}/macroetapa`, { macroetapa: data.macroetapa }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['kanban'] });
      queryClient.invalidateQueries({ queryKey: ['kanban-insights'] });
      toast.success('Macroetapa avançada');
    },
    onError: (err: AxiosError<{ detail?: string }>) => {
      toast.error(err.response?.data?.detail ?? 'Erro ao avançar macroetapa');
    },
  });

  const handleDragStart = (e: React.DragEvent, processId: number) => {
    e.dataTransfer.setData('processId', processId.toString());
  };

  const handleDrop = (e: React.DragEvent, targetMacroetapa: string) => {
    e.preventDefault();
    const processId = e.dataTransfer.getData('processId');
    if (processId) {
      advanceMutation.mutate({ id: parseInt(processId), macroetapa: targetMacroetapa });
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const columns = kanbanData?.columns ?? [];
  const totalActive = kanbanData?.total_active ?? 0;

  // Filtro por busca
  const filteredColumns = columns.map(col => ({
    ...col,
    cards: searchTerm
      ? col.cards.filter(
          c =>
            c.client_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
            c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
            c.property_name?.toLowerCase().includes(searchTerm.toLowerCase())
        )
      : col.cards,
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
                onDragOver={handleDragOver}
                onDrop={e => handleDrop(e, column.macroetapa)}
              >
                {/* Column header */}
                <div
                  className={`p-3 rounded-t-xl border-b font-medium text-sm flex items-center justify-between ${colors.bg} ${colors.border} ${colors.text} dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200`}
                >
                  <span className="truncate">{column.label}</span>
                  <span className="bg-white/50 dark:bg-black/20 px-2 py-0.5 rounded-full text-xs">
                    {column.count}
                  </span>
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
                        onDragStart={e => handleDragStart(e, card.id)}
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
