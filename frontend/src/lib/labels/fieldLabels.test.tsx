// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import AgentResultRenderer from '@/components/AgentResultRenderer';
import { labelFor, humanizeValue, isMetaField, FIELD_LABELS } from './fieldLabels';

/**
 * Prova de que termos técnicos não vazam para a tela após a centralização de
 * rótulos (fix/ui-termos-tecnicos). Renderiza os renderers reais com payloads
 * que antes vazavam snake_case, JSON cru e [object Object].
 */

// Termos técnicos que NUNCA podem aparecer em texto visível ao usuário.
function assertNoTechnicalLeak(text: string) {
  expect(text).not.toContain('[object Object]');
  // sem JSON cru (chaves entre aspas seguidas de dois-pontos)
  expect(text).not.toMatch(/"\w+"\s*:/);
  // sem snake_case visível
  expect(text).not.toMatch(/[a-z]+_[a-z]+/);
}

describe('labelFor / humanizeValue (fonte única de rótulos)', () => {
  it('traduz campos de matrícula e RG para PT-BR', () => {
    expect(labelFor('area_hectares')).toBe('Área (ha)');
    expect(labelFor('proprietario_cpf_cnpj')).toBe('CPF / CNPJ');
    expect(labelFor('numero_matricula')).toBe('Número da matrícula');
    expect(labelFor('orgao_expedidor')).toBe('Órgão expedidor');
    expect(labelFor('data_nascimento')).toBe('Data de nascimento');
  });

  it('fallback humaniza chave desconhecida sem deixar underscore cru', () => {
    const out = labelFor('campo_totalmente_novo');
    expect(out).toBe('Campo totalmente novo');
    expect(out).not.toContain('_');
  });

  it('isMetaField oculta confidence, *_raw, prefixo _ e chaves internas', () => {
    expect(isMetaField('confidence')).toBe(true);
    expect(isMetaField('findings_raw')).toBe(true);
    expect(isMetaField('extracted_raw')).toBe(true);
    expect(isMetaField('_parse_error')).toBe(true);
    expect(isMetaField('chain_trace_id')).toBe(true);
    expect(isMetaField('nome')).toBe(false);
  });

  it('humanizeValue nunca produz JSON cru nem [object Object]', () => {
    expect(humanizeValue({ proprietario_nome: 'João', cpf: '123' })).toBe(
      'Proprietário: João · CPF: 123',
    );
    expect(humanizeValue(['APP', 'Reserva Legal'])).toBe('APP, Reserva Legal');
    expect(humanizeValue([{ a: 1 }, { b: 2 }])).toBe('2 itens');
    expect(humanizeValue(null)).toBe('—');
    // o caso que antes vazava:
    expect(humanizeValue({ x: 1 })).not.toContain('[object Object]');
    expect(humanizeValue({ x: 1 })).not.toContain('{');
  });

  it('todo rótulo do dicionário é PT-BR legível sem underscore', () => {
    for (const label of Object.values(FIELD_LABELS)) {
      expect(label).not.toMatch(/[a-z]_[a-z]/);
    }
  });
});

describe('AgentResultRenderer — extrator (matrícula)', () => {
  it('mostra campos com rótulo PT-BR, sem termo técnico nem meta', () => {
    const { container } = render(
      <AgentResultRenderer
        agentName="extrator"
        result={{
          doc_type: 'matricula',
          fields_count: 4,
          extracted_fields: {
            proprietario_nome: 'Maria Silva',
            numero_matricula: '6253',
            area_hectares: '58,7654',
            denominacao_imovel: 'Fazenda Boa Vista',
            confidence: 0.92, // meta — deve sumir
            descricao_limites_raw: 'lixo cru', // *_raw — deve sumir
          },
        }}
      />,
    );
    const text = container.textContent ?? '';
    expect(screen.getByText('Proprietário')).toBeInTheDocument();
    expect(screen.getByText('Número da matrícula')).toBeInTheDocument();
    expect(screen.getByText('Área (ha)')).toBeInTheDocument();
    expect(screen.getByText('Denominação do imóvel')).toBeInTheDocument();
    expect(text).toContain('Maria Silva');
    expect(text).toContain('58,7654');
    // meta ocultos
    expect(text).not.toContain('0.92');
    expect(text).not.toContain('lixo cru');
    assertNoTechnicalLeak(text);
  });
});

describe('AgentResultRenderer — extrator (RG/CPF)', () => {
  it('humaniza campos de identidade', () => {
    const { container } = render(
      <AgentResultRenderer
        agentName="extrator"
        result={{
          doc_type: 'rg',
          extracted_fields: {
            nome: 'José Souza',
            nome_social: 'Zé',
            data_nascimento: '1980-05-10',
            orgao_expedidor: 'SSP/GO',
            naturalidade: 'Goiânia',
          },
        }}
      />,
    );
    const text = container.textContent ?? '';
    expect(screen.getByText('Nome social')).toBeInTheDocument();
    expect(screen.getByText('Data de nascimento')).toBeInTheDocument();
    expect(screen.getByText('Órgão expedidor')).toBeInTheDocument();
    assertNoTechnicalLeak(text);
  });
});

describe('AgentResultRenderer — GenericResult (diagnóstico/auditor sem renderer dedicado)', () => {
  it('renderiza objetos/arrays sem JSON cru nem [object Object], oculta meta', () => {
    const { container } = render(
      <AgentResultRenderer
        agentName="agente_desconhecido"
        result={{
          resumo_geral: 'Imóvel com pendências de APP.',
          itens_verificados: ['APP', 'Reserva Legal', 'CAR'],
          detalhe_tecnico: { area_app: '12,5', area_rl: '40,0' },
          chain_trace_id: 'abc-123', // meta
          findings_raw: { x: 1 }, // *_raw meta
        }}
      />,
    );
    const text = container.textContent ?? '';
    expect(text).toContain('Imóvel com pendências de APP.');
    expect(screen.getByText('Área de APP (ha)')).toBeInTheDocument();
    expect(text).not.toContain('abc-123');
    assertNoTechnicalLeak(text);
  });
});
