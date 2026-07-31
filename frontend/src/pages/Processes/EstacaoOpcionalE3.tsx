/**
 * E3 (Coleta Documental) como ESTAÇÃO OPCIONAL — validação da Isis, 30/07.
 *
 * O salto E2→E4 é DESIGN (ADR-019): terminada a E2, se não há documento
 * essencial pendente o caso vai direto ao Diagnóstico Técnico. Isso continua
 * exatamente como está — este componente não toca a máquina de etapas.
 *
 * O que muda é que a E3 **nunca fica inalcançável**. Antes, clicar na etapa
 * pulada abria uma estação vazia, sem explicação: parecia um degrau perdido. Ela
 * não é. É a porta de entrada do material que a consultora produz DEPOIS —
 * relatórios, pareceres, análises dela — e a expectativa que ela declarou no
 * teste é poder reentrar ali a qualquer momento.
 *
 * Conecta com o item 7 da mesma validação: documento anexado depois passa a
 * entrar nas leituras seguintes da IA, com fonte. Sem isso, a reentrada seria
 * um arquivo morto no caso.
 */

interface Props {
  /** Etapa que o consultor está visualizando pelo stepper (null = a atual). */
  viewingStage: string | null;
  /** Macroetapa corrente do processo. */
  currentStage: string;
  /** Leva ao upload à mão (aba Documentos). */
  onAnexar: () => void;
}

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

export default function EstacaoOpcionalE3({ viewingStage, currentStage, onAnexar }: Props) {
  if (!deveExibirEstacaoOpcional(viewingStage, currentStage)) return null;

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-sky-800 dark:text-sky-300 bg-sky-50 dark:bg-sky-500/10 border border-sky-200 dark:border-sky-500/30 rounded-lg px-3 py-2">
      <span className="min-w-0">
        <strong>Etapa opcional</strong> — adicione aqui relatórios e análises suas a
        qualquer momento. Documento anexado depois entra nas próximas leituras da IA.
      </span>
      <button
        type="button"
        onClick={onAnexar}
        className="ml-auto shrink-0 px-2.5 py-1 rounded-lg bg-sky-600 text-white hover:bg-sky-700 transition-colors"
      >
        Anexar documento
      </button>
    </div>
  );
}
