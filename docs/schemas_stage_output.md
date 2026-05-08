# Schemas Pydantic para `StageOutput.content_data`

**Sprint:** A1 (Tarefa C)
**Status:** opt-in. Adoção real nos agentes fica para Sprint A2.

## Contexto

O modelo SQLAlchemy [`app/models/stage_output.py`](../app/models/stage_output.py) tem o campo `content_data` (`PortableJSON`) sem schema obrigatório — gap **B2** do audit `docs/AUDITORIA_FLUXO_2026-04-29.md`. Esta sprint introduz o **contrato de conteúdo** em Pydantic v2, validável tanto na API quanto no `BaseAgent.run()`, sem migrar agentes existentes.

## Arquitetura

```
StageOutputContent              (base — content/metadata/sources/confidence)
├── DiagnosticoPreliminarContent (hipóteses/lacunas/riscos/checklist)
├── PecaJuridicaContent          (template/legal_citations/addressee)
│   └── RespostaNotificacaoContent (+ prazo_dias/ato_regulatorio)
```

Tipos auxiliares:

- `Source(type, ref, excerpt?)` — onde `type ∈ {legislation, document, manual}`.
- `CitationRef(kind, numero, ano, raw, chunk_id?)` — referência canônica a uma norma legal. Reusada pelo evaluator de citação (Tarefa B); o campo `chunk_id` referencia `knowledge_catalog.id` quando a citação é validada contra o RAG.
- `Risco(descricao, severidade, mitigacao_sugerida?)` — `severidade ∈ {baixo, medio, alto}`.

## Validações

| Campo | Regra |
|---|---|
| `sources` | Lista **não vazia**. Pelo menos 1 `Source` obrigatória — força "evidence ou nada" no output do agente. |
| `confidence` | Quando presente, deve estar em `[0.0, 1.0]`. |
| `CitationRef.ano` | `1500 ≤ ano ≤ 3000`. |
| `RespostaNotificacaoContent.prazo_dias` | `≥ 0`. |
| Todos os schemas | `extra="forbid"` — campo desconhecido falha fast (evita drift silencioso). |

## Como usar

### Construção válida

```python
from app.schemas.stage_output import (
    PecaJuridicaContent, Source, CitationRef,
)

content = PecaJuridicaContent(
    content="Em atenção à notificação...",
    sources=[Source(type="legislation", ref="knowledge_chunk_42")],
    template="oficio",
    legal_citations=[
        CitationRef(kind="lei", numero="12.651", ano=2012, raw="Lei nº 12.651/2012", chunk_id=42),
    ],
    addressee="SEMAD-GO",
    confidence=0.85,
)
```

### Persistir em `StageOutput.content_data`

```python
from app.models.stage_output import StageOutput

output = StageOutput(
    tenant_id=tenant_id,
    process_id=process_id,
    macroetapa="diagnostico_preliminar",
    output_type="peca_oficio",
    title="Ofício SEMAD nº 123",
    content=content.content,             # texto plain para busca/listagem
    content_data=content.model_dump(),   # JSON estruturado
    produced_by_agent="redator",
)
```

### Aceitar formato legado e novo

Em quem consome o output:

```python
from pydantic import ValidationError
from app.schemas.stage_output import StageOutputContent

raw = stage_output.content_data
try:
    parsed = StageOutputContent.model_validate(raw)
except ValidationError:
    # formato legado ainda é dict[str, Any] — caller decide o caminho
    parsed = None
```

## Migração futura (Sprint A2)

A migração dos 5 agentes para o `StageOutputContent` é incremental:

1. `extrator` — produz `StageOutputContent` simples (mais barato).
2. `atendimento` — idem.
3. `diagnostico` → `DiagnosticoPreliminarContent`.
4. `redator` → `PecaJuridicaContent` ou `RespostaNotificacaoContent` conforme `document_template`.
5. `legislacao` — produz `StageOutputContent` com `sources` apontando para chunks do `knowledge_catalog`.

Cada um vira um sub-commit; os outros continuam aceitando `dict` enquanto não migram.

## Decisões da Fase 0 aplicadas

- **Q5:** `StageOutputContent` (não `StageOutputBase`) — não colide visualmente com `app.models.stage_output.StageOutput`.
- **Q1:** continua usando `StageOutput.content_data` (JSONB do ORM existente) — não há `AIJob.output_data` separado.
- **Risk #5:** sem tabela associativa N-N — `RegulatoryDiagnosis` (Tarefa D) referencia issues via lista de IDs no próprio `content`.
