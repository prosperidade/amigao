# Auditoria documental — inventário de dívidas e pendências

**Data:** 2026-05-23
**Autor:** Claude (coordenação) · **Validação:** Andre
**Método:** leitura consolidada dos docs vivos (ESTADO_ATUAL, TESTING, GOVERNANCA_IA, BASE_REGULATORIA, SEED_DADOS, CRUZAMENTO_DOC_X_CODIGO, RELATORIO_DESCOBERTA_AGENTES, PROGRESSO_WAITLIST, ADRs) + rodapés das skills produzidas nesta sessão.
**Natureza:** esta é auditoria **documental**. A validação contra o código real é a Fase 0 do agente. Onde as fontes divergem, marquei `[CONFIRMAR NO CÓDIGO]`.

---

## 1. Divergências entre as próprias fontes (resolver na Fase 0)

Não são dívidas — são incertezas de estado que só o código resolve. O agente confirma cada uma com um comando objetivo antes de qualquer implementação.

| Item | Fonte A | Fonte B | Comando de verificação |
|---|---|---|---|
| Bloqueio Testcontainers / pytest e2e | Memória do projeto: "bloqueado" | TESTING + ESTADO_ATUAL: "desbloqueado 17/05 (`0e17ebd`)" | `pytest tests/ -q --no-cov` e ver se sobe o container |
| Nº de arquivos de teste | ESTADO_ATUAL: 102 | CRUZAMENTO: 39 reais | `find tests -name "test_*.py" \| wc -l` e `pytest --collect-only -q \| grep -c "::"` |
| Nº de routers REST | docs: 28 | CRUZAMENTO: 26 | `grep -c "include_router" app/main.py` |
| Nº de migrations | docs: 40 | CRUZAMENTO: 38 | `ls alembic/versions/*.py \| wc -l` |
| Estado da Waitlist | Memória: "B1 mergeada" | PROGRESSO_WAITLIST: "PR2 mergeado, PR3 pendente" / CRUZAMENTO: "em stash" | `git log --oneline \| grep -i waitlist` + `git stash list` |
| `feat/ocr-automatico` | Memória: "não pushada, aguarda rebase" | — | `git branch -a \| grep ocr` |

A lição: a memória e os docs de estado têm recência diferente. O código é a fonte de verdade. A Fase 0 reconcilia tudo isso num mapa único.

---

## 2. Inventário de dívidas por categoria

### 2.1 Agentes e skills (núcleo do produto)

| # | Dívida | Fonte | Conecta com hoje? |
|---|---|---|---|
| A1 | Skills reais não existem — só placeholders `_template/SKILL.md` (redator, extrator) | GOVERNANCA_IA #1, ESTADO_ATUAL, ADR-006 | **SIM** — a skill de diagnóstico que fechamos é a primeira real |
| A2 | **`auditor_imovel` não existe** (gap I3 / tarefa C6) — cruzar matrícula × CAR × CCIR, detectar divergências de área/sobreposição | RELATORIO_DESCOBERTA C6, audit gap I3 | **SIM, crítico** — é a "matriz de cruzamento" e a tool determinística que a skill de diagnóstico pressupõe |
| A3 | **Citation evaluator só roda no Redator** — não roda no Diagnóstico | GOVERNANCA_IA #2 | **SIM** — sem isso, as citações da skill de diagnóstico não são validadas |
| A4 | Sem modelo `RegulatoryDiagnosis(content_jsonb, validated_by, version)` para versionar diagnóstico (gap B3); preliminar e consolidado usam o mesmo campo (gap #8) | RELATORIO_DESCOBERTA, audit B3/#8 | **SIM** — é a extensão de schema que a skill pede (níveis de risco, 7 categorias, divergências) |
| A5 | MemPalace stub vivo em `app/agents/memory.py` (16 arquivos afetados) — ADR-003 revogou, código não removido | GOVERNANCA_IA #4, ADR-003 | Não, mas é limpeza pendente |
| A6 | Skills do Redator (5 entregáveis) não escritas | ESTADO_ATUAL, ADR-006 | Amanhã, com a Isis |

### 2.2 Conhecimento e RAG

| # | Dívida | Fonte | Conecta com hoje? |
|---|---|---|---|
| K1 | **`ingest_pasta_socia.py` existe, mas nenhum ofício/gabarito ingerido** | BASE_REGULATORIA #3 | **SIM** — é o ponto de partida do loop do ADR-010 |
| K2 | Cobertura RAG limitada a 4 UFs (Federal, GO, MS, MT); SP/MG/TO na fila; nacional só na janela 3 | BASE_REGULATORIA #2, ESTADO_ATUAL | **SIM** — a skill é desenhada para 27 estados; o conteúdo segue por trás |
| K3 | Normas GO específicas da skill podem não estar indexadas (IN SEMAD 3/2025, 7/2024, 1/2024; Lei 21.231; Decreto 9.710/2020; CEMAm 259/2024; IN INCRA 131/2023; CONAMA 428/429) | rodapé da skill de diagnóstico | **SIM** — sem elas, citation evaluator marca as citações da skill como suspeitas |
| K4 | Crawlers DOU/DOE/IBAMA não ativos em produção (só esqueleto) | BASE_REGULATORIA #1 | Não |
| K5 | Re-indexação manual (sem gatilho quando muda provider de embedding) | BASE_REGULATORIA #5 | Não |
| K6 | `min_similarity = 0.7` heurístico, não calibrado | BASE_REGULATORIA #6 | Não |

### 2.3 Dados espaciais

| # | Dívida | Fonte | Conecta com hoje? |
|---|---|---|---|
| D1 | **`Property.geom` não populado** em nenhuma propriedade — falta parser shapefile + ingestão KML/SHP | ESTADO_ATUAL, SEED_DADOS #1 | **SIM (limite)** — a skill já assume isso: raciocínio espacial sai de campos extraídos, não de geometria. Quando `geom` existir, A2 (`auditor_imovel`) faz overlay PostGIS real |

### 2.4 Testes e CI

| # | Dívida | Fonte |
|---|---|---|
| T1 | State-leakage entre testes — 29 testes passam isolados, falham na suíte (slowapi in-process + commits manuais) | TESTING #1 |
| T2 | Sem CI/CD — testes só rodam local, sem pipeline em PR | TESTING #2 |
| T3 | Suíte E2E pobre — só 2 testes | TESTING #3 |
| T4 | Sem testes de regressão de prompt — ajuste no Redator não tem rede de segurança | TESTING #4 |

### 2.5 Renomeação e config

| # | Dívida | Fonte |
|---|---|---|
| R1 | `PROJECT_NAME='Amigão do Meio Ambiente'` ainda em `config.py` — rebrand Amigão→Regente pendente (9 pontos confirmados) | CRUZAMENTO, memória config.py:52 |
| R2 | `AI_HOURLY_COST_LIMIT_USD` hardcoded — migrar para config | GOVERNANCA_IA #5 |
| R3 | Override de prompts via UI cortado — formalizar como ADR | GOVERNANCA_IA #3 |

### 2.6 Produção e integrações

| # | Dívida | Fonte |
|---|---|---|
| P1 | Hardening de produção (secrets, CORS, Swagger desabilitado) — checklist em `ops/production-secrets-checklist.md` | ESTADO_ATUAL |
| P2 | Connector e-mail inbound (acompanhamento) — sem integração hoje | ESTADO_ATUAL |
| P3 | Pipeline de transcrição estruturada de áudio (MP3/WAV/M4A/AAC → 12 blocos) | rodapé da skill de diagnóstico |
| P4 | Tool determinística de cálculo de uso do solo (pós-contrato) | rodapé da skill de diagnóstico |

---

## 3. O que as sprints de hoje destravam ou dependem

Cruzando o trabalho da sessão (skill de diagnóstico v1.0 + ADR-010) com o inventário:

**A skill de diagnóstico v1.0 entra como A1 resolvido** (primeira skill real), mas ela **pressupõe três coisas que ainda não existem**:
- **A2 (`auditor_imovel`)** — a matriz de cruzamento e a tool determinística. Sem isso, a skill orienta o raciocínio, mas não há a peça de código que cruza documentos e calcula. **É a dependência mais forte.**
- **A3 (citation evaluator no Diagnóstico)** — sem expandir, as citações da skill não são validadas.
- **A4 (schema estendido / `RegulatoryDiagnosis`)** — os 8 campos de risco, 4 níveis, 7 categorias e a matriz de divergências precisam virar tipos.
- **K3 (normas GO indexadas)** — pré-condição para o citation evaluator não barrar as citações.

**O ADR-010 (loop de aprendizado) tem ponto de partida em K1** (`ingest_pasta_socia.py` já existe). Não parte do zero.

Ou seja: fechar a skill foi necessário, mas a skill sozinha não roda bem sem A2, A3, A4 e K3. Essas quatro são as candidatas naturais às sprints de implementação de hoje/amanhã.

---

## 4. Recomendação de sequência para as sprints

Ordenado por dependência e por risco (não por esforço):

1. **K3 — indexar as normas GO da skill** no `knowledge_catalog`. Barato, destrava A3, e sem isso a skill cita no vazio. Primeiro.
2. **A4 — estender o schema** (`DiagnosticoPreliminarContent` com risco de 8 campos, 4 níveis, 7 categorias, divergências; avaliar `RegulatoryDiagnosis` versionado). É fundação para A2 e A3.
3. **A3 — citation evaluator no Diagnóstico.** Depende de K3.
4. **A2 — `auditor_imovel`** (matriz de cruzamento + cálculo determinístico). É a peça mais valiosa e a mais complexa; entra depois da fundação pronta. A parte de overlay espacial fica limitada até D1 (geom), mas a parte de cruzamento documental (área CAR vs matrícula, nome, titularidade) já funciona sem geometria.
5. **P4 — tool de uso do solo** (pós-contrato, mas a fórmula já está documentada na skill).

Limpezas paralelas de baixo risco, encaixáveis quando houver folga: **R1** (rebrand), **A5** (remover MemPalace stub), **T1** (state-leakage dos testes).

O loop de aprendizado (ADR-010) é transversal e maior — provavelmente uma trilha própria depois que A2/A3/A4 estabilizarem, começando por formalizar K1.

---

## 5. O que falta decidir antes de implementar (humano)

- **A4:** estende o schema atual com dual-emit, ou cria `RegulatoryDiagnosis` versionado novo? (gap B3 sugere o segundo)
- **A2:** `auditor_imovel` é agente novo ou tool chamada pelo Diagnóstico? (RELATORIO sugere "agente único com tools determinísticas")
- **ADR-010:** os pontos abertos da seção própria (escopo tenant vs global do conhecimento exemplar; quem cura; sinal de desfecho)
