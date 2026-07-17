/**
 * ProcessDossier — Dossiê técnico do processo (Sprint 3)
 * Exibe dados agregados: imóvel, cliente, documentos e inconsistências.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { AlertTriangle, CheckCircle2, Copy, Info, KeyRound, MapPin, Ruler, User, FileText, RefreshCw } from 'lucide-react';
import { acoesKeys } from '@/lib/acoes/hooks';
import ContiguidadeDeclararLink from './ContiguidadeDeclararLink';

interface Inconsistency {
  severity: string;
  title: string;
  description: string;
  // Backend emite `code`/`field` (dossier.py); guardamos p/ deep-links por alerta.
  code?: string;
  field?: string;
}

/** True quando o alerta é o de contiguidade não declarada (item 4). */
function isContiguidadeAlert(issue: Inconsistency): boolean {
  return issue.code === 'CONTIGUIDADE_NAO_DECLARADA' || issue.field === 'property.matriculas_contiguas';
}

// ─── Selo de 3 estados (Ficha 07 §3.4) ───────────────────────────────────────

type SeloValue = 'nao_validado' | 'human_validated' | 'pendente_oficializacao';
type SeloEntity = 'cliente' | 'imovel' | 'matricula';

// Rótulos COMPLETOS — decisão travada: não abreviar o 2º para "Pendente".
const SELO_OPTIONS: { value: SeloValue; label: string }[] = [
  { value: 'nao_validado',            label: 'Não validado' },
  { value: 'human_validated',         label: 'Validado' },
  { value: 'pendente_oficializacao',  label: 'Correto, pendente de oficialização' },
];

const SELO_BADGE: Record<SeloValue, { label: string; cls: string }> = {
  human_validated:        { label: 'Validado', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400' },
  pendente_oficializacao: { label: 'Correto, pendente de oficialização', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400' },
  nao_validado:           { label: 'Não validado', cls: 'bg-gray-100 text-gray-500 dark:bg-white/5 dark:text-slate-400' },
};

function seloOf(fieldSources: Record<string, string> | undefined, field: string): SeloValue {
  const src = fieldSources?.[field];
  if (src === 'human_validated' || src === 'pendente_oficializacao') return src;
  return 'nao_validado'; // raw | ai_extracted | derived_matricula | ausente — default por construção
}

interface DossierMatricula {
  id: number;
  numero_matricula: string | null;
  geo_certificacao_codigo: string | null;
  geo_certificacao_status: string | null;
  codigo_incra_sncr: string | null;
  nirf_cib: string | null;
  area_ha: number | null;
  field_sources: Record<string, string>;
}

interface DossierAreas {
  area_documental_ha: number | null;
  area_grafica_ha: number | null;
  area_total_matriculas_ha: number | null;
  // Sprint 4 (Ficha 07 §9) — ressalva quando a soma cobre matrículas não
  // declaradas contíguas (anotada, nunca suprimida)
  area_total_nota: string | null;
}

interface SeloPayload {
  entity: SeloEntity;
  entity_id: number;
  field: string;
  selo: SeloValue;
}

interface DossierDocument {
  id: number;
  filename: string;
  document_type?: string;
}

interface PreviousProcess {
  id: number;
  title: string;
  demand_type?: string;
  status: string;
}

interface ProcessDossierProps {
  processId: number;
}

const SEVERITY_CONFIG = {
  error:   { icon: AlertTriangle, cls: 'text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20' },
  warning: { icon: AlertTriangle, cls: 'text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-500/10 border-yellow-200 dark:border-yellow-500/20' },
  info:    { icon: Info,          cls: 'text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20' },
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

  // Selo de 3 estados — grava no field_sources da entidade; o backend cria a
  // ação "Atualização de arquivos oficiais" quando pendente_oficializacao.
  const seloMutation = useMutation({
    mutationFn: async (payload: SeloPayload) => {
      const res = await api.post(`/processes/${processId}/field-selo`, payload);
      return res.data as { acao_criada: boolean };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['dossier', processId] });
      queryClient.invalidateQueries({ queryKey: acoesKeys.list(processId) });
      if (data.acao_criada) {
        toast.success('Selo aplicado — ação "Atualização de arquivos oficiais" criada em Ações');
      } else {
        toast.success('Selo atualizado');
      }
    },
    onError: () => toast.error('Falha ao aplicar o selo'),
  });

  if (isLoading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-10 rounded-xl bg-gray-100 dark:bg-white/5 w-48" />
        <div className="h-32 rounded-2xl bg-gray-100 dark:bg-white/5" />
        <div className="h-32 rounded-2xl bg-gray-100 dark:bg-white/5" />
      </div>
    );
  }

  if (!dossier) return null;

  const { property, client, documents, checklist_summary, previous_processes, inconsistencies } = dossier;
  const errors = inconsistencies?.filter((i: Inconsistency) => i.severity === 'error') ?? [];
  const warnings = inconsistencies?.filter((i: Inconsistency) => i.severity === 'warning') ?? [];

  return (
    <div className="space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {errors.length > 0 && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-600 dark:text-red-400">
              <AlertTriangle className="w-3.5 h-3.5" /> {errors.length} erro(s)
            </span>
          )}
          {warnings.length > 0 && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-yellow-50 dark:bg-yellow-500/10 border border-yellow-200 dark:border-yellow-500/20 text-yellow-700 dark:text-yellow-400">
              <AlertTriangle className="w-3.5 h-3.5" /> {warnings.length} aviso(s)
            </span>
          )}
          {errors.length === 0 && warnings.length === 0 && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" /> Sem inconsistências
            </span>
          )}
        </div>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-500 dark:text-slate-400 hover:text-gray-800 dark:hover:text-white text-xs transition-all disabled:opacity-40"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
          Atualizar
        </button>
      </div>

      {/* Inconsistências */}
      {inconsistencies?.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider px-1">
            Inconsistências Detectadas
          </p>
          {inconsistencies.map((issue: Inconsistency, idx: number) => {
            const cfg = SEVERITY_CONFIG[issue.severity as keyof typeof SEVERITY_CONFIG] ?? SEVERITY_CONFIG.info;
            const Icon = cfg.icon;
            return (
              <div key={idx} className={`flex items-start gap-3 p-3.5 rounded-xl border ${cfg.cls}`}>
                <Icon className="w-4 h-4 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium">{issue.title}</p>
                  <p className="text-xs opacity-75 mt-0.5">{issue.description}</p>
                  {/* Item 4 — leva direto ao controle onde se declara a contiguidade */}
                  {isContiguidadeAlert(issue) && property?.id != null && (
                    <ContiguidadeDeclararLink propertyId={property.id} />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Campos-chave — copiáveis + selo de 3 estados (Ficha 07 §3.4) */}
      {property && (
        <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-7 h-7 rounded-lg bg-violet-50 dark:bg-violet-500/15 flex items-center justify-center">
              <KeyRound className="w-3.5 h-3.5 text-violet-600 dark:text-violet-400" />
            </div>
            <h3 className="text-sm font-semibold text-gray-800 dark:text-slate-200">Campos-chave</h3>
          </div>
          <p className="text-xs text-gray-400 dark:text-slate-500 mb-4">
            Selar como "Correto, pendente de oficialização" cria automaticamente a ação
            "Atualização de arquivos oficiais" em Ações. O selo não trava o avanço do caso.
          </p>
          <div className="space-y-1">
            <KeyFieldRow
              label="CAR"
              value={property.car_code}
              entity="imovel"
              entityId={property.id}
              field="car_code"
              fieldSources={property.field_sources}
              onSelo={p => seloMutation.mutate(p)}
              pending={seloMutation.isPending}
            />
          </div>
          {(property.matriculas as DossierMatricula[] | undefined)?.map(m => (
            <div key={m.id} className="mt-3 rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 p-3">
              <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 mb-1">
                Matrícula {m.numero_matricula ?? `#${m.id}`}
                {m.area_ha != null && <span className="font-normal"> · {m.area_ha} ha</span>}
              </p>
              <div className="space-y-1">
                <KeyFieldRow label="Nº SIGEF" value={m.geo_certificacao_codigo} entity="matricula" entityId={m.id} field="geo_certificacao_codigo" fieldSources={m.field_sources} onSelo={p => seloMutation.mutate(p)} pending={seloMutation.isPending} />
                <KeyFieldRow label="INCRA/SNCR" value={m.codigo_incra_sncr} entity="matricula" entityId={m.id} field="codigo_incra_sncr" fieldSources={m.field_sources} onSelo={p => seloMutation.mutate(p)} pending={seloMutation.isPending} />
                <KeyFieldRow label="NIRF" value={m.nirf_cib} entity="matricula" entityId={m.id} field="nirf_cib" fieldSources={m.field_sources} onSelo={p => seloMutation.mutate(p)} pending={seloMutation.isPending} />
              </div>
            </div>
          ))}
          {(!property.matriculas || property.matriculas.length === 0) && (
            <p className="mt-3 text-xs text-gray-400 dark:text-slate-500">
              Nenhuma matrícula consolidada ainda — SIGEF, INCRA/SNCR e NIRF aparecem aqui após a consolidação.
            </p>
          )}
        </div>
      )}

      {/* Áreas — documental × gráfica × total derivada (Ficha 07 §3.4) */}
      {property && (
        <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg bg-cyan-50 dark:bg-cyan-500/15 flex items-center justify-center">
              <Ruler className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
            </div>
            <h3 className="text-sm font-semibold text-gray-800 dark:text-slate-200">Áreas</h3>
            {/* Sprint 4 — espelho da declaração de contiguidade (edição: Hub do Imóvel) */}
            {property.matriculas_contiguas === true && (
              <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400">
                Matrículas contíguas ✓
              </span>
            )}
            {property.matriculas_contiguas === false && (
              <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400">
                Matrículas NÃO contíguas
              </span>
            )}
            {property.matriculas_contiguas == null && (property.matriculas?.length ?? 0) > 1 && (
              <span className="ml-auto flex items-center gap-2">
                <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-gray-100 text-gray-500 dark:bg-white/5 dark:text-slate-400">
                  Contiguidade não declarada
                </span>
                {property.id != null && <ContiguidadeDeclararLink propertyId={property.id} />}
              </span>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <AreaTile
              label="Documental"
              value={(property.areas as DossierAreas | undefined)?.area_documental_ha ?? null}
              origem={origemLabel(property.field_sources, 'area_documental_ha')}
              note="Sem fonte no staging — dado ausente, não erro."
            />
            <AreaTile
              label="Gráfica"
              value={(property.areas as DossierAreas | undefined)?.area_grafica_ha ?? null}
              origem={origemLabel(property.field_sources, 'area_grafica_ha')}
              note="Sem fonte no staging — dado ausente, não erro."
            />
            <AreaTile
              label="Total"
              value={(property.areas as DossierAreas | undefined)?.area_total_matriculas_ha ?? null}
              origem="Derivada da soma das matrículas"
              note="Sem matrícula com área consolidada ainda."
              ressalva={(property.areas as DossierAreas | undefined)?.area_total_nota ?? null}
            />
          </div>
        </div>
      )}

      {/* Dados do Imóvel */}
      <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-7 h-7 rounded-lg bg-emerald-50 dark:bg-emerald-500/15 flex items-center justify-center">
            <MapPin className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <h3 className="text-sm font-semibold text-gray-800 dark:text-slate-200">Imóvel Rural</h3>
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
              <div key={f.label} className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 p-3">
                <p className="text-xs text-gray-400 dark:text-slate-500 mb-0.5">{f.label}</p>
                <p className="text-sm font-semibold text-gray-800 dark:text-white">{f.value}</p>
              </div>
            ))}
            <div className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 p-3 flex flex-col gap-1">
              <p className="text-xs text-gray-400 dark:text-slate-500">Situações</p>
              <div className="flex flex-wrap gap-1">
                {property.has_embargo && (
                  <span className="px-1.5 py-0.5 text-xs rounded bg-red-50 dark:bg-red-500/20 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-500/20">Embargo</span>
                )}
                {property.has_geom && (
                  <span className="px-1.5 py-0.5 text-xs rounded bg-emerald-50 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">Georref.</span>
                )}
                {!property.has_embargo && !property.has_geom && (
                  <span className="text-xs text-gray-400 dark:text-slate-500">—</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-400 dark:text-slate-500">Nenhum imóvel vinculado a este processo.</p>
        )}
      </div>

      {/* Dados do Cliente */}
      <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-500/15 flex items-center justify-center">
            <User className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
          </div>
          <h3 className="text-sm font-semibold text-gray-800 dark:text-slate-200">Cliente</h3>
        </div>
        {client ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { label: 'Nome', value: client.full_name },
              { label: 'CPF/CNPJ', value: client.document_number ?? '—' },
              { label: 'Telefone', value: client.phone ?? '—' },
              { label: 'E-mail', value: client.email ?? '—' },
            ].map(f => (
              <div key={f.label} className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 p-3">
                <p className="text-xs text-gray-400 dark:text-slate-500 mb-0.5">{f.label}</p>
                <p className="text-sm font-semibold text-gray-800 dark:text-white">{f.value}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400 dark:text-slate-500">Cliente não encontrado.</p>
        )}
      </div>

      {/* Documentos + Checklist */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg bg-indigo-50 dark:bg-indigo-500/15 flex items-center justify-center">
              <FileText className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <h3 className="text-sm font-semibold text-gray-800 dark:text-slate-200">Documentos</h3>
          </div>
          {documents?.length > 0 ? (
            <div className="space-y-1.5">
              {documents.slice(0, 6).map((doc: DossierDocument) => (
                <div key={doc.id} className="flex items-center justify-between text-xs">
                  <span className="text-gray-600 dark:text-slate-300 truncate flex-1">{doc.filename}</span>
                  {doc.document_type && (
                    <span className="ml-2 px-1.5 py-0.5 rounded bg-gray-100 dark:bg-white/5 text-gray-500 dark:text-slate-400 shrink-0">
                      {doc.document_type}
                    </span>
                  )}
                </div>
              ))}
              {documents.length > 6 && (
                <p className="text-xs text-gray-400 dark:text-slate-500">+{documents.length - 6} outros</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400 dark:text-slate-500">Nenhum documento enviado.</p>
          )}
        </div>

        <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
          <h3 className="text-sm font-semibold text-gray-800 dark:text-slate-200 mb-3">Checklist Documental</h3>
          {checklist_summary ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-slate-400">Progresso</span>
                <span className="font-bold text-gray-900 dark:text-white">{checklist_summary.completion_pct}%</span>
              </div>
              <div className="w-full bg-gray-100 dark:bg-white/5 rounded-full h-2">
                <div
                  className="bg-emerald-500 h-2 rounded-full transition-all"
                  style={{ width: `${checklist_summary.completion_pct}%` }}
                />
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  { label: 'Recebidos',   value: checklist_summary.received, cls: 'text-emerald-600 dark:text-emerald-400' },
                  { label: 'Pendentes',   value: checklist_summary.pending,  cls: 'text-yellow-600 dark:text-yellow-400' },
                  { label: 'Dispensados', value: checklist_summary.waived,   cls: 'text-gray-500 dark:text-slate-400' },
                ].map(s => (
                  <div key={s.label} className="rounded-xl bg-gray-50 dark:bg-white/5 p-2">
                    <p className={`text-lg font-bold ${s.cls}`}>{s.value}</p>
                    <p className="text-xs text-gray-400 dark:text-slate-500">{s.label}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400 dark:text-slate-500">Checklist não gerado ainda.</p>
          )}
        </div>
      </div>

      {/* Histórico de processos */}
      {previous_processes?.length > 0 && (
        <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-5">
          <h3 className="text-sm font-semibold text-gray-800 dark:text-slate-200 mb-3">Histórico do Cliente</h3>
          <div className="space-y-2">
            {previous_processes.map((p: PreviousProcess) => (
              <div key={p.id} className="flex items-center justify-between text-sm py-1.5 border-b border-gray-50 dark:border-white/5 last:border-0">
                <span className="text-gray-700 dark:text-slate-300">{p.title}</span>
                <div className="flex items-center gap-2">
                  {p.demand_type && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-white/5 text-gray-500 dark:text-slate-400">{p.demand_type}</span>
                  )}
                  <span className="text-xs text-gray-400 dark:text-slate-500">{p.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Auxiliares do selo / campos-chave / áreas ───────────────────────────────

const ORIGEM_LABEL: Record<string, string> = {
  raw: 'Bruto',
  ai_extracted: 'Extraído por IA',
  human_validated: 'Validado pelo consultor',
  pendente_oficializacao: 'Correto, pendente de oficialização',
  derived_matricula: 'Derivado da matrícula',
};

function origemLabel(fieldSources: Record<string, string> | undefined, field: string): string {
  const src = fieldSources?.[field];
  return src ? (ORIGEM_LABEL[src] ?? src) : 'Consolidado do staging';
}

function KeyFieldRow({
  label,
  value,
  entity,
  entityId,
  field,
  fieldSources,
  onSelo,
  pending,
}: {
  label: string;
  value: string | null | undefined;
  entity: SeloEntity;
  entityId: number;
  field: string;
  fieldSources: Record<string, string> | undefined;
  onSelo: (payload: SeloPayload) => void;
  pending: boolean;
}) {
  const selo = seloOf(fieldSources, field);
  const badge = SELO_BADGE[selo];

  const copy = async () => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label} copiado`);
    } catch {
      toast.error('Não foi possível copiar');
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 py-1.5 border-b border-gray-50 dark:border-white/5 last:border-0">
      <span className="text-xs text-gray-400 dark:text-slate-500 w-24 shrink-0">{label}</span>
      <span className="text-sm font-mono font-semibold text-gray-800 dark:text-white truncate">
        {value ?? '—'}
      </span>
      {value && (
        <button
          onClick={copy}
          title={`Copiar ${label}`}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-white/10 text-gray-400 hover:text-gray-700 dark:hover:text-white transition-colors"
        >
          <Copy className="w-3.5 h-3.5" />
        </button>
      )}
      <span className={`px-1.5 py-0.5 text-[10px] rounded font-medium ${badge.cls}`}>{badge.label}</span>
      <select
        value={selo}
        disabled={pending}
        onChange={e => onSelo({ entity, entity_id: entityId, field, selo: e.target.value as SeloValue })}
        aria-label={`Selo de ${label}`}
        className="ml-auto text-xs rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 px-2 py-1 disabled:opacity-40"
      >
        {SELO_OPTIONS.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

function AreaTile({
  label,
  value,
  origem,
  note,
  ressalva,
}: {
  label: string;
  value: number | null;
  origem: string;
  note: string;
  ressalva?: string | null;
}) {
  return (
    <div className="rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/5 p-3">
      <p className="text-xs text-gray-400 dark:text-slate-500 mb-0.5">{label}</p>
      <p className="text-sm font-semibold text-gray-800 dark:text-white">
        {value != null ? `${value} ha` : '—'}
      </p>
      <p className="text-[10px] text-gray-400 dark:text-slate-500 mt-1">
        {value != null ? origem : note}
      </p>
      {value != null && ressalva && (
        <p className="text-[10px] text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-1.5 mt-1.5">
          ⚠ {ressalva}
        </p>
      )}
    </div>
  );
}
