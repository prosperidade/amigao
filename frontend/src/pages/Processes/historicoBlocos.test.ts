import { describe, it, expect } from 'vitest';
import { agruparBlocos, resumoCluster, type DescribedEvent } from './historicoBlocos';
import type { EventoKind } from './historicoEventos';

/** Helper: cria um DescribedEvent mínimo com o kind desejado. */
function de(id: number, kind: EventoKind): DescribedEvent {
  return {
    log: { id, action: 'x', created_at: '2026-06-29T12:00:00Z' },
    ev: { kind, titulo: `evento ${id}` },
  };
}

describe('agruparBlocos', () => {
  it('colapsa um run contíguo de decisões num único cluster', () => {
    // criado (marco) + 5 decisões em sequência → 1 marco + 1 cluster
    const blocos = agruparBlocos([
      de(1, 'criado'),
      de(2, 'rejeitado'), de(3, 'rejeitado'), de(4, 'aceito'), de(5, 'rejeitado'), de(6, 'aceito'),
    ]);
    expect(blocos.map((b) => b.tipo)).toEqual(['marco', 'cluster']);
    const cluster = blocos[1];
    expect(cluster.tipo === 'cluster' && cluster.itens.length).toBe(5);
  });

  it('decisão isolada NÃO colapsa (vira marco)', () => {
    const blocos = agruparBlocos([de(1, 'criado'), de(2, 'aceito'), de(3, 'consolidado')]);
    expect(blocos.map((b) => b.tipo)).toEqual(['marco', 'marco', 'marco']);
  });

  it('marco entre decisões quebra o cluster em dois', () => {
    const blocos = agruparBlocos([
      de(1, 'rejeitado'), de(2, 'rejeitado'),
      de(3, 'consolidado'),
      de(4, 'aceito'), de(5, 'aceito'),
    ]);
    expect(blocos.map((b) => b.tipo)).toEqual(['cluster', 'marco', 'cluster']);
  });

  it('paredão de 77 rejeições vira 1 cluster', () => {
    const eventos = Array.from({ length: 77 }, (_, i) => de(i + 1, 'rejeitado'));
    const blocos = agruparBlocos(eventos);
    expect(blocos).toHaveLength(1);
    expect(blocos[0].tipo === 'cluster' && blocos[0].itens.length).toBe(77);
  });
});

describe('resumoCluster', () => {
  it('conta o total e o breakdown por tipo', () => {
    const r = resumoCluster([de(1, 'aceito'), de(2, 'aceito'), de(3, 'rejeitado')]);
    expect(r).toContain('3 decisões de conferência');
    expect(r).toContain('2 aceitas');
    expect(r).toContain('1 rejeitadas');
  });

  it('usa singular para uma decisão', () => {
    expect(resumoCluster([de(1, 'editado')])).toContain('1 decisão de conferência');
  });
});
