# ADR-028 — A proposta nasce da Rota validada (PRICE_TABLE vira precificação) + máquina de estados

- **Status:** Aceita
- **Data:** 2026-07-18
- **Espec de origem:** Ficha 07 §7–§8 (E5 Caminho Regulatório → E6 Orçamento/Negociação);
  Sprint 5-A. Critério: "a proposta nasce da Rota, não da tabela".
- **Relacionada a:** #92 (Rota E5 — entidade/passos), ADR-019 (ramo E2), gates
  `has_rota_validada`/`has_proposal_accepted` (Fase 0, item 9), Princípios 1 (IA
  propõe, humano decide) e 2 (tudo auditável).

## Contexto

O gerador legado (`proposal_generator.py`, "Sprint 4") criava o escopo a partir de
uma `PRICE_TABLE` estática: cada `demand_type` tinha um `scope_base` fixo (lista de
strings), e a proposta repetia esses itens genéricos. O escopo real do caso — os
passos que o consultor validou na **Rota Regulatória (E5)** — não alimentava a
proposta. Resultado: a proposta não refletia o trabalho caracterizado, e não havia
rastreabilidade item→passo. A caracterização (item 1, commit congelado) media isso:
cobertura de proposal era ZERO e o escopo vinha da tabela.

A máquina de estados também era frouxa: aceitava uma proposta direto do rascunho,
a recusa não gerava renegociação, e o estado `expired` existia no enum mas nenhum
fluxo o atribuía (validade vencida sem efeito).

## Decisão

**1. Escopo nasce da Rota validada.** `generate_proposal_from_rota` substitui o
gerador legado: cada `RotaPasso` classificado como `item_proposta` (faturável) vira
um item de escopo, ordenado por `ordem`, **rastreável** (`scope_items[].rota_passo_id`
aponta o passo de origem; carrega também `norma_ref` e `prazo_dias`). Passos
`direcao` (orientação) NÃO entram no escopo cobrável. Sem Rota validada — ou Rota
validada sem passo faturável — a geração é **bloqueada** com mensagem honesta
(HTTP 422), coerente com o gate E5→E6 (`has_rota_validada`).

**2. PRICE_TABLE muda de papel: escopo → precificação.** A tabela deixa de ser a
FONTE do escopo (`scope_base` aposentado) e passa a PRECIFICAR: a faixa
(min/max/prazo) por demanda × complexidade sugere o valor da rota, distribuído
entre seus itens faturáveis como preço unitário default (editável pelo consultor;
o ajuste de arredondamento fecha no último item). A complexidade segue derivada de
sinais objetivos (`_estimate_complexity`: urgência, docs pendentes, nº de tarefas).

**3. Máquina de estados explícita.** `rascunho → enviada → aceita | recusada |
expirada`. Aceitar/recusar exigem `enviada` (a permissividade rascunho→aceita foi
removida). Transições auditadas (quem/quando, hash chain). A validade conta a
partir do ENVIO.

**4. Expiração DERIVADA no read (sem cron).** `effective_status` calcula `expirada`
quando uma proposta `enviada` tem `expires_at` vencido — nada de job novo; o estado
efetivo viaja no serialize e nas guardas (aceitar expirada é bloqueado). O status
persistido permanece `sent` (a expiração é uma leitura do relógio, não uma escrita).

**5. Renegociação com histórico.** `POST /proposals/{id}/nova-versao` gera a versão
N+1 a partir de uma recusada/expirada: nova em rascunho, `previous_version_id`
apontando a anterior, `version_number` incrementado. A anterior é **preservada**
(nunca sobrescrita) — a linhagem de negociação fica auditável.

**6. Gate E6 intocado.** `has_proposal_accepted` continua lendo `status == accepted`.
O S5-A mudou COMO o escopo nasce e COMO os estados transitam, não o contrato do
gate — E6→E7 segue exigindo proposta aceita.

## Consequências

**Positivas**
- A proposta reflete o trabalho real (passos validados), com rastreabilidade
  item→passo — base para o contrato do S5-B espelhar o escopo aceito.
- A tabela de preços não inventa mais escopo; o valor é sugestão editável sobre um
  escopo verdadeiro.
- Renegociação e expiração deixam de ser buracos: histórico preservado, validade
  com efeito.

**Custos / riscos residuais**
- Precificação por distribuição igualitária da faixa entre itens é um DEFAULT
  grosseiro (editável) — precificação fina por tipo de item é follow-on.
- Multi-demanda (várias Rotas validadas no mesmo processo) agrega os passos e
  soma as faixas; `rota_id` no nível da proposta fica nulo nesse caso (a
  rastreabilidade fina permanece no item). Bloco único multi-titular é dívida do
  S5-B.
- O gerador legado (`generate_proposal_draft`) foi removido; qualquer consumidor
  externo deve usar `generate_proposal_from_rota`.

## Validação

- `tests/api/test_proposal_rota_s5a.py` — escopo rastreável, bloqueio sem Rota /
  sem passo faturável, precificação (1200 distribuído), transições, renegociação
  com histórico, expiração derivada, gate E6 intacto.
- `tests/api/test_proposal_caracterizacao.py` — comportamento preservado (criação
  em rascunho com validade; edição só em rascunho).
- Gates E5/E6/E7: `tests/services/test_macroetapa_engine_rota_proposta_contrato.py`
  mantido verde. Migration `d4b8e2f1a6c9` up→down→up limpa.
