import { describe, it, expect } from 'vitest';
import {
  isTabVisible,
  resolveActiveTab,
  resolveTabVisibility,
  parseTabFlagOverride,
  TAB_VISIBILITY_DEFAULTS,
  FALLBACK_TAB,
} from './tabFlags';

// As 6 abas do MVP + a Comercial, que voltou à superfície (21/07): o consultor
// sentiu falta dos botões de Proposta/Contrato no workspace. Segue gated por
// etapa (min_stage_index=5) — visível de novo, mas só a partir do momento
// comercial. As 5 abas do Sprint 6 seguem ocultas (vivas por baixo).
const AbasVisiveis = ['diagnosis', 'documents', 'alertas', 'dossier', 'acoes', 'saidas', 'commercial'];
const AbasOcultas = ['tasks', 'messages', 'ai', 'timeline', 'decisions'];

describe('isTabVisible', () => {
  it('as 6 abas do MVP + a Comercial ficam visíveis', () => {
    for (const key of AbasVisiveis) {
      expect(isTabVisible(key), `${key} deveria estar visível`).toBe(true);
    }
  });

  it('as 5 abas do Sprint 6 ficam ocultas', () => {
    for (const key of AbasOcultas) {
      expect(isTabVisible(key), `${key} deveria estar oculta`).toBe(false);
    }
  });

  it('a Comercial (E6/E7) voltou à superfície (21/07) — botões de proposta/contrato', () => {
    expect(isTabVisible('commercial')).toBe(true);
  });

  it('chave desconhecida é fail-open (visível) — nunca esconde aba nova por engano', () => {
    expect(isTabVisible('aba-que-nao-existe')).toBe(true);
  });

  it('o default cobre exatamente as 12 abas conhecidas', () => {
    expect(Object.keys(TAB_VISIBILITY_DEFAULTS).sort()).toEqual(
      [...AbasVisiveis, ...AbasOcultas].sort(),
    );
  });
});

describe('resolveActiveTab (guarda de deep-link / estado herdado)', () => {
  it('aba visível é preservada', () => {
    expect(resolveActiveTab('acoes')).toBe('acoes');
  });

  it('aba OCULTA cai suave na Visão geral (redirect)', () => {
    expect(resolveActiveTab('tasks')).toBe(FALLBACK_TAB);
    expect(resolveActiveTab('ai')).toBe(FALLBACK_TAB);
  });

  it('deep-link desconhecido/lixo → Visão geral (sem área em branco)', () => {
    expect(resolveActiveTab('banana')).toBe(FALLBACK_TAB);
  });

  it('vazio/null/undefined → Visão geral', () => {
    expect(resolveActiveTab(null)).toBe(FALLBACK_TAB);
    expect(resolveActiveTab(undefined)).toBe(FALLBACK_TAB);
    expect(resolveActiveTab('')).toBe(FALLBACK_TAB);
  });

  it('FALLBACK_TAB é a Visão geral', () => {
    expect(FALLBACK_TAB).toBe('diagnosis');
  });
});

describe('resolveTabVisibility (merge default + override por-tenant/env)', () => {
  it('sem override devolve os defaults', () => {
    expect(resolveTabVisibility(TAB_VISIBILITY_DEFAULTS, undefined)).toEqual(TAB_VISIBILITY_DEFAULTS);
  });

  it('override booleano vence o default (ex.: religar Histórico)', () => {
    const merged = resolveTabVisibility(TAB_VISIBILITY_DEFAULTS, { timeline: true });
    expect(merged.timeline).toBe(true);
    expect(merged.tasks).toBe(false); // demais intactos
  });

  it('valores não-booleanos no override são ignorados', () => {
    const merged = resolveTabVisibility(TAB_VISIBILITY_DEFAULTS, { acoes: 'sim', ai: 1, tasks: null });
    expect(merged.acoes).toBe(true);  // default preservado
    expect(merged.ai).toBe(false);
    expect(merged.tasks).toBe(false);
  });
});

describe('parseTabFlagOverride (env VITE_TAB_FLAGS)', () => {
  it('vazio/undefined → objeto vazio', () => {
    expect(parseTabFlagOverride(undefined)).toEqual({});
    expect(parseTabFlagOverride('')).toEqual({});
  });

  it('JSON válido é parseado', () => {
    expect(parseTabFlagOverride('{"timeline": true}')).toEqual({ timeline: true });
  });

  it('JSON inválido é silencioso (sem override)', () => {
    expect(parseTabFlagOverride('{nao é json')).toEqual({});
  });

  it('JSON não-objeto (ex.: número) → objeto vazio', () => {
    expect(parseTabFlagOverride('42')).toEqual({});
  });
});
