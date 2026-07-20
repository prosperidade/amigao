/**
 * ConferenciaTab — aba "Conferência" do ProcessDetail (Ficha 07).
 *
 * "Onde o que foi lido vira base": a decisão do consultor sobre o staging
 * (campos a conferir + divergências de dado) e a consolidação na base, via
 * ConsolidacaoPanel. Os ALERTAS REGULATÓRIOS do auditor NÃO ficam aqui — vivem
 * na Visão geral, junto do diagnóstico (Sprint 0 / decisão Isis+André).
 *
 * Antes esta era a aba "Alertas" (AlertasTab) e misturava consolidação + alertas.
 */

import { useQuery } from '@tanstack/react-query';
import { Loader2, ClipboardCheck } from 'lucide-react';
import { api } from '@/lib/api';
import ConsolidacaoPanel from './ConsolidacaoPanel';
import CadeiaFichasPanel from './CadeiaFichasPanel';
import RequisitosPanel from './RequisitosPanel';

interface ConferenciaTabProps {
  processId: number;
}

export default function ConferenciaTab({ processId }: ConferenciaTabProps) {
  // Mesma query do ConsolidacaoPanel (mesma queryKey → cache compartilhado, sem
  // fetch duplicado). Aqui é só pra decidir entre painel e empty state — o
  // ConsolidacaoPanel retorna null quando não há campos, o que deixaria a aba em
  // branco sem este guard.
  const { data: fields = [], isLoading } = useQuery<unknown[]>({
    queryKey: ['staging-fields', processId],
    queryFn: () => api.get(`/processes/${processId}/staging-fields`).then(r => r.data),
  });

  if (isLoading) {
    return (
      <p className="text-sm text-gray-500 dark:text-slate-400 flex items-center gap-1.5 p-1">
        <Loader2 className="w-4 h-4 animate-spin" /> Carregando conferência…
      </p>
    );
  }

  if (fields.length === 0) {
    return (
      <div className="space-y-6">
        {/* Cadeia pode existir mesmo sem staging pendente (matrículas já
            consolidadas) — o painel se auto-oculta quando não há proposta. */}
        <RequisitosPanel processId={processId} />
        <CadeiaFichasPanel processId={processId} />
        <div className="rounded-xl bg-gray-50 dark:bg-white/5 border border-dashed border-gray-200 dark:border-white/10 p-8 text-center">
          <ClipboardCheck className="w-8 h-8 text-gray-300 dark:text-slate-600 mx-auto mb-2" />
          <p className="text-sm text-gray-500 dark:text-slate-400">Nada para conferir ainda.</p>
          <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">
            Quando os documentos forem extraídos, os campos a conferir e as
            divergências aparecem aqui para você decidir e gravar na base.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <RequisitosPanel processId={processId} />
      <CadeiaFichasPanel processId={processId} />
      <ConsolidacaoPanel processId={processId} />
    </div>
  );
}
