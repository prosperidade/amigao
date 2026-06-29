/**
 * historicoBlocos — agrupa a timeline em MARCOS (visíveis) e CLUSTERS recolhidos
 * num bloco expansível.
 *
 * Princípio (pedido do André): cada seção mostra só o RESULTADO; o resto fica
 * oculto num histórico expansível. No Histórico de eventos isso vira:
 *   1. Decisões individuais do consultor (aceito/rejeitado/escolhido/editado),
 *      que enchem a timeline em sequência (ex.: 77 rejeições no caso 13), colapsam.
 *   2. Resultados que SE REPETEM (consolidação na base, aceite em lote): só o
 *      MAIS RECENTE fica visível; as ocorrências anteriores recolhem ("só fica o
 *      último resultado").
 * Os demais marcos (caso criado, extração, status, etapa, resumo) ficam sempre
 * visíveis. Lógica pura, testável — a UI vive em TimelineTab.
 */
import type { EventoKind, HistoricoEvento, TimelineEvent } from './historicoEventos';

// Decisões individuais do consultor na conferência (Ficha 01 / Fase 4) — sempre
// "ruído" que colapsa quando vem em sequência.
export const DECISAO_KINDS = new Set<EventoKind>(['aceito', 'rejeitado', 'escolhido', 'editado']);

// Resultados que se repetem: só o último de cada tipo fica visível; os anteriores
// viram ruído (recolhem no histórico). O botão que os gera ("Consolidar na base")
// é decisão de outra seção — não afeta esta regra de apresentação.
export const RESULTADO_RECORRENTE_KINDS = new Set<EventoKind>(['consolidado', 'lote']);

// Rótulo plural por tipo, para o resumo do bloco recolhido.
export const RUIDO_PLURAL: Record<string, string> = {
  aceito: 'aceitas', rejeitado: 'rejeitadas', escolhido: 'com fonte escolhida',
  editado: 'editadas', consolidado: 'consolidações anteriores', lote: 'aceites em lote anteriores',
};

export interface DescribedEvent { log: TimelineEvent; ev: HistoricoEvento }
export type Bloco =
  | { tipo: 'marco'; item: DescribedEvent }
  | { tipo: 'cluster'; itens: DescribedEvent[] };

/** id do evento mais recente (maior created_at; desempate por id) de cada tipo de
 * resultado recorrente — esses NÃO colapsam (são o "último resultado" visível). */
function idsUltimoResultado(eventos: DescribedEvent[]): Set<number> {
  const melhor = new Map<EventoKind, DescribedEvent>();
  for (const de of eventos) {
    if (!RESULTADO_RECORRENTE_KINDS.has(de.ev.kind)) continue;
    const atual = melhor.get(de.ev.kind);
    if (!atual || _maisRecente(de, atual)) melhor.set(de.ev.kind, de);
  }
  return new Set([...melhor.values()].map((de) => de.log.id));
}

function _maisRecente(a: DescribedEvent, b: DescribedEvent): boolean {
  const ta = Date.parse(a.log.created_at), tb = Date.parse(b.log.created_at);
  if (Number.isNaN(ta) || Number.isNaN(tb) || ta === tb) return a.log.id > b.log.id;
  return ta > tb;
}

/** True se o evento deve recolher no histórico: decisão de conferência, OU um
 * resultado recorrente que NÃO é o mais recente do seu tipo. */
function ehRuido(de: DescribedEvent, ultimos: Set<number>): boolean {
  if (DECISAO_KINDS.has(de.ev.kind)) return true;
  if (RESULTADO_RECORRENTE_KINDS.has(de.ev.kind)) return !ultimos.has(de.log.id);
  return false;
}

/** Agrupa runs contíguos de "ruído" num único bloco colapsável. Marcos (e o
 * último resultado de cada tipo recorrente) passam direto. Um run de 1 NÃO
 * colapsa (não vira paredão). */
export function agruparBlocos(eventos: DescribedEvent[]): Bloco[] {
  const ultimos = idsUltimoResultado(eventos);
  const blocos: Bloco[] = [];
  let buffer: DescribedEvent[] = [];
  const flush = () => {
    if (buffer.length === 0) return;
    if (buffer.length === 1) blocos.push({ tipo: 'marco', item: buffer[0] });
    else blocos.push({ tipo: 'cluster', itens: buffer });
    buffer = [];
  };
  for (const de of eventos) {
    if (ehRuido(de, ultimos)) {
      buffer.push(de);
    } else {
      flush();
      blocos.push({ tipo: 'marco', item: de });
    }
  }
  flush();
  return blocos;
}

/** Resumo textual de um cluster. Só decisões → "N decisões de conferência · …";
 * misto (com resultados anteriores) → "N eventos anteriores · …". */
export function resumoCluster(itens: DescribedEvent[]): string {
  const counts: Record<string, number> = {};
  for (const { ev } of itens) counts[ev.kind] = (counts[ev.kind] ?? 0) + 1;
  const partes = Object.entries(counts).map(([k, n]) => `${n} ${RUIDO_PLURAL[k] ?? k}`);
  const total = itens.length;
  const soDecisoes = itens.every(({ ev }) => DECISAO_KINDS.has(ev.kind));
  const cabeca = soDecisoes
    ? `${total} ${total === 1 ? 'decisão de conferência' : 'decisões de conferência'}`
    : `${total} ${total === 1 ? 'evento anterior' : 'eventos anteriores'}`;
  return `${cabeca} · ${partes.join(' · ')}`;
}
