import { describe, it, expect } from 'vitest';
import { describeEvento, type TimelineEvent } from './historicoEventos';

/**
 * Prova de que o histórico de eventos NUNCA mostra JSON cru / termo técnico ao
 * consultor. Payloads são os shapes reais do AuditLog de produção (process 13).
 */

function ev(partial: Partial<TimelineEvent>): TimelineEvent {
  return {
    id: 1,
    action: 'generico',
    details: null,
    old_value: null,
    new_value: null,
    created_at: '2026-06-18T12:00:00Z',
    origin_document: null,
    ...partial,
  };
}

const TECH_TOKENS = [
  'target_field', 'target_entity', 'field_id', 'matricula_hint', 'ai_job_id',
  'staging_origin_ai_job_id', '"fonte"', 'fonte:', '{', '}', '[object Object]',
  'geo_certificacao_codigo', 'denominacao_imovel', 'snake_case',
];

function assertNoTech(...texts: (string | undefined)[]) {
  const joined = texts.filter(Boolean).join(' || ');
  for (const t of TECH_TOKENS) {
    expect(joined).not.toContain(t);
  }
}

describe('describeEvento — decisões de staging (process 13 real)', () => {
  it('aceitar → frase humana com campo + matrícula, gênero masculino', () => {
    const r = describeEvento(ev({
      action: 'staging_decidir',
      details: JSON.stringify({
        field_id: 401, acao: 'aceitar', status: 'aceito', target_entity: 'matricula',
        target_field: 'geo_certificacao_codigo', matricula_hint: '4655', fonte: null,
      }),
    }));
    expect(r.kind).toBe('aceito');
    expect(r.titulo).toBe('Código de certificação SIGEF da matrícula 4655 aceito.');
    assertNoTech(r.titulo, r.detalhe);
  });

  it('rejeitar → particípio feminino para campo feminino (denominação)', () => {
    const r = describeEvento(ev({
      action: 'staging_decidir',
      details: JSON.stringify({
        field_id: 5, acao: 'rejeitar', status: 'rejeitado', target_entity: 'matricula',
        target_field: 'denominacao_imovel', matricula_hint: '2923', fonte: null,
      }),
    }));
    expect(r.kind).toBe('rejeitado');
    expect(r.titulo).toContain('rejeitada');
    expect(r.titulo).toContain('matrícula 2923');
    assertNoTech(r.titulo);
  });

  it('escolher_fonte → frase de escolha entre divergentes', () => {
    const r = describeEvento(ev({
      action: 'staging_decidir',
      details: JSON.stringify({
        field_id: 9, acao: 'escolher_fonte', status: 'aceito', target_entity: 'matricula',
        target_field: 'denominacao_imovel', matricula_hint: '6776', fonte: null,
      }),
    }));
    expect(r.kind).toBe('escolhido');
    expect(r.titulo).toContain('escolhida uma fonte entre as divergentes');
    expect(r.titulo).toContain('6776');
    assertNoTech(r.titulo);
  });

  it('Item 2 — origem do dado vem do documento, nunca "fonte: null"', () => {
    const r = describeEvento(ev({
      action: 'staging_decidir',
      origin_document: 'Matrícula 4655 - Cartório.pdf',
      details: JSON.stringify({
        field_id: 401, acao: 'aceitar', target_field: 'area_ha', matricula_hint: '4655', fonte: null,
      }),
    }));
    expect(r.origem).toBe('Matrícula 4655 - Cartório.pdf');
    assertNoTech(r.titulo, r.detalhe);
    expect((r.titulo + (r.detalhe ?? '')).toLowerCase()).not.toContain('null');
  });

  it('aceitar em lote → "N campos consistentes aceitos de uma vez"', () => {
    const r = describeEvento(ev({
      action: 'staging_aceitar_consistentes',
      details: JSON.stringify({ field_ids: [1, 2, 3, 4, 5, 6], count: 6 }),
    }));
    expect(r.kind).toBe('lote');
    expect(r.titulo).toBe('6 campos consistentes aceitos de uma vez.');
  });

  it('consolidar → campos gravados + matrículas, sem JSON', () => {
    const r = describeEvento(ev({
      action: 'consolidar',
      details: JSON.stringify({
        process_id: 13, campos_gravados: 7, matriculas_criadas: 2, matriculas_atualizadas: 0,
        writes: [{ field: 'area_ha' }], reconciliacoes: [],
      }),
    }));
    expect(r.kind).toBe('consolidado');
    expect(r.titulo).toContain('7 campos gravados');
    expect(r.detalhe).toContain('2 matrículas criadas');
    assertNoTech(r.titulo, r.detalhe);
  });
});

describe('describeEvento — status / sistema', () => {
  it('status_changed usa rótulos PT-BR', () => {
    const r = describeEvento(ev({ action: 'status_changed', old_value: 'triagem', new_value: 'diagnostico' }));
    expect(r.kind).toBe('status');
    expect(r.titulo).toBe('Status do caso: Triagem → Diagnóstico');
  });

  it('notification_process_status_changed (JSON) não vaza JSON', () => {
    const r = describeEvento(ev({
      action: 'notification_process_status_changed',
      details: JSON.stringify({ old_status: 'lead', new_status: 'triagem', channels: ['realtime_client'] }),
    }));
    expect(r.titulo).toBe('Status do caso: Lead → Triagem');
    assertNoTech(r.titulo);
    expect(r.titulo).not.toContain('channels');
  });

  it('created → "Caso criado."', () => {
    const r = describeEvento(ev({ action: 'created', details: 'Processo criado via intake (car)' }));
    expect(r.titulo).toBe('Caso criado.');
  });

  it('fallback genérico com JSON desconhecido nunca imprime chaves técnicas', () => {
    const r = describeEvento(ev({
      action: 'algo_novo_qualquer',
      details: JSON.stringify({ field_id: 99, ai_job_id: 7, alguma_coisa: 'x' }),
    }));
    assertNoTech(r.titulo, r.detalhe);
    expect(r.titulo).not.toContain('_');
  });

  it('fallback com texto livre passa direto', () => {
    const r = describeEvento(ev({ action: 'qualquer', details: 'Mensagem já humana.' }));
    expect(r.titulo).toBe('Mensagem já humana.');
  });
});
