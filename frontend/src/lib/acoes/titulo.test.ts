import { describe, it, expect } from 'vitest';
import { humanizeAcaoTitulo } from './titulo';
import type { Acao } from './types';

function makeAcao(over: Partial<Acao>): Acao {
  return {
    id: 1,
    process_id: 1,
    titulo: '',
    descricao: null,
    origem: 'manual',
    origem_descricao: null,
    origem_fontes: [],
    vinculo_passivo: null,
    responsavel_id: null,
    prazo: null,
    prioridade: 'media',
    status: 'a_fazer',
    tipo_triagem: 'pendente',
    created_by_user_id: null,
    concluida_at: null,
    created_at: null,
    updated_at: null,
    ...over,
  };
}

describe('humanizeAcaoTitulo (item 2 — título legível por padrão)', () => {
  it('reescreve divergência de consolidação em instrução com rótulo + valores', () => {
    const acao = makeAcao({
      titulo: 'Resolver divergência de total_area_ha (matrícula 4698)',
      origem: 'diagnostico',
      origem_fontes: [
        { tipo: 'documento', descricao: 'CCIR', valor: '349,90' },
        { tipo: 'documento', descricao: 'SIGEF', valor: '350,00' },
      ],
    });
    expect(humanizeAcaoTitulo(acao)).toBe(
      'Padronizar Área total (ha) (matrícula 4698): CCIR: "349,90" vs SIGEF: "350,00"',
    );
  });

  it('reescreve divergência sem matrícula e usa o rótulo PT-BR do campo', () => {
    const acao = makeAcao({
      titulo: 'Resolver divergência de denominacao',
      origem_fontes: [{ tipo: 'documento', sem_fonte: true }],
    });
    // sem valores utilizáveis → só a instrução com o rótulo, sem comparação
    expect(humanizeAcaoTitulo(acao)).toBe('Padronizar Denominação do imóvel');
  });

  it('torna a ação de oficialização imperativa', () => {
    const acao = makeAcao({
      titulo: 'Atualização de arquivos oficiais — Nº SIGEF (certificação)',
    });
    expect(humanizeAcaoTitulo(acao)).toBe('Atualizar nos arquivos oficiais — Nº SIGEF (certificação)');
  });

  it('deixa passar título manual/já-editado intacto (idempotente)', () => {
    const manual = makeAcao({ titulo: 'Ligar para o cartório de Rio Verde' });
    expect(humanizeAcaoTitulo(manual)).toBe('Ligar para o cartório de Rio Verde');

    // aplicar de novo sobre a saída não muda nada (não casa padrão de máquina)
    const jaLegivel = makeAcao({ titulo: 'Padronizar Área total (ha) (matrícula 4698): CCIR: "1" vs SIGEF: "2"' });
    expect(humanizeAcaoTitulo(jaLegivel)).toBe(jaLegivel.titulo);
  });
});
