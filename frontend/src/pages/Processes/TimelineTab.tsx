import { useMemo, useState } from 'react';
import {
  ArrowLeftRight, CheckCheck, CheckCircle2, Clock, Database, FileText,
  GitBranch, Pencil, Sparkles, Tag, XCircle, FileSearch, ListChecks, ChevronRight,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import { describeEvento, type EventoKind, type TimelineEvent } from './historicoEventos';
import { agruparBlocos, resumoCluster, type DescribedEvent } from './historicoBlocos';
import { origemDadoLabel } from '@/lib/labels/docLabels';

interface TimelineTabProps {
  processId: number;
}

// Ícone + cor por tipo de evento (reusa o padrão de tons da severidade:
// emerald/positivo, red/negativo, violet/escolha, indigo/status, slate/neutro).
const KIND_STYLE: Record<EventoKind, { icon: LucideIcon; dot: string; ring: string; iconCls: string }> = {
  aceito:       { icon: CheckCircle2, dot: 'bg-emerald-500', ring: 'ring-emerald-100 dark:ring-emerald-500/20', iconCls: 'text-emerald-600 dark:text-emerald-400' },
  rejeitado:    { icon: XCircle,      dot: 'bg-red-500',     ring: 'ring-red-100 dark:ring-red-500/20',         iconCls: 'text-red-600 dark:text-red-400' },
  escolhido:    { icon: GitBranch,    dot: 'bg-violet-500',  ring: 'ring-violet-100 dark:ring-violet-500/20',   iconCls: 'text-violet-600 dark:text-violet-400' },
  editado:      { icon: Pencil,       dot: 'bg-blue-500',    ring: 'ring-blue-100 dark:ring-blue-500/20',       iconCls: 'text-blue-600 dark:text-blue-400' },
  lote:         { icon: CheckCheck,   dot: 'bg-emerald-500', ring: 'ring-emerald-100 dark:ring-emerald-500/20', iconCls: 'text-emerald-600 dark:text-emerald-400' },
  consolidado:  { icon: Database,     dot: 'bg-emerald-600', ring: 'ring-emerald-100 dark:ring-emerald-500/20', iconCls: 'text-emerald-700 dark:text-emerald-400' },
  status:       { icon: ArrowLeftRight, dot: 'bg-indigo-500', ring: 'ring-indigo-100 dark:ring-indigo-500/20',  iconCls: 'text-indigo-600 dark:text-indigo-400' },
  criado:       { icon: Sparkles,     dot: 'bg-emerald-500', ring: 'ring-emerald-100 dark:ring-emerald-500/20', iconCls: 'text-emerald-600 dark:text-emerald-400' },
  resumo:       { icon: FileText,     dot: 'bg-slate-400',   ring: 'ring-slate-100 dark:ring-slate-500/20',     iconCls: 'text-slate-500 dark:text-slate-400' },
  classificacao:{ icon: Tag,          dot: 'bg-indigo-500',  ring: 'ring-indigo-100 dark:ring-indigo-500/20',   iconCls: 'text-indigo-600 dark:text-indigo-400' },
  generico:     { icon: Clock,        dot: 'bg-gray-400',    ring: 'ring-gray-100 dark:ring-white/10',          iconCls: 'text-gray-400 dark:text-slate-500' },
};

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('pt-BR', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

/** Card de um evento (marco ou item dentro do cluster). */
function EventoCard({ log, ev }: DescribedEvent) {
  const style = KIND_STYLE[ev.kind];
  const Icon = style.icon;
  return (
    <div className="rounded-xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/5 p-4 shadow-sm dark:shadow-none">
      <div className="flex items-start gap-2">
        <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${style.iconCls}`} />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-800 dark:text-white">{ev.titulo}</p>
          {ev.detalhe && (
            <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">{ev.detalhe}</p>
          )}
          {ev.origem && (
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-2 flex items-center gap-1">
              <FileSearch className="w-3 h-3 shrink-0 text-gray-400 dark:text-slate-500" />
              {/* Item 14 — `origem` é chave interna ("human_validated",
                  "derived_matricula"); passa pelo dicionário. */}
              <span className="min-w-0">Origem do dado: <span className="font-medium text-gray-600 dark:text-slate-300">{origemDadoLabel(ev.origem)}</span></span>
            </p>
          )}
        </div>
      </div>
      <p className="text-xs text-gray-400 dark:text-slate-500 mt-2 flex items-center gap-1">
        <Clock className="w-3 h-3" />
        {formatWhen(log.created_at)}
      </p>
    </div>
  );
}

/** Bloco colapsável de decisões de conferência — resultado visível, detalhe oculto. */
function ClusterCard({ itens }: { itens: DescribedEvent[] }) {
  const [aberto, setAberto] = useState(false);
  const periodo = `${formatWhen(itens[itens.length - 1].log.created_at)}`;
  return (
    <div className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/10">
      <button
        onClick={() => setAberto((v) => !v)}
        className="w-full flex items-center gap-2 p-4 text-left"
        aria-expanded={aberto}
      >
        <ListChecks className="w-4 h-4 shrink-0 text-gray-500 dark:text-slate-400" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-gray-800 dark:text-white">{resumoCluster(itens)}</p>
          <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5 flex items-center gap-1">
            <Clock className="w-3 h-3" /> até {periodo}
          </p>
        </div>
        <ChevronRight
          className={`w-4 h-4 shrink-0 text-gray-400 transition-transform ${aberto ? 'rotate-90' : ''}`}
        />
      </button>
      {aberto && (
        <div className="px-4 pb-4 space-y-2 border-t border-gray-100 dark:border-white/10 pt-3">
          {itens.map((de) => <EventoCard key={de.log.id} {...de} />)}
        </div>
      )}
    </div>
  );
}

export default function TimelineTab({ processId }: TimelineTabProps) {
  const { data: timeline } = useQuery({
    queryKey: ['timeline', processId],
    queryFn: async () => {
      const res = await api.get(`/processes/${processId}/timeline`);
      return res.data as TimelineEvent[];
    },
    enabled: !!processId,
  });

  const blocos = useMemo(
    () => agruparBlocos((timeline ?? []).map((log) => ({ log, ev: describeEvento(log) }))),
    [timeline],
  );

  if (timeline && timeline.length === 0) {
    return <p className="text-sm text-gray-400 dark:text-slate-500">Nenhum evento registrado.</p>;
  }

  return (
    <div className="relative pl-6 border-l-2 border-gray-100 dark:border-white/10 space-y-5 py-1">
      {blocos.map((bloco, i) => {
        const dotCls = bloco.tipo === 'cluster'
          ? 'bg-gray-300 dark:bg-slate-600 ring-gray-100 dark:ring-white/10'
          : `${KIND_STYLE[bloco.item.ev.kind].dot} ${KIND_STYLE[bloco.item.ev.kind].ring}`;
        return (
          <div key={bloco.tipo === 'marco' ? `m${bloco.item.log.id}` : `c${i}`} className="relative">
            <div className="absolute -left-[31px] bg-white dark:bg-slate-900 p-1">
              <div className={`w-3 h-3 rounded-full ring-2 ${dotCls}`} />
            </div>
            {bloco.tipo === 'marco'
              ? <EventoCard {...bloco.item} />
              : <ClusterCard itens={bloco.itens} />}
          </div>
        );
      })}
    </div>
  );
}
