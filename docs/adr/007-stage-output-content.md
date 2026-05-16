# ADR-007 · StageOutputContent — schema validado para saídas de agente

**Status:** Aceito
**Data:** 2026-05-08 (Sprint A1); formalizada como ADR em 2026-05-15
**Decisores:** tecnologia
**Relacionado:** [`./002-multi-llm-gateway.md`](./002-multi-llm-gateway.md), [`./006-skills-procedurais.md`](./006-skills-procedurais.md)

---

## Contexto

Nas Sprints iniciais (IA-1 a IA-4), cada agente emitia resultado em formato livre dentro de `AIJob.result` (JSONB). Funcionava, mas criava três problemas crescentes:

1. **Consumidor à mercê do produtor.** Frontend tinha que adivinhar campos por agente, com fallbacks proliferando. Mudança em um agente quebrava UI silenciosamente.
2. **Chains frágeis.** Quando o `LegislacaoAgent` alimentava o `RedatorAgent` numa chain, o segundo lia campos do primeiro sem garantia de existência. Em runtime, ausência virava bug obscuro.
3. **Audit pobre.** Sem schema declarado, era difícil saber "o que esse agente promete entregar" sem ler código.

Três caminhos:

1. **Dict livre + documentação** — manter `result` como JSONB sem validação
2. **TypedDict / dataclass simples** — declarar formato em Python sem runtime validation
3. **Pydantic v2 schema com discriminator** — validar runtime + emitir em formato auditável

## Decisão

**Pydantic v2 `StageOutputContent` base + derivados por tipo de saída.** Schema discriminado por `content_type`.

Em `app/schemas/stage_output.py`:

```python
class StageOutputContent(BaseModel, ABC):
    content_type: Literal["..."]  # discriminator
    ...

class DiagnosticoPreliminarContent(StageOutputContent):
    content_type: Literal["diagnostico_preliminar"]
    hipoteses: list[Hipotese]
    lacunas: list[Lacuna]
    riscos: list[Risco]
    checklist_inicial: list[ItemChecklist]
    ...

class PecaJuridicaContent(StageOutputContent):
    content_type: Literal["peca_juridica"]
    template: DocumentType  # computed_field defesa em profundidade
    content: str
    legal_citations: list[LegalCitation]
    addressee: Addressee
    prazo_dias: Optional[int]
    ato_regulatorio: Optional[str]
    ...

class LegislationContextContent(StageOutputContent):
    content_type: Literal["legislation_context"]
    normas_aplicaveis: list[NormaAplicavel]
    ...
```

`StageOutput` (tabela) persiste o JSONB em `content_data`. Discriminator `content_type` permite Pydantic deserializar corretamente quando o consumidor lê.

### Migração gradual (dual-emit)

Para não quebrar consumidores existentes (frontend lia chaves antigas), agentes migrados **emitem chave nova E chave antiga simultaneamente** durante transição:

```python
result = {
    "content": peca_juridica_content.model_dump(),     # chave nova
    "extracted_fields": legacy_dict,                    # chave antiga (mantida)
    ...
}
```

Consumidor migra no seu próprio tempo. Após todos migrarem, chave antiga é removida em sprint cleanup.

## Consequências

**Positivas:**
- **Contrato explícito** — quem consome `RedatorAgent` sabe exatamente o que recebe
- **Validação runtime** — agente que emite saída inválida falha cedo (`ValidationError`), não em produção
- **Chains robustas** — `LegislacaoAgent → RedatorAgent` valida que o primeiro emitiu `LegislationContextContent` antes de prosseguir
- **Auditável** — leitor do código entende o que cada agente promete sem ler implementação
- **Frontend tipado** — schemas exportáveis para TypeScript no futuro (`pydantic.types_for_typescript`)
- **Defesa em profundidade** — `computed_field` para `template = document_type` evita inconsistência entre os dois quando o LLM "esquece" um campo

**Negativas:**
- **Migração custa tempo** — cada agente leva 2-4 horas para migrar com testes
- **Schema rígido pode podar criatividade** — agente que quer emitir campo novo precisa adicionar no schema (raramente um problema real)
- **Dual-emit polui temporariamente** — `result` tem chaves redundantes durante a transição

**Mitigações:**
- Migração agente por agente, sem big-bang
- Schema com campos opcionais e `extra` configurável (`model_config = ConfigDict(extra="forbid")` ou `"allow"` conforme caso)
- Sprint cleanup dedicada (futura) para remover chaves legadas após migração total

## Estado atual

### Agentes migrados (Sprint A2)

| Agente | Schema emitido | Sprint |
|---|---|---|
| `RedatorAgent` | `PecaJuridicaContent` | A2-redator (09/05) |
| `DiagnosticoAgent` | `DiagnosticoPreliminarContent` | A2-diagnostico (09/05) |

### Agentes ainda em dict legado

| Agente | Schema previsto | Status |
|---|---|---|
| `LegislacaoAgent` | `LegislationContextContent` | Próxima sprint (A2-legislacao) |
| `AtendimentoAgent` | a definir | Sem urgência |
| `ExtratorAgent` | a definir (`ExtractedFieldsContent`) | Após skills do extrator |
| `OrcamentoAgent` | a definir | Sem urgência |
| `FinanceiroAgent` | a definir | Sem urgência |
| `AcompanhamentoAgent` | a definir | Após connector inbound |
| `VigiaAgent` | n/a (rules-based, sem LLM) | — |
| `MarketingAgent` | a definir | Sem urgência |

### Smoke real validado

Sprint A2-redator: 7 templates × gpt-4o-mini = **$0.0030 total**, 100% emitiu `PecaJuridicaContent` válido com `requires_review=True` e `legal_citations` populadas onde aplicável.

## Padrão para agentes futuros

Quando criar novo agente ou migrar legado:

1. Definir schema derivado de `StageOutputContent` em `app/schemas/stage_output.py`
2. Agente emite `content_data = schema_instance.model_dump()` em `AgentResult.content_data`
3. Aplicar `requires_review=True` quando aplicável (Princípio 1 do manifesto)
4. Adicionar smoke test em `scripts/smoke_a2_<agente>.py`
5. Testes em `tests/agents/test_<agente>_a2.py`

Detalhes em [`../arquitetura/GOVERNANCA_IA.md`](../arquitetura/GOVERNANCA_IA.md) e nos sprints históricos arquivados.

## Relação com outros ADRs

- [`./002-multi-llm-gateway.md`](./002-multi-llm-gateway.md) — agente chama o gateway; o schema valida a saída
- [`./006-skills-procedurais.md`](./006-skills-procedurais.md) — skills orientam a saída; schema valida o formato dela
