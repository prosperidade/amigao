# Sprint A2-redator C2 — Smoke E2E real

**Timestamp:** 2026-05-09 05:02:08 UTC
**Commit:** `d0e0c4f`
**Provider/modelo:** `gpt-4o-mini` (gpt-4o-mini via litellm/OpenAI)
**Templates executados:** 7
**Custo total:** **$0.0030**

## Tabela consolidada

| Template | OK? | review | model_used | tokens (in/out) | cost USD | citations (total/valid) | sources | addressee | prazo+ato? |
|---|---|---|---|---|---|---|---|---|---|
| `prad` | ✅ | True | `gpt-4o-mini` | 203/903 | $0.0006 | 3/True | 3 | — | n/a |
| `memorial` | ✅ | True | `gpt-4o-mini` | 134/697 | $0.0004 | — | 1 | — | n/a |
| `oficio` | ✅ | True | `gpt-4o-mini` | 159/611 | $0.0004 | — | 2 | SEMAD-GO | n/a |
| `proposta` | ✅ | True | `gpt-4o-mini` | 152/632 | $0.0004 | — | 1 | — | n/a |
| `resposta_notificacao` | ✅ | True | `gpt-4o-mini` | 154/694 | $0.0004 | 3/True | 3 | SEMAD-GO | ✅ |
| `contrato` | ✅ | True | `gpt-4o-mini` | 141/959 | $0.0006 | — | 1 | — | n/a |
| `comunicacao` | ✅ | True | `gpt-4o-mini` | 104/218 | $0.0001 | — | 1 | Cliente Final | n/a |

## Observações por template

### `prad`

- **`requires_review`:** True
- **Schema:** `template=prad`, `document_type=prad` (alias preservado).
- **Sources:** 3
- **Legal citations:** 3
- **Citations evaluator:** total=3, valid=True, coverage=100%
- **Latência:** 22419ms
- **Custo:** $0.0006

**Preview do `content`** (primeiros 200 chars):

> # Plano de Recuperação de Área Degradada (PRAD) ⏎  ⏎ ## 1. Introdução ⏎  ⏎ O presente Plano de Recuperação de Área Degradada (PRAD) tem como objetivo a recuperação de 12 hectares de área degradada, localizada

### `memorial`

- **`requires_review`:** True
- **Schema:** `template=memorial`, `document_type=memorial` (alias preservado).
- **Sources:** 1
- **Legal citations:** 0
- **Citations evaluator:** skip (sem legal_data ou sem citação no texto).
- **Latência:** 16688ms
- **Custo:** $0.0004

**Preview do `content`** (primeiros 200 chars):

> **MEMORIAL DESCRITIVO DA FAZENDA BOA VISTA** ⏎  ⏎ **PROCESSO:** [Inserir número do processo] ⏎  ⏎ **1. IDENTIFICAÇÃO DO IMÓVEL** ⏎  ⏎ **1.1. Nome da Propriedade:** Fazenda Boa Vista   ⏎ **1.2. Localização:** Estado

### `oficio`

- **`requires_review`:** True
- **Schema:** `template=oficio`, `document_type=oficio` (alias preservado).
- **Sources:** 2
- **Legal citations:** 0
- **Citations evaluator:** skip (sem legal_data ou sem citação no texto).
- **Latência:** 7676ms
- **Custo:** $0.0004

**Preview do `content`** (primeiros 200 chars):

> **OFÍCIO N.º [NÚMERO DO OFÍCIO]**   ⏎ **[LOCALIDADE], [DATA]**   ⏎  ⏎ **À**   ⏎ **[NOME DO ÓRGÃO AMBIENTAL]**   ⏎ **[ENDEREÇO DO ÓRGÃO AMBIENTAL]**   ⏎ **[CIDADE - UF]**   ⏎  ⏎ **ASSUNTO:** Resposta à Notificação sob

### `proposta`

- **`requires_review`:** True
- **Schema:** `template=proposta`, `document_type=proposta` (alias preservado).
- **Sources:** 1
- **Legal citations:** 0
- **Citations evaluator:** skip (sem legal_data ou sem citação no texto).
- **Latência:** 11225ms
- **Custo:** $0.0004

**Preview do `content`** (primeiros 200 chars):

> # Proposta Comercial de Serviços de Consultoria Ambiental ⏎  ⏎ ## 1. Introdução ⏎  ⏎ A presente proposta tem como objetivo apresentar os serviços de consultoria ambiental a serem prestados à Fazenda Sol Nasce

### `resposta_notificacao`

- **`requires_review`:** True
- **Schema:** `template=resposta_notificacao`, `document_type=resposta_notificacao` (alias preservado).
- **Sources:** 3
- **Legal citations:** 3
- **Citations evaluator:** total=3, valid=True, coverage=100%
- **Subclass enriched:** ✅ `RespostaNotificacaoContent` (prazo_dias + ato_regulatorio populados).
- **Latência:** 9314ms
- **Custo:** $0.0004

**Preview do `content`** (primeiros 200 chars):

> **Resposta à Notificação/Auto de Infração Ambiental** ⏎  ⏎ **PROCESSO:** [Inserir número do processo] ⏎  ⏎ **CLIENTE:** [Inserir nome do cliente] ⏎  ⏎ **DATA:** [Inserir data] ⏎  ⏎ **À**   ⏎ [Nome do órgão ambiental re

### `contrato`

- **`requires_review`:** True
- **Schema:** `template=contrato`, `document_type=contrato` (alias preservado).
- **Sources:** 1
- **Legal citations:** 0
- **Citations evaluator:** skip (sem legal_data ou sem citação no texto).
- **Latência:** 25814ms
- **Custo:** $0.0006

**Preview do `content`** (primeiros 200 chars):

> **CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE CONSULTORIA AMBIENTAL** ⏎  ⏎ **PROCESSO: {}** ⏎  ⏎ **CLIENTE: Fazenda Águas Claras LTDA**   ⏎ **CNPJ: 12.345.678/0001-90** ⏎  ⏎ **Pelo presente instrumento particular, de um l

### `comunicacao`

- **`requires_review`:** True
- **Schema:** `template=comunicacao`, `document_type=comunicacao` (alias preservado).
- **Sources:** 1
- **Legal citations:** 0
- **Citations evaluator:** skip (sem legal_data ou sem citação no texto).
- **Latência:** 3015ms
- **Custo:** $0.0001

**Preview do `content`** (primeiros 200 chars):

> **COMUNICAÇÃO FORMAL** ⏎  ⏎ **PROCESSO:** [Inserir número do processo]   ⏎ **CLIENTE:** [Inserir nome do cliente]   ⏎  ⏎ **DATA:** [Inserir data]   ⏎  ⏎ **ASSUNTO:** Confirmação de Protocolo do Cadastro Ambiental R

## Calibração `requires_review`

**7/7 templates** retornaram `requires_review=True`.

**Por design.** O `RedatorAgent` retorna `requires_review=True` **hardcoded** em todos os templates (`app/agents/redator.py` no merge final do `execute()`) — peças formais sempre precisam de revisão humana antes de virar peça oficial. Não é o `citation_evaluator` forçando: tendo ou não citação inválida, o flag é `True`. O evaluator só acrescenta `citation_issues` + `citation_valid=False` no payload quando aplicável (e o frontend renderiza badge adicional 'Citações suspeitas').

---

**Nota:** smoke produzido via `scripts/smoke_a2_redator.py` (Sprint A2-redator-C2).