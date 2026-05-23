# Mapa de gaps confirmado — Fase 0 da skill de diagnóstico

**Data:** 2026-05-23
**Autor:** Claude (Fase 0, worktree `chore/auditoria-fase0`)
**Insumo:** [`AUDITORIA_DOCUMENTAL_2026-05-23.md`](./AUDITORIA_DOCUMENTAL_2026-05-23.md) confrontada com o código real.
**Natureza:** confirmação contra realidade. Onde a auditoria documental e o código divergem, **o código vence**.

---

## 1. Reconciliação das divergências entre fontes (Tarefa 2)

| Item | Valor declarado | Valor real | Fonte do comando |
|---|---|---|---|
| pytest e2e / Testcontainers | "bloqueado" (memória) vs "destravado 17/05 commit 0e17ebd" (TESTING/ESTADO_ATUAL) | **Destravado.** 411 testes coletam sem erro de import com env mockado; Docker daemon ativo; containers do projeto rodando. | `pytest tests/ --collect-only -q --no-cov` |
| Nº de arquivos de teste | 102 (ESTADO_ATUAL) / 39 (CRUZAMENTO) | **42** | `find tests -name "test_*.py" \| wc -l` |
| Nº de funções de teste | — | **411** | `pytest --collect-only -q` (cabeçalho `411 tests collected`) |
| Nº de routers REST | 28 (docs) / 26 (CRUZAMENTO) | **27** | `grep -c "include_router" app/main.py` |
| Nº de migrations | 40 (docs) / 38 (CRUZAMENTO) | **39** | `ls alembic/versions/*.py \| wc -l` |
| Estado da Waitlist | "B1 mergeada" (memória) / "PR2 mergeado, PR3 pendente" (PROGRESSO_WAITLIST) / "em stash" (CRUZAMENTO) | **Apenas B1 mergeada** (`148c25b feat(waitlist): Sprint B1`) + hotfix de export (`5b736e7 fix(waitlist): exporta waitlist_tasks`). Sem B2/B3 no histórico. `git stash list` vazio. Router ativo em `app/main.py:160`. | `git log --all --oneline \| grep waitlist`, `git stash list` |
| `feat/ocr-automatico` | "não pushada, aguarda rebase" (memória) | **Existe local + `origin/feat/ocr-automatico`, mas sem commits exclusivos vs `main`** (`git log main..feat/ocr-automatico` vazio). Branch obsoleta/superseded — conteúdo já integrado no main por outro caminho. | `git branch -a`, `git log main..feat/ocr-automatico` |

**Leitura:** a memória do projeto está mais defasada que os docs vivos em três pontos (pytest, OCR, waitlist). Os números de teste/router/migration apontam um terceiro padrão: ambos os docs (ESTADO_ATUAL e CRUZAMENTO) estão errados, mas em direções diferentes — provavelmente colhidos em momentos distintos sem reconciliação. A próxima fase de doc-hygiene precisa de uma única tabela canônica.

---

## 2. Estado das 4 dependências da skill (Tarefa 3)

### A2 — `auditor_imovel`
**Estado:** **AUSENTE** (gap I3 / tarefa C6 confirmado).

- `app/agents/auditor_imovel.py` não existe (`ls app/agents/` retorna 10 agentes, nenhum auditor).
- Único vestígio são duas menções textuais como peça futura:
  - [`app/api/v1/regulatory.py:11`](../../app/api/v1/regulatory.py#L11) — *"POST/PUT/PATCH/DELETE ficam para A2/Y (quando o agente `auditor_imovel`...)"*
  - [`app/models/document.py:28`](../../app/models/document.py#L28) — *"...do onboarding e o auditor_imovel a priorizar fontes da abertura do caso."*

**O que falta:** o agente/tool inteiro. A skill pressupõe matriz de cruzamento documental (Matrícula × CAR × CCIR/ITR/SIGEF × Sistema Ipê × cobertura real) e cálculos determinísticos de divergência de área. Sem D1 (`Property.geom` populado), a parte de overlay espacial fica capada, mas o cruzamento documental (área CAR vs matrícula, titularidade, GEO INCRA, RL averbada) já roda sem geometria.

### A3 — citation evaluator no Diagnóstico
**Estado:** **AUSENTE** no Diagnóstico, **presente** no Redator.

- [`app/agents/diagnostico.py`](../../app/agents/diagnostico.py): grep por `citation_evaluator|CitationEvaluator` retorna 0 ocorrências.
- [`app/agents/redator.py:246`](../../app/agents/redator.py#L246): `from app.services.citation_evaluator import (...)` confirmado.

**O que falta:** chamar o `citation_evaluator` na saída do `DiagnosticoAgent` (preliminar, consolidado e saneamento) — equivalente ao que o Redator já faz. Dependência forte de **K3** (sem normas indexadas, evaluator marca toda citação da skill como não-validada).

### A4 — schema estendido / `RegulatoryDiagnosis`
**Estado:** **PARCIAL — com surpresa positiva.**

- **`RegulatoryDiagnosis` JÁ EXISTE** ([`app/models/regulatory.py:63`](../../app/models/regulatory.py#L63)), versionado, com FK para `Process`, validação humana opcional, `content` em JSONB, `UniqueConstraint("process_id","version")`. **O gap B3 da auditoria 2026-04-29 já foi fechado** (Sprint A1 Tarefa D1 — ver docstring linha 1-19 do mesmo arquivo). Schema de leitura `RegulatoryDiagnosisOut` em [`app/schemas/regulatory.py:18`](../../app/schemas/regulatory.py#L18) e endpoints de leitura em [`app/api/v1/regulatory.py:66+`](../../app/api/v1/regulatory.py#L66).
- **`RegulatoryIssue` também existe** ([`app/models/regulatory.py:118`](../../app/models/regulatory.py#L118)) com enum `RegulatoryIssueType` (`area_divergente`, `sobreposicao_app`, `sobreposicao_reserva`, `poligono_fora_matricula`, `outro`) e severidade `info/warning/critical` — peça útil para a matriz de divergências da skill.
- **O gap remanescente é no shape do conteúdo Pydantic.** [`DiagnosticoPreliminarContent`](../../app/schemas/stage_output.py#L142) (`app/schemas/stage_output.py:142`) tem apenas 4 campos: `hipoteses, lacunas, riscos, checklist_documental`. [`Risco`](../../app/schemas/stage_output.py#L100) (linha 100) tem 3 campos básicos: `descricao, severidade, mitigacao_sugerida`.

**O que falta exatamente:**
1. Estender `Risco` para 8 campos (4 níveis × 7 categorias × evidências/impacto/mitigação/responsável conforme a skill).
2. Estender `DiagnosticoPreliminarContent` para carregar matriz de divergências, hipóteses tipadas, lacunas tipadas e (no estágio saneamento) matriz de resposta à notificação.
3. Decidir se a forma estendida vira `DiagnosticoPreliminarContent v2` (extensão do schema atual) ou nasce como derivado (`DiagnosticoSaneamentoContent` etc.) — escopo do "ponto aberto A4" no fim da auditoria documental fica mais leve: a tabela versionada já existe, é só Pydantic.

### K3 — normas GO indexadas
**Estado:** **MAJORITARIAMENTE AUSENTE.** 2 de 11 normas-chave da skill estão no `knowledge_catalog`.

Query no banco local (`amigao_do_meio_ambiente-db-1` em `:55432`):

| Norma citada na skill | Chunks no `knowledge_catalog` | Observação |
|---|---:|---|
| IN SEMAD 1/2024 | **1023** | Presente — ingestão massiva |
| Resolução CEMAm 259/2024 | **45** | Presente |
| IN SEMAD 3/2025 | 0 | Ausente (testado também com variantes) |
| IN SEMAD 7/2024 | 0 | Ausente |
| Lei GO 18.104 | 0 | Ausente (testado `18.104` e `18104`) |
| Lei GO 18.102 | 0 | Ausente |
| Lei GO 21.231 | 0 | Ausente |
| Decreto GO 9.710/2020 | 0 | Ausente (testado `9.710` e `9710`) |
| IN INCRA 131/2023 | 0 | Ausente |
| CONAMA 428/2010 | 0 | Ausente — `jurisdiction='federal'` tem CONAMA 001/237/369 mas não 428/429 |
| CONAMA 429/2011 | 0 | Ausente |

Federal tem boa base estrutural (Lei 12.651, 6.938, 9.605, 9.985, LC 140, Decretos 7.830/8.235, IN MMA 02/2014, IN IBAMA 14/2024, Res. CONAMA 001/237/369, Manual SFB) — mas não cobre as duas resoluções CONAMA específicas que a skill cita (APP/regularização ambiental).

**O que falta:** ingerir 9 normas via pipeline existente (`ingest_pasta_socia.py` + os scripts `ingest_*`). É a dívida com maior assimetria custo/valor: barato, destrava A3, e é pré-condição para a skill citar fundamentos sem alarme do evaluator.

---

## 3. Demais dívidas — passada rápida (Tarefa 3 bis)

| # | Item | Estado real | Evidência |
|---|---|---|---|
| K1 | `ingest_pasta_socia.py` | **Presente** | `scripts/ingest_pasta_socia.py` existe |
| D1 | `Property.geom` populado | **Ausente** — 10 properties, 0 com `geom` não-nulo | `SELECT COUNT(*), COUNT(geom) FROM properties` → `10\|0` |
| A5 | MemPalace stub em `app/agents/memory.py` | **FECHADO** — arquivo deletado | commit `757b7de chore(mempalace): deleta memory.py + remove patches em smokes/tests`; `grep MemPalace app/` retorna 0 |
| R1 | `PROJECT_NAME='Amigão'` em config | **Parcialmente fechado** — `app/core/config.py:52` agora é `"Regente Ambiental"`. Mas restam 9 ocorrências de "Amigão" em 5 arquivos secundários: `app/agents/__init__.py`, `app/core/alerts.py`, `app/services/crawlers/{ibama,dou,doe}_crawler.py`. Frontend `frontend/src/` está limpo (0). | grep |
| T1 | State-leakage 29 testes | **Confirmado pela memória 17/05** (`feedback`/`project_pytest_unblock_2026-05-17`). Não re-rodado nesta fase — fora do escopo. | memória |

---

## 4. Recomendação de ondas de implementação

A auditoria documental sugeriu sequência **K3 → A4 → A3 → A2**. Confirmo a ordem geral, mas com **K3 e A4 em paralelo** na Onda 1 — não há dependência real entre eles.

### Onda 1 — desbloqueio (paralelizável, sem conflito)

| Sub-tarefa | Subagent independente? | Por quê |
|---|---|---|
| **K3** ingerir 9 normas (IN SEMAD 3/2025, 7/2024; Lei GO 18.104, 18.102, 21.231; Decreto GO 9.710/2020; IN INCRA 131/2023; CONAMA 428/2010, 429/2011) | Sim | Mexe só no pipeline de ingestão e no `knowledge_catalog` (escrita). Não toca em `app/agents/` nem em `app/schemas/`. |
| **A4** estender `Risco` e `DiagnosticoPreliminarContent` (Pydantic + tests do schema) | Sim | Mexe só em `app/schemas/stage_output.py` e nos testes correspondentes. Não depende de K3. Reutiliza `RegulatoryDiagnosis` (já existe) como destino do JSONB. |

### Onda 2 — habilita citações e cruzamento (depende da Onda 1)

| Sub-tarefa | Depende de | Por quê |
|---|---|---|
| **A3** citation evaluator no Diagnóstico | **K3** (forte) e **A4** (leve) | Sem K3, evaluator marca a maioria das citações da skill como suspeitas e o agente vira ruído. A4 ajuda transportando citações em campos tipados, mas não bloqueia. |
| **A2** `auditor_imovel` (matriz documental + cálculos determinísticos) | **A4** (forte) | Precisa do shape de divergência/risco para emitir output válido. Pode usar `RegulatoryIssue` (já existe!) como persistência. Parte espacial fica capada até **D1** (`Property.geom`), mas cruzamento documental roda sem geometria. |

### Limpezas paralelas (qualquer onda, baixo risco)

- **R1** polish da rebrand — 9 ocorrências em 5 arquivos secundários
- **T1** state-leakage 29 testes — sprint própria conforme memória
- **A5** já fechado, nada a fazer
- **ocr-automatico** apagar a branch obsoleta (após verificação manual de que de fato não há diff)

### Não-bloqueantes da skill, mas no roadmap

- **D1** parser shapefile + ingestão KML/SHP (destrava overlay PostGIS no A2)
- **P3** pipeline de transcrição de áudio estruturada (12 blocos) — a skill espera receber `metadata.transcricao_estruturada` pronto; quem produz isso é upstream
- **P4** tool determinística de cálculo de uso do solo

---

## 5. Riscos / surpresas encontradas no código

1. **`RegulatoryDiagnosis` + `RegulatoryIssue` já existem em produção** (Sprint A1 Tarefa D1, commit anterior ao 14462b5 da Sprint Z). A auditoria documental e a memória tratavam isso como gap B3 aberto. Reduz escopo de A4 para "estender forma do conteúdo" (Pydantic) — não "criar tabela versionada". E A2 ganha de presente a persistência de issues (`RegulatoryIssue`).
2. **MemPalace stub já foi deletado** (commit `757b7de`, parte da Sprint Z) — A5 está fechado, não é "limpeza pendente" como o doc dizia.
3. **PROJECT_NAME já é "Regente Ambiental"** no `config.py`. Memória dizia "Amigão" ainda — desatualizada. Restam 9 ocorrências em arquivos secundários (não-funcionais).
4. **`feat/ocr-automatico` é branch fantasma** — existe em `origin` mas sem commits exclusivos vs `main`. Conteúdo já integrado por outro caminho.
5. **Suite de testes muito maior do que docs sugerem** — 411 funções coletadas, não 102 nem 39. Sinal de descompasso entre ESTADO_ATUAL/CRUZAMENTO e a realidade do projeto.
6. **K3 é o gap mais crítico** — 9/11 normas-chave da skill ausentes. É também o mais barato: pipeline de ingestão pronto, scripts existem. Custo/valor disparado.
7. **Risco de divergência semântica em A4** — `DiagnosticoPreliminarContent` (Pydantic, `app/schemas/stage_output.py`) e `RegulatoryDiagnosis.content` (JSONB livre) hoje **não conversam**: o JSONB aceita qualquer forma. A4 precisa amarrar — caso contrário a estrutura do diagnóstico vai divergir entre o que sai do agente e o que persiste na tabela versionada.

---

## 6. O que NÃO foi resolvido nesta fase (deixado em aberto para humano)

Mantém os pontos abertos da auditoria documental (seção 5):

- **A4 — extensão vs. derivados.** Estende `DiagnosticoPreliminarContent` v2, ou cria `DiagnosticoConsolidadoContent`/`DiagnosticoSaneamentoContent` como derivados? A descoberta de que `RegulatoryDiagnosis` já existe simplifica a decisão: o JSONB é "qualquer derivado de `StageOutputContent`", então a sub-tipagem fica natural.
- **A2 — agente próprio vs. tool no Diagnóstico.** O comentário em `regulatory.py:11` fala em "agente `auditor_imovel`", mas `RELATORIO_DESCOBERTA` sugere "agente único com tools determinísticas". Decisão de design pendente.
- **ADR-010** — escopo tenant vs global do conhecimento exemplar, quem cura, sinal de desfecho.

---

## Resumo executivo (3 frases)

A Fase 0 confirma A2/A3/K3 como gaps reais e descobre que **A4 está muito mais perto do que a auditoria documental supunha** (tabela versionada `RegulatoryDiagnosis` + `RegulatoryIssue` já em produção). **A5 (MemPalace) e o miolo de R1 (PROJECT_NAME) já estão fechados.** A próxima fase pode rodar **K3 e A4 em paralelo** na Onda 1, e A3+A2 na Onda 2 — com K3 sendo o investimento de maior assimetria custo/valor (barato, destrava A3, sem ele a skill cita no vácuo).
