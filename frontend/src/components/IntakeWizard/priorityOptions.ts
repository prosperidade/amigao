/**
 * Opções dos dois eixos INDEPENDENTES de prioridade (decisão Isis 2026-05-28).
 *
 * Urgência (4 níveis) e Valor Estratégico (3 níveis) são eixos separados —
 * NÃO se combinam num único índice. O nível "baixo" de Valor Estratégico não
 * tem critério escrito (Isis não definiu — dívida #29); o consultor decide livre.
 *
 * Constantes movidas de PriorityStep.tsx para um módulo próprio: um arquivo de
 * componente não pode exportar valores não-componente sem quebrar o Fast Refresh
 * (regra react-refresh/only-export-components).
 */

export const URGENCIA_OPTIONS = [
  { value: 'urgentissima', label: '🔴 Urgentíssima — prazo vencendo, embargo, auto de infração' },
  { value: 'alta', label: '🟠 Alta — banco, prazo de crédito, exigência com data' },
  { value: 'media', label: '🟡 Média — nas próximas semanas' },
  { value: 'baixa', label: '🟢 Baixa — pode aguardar' },
];

export const VALOR_ESTRATEGICO_OPTIONS = [
  { value: 'alto', label: '⭐ Alto — cliente/caso prioritário' },
  { value: 'medio', label: '◐ Médio' },
  { value: 'baixo', label: '○ Baixo — sem critério fixo (consultor decide)' },
];
