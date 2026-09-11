# Frente H — estado único e invalidação transitiva (medição)

**Branch:** `feat/estado-unico-invalidacao` · **ADR:** 068 · **Dívidas fechadas:**
DOC-001, STATE-001, REV-001 (nenhuma dívida numerada nova)
**Insumo:** `docs/auditoria/AUDITORIA_INDEPENDENTE_FASE1_2026-09.md` bloco E,
`docs/auditoria/AUDITORIA_INDEPENDENTE_REGENTE_4a96b5d.md` bloco C,
`docs/adr/067-decisao-como-unidade-da-conferencia.md`, `docs/adr/039-rota-
nasce-do-diagnostico-fundamentado.md`
**Data da medição:** 11/09/2026

---

## Revisão de código — achados e correções (mesma rodada)

Um `code-reviewer` independente leu o diff completo antes do PR abrir. Quatro
achados reais, todos corrigidos nesta mesma sessão (re-medido depois — tabelas
abaixo já refletem o código corrigido):

1. **Crítico** — o bloco DOC-001 em `consolidate_process` rodava DEPOIS do
   `db.commit()` real, sem guarda: uma exceção ali propagaria e o endpoint
   reportaria "nada foi gravado" quando na verdade JÁ TINHA gravado. Corrigido
   com `try/except Exception` largo (idêntico ao padrão que `emit_leitura_
   event` já usa), `logger.warning`, sem propagar.
2. **Importante** — REV-001 tinha três falsos negativos medidos: documento
   lido tardiamente (`extracted_at` depois do corte, `created_at` antes),
   "reabrir" uma decisão zerando `decided_at` (apaga o próprio sinal), e a
   consolidação carimbando `consolidated_at` sem nunca tocar `decided_at`.
   Corrigido trocando a comparação para `Document.created_at`/`extracted_at`
   e `ExtractedFieldStaging.updated_at` (toca em qualquer UPDATE da linha).
   ADR-068 atualizada para não overclaim "nunca falso negativo".
3. **Importante** — `DecisoesPanel.tsx` (onde o consultor decide de fato) não
   invalidava a query do banner canônico de `ConsolidacaoPanel.tsx` — dois
   números sobre o mesmo fato podiam discordar na mesma tela até um reload.
   Corrigido com uma `queryKey` compartilhada (`progressoConferenciaKey`).
4. **Menor** — três queries novas sem filtro `tenant_id` explícito (nenhuma
   com vazamento cross-tenant alcançável, mas o padrão do CLAUDE.md é
   explícito). Corrigidas.

---

## Ambiente da medição

| item | valor |
|---|---|
| banco | Testcontainers (Postgres via `tests/conftest.py`, imagem `amigao_do_meio_ambiente-db:latest` — postgis+pgvector), descartável, um container por sessão de teste |
| entrada | fixture ELODI (`tests/services/test_reconciliation_decisions.py::_elodi`) — a mesma fixture já vetada nas Frentes E/F/fiação/G, valores medidos de `extracted_text` real de produção (docs 546/547/549) |
| LLM | nenhuma chamada nesta frente — STATE-001/DOC-001/REV-001 são serviços determinísticos (leitura de estado, projeção, comparação de timestamp). "Duas execuções onde houver LLM" não se aplica; a evolução pendente→decidida→gravada foi medida em duas chamadas de `consolidate_process`, mesma convenção de duas passagens do GATE da Frente G (guard fantasma da matrícula) |
| produção | não acessada nesta rodada |
| teste que reproduz esta medição | `tests/services/test_gate_frente_h.py::test_gate_frente_h_estado_unico_elodi` (roda em CI/local via `pytest -s` para ver a tabela) |

## GATE 1 — STATE-001: os seis números, lado a lado

Checklist do processo (3 itens: matrícula 3.181 recebida COM documento, CCIR
recebido SEM documento — o achado da triagem —, ITR pendente) + staging ELODI
completo (10 decisões após agrupamento pelas regras da Frente G — composição
×4, área ×1 medida, RL, gravames ×1 agregado, titularidade, representante,
CAR — mais o resto em `sem_agrupamento`, nunca escondido).

| estágio | checklist (`get_checklist_status`) | conferência (`progresso_conferencia`) | dossiê.checklist_summary | dossiê.conferencia_summary |
|---|---|---|---|---|
| 1 — staging recém-chegado | 2/3 recebidos (1 sem doc) → **33.3%** | 0/10 decididas · 0 gravadas · 10 pendentes | idêntico ao checklist ⬅ | idêntico à conferência ⬅ |
| 2 — composição da 3.181 decidida | 2/3 recebidos (1 sem doc) → **33.3%** | 1/10 decididas · 0 gravadas · 9 pendentes | idêntico ⬅ | idêntico ⬅ |
| 3 — composição da 3.181 gravada | 2/3 recebidos (1 sem doc) → **33.3%** | 1/10 decididas · **1 gravada** · 9 pendentes | idêntico ⬅ | idêntico ⬅ |

Em cada estágio, `dossie.checklist_summary == asdict(get_checklist_status(...))`
e `dossie.conferencia_summary == progresso_conferencia(...).to_dict()`,
verificado por `assert` no teste (não só por leitura visual) — o dossiê não
recalcula, só embute a mesma resposta.

**Checklist não muda entre os 3 estágios** — ele mede DOCUMENTOS do processo
(quantos entraram), não decisões da Conferência; nenhuma das ações do
estágio 2/3 muda quais documentos existem. É a divergência ESPERADA e
nomeada, não um bug: as duas perguntas são diferentes (Astra bloco C).

**Resultado da consolidação (`campos_gravados`, o delta de UMA chamada) vs.
`progresso_conferencia.gravadas` (o total corrente):**

| chamada | `campos_gravados` (writes desta chamada) | `progresso_conferencia.gravadas` (total corrente, medido depois) |
|---|---|---|
| passagem 1 | 0 | — |
| passagem 2 | 0 | **1** |

Medido, não hipotético: `campos_gravados` ficou em 0 nas duas passagens
(estabelecer/reconciliar a matrícula 3.181 não passa pela mesma contagem de
"writes" de campo que grava valores em `Client`/`Property`), enquanto AMBAS
as linhas do grupo `composicao` (CAR + certidão) receberam o carimbo
`consolidated_at` — e `progresso_conferencia` conta a decisão como "gravada"
porque pelo menos um membro do grupo carimbou. Confirma, na prática, o achado
da Astra (bloco C, família 5): "aceites, destinos alterados e linhas
carimbadas são unidades distintas". `campos_gravados` responde "quanto esta
CHAMADA escreveu"; `progresso_conferencia.gravadas` responde "quanto está
gravado AGORA, no total". Rotulados como perguntas diferentes na ADR-068 — não
fundidos num só número.

**Checklist marcado sem documento não conta:** o item CCIR foi marcado
`received` sem `document_id` (`mark_item_received(checklist, "ccir")`, sem o
terceiro argumento) — o gesto exato do achado da triagem
(`TRIAGEM_AUDITORIA_CODEX.md:341-350`). `received=2` mas `received_without_
document=1`, e o `completion_pct` (33.3%, 1 de 3 = a matrícula com documento
de verdade) NÃO conta o CCIR como concluído — antes desta frente contaria
2/3=66.7%.

## GATE 2 — DOC-001: transição auditada de um documento

Documento: a certidão da matrícula 3.181 (`mat_3181`), que carrega 2 linhas de
staging na fixture (`certidao_3181` — decidida no GATE 1; `area_3181` — nunca
tocada, continua `pendente`).

```
recebido → extraido    autor=None ação=document_status_changed
estado atual derivado: extraido
```

**Por que "extraido" e não "conferido"**, mesmo com `certidao_3181` já
`aceito`: o documento tem DUAS linhas de staging, e `area_3181` continua
`pendente` — `derive_document_status` exige que TODAS as linhas do documento
saiam de pendente, não só as de uma decisão. Medido, não assumido: é
exatamente o comportamento que impede um documento parcialmente decidido de
aparecer como "conferido" na tela.

A sequência começa em "recebido" (implícito — o próprio `action="uploaded"`
do upload, com autor, já o marca) e pula direto para "extraido" porque a
fixture grava `ocr_status=done` e `document_type="matricula"` diretamente no
banco (setup de teste, não os serviços reais) — os degraus "lido" e
"classificado" já estavam alcançados na primeira leitura. Em produção, onde
OCR e classificação rodam em momentos separados de verdade
(`ocr_tasks.emit_leitura_event`, `document_classification.
aplicar_classificacao`), a sequência aparece completa — ver
`tests/services/test_document_lifecycle.py::
test_registrar_transicao_grava_sequencia_completa_com_autor`, que reproduz
recebido→lido→classificado→extraído→conferido, cada transição com o autor
correto (`None` para gatilho automático, `user.id` para gesto humano),
hash-chain presente em todas.

## GATE 3 — REV-001: avisa, nunca regenera

Coberto por `tests/services/test_artifact_staleness.py` (6 cenários,
diagnóstico e rota):

- diagnóstico validado + documento novo depois da validação →
  `aviso_desatualizado.tipo == "documento_novo"`, `version`/`content`
  intactos (nada regenerado, nada apagado);
- documento que já existia ANTES da validação → sem aviso (não é novidade);
- decisão da Conferência (`ExtractedFieldStaging.decided_at`) alterada depois
  da validação → `aviso_desatualizado.tipo == "decisao_alterada"`;
- diagnóstico sem validação usa a própria criação como corte;
- rota validada + documento novo → aviso, `RotaStatus` não tocado por este
  módulo (só lê).

Nenhum teste desta frente regenera ou apaga um artefato — a garantia
estrutural é que `checar_desatualizacao`/`desatualizacao_*` só fazem `SELECT`.

## Regressão — frentes C-G

`pytest -k "checklist or dossier or rota or consolidation or regulatory or
diagnos or classification or ficha01"` + `tests/services/
test_reconciliation_decisions.py`: **413 passed**, 0 falhas, 0 skips
inesperados (rodado sobre a branch desta frente, 11/09/2026).

## Frontend

`npx tsc --noEmit`: 0 erros (node_modules instalado na worktree para a
checagem — sem isso o comando sai 0 vazio e mente, ver `feedback_npx_sem_
node_modules_passa_vazio`). Telas que passam a mostrar o aviso:
`ConsolidacaoPanel.tsx` (banner "Conferência: N/M decisão(ões)..."),
`RotaTab.tsx` (banner `aviso_desatualizado`, ao lado do `aviso_fundamento` do
ADR-039 — que a auditoria desta frente encontrou sem render nenhum na UI, uma
lacuna pré-existente ao ADR-039 fechada de graça aqui), `DiagnosisAssinatura.
tsx` (banner no card de diagnóstico validado), `ProcessChecklist.tsx` (nota
de transparência sobre itens recebidos sem documento).
