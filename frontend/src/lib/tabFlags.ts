/**
 * tabFlags — feature flag de VISIBILIDADE das abas do workspace do caso.
 *
 * Sprint 6 (Ficha 07 §3). A Ficha define 6 abas no MVP, nesta ordem:
 *   Visão geral · Documentos · Conferência · Dados · Ações · Saídas.
 * Hoje o workspace mostra ~10. Este módulo é a FONTE ÚNICA de "qual aba
 * aparece na barra". OCULTAR ≠ APAGAR: as abas ocultas continuam existindo
 * (componente, rota de API, dados gravados por baixo) — só somem da superfície.
 * Ver ADR-024.
 *
 * Precedente: `min_stage_index` (TabDef em ProcessDetailTypes) já filtrava a
 * aba Comercial por etapa. Este flag é o eixo ORTOGONAL "visível/oculto por
 * decisão de produto" — os dois convivem (a Comercial precisa dos dois: flag
 * visível E etapa ≥ 6).
 *
 * Evolução prevista (NÃO construída aqui — sem admin de flags): por-tenant.
 * Quando existir, `TAB_VISIBILITY_DEFAULTS` vira o fallback e `isTabVisible`
 * passa a consultar o override do tenant. A assinatura já recebe um `ctx`
 * opcional pra o call site não precisar mudar quando isso chegar.
 */

/**
 * Default global de visibilidade por chave de aba (as chaves espelham
 * `TABS[].key` em ProcessDetailTypes). Chave ausente = visível (fail-open).
 */
export const TAB_VISIBILITY_DEFAULTS: Record<string, boolean> = {
  // ── As 6 abas do MVP (Ficha 07 §3) ──────────────────────────────────────
  diagnosis: true,   // Visão geral
  documents: true,   // Documentos
  alertas: true,     // Conferência (a key histórica é 'alertas'; o label é Conferência)
  dossier: true,     // Dados
  acoes: true,       // Ações
  saidas: true,      // Saídas

  // Comercial VISÍVEL de novo (21/07): o consultor sentiu falta dos botões de
  // Proposta e Contrato no workspace do caso. A aba volta à superfície — segue
  // gated por etapa (min_stage_index=5, orçamento/negociação em diante), então
  // só aparece quando o caso chega ao momento comercial e os botões têm o que
  // fazer (a proposta nasce da Rota, S5-A) — sem botão morto em etapa cedo.
  commercial: true,

  // ── Ocultas no MVP (Sprint 6) — vivas por baixo, só a superfície some ────
  tasks: false,      // Tarefas — a entidade Task segue existindo; a fusão
                     //   Tarefas→Ações é dívida pós-MVP (não é 1:1).
  messages: false,   // Comunicação
  timeline: false,   // Histórico — o sistema SEGUE registrando (audit log intacto)
  decisions: false,  // Decisões
  ai: false,         // IA — aba quebrada (não dispara a cadeia); ocultar resolve
                     //   a dor de hoje, o conserto é dívida.
};

/**
 * Contexto reservado para evolução por-tenant. Hoje ignorado (flag global).
 */
export interface TabFlagContext {
  tenantId?: number;
}

/**
 * Faz o merge do default com um override (ex.: vindo de env), mantendo só
 * valores booleanos. Pura e testável — não lê `import.meta` diretamente.
 */
export function resolveTabVisibility(
  defaults: Record<string, boolean>,
  override: Record<string, unknown> | undefined,
): Record<string, boolean> {
  const merged: Record<string, boolean> = { ...defaults };
  if (override) {
    for (const [key, value] of Object.entries(override)) {
      if (typeof value === 'boolean') merged[key] = value;
    }
  }
  return merged;
}

/**
 * Faz o parse de um override serializado em env (`VITE_TAB_FLAGS`, JSON de
 * `{ "<key>": true|false }`). Silencioso: JSON inválido → sem override.
 */
export function parseTabFlagOverride(raw: string | undefined): Record<string, unknown> {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

const ENV_OVERRIDE = parseTabFlagOverride(
  typeof import.meta !== 'undefined' ? import.meta.env?.VITE_TAB_FLAGS : undefined,
);

/** Mapa resolvido (default + override de env), materializado no load do módulo. */
export const TAB_VISIBILITY: Record<string, boolean> = resolveTabVisibility(
  TAB_VISIBILITY_DEFAULTS,
  ENV_OVERRIDE,
);

/**
 * A aba de chave `key` deve aparecer na barra? `ctx` é reservado p/ por-tenant.
 * Chave desconhecida → visível (fail-open: nunca esconde uma aba nova por engano).
 */
export function isTabVisible(key: string, _ctx?: TabFlagContext): boolean {
  return TAB_VISIBILITY[key] ?? true;
}

/**
 * Resolve a aba efetiva a partir de uma aba REQUISITADA (ex.: deep-link `?tab=`
 * ou estado herdado). Se a requisitada estiver oculta/desconhecida-como-oculta,
 * cai suavemente na Visão geral — nunca renderiza uma aba fora da superfície,
 * nunca quebra. É o antídoto contra "deep-link de aba oculta".
 */
export const FALLBACK_TAB = 'diagnosis';

export function resolveActiveTab(requested: string | null | undefined): string {
  if (!requested) return FALLBACK_TAB;
  // Estrito (ao contrário de `isTabVisible`, que é fail-open p/ a barra):
  // só devolve a aba requisitada se ela for CONHECIDA e visível. Aba oculta,
  // desconhecida ou lixo de deep-link → cai na Visão geral (nunca área em branco).
  const known = Object.prototype.hasOwnProperty.call(TAB_VISIBILITY, requested);
  return known && isTabVisible(requested) ? requested : FALLBACK_TAB;
}
