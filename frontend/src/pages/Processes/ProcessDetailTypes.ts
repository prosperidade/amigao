/**
 * ProcessDetail — Shared types and constants
 */
import {
  Stethoscope, LayoutGrid, Briefcase, ListChecks,
  FolderOpen, CalendarDays, Bot, Scale, PackageCheck,
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Process {
  id: number;
  title: string;
  description: string;
  client_id: number;
  property_id: number | null;
  status: string;
  priority: string;
  urgency: string;
  process_type: string;
  demand_type: string | null;
  macroetapa: string | null;   // ver Process schema do backend; usado p/ stepper
  intake_source: string | null;
  initial_diagnosis: string | null;
  suggested_checklist_template: string | null;
  intake_notes: string | null;
  destination_agency: string | null;
  external_protocol_number: string | null;
  created_at: string;
  due_date: string | null;
  responsible_user_id: number | null;
}

export interface Task {
  id: number;
  title: string;
  status: string;
  allowed_transitions?: string[];
}

export interface Document {
  id: number;
  filename: string;
  original_file_name?: string;
  file_size_bytes: number;
  document_type?: string;
  created_at: string;
}

export interface TimelineEntry {
  id: number;
  action: string;
  details?: string;
  old_value?: string;
  new_value?: string;
  created_at: string;
}

// ─── Constants ─────────────────────────────────────────────────────────────────

export const STATUS_CONFIG: Record<string, { label: string; dot: string; badge: string }> = {
  lead:             { label: 'Lead',              dot: 'bg-gray-400',     badge: 'text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-500/10 border-gray-300 dark:border-gray-500/20' },
  triagem:          { label: 'Triagem',           dot: 'bg-blue-400',     badge: 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20' },
  diagnostico:      { label: 'Diagn\u00f3stico',       dot: 'bg-indigo-400',   badge: 'text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/10 border-indigo-200 dark:border-indigo-500/20' },
  planejamento:     { label: 'Planejamento',      dot: 'bg-purple-400',   badge: 'text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-500/10 border-purple-200 dark:border-purple-500/20' },
  execucao:         { label: 'Execu\u00e7\u00e3o',          dot: 'bg-teal-400',     badge: 'text-teal-700 dark:text-teal-300 bg-teal-50 dark:bg-teal-500/10 border-teal-200 dark:border-teal-500/20' },
  protocolo:        { label: 'Protocolo',         dot: 'bg-orange-400',   badge: 'text-orange-700 dark:text-orange-300 bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/20' },
  aguardando_orgao: { label: 'Aguardando \u00d3rg\u00e3o', dot: 'bg-yellow-400',   badge: 'text-yellow-700 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-500/10 border-yellow-200 dark:border-yellow-500/20' },
  pendencia_orgao:  { label: 'Pend\u00eancia \u00d3rg\u00e3o',  dot: 'bg-red-400',      badge: 'text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20' },
  concluido:        { label: 'Conclu\u00eddo',         dot: 'bg-emerald-400',  badge: 'text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20' },
  arquivado:        { label: 'Arquivado',         dot: 'bg-slate-400',    badge: 'text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-500/10 border-slate-300 dark:border-slate-500/20' },
  cancelado:        { label: 'Cancelado',         dot: 'bg-rose-400',     badge: 'text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20' },
};

export const DEMAND_LABELS: Record<string, string> = {
  car: '\ud83c\udf3f CAR',
  retificacao_car: '\ud83d\udcdd Retifica\u00e7\u00e3o CAR',
  licenciamento: '\ud83d\udccb Licenciamento',
  regularizacao_fundiaria: '\ud83c\udfe1 Reg. Fundi\u00e1ria',
  outorga: '\ud83d\udca7 Outorga',
  defesa: '\u2696\ufe0f Defesa',
  compensacao: '\ud83c\udf31 Compensa\u00e7\u00e3o/PRAD',
  exigencia_bancaria: '\ud83c\udfe6 Exig\u00eancia Banc\u00e1ria',
  misto: '\ud83d\udd00 Misto',
  nao_identificado: '\u2753 N\u00e3o identificado',
};

export const URGENCY_CONFIG: Record<string, { label: string; cls: string }> = {
  baixa:   { label: '\ud83d\udfe2 Baixa',   cls: 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20' },
  media:   { label: '\ud83d\udfe1 M\u00e9dia',   cls: 'text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-500/10 border-yellow-200 dark:border-yellow-500/20' },
  alta:    { label: '\ud83d\udfe0 Alta',    cls: 'text-orange-700 dark:text-orange-400 bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/20' },
  critica: { label: '\ud83d\udd34 Cr\u00edtica', cls: 'text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20' },
};

export const TASK_PROGRESS_ORDER = ['backlog', 'a_fazer', 'em_progresso', 'aguardando', 'revisao', 'concluida'];

export const TASK_STATUS_LABELS: Record<string, string> = {
  backlog: 'Backlog', a_fazer: 'A Fazer', em_progresso: 'Em Progresso',
  aguardando: 'Aguardando', revisao: 'Revisao', concluida: 'Concluida', cancelada: 'Cancelada',
};

// CAM3WS-007 (Sprint J) — Menu lateral alinhado com a sócia:
// Visão geral / Ações / Documentos / Dados / IA / Histórico / Decisões / Saídas.
// Comercial mantido como bloco condicional (sócia: etapa 6+7).
// "Trilha" removida (duplicava o stepper horizontal do topo).
export const TABS = [
  { key: 'diagnosis',  label: 'Vis\u00e3o geral', icon: Stethoscope },
  { key: 'tasks',      label: 'A\u00e7\u00f5es',       icon: ListChecks },
  { key: 'documents',  label: 'Documentos',       icon: FolderOpen },
  { key: 'dossier',    label: 'Dados',            icon: LayoutGrid },
  { key: 'ai',         label: 'IA',               icon: Bot },
  { key: 'timeline',   label: 'Hist\u00f3rico',      icon: CalendarDays },
  { key: 'decisions',  label: 'Decis\u00f5es',       icon: Scale },
  { key: 'saidas',     label: 'Sa\u00eddas',          icon: PackageCheck },
  { key: 'commercial', label: 'Comercial',        icon: Briefcase },
];
