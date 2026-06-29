import { describe, it, expect } from 'vitest';
import { agruparBlocos, resumoCluster, type DescribedEvent } from './historicoBlocos';
import type { EventoKind } from './historicoEventos';

/** Helper: cria um DescribedEvent mínimo. `min` controla o created_at (recência). */
function de(id: number, kind: EventoKind, min = 0): DescribedEvent {
  const created_at = `2026-06-29T12:${String(min).padStart(2, '0')}:00Z`;
  return { log: { id, action: 'x', created_at }, ev: { kind, titulo: `evento ${id}` } };
}

describe('agruparBlocos', () => {
  it('colapsa um run contíguo de decisões num único cluster', () => {
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
      de(3, 'criado'),
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

  it('resultado recorrente: só o MAIS RECENTE de cada tipo fica visível', () => {
    // 3 consolidações + 2 aceites-em-lote (ordem cronológica crescente via `min`).
    const blocos = agruparBlocos([
      de(1, 'consolidado', 1), de(2, 'lote', 2), de(3, 'consolidado', 3),
      de(4, 'lote', 4), de(5, 'consolidado', 5),
    ]);
    // anteriores (1,2,3) recolhem num cluster; ficam visíveis o último lote (4)
    // e o último consolidado (5).
    const marcoIds = blocos
      .filter((b) => b.tipo === 'marco')
      .map((b) => (b.tipo === 'marco' ? b.item.log.id : 0))
      .sort((a, z) => a - z);
    expect(marcoIds).toEqual([4, 5]);
    const cluster = blocos.find((b) => b.tipo === 'cluster');
    expect(cluster?.tipo === 'cluster' && cluster.itens.length).toBe(3);
  });

  it('uma única consolidação fica visível (não recolhe)', () => {
    const blocos = agruparBlocos([de(1, 'criado'), de(2, 'consolidado')]);
    expect(blocos.map((b) => b.tipo)).toEqual(['marco', 'marco']);
  });
});

describe('resumoCluster', () => {
  it('só decisões → "N decisões de conferência" + breakdown', () => {
    const r = resumoCluster([de(1, 'aceito'), de(2, 'aceito'), de(3, 'rejeitado')]);
    expect(r).toContain('3 decisões de conferência');
    expect(r).toContain('2 aceitas');
    expect(r).toContain('1 rejeitadas');
  });

  it('singular para uma decisão', () => {
    expect(resumoCluster([de(1, 'editado')])).toContain('1 decisão de conferência');
  });

  it('misto (com resultados anteriores) → "N eventos anteriores"', () => {
    const r = resumoCluster([de(1, 'rejeitado'), de(2, 'consolidado'), de(3, 'lote')]);
    expect(r).toContain('3 eventos anteriores');
    expect(r).toContain('1 consolidações anteriores');
    expect(r).toContain('1 aceites em lote anteriores');
  });
});
