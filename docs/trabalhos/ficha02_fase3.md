# Ficha 02 / FASE 3 — Auditor → Matriz de Inconsistências

**Branch:** `feat/ficha02-fase3-matriz-inconsistencias` (base `main`, requer Fase 2 #61)
**Data:** 2026-06-05
**Espec:** Ficha 02 (§3/§4/§5/§7) + Ficha 01 (staging)
**Relacionada a:** ADR-015, Fase 1 (#60) e Fase 2 (#61)

A saída canônica do `auditor_imovel` passa a ser a **MATRIZ DE INCONSISTÊNCIAS**:
confronto multi-fonte determinístico (sem LLM), classificação pela taxonomia da
Ficha 02 §4 e ação recomendada. Lê o staging da Fase 2; **não** grava na base real.

## Estrutura (Ficha 02 §3/§5)

- **Linhas (itens canônicos, profundidade INTAKE):** `area_total`,
  `denominacao_imovel`, `codigo_incra_sncr`, `sigef_georreferenciamento`,
  `car_presenca_consistencia`, `acesso_imovel`. As técnicas (APP/RL/hidrografia/
  cobertura) entram como **linhas técnicas registradas** (`profundidade="tecnica"`,
  `critico`) a partir das `pendencias_rat` — sem confronto espacial (gap D1).
- **Colunas:** dinâmicas, uma por FONTE no staging — cada matrícula
  (`matricula_hint`), + `ccir`/`itr`/`car`/`rat`/`sigef`.
- Cada linha: `item`, `label`, `fontes{...}`, `situacao`, `subtipo?`,
  `acao_recomendada`, `destino[]`, `profundidade`.

## Taxonomia (Ficha 02 §4 — enum `MatrixSituacao`)

| situação | destino |
|---|---|
| `critico` | diagnostico + orcamento |
| `inconsistente` | correcao_documental (+ diagnostico+orcamento se exigir plataforma oficial) |
| `divergente` (`transcricao`) | alertas |
| `divergente` (`fundo`) | diagnostico |
| `atencao` | alertas |

## Regras de confronto (determinísticas; âncora = SIGEF)

`app/services/inconsistency_matrix.py` (puro, testável; parsing PT-BR de área).
- **area_total:** SIGEF (âncora) × soma matrículas × CCIR × ITR × CAR. ≤0,5% ⇒
  consistente; diferença não-nula ⇒ divergente (`fundo` se geo ausente/0, senão
  `transcricao`), ação "ajustar/justificar diferença de X ha".
- **denominacao:** distintas entre fontes ⇒ divergente/transcricao, "padronizar".
- **codigo_incra_sncr:** distintos (CCIR × ITR × matrículas) ⇒ atencao, "tabela de
  correspondência cadastral".
- **sigef:** área certificada 0/ausente OU pendência geo no RAT ⇒ critico,
  "verificar DCR/SIGEF/SNCR".
- **car_presenca:** CAR presente mas ITR sem CAR declarado ⇒ inconsistente,
  "atualizar ITR/DIAC" (plataforma oficial → diagnostico+orcamento). Matrículas
  listadas no CAR ≠ matrículas do staging ⇒ inconsistente.
- **acesso:** pendência de acesso no RAT ⇒ atencao, "padronizar acesso com coordenadas".
- **linhas técnicas:** pendências APP/hidrografia/supressões/cobertura/APA do RAT ⇒
  critico, `profundidade=tecnica` (aguardam geo/Etapa 4).

## Efeitos

1. **Staging:** marca o status das linhas confrontadas — `consistente` /
   `divergente_transcricao` / `divergente_fundo` (a decisão `aceito`/`rejeitado` é
   do consultor, Fase 4 — não aqui).
2. **AIJob do auditor:** matriz persistida em `result["matriz_inconsistencias"]`
   (campo NOVO — shape antigo de `AuditorResult` intacto: `content`,
   `divergencias`, `issue_ids`, `findings_raw`, `geom_present`, `method`).
3. **Diagnóstico:** novo `_load_persisted_auditor` (padrão do atendimento) — quando
   a chain não traz o auditor, recupera o AIJob persistido; a matriz entra no
   contexto do prompt (`process.matriz_inconsistencias`, sem tocar prompt-template).
4. **UI:** `AuditorResult` ganhou a tabela da matriz (item × situação × ação, cores
   por situação; flag "técnica — aguarda geo"). A tela de DECISÃO é Fase 4.

## Ajustes de Fase 2 (necessários para a matriz)

`app/services/ficha01_extraction.py`: `matricula` ganhou `denominacao` e `itr`
ganhou `numero_car` (ambos aditivos; alimentam denominação × confronto e
car_presença).

## Validação real (rodando — matriz da Isis, Ficha 02 §7, caso São Jorge)

Staging do caso São Jorge semeado no processo 30; auditor disparado. Matriz gerada:

| item | situação | ação | destino |
|---|---|---|---|
| area_total | **divergente/transcricao** | ajustar/justificar diferença de **0,153 ha** (soma matrículas 1.010,5583 vs CAR 1.010,7113) | alertas |
| denominacao_imovel | **divergente/transcricao** | padronizar denominação (São Jorge × Shangri-lá Parte 2 × São Jorge) | alertas |
| codigo_incra_sncr | **atencao** | tabela de correspondência cadastral | alertas |
| sigef_georreferenciamento | **critico** | verificar DCR/SIGEF/SNCR (ausente) | diagnostico+orcamento |
| car_presenca_consistencia | **inconsistente** | atualizar ITR/DIAC com o nº do CAR | correcao+diagnostico+orcamento |
| acesso_imovel | **atencao** | padronizar acesso com coordenadas | alertas |
| 3× técnica (APA / supressões / hidrografia) | **critico** [técnica] | (recomendação do RAT) | diagnostico+orcamento |

`resumo`: critico 4, divergente 2, atencao 2, inconsistente 1.

**Staging marcado:** matrículas (área) → `consistente`; CAR (área) →
`divergente_transcricao`; matrículas (denominação) + ITR (nome) →
`divergente_transcricao`. Nenhuma marca `aceito`/`rejeitado`.

**Diagnóstico re-rodado** (processo 30, chain vazia → `_load_persisted_auditor`,
log `diagnostico.auditor_context`): output cita a matriz — "divergências
cadastrais, ... inconsistência no CAR, ... sobreposição com APA estadual,
conflitos em APP/hidrografia, e pendências de georreferenciamento".

## Testes

- `tests/services/test_inconsistency_matrix.py` — 9 testes determinísticos
  reproduzindo a matriz §7 (área, denominação, INCRA, SIGEF, CAR/ITR, acesso,
  técnicas, marcação de staging, vazio).
- `tests/agents/test_auditor_matriz.py` — integração: auditor anexa a matriz +
  marca staging SEM quebrar o shape antigo do `AuditorResult`.

## Skill

`auditor_imovel/analise_divergencias_documentais` → **v1.2.0**: nota da Matriz
(Ficha 02 §4) — a `situacao` da linha é eixo distinto do `grade` da "Régua de área"
(que segue valendo para o `RegulatoryIssue`).

## Não nesta fase (PROIBIDO)

LLM no auditor (segue determinístico); tela de decisão/consolidação (Fase 4);
confronto espacial real (gap D1 — linhas técnicas só registram).

## Arquivos

- `app/services/inconsistency_matrix.py` (novo)
- `app/agents/auditor_imovel.py` (`_build_matriz_inconsistencias` + campo novo)
- `app/agents/diagnostico.py` (`_resolve_auditor_payload` + `_load_persisted_auditor` + injeção no contexto)
- `app/services/ficha01_extraction.py` (matrícula `denominacao`, ITR `numero_car`)
- `frontend/src/components/AgentResultRenderer.tsx` (tabela da matriz)
- `app/skills/auditor_imovel/analise_divergencias_documentais/SKILL.md` (v1.2.0)
- `tests/services/test_inconsistency_matrix.py`, `tests/agents/test_auditor_matriz.py`
- Governança: ESTADO_ATUAL, MEMORIA_CHAT.
