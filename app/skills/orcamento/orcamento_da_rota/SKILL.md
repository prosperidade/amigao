---
name: orcamento/orcamento_da_rota
agent: orcamento
version: "1.0.0"
description: "Orçamento derivado da Rota validada (ADR-074 §4): um item por passo faturável, métodos e preços do tenant, totais determinísticos."
applies_to:
  chains: ["gerar_proposta", "orcamento"]
---

## Contrato de evidência — ADR-074

O Orçamento não é segunda fonte de escopo (decisão 6): a Rota validada manda. Método
determinístico, sem LLM.

## Entrada

Especificação de escopo aprovada e atual · Rota validada · métodos e preços do tenant (versão
corrente) · escolhas do consultor por passo.

## Método

1. Um item por passo vivo, validado e classificado como item de proposta. O item aponta o passo.
2. Passo removido não é cobrado e aparece em "fora do orçamento" com o motivo. Passo de direção
   não é cobrado.
3. Método do item: escolha do consultor → método mapeado à regra que originou o passo → método
   padrão do tenant. Sem método padrão, recusa; nunca preço de código.
4. Total do item = quantidade × valor unitário, em centavos, arredondamento meio-para-cima. Total do
   orçamento = soma dos itens. O consultor escolhe método e quantidade; nunca digita total.
5. Unidades: hora, fixo, unidade. Hectare fica fora até a medição canônica (Plano §6.1).
6. Diagnóstico em revisão é ressalva registrada, não bloqueio.
7. Orçamento desatualizado não retrocede etapa: marca, explica e espera o gesto do consultor.
