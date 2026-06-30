/**
 * Tipos do contrato regulatório.
 *
 * Espelha os schemas Pydantic `Out` do backend (PROMPT_5, 7 e 8):
 * - `RegulatoryIssueOut` (taxonomia rica + 2 status perenes — PROMPT_7 dropou os 3 campos
 *   de decisão; eles vivem agora em `ProcessIssueDecisionOut`).
 * - `ProcessIssueDecisionOut` (decisão contextual ao processo — ADR-012 / PROMPT_7).
 * - Enums (`StatusAchado`, `StatusSaneamento`, `DecisaoConsultor`, `RegulatoryFamilia`,
 *   `RegulatoryIssueSeverity`) — valores exatos do backend, sem aliases.
 *
 * NÃO inventar campo nem renomear valor — bate com o JSON real.
 */

export type StatusAchado =
  | 'suspeita'
  | 'confirmada'
  | 'descartada'
  | 'resolvida'
  | 'ignorada';

export type StatusSaneamento =
  | 'pendente'
  | 'em_validacao'
  | 'saneado'
  | 'descartado'
  | 'nao_aplicavel';

export type DecisaoConsultor =
  | 'corrigir_antes'
  | 'seguir_com_ressalva'
  | 'solicitar_doc'
  | 'fora_escopo'
  | 'ignorar_justificado';

export type RegulatoryFamilia =
  | 'identificacao'
  | 'titularidade'
  | 'area'
  | 'geoespacial'
  | 'geo_incra'
  | 'car'
  | 'ambiental'
  | 'fiscal'
  | 'restricao_risco'
  | 'licenciamento'
  | 'validade_documental';

export type RegulatoryIssueSeverity =
  | 'informativo'
  | 'atencao'
  | 'alto'
  | 'critico';

// Catálogo legado de tipos (deprecated — pode vir nullable).
export type RegulatoryIssueType =
  | 'area_divergente'
  | 'sobreposicao_app'
  | 'sobreposicao_reserva'
  | 'poligono_fora_matricula'
  | 'outro';

export interface RegulatoryIssue {
  id: number;
  property_id: number;
  document_id: number | null;
  codigo_alerta: string | null;
  familia: RegulatoryFamilia | null;
  muda_rota_regulatoria: boolean | null;
  muda_escopo_preco_prazo: boolean | null;
  documentos_cruzados: string[] | null;
  severity: RegulatoryIssueSeverity;
  status_achado: StatusAchado;
  status_saneamento: StatusSaneamento;
  type: RegulatoryIssueType | null;
  payload: Record<string, unknown> | null;
  detected_by: string | null;
  detected_at: string;
  resolved_at: string | null;
}

/**
 * Nota DERIVADA na leitura (ADR-020) — não-acionável, nunca armazenada.
 * Vem de `GET /properties/{id}/diagnosis-notes`. A UI a renderiza como linha
 * discreta (sem selects/decisão), separada dos achados.
 */
export interface DiagnosisNote {
  codigo: string;
  titulo: string;
  texto: string;
  severity: RegulatoryIssueSeverity;
  source: 'derived';
  acionavel: false;
}

export interface ProcessIssueDecision {
  id: number;
  process_id: number;
  issue_id: number;
  decisao: DecisaoConsultor;
  justificativa: string | null;
  decided_by_user_id: number | null;
  decided_at: string;
  created_at: string | null;
  updated_at: string | null;
}

/**
 * Payload do PATCH /properties/{prop}/issues/{id} — body parcial.
 * `extra="forbid"` no backend: SÓ esses 2 campos.
 */
export interface RegulatoryIssueUpdatePayload {
  status_achado?: StatusAchado;
  status_saneamento?: StatusSaneamento;
}

/**
 * Payload do PUT /processes/{pid}/issues/{iid}/decision.
 * `decisao` é obrigatório; `justificativa` exigida quando
 * `decisao in {ignorar_justificado, fora_escopo}` (#19).
 */
export interface ProcessIssueDecisionUpsertPayload {
  decisao: DecisaoConsultor;
  justificativa?: string | null;
}

/**
 * Shape do 422 do gate camada 2 (`PATCH /diagnoses/{version}/validate`).
 * Distinto do 422 string-simples das Regras A/B.
 */
export interface DiagnosisGate422Detail {
  message: string;
  alertas_pendentes: Array<{
    id: number;
    codigo_alerta: string | null;
    familia: RegulatoryFamilia | null;
    severity: RegulatoryIssueSeverity;
  }>;
}

/**
 * `RegulatoryDiagnosisOut` — só campos que a UI consome agora.
 */
export interface RegulatoryDiagnosis {
  id: number;
  process_id: number;
  version: number;
  validated_by_user_id: number | null;
  validated_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/**
 * Conjuntos que casam com as Regras A e B do `regulatory_coherence.py`.
 * Mantemos aqui pra que a UI desabilite proativamente o que o backend rejeitaria —
 * principalmente a Regra B (decisão indisponível enquanto achado for `suspeita`).
 */
export const DECISAOS_QUE_EXIGEM_JUSTIFICATIVA = new Set<DecisaoConsultor>([
  'ignorar_justificado',
  'fora_escopo',
]);

export const ACHADOS_QUE_HABILITAM_DECISAO = new Set<StatusAchado>([
  'confirmada',
  'descartada',
  'resolvida',
  'ignorada',
]);
// Equivalente a "não é `suspeita`" — espelha a Regra B do backend.
