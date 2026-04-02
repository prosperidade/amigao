/**
 * ProcessDossier — Dossiê técnico do processo (Sprint 3)
 * Exibe dados agregados: imóvel, cliente, documentos e inconsistências.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { AlertTriangle, CheckCircle2, Info, MapPin, User, FileText, RefreshCw } from 'lucide-react';

interface ProcessDossierProps {
  processId: number;
}

const SEVERITY_CONFIG = {
  error:   { icon: AlertTriangle, cls: 'text-red-400 bg-red-500/10 border-red-500/20' },
  warning: { icon: AlertTriangle, cls: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' },
  info:    { icon: Info, cls: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
};

export default function ProcessDossier({ processId }: ProcessDossierProps) {
  const queryClient = useQueryClient();

  const { data: dossier, isLoading } = useQuery({
    queryKey: ['dossier', processId],
    queryFn: async () => {
      const res = await api.get(`/processes/${processId}/dossier`);
      return res.data;
    },
  });

  const refreshMutation = useMutation({
    mutationFn: () => api.post(`/processes/${processId}/dossier/refresh`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['dossier', processId] }),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="animate-spin text-2xl text-slate-500">⟳</div>
      </div>
    );
  }

  if (!dossier) return null;

  const { property, client, documents, checklist_summary, tasks_summary, previous_processes, inconsistencies } = dossier;
  const errors = inconsistencies?.filter((i: any) => i.severity === 'error') ?? [];
  const warnings = inconsistencies?.filter((i: any) => i.severity === 'warning') ?? [];

  return (
    <div className="space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {errors.length > 0 && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 border border-red-500/20 text-red-400">
              <AlertTriangle className="w-3.5 h-3.5" /> {errors.length} erro(s)
            </span>
          )}
          {warnings.length > 0 && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-yellow-500/10 border border-yellow-500/20 text-yellow-400">
              <AlertTriangle className="w-3.5 h-3.5" /> {warnings.length} aviso(s)
            </span>
          )}
          {errors.length === 0 && warnings.length === 0 && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" /> Sem inconsistências
            </span>
          )}
        </div>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:text-white text-xs transition-all disabled:opacity-40"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
          Atualizar
        </button>
      </div>

      {/* Inconsistências */}
      {inconsistencies?.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1">
            Inconsistências Detectadas
          </p>
          {inconsistencies.map((issue: any, idx: number) => {
            const cfg = SEVERITY_CONFIG[issue.severity as keyof typeof SEVERITY_CONFIG] ?? SEVERITY_CONFIG.info;
            const Icon = cfg.icon;
            return (
              <div key={idx} className={`flex items-start gap-3 p-3.5 rounded-xl border ${cfg.cls}`}>
                <Icon className="w-4 h-4 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium">{issue.title}</p>
                  <p className="text-xs opacity-75 mt-0.5">{issue.description}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Dados do Imóvel */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
        <div className="flex items-center gap-2 mb-4">
          <MapPin className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold text-slate-200">Imóvel Rural</h3>
        </div>
        {property ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { label: 'Nome', value: property.name },
              { label: 'Matrícula', value: property.registry_number ?? '—' },
              { label: 'CCIR', value: property.ccir ?? '—' },
              { label: 'NIRF', value: property.nirf ?? '—' },
              { label: 'CAR', value: property.car_code ?? '—' },
              { label: 'Status CAR', value: property.car_status ?? '—' },
              { label: 'Área (ha)', value: property.total_area_ha ? `${property.total_area_ha} ha` : '—' },
              { label: 'Município/UF', value: property.municipality ? `${property.municipality}/${property.state ?? ''}` : '—' },
              { label: 'Bioma', value: property.biome ?? '—' },
            ].map(f => (
              <div key={f.label} className="rounded-xl bg-white/5 border border-white/5 p-3">
                <p className="text-xs text-slate-500 mb-0.5">{f.label}</p>
                <p className="text-sm font-medium text-white">{f.value}</p>
              </div>
            ))}
            <div className="rounded-xl bg-white/5 border border-white/5 p-3 flex flex-col gap-1">
              <p className="text-xs text-slate-500">Situações</p>
              <div className="flex flex-wrap gap-1">
                {property.has_embargo && (
                  <span className="px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/20">Embargo</span>
                )}
                {property.has_geom && (
                  <span className="px-1.5 py-0.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/20">Georref.</span>
                )}
                {!property.has_embargo && !property.has_geom && (
                  <span className="text-xs text-slate-500">—</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">Nenhum imóvel vinculado a este processo.</p>
        )}
      </div>

      {/* Dados do Cliente */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
        <div className="flex items-center gap-2 mb-4">
          <User className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-semibold text-slate-200">Cliente</h3>
        </div>
        {client ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { label: 'Nome', value: client.full_name },
              { label: 'CPF/CNPJ', value: client.document_number ?? '—' },
              { label: 'Telefone', value: client.phone ?? '—' },
              { label: 'E-mail', value: client.email ?? '—' },
            ].map(f => (
              <div key={f.label} className="rounded-xl bg-white/5 border border-white/5 p-3">
                <p className="text-xs text-slate-500 mb-0.5">{f.label}</p>
                <p className="text-sm font-medium text-white">{f.value}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Cliente não encontrado.</p>
        )}
      </div>

      {/* Documentos + Checklist */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-slate-200">Documentos</h3>
          </div>
          {documents?.length > 0 ? (
            <div className="space-y-1.5">
              {documents.slice(0, 6).map((doc: any) => (
                <div key={doc.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate flex-1">{doc.filename}</span>
                  {doc.document_type && (
                    <span className="ml-2 px-1.5 py-0.5 rounded bg-white/5 text-slate-400 shrink-0">
                      {doc.document_type}
                    </span>
                  )}
                </div>
              ))}
              {documents.length > 6 && (
                <p className="text-xs text-slate-500">+{documents.length - 6} outros</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-500">Nenhum documento enviado.</p>
          )}
        </div>

        <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-3">Checklist Documental</h3>
          {checklist_summary ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">Progresso</span>
                <span className="font-semibold text-white">{checklist_summary.completion_pct}%</span>
              </div>
              <div className="w-full bg-white/5 rounded-full h-2">
                <div
                  className="bg-emerald-500 h-2 rounded-full transition-all"
                  style={{ width: `${checklist_summary.completion_pct}%` }}
                />
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  { label: 'Recebidos', value: checklist_summary.received, cls: 'text-emerald-400' },
                  { label: 'Pendentes', value: checklist_summary.pending, cls: 'text-yellow-400' },
                  { label: 'Dispensados', value: checklist_summary.waived, cls: 'text-slate-400' },
                ].map(s => (
                  <div key={s.label} className="rounded-xl bg-white/5 p-2">
                    <p className={`text-lg font-bold ${s.cls}`}>{s.value}</p>
                    <p className="text-xs text-slate-500">{s.label}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Checklist não gerado ainda.</p>
          )}
        </div>
      </div>

      {/* Histórico de processos */}
      {previous_processes?.length > 0 && (
        <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-3">Histórico do Cliente</h3>
          <div className="space-y-2">
            {previous_processes.map((p: any) => (
              <div key={p.id} className="flex items-center justify-between text-sm">
                <span className="text-slate-300">{p.title}</span>
                <div className="flex items-center gap-2">
                  {p.demand_type && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-white/5 text-slate-400">{p.demand_type}</span>
                  )}
                  <span className="text-xs text-slate-500">{p.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
