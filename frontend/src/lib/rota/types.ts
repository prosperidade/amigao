/**
 * Tipos da Rota Regulatória (E5, Sprint 2).
 *
 * Espelham os schemas `Out` do backend (`app/schemas/rota.py`). NÃO inventar
 * campo nem renomear valor — bate com o JSON real.
 */

export type RotaStatus = 'proposta' | 'em_validacao' | 'validada' | 'desatualizada';
export type RotaPassoClassificacao = 'item_proposta' | 'direcao';
export type RotaPassoOrigem = 'ia' | 'manual';
export type RotaPassoStatus = 'proposto' | 'validado';

/** SourceRef do contrato #70 (`stage_output.py`). Leitura tolerante. */
export interface RotaFonte {
  tipo?: string;
  ref?: string | null;
  descricao?: string | null;
  valor?: string | null;
  confianca?: string | null;
  sem_fonte?: boolean;
}

export interface RotaPasso {
  id: number;
  rota_id: number;
  ordem: number;
  titulo: string;
  descricao: string | null;
  orgao: string | null;
  prazo_estimado_dias: number | null;
  prazo_fonte: string | null;
  sources: RotaFonte[];
  norma_ref: string | null;
  classificacao: RotaPassoClassificacao | null;
  origem: RotaPassoOrigem;
  origem_manual_nota: string | null;
  status: RotaPassoStatus;
  created_at: string | null;
  updated_at: string | null;
}

export interface Rota {
  id: number;
  process_id: number;
  demand_type: string;
  status: RotaStatus;
  caminho_regulatorio: string | null;
  orgao_competente: string | null;
  source_ai_job_id: number | null;
  validated_by: number | null;
  validated_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  passos: RotaPasso[];
}

export interface RotaMaterializeResponse {
  created: number;
  matched: number;
  is_diff: boolean;
  rota: Rota;
}

export interface PassoCreatePayload {
  titulo: string;
  descricao?: string | null;
  orgao?: string | null;
  prazo_estimado_dias?: number | null;
  norma_ref?: string | null;
  origem_manual_nota?: string | null;
  classificacao?: RotaPassoClassificacao | null;
}

export interface PassoUpdatePayload {
  titulo?: string;
  descricao?: string | null;
  orgao?: string | null;
  prazo_estimado_dias?: number | null;
  classificacao?: RotaPassoClassificacao | null;
  origem_manual_nota?: string | null;
}

// ─── Rótulos e badges (UI) ──────────────────────────────────────────────────

export const ROTA_STATUS_LABEL: Record<RotaStatus, string> = {
  proposta: 'Proposta pela IA',
  em_validacao: 'Em validação',
  validada: 'Rota fechada',
  desatualizada: 'Desatualizada',
};

export const ROTA_STATUS_CLS: Record<RotaStatus, string> = {
  proposta: 'bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-slate-300 border-slate-200 dark:border-zinc-700',
  em_validacao: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 border-blue-200 dark:border-blue-800',
  validada: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
  desatualizada: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 border-amber-200 dark:border-amber-800',
};

export const CLASSIFICACAO_LABEL: Record<RotaPassoClassificacao, string> = {
  item_proposta: 'Item de proposta',
  direcao: 'Direção',
};

export const CLASSIFICACAO_CLS: Record<RotaPassoClassificacao, string> = {
  item_proposta: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
  direcao: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800',
};
