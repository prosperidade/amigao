import { describe, expect, it } from 'vitest';
import { descreverVersao } from './versao';

describe('descreverVersao', () => {
  it('mostra os dois commits curtos e o ambiente em português', () => {
    const r = descreverVersao('3c0e3697abcdef', { commit: '3c0e3697abcdef', ambiente: 'production' }, false);
    expect(r.texto).toBe('Painel 3c0e369 · API 3c0e369 · produção');
    expect(r.divergente).toBe(false);
    expect(r.producao).toBe(true);
  });

  it('acusa painel e API em commits diferentes', () => {
    const r = descreverVersao('aaaaaaa1', { commit: 'bbbbbbb2', ambiente: 'production' }, false);
    expect(r.divergente).toBe(true);
  });

  it('commit ausente vira "sem commit", nunca some', () => {
    const r = descreverVersao(null, { commit: null, ambiente: 'development' }, false);
    expect(r.texto).toBe('Painel sem commit · API sem commit · desenvolvimento');
    expect(r.divergente).toBe(false);
  });

  it('API fora do ar é dito, não escondido', () => {
    const r = descreverVersao('abc1234', undefined, true);
    expect(r.texto).toBe('Painel abc1234 · API — · API indisponível');
    expect(r.producao).toBe(false);
  });
});
