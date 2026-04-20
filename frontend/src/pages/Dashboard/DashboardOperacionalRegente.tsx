/**
 * DashboardOperacionalRegente — Painel operacional conforme Lovable da sócia.
 *
 * Bloco 1 do Sprint F:
 *  - 8 cards KPI (Clientes Ativos, Casos Ativos, Em Diagnóstico, Em Coleta,
 *    Em Caminho Regulatório, Propostas Enviadas, Contratos Enviados, Formalizados)
 *  - Gráfico "Casos por Etapa" (barras horizontais)
 *  - "Funil Operacional" (7 degraus decrescentes)
 *  - Filtros: Período, Responsável, Tipo de demanda
 *
 * Sem dependência de lib de gráficos — CSS puro + divs proporcionais.
 */
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Users, Briefcase, Stethoscope, FileStack, Scale, Send,
  FileSignature, CheckCircle2, TrendingUp, TrendingDown, Minus,
} from 'lucide-react';
import { api } from '@/lib/api';
import { DEMAND_TYPE_LABELS } from '@/pages/Processes/quadro-types';

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface Kpi {
  key: string;
  label: string;
  value: number;
  delta_pct: number | null;
  hint: string | null;
}

interface StageDistribution {
  macroetapa: string;
  label: string;
  total: number;
  blocked?: number;
  ready_to_advance?: number;
}

interface KpisResponse {
  days: number;
  responsible_user_id: number | null;
  demand_type: string | null;
  kpis: Kpi[];
  funnel: StageDistribution[];
}

// ─── Config visual dos cards ─────────────────────────────────────────────────

const KPI_ICON: Record<string, typeof Users> = {
  clientes_ativos: Users,
  casos_ativos: Briefcase,
  em_diagnostico: Stethoscope,
  em_coleta: FileStack,
  em_caminho_regulatorio: Scale,
  propostas_enviadas: Send,
  contratos_enviados: FileSignature,
  casos_formalizados: CheckCircle2,
};

const KPI_ACCENT: Record<string, { bg: string; fg: string }> = {
  clientes_ativos:      { bg: 'bg-emerald-50 dark:bg-emerald-500/10', fg: 'text-emerald-600 dark:text-emerald-400' },
  casos_ativos:         { bg: 'bg-blue-50 dark:bg-blue-500/10',       fg: 'text-blue-600 dark:text-blue-400' },
  em_diagnostico:       { bg: 'bg-indigo-50 dark:bg-indigo-500/10',   fg: 'text-indigo-600 dark:text-indigo-400' },
  em_coleta:            { bg: 'bg-amber-50 dark:bg-amber-500/10',     fg: 'text-amber-600 dark:text-amber-400' },
  em_caminho_regulatorio:{ bg: 'bg-purple-50 dark:bg-purple-500/10',  fg: 'text-purple-600 dark:text-purple-400' },
  propostas_enviadas:   { bg: 'bg-teal-50 dark:bg-teal-500/10',       fg: 'text-teal-600 dark:text-teal-400' },
  contratos_enviados:   { bg: 'bg-sky-50 dark:bg-sky-500/10',         fg: 'text-sky-600 dark:text-sky-400' },
  casos_formalizados:   { bg: 'bg-emerald-50 dark:bg-emerald-500/10', fg: 'text-emerald-600 dark:text-emerald-400' },
};

const PERIOD_OPTIONS: { value: number; label: string }[] = [
  { value: 7,   label: '\u00daltimos 7 dias' },
  { value: 30,  label: '\u00daltimos 30 dias' },
  { value: 90,  label: '\u00daltimos 90 dias' },
  { value: 180, label: '\u00daltimos 180 dias' },
];

// ─── Componente principal ────────────────────────────────────────────────────

export default function DashboardOperacionalRegente() {
  const [days, setDays] = useState(30);
  const [demandType, setDemandType] = useState<string>('');

  const { data: kpisData, isLoading } = useQuery({
    queryKey: ['dashboard-kpis', days, demandType],
    queryFn: () => {
      const params = new URLSearchParams({ days: String(days) });
      if (demandType) params.set('demand_type', demandType);
      return api.get<KpisResponse>(`/dashboard/kpis?${params}`).then(r => r.data);
    },
    staleTime: 60_000,
  });

  const demandTypeOptions = useMemo(() => Object.keys(DEMAND_TYPE_LABELS), []);

  const kpis = kpisData?.kpis ?? [];
  const funnel = kpisData?.funnel ?? [];

  return (
    <section className="space-y-6">
      {/* Filtros operacionais */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={days}
          onChange={e => setDays(Number(e.target.value))}
          className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 dark:text-zinc-200"
        >
          {PERIOD_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <select
          value={demandType}
          onChange={e => setDemandType(e.target.value)}
          className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 dark:text-zinc-200"
        >
          <option value="">Tipo de demanda (todos)</option>
          {demandTypeOptions.map(d => (
            <option key={d} value={d}>{DEMAND_TYPE_LABELS[d]}</option>
          ))}
        </select>
      </div>

      {/* 8 KPI cards (2 linhas de 4) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {isLoading
          ? Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-28 bg-gray-100 dark:bg-zinc-800/50 rounded-2xl animate-pulse" />
            ))
          : kpis.map(k => <KpiCard key={k.key} kpi={k} />)}
      </div>

      {/* Gráficos lado a lado */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CasosPorEtapa data={funnel} loading={isLoading} />
        <FunilOperacional data={funnel} loading={isLoading} />
      </div>
    </section>
  );
}

// ─── Subcomponentes ───────────────────────────────────────────────────────────

function KpiCard({ kpi }: { kpi: Kpi }) {
  const Icon = KPI_ICON[kpi.key] ?? Briefcase;
  const accent = KPI_ACCENT[kpi.key] ?? { bg: 'bg-gray-100', fg: 'text-gray-600' };

  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-4 hover:border-gray-200 dark:hover:border-white/20 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 truncate">
            {kpi.label}
          </p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-gray-900 dark:text-white">
              {kpi.value.toLocaleString('pt-BR')}
            </span>
            <DeltaBadge value={kpi.delta_pct} />
          </div>
          {kpi.hint && (
            <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-1 truncate">
              {kpi.hint}
            </p>
          )}
        </div>
        <div className={`p-2 rounded-lg ${accent.bg} shrink-0`}>
          <Icon className={`w-4 h-4 ${accent.fg}`} />
        </div>
      </div>
    </div>
  );
}

function DeltaBadge({ value }: { value: number | null }) {
  if (value === null || value === undefined) return null;

  const isUp = value > 0;
  const isDown = value < 0;
  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;
  const cls = isUp
    ? 'text-emerald-600 dark:text-emerald-400'
    : isDown
    ? 'text-red-600 dark:text-red-400'
    : 'text-gray-500';

  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${cls}`}>
      <Icon className="w-3 h-3" />
      {value > 0 ? '+' : ''}{value.toFixed(1)}%
    </span>
  );
}

function CasosPorEtapa({ data, loading }: { data: StageDistribution[]; loading: boolean }) {
  const maxTotal = Math.max(...data.map(d => d.total), 1);

  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
        Casos por Etapa
      </h3>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-5 bg-gray-100 dark:bg-zinc-800/50 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-2.5">
          {data.map(d => {
            const pct = (d.total / maxTotal) * 100;
            return (
              <div key={d.macroetapa}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-gray-600 dark:text-gray-400 truncate max-w-[70%]">
                    {d.label}
                  </span>
                  <span className="font-semibold text-gray-900 dark:text-white">{d.total}</span>
                </div>
                <div className="h-2 bg-gray-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 rounded-full transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function FunilOperacional({ data, loading }: { data: StageDistribution[]; loading: boolean }) {
  // No funil, cada degrau tem largura decrescente proporcional ao total.
  const maxTotal = Math.max(...data.map(d => d.total), 1);

  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
        Funil Operacional
      </h3>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-7 bg-gray-100 dark:bg-zinc-800/50 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-1.5">
          {data.map((d, i) => {
            const pct = Math.max((d.total / maxTotal) * 100, 8); // mínimo 8% pra visibilidade
            // Gradiente: verde saturado → claro
            const intensity = Math.max(100 - i * 10, 30); // 100 → 30
            return (
              <div key={d.macroetapa} className="flex items-center gap-3">
                <div
                  className="text-white text-xs font-semibold flex items-center justify-center rounded-lg py-2 transition-all"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: `rgb(16, 185, ${Math.min(129 + (100 - intensity), 200)})`,
                    opacity: Math.max(intensity / 100, 0.35),
                  }}
                >
                  {d.total}
                </div>
                <span className="text-xs text-gray-600 dark:text-gray-400 flex-1 truncate">
                  {d.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
