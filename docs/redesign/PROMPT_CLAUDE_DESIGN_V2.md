# Briefing v2 para Claude Design — Redesign OUSADO do Dashboard Regente Ambiental

> **Atenção:** a v1 deste briefing foi rejeitada porque saiu "morno"
> (designs muito parecidos com o estado atual). Esta v2 inverte a
> filosofia: **lógica blindada, visual TOTALMENTE livre**. Não é
> pra refinar o que existe — é pra reinventar.

---

## 1. Manifesto do redesign

Imagine que o produto vai ser apresentado num pitch de Series B
em 2026 — tem que parecer **caro, novo, com personalidade**. O
dashboard atual é funcional mas genérico (cards retangulares,
sidebar à esquerda, header em cima, tudo num grid previsível).
**Quebre isso.** Se o resultado final lembrar o "antes", o
briefing falhou.

A audiência (consultora ambiental brasileira, 35-55) é
sofisticada e cansada de SaaS feios. Surpreenda.

---

## 2. Vibe visual obrigatória

### Estilo
- **Ousado e experimental** — glassmorphism, quebra de grid,
  tipografia mista (serif para títulos + sans para corpo),
  layouts assimétricos, sobreposições controladas, gradientes
- **Premium** — sensação de "produto novo, com personalidade
  forte", não startup mediana
- **Sutilmente orgânico** — referência ambiental sem clichê.
  Pode usar curvas, blobs sutis, texturas papel, mas SEM ícones
  de folhinha/árvore

### Paleta
- **Cor primária:** verde floresta escuro — algo entre
  `#1B5E20` (pine) e `#0F3D24` (forest deep). Mais sério e
  maduro que emerald-500. Combina com institucional.
- **Acento vibrante (use com coragem em pontos estratégicos):**
  escolha entre lime elétrico (#A3E635), salvia clara
  (#84CC16), ou um amarelo-ouro (#FACC15)
- **Neutros:** off-whites quentes (#FAF9F6, #F5F4ED) no light,
  e pretos esverdeados (#0A0F0A, #131A13) no dark — NÃO use
  cinza puro
- **Semânticos:** mantenha vermelho/âmbar/violeta para
  estados, mas com tons dessaturados/sofisticados

### Tipografia (proponha)
- Title: serif elegante (sugestões: Fraunces, Instrument Serif,
  GT Sectra) ou um sans display geométrico ousado (Geist,
  Inter Display)
- Body: sans neutra (Inter, Geist Sans, IBM Plex Sans)
- Misture os dois com confiança — títulos serif + corpo sans é
  uma marca visual forte

### Elementos visuais que QUERO ver explorados
- **Glassmorphism** em ao menos 2 blocos (frosted glass, blur,
  transparência sobre gradiente)
- **Cards com bordas irregulares** ou cantos assimétricos (tipo
  rounded-tl-3xl rounded-br-none)
- **Gradiente mesh** ou blobs sutis no fundo (estilo Stripe ou
  produtos da Linear)
- **Tipografia oversized** em pontos-chave (números KPI gigantes,
  letras como elementos gráficos)
- **Microinterações implícitas** — hover states com transform,
  parallax sutil, transições não-óbvias

---

## 3. O que ENTREGAR

### 3.1 Layouts alternativos
Proponha **2 ou 3 layouts distintos**, não variações do mesmo:

- **Layout A — "Comand Center"**: sidebar tradicional mas
  reinventada (talvez ícones flutuantes em vidro, label no
  hover), conteúdo principal em massive grid mosaic com
  blocos de tamanhos variados.
- **Layout B — "Editorial"**: topnav minimalista (sem
  sidebar), conteúdo em coluna central como uma revista
  digital, com hero da IA dominando metade superior da tela.
- **Layout C — "Surface"**: command-palette-first (search/
  Cmd+K como entrada principal), KPIs como faixa horizontal
  superior, conteúdo abaixo em layers/abas tipo zellij.

Sinta-se livre pra propor outros conceitos — só não me devolva
3 variações do dashboard atual.

### 3.2 Cada layout em 4 telas
Para o layout que mais te empolgar, entregue:
- Dashboard Executivo — Light
- Dashboard Executivo — Dark (assuma dark como protagonista)
- Dashboard Operacional — Light
- Dashboard Operacional — Dark

Para os outros 1-2 layouts, basta 1 tela cada (Executivo Dark
serve) — só pra eu entender o conceito.

### 3.3 Biblioteca de componentes
- StatCard reinventado (não card retangular com ícone no canto)
- StageCard (etapa de processo) — repensar
- AlertCard
- AISummaryCard com glassmorphism / gradiente mesh
- FunnelChart com personalidade (não o degrau verde óbvio)
- Toggle dark/light (precisa ser desenhado — ele não existe no
  código atual, é nova funcionalidade)
- Header com toggle de view (Executivo/Operacional)

---

## 4. ⚠️ Anti-padrões — coisas que vão fazer o cliente reprovar

Se o seu design tiver QUALQUER destas características, refaça:
- ❌ Sidebar fixa à esquerda com lista de ícones tradicional
  (já é assim, é o que ele NÃO quer)
- ❌ Header com saudação + botões "Novo X" no canto direito
  (cliché de SaaS)
- ❌ Grid 4×2 de KPIs idênticos
- ❌ Cards retangulares com ícone colorido no canto superior direito
- ❌ Verde emerald-500 saturado em botões grandes
- ❌ Tudo `bg-white` com `border-gray-100` e `rounded-xl`
- ❌ Lista vertical genérica com badge à direita
- ❌ Skeleton loading com `animate-pulse` cinza
- ❌ Tipografia 100% sans-serif, todos os tamanhos próximos
- ❌ Sombras `shadow-sm` em todos os cards igualmente

---

## 5. Dados disponíveis (única coisa intocável)

Estes são os tipos que o backend retorna. Use TODOS eles na
composição visual (não esconda dados), mas a FORMA de mostrar
é 100% sua decisão — pode virar gráfico, animação, lista,
mosaico, sparkline, o que fizer sentido.

### View Executivo

```ts
ExecutivoDashboard {
  active_processes: number          // ex: 21
  total_clients: number             // ex: 19
  total_properties: number          // ex: 12
  overdue_tasks: number             // ex: 3
  conversion_rate: number           // 0 a 1, ex: 0.42
  faturamento: number               // BRL, ex: 47900
  risco_medio: number | null        // 0 a 10, ex: 0.2
  processes_by_status: [{status, count}]      // distribuição
  processes_by_demand_type: [{status, count}] // distribuição
  proposal_pipeline: [{status, count, total_value}]
  recent_activities: [...]
  my_pending_tasks: [...]
}

DashboardAISummary {
  text: string                      // parágrafo executivo gerado por IA
  recommendation: string | null     // sugestão acionável
  top_stage_bottleneck_label: string | null
  critical_pending_count: number
  ready_to_advance_count: number
}

StageDistribution {              // 7 etapas
  label: string                  // "Entrada da Demanda", "Diagnóstico", etc.
  total: number
  blocked: number                // travados
  ready_to_advance: number       // prontos pra avançar
  avg_days_in_stage: number | null
}

DashboardAlert {
  severity: 'low' | 'medium' | 'high' | 'critical'
  label: string
  count: number
}

DashboardPriorityCase {
  client_name: string
  property_name: string | null
  macroetapa_label: string
  urgency: 'critica' | 'alta' | 'media' | 'baixa'
  priority_reason: string         // motivo da prioridade
  next_step: string | null
  responsible_user_name: string | null
}
```

### View Operacional

```ts
OperacionalDashboard {
  my_pending_tasks_count: number
  my_overdue_tasks_count: number
  documents_needing_review: number
  processes_aguardando_orgao: number
  my_pending_tasks: [...]
  documents_for_review: [...]
  expiring_documents: [...]       // com expires_at, urgency
  process_alerts: [...]
  recent_activities: [...]
}

Kpi {                              // 8 KPIs operacionais
  key: string
  label: string                    // "Clientes Ativos", "Em Diagnóstico", etc.
  value: number
  delta_pct: number | null         // variação % do período
  hint: string | null
}

VigiaAlert {                       // alertas do agente IA "Vigia"
  severity: 'error' | 'warning'
  message: string
  process_id: number
}

AgentMetrics {                     // métricas dos agentes IA (hoje)
  total_executions: number
  success_rate: number             // 0 a 100
  total_cost_usd: number
  needs_review_count: number
  failed_count: number
}
```

### Conteúdos textuais que existem no produto
- "Olá, {Nome}" como saudação
- "Visão estratégica do negócio" / "Visão operacional do dia a dia"
- "Leitura executiva da IA" (label do bloco IA)
- Etapas: Entrada da Demanda, Diagnóstico Preliminar, Coleta
  Documental, Diagnóstico Técnico, Caminho Regulatório,
  Orçamento e Negociação, Contrato e Formalização
- Demandas: CAR, Retificação CAR, Licenciamento, Regularização,
  Outorga, Defesa, Compensação, PRAD

---

## 6. Liberdades EXPLÍCITAS (use sem pedir licença)

- **Reorganize a ordem dos blocos** livremente
- **Mude os nomes visuais** dos blocos se ficar melhor (ex:
  "Casos por Etapa" → "Pipeline"); só preserve o significado
- **Crie blocos novos** que combinem dados de jeitos não-óbvios
  (ex: um "Pulso do Dia" que mistura KPIs + IA Summary +
  prioridades num único bloco hero)
- **Esconda blocos secundários** atrás de tabs/drawer se
  ajudar a hierarquia
- **Use bibliotecas de gráfico** modernas (recharts, tremor,
  visx) — não precisa ser CSS puro
- **Adicione animações** (framer-motion, lottie sutis)
- **Quebre o grid** — alturas variáveis, larguras quebradas,
  cards que sangram pra fora do container
- **Dark first** — desenhe o dark mode primeiro, light como
  variação. O dark deve ser o estado "padrão de quem usa
  diariamente"

---

## 7. Stack de implementação (pra quando virar código)

React 18 + Vite + TypeScript + TailwindCSS + lucide-react.
Use tokens compatíveis com Tailwind sempre que possível, mas
pode pedir:
- `framer-motion` para animações
- `recharts` ou `tremor` para gráficos
- Fontes via Google Fonts ou next/font equivalente
- Imagens/blobs SVG inline ou via `@/assets`

A lógica de dados (React Query, endpoints, tipos) já está
pronta — você só precisa entregar a CASCA visual. Não se
preocupe com como os dados chegam — eles chegam.

---

## 8. Referências visuais (inspiração, não cópia)

- **Linear.app** — para densidade e dark mode sofisticado
- **Vercel dashboard** — para minimalismo premium
- **Arc Browser** — para curvas, profundidade, micro-delights
- **Stripe.com** — para tipografia e gradientes mesh
- **Loops.so** — para glassmorphism funcional
- **Cron Calendar** (antigo) — para tipografia mista serif+sans
- **Raycast** — para command-palette-first

---

## FIM

Anexos esperados: 4 screenshots do estado atual (em
`docs/redesign/screenshots/`) — eles servem APENAS pra você
entender o que NÃO fazer. Trate como anti-referência.

Bora ousar.
