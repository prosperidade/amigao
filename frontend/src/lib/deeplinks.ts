/**
 * Deep-links entre telas do painel consultor.
 *
 * Mantém as URLs de navegação cruzada num só lugar (fora de arquivos de
 * componente, pra não quebrar o react-refresh) e testável isoladamente.
 */

/** Âncora do controle tri-state de contiguidade no Hub do Imóvel. */
export const CONTIGUIDADE_ANCHOR = 'contiguidade';

/** Hub do Imóvel, direto no controle onde se declara a contiguidade (item 4). */
export function contiguidadeHref(propertyId: number): string {
  return `/properties/${propertyId}#${CONTIGUIDADE_ANCHOR}`;
}
