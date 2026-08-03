/**
 * Tipos da Ficha 07 — Ações.
 *
 * Espelham os schemas `Out` do backend (`app/schemas/acao.py`). NÃO inventar
 * campo nem renomear valor — bate com o JSON real.
 */

export type AcaoPrioridade = 'alta' | 'media' | 'baixa';
export type AcaoStatus = 'a_fazer' | 'em_andamento' | 'concluida' | 'bloqueada';
export type AcaoTipoTriagem = 'pendente' | 'tarefa' | 'escopo' | 'dispensada';
export type AcaoOrigem = 'diagnostico' | 'auditor' | 'manual';
export type TriagemDecisao = 'tarefa' | 'escopo' | 'dispensar';

/** SourceRef do contrato #70 (`stage_output.py`). Leitura tolerante. */
export interface AcaoFonte {
  tipo?: string;
  ref?: string | null;
  descricao?: string | null;
  valor?: string | null;
  confianca?: string | null;
  sem_fonte?: boolean;
}

export interface VinculoPassivo {
  tipo?: string;
  ref?: string | null;
  descricao?: string | null;
}

export interface Acao {
  id: number;
  process_id: number;
  titulo: string;
  descricao: string | null;
  origem: AcaoOrigem;
  origem_descricao: string | null;
  origem_fontes: AcaoFonte[];
  vinculo_passivo: VinculoPassivo | null;
  responsavel_id: number | null;
  prazo: string | null;
  prioridade: AcaoPrioridade;
  status: AcaoStatus;
  tipo_triagem: AcaoTipoTriagem;
  /** Etapa em que a ação nasceu. null = criada antes deste carimbo. */
  macroetapa: string | null;
  created_by_user_id: number | null;
  concluida_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AcaoGenerateResponse {
  created: number;
  skipped: number;
  diagnosis_version: number | null;
  acoes: Acao[];
}

export interface AcaoCreatePayload {
  titulo: string;
  descricao?: string | null;
  prioridade?: AcaoPrioridade;
  prazo?: string | null;
}

export interface AcaoUpdatePayload {
  titulo?: string;
  descricao?: string | null;
  status?: AcaoStatus;
  prioridade?: AcaoPrioridade;
  prazo?: string | null;
  responsavel_id?: number | null;
}

// ─── Rótulos e ordens (UI) ──────────────────────────────────────────────────

export const ACAO_STATUS_LABELS: Record<AcaoStatus, string> = {
  a_fazer: 'A fazer',
  em_andamento: 'Em andamento',
  concluida: 'Concluída',
  bloqueada: 'Bloqueada',
};

export const ACAO_STATUS_ORDER: AcaoStatus[] = [
  'a_fazer',
  'em_andamento',
  'concluida',
  'bloqueada',
];

export const ACAO_PRIORIDADE_LABELS: Record<AcaoPrioridade, string> = {
  alta: '🔴 Alta',
  media: '🟡 Média',
  baixa: '🟢 Baixa',
};

export const ACAO_TRIAGEM_LABELS: Record<AcaoTipoTriagem, string> = {
  pendente: 'Pendente de triagem',
  tarefa: 'Tarefa interna',
  escopo: 'Escopo de venda',
  dispensada: 'Dispensada',
};
