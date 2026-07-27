import { describe, it, expect } from 'vitest';
import {
  DOC_TYPE_NAO_CLASSIFICADO,
  docTypeLabel,
  fonteTipoLabel,
  isDocTypeNaoClassificado,
  origemDadoLabel,
} from './docLabels';

/**
 * REGRA PERMANENTE DA CASA (26/07): termo interno de sistema NUNCA renderiza cru
 * na UI do consultor. Estes testes travam os três dicionários adicionados —
 * qualquer chave nova que escape do mapa cai num rótulo humano, nunca no
 * snake_case do banco.
 */
describe('docLabels — nenhum termo técnico chega à tela', () => {
  it('traduz os tipos de documento reais do caso 15', () => {
    expect(docTypeLabel('auto_infracao')).toBe('Auto de infração');
    expect(docTypeLabel('certidao_embargo')).toBe('Certidão de embargo');
    expect(docTypeLabel('rg_cpf')).toBe('Documento de identidade');
    expect(docTypeLabel('matricula')).toBe('Certidão de matrícula');
  });

  it('RAT aparece como análise HISTÓRICA do CAR (Ficha 08 §2)', () => {
    expect(docTypeLabel('rat')).toContain('histórica');
    expect(docTypeLabel('rat')).not.toBe('CAR');
  });

  it('tipo nulo/desconhecido é nomeado, não escondido nem cru', () => {
    expect(docTypeLabel(null)).toBe(DOC_TYPE_NAO_CLASSIFICADO);
    expect(docTypeLabel('')).toBe(DOC_TYPE_NAO_CLASSIFICADO);
    expect(docTypeLabel('tipo_que_nao_existe')).toBe(DOC_TYPE_NAO_CLASSIFICADO);
    expect(isDocTypeNaoClassificado('tipo_que_nao_existe')).toBe(true);
    expect(isDocTypeNaoClassificado('matricula')).toBe(false);
  });

  it('nenhum rótulo de documento contém snake_case', () => {
    const chaves = ['auto_infracao', 'certidao_embargo', 'rg_cpf', 'cpf_cnpj',
      'memorial_descritivo', 'planta_topografica', null, 'inexistente'];
    for (const k of chaves) {
      expect(docTypeLabel(k)).not.toMatch(/_/);
    }
  });

  it('traduz tipo de fonte e origem do dado', () => {
    expect(fonteTipoLabel('atendimento')).toBe('Relato do cliente');
    expect(fonteTipoLabel('auditor')).toBe('Verificação automática');
    expect(fonteTipoLabel('inexistente')).toBe('Fonte');
    expect(origemDadoLabel('human_validated')).toBe('conferido por você');
    expect(origemDadoLabel('derived_matricula')).toBe('derivado da matrícula');
    expect(origemDadoLabel(null)).toBe('—');
  });

  it('origem desconhecida degrada sem snake_case', () => {
    expect(origemDadoLabel('coisa_nova_do_backend')).toBe('coisa nova do backend');
  });
});
