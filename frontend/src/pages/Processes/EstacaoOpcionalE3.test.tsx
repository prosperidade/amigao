// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import EstacaoOpcionalE3, { deveExibirEstacaoOpcional } from './EstacaoOpcionalE3';

/**
 * Item 12 da validação da Isis (30/07) — "E3 como estação opcional".
 *
 * O salto E2→E4 é design (ADR-019) e continua. O que ela pediu é que a etapa
 * pulada nunca fique inalcançável: ao abri-la, dizer que é opcional e oferecer o
 * upload à mão, com reentrada a qualquer momento.
 */
describe('E3 — estação opcional (validação Isis 30/07, item 12)', () => {
  it('aparece quando o caso PULOU a coleta e está adiante (E4)', () => {
    expect(deveExibirEstacaoOpcional('coleta_documental', 'diagnostico_tecnico')).toBe(true);
  });

  it('aparece também quando o caso ainda não chegou lá (E1)', () => {
    // A frase continua verdadeira: a estação está aberta a qualquer momento.
    expect(deveExibirEstacaoOpcional('coleta_documental', 'entrada_demanda')).toBe(true);
  });

  it('NÃO aparece quando a coleta é a etapa corrente', () => {
    // Ali o caso está de fato coletando — a tela normal da etapa manda.
    expect(deveExibirEstacaoOpcional('coleta_documental', 'coleta_documental')).toBe(false);
  });

  it('NÃO aparece ao visualizar outra etapa', () => {
    expect(deveExibirEstacaoOpcional('caminho_regulatorio', 'diagnostico_tecnico')).toBe(false);
    expect(deveExibirEstacaoOpcional(null, 'diagnostico_tecnico')).toBe(false);
  });

  it('diz a frase que ela declarou no teste e oferece o upload à mão', () => {
    render(
      <EstacaoOpcionalE3
        viewingStage="coleta_documental"
        currentStage="diagnostico_tecnico"
        onAnexar={() => {}}
      />,
    );
    expect(screen.getByText(/etapa opcional/i)).toBeInTheDocument();
    expect(
      screen.getByText(/adicione aqui relatórios e análises suas a qualquer momento/i),
    ).toBeInTheDocument();
    // Conecta com o item 7: anexar depois não é arquivo morto.
    expect(screen.getByText(/entra nas próximas leituras da IA/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /anexar documento/i })).toBeInTheDocument();
  });

  it('o botão leva ao caminho de anexar (reentrada a qualquer momento)', async () => {
    const onAnexar = vi.fn();
    render(
      <EstacaoOpcionalE3
        viewingStage="coleta_documental"
        currentStage="orcamento_negociacao"
        onAnexar={onAnexar}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /anexar documento/i }));
    expect(onAnexar).toHaveBeenCalledOnce();
  });

  it('não renderiza nada quando não se aplica', () => {
    const { container } = render(
      <EstacaoOpcionalE3
        viewingStage="coleta_documental"
        currentStage="coleta_documental"
        onAnexar={() => {}}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
