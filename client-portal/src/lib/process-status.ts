const PROCESS_STATUS_META: Record<
  string,
  {
    label: string;
    className: string;
  }
> = {
  lead: {
    label: 'Lead',
    className: 'bg-amber-100 text-amber-800 border-amber-200',
  },
  triagem: {
    label: 'Triagem',
    className: 'bg-amber-100 text-amber-800 border-amber-200',
  },
  diagnostico: {
    label: 'Diagnóstico',
    className: 'bg-sky-100 text-sky-800 border-sky-200',
  },
  planejamento: {
    label: 'Planejamento',
    className: 'bg-indigo-100 text-indigo-800 border-indigo-200',
  },
  execucao: {
    label: 'Em Execução',
    className: 'bg-blue-100 text-blue-800 border-blue-200',
  },
  protocolo: {
    label: 'Protocolado',
    className: 'bg-cyan-100 text-cyan-800 border-cyan-200',
  },
  aguardando_orgao: {
    label: 'Aguardando Órgão',
    className: 'bg-violet-100 text-violet-800 border-violet-200',
  },
  pendencia_orgao: {
    label: 'Pendência do Órgão',
    className: 'bg-rose-100 text-rose-800 border-rose-200',
  },
  concluido: {
    label: 'Concluído',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  },
  arquivado: {
    label: 'Arquivado',
    className: 'bg-slate-100 text-slate-700 border-slate-200',
  },
  cancelado: {
    label: 'Cancelado',
    className: 'bg-red-100 text-red-800 border-red-200',
  },
  done: {
    label: 'Concluído',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  },
  in_progress: {
    label: 'Em Andamento',
    className: 'bg-blue-100 text-blue-800 border-blue-200',
  },
  blocked: {
    label: 'Com Pendência',
    className: 'bg-red-100 text-red-800 border-red-200',
  },
  todo: {
    label: 'Na Fila',
    className: 'bg-amber-100 text-amber-800 border-amber-200',
  },
};

export function getProcessStatusLabel(status: string | null | undefined): string {
  if (!status) {
    return 'Sem status';
  }

  return PROCESS_STATUS_META[status]?.label ?? status.replaceAll('_', ' ');
}

export function getProcessStatusClass(status: string | null | undefined): string {
  if (!status) {
    return 'bg-slate-100 text-slate-700 border-slate-200';
  }

  return (
    PROCESS_STATUS_META[status]?.className ??
    'bg-slate-100 text-slate-700 border-slate-200'
  );
}
