/**
 * Regra de exibição da E3 como estação opcional — separada do componente.
 *
 * Mora fora do `.tsx` porque arquivo de componente que também exporta função ou
 * constante quebra o Fast Refresh (`react-refresh/only-export-components`): o
 * HMR não sabe se deve remontar a árvore ou só recarregar o módulo, e desiste.
 * A regra é pura e testável sozinha — este é o lugar dela.
 */

export const ETAPA_COLETA = 'coleta_documental';

/**
 * A faixa aparece quando o consultor olha a Coleta Documental e ela não é a
 * etapa corrente — pulada (o caso já passou) ou ainda não alcançada. Nos dois
 * casos a mensagem é verdadeira: a estação é opcional e está aberta.
 *
 * Quando a E3 É a etapa corrente, o caso está de fato coletando documentos e a
 * tela normal da etapa manda — não há por que chamá-la de opcional ali.
 */
export function deveExibirEstacaoOpcional(
  viewingStage: string | null,
  currentStage: string,
): boolean {
  return viewingStage === ETAPA_COLETA && currentStage !== ETAPA_COLETA;
}
