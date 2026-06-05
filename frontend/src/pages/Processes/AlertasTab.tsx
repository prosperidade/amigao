/**
 * AlertasTab — aba "Alertas" do ProcessDetail.
 *
 * Lista os `RegulatoryIssue` do imóvel deste processo, **críticos primeiro**,
 * com `AlertaCard` de cada um. Empty state quando o processo não tem property
 * vinculada (`property_id == null` é permitido pelo backend).
 *
 * Filtro padrão: `?status=open` (não-resolvidos). O consultor decide alerta por
 * alerta neste processo — decisão é contextual ao trabalho (ADR-012).
 */

import { AlertTriangle, Loader2 } from 'lucide-react';
import { useIssues } from '@/lib/regulatory/hooks';
import { SEVERITY_ORDER } from '@/lib/regulatory/labels';
import AlertaCard from './AlertaCard';
import ConsolidacaoPanel from './ConsolidacaoPanel';

interface AlertasTabProps {
  processId: number;
  propertyId: number | null;
}

export default function AlertasTab({ processId, propertyId }: AlertasTabProps) {
  const { data: issues, isLoading, error } = useIssues(propertyId, 'open');

  // Críticos primeiro; depois alto, atencao, informativo (ordem semântica),
  // e desempate por `detected_at` decrescente.
  const sorted = issues
    ? [...issues].sort((a, b) => {
        const sev = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
        if (sev !== 0) return sev;
        return b.detected_at.localeCompare(a.detected_at);
      })
    : [];

  return (
    <div className="space-y-6">
      {/* FASE 4 — decisão do consultor + consolidação (sobre o staging) */}
      <ConsolidacaoPanel processId={processId} />

      {/* Alertas regulatórios (RegulatoryIssue) — fluxo existente, inalterado */}
      {propertyId === null ? (
        <div className="rounded-xl bg-gray-50 dark:bg-white/5 border border-dashed border-gray-200 dark:border-white/10 p-8 text-center">
          <AlertTriangle className="w-8 h-8 text-gray-300 dark:text-slate-600 mx-auto mb-2" />
          <p className="text-sm text-gray-500 dark:text-slate-400">
            Este processo não tem imóvel vinculado.
          </p>
          <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">
            Alertas regulatórios são fatos do imóvel — vincule uma property pra ver
            os alertas.
          </p>
        </div>
      ) : isLoading ? (
        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-slate-400 p-4">
          <Loader2 className="w-4 h-4 animate-spin" /> Carregando alertas…
        </div>
      ) : error ? (
        <div className="rounded-xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 p-4 text-sm text-red-700 dark:text-red-300">
          Falha ao carregar alertas regulatórios.
        </div>
      ) : sorted.length === 0 ? (
        <div className="rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 p-8 text-center">
          <p className="text-sm text-emerald-800 dark:text-emerald-300">
            Nenhum alerta aberto neste imóvel.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <header>
            <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 uppercase tracking-wider">
              Alertas regulatórios — {sorted.length}
            </h2>
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
              Adjudique o achado, depois decida o que fazer neste processo. Cada
              processo decide do zero — a decisão é contextual ao trabalho.
            </p>
          </header>
          <div className="space-y-4">
            {sorted.map(issue => (
              <AlertaCard key={issue.id} issue={issue} processId={processId} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
