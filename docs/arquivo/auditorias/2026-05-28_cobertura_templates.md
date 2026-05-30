# Cobertura de templates e base regulatória por DemandType

Gerado em: 2026-05-30T17:42:40+00:00

Fonte: `tools/check_template_coverage.py`.

> Atualizado em 2026-05-30 com rodada real do script contra o banco dev ativo (`127.0.0.1:55432`). A versão anterior (2026-05-29) tinha a coluna de `LegislationDocument` como "não verificado" porque o Postgres local não respondia; agora as contagens são reais. Fecha a pendência (b) do PR 2.2.

| demand_type | WorkflowTemplate ativo? | LegislationDocument com demand_type? |
|---|---:|---:|
| car | sim | 12 |
| retificacao_car | sim | 7 |
| licenciamento | sim | 16 |
| regularizacao_fundiaria | sim | 5 |
| outorga | sim | 3 |
| defesa | sim | 8 |
| compensacao | sim | 10 |
| exigencia_bancaria | sim | 0 |
| prad | não | 2 |
| sobreposicao | não | 0 |
| supressao | não | 0 |
| due_diligence | não | 0 |
| arrendamento | não | 0 |
| condicionantes_antigas | não | 0 |
| misto | não | 0 |
| nao_identificado | não | 0 |

## Gaps

- Sem WorkflowTemplate ativo: prad, sobreposicao, supressao, due_diligence, arrendamento, condicionantes_antigas, misto, nao_identificado
- Sem LegislationDocument especializado: exigencia_bancaria, sobreposicao, supressao, due_diligence, arrendamento, condicionantes_antigas, misto, nao_identificado

Observação: este relatório não cria templates; apenas evidencia cobertura.
