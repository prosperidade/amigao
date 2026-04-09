import { User, MapPin, ArrowRight } from 'lucide-react';
import type { KanbanProcessCard } from './quadro-types';
import { DEMAND_TYPE_LABELS, URGENCY_BADGES } from './quadro-types';

interface Props {
  card: KanbanProcessCard;
  onClick: () => void;
  onDragStart: (e: React.DragEvent) => void;
}

export default function QuadroProcessCard({ card, onClick, onDragStart }: Props) {
  const urgencyKey = card.urgency ?? card.priority ?? '';
  const urgencyBadge = URGENCY_BADGES[urgencyKey];
  const demandLabel = card.demand_type ? (DEMAND_TYPE_LABELS[card.demand_type] ?? card.demand_type) : null;

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onClick}
      className="bg-white dark:bg-zinc-900 p-4 rounded-xl shadow-sm border border-gray-100 dark:border-zinc-800 cursor-pointer hover:border-primary/30 dark:hover:border-primary/30 transition-colors"
    >
      {/* Cliente + Imóvel */}
      <p className="font-medium text-sm text-gray-900 dark:text-gray-100 line-clamp-1">
        {card.client_name ?? 'Cliente não vinculado'}
      </p>
      {card.property_name && (
        <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
          <MapPin className="w-3 h-3" /> {card.property_name}
        </p>
      )}

      {/* Tipo de demanda */}
      {demandLabel && (
        <p className="text-xs text-gray-600 dark:text-gray-400 mt-1.5">{demandLabel}</p>
      )}

      {/* Badges */}
      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
        {urgencyBadge && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${urgencyBadge}`}>
            {urgencyKey === 'critica' ? 'Urgente' : urgencyKey === 'alta' ? 'Alta' : urgencyKey === 'media' ? 'Média' : 'Baixa'}
          </span>
        )}
        {card.has_alerts && (
          <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
            Alerta
          </span>
        )}
      </div>

      {/* Responsável */}
      {card.responsible_user_name && (
        <div className="flex items-center gap-1.5 mt-2.5 text-xs text-gray-500">
          <User className="w-3 h-3" />
          <span>{card.responsible_user_name}</span>
        </div>
      )}

      {/* Próxima ação */}
      {card.next_action && (
        <div className="flex items-center gap-1.5 mt-1.5 text-xs text-emerald-600 dark:text-emerald-400">
          <ArrowRight className="w-3 h-3" />
          <span className="line-clamp-1">{card.next_action}</span>
        </div>
      )}

      {/* Barra de progresso */}
      <div className="mt-3 w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-1.5">
        <div
          className="bg-emerald-500 h-1.5 rounded-full transition-all"
          style={{ width: `${Math.min(card.macroetapa_completion_pct, 100)}%` }}
        />
      </div>
    </div>
  );
}
