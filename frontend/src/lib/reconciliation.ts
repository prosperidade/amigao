/**
 * Tipos + queryKey da Conferência por decisões (Frente G, ADR-067).
 *
 * Espelham `app/schemas/reconciliation.py` — endpoints `GET/POST
 * /processes/{id}/staging-decisions`. Em arquivo próprio (não em
 * `DecisoesPanel.tsx`) porque um arquivo de componente só pode exportar
 * componentes (react-refresh/only-export-components) — `ConsolidacaoPanel`
 * também precisa da mesma queryKey para saber quais staging_ids já viraram
 * decisão.
 */

export interface Evidencia {
  staging_id: number | null;
  documento_id: number | null;
  documento_tipo: string | null;
  campo: string | null;
  valor_bruto: unknown;
  valor_normalizado: unknown;
  unidade: string | null;
  vigencia: string | null;
  status: string;
  fonte_autoritativa: boolean;
}

export interface Decisao {
  chave: { entidade: string; identificador: string; aspecto: string };
  chave_str: string;
  label: string;
  evidencias: Evidencia[];
  concordancia: 'concordam' | 'divergem' | 'fonte_unica';
  nivel_divergencia: 'informativo' | 'atencao' | 'alto' | 'critico' | null;
  delta: number | null;
  percentual: number | null;
  valor_proposto: unknown;
  fonte_autoritativa_doc: string | null;
  estado: 'pendente' | 'decidida' | 'gravada';
  staging_ids: number[];
}

export interface ReconciliationData {
  decisoes: Decisao[];
  sem_agrupamento: Array<{ staging_id: number; motivo: string | null }>;
  total_staging: number;
}

export function decisoesQueryKey(processId: number) {
  return ['staging-decisions', processId];
}
