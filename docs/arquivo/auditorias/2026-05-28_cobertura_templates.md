# Cobertura de templates e base regulatória por DemandType

Gerado em: 2026-05-29.

Fonte planejada: `tools/check_template_coverage.py`.

Observação operacional: o banco configurado no `.env` (`127.0.0.1:55432`) não estava ativo nesta execução. A coluna `LegislationDocument com demand_type?` abaixo deve ser reemitida pelo script contra o banco de homologação/dev ativo. A cobertura de `WorkflowTemplate` foi derivada da seed Alembic `c4d5e6f7a8b9_sprint3_workflow_templates.py`.

| demand_type | WorkflowTemplate ativo? | LegislationDocument com demand_type? |
|---|---:|---:|
| car | sim | não verificado |
| retificacao_car | sim | não verificado |
| licenciamento | sim | não verificado |
| regularizacao_fundiaria | sim | não verificado |
| outorga | sim | não verificado |
| defesa | sim | não verificado |
| compensacao | sim | não verificado |
| exigencia_bancaria | sim | não verificado |
| prad | não | não verificado |
| sobreposicao | não | não verificado |
| supressao | não | não verificado |
| due_diligence | não | não verificado |
| arrendamento | não | não verificado |
| condicionantes_antigas | não | não verificado |
| misto | não | não verificado |
| nao_identificado | não | não verificado |

## Gaps

- Sem WorkflowTemplate ativo: `prad`, `sobreposicao`, `supressao`, `due_diligence`, `arrendamento`, `condicionantes_antigas`, `misto`, `nao_identificado`.
- Sem LegislationDocument especializado: não apurado nesta máquina porque o banco local não respondeu.

Este relatório não cria templates; apenas evidencia cobertura.
