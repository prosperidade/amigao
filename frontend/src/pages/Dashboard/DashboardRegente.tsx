/**
 * DashboardRegente — Blocos executivos do Regente Cam2 (CAM2D-001 a CAM2D-004)
 *
 * - Bloco 3 — Casos por etapa (7 estágios com totais/travados/prontos)
 * - Bloco 4 — Gargalos e alertas críticos
 * - Bloco 5 — Casos prioritários do dia
 * - Bloco 6 — Leitura executiva da IA
 */
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle, ArrowRight, CheckCircle2, ChevronRight, Filter,
  Flame, Layers, Sparkles, Zap,
} from 'lucide-react';
import { api } from '@/lib/api';
import { MACROETAPA_STATE_BADGE } from '@/pages/Processes/quadro-types';

// CAM2D-005 — Filtros executivos
interface DashboardFilters {
  urgency?: string;
  demand_type?: string;
  state_uf?: string;
  days?: number;
  view?: 'default' | 'bottlenecks' | 'priority';  // CAM2D-006
}

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface StageDistribution {
  macroetapa: string;
  label: string;
  total: number;
  blocked: number;
  ready_to_advance: number;
  avg_days_in_stage: number | null;
}

interface DashboardAlert {
  kind: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  count: number;
  label: string;
  macroetapa: string | null;
}

interface DashboardPriorityCase {
  process_id: number;
  client_name: string | null;
  property_name: string | null;
  demand_type: string | null;
  urgency: string | null;
  macroetapa: string | null;
  macroetapa_label: string | null;
  state: string | null;
  priority_reason: string;
  next_step: string | null;
  responsible_user_name: string | null;
}

interface DashboardAISummary {
  text: string;
  top_stage_bottleneck: string | null;
  top_stage_bottleneck_label: string | null;
  critical_pending_count: number;
  ready_to_advance_count: number;
  recommendation: string | null;
  source: string;
}

const SEVERITY_CLS: Record<string, string> = {
  low:      'bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-slate-300',
  medium:   'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  high:     'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
};

// ─── Componente ───────────────────────────────────────────────────────────────

export default function DashboardRegente() {
  const [filters, setFilters] = useState<DashboardFilters>({ view: 'default' });

  const qs = useMemo(() => {
    const params = new URLSearchParams();
    if (filters.urgency) params.append('urgency', filters.urgency);
    if (filters.demand_type) params.append('demand_type', filters.demand_type);
    if (filters.state_uf) params.append('state_uf', filters.state_uf);
    if (filters.days) params.append('days', String(filters.days));
    const s = params.toString();
    return s ? `?${s}` : '';
  }, [filters.urgency, filters.demand_type, filters.state_uf, filters.days]);

  const { data: stages = [] } = useQuery({
    queryKey: ['dashboard-stages', qs],
    queryFn: () => api.get<StageDistribution[]>(`/dashboard/stages${qs}`).then(r => r.data),
    staleTime: 30_000,
  });

  const { data: alerts = [] } = useQuery({
    queryKey: ['dashboard-alerts'],
    queryFn: () => api.get<DashboardAlert[]>('/dashboard/alerts').then(r => r.data),
    staleTime: 30_000,
  });

  const { data: priorityCases = [] } = useQuery({
    queryKey: ['dashboard-priority-cases', qs],
    queryFn: () => {
      const extra = qs ? `&${qs.slice(1)}` : '';
      return api.get<DashboardPriorityCase[]>(`/dashboard/priority-cases?limit=8${extra}`).then(r => r.data);
    },
    staleTime: 30_000,
  });

  const { data: aiSummary } = useQuery({
    queryKey: ['dashboard-ai-summary'],
    queryFn: () => api.get<DashboardAISummary>('/dashboard/ai-summary').then(r => r.data),
    staleTime: 60_000,
  });

  // CAM2D-006 — Aplica view:
  // default: stages + priority cases + alerts
  // bottlenecks: prioriza coluna de alertas e só mostra etapas com travas
  // priority: só casos prioritários
  const filteredStages = filters.view === 'bottlenecks'
    ? stages.filter(s => s.blocked > 0 || s.ready_to_advance > 0)
    : stages;

  return (
    <div className="space-y-5">
      {/* Barra de filtros + view selector */}
      <FilterBar filters={filters} setFilters={setFilters} />

      {/* Bloco 6 — Leitura executiva da IA */}
      <AIBlock summary={aiSummary} />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-5">
        <div className="space-y-5">
          {filters.view !== 'priority' && <StagesBlock stages={filteredStages} />}
          <PriorityCasesBlock cases={priorityCases} />
        </div>

        {filters.view !== 'priority' && <AlertsBlock alerts={alerts} />}
      </div>
    </div>
  );
}

// CAM2D-005 + CAM2D-006
function FilterBar({ filters, setFilters }: { filters: DashboardFilters; setFilters: (f: DashboardFilters) => void }) {
  const hasActiveFilters = !!(filters.urgency || filters.demand_type || filters.state_uf || filters.days);
  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-3 flex flex-wrap items-center gap-2">
      <Filter className="w-4 h-4 text-gray-400 shrink-0" />
      <span className="text-xs font-medium text-gray-500 dark:text-slate-400 shrink-0">Visão:</span>
      <div className="flex gap-1">
        {([
          { k: 'default', l: 'Geral' },
          { k: 'bottlenecks', l: 'Gargalos' },
          { k: 'priority', l: 'Prioridade do dia' },
        ] as { k: DashboardFilters['view']; l: string }[]).map(({ k, l }) => {
          const active = filters.view === k;
          return (
            <button
              key={k}
              onClick={() => setFilters({ ...filters, view: k })}
              className={`text-xs px-2.5 py-1 rounded-lg font-medium ${
                active
                  ? 'bg-emerald-500 text-white'
                  : 'bg-gray-100 dark:bg-white/5 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-white/10'
              }`}
            >
              {l}
            </button>
          );
        })}
      </div>

      <div className="h-5 w-px bg-gray-200 dark:bg-white/10 mx-1" />

      <select
        value={filters.urgency ?? ''}
        onChange={e => setFilters({ ...filters, urgency: e.target.value || undefined })}
        className="text-xs px-2 py-1 rounded-lg bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200"
      >
        <option value="">Urgência: todas</option>
        <option value="critica">🔴 Crítica</option>
        <option value="alta">🟠 Alta</option>
        <option value="media">🟡 Média</option>
        <option value="baixa">🟢 Baixa</option>
      </select>

      <select
        value={filters.demand_type ?? ''}
        onChange={e => setFilters({ ...filters, demand_type: e.target.value || undefined })}
        className="text-xs px-2 py-1 rounded-lg bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200"
      >
        <option value="">Demanda: todas</option>
        <option value="car">CAR</option>
        <option value="retificacao_car">Retificação CAR</option>
        <option value="licenciamento">Licenciamento</option>
        <option value="regularizacao_fundiaria">Regularização</option>
        <option value="outorga">Outorga</option>
        <option value="defesa">Defesa</option>
        <option value="compensacao">Compensação</option>
        <option value="prad">PRAD</option>
      </select>

      <input
        type="text"
        value={filters.state_uf ?? ''}
        onChange={e => setFilters({ ...filters, state_uf: e.target.value.toUpperCase().slice(0, 2) || undefined })}
        placeholder="UF"
        maxLength={2}
        className="text-xs px-2 py-1 rounded-lg bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200 w-14"
      />

      <select
        value={filters.days ?? ''}
        onChange={e => setFilters({ ...filters, days: e.target.value ? parseInt(e.target.value) : undefined })}
        className="text-xs px-2 py-1 rounded-lg bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200"
      >
        <option value="">Período: sempre</option>
        <option value="7">Últimos 7 dias</option>
        <option value="30">Últimos 30 dias</option>
        <option value="90">Últimos 90 dias</option>
      </select>

      {hasActiveFilters && (
        <button
          onClick={() => setFilters({ view: filters.view })}
          className="text-xs px-2 py-1 rounded-lg text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10"
        >
          Limpar
        </button>
      )}
    </div>
  );
}

// ─── Blocos ───────────────────────────────────────────────────────────────────

function AIBlock({ summary }: { summary: DashboardAISummary | undefined }) {
  if (!summary) return <div className="h-24 rounded-2xl bg-gray-100 dark:bg-white/5 animate-pulse" />;
  return (
    <div className="rounded-2xl bg-gradient-to-r from-violet-50 via-sky-50 to-emerald-50 dark:from-violet-500/10 dark:via-sky-500/10 dark:to-emerald-500/10 border border-violet-200 dark:border-violet-500/30 p-5">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-2xl bg-white dark:bg-violet-500/20 flex items-center justify-center shrink-0">
          <Sparkles className="w-5 h-5 text-violet-600 dark:text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs uppercase tracking-wide text-violet-700 dark:text-violet-300 font-semibold">
              Leitura executiva da IA
            </span>
            <span className="text-[10px] text-gray-400">· análise automática</span>
          </div>
          <p className="text-sm text-gray-800 dark:text-slate-100 leading-relaxed">{summary.text}</p>
          {summary.recommendation && (
            <div className="mt-2 text-xs text-emerald-800 dark:text-emerald-200 bg-emerald-50/60 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 rounded-lg p-2">
              💡 {summary.recommendation}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StagesBlock({ stages }: { stages: StageDistribution[] }) {
  const navigate = useNavigate();
  const totalCases = stages.reduce((sum, s) => sum + s.total, 0);

  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-slate-100">Casos por etapa</h2>
          <span className="text-xs text-gray-500">· {totalCases} ativos</span>
        </div>
        <button
          onClick={() => navigate('/processes')}
          className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1"
        >
          Ver fluxo <ChevronRight className="w-3 h-3" />
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        {stages.map((s) => (
          <div
            key={s.macroetapa}
            className={`p-3 rounded-xl border text-left ${
              s.total === 0
                ? 'bg-gray-50 dark:bg-white/5 border-gray-100 dark:border-white/10 opacity-60'
                : 'bg-white dark:bg-white/5 border-gray-200 dark:border-white/10'
            }`}
          >
            <div className="text-[11px] font-medium text-gray-500 dark:text-slate-400 truncate">
              {s.label}
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-gray-900 dark:text-white">{s.total}</span>
              {s.avg_days_in_stage !== null && (
                <span className="text-[10px] text-gray-400">~{s.avg_days_in_stage}d</span>
              )}
            </div>
            <div className="flex gap-1.5 mt-2 text-[10px]">
              {s.blocked > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300">
                  🚫 {s.blocked}
                </span>
              )}
              {s.ready_to_advance > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                  ✓ {s.ready_to_advance}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AlertsBlock({ alerts }: { alerts: DashboardAlert[] }) {
  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5 h-fit">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle className="w-4 h-4 text-red-500" />
        <h2 className="text-sm font-semibold text-gray-800 dark:text-slate-100">Gargalos e alertas</h2>
        <span className="text-xs text-gray-500">· {alerts.length}</span>
      </div>
      {alerts.length === 0 ? (
        <div className="text-center py-6 text-xs text-gray-400 italic">
          <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-400" />
          Nenhum alerta crítico no momento.
        </div>
      ) : (
        <ul className="space-y-2">
          {alerts.map((a, i) => (
            <li
              key={i}
              className={`flex items-start gap-2 p-2.5 rounded-xl border ${
                a.severity === 'critical'
                  ? 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30'
                  : a.severity === 'high'
                  ? 'bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/30'
                  : 'bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/30'
              }`}
            >
              <Flame className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${
                a.severity === 'critical' ? 'text-red-500' :
                a.severity === 'high' ? 'text-orange-500' : 'text-amber-500'
              }`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-gray-900 dark:text-slate-100">{a.label}</div>
                <span className={`inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded ${SEVERITY_CLS[a.severity]}`}>
                  {a.severity}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PriorityCasesBlock({ cases }: { cases: DashboardPriorityCase[] }) {
  const navigate = useNavigate();
  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-slate-100">Casos prioritários do dia</h2>
          <span className="text-xs text-gray-500">· top {cases.length}</span>
        </div>
      </div>
      {cases.length === 0 ? (
        <div className="text-center py-6 text-xs text-gray-400 italic">Nenhum caso com prioridade no momento.</div>
      ) : (
        <div className="space-y-2">
          {cases.map(c => {
            const stateBadge = c.state ? MACROETAPA_STATE_BADGE[c.state] : null;
            return (
              <button
                key={c.process_id}
                onClick={() => navigate(`/processes/${c.process_id}`)}
                className="w-full text-left p-3 rounded-xl border border-gray-100 dark:border-white/10 hover:bg-gray-50 dark:hover:bg-white/5 flex items-center gap-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {c.client_name ?? '—'}
                      {c.property_name && <span className="text-gray-400"> · {c.property_name}</span>}
                    </span>
                    {stateBadge && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${stateBadge.cls}`}>
                        {stateBadge.label}
                      </span>
                    )}
                    {c.urgency && ['critica', 'alta'].includes(c.urgency) && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-red-100 text-red-700">
                        {c.urgency}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5 truncate">
                    {c.macroetapa_label && <span>{c.macroetapa_label} · </span>}
                    <span className="italic">{c.priority_reason}</span>
                  </div>
                  {c.next_step && (
                    <div className="text-xs text-emerald-700 dark:text-emerald-400 mt-0.5 flex items-center gap-1">
                      <ArrowRight className="w-3 h-3" /> {c.next_step}
                    </div>
                  )}
                </div>
                {c.responsible_user_name && (
                  <div className="text-[10px] text-gray-500 shrink-0 hidden sm:block">
                    {c.responsible_user_name}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

