# Trabalho — Diagnóstico enxerga os dados (insumo persistido + modelo + citações UI)

> Arquivo único de trabalho. Causa → mudança → validação → status.
> Branch: `fix/diagnostico-insumo` (base `main`). Data: 2026-06-03.

## Causa (provada em produção, caso #8)

O diagnóstico rodou com `tokens_in=358` e saiu genérico/raso. Lido no código
(`app/agents/diagnostico.py`):

- `_load_process_data` incluía `process` (metadados), `property` (só se
  preenchida) e `documents` apenas como `id`/`tipo`/`ocr_status` — **sem os
  campos extraídos**.
- `extracted_fields` vinha **só** de `chain_data["extrator"]`; `legal_context`
  **só** de `chain_data["legislacao"]` — efêmeros, existem só quando a chain
  roda inteira.
- Rodado avulso (aba Agentes) ou com extrator falho na rodada → diagnóstico
  **cego**, mesmo com área/matrícula/CAR/UF persistidos no banco.

Onde os dados persistem: campos estruturados ficam no `AIJob.result` do extrator
(shape `ExtratorAgent`: `result.extracted_fields`; shape `document_extractor`
`save_job`: campos no topo do `result`). O enquadramento fica no `AIJob.result`
da legislação (`agent_name="legislacao"`, `job_type=consulta_regulatoria`).

Além disso: a UI da Legislação mostrava **"Legislação Aplicável: [object Object]"**
— os itens chegam como objetos `{identificador, titulo, ...}` e o helper `arr()`
só sabia ler objetos com chave `label`, caindo em `String(item)`.

## O que mudou

### 1. Fallback persistido (`app/agents/diagnostico.py`)

- `extracted_fields`: se `chain_data["extrator"]` vazio →
  `_load_persisted_extraction` busca os `AIJob` de extração (`extract_document`,
  `completed`) do processo **e** dos seus documentos, mescla o mais recente de
  cada documento (`id` desc, most-recent-wins) e devolve no mesmo shape de
  `chain_data["extrator"]`. Lê os **dois** shapes de result.
- `legal_context`: se `chain_data["legislacao"]` vazio →
  `_load_persisted_legislacao` busca o `AIJob` mais recente da legislação do
  **mesmo** processo (`agent_name="legislacao"`, `completed`).
- `property`: se a Property está vazia mas a extração tem município/UF/área →
  `_property_from_extracted` enriquece **o contexto do prompt** (marca
  `_source="extracted_fields"`). **Não grava na Property** (efeito colateral
  proibido).
- **Na chain, `chain_data` continua prioritário** (mais fresco): o fallback só
  dispara quando `_has_extracted_fields(chain)` é falso. Sem regressão.
- Só campos estruturados pequenos entram — **nunca** `extracted_text` bruto.

### 2. Modelo (`AI_DIAGNOSTICO_MODEL=gpt-4.1`)

Nenhuma mudança de código necessária: o agente já fazia
`diag_model = settings.AI_DIAGNOSTICO_MODEL or settings.AI_DEFAULT_MODEL` e
passava `model=` ao `call_llm`. Confirmado no gateway que `model=` explícito
(sem `user_preferences`) usa **só** esse modelo. O caso #8 saiu `gpt-4o-mini`
por ser **pré-deploy** do PR #53. Provado agora rodando: AIJob `model_used=gpt-4.1`.

### 3. UI — citações de lei (`frontend/src/components/AgentResultRenderer.tsx`)

Novo `formatLegislacao(item)`: formata string **ou** objeto
(`{identificador|norma|lei, numero, titulo, artigo, descricao}`) em texto tipo
**"Lei nº 12.651/2012 — Código Florestal, art. 17"**, espelhando a prioridade de
`legislacao._citation_ref_from_raw` no backend, com `humanizeValue` como último
recurso (nunca `[object Object]`). `LegislaçãoResult` passa a usar `rawArr(...).
map(formatLegislacao)`.

## Validação (rodando — container real, chave real, processo 30 "Fazenda Boa Vista")

```
1) FALLBACK PERSISTIDO (avulso, chain_data vazio)
   has_extracted_fields(chain) = False
   campos recuperados (12): uf=MS, municipio=Campo Grande, cartorio=..., area_hectares=250, numero_matricula=12.345, ...
   _source = persisted_aijob ; legal recuperado: SIM

2) tokens_in do PROMPT (system+user)
   ANTES (sem fallback): 359      # bate com os ~358 do caso #8
   DEPOIS (com fallback): 3491

3) EXECUÇÃO REAL (agent.run, chain_data vazio)
   success=True | model_used=gpt-4.1 | tokens_in=3491 | tokens_out=631
   situacao_geral: "A Fazenda Boa Vista apresenta múltiplos passivos ambientais,
     incluindo a necessidade de regularização do CAR e a existência de Auto de
     Infração por supressão de vegetação. ..."   # substantivo, caso-específico

4) VIA CHAIN (chain_data['extrator'] presente)
   has_extracted_fields(chain) = True → mantém chain (FRESCO_CHAIN), fallback NÃO dispara

5) PROPERTY FALLBACK (sem gravar):
   {name: Fazenda Boa Vista, municipality: Campo Grande, state: MS, total_area_ha: 250.0, _source: extracted_fields}
```

- Antes/depois do insumo: **tokens_in 359 → 3491** (prompt agora recebe os dados).
- Output deixou de ser genérico: nomeia o imóvel e cita Auto de Infração / CAR.
- `model_used=gpt-4.1` no AIJob.
- Testes: `pytest tests/agents/test_diagnostico_*` → **44 passed**.
- Frontend: `tsc --noEmit` ✅ ; `npm run build` ✅.

## Status

✅ Concluído. Diagnóstico **avulso e via chain** enxergam os campos extraídos e o
enquadramento persistidos; `model_used=gpt-4.1`; citações de lei humanizadas na UI.
