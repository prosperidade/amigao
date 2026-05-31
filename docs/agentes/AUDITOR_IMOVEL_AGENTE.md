# AUDITOR_IMOVEL — sister file

> Documento vivo do agente `auditor_imovel`. Toda afirmação aqui é verificável
> no código (referências `arquivo:linha`). Criado em 2026-05-31 a partir do
> código real (não de rascunho). Estrutura de 12 seções — molde dos sister files.

## 1. Papel no ecossistema

Cruza os documentos do imóvel rural (matrícula × CAR × CCIR/ITR/SIGEF) e emite
**divergências tipadas** — área divergente, GEO INCRA ausente, RL averbada ×
declarada. É o "primeiro movimento" antes do Diagnóstico: produz findings que
viram insumo, não peça formal. A matemática é **determinística** (tools puras em
`app/services/property_audit.py`); o LLM não faz conta
(`app/agents/auditor_imovel.py:5-6,41`).

Registrado como `"auditor_imovel"` / `AuditorImovelAgent`,
`job_type=AIJobType.diagnostico_propriedade` (enum reusado — tipo próprio é
sprint posterior, `app/agents/auditor_imovel.py:38-40`). Importado em
`app/agents/__init__.py:16`.

## 2. Estado de implementação

- **Implementado (determinístico).** `execute()` carrega Property + Documents,
  roda `audit_property()` e retorna divergências + findings crus
  (`app/agents/auditor_imovel.py:47-106`). `prompt_slugs=[]` — MVP sem LLM
  (`auditor_imovel.py:41`).
- **Persistência:** cada finding vira um `RegulatoryIssue` quando há
  `property_id` real (sem property persistida — dry-run/teste — só reporta no
  payload), `auditor_imovel.py:159-211`.
- **Taxonomia rica (PROMPT_5 Onda A):** `codigo_alerta` (FK no catálogo
  `regulatory_issue_catalog`) + `familia` (enum de 11) + `severity` de 4 níveis
  (= `finding.grade`); `type` legado fica `None` em registros novos
  (`auditor_imovel.py:184-205`).
- **Régua de área de 4 faixas:** ≤1% `informativo`, ≤5% `atencao`, ≤10% `alto`,
  >10% `critico`; dado ausente → `atencao`
  (`property_audit.py:50-72`).

## 3. Skills

Skill procedural dedicada: `auditor_imovel/analise_divergencias_documentais`
(`app/skills/auditor_imovel/analise_divergencias_documentais/SKILL.md`, v1.1.0).
Define a taxonomia de **40 códigos em 11 famílias**, a régua de área, as 10
heurísticas de decisão e a fronteira "factível agora (📄) × aguarda geom (🛰️) ×
aguarda base externa (🔌)". Anexo `bases_car_estaduais.md` (mapa das 27 UFs).
Conteúdo de domínio é da sócia (validado por construção, `SKILL.md:194-199`).

> Nota: o agente **não** injeta esta skill via prompt hoje — `prompt_slugs=[]`
> e não há chamada a LLM (`auditor_imovel.py:41,155-157`). A skill cobre as tools
> determinísticas de `property_audit.py` (`property_audit.py:8-9`) e documenta o
> domínio; é o contrato que `property_audit` implementa, não um system prompt.

## 4. Tools que usa

- **`property_audit.audit_property()`** — bateria determinística de cruzamentos
  (`property_audit.py:209-360`). Helpers: `compare_areas`, `grade_area_divergence`,
  `has_geo_incra`, `grade_overlap_severity`.
- **ORM read-only:** `Process`, `Property`, `Document` em `_load_process_data()`
  (`auditor_imovel.py:110-153`).
- **`RegulatoryIssue`** — persiste cada finding (`auditor_imovel.py:184-209`).
- Não usa LiteLLM gateway nem OCR.

## 5. Inputs aceitos

Exige `ctx.process_id` (`validate_preconditions`, `auditor_imovel.py:43-45`).
Monta `property_data` (áreas, `car_code`, `rl_status`, `geom`) e a lista de
`documents` a partir do processo (`auditor_imovel.py:128-152`). Consome também
`ctx.chain_data["extrator"]` quando presente — daí saem `car_area_ha`,
`ccir_area_ha`, `itr_area_ha`, `matricula_text` (`auditor_imovel.py:51`;
`property_audit.py:242-244,291`). Caminhos de disparo: via `/agents` (manual) ou
via a chain `diagnostico_completo`.

## 6. Outputs

`dict` com: `content` (resumo "N divergência(s)… crítica(s)/alto(s)/atenção"),
`requires_review=True` (princípio 1), `divergencias` (tema/divergencia/impacto),
`issue_ids`, `findings_raw` (taxonomia rica por finding), `geom_present`,
`method="deterministic_tools"` (`auditor_imovel.py:77-106`).

`requires_review=True` mas **não-bloqueante**: `auditor_imovel` está em
`NON_BLOCKING_REVIEW_AGENTS` (`orchestrator.py:54`) — a chain segue, a UI exibe o
badge (ADR-011). Output é insumo de downstream, não produto final.

## 7. Knowledge essencial

- Áreas comparadas: `area_documental_ha` (matrícula) × `car_area_ha`/
  `area_grafica_ha` × `ccir_area_ha` × `itr_area_ha`; 4 pares com código próprio
  (`property_audit.py:241-252`).
- GEO INCRA (H1): heurística textual sobre a matrícula — SIGEF, CNIR, "Lei
  10.267", "georreferenciado" (`property_audit.py:89-95,194-202`).
- RL averbada × declarada (H12): `rl_averbada_ha` × `rl_declared_ha`
  (`property_audit.py:308-336`).
- **Sempre emite o finding** — divergência ≤ tolerância vira `informativo`, nunca
  silêncio (radar, não cancela, `property_audit.py:42-43,262-266`).
- Par com um lado `None` não vira finding de área (dado faltante é domínio
  próprio, `property_audit.py:253-260`).

## 8. Conversation patterns

Não conversacional. Roda como task (síncrona via `/agents` ou async na chain).
Sem LLM. Reentrante na leitura, mas **`_persist_issues` cria novos
`RegulatoryIssue` a cada execução** e dá `commit()` (`auditor_imovel.py:207-210`)
— reprocessar o mesmo processo acumula issues (sem dedupe hoje).

## 9. Cross-agente

- Consome `chain_data["extrator"]` (áreas e texto da matrícula extraídos),
  `auditor_imovel.py:51`.
- Alimenta o `diagnostico` via `chain_data["auditor_imovel"]` — ordem da chain
  `diagnostico_completo`: `extrator → auditor_imovel → legislacao → diagnostico`
  (`orchestrator.py:33`). Ver `ECOSSISTEMA_AGENTICO.md`.
- Findings `grade=critico` conectam ao mecanismo de decisão obrigatória do
  consultor da skill de Diagnóstico (P4, `SKILL.md:183-184`).

## 10. Dívidas técnicas próprias

- **#14** — alertas geoespaciais (sobreposição, CAR deslocado, APP, confrontantes,
  datum/fuso, RL × realidade) aguardam `Property.geom` (gap D1). Hoje a seção
  espacial só emite "verificação espacial pendente" como `informativo`
  (`property_audit.py:338-358`); `grade_overlap_severity()` já existe, sem
  chamador, e pluga quando o geom chegar (`property_audit.py:75-84`;
  `REGISTRO_DIVIDAS.md:95-100`).
- **#15** — alertas de consulta externa (🔌 embargo IBAMA, auto de infração,
  licença/outorga) aguardam integração (`REGISTRO_DIVIDAS.md:102-103`).
- Reprocessamento sem dedupe de `RegulatoryIssue` (ver seção 8).

## 11. Próximas frentes

- Quando D1 (parser shapefile/KML + `Property.geom`) chegar, a seção 4 de
  `audit_property` faz overlay PostGIS real e ativa as famílias 🛰️
  (`property_audit.py:338-341`; `ESTADO_ATUAL.md:423`).
- `job_type` próprio (hoje reusa `diagnostico_propriedade`) e eventual camada LLM
  de explicação/priorização sobre os findings — previstos no cabeçalho do agente
  (`auditor_imovel.py:40`; `property_audit.py:4-6`).

## 12. Validação Isis

- **Skill validada pela Isis em 26/05** (`ECOSSISTEMA_AGENTICO.md:156`). A régua
  de 4 faixas e a fronteira de factibilidade foram conferidas com a sócia
  (`SKILL.md:194-199`).
- **Pendente:** sister file marcado como "⏳ pendente" no catálogo do ecossistema
  (`ECOSSISTEMA_AGENTICO.md:156`) — este documento quita essa pendência (dívida
  documental #32, `REGISTRO_DIVIDAS.md:123-130`); validação fim-a-fim do agente
  em caso real pela Isis ainda não registrada no código.
