---
name: redator/_template
agent: redator
version: "0.1.0"
description: "Placeholder técnico — não usar em produção. Valida que o pipeline de skills carrega corretamente."
applies_to:
  demand_types: ["template"]
  doc_types: []
---

# Skill placeholder — redator

Esta skill existe apenas para validar que o registry descobre, parseia e injeta
o conteúdo no system prompt. Ela só é ativada quando `ctx.metadata.demand_type == "template"`.

Skills reais de domínio (oficio_semad, memorial_car, prad, etc.) chegam na Sprint A3,
quando os PDFs-gabarito da sócia forem fornecidos.
