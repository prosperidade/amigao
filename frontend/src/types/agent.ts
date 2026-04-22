/** Tipos do sistema de agentes IA */

export interface AgentInfo {
  name: string;
  description: string;
}

export interface AgentRunRequest {
  agent_name: string;
  process_id?: number | null;
  metadata: Record<string, unknown>;
}

export interface AgentRunResponse {
  success: boolean;
  data: Record<string, unknown>;
  confidence: 'high' | 'medium' | 'low';
  ai_job_id: number | null;
  suggestions: string[];
  requires_review: boolean;
  agent_name: string;
  duration_ms: number;
  error: string | null;
}

export interface ChainRunRequest {
  chain_name: string;
  process_id?: number | null;
  metadata: Record<string, unknown>;
  stop_on_review?: boolean;
}

export interface ChainRunResponse {
  chain_name: string;
  steps: AgentRunResponse[];
  completed: boolean;
  stopped_for_review: boolean;
  total_duration_ms: number;
}

export interface AsyncTaskResponse {
  task_id: string;
  status: string;
  agent_name?: string;
  chain_name?: string;
  process_id?: number | null;
}

export interface AIJob {
  id: number;
  entity_type: string;
  entity_id: number;
  job_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  agent_name: string | null;
  model_used: string | null;
  provider: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  duration_ms: number | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export const AGENT_LABELS: Record<string, string> = {
  atendimento: 'Atendimento',
  extrator: 'Extrator de Documentos',
  diagnostico: 'Diagnóstico Ambiental',
  legislacao: 'Enquadramento Regulatório',
  redator: 'Redator de Documentos',
  orcamento: 'Orçamento',
  financeiro: 'Análise Financeira',
  acompanhamento: 'Acompanhamento',
  vigia: 'Monitoramento',
  marketing: 'Marketing',
};

export const CHAIN_LABELS: Record<string, string> = {
  intake: 'Classificação de Demanda',
  diagnostico_completo: 'Diagnóstico Completo',
  gerar_proposta: 'Gerar Proposta',
  gerar_documento: 'Gerar Documento',
  analise_regulatoria: 'Análise Regulatória',
  enquadramento_regulatorio: 'Enquadramento Regulatório',
  analise_financeira: 'Análise Financeira',
  monitoramento: 'Monitoramento',
  marketing_content: 'Conteúdo de Marketing',
};

// Status de execução (label + cls para badge). Sócia vê o estado em PT, não em inglês.
export const STATUS_LABELS: Record<string, string> = {
  pending: 'Aguardando',
  running: 'Em execução',
  completed: 'Concluída',
  failed: 'Falhou',
};

// Confiança do resultado em PT-BR.
export const CONFIDENCE_LABELS: Record<string, string> = {
  high: 'Alta',
  medium: 'Média',
  low: 'Baixa',
};

export const CONFIDENCE_STYLES: Record<string, string> = {
  high: 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/30',
  medium: 'bg-yellow-50 dark:bg-yellow-500/10 text-yellow-700 dark:text-yellow-300 border-yellow-200 dark:border-yellow-500/30',
  low: 'bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-300 border-red-200 dark:border-red-500/30',
};
