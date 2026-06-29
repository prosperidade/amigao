/**
 * historicoBlocos — agrupa a timeline em MARCOS (visíveis) e CLUSTERS de decisões
 * de conferência (recolhidos num bloco expansível).
 *
 * Princípio (pedido do André): cada seção mostra só o RESULTADO; o resto fica
 * oculto num histórico expansível. No Histórico de eventos isso vira: as decisões
 * individuais do consultor (aceito/rejeitado/escolhido/editado), que enchem a
 * timeline em sequência (ex.: 77 rejeições no caso 13), colapsam num único
 * bloco-resumo; os marcos (caso criado, extração, consolidação, status, etapa,
 * resumo) ficam sempre visíveis. Lógica pura, testável — a UI vive em TimelineTab.
 */
import type { EventoKind, HistoricoEvento, TimelineEvent } from './historicoEventos';

// Decisões individuais do consultor na conferência (Ficha 01 / Fase 4) — o "ruído"
// que colapsa quando vem em sequência.
export const DECISAO_KINDS = new Set<EventoKind>(['aceito', 'rejeitado', 'escolhido', 'editado']);

// Rótulo plural por tipo de decisão, para o resumo do bloco colapsado.
export const DECISAO_PLURAL: Record<string, string> = {
  aceito: 'aceitas', rejeitado: 'rejeitadas', escolhido: 'com fonte escolhida', editado: 'editadas',
};

export interface DescribedEvent { log: TimelineEvent; ev: HistoricoEvento }
export type Bloco =
  | { tipo: 'marco'; item: DescribedEvent }
  | { tipo: 'cluster'; itens: DescribedEvent[] };

/** Agrupa runs contíguos de decisões de conferência num único bloco colapsável.
 * Marcos passam direto. Um run de 1 decisão NÃO colapsa (não vira paredão). */
export function agruparBlocos(eventos: DescribedEvent[]): Bloco[] {
  const blocos: Bloco[] = [];
  let buffer: DescribedEvent[] = [];
  const flush = () => {
    if (buffer.length === 0) return;
    if (buffer.length === 1) blocos.push({ tipo: 'marco', item: buffer[0] });
    else blocos.push({ tipo: 'cluster', itens: buffer });
    buffer = [];
  };
  for (const de of eventos) {
    if (DECISAO_KINDS.has(de.ev.kind)) {
      buffer.push(de);
    } else {
      flush();
      blocos.push({ tipo: 'marco', item: de });
    }
  }
  flush();
  return blocos;
}

/** Resumo textual de um cluster: "32 decisões de conferência · 29 aceitas · 3 rejeitadas". */
export function resumoCluster(itens: DescribedEvent[]): string {
  const counts: Record<string, number> = {};
  for (const { ev } of itens) counts[ev.kind] = (counts[ev.kind] ?? 0) + 1;
  const partes = Object.entries(counts).map(([k, n]) => `${n} ${DECISAO_PLURAL[k] ?? k}`);
  const total = itens.length;
  return `${total} ${total === 1 ? 'decisão de conferência' : 'decisões de conferência'} · ${partes.join(' · ')}`;
}
