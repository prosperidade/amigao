import { describe, expect, it } from 'vitest';
import { apoioNaRodada, camposLegiveis, segmentar, type ObservacaoConferencia } from './documentObservations';

const obs = (id: string, inicio: number | null, fim: number | null): ObservacaoConferencia => ({
  id, version: 1, tipo: 'parte', predicado: 'parte', trecho: null, inicio, fim, conteudo: null,
  conhecimento: 'nao_determinado', superada: false, desatualizada: false,
});

describe('segmentar', () => {
  it('cuts the text at every anchor boundary and keeps overlapping anchors', () => {
    const segmentos = segmentar('A vende a B.', [obs('a', 0, 7), obs('b', 2, 12)]);
    expect(segmentos.map(s => [s.texto, s.observacoes])).toEqual([
      ['A ', ['a']], ['vende', ['a', 'b']], [' a B.', ['b']],
    ]);
    expect(segmentos.map(s => s.texto).join('')).toBe('A vende a B.');
  });

  it('leaves anchors outside the current text version unmarked', () => {
    expect(segmentar('abc', [obs('x', null, null)])).toEqual([{ inicio: 0, fim: 3, texto: 'abc', observacoes: [] }]);
  });
});

describe('camposLegiveis', () => {
  it('hides anchor bookkeeping and empty values', () => {
    expect(camposLegiveis({ nome: 'A', trecho: 't', posicao_inicio: 1, identificador: null, lista: [], papel: 'transmitente' }))
      .toEqual([['nome', 'A'], ['papel', 'transmitente']]);
  });
});

describe('apoioNaRodada (ADR-079)', () => {
  it('diz quantas leituras da rodada viram a observação, e some com uma leitura', () => {
    expect(apoioNaRodada({ leituras_na_rodada: { viram: 1, de: 3 } })).toBe('vista em 1 de 3 leituras da rodada');
    expect(apoioNaRodada({ leituras_na_rodada: { viram: 1, de: 1 } })).toBeNull();
    expect(apoioNaRodada({ valor: 'x' })).toBeNull();
    expect(camposLegiveis({ valor: 'x', leituras_na_rodada: { viram: 2, de: 3 } })).toEqual([['valor', 'x']]);
  });
});
