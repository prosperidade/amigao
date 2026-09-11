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

/**
 * STATE-001/ADR-068 (Frente H) — a MESMA chave que `ConsolidacaoPanel.tsx`
 * usa para o banner canônico de progresso da Conferência. Compartilhada aqui
 * para que `DecisoesPanel.tsx` (onde o consultor decide de fato) também
 * invalide o número — sem isto, decidir por `DecisoesPanel` refresca a lista
 * mas deixa o banner acima dela com a contagem velha: dois números sobre o
 * mesmo fato discordando na MESMA tela, o próprio sintoma que STATE-001
 * existe para matar (achado do code review desta frente).
 */
export function progressoConferenciaKey(processId: number) {
  return ['progresso-conferencia', processId];
}
