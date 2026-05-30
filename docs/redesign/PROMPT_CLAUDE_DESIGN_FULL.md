# Briefing COMPLETO para Claude Design — Redesign do Dashboard Regente Ambiental

> **Como usar:** abra o Claude Design / Figma e cole TODO o conteúdo
> deste arquivo (incluindo os 3 blocos de código no final). Anexe os
> 4 screenshots de `docs/redesign/screenshots/` como referência do
> estado atual ("antes").
>
> Este arquivo contém: (1) o briefing visual, (2) regras de
> integridade técnica, (3) os 3 arquivos `.tsx` atuais inteiros
> para você ter contexto completo de estrutura, tipos e componentes.

---

# PARTE 1 — Briefing visual

## Contexto do produto
Regente Ambiental é um SaaS multi-tenant para consultorias
ambientais brasileiras. O dashboard é a primeira tela que o
consultor vê ao logar — precisa transmitir CONTROLE e CLAREZA
sobre dezenas de processos regulatórios simultâneos (CAR,
licenciamento, outorga, defesas).

Audiência primária: consultora sênior, 35-55 anos, opera no
campo regulatório, valoriza informação densa mas legível.

## Tom visual desejado
- MODERNO e MINIMALISTA — nada de visual "corporativo pesado"
- Profissional mas com personalidade ambiental sutil (não usar
  metáforas óbvias de folha/árvore — o verde basta)
- Tipografia generosa, hierarquia clara, muito whitespace
- Bordas sutis, sombras quase imperceptíveis, cantos arredondados
- Densidade média: nem dashboard de trading nem landing page

## Sistema de cores
- Suporte completo a LIGHT MODE e DARK MODE (toggle no header)
- Cor primária: verde esmeralda (#10B981 / emerald-500)
- Acentos semânticos:
  - Crítico/erro: vermelho (red-500)
  - Atenção: âmbar (amber-500)
  - IA/sugestão: violeta (violet-500)
  - Sucesso: emerald-500
- Neutros: escala de zinc/slate (cinza levemente azulado)
- Dark mode com fundos #0A0A0B → #18181B → #27272A em camadas

## Estrutura — duas views alternáveis no mesmo header

### View 1: EXECUTIVO (visão estratégica)
1. Header
   - Saudação personalizada ("Olá, Maria")
   - Subtítulo: "Visão estratégica do negócio"
   - Toggle pill Executivo/Operacional
   - Toggle Dark/Light
   - Botão primário "Novo Caso" + secundário "Fluxo"

2. 4 Stat Cards em grid (Processos Ativos | Taxa Conversão |
   Faturamento | Risco Médio)

3. Barra de filtros (3 chips de view + selects: urgência,
   demanda, UF, período)

4. AI Summary Card (DESTAQUE) — fundo gradiente sutil
   (violet → sky → emerald), ícone Sparkles, label "Leitura
   executiva da IA", parágrafo de análise + recomendação verde

5. Casos por Etapa (grid 4 colunas com 7-8 cards)
   - Cada card: label + total grande + tempo médio + badges
     (🚫 travados / ✓ prontos para avançar)

6. Sidebar direita: Gargalos e Alertas

7. Casos Prioritários do Dia (lista vertical clicável)

8. Atividades Recentes (2/3) + Pipeline de Propostas (1/3)

9. 2 gráficos lado a lado: Processos por Status + por Demanda
   (barras horizontais com %)

10. Minhas Tarefas

### View 2: OPERACIONAL (visão do dia a dia)
1. Mesmo header

2. Filtros pill (Período + Tipo de demanda)

3. 8 KPI Cards em grid 4×2 (Clientes / Casos / Diagnóstico /
   Coleta / Regulatório / Propostas / Contratos / Formalizados)
   - Ícone colorido + label + número + delta % com seta

4. Dois gráficos lado a lado:
   - Casos por Etapa (barras horizontais simples)
   - Funil Operacional (degraus decrescentes em gradiente verde)

5. Banner de alertas do Vigia (agente IA)

6. Grid 3 colunas: Minhas Tarefas | Documentos para Revisão |
   Métricas dos Agentes IA (hoje — 4 mini-stats em 2×2)

7. Grid 2 colunas: Documentos Expirando | Alertas de Processo

8. Atividades Recentes

## Tipos de gráficos a desenhar
- Cards numéricos com delta % (KPIs)
- Barras horizontais com porcentagem (distribuições)
- Funil em degraus com gradiente (conversão por etapa)
- Lista de alertas com badge de severidade
- Cards de etapa com mini-badges contadores
- Pipeline com valor monetário por estágio

Quero gráficos onde fizerem sentido — não force gráfico onde
uma lista é mais clara.

## Estados a desenhar
- Loading (skeletons elegantes — pulse sutil)
- Vazio (mensagem amigável + ilustração mínima opcional)
- Com dados (estado padrão)
- Erro (raro, mas projetar)
- Light mode + Dark mode para cada um dos acima

## Componentes a entregar
1. Telas completas:
   - Dashboard Executivo Light
   - Dashboard Executivo Dark
   - Dashboard Operacional Light
   - Dashboard Operacional Dark

2. Componentes isolados na biblioteca:
   - StatCard (KPI numérico)
   - StageCard (etapa com badges)
   - AlertCard (severity-based)
   - PriorityCaseRow
   - AISummaryCard (gradient)
   - HorizontalBarChart
   - FunnelChart
   - ActivityItem
   - FilterBar
   - Header com toggle de view e tema

## Stack alvo
React 18 + Vite + TypeScript + TailwindCSS + lucide-react.
Use tokens Tailwind-compatíveis (emerald-500, zinc-900, etc.)
para que o handoff pra código seja direto.

## O que NÃO mudar (estrutura/fluxo)
- A nomenclatura dos blocos (a sócia validou)
- A divisão Executivo vs Operacional
- A presença da "Leitura executiva da IA" como bloco de destaque
- O fluxo: header → KPIs → análise IA → detalhes

---

# PARTE 2 — ⚠️ INTOCÁVEL — lógica, dados e integrações

Este é um redesign PURAMENTE VISUAL. Tudo que está abaixo
DEVE permanecer idêntico ao código atual (que está embutido na
Parte 3 deste arquivo). Se o redesign exigir mudar qualquer
item desta lista, ELE ESTÁ ERRADO — refaça.

## Endpoints de API (não renomear, não remover, não criar novos)
- `GET /dashboard/summary?view=executivo|operacional`
- `GET /dashboard/stages`
- `GET /dashboard/alerts`
- `GET /dashboard/priority-cases`
- `GET /dashboard/ai-summary`
- `GET /dashboard/kpis`
- `GET /ai/jobs` (usado por AgentMetricsCard e VigiaAlertsBanner)

## Hooks e bibliotecas (manter exatamente como está)
- `@tanstack/react-query` — todas as chamadas via `useQuery`
- `staleTime` atual de cada query (30s, 60s, 300s) — preservar
- `queryKeys` atuais — preservar para não invalidar cache
- `zustand` store `useAuthStore` — leitura de user
- `react-router-dom` — `useNavigate` para todas as ações
- `lib/api.ts` — único cliente HTTP, NUNCA `fetch`/`axios` direto

## Contratos TypeScript (campos exatos, nomes exatos)
- `ExecutivoDashboard`, `OperacionalDashboard`, `RecentActivity`,
  `PendingTask`, `StatusDistribution`, `ProposalPipelineItem`,
  `DocumentAlert`, `ProcessAlert`
- `StageDistribution`, `DashboardAlert`, `DashboardPriorityCase`,
  `DashboardAISummary`, `DashboardFilters`
- `Kpi`, `KpisResponse`

Não alterar nomes de campos. Não inventar campos novos. Se um
campo não está nos tipos abaixo (Parte 3), ele NÃO vem do backend.

## Comportamentos preservados
- Toggle Executivo/Operacional troca a view (estado local)
- `viewMode` persiste apenas em memória (não em localStorage)
- StatCard com `onClick` → `navigate` para rota
- Cliques em activity/task/doc/alert → `navigate('/processes/${id}')`
- Botão "Novo Caso" → `navigate('/intake')`
- Botão "Fluxo" → `navigate('/processes')`
- Filtros do DashboardRegente alteram queryString das queries
- AIBlock fica oculto/skeleton enquanto carrega
- VigiaAlertsBanner só aparece se houver alertas
- Cores de severidade (critical/high/medium/low) mantêm semântica
- Loading states com skeletons (não esconder a UI inteira)

## Consumidores externos (não quebrar)
- `PrivateLayout` envolve o Dashboard — o redesign vive DENTRO
  desse layout, não substitui o sidebar nem o topbar
- Rota `/dashboard` em `App.tsx` aponta para o default export
  de `pages/Dashboard/index.tsx` — manter esse default export

## Estrutura de arquivos
- Manter os 3 arquivos:
  - `pages/Dashboard/index.tsx` (orquestrador)
  - `pages/Dashboard/DashboardRegente.tsx` (blocos executivos)
  - `pages/Dashboard/DashboardOperacionalRegente.tsx` (operacional)
- Novos componentes visuais podem ser extraídos para
  `pages/Dashboard/components/` — não espalhar em `src/components/`

## Permitido mudar livremente
- Classes Tailwind (cores, espaçamentos, tipografia, layout)
- Estrutura JSX interna dos componentes
- Adicionar bibliotecas de gráficos se necessário (sugestão:
  `recharts` ou `tremor` — ambos compatíveis com a stack)
- Adicionar animações sutis (`framer-motion` permitido)
- Reorganizar a ORDEM visual dos blocos dentro da mesma view
- Tema dark/light via classe `dark:` do Tailwind (já configurado)

---

# PARTE 3 — Code base atual (verbatim)

São os 3 arquivos que compõem o dashboard hoje. Use como
referência exata de tipos, componentes, props e fluxo de dados.

## Arquivo 1: `frontend/src/pages/Dashboard/index.tsx` (831 linhas)

Orquestrador principal. Define os 2 modos (executivo/operacional),
o header, os stats cards condicionais, e renderiza os
subcomponentes específicos de cada modo.

```tsx
import { useState } from 'react';
import {
  Users, Briefcase, AlertCircle, FileText, Activity, Plus,
  CheckSquare, Clock, TrendingUp, DollarSign, AlertTriangle,
  Eye, Calendar, Shield, Bot,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/store/auth';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import DashboardRegente from './DashboardRegente';
import DashboardOperacionalRegente from './DashboardOperacionalRegente';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RecentActivity {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  details: string | null;
  actor_name: string | null;
  created_at: string;
}

interface PendingTask {
  id: number;
  title: string;
  status: string;
  priority: string;
  process_id: number | null;
  due_date: string | null;
}

interface StatusDistribution {
  status: string;
  count: number;
}

interface ProposalPipelineItem {
  status: string;
  count: number;
  total_value: number;
}

interface DocumentAlert {
  id: number;
  filename: string;
  document_type: string | null;
  process_id: number | null;
  expires_at: string | null;
  review_required: boolean;
}

interface ProcessAlert {
  id: number;
  title: string;
  status: string;
  priority: string | null;
  due_date: string | null;
  days_in_status: number | null;
}

interface ExecutivoDashboard {
  view: 'executivo';
  active_processes: number;
  overdue_tasks: number;
  total_clients: number;
  total_properties: number;
  conversion_rate: number;
  faturamento: number;
  risco_medio: number | null;
  processes_by_status: StatusDistribution[];
  processes_by_demand_type: StatusDistribution[];
  proposal_pipeline: ProposalPipelineItem[];
  recent_activities: RecentActivity[];
  my_pending_tasks: PendingTask[];
}

interface OperacionalDashboard {
  view: 'operacional';
  active_processes: number;
  overdue_tasks: number;
  total_clients: number;
  total_properties: number;
  my_pending_tasks_count: number;
  my_overdue_tasks_count: number;
  documents_needing_review: number;
  processes_aguardando_orgao: number;
  my_pending_tasks: PendingTask[];
  documents_for_review: DocumentAlert[];
  expiring_documents: DocumentAlert[];
  process_alerts: ProcessAlert[];
  recent_activities: RecentActivity[];
}

type DashboardData = ExecutivoDashboard | OperacionalDashboard;
type ViewMode = 'executivo' | 'operacional';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-gray-200 dark:bg-zinc-800", className)} />;
}

function SkeletonStatsCards() {
  return (
    <>
      {[0, 1, 2, 3].map(i => (
        <div key={i} className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm w-full">
          <div className="flex justify-between items-start">
            <div className="space-y-3 flex-1">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-8 w-16" />
            </div>
            <Skeleton className="h-12 w-12 rounded-lg shrink-0" />
          </div>
        </div>
      ))}
    </>
  );
}

function SkeletonSection() {
  return (
    <div className="space-y-2">
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} className="flex gap-4 items-start p-3">
          <Skeleton className="h-8 w-8 rounded-full shrink-0" />
          <div className="space-y-2 flex-1">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return 'Agora mesmo';
  if (diff < 3600) return `Há ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `Há ${Math.floor(diff / 3600)}h`;
  return `Há ${Math.floor(diff / 86400)} dia(s)`;
}

function actionLabel(action: string, entity_type: string): string {
  if (action === 'created') return `${entity_type === 'process' ? 'Processo' : 'Item'} criado`;
  if (action === 'status_changed') return 'Status alterado';
  if (action === 'updated') return `${entity_type === 'process' ? 'Processo' : 'Item'} atualizado`;
  return action;
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  high: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  low: 'bg-gray-100 text-gray-600 dark:bg-zinc-800 dark:text-gray-400',
};

const STATUS_LABELS: Record<string, string> = {
  lead: 'Lead',
  triagem: 'Triagem',
  diagnostico: 'Diagnóstico',
  planejamento: 'Planejamento',
  execucao: 'Execução',
  protocolo: 'Protocolo',
  aguardando_orgao: 'Aguardando Órgão',
  pendencia_orgao: 'Pendência Órgão',
  concluido: 'Concluído',
  arquivado: 'Arquivado',
  cancelado: 'Cancelado',
  draft: 'Rascunho',
  sent: 'Enviada',
  accepted: 'Aceita',
  rejected: 'Rejeitada',
  expired: 'Expirada',
};

const DEMAND_LABELS: Record<string, string> = {
  car: 'CAR',
  retificacao_car: 'Retificação CAR',
  licenciamento: 'Licenciamento',
  regularizacao_fundiaria: 'Reg. Fundiária',
  outorga: 'Outorga',
  defesa: 'Defesa',
  compensacao: 'Compensação',
  exigencia_bancaria: 'Exig. Bancária',
  prad: 'PRAD',
  misto: 'Misto',
  nao_identificado: 'Não Identificado',
};

function formatCurrency(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------

interface StatCardProps {
  title: string;
  value: string;
  icon: React.ElementType;
  color: string;
  bg: string;
  onClick?: () => void;
}

function StatCard({ title, value, icon: Icon, color, bg, onClick }: StatCardProps) {
  return (
    <button
      onClick={onClick}
      className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm transform transition-all hover:scale-[1.02] hover:border-gray-300 dark:hover:border-zinc-600 text-left w-full cursor-pointer"
    >
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          <h3 className="text-3xl font-bold text-gray-900 dark:text-white mt-2">{value}</h3>
        </div>
        <div className={`p-3 rounded-lg ${bg}`}>
          <Icon className={`w-6 h-6 ${color}`} />
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Section Components
// ---------------------------------------------------------------------------

function ActivitiesSection({ activities, loading, navigate }: {
  activities: RecentActivity[];
  loading: boolean;
  navigate: (path: string) => void;
}) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Activity className="w-5 h-5 mr-2 text-emerald-600" />
        Atividades Recentes
      </h2>
      {loading && <SkeletonSection />}
      {!loading && !activities.length && (
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhuma atividade registrada ainda.
        </div>
      )}
      {!loading && !!activities.length && (
        <div className="space-y-1">
          {activities.map(a => (
            <button
              type="button"
              key={a.id}
              className="flex gap-4 items-start p-3 hover:bg-gray-50 dark:hover:bg-zinc-800/50 rounded-lg transition-colors border border-transparent hover:border-gray-100 dark:hover:border-zinc-800 cursor-pointer text-left w-full"
              onClick={() => a.entity_type === 'process' && navigate(`/processes/${a.entity_id}`)}
            >
              <div className="bg-gray-100 dark:bg-zinc-800 p-2 rounded-full mt-0.5 shrink-0">
                <FileText className="w-4 h-4 text-gray-600 dark:text-gray-400" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {actionLabel(a.action, a.entity_type)}{a.details ? ` — ${a.details}` : ''}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {timeAgo(a.created_at)}{a.actor_name ? ` • ${a.actor_name}` : ''}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function TasksSection({ tasks, loading, navigate }: {
  tasks: PendingTask[];
  loading: boolean;
  navigate: (path: string) => void;
}) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <CheckSquare className="w-5 h-5 mr-2 text-emerald-600" />
        Minhas Tarefas
      </h2>
      {loading && <SkeletonSection />}
      {!loading && !tasks.length && (
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhuma tarefa pendente.
        </div>
      )}
      {!loading && !!tasks.length && (
        <div className="space-y-2">
          {tasks.map(task => (
            <button
              type="button"
              key={task.id}
              className="p-3 rounded-lg border border-gray-100 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer text-left w-full"
              onClick={() => task.process_id && navigate(`/processes/${task.process_id}`)}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-gray-900 dark:text-white leading-snug line-clamp-2">{task.title}</p>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${PRIORITY_COLORS[task.priority] ?? PRIORITY_COLORS.low}`}>
                  {task.priority}
                </span>
              </div>
              {task.due_date && (
                <p className="text-xs text-gray-400 mt-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(task.due_date).toLocaleDateString('pt-BR')}
                </p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Executivo Sections
// ---------------------------------------------------------------------------

function ProposalPipelineSection({ pipeline }: { pipeline: ProposalPipelineItem[] }) {
  if (!pipeline.length) {
    return (
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
          <DollarSign className="w-5 h-5 mr-2 text-emerald-600" />
          Pipeline de Propostas
        </h2>
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhuma proposta registrada ainda.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <DollarSign className="w-5 h-5 mr-2 text-emerald-600" />
        Pipeline de Propostas
      </h2>
      <div className="space-y-3">
        {pipeline.map(item => (
          <div key={item.status} className="flex items-center justify-between p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                {STATUS_LABELS[item.status] ?? item.status}
              </p>
              <p className="text-xs text-gray-500">{item.count} proposta{item.count !== 1 ? 's' : ''}</p>
            </div>
            <p className="text-sm font-bold text-gray-900 dark:text-white">{formatCurrency(item.total_value)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

const BAR_COLORS = [
  'bg-emerald-500', 'bg-blue-500', 'bg-amber-500', 'bg-purple-500',
  'bg-rose-500', 'bg-cyan-500', 'bg-indigo-500', 'bg-teal-500',
];

function DistributionSection({ title, icon: Icon, items, labelMap }: {
  title: string;
  icon: React.ElementType;
  items: StatusDistribution[];
  labelMap: Record<string, string>;
}) {
  if (!items.length) return null;
  const total = items.reduce((sum, i) => sum + i.count, 0);

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Icon className="w-5 h-5 mr-2 text-emerald-600" />
        {title}
      </h2>
      <div className="space-y-2">
        {items.map((item, index) => {
          const pct = total > 0 ? Math.round((item.count / total) * 100) : 0;
          return (
            <div key={item.status}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-gray-700 dark:text-gray-300">{labelMap[item.status] ?? item.status}</span>
                <span className="text-gray-500">{item.count} ({pct}%)</span>
              </div>
              <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-2">
                <div className={`${BAR_COLORS[index % BAR_COLORS.length]} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Operacional Sections
// ---------------------------------------------------------------------------

function DocumentsReviewSection({ docs, navigate }: { docs: DocumentAlert[]; navigate: (path: string) => void }) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Eye className="w-5 h-5 mr-2 text-amber-600" />
        Documentos para Revisão
      </h2>
      {!docs.length && (
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhum documento pendente de revisão.
        </div>
      )}
      {!!docs.length && (
        <div className="space-y-2">
          {docs.map(doc => (
            <button
              type="button"
              key={doc.id}
              className="flex items-center justify-between p-3 rounded-lg border border-gray-100 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer text-left w-full"
              onClick={() => doc.process_id && navigate(`/processes/${doc.process_id}`)}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{doc.filename}</p>
                <p className="text-xs text-gray-500">{doc.document_type ?? 'Tipo não definido'}</p>
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 shrink-0">
                Revisão
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function expiryUrgency(expiresAt: string): { label: string; className: string } {
  const days = Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 86_400_000);
  if (days <= 7) return { label: `${days}d`, className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' };
  if (days <= 14) return { label: `${days}d`, className: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' };
  return { label: `${days}d`, className: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' };
}

function ExpiringDocumentsSection({ docs, navigate }: { docs: DocumentAlert[]; navigate: (path: string) => void }) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Calendar className="w-5 h-5 mr-2 text-red-500" />
        Documentos Expirando
      </h2>
      {!docs.length && (
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhum documento expirando nos próximos 30 dias.
        </div>
      )}
      {!!docs.length && (
        <div className="space-y-2">
          {docs.map(doc => {
            const urgency = doc.expires_at ? expiryUrgency(doc.expires_at) : null;
            return (
              <button
                type="button"
                key={doc.id}
                className="flex items-center justify-between p-3 rounded-lg border border-gray-100 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer text-left w-full"
                onClick={() => doc.process_id && navigate(`/processes/${doc.process_id}`)}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{doc.filename}</p>
                  <p className="text-xs text-gray-500">{doc.document_type ?? 'Tipo não definido'}</p>
                </div>
                {urgency && (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${urgency.className}`}>
                    {new Date(doc.expires_at!).toLocaleDateString('pt-BR')} ({urgency.label})
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ProcessAlertsSection({ alerts, navigate }: { alerts: ProcessAlert[]; navigate: (path: string) => void }) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Shield className="w-5 h-5 mr-2 text-red-500" />
        Alertas de Processo
      </h2>
      {!alerts.length && (
        <div className="text-sm text-gray-500 bg-gray-50 dark:bg-zinc-800/50 p-6 rounded-lg text-center border border-dashed border-gray-200 dark:border-zinc-700">
          Nenhum alerta no momento.
        </div>
      )}
      {!!alerts.length && (
        <div className="space-y-2">
          {alerts.map(a => (
            <button
              type="button"
              key={a.id}
              className="p-3 rounded-lg border border-gray-100 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer text-left w-full"
              onClick={() => navigate(`/processes/${a.id}`)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{a.title}</p>
                  <p className="text-xs text-gray-500">
                    {STATUS_LABELS[a.status] ?? a.status}
                    {a.days_in_status != null ? ` • ${a.days_in_status} dias` : ''}
                  </p>
                </div>
                {a.due_date && (
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 shrink-0">
                    {new Date(a.due_date).toLocaleDateString('pt-BR')}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Agent Metrics + Vigia Alerts
// ---------------------------------------------------------------------------

function AgentMetricsCard() {
  const { data: jobs = [] } = useQuery<{
    id: number; status: string; agent_name: string | null;
    cost_usd: number | null; created_at: string;
    result: Record<string, unknown> | null;
  }[]>({
    queryKey: ['ai-jobs-dashboard'],
    queryFn: () => api.get('/ai/jobs', { params: { limit: 100 } }).then(r => r.data),
    staleTime: 60_000,
  });

  const today = new Date().toDateString();
  const todayJobs = jobs.filter(j => new Date(j.created_at).toDateString() === today);
  const completed = todayJobs.filter(j => j.status === 'completed').length;
  const failed = todayJobs.filter(j => j.status === 'failed').length;
  const totalCost = todayJobs.reduce((s, j) => s + (j.cost_usd ?? 0), 0);
  const needsReview = todayJobs.filter(j => j.result?.requires_review === true).length;
  const successRate = todayJobs.length > 0 ? Math.round((completed / todayJobs.length) * 100) : 0;

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-xl border border-gray-100 dark:border-zinc-800 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center">
        <Bot className="w-5 h-5 mr-2 text-purple-600" />
        Agentes IA (hoje)
      </h2>
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">Execucoes</p>
          <p className="text-xl font-bold text-gray-900 dark:text-white">{todayJobs.length}</p>
        </div>
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">Taxa Sucesso</p>
          <p className={`text-xl font-bold ${successRate >= 80 ? 'text-emerald-600' : successRate >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
            {successRate}%
          </p>
        </div>
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">Custo</p>
          <p className="text-xl font-bold text-gray-900 dark:text-white">${totalCost.toFixed(4)}</p>
        </div>
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">Revisao Pendente</p>
          <p className={`text-xl font-bold ${needsReview > 0 ? 'text-amber-600' : 'text-gray-900 dark:text-white'}`}>
            {needsReview}
          </p>
        </div>
      </div>
      {failed > 0 && (
        <div className="mt-3 p-2 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-500/20">
          <p className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" /> {failed} execucao(oes) falharam hoje
          </p>
        </div>
      )}
    </div>
  );
}

function VigiaAlertsBanner({ navigate }: { navigate: (path: string) => void }) {
  const { data: jobs = [] } = useQuery<{
    id: number; agent_name: string | null; status: string;
    result: Record<string, unknown> | null; created_at: string;
  }[]>({
    queryKey: ['vigia-alerts'],
    queryFn: () => api.get('/ai/jobs', {
      params: { agent_name: 'vigia', limit: 1 },
    }).then(r => r.data),
    staleTime: 300_000,
  });

  const lastVigia = jobs.find(j => j.agent_name === 'vigia' && j.status === 'completed');
  const alerts = (lastVigia?.result?.alerts ?? []) as {
    type: string; severity: string; message: string; process_id?: number;
  }[];

  if (!alerts.length) return null;

  const severityStyles: Record<string, string> = {
    error: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-500/30 text-red-700 dark:text-red-300',
    warning: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-500/30 text-amber-700 dark:text-amber-300',
  };

  return (
    <div className="space-y-2">
      {alerts.slice(0, 5).map((alert, i) => (
        <button
          key={i}
          type="button"
          onClick={() => alert.process_id && navigate(`/processes/${alert.process_id}`)}
          className={`w-full text-left p-3 rounded-xl border text-sm flex items-center gap-2 transition-colors hover:opacity-80 ${severityStyles[alert.severity] ?? severityStyles.warning}`}
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span className="truncate">{alert.message}</span>
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState<ViewMode>('executivo');

  const { data: summaryData, isLoading } = useQuery({
    queryKey: ['dashboard-stats', viewMode],
    queryFn: () => api.get<DashboardData>('/dashboard/summary', { params: { view: viewMode } }).then(r => r.data),
    staleTime: 30_000,
  });

  const activities: RecentActivity[] = summaryData?.recent_activities ?? [];
  const tasks: PendingTask[] = summaryData?.my_pending_tasks ?? [];

  // Stats cards condicionais
  const stats: StatCardProps[] = (() => {
    if (!summaryData || isLoading) return [];

    if (viewMode === 'executivo' && summaryData.view === 'executivo') {
      const d = summaryData;
      return [
        { title: 'Processos Ativos', value: String(d.active_processes), icon: Briefcase, color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30', onClick: () => navigate('/processes') },
        { title: 'Taxa de Conversão', value: `${(d.conversion_rate * 100).toFixed(0)}%`, icon: TrendingUp, color: 'text-emerald-600', bg: 'bg-emerald-100 dark:bg-emerald-900/30' },
        { title: 'Faturamento', value: formatCurrency(d.faturamento), icon: DollarSign, color: 'text-green-600', bg: 'bg-green-100 dark:bg-green-900/30' },
        { title: 'Risco Médio', value: d.risco_medio != null ? d.risco_medio.toFixed(1) : '—', icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-900/30' },
      ];
    }

    if (viewMode === 'operacional' && summaryData.view === 'operacional') {
      const d = summaryData;
      return [
        { title: 'Minhas Pendentes', value: String(d.my_pending_tasks_count), icon: CheckSquare, color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30' },
        { title: 'Tarefas em Atraso', value: String(d.my_overdue_tasks_count), icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-900/30' },
        { title: 'Docs para Revisão', value: String(d.documents_needing_review), icon: FileText, color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-900/30' },
        { title: 'Aguardando Órgão', value: String(d.processes_aguardando_orgao), icon: Clock, color: 'text-purple-600', bg: 'bg-purple-100 dark:bg-purple-900/30' },
      ];
    }

    return [];
  })();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Olá, {user?.full_name?.split(' ')[0] ?? 'Administrador'}
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            {viewMode === 'executivo' ? 'Visão estratégica do negócio' : 'Visão operacional do dia a dia'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex rounded-xl bg-gray-100 dark:bg-zinc-800 p-1">
            <button
              onClick={() => setViewMode('executivo')}
              className={cn(
                "px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200",
                viewMode === 'executivo'
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
              )}
            >
              Executivo
            </button>
            <button
              onClick={() => setViewMode('operacional')}
              className={cn(
                "px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200",
                viewMode === 'operacional'
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
              )}
            >
              Operacional
            </button>
          </div>
          <button
            onClick={() => navigate('/intake')}
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-colors shadow-lg shadow-emerald-500/20 flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Novo Caso
          </button>
          {/* CAM2D-007 — Ação rápida: Fluxo de trabalho */}
          <button
            onClick={() => navigate('/processes')}
            className="bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200 hover:bg-gray-50 dark:hover:bg-white/10 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
          >
            <Briefcase className="w-4 h-4" />
            Fluxo
          </button>
        </div>
      </div>

      {/* Stats Cards — só na view executivo (operacional tem os 8 do Regente) */}
      {viewMode === 'executivo' && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {isLoading ? (
            <SkeletonStatsCards />
          ) : (
            stats.map((item, index) => <StatCard key={index} {...item} />)
          )}
        </div>
      )}

      {/* Regente Cam2 — Blocos 3/4/5/6 (CAM2D-001/002/003/004) */}
      {viewMode === 'executivo' && <DashboardRegente />}

      {/* === EXECUTIVO SECTIONS === */}
      {viewMode === 'executivo' && (
        <div className="space-y-6">
          {/* Row 1: Atividades + Pipeline */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="col-span-1 lg:col-span-2">
              <ActivitiesSection activities={activities} loading={isLoading} navigate={navigate} />
            </div>
            <div className="col-span-1">
              {summaryData?.view === 'executivo' && (
                <ProposalPipelineSection pipeline={summaryData.proposal_pipeline} />
              )}
            </div>
          </div>

          {/* Row 2: Distribuicoes */}
          {summaryData?.view === 'executivo' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <DistributionSection
                title="Processos por Status"
                icon={Briefcase}
                items={summaryData.processes_by_status}
                labelMap={STATUS_LABELS}
              />
              <DistributionSection
                title="Processos por Tipo de Demanda"
                icon={Users}
                items={summaryData.processes_by_demand_type}
                labelMap={DEMAND_LABELS}
              />
            </div>
          )}

          {/* Row 3: Tarefas */}
          <TasksSection tasks={tasks} loading={isLoading} navigate={navigate} />
        </div>
      )}

      {/* === OPERACIONAL SECTIONS === */}
      {viewMode === 'operacional' && (
        <div className="space-y-6">
          {/* Bloco 1 do Sprint F — 8 KPIs + Casos por Etapa + Funil Operacional */}
          <DashboardOperacionalRegente />

          {/* Vigia Alerts Banner */}
          <VigiaAlertsBanner navigate={navigate} />

          {/* Row 1: Tarefas + Docs Revisao + IA Metrics */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <TasksSection tasks={tasks} loading={isLoading} navigate={navigate} />
            {summaryData?.view === 'operacional' && (
              <DocumentsReviewSection docs={summaryData.documents_for_review} navigate={navigate} />
            )}
            <AgentMetricsCard />
          </div>

          {/* Row 2: Docs Expirando + Alertas */}
          {summaryData?.view === 'operacional' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ExpiringDocumentsSection docs={summaryData.expiring_documents} navigate={navigate} />
              <ProcessAlertsSection alerts={summaryData.process_alerts} navigate={navigate} />
            </div>
          )}

          {/* Row 3: Atividades */}
          <ActivitiesSection activities={activities} loading={isLoading} navigate={navigate} />
        </div>
      )}
    </div>
  );
}
```

---

## Arquivo 2: `frontend/src/pages/Dashboard/DashboardRegente.tsx` (433 linhas)

Blocos executivos: filtros, AI Summary, Stages, Alerts, Priority Cases.

```tsx
/**
 * DashboardRegente — Blocos executivos do Regente Cam2 (CAM2D-001 a CAM2D-004)
 *
 * - Bloco 3 — Casos por etapa (7 estágios com totais/travados/prontos)
 * - Bloco 4 — Gargalos e alertas críticos
 * - Bloco 5 — Casos prioritários do dia
 * - Bloco 6 — Leitura executiva da IA
 */
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle, ArrowRight, CheckCircle2, ChevronRight, Filter,
  Flame, Layers, Sparkles, Zap,
} from 'lucide-react';
import { api } from '@/lib/api';
import { MACROETAPA_STATE_BADGE } from '@/pages/Processes/quadro-types';

// CAM2D-005 — Filtros executivos
interface DashboardFilters {
  urgency?: string;
  demand_type?: string;
  state_uf?: string;
  days?: number;
  view?: 'default' | 'bottlenecks' | 'priority';  // CAM2D-006
}

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface StageDistribution {
  macroetapa: string;
  label: string;
  total: number;
  blocked: number;
  ready_to_advance: number;
  avg_days_in_stage: number | null;
}

interface DashboardAlert {
  kind: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  count: number;
  label: string;
  macroetapa: string | null;
}

interface DashboardPriorityCase {
  process_id: number;
  client_name: string | null;
  property_name: string | null;
  demand_type: string | null;
  urgency: string | null;
  macroetapa: string | null;
  macroetapa_label: string | null;
  state: string | null;
  priority_reason: string;
  next_step: string | null;
  responsible_user_name: string | null;
}

interface DashboardAISummary {
  text: string;
  top_stage_bottleneck: string | null;
  top_stage_bottleneck_label: string | null;
  critical_pending_count: number;
  ready_to_advance_count: number;
  recommendation: string | null;
  source: string;
}

const SEVERITY_CLS: Record<string, string> = {
  low:      'bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-slate-300',
  medium:   'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  high:     'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
};

// ─── Componente ───────────────────────────────────────────────────────────────

export default function DashboardRegente() {
  const [filters, setFilters] = useState<DashboardFilters>({ view: 'default' });

  const qs = useMemo(() => {
    const params = new URLSearchParams();
    if (filters.urgency) params.append('urgency', filters.urgency);
    if (filters.demand_type) params.append('demand_type', filters.demand_type);
    if (filters.state_uf) params.append('state_uf', filters.state_uf);
    if (filters.days) params.append('days', String(filters.days));
    const s = params.toString();
    return s ? `?${s}` : '';
  }, [filters.urgency, filters.demand_type, filters.state_uf, filters.days]);

  const { data: stages = [] } = useQuery({
    queryKey: ['dashboard-stages', qs],
    queryFn: () => api.get<StageDistribution[]>(`/dashboard/stages${qs}`).then(r => r.data),
    staleTime: 30_000,
  });

  const { data: alerts = [] } = useQuery({
    queryKey: ['dashboard-alerts'],
    queryFn: () => api.get<DashboardAlert[]>('/dashboard/alerts').then(r => r.data),
    staleTime: 30_000,
  });

  const { data: priorityCases = [] } = useQuery({
    queryKey: ['dashboard-priority-cases', qs],
    queryFn: () => {
      const extra = qs ? `&${qs.slice(1)}` : '';
      return api.get<DashboardPriorityCase[]>(`/dashboard/priority-cases?limit=8${extra}`).then(r => r.data);
    },
    staleTime: 30_000,
  });

  const { data: aiSummary } = useQuery({
    queryKey: ['dashboard-ai-summary'],
    queryFn: () => api.get<DashboardAISummary>('/dashboard/ai-summary').then(r => r.data),
    staleTime: 60_000,
  });

  // CAM2D-006 — Aplica view:
  // default: stages + priority cases + alerts
  // bottlenecks: prioriza coluna de alertas e só mostra etapas com travas
  // priority: só casos prioritários
  const filteredStages = filters.view === 'bottlenecks'
    ? stages.filter(s => s.blocked > 0 || s.ready_to_advance > 0)
    : stages;

  return (
    <div className="space-y-5">
      {/* Barra de filtros + view selector */}
      <FilterBar filters={filters} setFilters={setFilters} />

      {/* Bloco 6 — Leitura executiva da IA */}
      <AIBlock summary={aiSummary} />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-5">
        <div className="space-y-5">
          {filters.view !== 'priority' && <StagesBlock stages={filteredStages} />}
          <PriorityCasesBlock cases={priorityCases} />
        </div>

        {filters.view !== 'priority' && <AlertsBlock alerts={alerts} />}
      </div>
    </div>
  );
}

// CAM2D-005 + CAM2D-006
function FilterBar({ filters, setFilters }: { filters: DashboardFilters; setFilters: (f: DashboardFilters) => void }) {
  const hasActiveFilters = !!(filters.urgency || filters.demand_type || filters.state_uf || filters.days);
  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-3 flex flex-wrap items-center gap-2">
      <Filter className="w-4 h-4 text-gray-400 shrink-0" />
      <span className="text-xs font-medium text-gray-500 dark:text-slate-400 shrink-0">Visão:</span>
      <div className="flex gap-1">
        {([
          { k: 'default', l: 'Geral' },
          { k: 'bottlenecks', l: 'Gargalos' },
          { k: 'priority', l: 'Prioridade do dia' },
        ] as { k: DashboardFilters['view']; l: string }[]).map(({ k, l }) => {
          const active = filters.view === k;
          return (
            <button
              key={k}
              onClick={() => setFilters({ ...filters, view: k })}
              className={`text-xs px-2.5 py-1 rounded-lg font-medium ${
                active
                  ? 'bg-emerald-500 text-white'
                  : 'bg-gray-100 dark:bg-white/5 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-white/10'
              }`}
            >
              {l}
            </button>
          );
        })}
      </div>

      <div className="h-5 w-px bg-gray-200 dark:bg-white/10 mx-1" />

      <select
        value={filters.urgency ?? ''}
        onChange={e => setFilters({ ...filters, urgency: e.target.value || undefined })}
        className="text-xs px-2 py-1 rounded-lg bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200"
      >
        <option value="">Urgência: todas</option>
        <option value="critica">🔴 Crítica</option>
        <option value="alta">🟠 Alta</option>
        <option value="media">🟡 Média</option>
        <option value="baixa">🟢 Baixa</option>
      </select>

      <select
        value={filters.demand_type ?? ''}
        onChange={e => setFilters({ ...filters, demand_type: e.target.value || undefined })}
        className="text-xs px-2 py-1 rounded-lg bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200"
      >
        <option value="">Demanda: todas</option>
        <option value="car">CAR</option>
        <option value="retificacao_car">Retificação CAR</option>
        <option value="licenciamento">Licenciamento</option>
        <option value="regularizacao_fundiaria">Regularização</option>
        <option value="outorga">Outorga</option>
        <option value="defesa">Defesa</option>
        <option value="compensacao">Compensação</option>
        <option value="prad">PRAD</option>
      </select>

      <input
        type="text"
        value={filters.state_uf ?? ''}
        onChange={e => setFilters({ ...filters, state_uf: e.target.value.toUpperCase().slice(0, 2) || undefined })}
        placeholder="UF"
        maxLength={2}
        className="text-xs px-2 py-1 rounded-lg bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200 w-14"
      />

      <select
        value={filters.days ?? ''}
        onChange={e => setFilters({ ...filters, days: e.target.value ? parseInt(e.target.value) : undefined })}
        className="text-xs px-2 py-1 rounded-lg bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-slate-200"
      >
        <option value="">Período: sempre</option>
        <option value="7">Últimos 7 dias</option>
        <option value="30">Últimos 30 dias</option>
        <option value="90">Últimos 90 dias</option>
      </select>

      {hasActiveFilters && (
        <button
          onClick={() => setFilters({ view: filters.view })}
          className="text-xs px-2 py-1 rounded-lg text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10"
        >
          Limpar
        </button>
      )}
    </div>
  );
}

// ─── Blocos ───────────────────────────────────────────────────────────────────

function AIBlock({ summary }: { summary: DashboardAISummary | undefined }) {
  if (!summary) return <div className="h-24 rounded-2xl bg-gray-100 dark:bg-white/5 animate-pulse" />;
  return (
    <div className="rounded-2xl bg-gradient-to-r from-violet-50 via-sky-50 to-emerald-50 dark:from-violet-500/10 dark:via-sky-500/10 dark:to-emerald-500/10 border border-violet-200 dark:border-violet-500/30 p-5">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-2xl bg-white dark:bg-violet-500/20 flex items-center justify-center shrink-0">
          <Sparkles className="w-5 h-5 text-violet-600 dark:text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs uppercase tracking-wide text-violet-700 dark:text-violet-300 font-semibold">
              Leitura executiva da IA
            </span>
            <span className="text-[10px] text-gray-400">· análise automática</span>
          </div>
          <p className="text-sm text-gray-800 dark:text-slate-100 leading-relaxed">{summary.text}</p>
          {summary.recommendation && (
            <div className="mt-2 text-xs text-emerald-800 dark:text-emerald-200 bg-emerald-50/60 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 rounded-lg p-2">
              💡 {summary.recommendation}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StagesBlock({ stages }: { stages: StageDistribution[] }) {
  const navigate = useNavigate();
  const totalCases = stages.reduce((sum, s) => sum + s.total, 0);

  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-slate-100">Casos por etapa</h2>
          <span className="text-xs text-gray-500">· {totalCases} ativos</span>
        </div>
        <button
          onClick={() => navigate('/processes')}
          className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1"
        >
          Ver fluxo <ChevronRight className="w-3 h-3" />
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        {stages.map((s) => (
          <div
            key={s.macroetapa}
            className={`p-3 rounded-xl border text-left ${
              s.total === 0
                ? 'bg-gray-50 dark:bg-white/5 border-gray-100 dark:border-white/10 opacity-60'
                : 'bg-white dark:bg-white/5 border-gray-200 dark:border-white/10'
            }`}
          >
            <div className="text-[11px] font-medium text-gray-500 dark:text-slate-400 truncate">
              {s.label}
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-gray-900 dark:text-white">{s.total}</span>
              {s.avg_days_in_stage !== null && (
                <span className="text-[10px] text-gray-400">~{s.avg_days_in_stage}d</span>
              )}
            </div>
            <div className="flex gap-1.5 mt-2 text-[10px]">
              {s.blocked > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300">
                  🚫 {s.blocked}
                </span>
              )}
              {s.ready_to_advance > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                  ✓ {s.ready_to_advance}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AlertsBlock({ alerts }: { alerts: DashboardAlert[] }) {
  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5 h-fit">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle className="w-4 h-4 text-red-500" />
        <h2 className="text-sm font-semibold text-gray-800 dark:text-slate-100">Gargalos e alertas</h2>
        <span className="text-xs text-gray-500">· {alerts.length}</span>
      </div>
      {alerts.length === 0 ? (
        <div className="text-center py-6 text-xs text-gray-400 italic">
          <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-400" />
          Nenhum alerta crítico no momento.
        </div>
      ) : (
        <ul className="space-y-2">
          {alerts.map((a, i) => (
            <li
              key={i}
              className={`flex items-start gap-2 p-2.5 rounded-xl border ${
                a.severity === 'critical'
                  ? 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30'
                  : a.severity === 'high'
                  ? 'bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/30'
                  : 'bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/30'
              }`}
            >
              <Flame className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${
                a.severity === 'critical' ? 'text-red-500' :
                a.severity === 'high' ? 'text-orange-500' : 'text-amber-500'
              }`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-gray-900 dark:text-slate-100">{a.label}</div>
                <span className={`inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded ${SEVERITY_CLS[a.severity]}`}>
                  {a.severity}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PriorityCasesBlock({ cases }: { cases: DashboardPriorityCase[] }) {
  const navigate = useNavigate();
  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-slate-100">Casos prioritários do dia</h2>
          <span className="text-xs text-gray-500">· top {cases.length}</span>
        </div>
      </div>
      {cases.length === 0 ? (
        <div className="text-center py-6 text-xs text-gray-400 italic">Nenhum caso com prioridade no momento.</div>
      ) : (
        <div className="space-y-2">
          {cases.map(c => {
            const stateBadge = c.state ? MACROETAPA_STATE_BADGE[c.state] : null;
            return (
              <button
                key={c.process_id}
                onClick={() => navigate(`/processes/${c.process_id}`)}
                className="w-full text-left p-3 rounded-xl border border-gray-100 dark:border-white/10 hover:bg-gray-50 dark:hover:bg-white/5 flex items-center gap-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {c.client_name ?? '—'}
                      {c.property_name && <span className="text-gray-400"> · {c.property_name}</span>}
                    </span>
                    {stateBadge && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${stateBadge.cls}`}>
                        {stateBadge.label}
                      </span>
                    )}
                    {c.urgency && ['critica', 'alta'].includes(c.urgency) && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-red-100 text-red-700">
                        {c.urgency}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5 truncate">
                    {c.macroetapa_label && <span>{c.macroetapa_label} · </span>}
                    <span className="italic">{c.priority_reason}</span>
                  </div>
                  {c.next_step && (
                    <div className="text-xs text-emerald-700 dark:text-emerald-400 mt-0.5 flex items-center gap-1">
                      <ArrowRight className="w-3 h-3" /> {c.next_step}
                    </div>
                  )}
                </div>
                {c.responsible_user_name && (
                  <div className="text-[10px] text-gray-500 shrink-0 hidden sm:block">
                    {c.responsible_user_name}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

---

## Arquivo 3: `frontend/src/pages/Dashboard/DashboardOperacionalRegente.tsx` (281 linhas)

Bloco operacional: 8 KPIs, Casos por Etapa (barras horizontais),
Funil Operacional (degraus). Sem dependência de lib de gráficos.

```tsx
/**
 * DashboardOperacionalRegente — Painel operacional conforme Lovable da sócia.
 *
 * Bloco 1 do Sprint F:
 *  - 8 cards KPI (Clientes Ativos, Casos Ativos, Em Diagnóstico, Em Coleta,
 *    Em Caminho Regulatório, Propostas Enviadas, Contratos Enviados, Formalizados)
 *  - Gráfico "Casos por Etapa" (barras horizontais)
 *  - "Funil Operacional" (7 degraus decrescentes)
 *  - Filtros: Período, Responsável, Tipo de demanda
 *
 * Sem dependência de lib de gráficos — CSS puro + divs proporcionais.
 */
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Users, Briefcase, Stethoscope, FileStack, Scale, Send,
  FileSignature, CheckCircle2, TrendingUp, TrendingDown, Minus,
} from 'lucide-react';
import { api } from '@/lib/api';
import { DEMAND_TYPE_LABELS } from '@/pages/Processes/quadro-types';

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface Kpi {
  key: string;
  label: string;
  value: number;
  delta_pct: number | null;
  hint: string | null;
}

interface StageDistribution {
  macroetapa: string;
  label: string;
  total: number;
  blocked?: number;
  ready_to_advance?: number;
}

interface KpisResponse {
  days: number;
  responsible_user_id: number | null;
  demand_type: string | null;
  kpis: Kpi[];
  funnel: StageDistribution[];
}

// ─── Config visual dos cards ─────────────────────────────────────────────────

const KPI_ICON: Record<string, typeof Users> = {
  clientes_ativos: Users,
  casos_ativos: Briefcase,
  em_diagnostico: Stethoscope,
  em_coleta: FileStack,
  em_caminho_regulatorio: Scale,
  propostas_enviadas: Send,
  contratos_enviados: FileSignature,
  casos_formalizados: CheckCircle2,
};

const KPI_ACCENT: Record<string, { bg: string; fg: string }> = {
  clientes_ativos:      { bg: 'bg-emerald-50 dark:bg-emerald-500/10', fg: 'text-emerald-600 dark:text-emerald-400' },
  casos_ativos:         { bg: 'bg-blue-50 dark:bg-blue-500/10',       fg: 'text-blue-600 dark:text-blue-400' },
  em_diagnostico:       { bg: 'bg-indigo-50 dark:bg-indigo-500/10',   fg: 'text-indigo-600 dark:text-indigo-400' },
  em_coleta:            { bg: 'bg-amber-50 dark:bg-amber-500/10',     fg: 'text-amber-600 dark:text-amber-400' },
  em_caminho_regulatorio:{ bg: 'bg-purple-50 dark:bg-purple-500/10',  fg: 'text-purple-600 dark:text-purple-400' },
  propostas_enviadas:   { bg: 'bg-teal-50 dark:bg-teal-500/10',       fg: 'text-teal-600 dark:text-teal-400' },
  contratos_enviados:   { bg: 'bg-sky-50 dark:bg-sky-500/10',         fg: 'text-sky-600 dark:text-sky-400' },
  casos_formalizados:   { bg: 'bg-emerald-50 dark:bg-emerald-500/10', fg: 'text-emerald-600 dark:text-emerald-400' },
};

const PERIOD_OPTIONS: { value: number; label: string }[] = [
  { value: 7,   label: 'Últimos 7 dias' },
  { value: 30,  label: 'Últimos 30 dias' },
  { value: 90,  label: 'Últimos 90 dias' },
  { value: 180, label: 'Últimos 180 dias' },
];

// ─── Componente principal ────────────────────────────────────────────────────

export default function DashboardOperacionalRegente() {
  const [days, setDays] = useState(30);
  const [demandType, setDemandType] = useState<string>('');

  const { data: kpisData, isLoading } = useQuery({
    queryKey: ['dashboard-kpis', days, demandType],
    queryFn: () => {
      const params = new URLSearchParams({ days: String(days) });
      if (demandType) params.set('demand_type', demandType);
      return api.get<KpisResponse>(`/dashboard/kpis?${params}`).then(r => r.data);
    },
    staleTime: 60_000,
  });

  const demandTypeOptions = useMemo(() => Object.keys(DEMAND_TYPE_LABELS), []);

  const kpis = kpisData?.kpis ?? [];
  const funnel = kpisData?.funnel ?? [];

  return (
    <section className="space-y-6">
      {/* Filtros operacionais */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={days}
          onChange={e => setDays(Number(e.target.value))}
          className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 dark:text-zinc-200"
        >
          {PERIOD_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <select
          value={demandType}
          onChange={e => setDemandType(e.target.value)}
          className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 dark:text-zinc-200"
        >
          <option value="">Tipo de demanda (todos)</option>
          {demandTypeOptions.map(d => (
            <option key={d} value={d}>{DEMAND_TYPE_LABELS[d]}</option>
          ))}
        </select>
      </div>

      {/* 8 KPI cards (2 linhas de 4) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {isLoading
          ? Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-28 bg-gray-100 dark:bg-zinc-800/50 rounded-2xl animate-pulse" />
            ))
          : kpis.map(k => <KpiCard key={k.key} kpi={k} />)}
      </div>

      {/* Gráficos lado a lado */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CasosPorEtapa data={funnel} loading={isLoading} />
        <FunilOperacional data={funnel} loading={isLoading} />
      </div>
    </section>
  );
}

// ─── Subcomponentes ───────────────────────────────────────────────────────────

function KpiCard({ kpi }: { kpi: Kpi }) {
  const Icon = KPI_ICON[kpi.key] ?? Briefcase;
  const accent = KPI_ACCENT[kpi.key] ?? { bg: 'bg-gray-100', fg: 'text-gray-600' };

  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-4 hover:border-gray-200 dark:hover:border-white/20 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 truncate">
            {kpi.label}
          </p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-gray-900 dark:text-white">
              {kpi.value.toLocaleString('pt-BR')}
            </span>
            <DeltaBadge value={kpi.delta_pct} />
          </div>
          {kpi.hint && (
            <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-1 truncate">
              {kpi.hint}
            </p>
          )}
        </div>
        <div className={`p-2 rounded-lg ${accent.bg} shrink-0`}>
          <Icon className={`w-4 h-4 ${accent.fg}`} />
        </div>
      </div>
    </div>
  );
}

function DeltaBadge({ value }: { value: number | null }) {
  if (value === null || value === undefined) return null;

  const isUp = value > 0;
  const isDown = value < 0;
  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;
  const cls = isUp
    ? 'text-emerald-600 dark:text-emerald-400'
    : isDown
    ? 'text-red-600 dark:text-red-400'
    : 'text-gray-500';

  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${cls}`}>
      <Icon className="w-3 h-3" />
      {value > 0 ? '+' : ''}{value.toFixed(1)}%
    </span>
  );
}

function CasosPorEtapa({ data, loading }: { data: StageDistribution[]; loading: boolean }) {
  const maxTotal = Math.max(...data.map(d => d.total), 1);

  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
        Casos por Etapa
      </h3>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-5 bg-gray-100 dark:bg-zinc-800/50 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-2.5">
          {data.map(d => {
            const pct = (d.total / maxTotal) * 100;
            return (
              <div key={d.macroetapa}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-gray-600 dark:text-gray-400 truncate max-w-[70%]">
                    {d.label}
                  </span>
                  <span className="font-semibold text-gray-900 dark:text-white">{d.total}</span>
                </div>
                <div className="h-2 bg-gray-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 rounded-full transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function FunilOperacional({ data, loading }: { data: StageDistribution[]; loading: boolean }) {
  // No funil, cada degrau tem largura decrescente proporcional ao total.
  const maxTotal = Math.max(...data.map(d => d.total), 1);

  return (
    <div className="bg-white dark:bg-white/5 rounded-2xl border border-gray-100 dark:border-white/10 p-5">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
        Funil Operacional
      </h3>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-7 bg-gray-100 dark:bg-zinc-800/50 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-1.5">
          {data.map((d, i) => {
            const pct = Math.max((d.total / maxTotal) * 100, 8); // mínimo 8% pra visibilidade
            // Gradiente: verde saturado → claro
            const intensity = Math.max(100 - i * 10, 30); // 100 → 30
            return (
              <div key={d.macroetapa} className="flex items-center gap-3">
                <div
                  className="text-white text-xs font-semibold flex items-center justify-center rounded-lg py-2 transition-all"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: `rgb(16, 185, ${Math.min(129 + (100 - intensity), 200)})`,
                    opacity: Math.max(intensity / 100, 0.35),
                  }}
                >
                  {d.total}
                </div>
                <span className="text-xs text-gray-600 dark:text-gray-400 flex-1 truncate">
                  {d.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

---

# FIM DO BRIEFING

Boa criação! Lembrar:
- Os 4 screenshots em anexo mostram o "antes"
- Os 3 arquivos `.tsx` acima são a fonte da verdade técnica
- Light + Dark, Executivo + Operacional = 4 telas mínimas a desenhar
- Não mexer em endpoints, tipos, hooks ou comportamentos
