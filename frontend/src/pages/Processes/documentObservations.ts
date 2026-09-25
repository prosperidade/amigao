// Documento × observações: o texto é cortado nas fronteiras de todas as âncoras, e cada
// pedaço sabe quais observações o cobrem. Âncoras podem se sobrepor.

export interface ObservacaoConferencia {
  id: string;
  version: number;
  tipo: string | null;
  predicado: string | null;
  trecho: string | null;
  inicio: number | null;
  fim: number | null;
  conteudo: Record<string, unknown> | null;
  conhecimento: string | null;
  superada: boolean;
  desatualizada: boolean;
  // Dívida #281: a última leitura não reencontrou esta observação; fica até o consultor decidir.
  nao_reencontrada?: boolean;
}

export interface Segmento {
  inicio: number;
  fim: number;
  texto: string;
  observacoes: string[];
}

export function segmentar(texto: string, observacoes: ObservacaoConferencia[]): Segmento[] {
  const ancoradas = observacoes.filter(o => o.inicio !== null && o.fim !== null && o.inicio < o.fim);
  const cortes = new Set<number>([0, texto.length]);
  for (const o of ancoradas) {
    cortes.add(o.inicio as number);
    cortes.add(o.fim as number);
  }
  const pontos = [...cortes].filter(p => p >= 0 && p <= texto.length).sort((a, b) => a - b);
  const segmentos: Segmento[] = [];
  for (let i = 0; i < pontos.length - 1; i++) {
    const [inicio, fim] = [pontos[i], pontos[i + 1]];
    const cobrem = ancoradas.filter(o => (o.inicio as number) <= inicio && (o.fim as number) >= fim).map(o => o.id);
    segmentos.push({ inicio, fim, texto: texto.slice(inicio, fim), observacoes: cobrem });
  }
  return segmentos;
}

const OCULTOS = new Set(['trecho', 'posicao_inicio', 'posicao_fim', 'campos_sem_suporte']);

// Campos simples do conteúdo normalizado, na ordem proposta, para leitura da consultora.
export function camposLegiveis(conteudo: Record<string, unknown> | null): [string, string][] {
  if (!conteudo) return [];
  return Object.entries(conteudo)
    .filter(([chave, valor]) => !OCULTOS.has(chave) && valor !== null && valor !== '' &&
      !(Array.isArray(valor) && valor.length === 0))
    .map(([chave, valor]) => [chave.replace(/_/g, ' '),
      typeof valor === 'object' ? JSON.stringify(valor) : String(valor)]);
}
