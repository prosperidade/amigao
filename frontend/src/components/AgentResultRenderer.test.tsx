// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import AgentResultRenderer from './AgentResultRenderer';

describe('contraprova da auditoria Jobson', () => {
  it('deriva o resumo da matriz mesmo em resultado histórico contraditório', () => {
    render(<AgentResultRenderer agentName="auditor_imovel" result={{
      content: '0 divergência(s) detectada(s)',
      method: 'deterministic_tools',
      divergencias: [],
      matriz_inconsistencias: { linhas: [
        { item: 'sigef', label: 'SIGEF', situacao: 'atencao', acao_recomendada: 'Verificar aplicabilidade' },
      ] },
    }} />);
    expect(screen.queryByText('0 divergência(s) detectada(s)')).not.toBeInTheDocument();
    expect(screen.getByText(/1 ponto\(s\) para revisão/)).toBeInTheDocument();
    expect(screen.getByText('Há pontos para revisão na matriz abaixo.')).toBeInTheDocument();
    expect(screen.queryByText('Nenhuma divergência documental encontrada.')).not.toBeInTheDocument();
    expect(screen.getByText('Auditoria por regras determinísticas')).toBeInTheDocument();
  });
});
