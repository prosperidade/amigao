/**
 * Tipos do fechamento comercial (ADR-074) e do motor jurídico (ADR-073).
 *
 * Espelham o JSON de `app/api/v1/comercial.py` e `app/api/v1/motor_juridico.py`
 * — NÃO inventar campo nem renomear valor.
 */

export type EvidenciaTipo =
  | 'dispositivo'
  | 'fonte_versao'
  | 'observacao'
  | 'fonte_primaria'
  | 'conclusao'
  | 'documento'
  | 'avaliacao_regra'
  | 'ciencia_alerta'
  | 'execucao_motor'
  | 'rota'
  | 'rota_passo';

export interface EvidenciaRef {
  tipo: EvidenciaTipo;
  id: number;
  rotulo: string;
}

/** `GET /processes/{id}/evidencias/{tipo}/{id}` — o que está por trás do ID. */
export interface EvidenciaDetalhe {
  tipo: EvidenciaTipo;
  id: number;
  titulo: string;
  texto: string | null;
  texto_cortado: boolean;
  campos: { rotulo: string; valor: string }[];
  refs: EvidenciaRef[];
  documento_id: number | null;
}

export interface Afirmacao {
  id: string;
  texto: string;
  evidencias: EvidenciaRef[];
}

export interface Secao {
  chave: string;
  titulo: string;
  afirmacoes: Afirmacao[];
}

export type EstadoRevisao = 'proposta' | 'aprovada' | 'rejeitada';
export type EstadoAtualidade = 'vigente' | 'desatualizado' | 'superada';

export interface Atualidade {
  estado: EstadoAtualidade;
  motivos: string[];
}

interface Revisao {
  estado_revisao: EstadoRevisao;
  revisado_por_id: number | null;
  revisado_em: string | null;
  justificativa: string | null;
}

export type TipoRedacao = 'relatorio_preliminar' | 'especificacao_escopo';

export interface Redacao extends Revisao {
  id: number;
  tipo: TipoRedacao;
  versao: number;
  rota_id: number | null;
  execucao_motor_id: number | null;
  criado_por_id: number | null;
  created_at: string;
  superada_em: string | null;
  atualidade: Atualidade;
  conteudo: { secoes: Secao[]; limites?: string[] };
}

export interface VersaoResumo {
  id: number;
  versao: number;
  estado_revisao: EstadoRevisao;
  superada_em: string | null;
  created_at: string;
  tipo?: TipoRedacao;
  total?: string | null;
}

export interface RedacoesOut {
  relatorio_preliminar: Redacao | null;
  especificacao_escopo: Redacao | null;
  versoes: VersaoResumo[];
}

export interface OrcamentoItem {
  id: number;
  ordem: number;
  rota_passo_id: number;
  descricao: string;
  fundamento: { caminho?: string; rule_id?: string; dispositivo_id?: number; fonte_versao_id?: number } | null;
  metodo: { id: number; codigo: string; versao: number; nome: string };
  /** De onde veio o método: consultor → regra → padrão. */
  escolha: string;
  unidade: string;
  quantidade: string;
  valor_unitario: string;
  total: string;
  calculo: string | null;
}

export interface OrcamentoFora {
  rota_passo_id: number;
  titulo: string;
  motivo: string;
}

export interface OrcamentoRessalva {
  tipo: string;
  texto: string;
  conclusoes?: number[];
}

export interface Orcamento extends Revisao {
  id: number;
  versao: number;
  rota_id: number | null;
  escopo_id: number;
  total: string;
  fora: OrcamentoFora[];
  ressalvas: OrcamentoRessalva[];
  created_at: string;
  criado_por_id: number | null;
  superada_em: string | null;
  atualidade: Atualidade;
  itens: OrcamentoItem[];
}

export interface OrcamentoOut {
  orcamento: Orcamento | null;
  versoes: VersaoResumo[];
}

export interface MetodoOrcamento {
  id: number;
  codigo: string;
  versao: number;
  nome: string;
  unidade: 'hora' | 'fixo' | 'unidade';
  valor_unitario: string;
  quantidade_padrao: string;
  rule_ids: string[];
  padrao: boolean;
  ativo: boolean;
}

// ─── Motor jurídico ─────────────────────────────────────────────────────────

export type EstadoAvaliacao =
  | 'aplicavel_disparou'
  | 'aplicavel_nao_disparou'
  | 'nao_aplicavel'
  | 'indeterminado'
  | 'conflito'
  | 'erro_execucao';

export interface AvaliacaoLinha {
  avaliacao_id: number;
  rule_id: string;
  regra_versao_id: number;
  estado: EstadoAvaliacao;
  faltantes: string[];
  efeitos: { tipo?: string; [k: string]: unknown }[];
  fundamento: {
    fonte_versao_id: number | null;
    dispositivo_id: number | null;
    caminho: string | null;
    razao: string | null;
  };
  alerta_critico_sem_ciencia: boolean;
  /** Ciência vigente: a própria ou, com `herdada`, a de execução anterior de mesmo conteúdo (#289). */
  ciencia: { id: number; avaliacao_id: number; herdada: boolean } | null;
  detalhe_erro: string | null;
}

export interface Fato {
  valor: unknown;
  estado: string;
  origem?: Record<string, unknown>;
  revisao?: string;
}

export interface ExecucaoRelatorio {
  execucao_id: number;
  process_id: number;
  conjunto_id: number;
  conjunto_tenant_id: number | null;
  data_referencia: string;
  fatos: Record<string, Fato>;
  fatos_hash: string;
  contagem: Record<string, number>;
  disparadas: number;
  avaliacoes: AvaliacaoLinha[];
  alertas_sem_ciencia: number[];
}

// ─── Rótulos ────────────────────────────────────────────────────────────────

export const ESTADO_AVALIACAO_LABEL: Record<EstadoAvaliacao, string> = {
  aplicavel_disparou: 'Disparou',
  aplicavel_nao_disparou: 'Aplicável, não disparou',
  nao_aplicavel: 'Não aplicável',
  indeterminado: 'Indeterminada',
  conflito: 'Conflito entre regras',
  erro_execucao: 'Erro de execução',
};

export const EVIDENCIA_TIPO_LABEL: Record<EvidenciaTipo, string> = {
  dispositivo: 'dispositivo',
  fonte_versao: 'fonte normativa',
  observacao: 'observação',
  fonte_primaria: 'fonte primária',
  conclusao: 'conclusão',
  documento: 'documento',
  avaliacao_regra: 'avaliação',
  ciencia_alerta: 'ciência',
  execucao_motor: 'execução do motor',
  rota: 'rota',
  rota_passo: 'passo',
};

export const REVISAO_LABEL: Record<EstadoRevisao, string> = {
  proposta: 'Aguardando revisão',
  aprovada: 'Aprovado',
  rejeitada: 'Rejeitado',
};

export const ATUALIDADE_LABEL: Record<EstadoAtualidade, string> = {
  vigente: 'Atual',
  desatualizado: 'Desatualizado',
  superada: 'Superado',
};

export function reais(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'number' ? v : Number(v);
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
