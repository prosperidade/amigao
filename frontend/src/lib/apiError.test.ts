import { describe, it, expect } from 'vitest';
import { mensagemDeErro, clienteDuplicado } from './apiError';

/**
 * O caso que motivou o helper: o 409 de documento duplicado (ENT-002) devolve
 * `detail` como OBJETO, e o tratamento antigo (`detail || padrão`) jogaria o
 * objeto no estado de erro — React quebra ao renderizar objeto como filho.
 */
describe('mensagemDeErro', () => {
  it('usa o texto quando detail é string', () => {
    expect(mensagemDeErro({ response: { data: { detail: 'Cliente não encontrado' } } }, 'padrão'))
      .toBe('Cliente não encontrado');
  });

  it('extrai message quando detail é objeto (409 de duplicado)', () => {
    const erro = {
      response: {
        status: 409,
        data: {
          detail: {
            code: 'documento_ja_cadastrado',
            message: 'O documento 29.091.958/0001-17 já pertence ao cadastro #7 — ELODI.',
            client_id: 7,
          },
        },
      },
    };
    expect(mensagemDeErro(erro, 'padrão')).toContain('já pertence ao cadastro #7');
  });

  it('junta os problemas quando detail é lista (422 do Pydantic)', () => {
    const erro = {
      response: {
        data: {
          detail: [
            { loc: ['body', 'cpf_cnpj'], msg: 'CPF deve ter 11 dígitos e CNPJ 14' },
          ],
        },
      },
    };
    expect(mensagemDeErro(erro, 'padrão')).toBe('cpf_cnpj: CPF deve ter 11 dígitos e CNPJ 14');
  });

  it('cai no padrão quando não há detail legível', () => {
    expect(mensagemDeErro({ response: { data: {} } }, 'padrão')).toBe('padrão');
    expect(mensagemDeErro(undefined, 'padrão')).toBe('padrão');
    expect(mensagemDeErro({ response: { data: { detail: '   ' } } }, 'padrão')).toBe('padrão');
  });
});

describe('clienteDuplicado', () => {
  it('devolve o cadastro a reutilizar no 409 de documento', () => {
    const erro = {
      response: {
        data: {
          detail: {
            code: 'documento_ja_cadastrado',
            client_id: 7,
            full_name: 'ELODI',
            legal_name: 'ELODI Agropecuária Ltda.',
          },
        },
      },
    };
    expect(clienteDuplicado(erro)).toEqual({
      client_id: 7,
      full_name: 'ELODI',
      legal_name: 'ELODI Agropecuária Ltda.',
    });
  });

  it('devolve null para qualquer outro erro', () => {
    expect(clienteDuplicado({ response: { data: { detail: 'erro qualquer' } } })).toBeNull();
    expect(clienteDuplicado({ response: { data: { detail: { code: 'outro', client_id: 1 } } } })).toBeNull();
    expect(clienteDuplicado(undefined)).toBeNull();
  });
});
