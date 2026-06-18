/**
 * historicoEventos — humaniza os eventos do "Histórico de eventos do caso".
 *
 * Regra de ouro (identidade do produto): o consultor é advogado/engenheiro
 * ambiental, não vê `target_field`, `field_id`, `staging_origin_ai_job_id` nem
 * JSON cru. Cada AuditLog vira uma FRASE em PT-BR. Os rótulos de campo vêm do
 * módulo central `lib/labels/fieldLabels` (`labelFor`).
 *
 * Item 2 (fonte): o `fonte` cru do audit é a fonte opcional do `escolher_fonte`
 * (quase sempre null e enganosa). A rastreabilidade real é o DOCUMENTO de
 * origem — entregue pelo backend em `origin_document` (resolvido via field_id).
 * Nunca exibimos "fonte: null".
 */
import { labelFor } from '@/lib/labels/fieldLabels';
import { MACROETAPA_LABELS } from './quadro-types';
import { STATUS_CONFIG, DEMAND_LABELS } from './ProcessDetailTypes';

export type EventoKind =
  | 'aceito'
  | 'rejeitado'
  | 'escolhido'
  | 'editado'
  | 'lote'
  | 'consolidado'
  | 'status'
  | 'criado'
  | 'resumo'
  | 'classificacao'
  | 'generico';

export interface HistoricoEvento {
  kind: EventoKind;
  /** Frase principal — PT-BR, sem JSON nem termo técnico. */
  titulo: string;
  /** Linha secundária opcional. */
  detalhe?: string;
  /** Documento de origem do dado decidido (rastreabilidade real). */
  origem?: string;
}

/** Entrada da timeline (espelha `AuditLogRead` do backend). */
export interface TimelineEvent {
  id: number;
  action: string;
  details?: string | null;
  old_value?: string | null;
  new_value?: string | null;
  created_at: string;
  origin_document?: string | null;
}

// Campos cujo rótulo PT-BR é feminino (para concordância do particípio:
// "aceita/rejeitada"). Default é masculino ("aceito/rejeitado" — concorda com
// "o campo"). Chaveado pelo `target_field` da base.
const CAMPO_FEMININO = new Set<string>([
  'denominacao_imovel', 'area_ha', 'area', 'area_total_ha', 'total_area_ha',
  'area_grafica_ha', 'app_area_ha', 'area_hectares', 'area_app', 'area_rl',
  'rl_status', 'car_status', 'geo_certificacao_status', 'averbacao_app',
  'averbacao_rl', 'birth_date', 'data_emissao', 'data_registro', 'data_nascimento',
  'rat_data_emissao', 'validade', 'uf', 'state',
]);

type Particula = 'aceito' | 'rejeitado' | 'editado';

function participio(base: Particula, target?: string): string {
  const f = !!target && CAMPO_FEMININO.has(target);
  if (base === 'aceito') return f ? 'aceita' : 'aceito';
  if (base === 'rejeitado') return f ? 'rejeitada' : 'rejeitado';
  return f ? 'editada' : 'editado';
}

/** "da matrícula 4655" / "do imóvel" / "do cliente" / "". */
function sufixoAlvo(d: Record<string, unknown>): string {
  const hint = d.matricula_hint;
  if (typeof hint === 'string' && hint.trim()) return `da matrícula ${hint}`;
  const entity = typeof d.target_entity === 'string' ? d.target_entity.toLowerCase() : '';
  if (entity === 'imovel') return 'do imóvel';
  if (entity === 'cliente') return 'do cliente';
  if (entity === 'matricula') return 'da matrícula';
  return '';
}

function statusLabel(v?: string | null): string {
  if (!v) return '—';
  return STATUS_CONFIG[v]?.label ?? humanizar(v);
}

function demandLabel(v?: string | null): string {
  if (!v) return '—';
  return DEMAND_LABELS[v] ?? humanizar(v);
}

/** Humaniza um token técnico cru (snake_case → "Snake case"). */
function humanizar(token: string): string {
  const s = token.replace(/_/g, ' ').trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : token;
}

function plural(n: number, singular: string, plural_: string): string {
  return n === 1 ? `1 ${singular}` : `${n} ${plural_}`;
}

function parseDetails(details?: string | null): Record<string, unknown> | string | null {
  if (!details) return null;
  const trimmed = details.trim();
  if (!(trimmed.startsWith('{') || trimmed.startsWith('['))) return details;
  try {
    const parsed = JSON.parse(trimmed);
    return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : details;
  } catch {
    return details;
  }
}

function str(v: unknown): string | undefined {
  return typeof v === 'string' && v.trim() ? v : undefined;
}
function num(v: unknown): number {
  return typeof v === 'number' ? v : 0;
}

/**
 * Converte um evento bruto da timeline numa frase humana. NUNCA devolve JSON
 * cru nem `target_field`/`field_id`/`fonte` técnicos.
 */
export function describeEvento(log: TimelineEvent): HistoricoEvento {
  const d = parseDetails(log.details);
  const obj = (typeof d === 'object' && d !== null) ? (d as Record<string, unknown>) : null;
  const origem = str(log.origin_document);

  switch (log.action) {
    // ── Decisão do consultor sobre um campo (Ficha 01 / FASE 4) ──────────────
    case 'staging_decidir': {
      const o = obj ?? {};
      const target = typeof o.target_field === 'string' ? o.target_field : '';
      const campo = labelFor(target || '');
      const suf = sufixoAlvo(o);
      const alvo = suf ? `${campo} ${suf}` : campo;
      const acao = typeof o.acao === 'string' ? o.acao : '';
      if (acao === 'rejeitar') {
        return { kind: 'rejeitado', titulo: `${alvo} ${participio('rejeitado', target)}.`, origem };
      }
      if (acao === 'editar') {
        return { kind: 'editado', titulo: `${alvo} ${participio('editado', target)} manualmente.`, origem };
      }
      if (acao === 'escolher_fonte') {
        return {
          kind: 'escolhido',
          titulo: `${alvo}: escolhida uma fonte entre as divergentes.`,
          origem,
        };
      }
      // aceitar (default)
      return { kind: 'aceito', titulo: `${alvo} ${participio('aceito', target)}.`, origem };
    }

    case 'staging_aceitar_consistentes': {
      const count = num(obj?.count);
      return {
        kind: 'lote',
        titulo: `${plural(count, 'campo consistente aceito', 'campos consistentes aceitos')} de uma vez.`,
      };
    }

    case 'consolidar': {
      const gravados = num(obj?.campos_gravados);
      const criadas = num(obj?.matriculas_criadas);
      const atualizadas = num(obj?.matriculas_atualizadas);
      const recon = Array.isArray(obj?.reconciliacoes) ? (obj!.reconciliacoes as unknown[]).length : 0;
      const partes: string[] = [];
      if (criadas > 0) partes.push(plural(criadas, 'matrícula criada', 'matrículas criadas'));
      if (atualizadas > 0) partes.push(plural(atualizadas, 'matrícula atualizada', 'matrículas atualizadas'));
      if (recon > 0) partes.push(`${plural(recon, 'divergência', 'divergências')} aguardando decisão`);
      return {
        kind: 'consolidado',
        titulo: `${plural(gravados, 'campo gravado', 'campos gravados')} na base do imóvel.`,
        detalhe: partes.length ? partes.join(' · ') : undefined,
      };
    }

    // ── Status / etapa ───────────────────────────────────────────────────────
    case 'status_changed':
      return {
        kind: 'status',
        titulo: `Status do caso: ${statusLabel(log.old_value)} → ${statusLabel(log.new_value)}`,
      };

    case 'notification_process_status_changed': {
      const o = obj ?? {};
      return {
        kind: 'status',
        titulo: `Status do caso: ${statusLabel(str(o.old_status) ?? null)} → ${statusLabel(str(o.new_status) ?? null)}`,
      };
    }

    case 'macroetapa_changed': {
      const old = log.old_value ? (MACROETAPA_LABELS[log.old_value] ?? humanizar(log.old_value)) : '—';
      const nv = log.new_value ? (MACROETAPA_LABELS[log.new_value] ?? humanizar(log.new_value)) : '—';
      return { kind: 'status', titulo: `Etapa do caso: ${old} → ${nv}` };
    }

    case 'demand_type_classified':
      return {
        kind: 'classificacao',
        titulo: `Tipo de demanda: ${demandLabel(log.old_value)} → ${demandLabel(log.new_value)}`,
      };

    // ── Eventos de sistema ───────────────────────────────────────────────────
    case 'created':
      return { kind: 'criado', titulo: 'Caso criado.' };

    case 'extractor_dispatched':
      return { kind: 'generico', titulo: 'Extração de documentos iniciada.' };

    case 'ai_summary_generated': {
      const texto = typeof d === 'string' ? d : undefined;
      return {
        kind: 'resumo',
        titulo: 'Resumo automático do caso atualizado.',
        detalhe: texto && texto.length > 200 ? `${texto.slice(0, 200)}…` : texto,
      };
    }

    default:
      return descreverGenerico(log, d);
  }
}

/**
 * Fallback seguro: nunca imprime JSON cru. Texto livre passa direto; objeto vira
 * "Rótulo: valor" só dos campos escalares relevantes (sem field_id/ai_job_id).
 */
const META_OCULTO = new Set<string>([
  'field_id', 'field_ids', 'ai_job_id', 'staging_origin_ai_job_id', 'fonte',
  'irmaos_rejeitados', 'status', 'target_entity', 'process_id', 'channels',
  'writes', 'reconciliacoes', 'count', 'acao',
]);

function descreverGenerico(log: TimelineEvent, d: Record<string, unknown> | string | null): HistoricoEvento {
  if (typeof d === 'string') {
    return { kind: 'generico', titulo: d };
  }
  const titulo = humanizar(log.action);
  if (d && typeof d === 'object') {
    const partes = Object.entries(d)
      .filter(([k, v]) =>
        !META_OCULTO.has(k) &&
        v != null && v !== '' &&
        (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean'),
      )
      .map(([k, v]) => `${labelFor(k)}: ${String(v)}`);
    return { kind: 'generico', titulo, detalhe: partes.length ? partes.join(' · ') : undefined };
  }
  return { kind: 'generico', titulo };
}
