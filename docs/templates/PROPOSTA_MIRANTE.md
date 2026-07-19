# Template de Proposta — Padrão Mirante

> **Origem:** destilado dos documentos reais de proposta da Mirante Ambiental.
> **LGPD:** este template contém **ZERO dado pessoal real**. Todos os exemplos
> abaixo são **fictícios**. Os originais (com CPF/RG/conta bancária) **nunca**
> entram no repositório.
>
> **Como é usado:** o gerador (RedatorAgent) preenche os `{{placeholders}}`
> a partir da Rota validada + precificação (S5-A) e do Property Hub do caso.
> Placeholder não resolvido = **geração bloqueada** (nunca sai `[12]` ou
> `{{...}}` no documento final).
>
> **Rastreabilidade:** cada linha da tabela da Seção 3 carrega o
> `rota_passo_id` de origem (não impresso no PDF, mas persistido no registro
> de Saída). Ver ADR sobre "contrato nasce da proposta aceita".

---

## Convenção de placeholders

| Placeholder | Origem | Exemplo fictício |
|---|---|---|
| `{{tenant.razao_social}}` | Tenant (consultoria) | Mirante Consultoria Ambiental Ltda. |
| `{{tenant.cnpj}}` | Tenant | 00.000.000/0001-00 |
| `{{tenant.responsavel_tecnico.nome}}` | Tenant | Eng. Fictícia de Exemplo |
| `{{tenant.responsavel_tecnico.titulo}}` | Tenant | Engenheira Agrônoma |
| `{{tenant.responsavel_tecnico.crea}}` | Tenant | CREA-XX 000000/D |
| `{{cliente.nome}}` | Property Hub | Cliente Exemplo |
| `{{imovel.nome}}` | Property Hub | Fazenda Exemplo |
| `{{imovel.localizacao}}` | Property Hub | Município Exemplo / UF |
| `{{imovel.area_ha}}` | Property Hub | 349,9022 ha |
| `{{imovel.uso_atual}}` | Property Hub | Pecuária extensiva |
| `{{imovel.situacao_fundiaria}}` | Property Hub | Matrícula 0.000, Cartório de Exemplo |
| `{{imovel.historico}}` | Property Hub | Aquisição em 0000; sem passivo conhecido |
| `{{cliente.necessidade}}` | Property Hub / caso | Regularização do CAR e licenciamento |
| `{{proposta.numero}}` | Proposta | PROP-0000/2026 |
| `{{proposta.data}}` | Proposta | 00 de mês de 0000 |
| `{{passo.*}}` | Rota validada (item_proposta) | ver Seção 3 |
| `{{investimento.*}}` | Precificação (PRICE_TABLE) | ver Seção 5 |
| `{{condicoes.*}}` | Condições comerciais do tenant | ver Seção 6 |

---

# PROPOSTA TÉCNICA E COMERCIAL Nº {{proposta.numero}}

**{{tenant.razao_social}}** — CNPJ {{tenant.cnpj}}
Data: {{proposta.data}}
Cliente: {{cliente.nome}}
Imóvel: {{imovel.nome}}

---

## 1. Caracterização da Propriedade

| Item | Descrição |
|---|---|
| **Localização** | {{imovel.localizacao}} |
| **Área** | {{imovel.area_ha}} |
| **Uso atual** | {{imovel.uso_atual}} |
| **Situação fundiária** | {{imovel.situacao_fundiaria}} |
| **Histórico** | {{imovel.historico}} |
| **Necessidade do cliente** | {{cliente.necessidade}} |

> *Exemplo fictício preenchido:*
>
> | Item | Descrição |
> |---|---|
> | Localização | Município Exemplo / UF |
> | Área | 349,9022 ha |
> | Uso atual | Pecuária extensiva |
> | Situação fundiária | Matrícula 0.000, Cartório de Registro de Imóveis de Exemplo |
> | Histórico | Aquisição em 0000; CAR ativo; sem embargo conhecido |
> | Necessidade do cliente | Regularização ambiental e licenciamento da atividade |

---

## 2. Objetivo

{{proposta.objetivo}}

> *Exemplo fictício:* "Promover a regularização ambiental do imóvel rural
> denominado Fazenda Exemplo, contemplando a análise da situação atual, o
> saneamento das pendências identificadas e o encaminhamento do processo de
> licenciamento junto ao órgão ambiental competente."

---

## 3. O que será feito

> A tabela abaixo é gerada **a partir dos passos da Rota validada** (S5-A).
> Cada linha corresponde a um `item_proposta` e mantém rastreabilidade ao
> `rota_passo_id` de origem no registro de Saída.

| # | Etapa | Descrição |
|---|---|---|
{{#each passos}}
| {{this.ordem}} | {{this.titulo}} | {{this.descricao}} |
{{/each}}

> *Exemplo fictício preenchido (2 etapas):*
>
> | # | Etapa | Descrição |
> |---|---|---|
> | 1 | Diagnóstico ambiental | Levantamento documental e análise da situação regulatória do imóvel. |
> | 2 | Regularização do CAR | Retificação e adequação do Cadastro Ambiental Rural. |

---

## 4. Entregáveis

> Derivados dos entregáveis de cada passo da Rota (Seção 3).

{{#each passos}}
- {{this.entregavel}}
{{/each}}

> *Exemplo fictício:*
> - Relatório de diagnóstico ambiental.
> - CAR retificado e protocolado.

---

## 5. Investimento

**Valor total: {{investimento.total_formatado}}**

Forma de pagamento: {{investimento.forma_pagamento}}

{{#if investimento.parcelas}}
| Parcela | Vencimento | Valor |
|---|---|---|
{{#each investimento.parcelas}}
| {{this.numero}} | {{this.vencimento}} | {{this.valor_formatado}} |
{{/each}}
{{/if}}

> *Exemplo fictício:*
>
> **Valor total: R$ 00.000,00**
> Forma de pagamento: 50% na assinatura, 50% na entrega.
>
> | Parcela | Vencimento | Valor |
> |---|---|---|
> | 1 | Na assinatura | R$ 00.000,00 |
> | 2 | Na entrega | R$ 00.000,00 |

---

## 6. Condições Comerciais

- **Prazo de execução:** {{condicoes.prazo_execucao}}
- **Validade da proposta:** {{condicoes.validade}}
- **Limitações de escopo:** {{condicoes.limitacoes_escopo}}

> *Exemplo fictício:*
> - Prazo de execução: 00 dias corridos a partir da assinatura.
> - Validade da proposta: 30 dias a partir da data de emissão.
> - Limitações de escopo: não inclui taxas de órgãos, custas cartorárias
>   nem serviços topográficos, salvo previsão expressa acima.

---

_______________________________________________
**{{tenant.responsavel_tecnico.nome}}**
{{tenant.responsavel_tecnico.titulo}}
{{tenant.responsavel_tecnico.crea}}
{{tenant.razao_social}}
