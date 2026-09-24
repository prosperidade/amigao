---
name: redator/relatorio_preliminar_escopo
agent: redator
version: "1.0.0"
description: "Redator pré-contratação (ADR-074 §2): relatório preliminar e especificação de escopo a partir da Rota validada, com evidência por ID em cada afirmação."
applies_to:
  chains: ["gerar_proposta", "redator"]
---

## Contrato de evidência — ADR-074

Método determinístico, sem LLM nesta versão. O Redator não gera contrato (decisão 5) nem a peça
técnica definitiva (decisão 10): ela é pós-contratação.

## Entrada

Somente a Rota validada do caso (passos vivos, lápides com motivo) e a execução do motor jurídico
que a gerou (retrato de fatos, avaliações, fundamento por ID, ciências de alerta). O diagnóstico não
é premissa do escopo: conclusões em revisão entram como ressalva, com seus IDs.

## Método

1. Toda afirmação carrega ao menos uma evidência por ID resolvida no tenant e no caso:
   dispositivo e versão da fonte, observação, fonte primária, documento, avaliação de regra, ciência
   de alerta, execução do motor, Rota ou passo. Afirmação sem evidência resolvida não é emitida — a
   geração falha nomeando o ID.
2. Fundamento é por ID, nunca por semelhança. Passo validado sem dispositivo resolvido é incluído
   como decisão do consultor ("sem fundamento normativo por ID") e aparece também como lacuna.
3. "Não consta nos autos" é fato sobre os autos, não sobre o imóvel.
4. Fato desconhecido e regra indeterminada viram lacuna, com a avaliação que os declarou.
5. Passo removido vai para "fora do escopo" com o motivo registrado na remoção.
6. Cada geração é versão nova; a anterior fica superada e preservada.

## Relatório preliminar

Situação dos autos · achados do motor · alertas críticos e ciência · lacunas · caminho validado.

## Especificação de escopo

O que será feito (item de proposta) · orientações não cobradas (direção) · fora do escopo ·
premissas (Rota, execução do motor, estado do diagnóstico).

## Redação por LLM (futuro, dívida #283)

Poderá reescrever o `texto` de uma afirmação; nunca criar, remover ou trocar `evidencias`. O
validador de evidência é o mesmo.
