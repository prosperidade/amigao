import { User, MapPin, ArrowRight } from 'lucide-react';
import type { KanbanProcessCard } from './quadro-types';
import { DEMAND_TYPE_LABELS, MACROETAPA_STATE_BADGE, URGENCY_BADGES } from './quadro-types';

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
        {/* Regente Cam3 — Estado formal da etapa (CAM3FT-004) */}
        {card.macroetapa_state && MACROETAPA_STATE_BADGE[card.macroetapa_state] && (
          <span
            title={card.blockers.length > 0 ? `Travas:\n${card.blockers.join('\n')}` : MACROETAPA_STATE_BADGE[card.macroetapa_state].label}
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${MACROETAPA_STATE_BADGE[card.macroetapa_state].cls}`}
          >
            {MACROETAPA_STATE_BADGE[card.macroetapa_state].label}
          </span>
        )}
        {/* Regente Cam1 — Gate de prontidão */}
        {card.has_minimal_base ? (
          <span
            title="Base mínima (cliente+imóvel) preenchida"
            className="text-xs px-2 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
          >
            Base ✓
          </span>
        ) : (
          <span
            title="Faltam dados mínimos do cliente ou imóvel"
            className="text-xs px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
          >
            Base incompleta
          </span>
        )}
        {card.has_complementary_base && (
          <span
            title="Documentos complementares anexados"
            className="text-xs px-2 py-0.5 rounded-full font-medium bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400"
          >
            Docs anexados
          </span>
        )}
        {card.missing_docs_count > 0 && (
          <span
            title={`${card.missing_docs_count} documento(s) obrigatório(s) pendente(s)`}
            className="text-xs px-2 py-0.5 rounded-full font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
          >
            {card.missing_docs_count} pendente{card.missing_docs_count > 1 ? 's' : ''}
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
