# Ficha 07 — Aba Ações + Quadro de Ações global

> Onde o diagnóstico vira trabalho. **A IA propõe a ação; o consultor decide.**

- **Branch:** `feat/ficha07-aba-acoes`
- **Decisões de domínio:** Isis, 16/06/2026
- **ADR:** [ADR-016 — Concluir uma ação NÃO resolve o passivo](../adr/016-acao-nao-resolve-passivo.md)

## O que entrou

Uma entidade nova, `Acao`, e duas telas: a **aba Ações** do workspace do caso e o **Quadro de Ações
global** (kanban por status, todos os casos do tenant).

Cada ação de remediação proposta pelo diagnóstico (com fonte — contrato #70) vira uma `Acao`
`pendente` aguardando **triagem** do consultor: vira **tarefa** interna, vira **escopo** de venda
(candidata a item da proposta), ou é **dispensada**. Criação manual também é suportada.

## Decisões fechadas (Isis 16/06)

1. **Responsável** — sem responsável no MVP (campo `—`). `responsavel_id` é **nullable**, modelado
   para ligar à entidade Usuário quando o **Bloco 0** (multi-tenant de usuários) entrar. Não bloqueia
   a tela agora.
2. **Quadro global** — kanban por **status**: `a_fazer` · `em_andamento` · `concluida` · `bloqueada`.
3. **Ação × Passivo** — concluir uma ação **NÃO** marca o passivo como resolvido (ver ADR-016). A
   ação **referencia** o passivo (`vinculo_passivo`, rastreabilidade), mas concluí-la é só "trabalho
   interno feito". **Nenhum** mecanismo altera o status do passivo/achado a partir da ação.

## Modelo

`Acao` (tabela `acoes`) — campos: `titulo`, `descricao`, `origem` (diagnostico/auditor/manual),
`origem_descricao` (texto do passivo), `origem_fontes` (lista de `SourceRef` #70), `vinculo_passivo`
(JSON solto, sem FK), `responsavel_id` (nullable), `prazo`, `prioridade` (alta/media/baixa),
`status` (a_fazer/em_andamento/concluida/bloqueada), `tipo_triagem`
(pendente/tarefa/escopo/dispensada), `dedupe_key` (idempotência), `tenant_id`, `process_id`,
timestamps. Migration: `ac7f01b9e3d5_ficha07_acoes`.

Detalhe em [MODELO_DE_DADOS](../arquitetura/MODELO_DE_DADOS.md#acao-ficha-07).

## Geração a partir do diagnóstico

`POST /processes/{id}/acoes/generate` lê o diagnóstico mais recente (`RegulatoryDiagnosis`) e cria
ações `pendente` de duas fontes, ambas com fonte #70:

- `riscos[*].proximo_passo` (ou `mitigacao_sugerida` legado) — passivo = o próprio risco; fonte =
  `risco.sources`.
- `afirmacoes[*]` com `categoria="acao"` — fonte = `afirmacao.fontes`.

**Idempotente**: `dedupe_key = hash(process + passivo + título)`, estável entre versões do
diagnóstico — regerar não duplica. Sem fonte identificável, injeta uma `SourceRef` `sem_fonte`
(nunca inventar fonte).

## Triagem (Princípio 1)

`POST /processes/{id}/acoes/{acaoId}/triagem` com `{decisao: "tarefa"|"escopo"|"dispensar"}`.
`escopo` **apenas marca** a ação como candidata a item de proposta — a ponte com o Orçamento é
consumida depois (**não** construímos o Orçamento aqui).

## Telas

- **Aba Ações** (`AcoesTab`) — lista as ações do caso, filtra por status e triagem, botão "Gerar do
  diagnóstico", criação manual, e por card: origem com fonte (chips), prioridade, prazo, status
  editável, botões de triagem. Responsável aparece `—`.
> **Revertido em 2026-06-28:** o "Quadro de Ações global" (`/acoes`, `QuadroAcoesGlobal`) e a
> renomeação do board `/processes` para "Casos" foram **desfeitos**. O sidebar voltou ao item único
> **"Quadro de Ações" → `/processes`** (board de casos por macroetapa). O componente
> `QuadroAcoesGlobal`, os hooks `useAcoesKanban`/`useMoveAcaoStatus`, os tipos `AcaoKanban*` e o
> endpoint `GET /acoes/kanban` foram **removidos** (código órfão, sem consumidor). A aba **Ações**
> do workspace (abaixo) e o restante do backend Ficha 07 permanecem. Ver
> `docs/trabalhos/reverter_sidebar.md`.

## Endpoints

Ver [API_v1](../arquitetura/API_v1.md#acoes-ficha-07). Fluxo E2E em
[FLUXOS_E2E](../arquitetura/FLUXOS_E2E.md#diagnostico-acao-triagem-ficha-07).

## Proibições respeitadas

- Nenhum mecanismo altera status de passivo/achado a partir da ação (ADR-016).
- Não construímos o Orçamento — `escopo` só marca.
- Não acoplamos à entidade Usuário (`responsavel` nullable, sem depender do Bloco 0).
- Contrato de fontes #70 preservado (reuso de `SourceRef`).

## Validação

Suíte `tests/api/test_acoes.py` (10 testes): geração com fonte, idempotência, triagem, conclusão não
altera o passivo, quadro global com caso de origem, tenant isolation. `tsc` + `build` verdes.
