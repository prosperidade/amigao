---
name: extrator/_template
agent: extrator
version: "0.1.0"
description: "Placeholder técnico — não usar em produção. Valida que o pipeline de skills carrega corretamente."
applies_to:
  demand_types: ["template"]
  doc_types: ["template"]
---

# Skill placeholder — extrator

Esta skill existe apenas para validar que o registry descobre, parseia e injeta
o conteúdo no system prompt. Ela só é ativada quando `ctx.metadata.demand_type == "template"`
e `ctx.metadata.doc_type == "template"`.

Skills reais de domínio (matricula_generica, car_sicar, etc.) chegam na Sprint A3,
quando os PDFs-gabarito da sócia forem fornecidos.
