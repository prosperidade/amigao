# Sprint A2-diagnostico C2 — Smoke E2E real

**Timestamp:** 2026-05-09 14:11:35 UTC
**Commit:** `ba5e4a4`
**Provider/modelo:** `gpt-4o-mini` (gpt-4o-mini via litellm/OpenAI)
**Cenários executados:** 2
**Custo total:** **$0.0002**

**Estratégia:** mock pesado de `DiagnosticoAgent._load_process_data` (Q5 da Fase 0) — preserva isolamento de DB. Cenários cobrem path A.1 (IA com gpt-4o-mini real) e A.2 (rules-based sem IA — custo zero).

## Tabela consolidada

| Cenário | AI on | OK? | review | model | tokens (in/out) | cost USD | sources | hipóteses | risco | dual-emit |
|---|---|---|---|---|---|---|---|---|---|---|
| `ai_on_rich_context` | True | ✅ | True | `gpt-4o-mini` | 490/205 | $0.0002 | 7 | 3 | alto | ✅ |
| `ai_off_rules_based` | False | ✅ | True | `—` | 0/0 | $0.0000 | 1 | 1 | medio | ✅ |

## Observações por cenário

### `ai_on_rich_context`

- **AI on:** True
- **`requires_review`:** True
- **Sources** (7): `document/1`, `document/2`, `document/3`, `document/4`, `legislation/Lei 12.651/2012`, `legislation/Lei 9.605/1998`, `legislation/Decreto 7.830/2012`
- **Hipóteses** (3):
    - Pendência no CAR (Cadastro Ambiental Rural)
    - Embargo ativo na propriedade
    - Auto de infração registrado pelo IBAMA
- **Lacunas** (0): _(vazio em V1, schema-only)_
- **Checklist** (3):
    - Regularizar o CAR junto à SEMAD-GO
    - Resolver o embargo através de medidas corretivas
    - Atender ao auto de infração emitido pelo IBAMA
- **Riscos** (1):
    - severidade=`alto` — Imóvel com pendências múltiplas e embargo ativo, necessitando de regularização ambiental urgente.
- **Metadata:** {"prioridade_acoes": ["Resolver o embargo", "Regularizar o CAR", "Atender ao auto de infração"], "observacoes": "A situação atual da propriedade pode resultar em penalidades severas e restrições de uso, sendo essencial a adoção imediata das ações de remediação."}
- **Latência:** 9329ms
- **Custo:** $0.0002

**Preview do `content`** (primeiros 200 chars):

> Imóvel com pendências múltiplas e embargo ativo, necessitando de regularização ambiental urgente.

### `ai_off_rules_based`

- **AI on:** False
- **`requires_review`:** True
- **Sources** (1): `manual/rules_engine`
- **Hipóteses** (1):
    - CAR nao cadastrado
- **Lacunas** (0): _(vazio em V1, schema-only)_
- **Checklist** (1):
    - Realizar inscricao no CAR
- **Riscos** (1):
    - severidade=`medio` — Diagnostico baseado em regras (IA indisponivel)
- **Metadata:** {"prioridade_acoes": [], "observacoes": "Diagnostico simplificado. Ative a IA para analise completa."}
- **Latência:** 0ms
- **Custo:** $0.0000

**Preview do `content`** (primeiros 200 chars):

> Diagnostico baseado em regras (IA indisponivel)

## Calibração `requires_review`

**2/2 cenários** retornaram `requires_review=True`.

**Por design.** O `DiagnosticoAgent` retorna `requires_review=True` **hardcoded** em ambos os paths (linha equivalente do `_build_payload`) — diagnóstico ambiental sempre precisa de validação humana antes de alimentar peças do redator. Mesma decisão arquitetural do redator (A2-redator-C2).

## Dual-emit (γ)

**2/2 cenários** preservam todas as 6 chaves antigas no payload (`situacao_geral`, `passivos_identificados`, `acoes_remediacao`, `prioridade_acoes`, `risco_estimado`, `observacoes`). Confirma que a estratégia γ está em pé — frontend `DiagnósticoResult` não quebra com AIJobs novos, e AIJobs históricos continuam renderizando.

---

**Nota:** smoke produzido via `scripts/smoke_a2_diagnostico.py` (Sprint A2-diagnostico-C2).