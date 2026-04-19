/** Tipos para o Quadro de Ações (kanban por macroetapa). */

export type Macroetapa =
  | 'entrada_demanda'
  | 'diagnostico_preliminar'
  | 'coleta_documental'
  | 'diagnostico_tecnico'
  | 'caminho_regulatorio'
  | 'orcamento_negociacao'
  | 'contrato_formalizacao';

export interface KanbanProcessCard {
  id: number;
  title: string;
  client_name: string | null;
  property_name: string | null;
  demand_type: string | null;
  urgency: string | null;
  priority: string | null;
  macroetapa: string | null;
  macroetapa_label: string | null;
  macroetapa_completion_pct: number;
  responsible_user_name: string | null;
  next_action: string | null;
  has_alerts: boolean;
  created_at: string | null;

  // Regente Cam1 — Gate de prontidão (CAM1-011)
  entry_type: string | null;
  has_minimal_base: boolean;
  has_complementary_base: boolean;
  missing_docs_count: number;

  // Regente Cam3 — Estado formal da etapa (CAM3FT-004)
  macroetapa_state: string | null;
  blockers: string[];
}

export type MacroetapaState =
  | 'nao_iniciada'
  | 'em_andamento'
  | 'aguardando_input'
  | 'aguardando_validacao'
  | 'travada'
  | 'pronta_para_avancar'
  | 'concluida';

export const MACROETAPA_STATE_BADGE: Record<string, { label: string; cls: string }> = {
  nao_iniciada:           { label: 'Não iniciada', cls: 'bg-gray-100 text-gray-600 dark:bg-zinc-800 dark:text-gray-400' },
  em_andamento:           { label: 'Em andamento', cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' },
  aguardando_input:       { label: 'Aguardando input', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  aguardando_validacao:   { label: 'Aguardando validação', cls: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300' },
  travada:                { label: 'Travada', cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' },
  pronta_para_avancar:    { label: 'Pronta p/ avançar', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
  concluida:              { label: 'Concluída', cls: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200' },
};

export interface KanbanColumn {
  macroetapa: string;
  label: string;
  count: number;
  blocked_count: number;
  ready_to_advance_count: number;
  cards: KanbanProcessCard[];
}

export interface KanbanResponse {
  columns: KanbanColumn[];
  total_active: number;
}

export interface ActionItem {
  id: string;
  label: string;
  completed: boolean;
  completed_at: string | null;
  agent_suggestion: string | null;
}

export interface MacroetapaStep {
  macroetapa: string;
  label: string;
  order: number;
  status: 'pending' | 'active' | 'completed';
  completion_pct: number;
  actions: ActionItem[];
  agent_chain: string | null;
}

export interface MacroetapaStatusResponse {
  current_macroetapa: string | null;
  current_label: string | null;
  current_index: number;
  total_steps: number;
  next_action: string | null;
  steps: MacroetapaStep[];
}

export interface KanbanInsight {
  gargalo_macroetapa: string | null;
  gargalo_label: string | null;
  gargalo_count: number;
  pendencias_criticas: number;
  prontos_para_avancar: number;
  mensagem: string;
  distribuicao: { macroetapa: string; label: string; count: number }[];
}

export const MACROETAPA_LABELS: Record<string, string> = {
  entrada_demanda: 'Entrada da Demanda',
  diagnostico_preliminar: 'Diagnóstico Preliminar',
  coleta_documental: 'Coleta Documental',
  diagnostico_tecnico: 'Diagnóstico Técnico',
  caminho_regulatorio: 'Caminho Regulatório',
  orcamento_negociacao: 'Orçamento e Negociação',
  contrato_formalizacao: 'Contrato e Formalização',
};

export const MACROETAPA_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  entrada_demanda:        { bg: 'bg-slate-50',   border: 'border-slate-200',  text: 'text-slate-700' },
  diagnostico_preliminar: { bg: 'bg-blue-50',    border: 'border-blue-200',   text: 'text-blue-700' },
  coleta_documental:      { bg: 'bg-amber-50',   border: 'border-amber-200',  text: 'text-amber-700' },
  diagnostico_tecnico:    { bg: 'bg-indigo-50',  border: 'border-indigo-200', text: 'text-indigo-700' },
  caminho_regulatorio:    { bg: 'bg-purple-50',  border: 'border-purple-200', text: 'text-purple-700' },
  orcamento_negociacao:   { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700' },
  contrato_formalizacao:  { bg: 'bg-green-50',   border: 'border-green-200',  text: 'text-green-700' },
};

export const URGENCY_BADGES: Record<string, string> = {
  critica: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  alta:    'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  media:   'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  baixa:   'bg-gray-100 text-gray-600 dark:bg-zinc-800 dark:text-gray-400',
};

export const DEMAND_TYPE_LABELS: Record<string, string> = {
  car: 'CAR',
  retificacao_car: 'Retificação CAR',
  licenciamento: 'Licenciamento',
  regularizacao_fundiaria: 'Regularização Fundiária',
  outorga: 'Outorga',
  defesa: 'Defesa',
  compensacao: 'Compensação',
  exigencia_bancaria: 'Exigência Bancária',
  prad: 'PRAD',
  misto: 'Misto',
  nao_identificado: 'Não Identificado',
};
