/**
 * PropertyHub — Hub técnico do imóvel (Regente Cam2 — CAM2IH-001 a CAM2IH-010).
 *
 * Layout:
 *  Bloco 1 — Cabeçalho (identificação + status regulatório + chips + ações)
 *  Bloco 2 — Dashboard técnico (KPIs)
 *  Bloco 6 — Indicadores de saúde (score 0-100)
 *  Painel lateral — Leitura da IA (Bloco 4)
 *  5 Abas: Informações / Documentos / Análises / Histórico / Casos
 */
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  ArrowLeft, MapPin, FileText, BarChart3, Briefcase,
  AlertTriangle, Plus, Sparkles, Shield,
} from 'lucide-react';
import { api } from '@/lib/api';
import { MACROETAPA_STATE_BADGE } from '@/pages/Processes/quadro-types';

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface PropertyHubHeader {
  id: number;
  name: string;
  client_id: number;
  client_name: string | null;
  registry_number: string | null;
  ccir: string | null;
  nirf: string | null;
  car_code: string | null;
  car_status: string | null;
  total_area_ha: number | null;
  municipality: string | null;
  state: string | null;
  biome: string | null;
  has_embargo: boolean;
  created_at: string | null;
  field_sources: Record<string, string>;
  // CAM2IH-003/004 (Sprint H) — campos técnicos
  rl_status: string | null;
  app_area_ha: number | null;
  regulatory_issues: Array<{ tipo?: string; descricao?: string; severidade?: string }>;
  area_documental_ha: number | null;
  area_grafica_ha: number | null;
  tipologia: string | null;
  strategic_notes: string | null;
}

// CAM2IH-010 (Sprint H) — labels pt-BR das 6 categorias canônicas Regente.
const CATEGORY_LABELS: Record<string, string> = {
  fundiarios: 'Fundiários',
  ambientais: 'Ambientais',
  fiscais_rurais: 'Fiscais/Rurais',
  societarios: 'Societários',
  espaciais: 'Espaciais (KML/SIGEF)',
  relatorios_gerados: 'Relatórios gerados',
};

// CAM2IH-007 — Origem dos dados
const FIELD_SOURCE_BADGE: Record<string, { icon: string; label: string; cls: string }> = {
  raw:              { icon: '📥', label: 'Bruto',          cls: 'bg-gray-100 text-gray-600' },
  ai_extracted:     { icon: '🤖', label: 'Extraído por IA', cls: 'bg-sky-100 text-sky-700' },
  human_validated:  { icon: '✓', label: 'Validado',        cls: 'bg-emerald-100 text-emerald-700' },
};

interface PropertyHubChips {
  has_car: boolean;
  car_pending: boolean;
  has_embargo: boolean;
  has_active_cases: boolean;
  has_doc_pending: boolean;
}

interface PropertyHubKpis {
  cases_count: number;
  cases_active: number;
  documents_count: number;
  analyses_count: number;
  last_document_at: string | null;
  last_analysis_at: string | null;
  last_activity_at: string | null;
  pending_critical: number;
}

interface PropertyHealthScore {
  overall: number;
  documental_completeness: number;
  regulatory_update: number;
  analysis_depth: number;
  consistency: number;
  confidence_base: number;
  pending_critical: number;
  label: string;
}

interface PropertyHubSummary {
  header: PropertyHubHeader;
  chips: PropertyHubChips;
  kpis: PropertyHubKpis;
  health: PropertyHealthScore;
  state: string;
}

interface PropertyCase {
  id: number;
  title: string;
  demand_type: string | null;
  urgency: string | null;
  macroetapa: string | null;
  macroetapa_label: string | null;
  state: string | null;
  next_step: string | null;
  responsible_user_name: string | null;
  last_activity_at: string | null;
}

interface PropertyEvent {
  when: string;
  kind: string;
  label: string;
  entity_type: string;
  entity_id: number | null;
  macroetapa: string | null;
}

interface PropertyAISummary {
  text: string;
  main_inconsistency: string | null;
  top_pending: string | null;
  recommendation: string | null;
  source: string;
}

const HUB_STATE_LABEL: Record<string, { label: string; cls: string }> = {
  recem_criado:         { label: 'Recém-criado', cls: 'bg-gray-100 text-gray-700' },
  em_construcao:        { label: 'Em construção', cls: 'bg-blue-100 text-blue-700' },
  memoria_estruturada:  { label: 'Memória estruturada', cls: 'bg-emerald-100 text-emerald-700' },
  com_alertas:          { label: 'Com alertas', cls: 'bg-red-100 text-red-700' },
  consolidado:          { label: 'Consolidado', cls: 'bg-violet-100 text-violet-700' },
};

type TabKey = 'info' | 'documents' | 'analyses' | 'history' | 'cases';

// ─── Componente ───────────────────────────────────────────────────────────────

export default function PropertyHub() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const propertyId = parseInt(id ?? '0', 10);
  const [tab, setTab] = useState<TabKey>('info');

  // CAM2IH-007 — validar campos
  const validateFields = useMutation({
    mutationFn: (fields: string[]) =>
      api.post(`/properties/${propertyId}/validate-fields`, { fields, source: 'human_validated' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['property-hub-summary', propertyId] });
      toast.success('Campo validado');
    },
    onError: () => toast.error('Falha ao validar campo'),
  });

  const { data: summary, isLoading } = useQuery({
    queryKey: ['property-hub-summary', propertyId],
    queryFn: () => api.get<PropertyHubSummary>(`/properties/${propertyId}/summary`).then(r => r.data),
    enabled: !!propertyId,
  });

  const { data: cases = [] } = useQuery({
    queryKey: ['property-hub-cases', propertyId],
    queryFn: () => api.get<PropertyCase[]>(`/properties/${propertyId}/cases`).then(r => r.data),
    enabled: !!propertyId,
  });

  const { data: events = [] } = useQuery({
    queryKey: ['property-hub-events', propertyId],
    queryFn: () => api.get<PropertyEvent[]>(`/properties/${propertyId}/events?limit=50`).then(r => r.data),
    enabled: !!propertyId,
  });

  const { data: ai } = useQuery({
    queryKey: ['property-hub-ai', propertyId],
    queryFn: () => api.get<PropertyAISummary>(`/properties/${propertyId}/ai-summary`).then(r => r.data),
    enabled: !!propertyId,
    staleTime: 60_000,
  });

  if (isLoading || !summary) {
    return (
      <div className="max-w-7xl mx-auto space-y-4 animate-pulse">
        <div className="h-32 rounded-2xl bg-gray-100 dark:bg-white/5" />
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-24 rounded-2xl bg-gray-100 dark:bg-white/5" />)}
        </div>
      </div>
    );
  }

  const { header, chips, kpis, health, state } = summary;
  const hubState = HUB_STATE_LABEL[state] ?? { label: state, cls: 'bg-gray-100 text-gray-700' };

  const primaryCase = cases.find(c => !!c.macroetapa) ?? cases[0];

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <button
        onClick={() => navigate('/properties')}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-slate-400 hover:text-gray-800 dark:hover:text-white"
      >
        <ArrowLeft className="w-4 h-4" /> Voltar para imóveis
      </button>

      {/* Bloco 1 — Cabeçalho */}
      <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5 space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-12 h-12 rounded-2xl bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center text-emerald-700 dark:text-emerald-300 shrink-0">
              <MapPin className="w-6 h-6" />
            </div>
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-gray-900 dark:text-white truncate">{header.name}</h1>
              <p className="text-xs text-gray-500 dark:text-slate-400">
                ID #{header.id}
                {header.client_name && (
                  <> · cliente: <button onClick={() => navigate(`/clients/${header.client_id}`)} className="underline hover:text-emerald-600">{header.client_name}</button></>
                )}
                {header.municipality && header.state && ` · ${header.municipality}/${header.state}`}
              </p>
            </div>
          </div>
          <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${hubState.cls}`}>
            {hubState.label}
          </span>
        </div>

        {/* Identificação técnica com badges de origem (CAM2IH-007) */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 text-sm">
          <InfoField
            label="Matrícula"
            value={header.registry_number}
            source={header.field_sources.registry_number}
            onValidate={() => validateFields.mutate(['registry_number'])}
          />
          <InfoField
            label="CAR"
            value={header.car_code}
            sub={header.car_status}
            source={header.field_sources.car_code}
            onValidate={() => validateFields.mutate(['car_code'])}
          />
          <InfoField
            label="CCIR"
            value={header.ccir}
            source={header.field_sources.ccir}
            onValidate={() => validateFields.mutate(['ccir'])}
          />
          <InfoField
            label="NIRF"
            value={header.nirf}
            source={header.field_sources.nirf}
            onValidate={() => validateFields.mutate(['nirf'])}
          />
          <InfoField
            label="Área"
            value={header.total_area_ha ? `${header.total_area_ha} ha` : null}
            sub={header.biome}
            source={header.field_sources.total_area_ha}
            onValidate={() => validateFields.mutate(['total_area_ha'])}
          />
        </div>

        {/* Chips */}
        <div className="flex flex-wrap gap-1.5">
          {chips.has_car
            ? (chips.car_pending
                ? <Chip cls="bg-amber-100 text-amber-700">⚠ CAR pendente</Chip>
                : <Chip cls="bg-emerald-100 text-emerald-700">CAR cadastrado</Chip>)
            : <Chip cls="bg-red-100 text-red-700">Sem CAR</Chip>}
          {chips.has_embargo && <Chip cls="bg-red-100 text-red-700">🚫 Embargo</Chip>}
          {chips.has_active_cases && <Chip cls="bg-blue-100 text-blue-700">Casos em andamento</Chip>}
          {chips.has_doc_pending && <Chip cls="bg-amber-100 text-amber-700">Pendência documental</Chip>}
        </div>

        {/* CTAs — CAM2IH-009: CTA principal é sempre "Abrir workspace" */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100 dark:border-white/10">
          {primaryCase ? (
            <button
              onClick={() => navigate(`/processes/${primaryCase.id}`)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-semibold"
            >
              <Briefcase className="w-3.5 h-3.5" /> Abrir workspace do caso
            </button>
          ) : (
            <button
              onClick={() => navigate('/intake')}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-semibold"
            >
              <Plus className="w-3.5 h-3.5" /> Abrir primeiro caso
            </button>
          )}
          <button
            onClick={() => navigate('/intake')}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-sm text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-white/10"
          >
            <Plus className="w-3.5 h-3.5" /> Novo caso neste imóvel
          </button>
        </div>
      </div>

      {/* Bloco 2 — Dashboard técnico + Bloco 6 — Health score */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KpiCard label="Casos" value={kpis.cases_count} sub={`${kpis.cases_active} ativos`} icon={<Briefcase className="w-4 h-4" />} />
          <KpiCard label="Documentos" value={kpis.documents_count} icon={<FileText className="w-4 h-4" />} />
          <KpiCard label="Análises" value={kpis.analyses_count} icon={<BarChart3 className="w-4 h-4" />} />
          <KpiCard label="Pendências" value={kpis.pending_critical} alarm={kpis.pending_critical > 0} icon={<AlertTriangle className="w-4 h-4" />} />
        </div>
        <HealthScoreCard health={health} />
      </div>

      {/* Grid: conteúdo (abas) + painel lateral IA */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 overflow-hidden min-w-0">
          <div className="border-b border-gray-100 dark:border-white/10 flex overflow-x-auto">
            {([
              { k: 'info', l: 'Informações' },
              { k: 'documents', l: `Documentos (${kpis.documents_count})` },
              { k: 'analyses', l: `Análises (${kpis.analyses_count})` },
              { k: 'history', l: 'Histórico' },
              { k: 'cases', l: `Casos (${kpis.cases_count})` },
            ] as { k: TabKey; l: string }[]).map(({ k, l }) => {
              const active = tab === k;
              return (
                <button
                  key={k}
                  onClick={() => setTab(k)}
                  className={`px-4 py-3 text-sm font-medium border-b-2 transition-all -mb-px whitespace-nowrap shrink-0 ${
                    active
                      ? 'border-emerald-500 text-emerald-700 dark:text-emerald-400 bg-emerald-50/50 dark:bg-emerald-500/5'
                      : 'border-transparent text-gray-500 dark:text-slate-400 hover:text-gray-800 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-white/5'
                  }`}
                >
                  {l}
                </button>
              );
            })}
          </div>
          <div className="p-5">
            {tab === 'info' && <InfoTab header={header} kpis={kpis} onValidate={(fields) => validateFields.mutate(fields)} />}
            {tab === 'documents' && <DocumentsTab propertyId={propertyId} />}
            {tab === 'analyses' && <AnalysesTab propertyId={propertyId} count={kpis.analyses_count} cases={cases} />}
            {tab === 'history' && <HistoryTab events={events} />}
            {tab === 'cases' && <CasesTab cases={cases} navigate={navigate} />}
          </div>
        </div>

        {/* CAM2IH-005 — Painel lateral IA */}
        <aside className="lg:sticky lg:top-4 h-fit">
          <AIPanel summary={ai} />
        </aside>
      </div>
    </div>
  );
}

// ─── Sub-componentes ──────────────────────────────────────────────────────────

function Chip({ cls, children }: { cls: string; children: React.ReactNode }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{children}</span>;
}

function InfoField({
  label, value, sub, source, onValidate,
}: {
  label: string;
  value: string | null;
  sub?: string | null;
  source?: string;
  onValidate?: () => void;
}) {
  const badge = source ? FIELD_SOURCE_BADGE[source] : null;
  const canValidate = !!onValidate && source && source !== 'human_validated' && value;
  return (
    <div>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] uppercase tracking-wide text-gray-400 font-medium">{label}</span>
        {badge && (
          <span
            title={badge.label}
            className={`text-[9px] px-1 py-0 rounded font-medium ${badge.cls}`}
          >
            {badge.icon}
          </span>
        )}
      </div>
      <div className="text-sm text-gray-900 dark:text-slate-100 font-medium truncate">{value || '—'}</div>
      {sub && <div className="text-[10px] text-gray-500 truncate">{sub}</div>}
      {canValidate && (
        <button
          onClick={onValidate}
          className="mt-0.5 text-[10px] text-emerald-600 dark:text-emerald-400 hover:underline"
        >
          ✓ Validar
        </button>
      )}
    </div>
  );
}

function KpiCard({ label, value, sub, icon, alarm }: {
  label: string; value: number; sub?: string; icon: React.ReactNode; alarm?: boolean;
}) {
  return (
    <div className={`rounded-2xl border p-3 ${
      alarm
        ? 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30'
        : 'bg-white dark:bg-white/5 border-gray-100 dark:border-white/10'
    }`}>
      <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-slate-400 font-medium">
        {icon}
        <span className="truncate">{label}</span>
      </div>
      <div className={`mt-1 text-2xl font-bold ${alarm ? 'text-red-700 dark:text-red-300' : 'text-gray-900 dark:text-white'}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function HealthScoreCard({ health }: { health: PropertyHealthScore }) {
  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Shield className="w-4 h-4 text-emerald-600" />
        <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-slate-400 font-semibold">
          Saúde do imóvel
        </span>
      </div>
      <div className="flex items-baseline gap-2 mb-3">
        <span className="text-3xl font-bold text-gray-900 dark:text-white">{health.overall}</span>
        <span className="text-sm text-gray-500">/100</span>
        <span className="ml-auto text-xs px-2 py-0.5 rounded-full font-medium capitalize bg-gray-100 dark:bg-white/5">
          {health.label}
        </span>
      </div>
      <div className="space-y-2">
        <ScoreBar label="Docs" value={health.documental_completeness} />
        <ScoreBar label="Regulatório" value={health.regulatory_update} />
        <ScoreBar label="Análises" value={health.analysis_depth} />
        <ScoreBar label="Consistência" value={health.consistency} />
      </div>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = value >= 75 ? 'bg-emerald-500' : value >= 50 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div>
      <div className="flex justify-between text-[10px] mb-0.5">
        <span className="text-gray-500 dark:text-slate-400">{label}</span>
        <span className="text-gray-700 dark:text-slate-200 font-medium">{value}</span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 dark:bg-zinc-800 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function AIPanel({ summary }: { summary: PropertyAISummary | undefined }) {
  if (!summary) return <div className="h-48 rounded-2xl bg-gray-100 dark:bg-white/5 animate-pulse" />;
  return (
    <div className="rounded-2xl bg-gradient-to-br from-violet-50 to-sky-50 dark:from-violet-500/10 dark:to-sky-500/10 border border-violet-200 dark:border-violet-500/30 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-violet-600 dark:text-violet-400" />
        <span className="text-xs uppercase tracking-wide text-violet-700 dark:text-violet-300 font-semibold">
          Leitura técnica da IA
        </span>
      </div>
      <p className="text-sm text-gray-800 dark:text-slate-100 leading-relaxed">{summary.text}</p>
      {summary.main_inconsistency && (
        <div className="text-xs text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-lg p-2">
          <strong>⚠ Inconsistência:</strong> {summary.main_inconsistency}
        </div>
      )}
      {summary.top_pending && (
        <div className="text-xs text-amber-800 dark:text-amber-200 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-2">
          <strong>Pendência:</strong> {summary.top_pending}
        </div>
      )}
      {summary.recommendation && (
        <div className="text-xs text-emerald-800 dark:text-emerald-200 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 rounded-lg p-2">
          <strong>💡</strong> {summary.recommendation}
        </div>
      )}
      <div className="text-[10px] text-gray-400 pt-1 border-t border-violet-200 dark:border-violet-500/30">
        Fonte: análise automática
      </div>
    </div>
  );
}

function InfoTab({ header, kpis, onValidate }: {
  header: PropertyHubHeader;
  kpis: PropertyHubKpis;
  onValidate?: (fields: string[]) => void;
}) {
  const src = header.field_sources;
  return (
    <div className="space-y-4">
      <section>
        <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-2">
          Identificação
          <span className="ml-2 text-[10px] font-normal text-gray-400">
            {Object.entries(FIELD_SOURCE_BADGE).map(([k, b]) => (
              <span key={k} className={`mr-1 px-1 rounded ${b.cls}`}>{b.icon} {b.label}</span>
            ))}
          </span>
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <InfoField label="Nome" value={header.name} />
          <InfoField label="Matrícula" value={header.registry_number} source={src.registry_number} onValidate={onValidate ? () => onValidate(['registry_number']) : undefined} />
          <InfoField label="CAR" value={header.car_code} sub={header.car_status} source={src.car_code} onValidate={onValidate ? () => onValidate(['car_code']) : undefined} />
          <InfoField label="CCIR" value={header.ccir} source={src.ccir} onValidate={onValidate ? () => onValidate(['ccir']) : undefined} />
          <InfoField label="NIRF" value={header.nirf} source={src.nirf} onValidate={onValidate ? () => onValidate(['nirf']) : undefined} />
          <InfoField label="Área total" value={header.total_area_ha ? `${header.total_area_ha} ha` : null} source={src.total_area_ha} onValidate={onValidate ? () => onValidate(['total_area_ha']) : undefined} />
          <InfoField label="Localização" value={header.municipality && header.state ? `${header.municipality}/${header.state}` : null} />
          <InfoField label="Bioma" value={header.biome} source={src.biome} />
          <InfoField label="Embargo" value={header.has_embargo ? 'Sim' : 'Não'} />
        </div>
      </section>
      {/* CAM2IH-003/004 (Sprint H) — Dados técnicos ambientais */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-2">Dados técnicos</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <InfoField
            label="Reserva Legal"
            value={header.rl_status}
            source={src.rl_status}
            onValidate={onValidate ? () => onValidate(['rl_status']) : undefined}
          />
          <InfoField
            label="Área APP"
            value={header.app_area_ha != null ? `${header.app_area_ha} ha` : null}
            source={src.app_area_ha}
            onValidate={onValidate ? () => onValidate(['app_area_ha']) : undefined}
          />
          <InfoField
            label="Área documental"
            value={header.area_documental_ha != null ? `${header.area_documental_ha} ha` : null}
            source={src.area_documental_ha}
            onValidate={onValidate ? () => onValidate(['area_documental_ha']) : undefined}
          />
          <InfoField
            label="Área gráfica"
            value={header.area_grafica_ha != null ? `${header.area_grafica_ha} ha` : null}
            sub={
              header.area_documental_ha != null && header.area_grafica_ha != null
              && Math.abs(header.area_documental_ha - header.area_grafica_ha) > 0.5
                ? '⚠ divergência com documental'
                : undefined
            }
            source={src.area_grafica_ha}
            onValidate={onValidate ? () => onValidate(['area_grafica_ha']) : undefined}
          />
          <InfoField
            label="Tipologia"
            value={header.tipologia}
            source={src.tipologia}
            onValidate={onValidate ? () => onValidate(['tipologia']) : undefined}
          />
        </div>
        {header.regulatory_issues && header.regulatory_issues.length > 0 && (
          <div className="mt-3 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 p-3">
            <p className="text-[10px] uppercase tracking-wide text-amber-700 dark:text-amber-300 font-semibold mb-1.5">
              Pendências ambientais ({header.regulatory_issues.length})
            </p>
            <ul className="space-y-1 text-xs text-amber-900 dark:text-amber-100">
              {header.regulatory_issues.map((iss, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
                  <span>
                    {iss.tipo && <strong>{iss.tipo}: </strong>}
                    {iss.descricao ?? '—'}
                    {iss.severidade && <span className="ml-1 text-[10px] text-amber-700">[{iss.severidade}]</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {header.strategic_notes && (
          <div className="mt-3 rounded-xl bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 p-3">
            <p className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold mb-1">Observações estratégicas</p>
            <p className="text-xs text-gray-700 dark:text-slate-200 whitespace-pre-line">{header.strategic_notes}</p>
          </div>
        )}
      </section>

      <section>
        <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-2">Atividade</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <InfoField label="Último documento" value={kpis.last_document_at ? formatRelative(kpis.last_document_at) : null} />
          <InfoField label="Última análise" value={kpis.last_analysis_at ? formatRelative(kpis.last_analysis_at) : null} />
          <InfoField label="Última atividade" value={kpis.last_activity_at ? formatRelative(kpis.last_activity_at) : null} />
        </div>
      </section>
    </div>
  );
}

// CAM2IH-004+010 (Sprint H) — Aba Documentos real do imóvel
interface PropertyDocument {
  id: number;
  original_file_name: string;
  content_type: string;
  file_size_bytes: number;
  document_category: string | null;
  document_type: string | null;
  ocr_status: string | null;
  process_id: number | null;
  created_at: string;
}

function DocumentsTab({ propertyId }: { propertyId: number }) {
  const [category, setCategory] = useState<string>('all');
  const navigate = useNavigate();

  const { data: docs = [], isLoading } = useQuery({
    queryKey: ['property-hub-documents', propertyId],
    queryFn: () => api.get<PropertyDocument[]>(`/documents/?property_id=${propertyId}`).then(r => r.data),
    enabled: !!propertyId,
  });

  if (isLoading) {
    return <div className="animate-pulse space-y-2">{[1, 2, 3].map(i => <div key={i} className="h-14 rounded-xl bg-gray-100 dark:bg-white/5" />)}</div>;
  }
  if (docs.length === 0) {
    return <p className="text-sm text-gray-400 italic">Nenhum documento vinculado a este imóvel.</p>;
  }

  const filtered = category === 'all' ? docs : docs.filter(d => (d.document_category ?? 'outras') === category);
  const counts: Record<string, number> = { all: docs.length, outras: 0 };
  for (const d of docs) {
    const k = d.document_category ?? 'outras';
    counts[k] = (counts[k] ?? 0) + 1;
  }

  return (
    <div className="space-y-3">
      {/* Filtro por categoria (6 canônicas Regente + outras) */}
      <div className="flex gap-1.5 flex-wrap text-xs">
        {(['all', ...Object.keys(CATEGORY_LABELS), 'outras'] as const).map(k => {
          const active = category === k;
          const count = counts[k] ?? 0;
          if (k !== 'all' && count === 0) return null;
          const label = k === 'all' ? 'Todos' : k === 'outras' ? 'Outras' : CATEGORY_LABELS[k];
          return (
            <button
              key={k}
              onClick={() => setCategory(k)}
              className={`px-2 py-1 rounded-full font-medium border ${
                active
                  ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
                  : 'bg-white dark:bg-white/5 text-gray-500 border-gray-200 dark:border-white/10 hover:bg-gray-50'
              }`}
            >
              {label} <span className="text-gray-400">({count})</span>
            </button>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-gray-400 italic">Nenhum documento nesta categoria.</p>
      ) : (
        <div className="space-y-2">
          {filtered.map(d => (
            <div
              key={d.id}
              className="p-3 rounded-xl border border-gray-100 dark:border-white/10 hover:bg-gray-50 dark:hover:bg-white/5 flex items-start justify-between gap-3"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <FileText className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                  <span className="font-medium text-gray-900 dark:text-white text-sm truncate">{d.original_file_name}</span>
                  {d.document_category && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-700">
                      {CATEGORY_LABELS[d.document_category] ?? d.document_category}
                    </span>
                  )}
                  {d.ocr_status && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">{d.ocr_status}</span>}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">
                  {d.content_type}
                  {d.file_size_bytes > 0 && ` · ${(d.file_size_bytes / 1024).toFixed(1)} KB`}
                  {d.process_id && ` · Caso #${d.process_id}`}
                  {` · ${formatRelative(d.created_at)}`}
                </p>
              </div>
              {d.process_id && (
                <button
                  onClick={() => navigate(`/processes/${d.process_id}`)}
                  className="text-xs px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 hover:bg-slate-200 shrink-0"
                >
                  Abrir caso
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AnalysesTab({ propertyId: _propertyId, count, cases }: { propertyId: number; count: number; cases: PropertyCase[] }) {
  if (count === 0) return <p className="text-sm text-gray-400 italic">Nenhuma análise registrada ainda.</p>;
  return (
    <div className="text-sm text-gray-500">
      <p className="mb-2">{count} análise(s) registrada(s) via StageOutput nos casos do imóvel.</p>
      <p className="text-xs italic mb-3">Abra cada caso para ver os artefatos:</p>
      <ul className="space-y-1">
        {cases.slice(0, 5).map(c => (
          <li key={c.id} className="text-xs">
            <a href={`/processes/${c.id}`} className="text-emerald-600 hover:underline">Caso #{c.id}</a> — {c.title}
          </li>
        ))}
      </ul>
    </div>
  );
}

function HistoryTab({ events }: { events: PropertyEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-gray-400 italic">Nenhum evento registrado.</p>;
  return (
    <ul className="space-y-1.5">
      {events.map((ev, i) => (
        <li key={i} className="text-xs flex gap-2 items-start py-1.5 border-b border-gray-50 dark:border-white/5 last:border-0">
          <span className="text-[10px] text-gray-400 shrink-0 w-20">{formatRelative(ev.when)}</span>
          <span className="text-gray-400 shrink-0">·</span>
          <span className="text-gray-700 dark:text-slate-200 flex-1">
            <strong className="text-gray-900 dark:text-white">{ev.entity_type}</strong>{' '}
            <span className="text-gray-500">{ev.label}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

function CasesTab({ cases, navigate }: { cases: PropertyCase[]; navigate: (p: string) => void }) {
  if (cases.length === 0) return <p className="text-sm text-gray-400 italic">Nenhum caso vinculado a este imóvel.</p>;
  return (
    <div className="space-y-2">
      {cases.map(c => {
        const stateBadge = c.state ? MACROETAPA_STATE_BADGE[c.state] : null;
        return (
          <button
            key={c.id}
            onClick={() => navigate(`/processes/${c.id}`)}
            className="w-full text-left flex items-center gap-3 p-3 rounded-xl border border-gray-100 dark:border-white/10 hover:bg-gray-50 dark:hover:bg-white/5"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-gray-900 dark:text-white truncate">{c.title}</span>
                {c.urgency && ['critica', 'alta'].includes(c.urgency) && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-red-100 text-red-700">
                    {c.urgency}
                  </span>
                )}
                {stateBadge && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${stateBadge.cls}`}>
                    {stateBadge.label}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                {c.macroetapa_label ?? '—'}
                {c.responsible_user_name && ` · ${c.responsible_user_name}`}
                {c.next_step && ` · ${c.next_step}`}
              </p>
            </div>
            <ArrowLeft className="w-3 h-3 rotate-180 text-gray-400" />
          </button>
        );
      })}
    </div>
  );
}

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const days = Math.floor(diffMs / 86400000);
  if (days < 1) return 'Hoje';
  if (days < 2) return 'Ontem';
  if (days < 30) return `${days}d atrás`;
  if (days < 365) return `${Math.floor(days / 30)}m atrás`;
  return d.toLocaleDateString('pt-BR');
}

