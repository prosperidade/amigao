# Briefing para Claude Design — Redesign do Dashboard Regente Ambiental

> **Como usar:** abra o Claude Design / Figma e cole TODO o conteúdo
> abaixo (do título "Redesign do Dashboard" até o final). Anexe os
> 4 screenshots de `docs/redesign/screenshots/` como referência do
> estado atual ("antes").

---

# Redesign do Dashboard — Regente Ambiental

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
   - Cada card: label + número grande + ícone + delta opcional

3. Barra de filtros (3 chips de view + selects: urgência,
   demanda, UF, período)

4. AI Summary Card (DESTAQUE)
   - Fundo gradiente sutil (violet → sky → emerald)
   - Ícone Sparkles + label "Leitura executiva da IA"
   - Parágrafo de análise + recomendação destacada em verde

5. Casos por Etapa (grid 4 colunas com 7-8 cards)
   - Cada card: label + total grande + tempo médio + badges
     (🚫 travados / ✓ prontos para avançar)

6. Sidebar direita: Gargalos e Alertas
   - Lista de cards coloridos por severidade

7. Casos Prioritários do Dia (lista vertical clicável)
   - Cliente · propriedade · badge etapa · razão da prioridade
   - Próximo passo destacado em verde

8. Atividades Recentes (2/3) + Pipeline de Propostas (1/3)

9. 2 gráficos lado a lado: Processos por Status + por Demanda
   (barras horizontais com %)

10. Minhas Tarefas

### View 2: OPERACIONAL (visão do dia a dia)
1. Mesmo header

2. Filtros pill (Período + Tipo de demanda)

3. 8 KPI Cards em grid 4×2
   - Clientes Ativos | Casos Ativos | Em Diagnóstico | Em Coleta
   - Em Caminho Regulatório | Propostas | Contratos | Formalizados
   - Cada card: ícone colorido + label + número + delta % com
     seta (verde sobe, vermelho desce)

4. Dois gráficos lado a lado:
   - Casos por Etapa (barras horizontais simples)
   - Funil Operacional (degraus decrescentes em gradiente verde)

5. Banner de alertas do Vigia (agente IA)
   - Cards horizontais por severidade

6. Grid 3 colunas: Minhas Tarefas | Documentos para Revisão |
   Métricas dos Agentes IA (hoje)
   - Card IA tem 4 mini-stats em grid 2×2: Execuções, Taxa
     Sucesso, Custo USD, Revisão Pendente

7. Grid 2 colunas: Documentos Expirando | Alertas de Processo

8. Atividades Recentes

## Tipos de gráficos a desenhar
- Cards numéricos com delta % (KPIs)
- Barras horizontais com porcentagem (distribuições)
- Funil em degraus com gradiente (conversão por etapa)
- Lista de alertas com badge de severidade
- Cards de etapa com mini-badges contadores
- Pipeline com valor monetário por estágio
- Quero gráficos onde fizerem sentido — não force gráfico
  onde uma lista é mais clara

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

## ⚠️ INTOCÁVEL — lógica, dados e integrações

Este é um redesign PURAMENTE VISUAL. Tudo que está abaixo
DEVE permanecer idêntico ao código atual. Se o redesign exigir
mudar qualquer item desta lista, ELE ESTÁ ERRADO — refaça.

### Endpoints de API (não renomear, não remover, não criar novos)
- GET /dashboard/summary?view=executivo|operacional
- GET /dashboard/stages
- GET /dashboard/alerts
- GET /dashboard/priority-cases
- GET /dashboard/ai-summary
- GET /dashboard/kpis
- GET /ai/jobs (usado por AgentMetricsCard e VigiaAlertsBanner)

### Hooks e bibliotecas (manter exatamente como está)
- @tanstack/react-query — todas as chamadas via useQuery
- staleTime atual de cada query (30s, 60s, 300s) — preservar
- queryKeys atuais — preservar para não invalidar cache
- zustand store useAuthStore — leitura de user
- react-router-dom — useNavigate para todas as ações
- lib/api.ts — único cliente HTTP, NUNCA fetch/axios direto

### Contratos TypeScript (campos exatos, nomes exatos)
- ExecutivoDashboard, OperacionalDashboard, RecentActivity,
  PendingTask, StatusDistribution, ProposalPipelineItem,
  DocumentAlert, ProcessAlert
- StageDistribution, DashboardAlert, DashboardPriorityCase,
  DashboardAISummary, DashboardFilters
- Kpi, KpisResponse
Não alterar nomes de campos. Não inventar campos novos. Se um
campo não está nos tipos, ele NÃO vem do backend.

### Comportamentos preservados
- Toggle Executivo/Operacional troca a view (estado local)
- viewMode persiste apenas em memória (não em localStorage)
- StatCard com onClick → navigate para rota
- Cliques em activity/task/doc/alert → navigate(`/processes/${id}`)
- Botão "Novo Caso" → navigate('/intake')
- Botão "Fluxo" → navigate('/processes')
- Filtros do DashboardRegente alteram queryString das queries
- AIBlock fica oculto/skeleton enquanto carrega
- VigiaAlertsBanner só aparece se houver alertas
- Cores de severidade (critical/high/medium/low) mantêm semântica
- Loading states com skeletons (não esconder a UI inteira)

### Consumidores externos (não quebrar)
- PrivateLayout envolve o Dashboard — o redesign vive DENTRO
  desse layout, não substitui o sidebar nem o topbar
- Rota /dashboard em App.tsx aponta para o default export
  de pages/Dashboard/index.tsx — manter esse default export

### Estrutura de arquivos
- Manter os 3 arquivos:
  - pages/Dashboard/index.tsx (orquestrador)
  - pages/Dashboard/DashboardRegente.tsx (blocos executivos)
  - pages/Dashboard/DashboardOperacionalRegente.tsx (operacional)
- Novos componentes visuais podem ser extraídos para
  pages/Dashboard/components/ — não espalhar em src/components/

### Permitido mudar livremente
- Classes Tailwind (cores, espaçamentos, tipografia, layout)
- Estrutura JSX interna dos componentes
- Adicionar bibliotecas de gráficos se necessário (sugestão:
  recharts ou tremor — ambos compatíveis com a stack)
- Adicionar animações sutis (framer-motion permitido)
- Reorganizar a ORDEM visual dos blocos dentro da mesma view
- Tema dark/light via classe `dark:` do Tailwind (já configurado)
