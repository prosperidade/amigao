import { describe, it, expect } from 'vitest';
import {
  translateActivity,
  agentLabel,
  taskPriorityLabel,
  FALLBACK_TITLE,
  type ActivityLike,
} from './activityLabels';

function evt(partial: Partial<ActivityLike>): ActivityLike {
  return {
    action: 'created',
    entity_type: 'process',
    entity_id: 1,
    entity_label: null,
    details: null,
    actor_name: null,
    ...partial,
  };
}

describe('agentLabel — rótulo de produto (nunca identificador interno)', () => {
  it('mapeia os 11 agentes + orchestrator', () => {
    expect(agentLabel('vigia')).toBe('Vigia normativo');
    expect(agentLabel('auditor_imovel')).toBe('Auditoria do imóvel');
    expect(agentLabel('legislacao')).toBe('Análise legal');
    expect(agentLabel('diagnostico')).toBe('Diagnóstico');
    expect(agentLabel('redator')).toBe('Redator');
    expect(agentLabel('orchestrator')).toBe('Equipe de agentes');
  });

  it('agente desconhecido: humaniza o slug (sem underscore), sem quebrar', () => {
    expect(agentLabel('agente_novo')).toBe('agente novo');
  });
});

describe('translateActivity — eventos de agente', () => {
  it('agent.vigia.completed → frase de consultor (o caso do print do André)', () => {
    const r = translateActivity(evt({
      action: 'agent.vigia.completed',
      entity_type: 'agent',
      entity_id: 0,
      details: '{"agent_name":"vigia","trace_id":"abc","process_id":null,"status":"completed"}',
    }));
    expect(r.title).toBe('Vigia normativo: verificação de legislação concluída');
    expect(r.isFallback).toBe(false);
    // JSON cru NUNCA aparece na title
    expect(r.title).not.toContain('{');
    expect(r.title).not.toContain('trace_id');
  });

  it('agent.diagnostico.completed interpola o nome do caso', () => {
    const r = translateActivity(evt({
      action: 'agent.diagnostico.completed',
      entity_type: 'agent',
      entity_id: 42,
      entity_label: 'Fazenda São Jorge',
    }));
    expect(r.title).toBe('Diagnóstico concluído — Fazenda São Jorge');
  });

  it('sem nome de caso, cai para "caso #id"', () => {
    const r = translateActivity(evt({
      action: 'agent.diagnostico.completed',
      entity_type: 'agent',
      entity_id: 42,
      entity_label: null,
    }));
    expect(r.title).toBe('Diagnóstico concluído — caso #42');
  });

  it('agent.legislacao.failed → frase humana, nunca "failed"', () => {
    const r = translateActivity(evt({ action: 'agent.legislacao.failed', entity_type: 'agent', entity_id: 7 }));
    expect(r.title).toContain('Análise legal');
    expect(r.title).toContain('problema');
    expect(r.title.toLowerCase()).not.toContain('failed');
  });
});

describe('translateActivity — eventos de caso conhecidos', () => {
  it('rota.fechada interpola o número de passos', () => {
    const r = translateActivity(evt({
      action: 'rota_fechada',
      entity_type: 'rota',
      entity_id: 3,
      details: '{"passos": 5}',
    }));
    expect(r.title).toBe('Rota do caso fechada com 5 passos');
  });

  it('rota.fechada sem número de passos degrada com elegância', () => {
    const r = translateActivity(evt({ action: 'rota_fechada', entity_type: 'rota', entity_id: 3 }));
    expect(r.title).toBe('Rota do caso fechada');
  });

  it('created em process vs task', () => {
    expect(translateActivity(evt({ action: 'created', entity_type: 'process', entity_id: 9, entity_label: 'Sítio X' })).title)
      .toBe('Caso criado — Sítio X');
    expect(translateActivity(evt({ action: 'created', entity_type: 'task', entity_id: 9 })).title)
      .toBe('Tarefa criada');
  });

  it('validated → "Diagnóstico assinado pelo consultor"', () => {
    expect(translateActivity(evt({ action: 'validated', entity_type: 'regulatory_diagnosis', entity_id: 1 })).title)
      .toBe('Diagnóstico assinado pelo consultor');
  });

  it('mudança de campo dinâmica ({campo}_changed) → alerta atualizado', () => {
    const r = translateActivity(evt({ action: 'severity_changed', entity_type: 'regulatory_issue', entity_id: 5 }));
    expect(r.title).toBe('Alerta regulatório atualizado');
    expect(r.isFallback).toBe(false);
  });
});

describe('translateActivity — fallback obrigatório (item 4)', () => {
  it('evento desconhecido → frase genérica humana, NUNCA JSON cru', () => {
    const r = translateActivity(evt({
      action: 'algum_evento_novo_e_estranho',
      entity_type: 'coisa',
      entity_id: 1,
      details: '{"foo":"bar","trace_id":"xyz"}',
    }));
    expect(r.title).toBe(FALLBACK_TITLE);
    expect(r.isFallback).toBe(true);
    // O JSON só pode viver no detalhe técnico, nunca na frase visível.
    expect(r.title).not.toContain('{');
    expect(r.title).not.toContain('bar');
  });

  it('technical carrega o action + escalares úteis (p/ tooltip), sem hashes de ruído', () => {
    const r = translateActivity(evt({
      action: 'agent.vigia.completed',
      entity_type: 'agent',
      entity_id: 0,
      details: '{"status":"completed","trace_id":"abc","confidence":0.9,"duration_ms":1200}',
    }));
    expect(r.technical).toContain('agent.vigia.completed');
    expect(r.technical).toContain('status=completed');
    expect(r.technical).toContain('confidence=0.9');
    expect(r.technical).not.toContain('trace_id'); // ruído fica de fora
  });

  it('details com JSON inválido não quebra (degrada para só o action)', () => {
    const r = translateActivity(evt({ action: 'created', details: '{isso não é json' }));
    expect(r.title).toContain('Caso criado');
    expect(r.technical).toBe('created');
  });
});

describe('taskPriorityLabel — varredura (sem inglês na tela)', () => {
  it('traduz as prioridades', () => {
    expect(taskPriorityLabel('critical')).toBe('Crítica');
    expect(taskPriorityLabel('high')).toBe('Alta');
    expect(taskPriorityLabel('medium')).toBe('Média');
    expect(taskPriorityLabel('low')).toBe('Baixa');
  });
  it('valor desconhecido passa direto (sem quebrar)', () => {
    expect(taskPriorityLabel('urgentissima')).toBe('urgentissima');
  });
});
