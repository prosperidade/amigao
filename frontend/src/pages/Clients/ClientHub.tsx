/**
 * ClientHub — Hub 360° do cliente (Regente Cam2 — CAM2CH-001 a CAM2CH-009)
 *
 * Layout:
 *  Bloco 1 — Cabeçalho (identificação + status + chips + ações rápidas)
 *  Bloco 2 — Dashboard resumido (cards KPI)
 *  Bloco 3 — Lista de imóveis vinculados com status do caso primário
 *  Bloco 5 — Timeline de eventos
 *  Abas internas: Visão geral / Imóveis / Casos / Contratos / Histórico
 */
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft, Mail, Phone, Building2, MapPin, Briefcase, FileText,
  AlertTriangle, Clock, Plus, Sparkles,
} from 'lucide-react';
import { api } from '@/lib/api';
import { MACROETAPA_LABELS, MACROETAPA_STATE_BADGE } from '@/pages/Processes/quadro-types';

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface ClientHubHeader {
  id: number;
  full_name: string;
  legal_name: string | null;
  client_type: string;
  cpf_cnpj: string | null;
  email: string | null;
  phone: string | null;
  status: string;
  source_channel: string | null;
  created_at: string | null;
}

interface ClientHubChips {
  is_active: boolean;
  has_active_cases: boolean;
  has_doc_pending: boolean;
  has_contract_pending: boolean;
  is_pj: boolean;
}

interface ClientHubKpis {
  properties_count: number;
  cases_active: number;
  cases_completed: number;
  contracts_emitted: number;
  diagnoses_done: number;
  pending_critical: number;
  last_activity_at: string | null;
}

interface ClientHubSummary {
  header: ClientHubHeader;
  chips: ClientHubChips;
  kpis: ClientHubKpis;
  state: string;
}

interface PropertyEvent {
  when: string;
  kind: string;
  label: string;
  macroetapa: string | null;
}

interface ClientHubProperty {
  id: number;
  name: string;
  matricula: string | null;
  car_code: string | null;
  municipality: string | null;
  state: string | null;
  total_area_ha: number | null;
  cases_count: number;
  primary_case_id: number | null;
  primary_case_macroetapa: string | null;
  primary_case_state: string | null;
  last_activity_at: string | null;
  events: PropertyEvent[];
}

interface ClientHubAISummary {
  text: string;
  focus_property_id: number | null;
  focus_property_name: string | null;
  top_pending: string | null;
  recommendation: string | null;
  source: string;
}

interface TimelineItem {
  when: string;
  entity_type: string;
  entity_id: number | null;
  action: string;
  description: string | null;
  user_id: number | null;
}

const HUB_STATE_LABEL: Record<string, { label: string; cls: string }> = {
  recem_criado:   { label: 'Recém-criado', cls: 'bg-gray-100 text-gray-700' },
  em_construcao:  { label: 'Em construção', cls: 'bg-blue-100 text-blue-700' },
  ativo:          { label: 'Ativo', cls: 'bg-emerald-100 text-emerald-700' },
  com_alertas:    { label: 'Com alertas', cls: 'bg-red-100 text-red-700' },
  consolidado:    { label: 'Consolidado', cls: 'bg-violet-100 text-violet-700' },
};

type TabKey = 'overview' | 'properties' | 'cases' | 'contracts' | 'history';

// ─── Componente ───────────────────────────────────────────────────────────────

export default function ClientHub() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const clientId = parseInt(id ?? '0', 10);
  const [tab, setTab] = useState<TabKey>('overview');

  const { data: summary, isLoading } = useQuery({
    queryKey: ['client-hub-summary', clientId],
    queryFn: () => api.get<ClientHubSummary>(`/clients/${clientId}/summary`).then(r => r.data),
    enabled: !!clientId,
  });

  const { data: properties = [] } = useQuery({
    queryKey: ['client-hub-properties', clientId],
    queryFn: () => api.get<ClientHubProperty[]>(`/clients/${clientId}/properties-with-status`).then(r => r.data),
    enabled: !!clientId,
  });

  const { data: timeline = [] } = useQuery({
    queryKey: ['client-hub-timeline', clientId],
    queryFn: () => api.get<TimelineItem[]>(`/clients/${clientId}/timeline?limit=30`).then(r => r.data),
    enabled: !!clientId,
  });

  const { data: aiSummary } = useQuery({
    queryKey: ['client-hub-ai-summary', clientId],
    queryFn: () => api.get<ClientHubAISummary>(`/clients/${clientId}/ai-summary`).then(r => r.data),
    enabled: !!clientId,
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

  const { header, chips, kpis, state } = summary;
  const hubState = HUB_STATE_LABEL[state] ?? { label: state, cls: 'bg-gray-100 text-gray-700' };

  return (
    <div className="max-w-7xl mx-auto space-y-4">

      {/* Voltar */}
      <button
        onClick={() => navigate('/clients')}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-slate-400 hover:text-gray-800 dark:hover:text-white"
      >
        <ArrowLeft className="w-4 h-4" /> Voltar para clientes
      </button>

      {/* Bloco 1 — Cabeçalho */}
      <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5 space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-12 h-12 rounded-2xl bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center text-emerald-700 dark:text-emerald-300 font-bold text-lg shrink-0">
              {chips.is_pj ? '🏢' : '👤'}
            </div>
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-gray-900 dark:text-white truncate">{header.full_name}</h1>
              <p className="text-xs text-gray-500 dark:text-slate-400">
                ID #{header.id} · {header.client_type === 'pj' ? 'Pessoa Jurídica' : 'Pessoa Física'}
                {header.cpf_cnpj && ` · ${header.cpf_cnpj}`}
              </p>
            </div>
          </div>
          <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${hubState.cls}`}>
            {hubState.label}
          </span>
        </div>

        {/* Identificação */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          {header.email && (
            <div className="flex items-center gap-2 text-gray-700 dark:text-slate-200 min-w-0">
              <Mail className="w-3.5 h-3.5 text-gray-400 shrink-0" />
              <span className="truncate">{header.email}</span>
            </div>
          )}
          {header.phone && (
            <div className="flex items-center gap-2 text-gray-700 dark:text-slate-200">
              <Phone className="w-3.5 h-3.5 text-gray-400 shrink-0" />
              <span>{header.phone}</span>
            </div>
          )}
          {header.source_channel && (
            <div className="flex items-center gap-2 text-gray-700 dark:text-slate-200">
              <span className="text-gray-400">📥</span>
              <span className="capitalize">{header.source_channel}</span>
            </div>
          )}
        </div>

        {/* Chips */}
        <div className="flex flex-wrap gap-1.5">
          {chips.is_active && <Chip cls="bg-emerald-100 text-emerald-700">Ativo</Chip>}
          {chips.has_active_cases && <Chip cls="bg-blue-100 text-blue-700">Casos em andamento</Chip>}
          {chips.has_doc_pending && <Chip cls="bg-amber-100 text-amber-700">⚠ Pendência documental</Chip>}
          {!chips.has_contract_pending && chips.is_active && <Chip cls="bg-emerald-50 text-emerald-700">Sem pendência contratual</Chip>}
          <Chip cls="bg-slate-100 text-slate-700">{chips.is_pj ? 'PJ' : 'PF'}</Chip>
        </div>

        {/* Ações rápidas */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100 dark:border-white/10">
          <ActionBtn icon={<Plus className="w-3.5 h-3.5" />} onClick={() => navigate('/intake')}>Novo caso</ActionBtn>
          <ActionBtn icon={<Briefcase className="w-3.5 h-3.5" />} onClick={() => setTab('contracts')}>Ver contratos</ActionBtn>
          <ActionBtn icon={<FileText className="w-3.5 h-3.5" />} onClick={() => setTab('cases')}>Ver diagnósticos</ActionBtn>
          <ActionBtn icon={<Building2 className="w-3.5 h-3.5" />} onClick={() => navigate('/properties')}>Adicionar imóvel</ActionBtn>
        </div>
      </div>

      {/* Bloco 2 — Dashboard resumido */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <KpiCard label="Imóveis" value={kpis.properties_count} icon={<MapPin className="w-4 h-4" />} />
        <KpiCard label="Casos ativos" value={kpis.cases_active} icon={<Briefcase className="w-4 h-4" />} highlight={kpis.cases_active > 0} />
        <KpiCard label="Concluídos" value={kpis.cases_completed} icon={<FileText className="w-4 h-4" />} />
        <KpiCard label="Contratos" value={kpis.contracts_emitted} icon={<FileText className="w-4 h-4" />} />
        <KpiCard label="Diagnósticos" value={kpis.diagnoses_done} icon={<Sparkles className="w-4 h-4" />} />
        <KpiCard label="Pendências" value={kpis.pending_critical} icon={<AlertTriangle className="w-4 h-4" />} alarm={kpis.pending_critical > 0} />
        <KpiCard
          label="Última atividade"
          value={kpis.last_activity_at ? formatRelative(kpis.last_activity_at) : '—'}
          icon={<Clock className="w-4 h-4" />}
        />
      </div>

      {/* Grid principal: abas/conteúdo + painel lateral IA */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        {/* Abas + conteúdo central */}
        <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 overflow-hidden min-w-0">
          <div className="border-b border-gray-100 dark:border-white/10 flex gap-0 overflow-x-auto">
            {(['overview', 'properties', 'cases', 'contracts', 'history'] as TabKey[]).map(k => {
              const labels: Record<TabKey, string> = {
                overview: 'Visão geral',
                properties: `Imóveis (${kpis.properties_count})`,
                cases: `Casos (${kpis.cases_active + kpis.cases_completed})`,
                contracts: `Contratos (${kpis.contracts_emitted})`,
                history: 'Histórico',
              };
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
                  {labels[k]}
                </button>
              );
            })}
          </div>

          <div className="p-5">
            {tab === 'overview' && (
              <OverviewTab properties={properties} timeline={timeline.slice(0, 5)} />
            )}
            {tab === 'properties' && <PropertiesTab properties={properties} navigate={navigate} />}
            {tab === 'cases' && <CasesTab properties={properties} navigate={navigate} />}
            {tab === 'contracts' && <PlaceholderTab title="Contratos" message="Em construção — Camada 4 trará a listagem completa." />}
            {tab === 'history' && <HistoryTab timeline={timeline} />}
          </div>
        </div>

        {/* CAM2CH-007 — Painel lateral de IA */}
        <aside className="lg:sticky lg:top-4 h-fit">
          <AIPanel summary={aiSummary} onFocusProperty={(pid) => {
            setTab('properties');
            setTimeout(() => document.getElementById(`prop-${pid}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
          }} />
        </aside>
      </div>
    </div>
  );
}

function AIPanel({ summary, onFocusProperty }: { summary: ClientHubAISummary | undefined; onFocusProperty: (id: number) => void }) {
  if (!summary) {
    return <div className="rounded-2xl bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-4 h-48 animate-pulse" />;
  }
  return (
    <div className="space-y-3">
      <div className="rounded-2xl bg-gradient-to-br from-violet-50 to-sky-50 dark:from-violet-500/10 dark:to-sky-500/10 border border-violet-200 dark:border-violet-500/30 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-violet-600 dark:text-violet-400" />
          <span className="text-xs uppercase tracking-wide text-violet-700 dark:text-violet-300 font-semibold">
            Leitura da IA
          </span>
        </div>
        <p className="text-sm text-gray-800 dark:text-slate-100 leading-relaxed">{summary.text}</p>

        {summary.focus_property_name && summary.focus_property_id && (
          <button
            onClick={() => onFocusProperty(summary.focus_property_id!)}
            className="w-full text-left text-xs px-3 py-2 rounded-lg bg-white dark:bg-white/5 border border-violet-200 dark:border-violet-500/30 hover:bg-violet-50 dark:hover:bg-violet-500/10"
          >
            <span className="text-violet-700 dark:text-violet-300 font-semibold">🎯 Foco:</span>{' '}
            <span className="text-gray-800 dark:text-slate-100">{summary.focus_property_name}</span>
          </button>
        )}

        {summary.top_pending && (
          <div className="text-xs text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-lg p-2">
            <strong>⚠ Pendência crítica:</strong> {summary.top_pending}
          </div>
        )}

        {summary.recommendation && (
          <div className="text-xs text-emerald-800 dark:text-emerald-200 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 rounded-lg p-2">
            <strong>💡 Recomendação:</strong> {summary.recommendation}
          </div>
        )}

        <div className="text-[10px] text-gray-400 pt-1 border-t border-violet-200 dark:border-violet-500/30">
          Fonte: {summary.source === 'deterministic' ? 'análise automática' : summary.source}
        </div>
      </div>
    </div>
  );
}

// ─── Sub-componentes ──────────────────────────────────────────────────────────

function Chip({ cls, children }: { cls: string; children: React.ReactNode }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{children}</span>;
}

function ActionBtn({ icon, onClick, children }: { icon: React.ReactNode; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-sm text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-white/10"
    >
      {icon}{children}
    </button>
  );
}

function KpiCard({
  label, value, icon, highlight, alarm,
}: { label: string; value: number | string; icon: React.ReactNode; highlight?: boolean; alarm?: boolean }) {
  return (
    <div className={`rounded-2xl border p-3 ${
      alarm
        ? 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30'
        : highlight
        ? 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/30'
        : 'bg-white dark:bg-white/5 border-gray-100 dark:border-white/10'
    }`}>
      <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-slate-400 font-medium">
        {icon}
        <span className="truncate">{label}</span>
      </div>
      <div className={`mt-1 text-2xl font-bold ${alarm ? 'text-red-700 dark:text-red-300' : 'text-gray-900 dark:text-white'}`}>
        {value}
      </div>
    </div>
  );
}

function OverviewTab({ properties, timeline }: { properties: ClientHubProperty[]; timeline: TimelineItem[] }) {
  return (
    <div className="grid md:grid-cols-2 gap-5">
      <section>
        <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-2">Imóveis em destaque</h3>
        {properties.length === 0 ? (
          <p className="text-xs text-gray-400 italic">Nenhum imóvel vinculado.</p>
        ) : (
          <div className="space-y-2">
            {properties.slice(0, 3).map(p => <PropertyRow key={p.id} p={p} />)}
          </div>
        )}
      </section>
      <section>
        <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-2">Atividade recente</h3>
        {timeline.length === 0 ? (
          <p className="text-xs text-gray-400 italic">Nenhuma atividade registrada.</p>
        ) : (
          <ul className="space-y-1.5">
            {timeline.map((t, i) => <TimelineRow key={i} t={t} />)}
          </ul>
        )}
      </section>
    </div>
  );
}

function PropertiesTab({ properties, navigate }: { properties: ClientHubProperty[]; navigate: (p: string) => void }) {
  if (properties.length === 0) return <p className="text-sm text-gray-400 italic">Nenhum imóvel vinculado.</p>;
  return (
    <div className="space-y-3">
      {properties.map(p => (
        <div
          id={`prop-${p.id}`}
          key={p.id}
          className="p-3 rounded-xl border border-gray-100 dark:border-white/10 hover:bg-gray-50 dark:hover:bg-white/5 space-y-2"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-gray-900 dark:text-white truncate">{p.name}</span>
                {p.car_code && <span className="text-xs text-gray-500">CAR {p.car_code.slice(-8)}</span>}
                {p.total_area_ha && <span className="text-xs text-gray-500">{p.total_area_ha} ha</span>}
                {p.primary_case_state && MACROETAPA_STATE_BADGE[p.primary_case_state] && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${MACROETAPA_STATE_BADGE[p.primary_case_state].cls}`}>
                    {MACROETAPA_STATE_BADGE[p.primary_case_state].label}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                {p.municipality && p.state ? `${p.municipality}/${p.state}` : 'Localização não informada'}
                {' · '}
                {p.cases_count} caso{p.cases_count !== 1 ? 's' : ''}
                {p.primary_case_macroetapa && ` · etapa: ${MACROETAPA_LABELS[p.primary_case_macroetapa] ?? p.primary_case_macroetapa}`}
              </p>
            </div>
            <div className="flex gap-1.5 shrink-0">
              {p.primary_case_id && (
                <button
                  onClick={() => navigate(`/processes/${p.primary_case_id}`)}
                  className="text-xs px-2.5 py-1 rounded-md bg-emerald-100 text-emerald-700 hover:bg-emerald-200"
                >
                  Abrir caso
                </button>
              )}
            </div>
          </div>
          {/* CAM2CH-005 — mini-timeline por imóvel */}
          {p.events.length > 0 && (
            <div className="pt-2 border-t border-gray-100 dark:border-white/10">
              <div className="flex flex-wrap gap-1.5 text-[10px]">
                {p.events.slice(0, 6).map((ev, i) => (
                  <span
                    key={i}
                    title={`${formatRelative(ev.when)} — ${ev.label}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 dark:bg-white/5 text-gray-600 dark:text-slate-300"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    {ev.label}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function CasesTab({ properties, navigate }: { properties: ClientHubProperty[]; navigate: (p: string) => void }) {
  const cases = properties.filter(p => p.primary_case_id);
  if (cases.length === 0) return <p className="text-sm text-gray-400 italic">Nenhum caso ativo no momento.</p>;
  return (
    <div className="space-y-2">
      {cases.map(p => (
        <button
          key={p.primary_case_id}
          onClick={() => navigate(`/processes/${p.primary_case_id}`)}
          className="w-full text-left flex items-center justify-between gap-3 p-3 rounded-xl border border-gray-100 dark:border-white/10 hover:bg-gray-50 dark:hover:bg-white/5"
        >
          <div className="min-w-0">
            <div className="font-medium text-gray-900 dark:text-white truncate">{p.name}</div>
            <p className="text-xs text-gray-500">
              Caso #{p.primary_case_id} · {p.primary_case_macroetapa && MACROETAPA_LABELS[p.primary_case_macroetapa]}
            </p>
          </div>
          {p.primary_case_state && MACROETAPA_STATE_BADGE[p.primary_case_state] && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${MACROETAPA_STATE_BADGE[p.primary_case_state].cls}`}>
              {MACROETAPA_STATE_BADGE[p.primary_case_state].label}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function HistoryTab({ timeline }: { timeline: TimelineItem[] }) {
  if (timeline.length === 0) return <p className="text-sm text-gray-400 italic">Nenhum evento registrado ainda.</p>;
  return (
    <ul className="space-y-1.5">
      {timeline.map((t, i) => <TimelineRow key={i} t={t} />)}
    </ul>
  );
}

function PlaceholderTab({ title, message }: { title: string; message: string }) {
  return (
    <div className="text-center py-12 text-gray-500">
      <h3 className="font-semibold mb-1">{title}</h3>
      <p className="text-sm">{message}</p>
    </div>
  );
}

function TimelineRow({ t }: { t: TimelineItem }) {
  return (
    <li className="text-xs flex gap-2 items-start py-1.5 border-b border-gray-50 dark:border-white/5 last:border-0">
      <span className="text-[10px] text-gray-400 shrink-0 w-20">{formatRelative(t.when)}</span>
      <span className="text-gray-400 shrink-0">·</span>
      <span className="text-gray-700 dark:text-slate-200 flex-1">
        <strong className="text-gray-900 dark:text-white">{t.entity_type}</strong>
        {' '}
        <span className="text-gray-500">{t.action}</span>
        {t.description && <> — {t.description}</>}
      </span>
    </li>
  );
}

function PropertyRow({ p }: { p: ClientHubProperty }) {
  return (
    <div className="flex items-start gap-2 p-2 rounded-lg border border-gray-100 dark:border-white/10">
      <MapPin className="w-3.5 h-3.5 mt-0.5 text-gray-400 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-gray-900 dark:text-white truncate">{p.name}</div>
        <div className="text-[11px] text-gray-500">
          {p.cases_count} caso{p.cases_count !== 1 ? 's' : ''}
          {p.primary_case_state && MACROETAPA_STATE_BADGE[p.primary_case_state] && (
            <> · <span className={`px-1 py-0.5 rounded text-[9px] ${MACROETAPA_STATE_BADGE[p.primary_case_state].cls}`}>
              {MACROETAPA_STATE_BADGE[p.primary_case_state].label}
            </span></>
          )}
        </div>
      </div>
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
