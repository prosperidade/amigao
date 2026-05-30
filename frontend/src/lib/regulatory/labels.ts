/**
 * Labels pt-BR e classes Tailwind dos enums regulatórios.
 *
 * Convenções:
 * - Severidade: `informativo`/`atencao` em tons neutros; `alto` em laranja; `critico`
 *   em vermelho. Reserva o tom forte só pra crítico — não afoga a tela em vermelho.
 *   Inspirado em `DashboardRegente.tsx:71` e `ProcessDetailTypes.ts` (URGENCY_CONFIG).
 * - Decisão: labels acordados no PROMPT_9 (5 botões da P4 — camada 2 do Princípio 1).
 * - Status do achado: vocabulário do consultor (suspeita = "ainda não olhei",
 *   confirmada/descartada = adjudicação, resolvida = sanou no mundo, ignorada =
 *   optei por não tratar).
 */

import type {
  DecisaoConsultor,
  RegulatoryFamilia,
  RegulatoryIssueSeverity,
  StatusAchado,
  StatusSaneamento,
} from './types';

export const SEVERITY_LABEL: Record<RegulatoryIssueSeverity, string> = {
  informativo: 'Informativo',
  atencao: 'Atenção',
  alto: 'Alto',
  critico: 'Crítico',
};

export const SEVERITY_CLS: Record<RegulatoryIssueSeverity, string> = {
  informativo: 'bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-slate-300 border-slate-200 dark:border-zinc-700',
  atencao: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 border-amber-200 dark:border-amber-500/30',
  alto: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300 border-orange-200 dark:border-orange-500/30',
  critico: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 border-red-200 dark:border-red-500/30',
};

// Ordem decrescente — para sort de cards (críticos no topo).
export const SEVERITY_ORDER: Record<RegulatoryIssueSeverity, number> = {
  critico: 0,
  alto: 1,
  atencao: 2,
  informativo: 3,
};

export const FAMILIA_LABEL: Record<RegulatoryFamilia, string> = {
  identificacao: 'Identificação',
  titularidade: 'Titularidade',
  area: 'Área',
  geoespacial: 'Geoespacial',
  geo_incra: 'Geo / INCRA',
  car: 'CAR',
  ambiental: 'Ambiental',
  fiscal: 'Fiscal',
  restricao_risco: 'Restrição / Risco',
  licenciamento: 'Licenciamento',
  validade_documental: 'Validade documental',
};

export const STATUS_ACHADO_LABEL: Record<StatusAchado, string> = {
  suspeita: 'Suspeita',
  confirmada: 'Confirmada',
  descartada: 'Descartada',
  resolvida: 'Resolvida',
  ignorada: 'Ignorada',
};

export const STATUS_ACHADO_HINT: Record<StatusAchado, string> = {
  suspeita: 'Auditor emitiu; consultor ainda não adjudicou',
  confirmada: 'Divergência real, confirmada pelo consultor',
  descartada: 'Auditor errou; não é divergência real',
  resolvida: 'Divergência foi sanada no mundo',
  ignorada: 'Consultor optou por não tratar',
};

export const STATUS_SANEAMENTO_LABEL: Record<StatusSaneamento, string> = {
  pendente: 'Pendente',
  em_validacao: 'Em validação',
  saneado: 'Saneado',
  descartado: 'Descartado',
  nao_aplicavel: 'Não aplicável',
};

export const DECISAO_LABEL: Record<DecisaoConsultor, string> = {
  corrigir_antes: 'Corrigir antes de prosseguir',
  seguir_com_ressalva: 'Seguir com ressalva',
  solicitar_doc: 'Solicitar documento',
  fora_escopo: 'Fora do escopo deste trabalho',
  ignorar_justificado: 'Ignorar (justificado)',
};

export const DECISAO_HINT: Record<DecisaoConsultor, string> = {
  corrigir_antes: 'Corrige antes de protocolar',
  seguir_com_ressalva: 'Segue mesmo com problema, registra a ressalva',
  solicitar_doc: 'Exige documento adicional antes de decidir',
  fora_escopo: 'Alerta existe mas fora do contratado (exige justificativa)',
  ignorar_justificado: 'Ignora intencionalmente (exige justificativa)',
};
