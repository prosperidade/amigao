import { ArrowLeft, User, Building2, Clock } from 'lucide-react';
import { Process, STATUS_CONFIG, DEMAND_LABELS, URGENCY_CONFIG } from './ProcessDetailTypes';

interface ProcessHeaderProps {
  process: Process;
  client: { full_name: string } | undefined;
  onBack: () => void;
}

export default function ProcessHeader({ process, client, onBack }: ProcessHeaderProps) {
  const statusCfg = STATUS_CONFIG[process.status] ?? { label: process.status, dot: 'bg-gray-400', badge: 'text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-500/10 border-gray-300 dark:border-gray-500/20' };
  const urgencyCfg = URGENCY_CONFIG[process.urgency ?? 'media'];
  const demandLabel = process.demand_type ? DEMAND_LABELS[process.demand_type] : null;

  return (
    <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 overflow-hidden">
      {/* Accent strip */}
      <div className="h-1.5 bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-600" />
      <div className="p-5 flex items-start gap-4">
        <button
          onClick={onBack}
          className="mt-0.5 p-2 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-500 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-200 dark:hover:bg-white/10 transition-all shrink-0"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          {/* Badges */}
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${statusCfg.badge}`}>
              <span className={`w-2 h-2 rounded-full ${statusCfg.dot}`} />
              {statusCfg.label}
            </span>
            {demandLabel && (
              <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-300">
                {demandLabel}
              </span>
            )}
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${urgencyCfg.cls}`}>
              {urgencyCfg.label}
            </span>
          </div>
          {/* Title */}
          <h1 className="text-xl font-bold text-gray-900 dark:text-white leading-tight">{process.title}</h1>
          {/* Meta row */}
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 mt-2.5 text-sm text-gray-500 dark:text-slate-400">
            {client && (
              <span className="flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-gray-400 dark:text-slate-500" />
                <span className="text-gray-700 dark:text-slate-300 font-medium">{client.full_name}</span>
              </span>
            )}
            {process.intake_source && (
              <span className="flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-gray-400 dark:text-slate-500" />
                via {process.intake_source}
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-gray-400 dark:text-slate-500" />
              {new Date(process.created_at).toLocaleDateString('pt-BR', { dateStyle: 'long' })}
            </span>
            <span className="text-xs font-mono text-gray-400 dark:text-slate-500">#{process.id}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
