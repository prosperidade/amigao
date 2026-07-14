/**
 * activityLabels — tradução de eventos de auditoria para linguagem de consultor.
 *
 * O feed "Atividades Recentes" do dashboard lê `AuditLog` cru (ex.:
 * `agent.vigia.completed` + JSON). O consultor não pode ver linguagem de máquina.
 * Este módulo é a CAMADA DE APRESENTAÇÃO: converte cada evento numa frase PT-BR
 * com dados úteis interpolados. A gravação do evento permanece intocada (é
 * auditoria). Ver ADR-025.
 *
 * Contrato: `translateActivity` NUNCA devolve JSON cru na `title`. O detalhe
 * técnico (action + payload) vai só em `technical`, para tooltip/expandir.
 * Evento sem tradução → frase genérica humana (fallback obrigatório).
 */

// Fonte única do mapa agente → rótulo de produto: `@/types/agent`. Reexportado
// aqui por conveniência para quem já importa deste módulo.
import { AGENT_LABELS } from '@/types/agent';
export { AGENT_LABELS };

export function agentLabel(name: string): string {
  return AGENT_LABELS[name] ?? name.replace(/_/g, ' ');
}

// ── Tipos ────────────────────────────────────────────────────────────────────
export interface ActivityLike {
  action: string;
  entity_type: string;
  entity_id: number;
  entity_label?: string | null;
  details?: string | null;
  actor_name?: string | null;
}

export interface TranslatedActivity {
  /** Frase PT-BR de consultor. Nunca contém JSON cru nem termo técnico. */
  title: string;
  /** Detalhe técnico (action + payload legível) — só p/ tooltip/expandir. */
  technical: string;
  /** True quando caiu no fallback genérico (evento sem tradução dedicada). */
  isFallback: boolean;
}

export const FALLBACK_TITLE = 'Atividade registrada no sistema';

// ── Parse seguro do details (JSON string) ────────────────────────────────────
function parseDetails(details: string | null | undefined): Record<string, unknown> | null {
  if (!details) return null;
  const trimmed = details.trim();
  if (!trimmed || trimmed[0] !== '{') return null;
  try {
    const parsed: unknown = JSON.parse(trimmed);
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** Sufixo " — {caso}" quando há um nome de caso resolvido. */
function caseSuffix(a: ActivityLike): string {
  const label = a.entity_label?.trim();
  if (label) return ` — ${label}`;
  // process/agent têm entity_id = id do processo; senão não há caso resolvível.
  if ((a.entity_type === 'process' || a.entity_type === 'agent') && a.entity_id > 0) {
    return ` — caso #${a.entity_id}`;
  }
  return '';
}

// ── Frases específicas de agente (completed) ─────────────────────────────────
// Sem entrada aqui → "{rótulo} concluído{caso}".
const AGENT_COMPLETED_PHRASE: Record<string, string> = {
  vigia: 'Vigia normativo: verificação de legislação concluída',
  extrator: 'Leitura de documentos concluída',
  auditor_imovel: 'Auditoria do imóvel concluída',
  diagnostico: 'Diagnóstico concluído',
  legislacao: 'Análise legal concluída',
  redator: 'Peça redigida',
  orcamento: 'Orçamento calculado',
  financeiro: 'Análise financeira concluída',
  atendimento: 'Triagem de atendimento concluída',
  marketing: 'Ação de marketing concluída',
  acompanhamento: 'Acompanhamento atualizado',
  orchestrator: 'Rodada de agentes concluída',
};

// ── Dicionário de ações não-agente → frase ───────────────────────────────────
// Cada função recebe o evento + details parseado e devolve a frase. TODOS os
// event types existentes têm entrada; o que faltar cai no fallback (por design).
type Phraser = (a: ActivityLike, d: Record<string, unknown> | null) => string;

const ACTION_PHRASES: Record<string, Phraser> = {
  created: (a) => (a.entity_type === 'task' ? 'Tarefa criada' : `Caso criado${caseSuffix(a)}`),
  status_changed: (a) => `Status do caso atualizado${caseSuffix(a)}`,
  notification_process_status_changed: (a) => `Status do caso atualizado${caseSuffix(a)}`,
  updated: (a) => `Caso atualizado${caseSuffix(a)}`,
  deleted: () => 'Registro removido',
  cascade_deleted: (a) => (a.entity_type === 'property' ? 'Imóvel removido' : 'Cliente removido'),
  macroetapa_changed: (a) => `Etapa do caso avançada${caseSuffix(a)}`,
  triagem: (a) => `Caso triado${caseSuffix(a)}`,
  demand_type_classified: (a) => `Tipo de demanda identificado${caseSuffix(a)}`,
  consolidar: (a) => `Base do caso consolidada${caseSuffix(a)}`,
  reconciled: (a) => `Dados do caso reconciliados${caseSuffix(a)}`,
  base_enriched: (a) => `Base do caso enriquecida${caseSuffix(a)}`,
  field_selo: () => 'Selo de validação aplicado a um campo',
  fields_validated: () => 'Campos validados',
  validated: () => 'Diagnóstico assinado pelo consultor',
  decisao_changed: () => 'Decisão do consultor registrada em um alerta',
  justificativa_changed: () => 'Justificativa de decisão atualizada',
  rota_materializada: (a) => `Documento da rota gerado${caseSuffix(a)}`,
  rota_fechada: (a, d) => {
    const n = num(d?.passos ?? d?.total_passos ?? d?.n_passos);
    return n != null
      ? `Rota do caso fechada com ${n} passo${n === 1 ? '' : 's'}${caseSuffix(a)}`
      : `Rota do caso fechada${caseSuffix(a)}`;
  },
  generated: () => 'Documento gerado',
  uploaded: () => 'Documento enviado',
  notification_document_uploaded: () => 'Documento enviado',
  extractor_dispatched: (a) => `Leitura de documentos iniciada${caseSuffix(a)}`,
  stage_agents_dispatched: (a) => `Agentes da etapa acionados${caseSuffix(a)}`,
  draft_migrated: (a) => `Rascunho migrado para o caso${caseSuffix(a)}`,
  matricula_movida: () => 'Matrícula reorganizada entre imóveis',
  declarar_contiguidade: () => 'Contiguidade de matrículas declarada',
  ai_summary_generated: (a) => `Resumo do caso atualizado${caseSuffix(a)}`,
  inbound_orphan: () => 'Mensagem recebida sem caso vinculado',
  // Eventos de sistema — normalmente filtrados no backend antes de chegar aqui;
  // mantidos como defesa (nunca devem vazar JSON, mesmo se aparecerem).
  reset_casos_teste: () => 'Manutenção do sistema',
  ai_key_used: () => 'Uso de chave de IA registrado',
};

// Regex do padrão de evento de agente: agent.{nome}.{status}
const AGENT_EVENT_RE = /^agent\.([a-z_]+)\.(started|completed|failed)$/;
// Regex do padrão de mudança de campo dinâmico: {campo}_changed
const FIELD_CHANGED_RE = /^([a-z_]+)_changed$/;

/** Monta o detalhe técnico legível (nunca vira title). */
function technicalDetail(a: ActivityLike, d: Record<string, unknown> | null): string {
  const base = a.action;
  if (!d) return base;
  // Escalares úteis, sem ruído (trace_id/hashes ficam de fora).
  const keep = ['status', 'confidence', 'requires_review', 'duration_ms', 'process_id'];
  const parts = keep
    .filter((k) => d[k] !== undefined && d[k] !== null)
    .map((k) => `${k}=${String(d[k])}`);
  return parts.length ? `${base} · ${parts.join(' · ')}` : base;
}

/**
 * Traduz um evento de auditoria para linguagem de consultor.
 * Garante: title humana sempre; JSON cru nunca renderiza; fallback obrigatório.
 */
export function translateActivity(a: ActivityLike): TranslatedActivity {
  const d = parseDetails(a.details);
  const technical = technicalDetail(a, d);

  // 1) Eventos de agente: agent.{nome}.{status}
  const agentMatch = a.action.match(AGENT_EVENT_RE);
  if (agentMatch) {
    const [, name, status] = agentMatch;
    if (status === 'failed') {
      return {
        title: `${agentLabel(name)}: houve um problema na execução${caseSuffix(a)}`,
        technical,
        isFallback: false,
      };
    }
    if (status === 'started') {
      return { title: `${agentLabel(name)} em execução${caseSuffix(a)}`, technical, isFallback: false };
    }
    // completed
    const phrase = AGENT_COMPLETED_PHRASE[name] ?? `${agentLabel(name)} concluído`;
    return { title: `${phrase}${caseSuffix(a)}`, technical, isFallback: false };
  }

  // 2) Dicionário de ações conhecidas
  const phraser = ACTION_PHRASES[a.action];
  if (phraser) {
    return { title: phraser(a, d), technical, isFallback: false };
  }

  // 3) Mudança de campo dinâmica ({campo}_changed) — de RegulatoryIssue etc.
  if (FIELD_CHANGED_RE.test(a.action)) {
    return { title: 'Alerta regulatório atualizado', technical, isFallback: false };
  }

  // 4) Fallback obrigatório: frase genérica humana, técnico só no detalhe.
  return { title: FALLBACK_TITLE, technical, isFallback: true };
}

// ── Rótulos de prioridade de tarefa (varredura: evita "high"/"critical" na tela) ─
export const TASK_PRIORITY_LABELS: Record<string, string> = {
  critical: 'Crítica',
  high: 'Alta',
  medium: 'Média',
  low: 'Baixa',
};

export function taskPriorityLabel(priority: string): string {
  return TASK_PRIORITY_LABELS[priority] ?? priority;
}
