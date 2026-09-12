# Frente J — fechamento de contrato (os 7 do Codex + o gate E2E)

**Branch:** `fix/fechamento-contrato-spec` · **Worktree:** `wt-fechamento-contrato`
**Insumo:** `docs/auditoria/REAUDITORIA_CODEX_11-09.md` (passo zero)
**ADRs:** adendos em 065, 066, 067, 068 — nenhuma ADR nova
**Dívidas:** nenhuma nova numerada (cada item é contrato já declarado fechado
pela metade); faixa 200-299, próximo livre continua **#225**
**Data:** 11/09/2026

> Nenhuma feature nova. Cada item é um contrato da spec que existia pela
> metade. Ao fim, o #23 atravessa tela → decisão → consolidação → recarga →
> nova sessão como UM gate, no ambiente autenticado.

---

## Como esta frente foi conduzida

O Codex implementou os 7 itens (backend + frontend) e parou **antes de
validar** ("vou validar primeiro a sintaxe e os testes focados, antes de
documentar qualquer fechamento"). A retomada começou por aí: commit de
checkpoint do que ele deixou (`df67c2b`, "sem validação"), depois ruff, tsc,
eslint, vitest, pytest — e a revisão crítica do código, que achou o que a
seção "O que a validação achou" registra. Só então docs, gate e relatório.

## Item a item

| # | contrato | o que existia pela metade | o que fecha | onde |
|---|---|---|---|---|
| 1 | REV-001 — invalidação enxerga reextração cacheada | `_decisao_alterada_apos` só olhava `updated_at` (NULL em linha nova) | `created_at OR updated_at > cutoff`; marco mais antigo calculado em Python; motivo "nova evidência" | `artifact_staleness.py`; ADR-068 adendo §1 |
| 2 | CONF-001/STATE-001 — "gravada" honesta | `any(consolidated_at)` ⇒ gravada | `all` ⇒ `gravada`; misto ⇒ `parcialmente_gravada` (selo âmbar); indicador não conta como decidida | `reconciliation_decisions._estado_de`, `process_indicators`, `DecisoesPanel`; ADR-067 adendo |
| 3 | REV-001 — aceite de proposta desatualizada | aviso no GET, aceite passava | `POST /accept` recusa **422 com a razão**; proposta continua `sent`; tela mostra banner, bloqueia o botão, 422 vira toast | `proposals.py`, `ProposalEditor.tsx`; ADR-068 adendo §2 (corrige "aviso") |
| 4 | HIST-001 — `rl_vigente` respeita vigência | última RL do papel, mesmo baixada | exclui baixado/retificado/expirado; `ultimo_por_destino` não promove ato baixado à coluna | `observacao_registral.py`; ADR-066 adendo |
| 5 | CONF-002 — tipo editável na decisão | tipo do modelo era terminal; cartão só aceitar/reabrir | `reclassificar` (por campo e pela decisão), `tipo_sugerido` preservado, reconciliação consome o decidido; `escolher_fonte`/`editar` no cartão; UI: "Editar tipo" em qualquer pendente tipada, "Editar valor"/"Escolher esta fonte" em divergência | `staging_consolidation.decide_field`, `decidir_decisao_agrupada`, schemas, `DecisoesPanel`; ADR-065 adendo |
| 6 | DOC-001 — "lido" = legível; estados negativos; projeção na API | `done` ⇒ lido (doc 551 "lido" com 444 chars de boilerplate) | `texto_sem_conteudo_legivel` (mesma régua da `extraction_status`); `processando`/`erro_leitura`/`desatualizado`/`substituido`/`nao_apresentado`/`dispensado`; `DocumentResponse.lifecycle_status` (lote, 1 query); selo na aba Documentos | `document_lifecycle.py`, `documents.py`, `DocumentsTab`; ADR-068 adendo §3 |
| 7 | ENT/HIST — sucessão; data do caso | só `compra_venda` transferia; `date.today()` | `sucessao`/`inventario`/`adjudicacao`/`formal_partilha` no vocabulário, prompt e cadeia; `data_referencia_do_processo` (`opened_at`→`created_at`); termo sem referência ⇒ `indeterminado` | `observacao_registral.py`, `ficha01_extraction.py`; ADR-065/066 adendos |

## O que a validação achou no código do Codex (e corrigiu)

1. **`Evidencia.tipo_observacao` obrigatório derrubava a Conferência inteira.**
   Campo posicional sem default antes de `status`; `_montar_decisao_titularidade`
   (e a evidência sintética de soma) construíam `Evidencia(...)` sem ele →
   `TypeError`. Medido rodando `build_decisions` sobre as 116 linhas reais do
   #23: `GET /processes/23/staging-decisions` **quebraria em produção** no
   primeiro deploy. Corrigido (opcional com default, preenchido na
   titularidade) + teste de regressão `TestFrenteJEvidenciaTipada`.
2. **`desde` errado na invalidação.** `ORDER BY created_at, updated_at` +
   `.first()` escolhia uma linha antiga com `updated_at` recente antes de uma
   nova com `created_at` mais cedo. Marco agora é o mínimo entre todas as
   candidatas (Python). Teste `test_desde_e_o_marco_mais_antigo_...`.
3. **`derivar_vigencia` sem data de referência afirmava "vigente"** para
   arrendamento com termo final (caía no passo 3, "tem `data_ato`"). Agora
   `indeterminado`; gravame com data continua `vigente`. Testes em
   `TestFrenteJVigenciaEDestino`.
4. **RL baixada ainda gravava a coluna.** `rl_vigente` foi corrigido pelo
   Codex, mas `ultimo_por_destino` (quem grava `averbacao_rl`) continuava
   promovendo a última do papel. Agora ignora `baixado`.
5. **N+1 na listagem de documentos.** `_with_lifecycle` por documento =
   uma query de staging por linha em `GET /documents` (que sem filtro devolve
   o tenant inteiro). `derive_document_statuses` em lote, uma query; teste
   de equivalência lote ≡ unitário.
6. **Reclassificar com rótulo desconhecido virava `nao_classificado` calado**
   pela precedência `A or B and C`. Agora 422 nomeando o rótulo; escape só
   quando pedido por escrito.
7. **Tela: "Editar tipo" só em divergência.** Corrigir tipo não depende de
   divergência (gravames "concordam" por definição). Reestruturado: tipo em
   qualquer pendente tipada; valor/fonte em divergência.
8. **`ProposalEditor` sem `onError`**: o 422 do item 3 morreria em silêncio
   (lição do caso 15). Toast + banner + botão bloqueado.
9. **vitest quebrado** pelo select de tipos (`findByText('Reserva Legal')`
   estrito colidia com a `<option>`). Corrigido no teste.
10. **A mensagem do bloqueio apontava porta trancada.** O 422 do item 3 dizia
    "Gere e valide uma nova versão", mas `POST /nova-versao` (S5-A) exige
    proposta **recusada ou expirada** — de `sent` não sai. O consultor leria a
    instrução e bateria noutro 422. Corrigido para nomear o movimento real
    (**Recusar → Nova versão**), na doutrina do ADR-039 (bloqueio de fluxo diz
    o próximo passo que existe). O teste percorre o caminho inteiro:
    422 → `reject` 200 → `nova-versao` 201 (rascunho).
11. **`escolher_fonte` numa evidência sem destino rejeitaria a matrícula
    inteira.** `_reject_siblings` casa `target_entity`/`target_field`; numa
    observação sem destino (gravame, baixa, aditivo, arrendamento — ADR-065)
    isso é `IS NULL AND IS NULL`, ou seja, **todas** as outras observações da
    mesma matrícula viravam `rejeitado` de uma vez. O caminho só ficou
    alcançável porque a Frente J expôs `escolher_fonte` na decisão agrupada
    (item 5) — a guarda entra junto com ele: linha sem destino não tem irmão
    a rejeitar. Teste `TestFrenteJEscolherFonteSemDestino`.
12. **Shadowing em `decidir_decisao_agrupada`**: o loop do `reabrir` usava a
    variável `staging_id`, o mesmo nome do parâmetro lido no fim da função —
    o fallback de lá procuraria a decisão do último membro reaberto em vez de
    devolver o 500 honesto "a decisão sumiu". Renomeado para `membro_id`.
13. **Geoespacial viraria "Erro de leitura".** `not_required` estava no
    mesmo balde de `done`/`failed`: shapefile e KML, que entram sem OCR de
    propósito (gap D1), apareceriam com selo de erro. Agora leitura
    dispensada segue a escada pelo que existe e, sem tipo nem staging, fica
    em `recebido`. Teste `test_leitura_dispensada_nao_e_erro_de_leitura`.
14. **Dois uploads devolviam documento sem a projeção**: os early returns de
    geoespacial e de áudio em `confirm_upload` retornavam `db_doc` cru, então
    `lifecycle_status` vinha `null` só nesses dois caminhos — o contrato do
    `DocumentResponse` promete o campo em todos. Varridos os 3 endpoints que
    devolvem `DocumentResponse`: 5 pontos de retorno, todos com a projeção.
15. **O botão "Aceitar" não fechava a decisão de titularidade** (achado da
    camada UI do gate). `decidir_decisao_agrupada` percorria as EVIDÊNCIAS, e
    nem todo membro vira evidência: a titularidade monta a lista pela CADEIA,
    então um ato de compra e venda sem adquirente/transmitente nomeado entra
    no grupo e não aparece. Medido no caso real: 3.181 com 3 membros para 2
    evidências, 3.673 com 4 para 2. A linha órfã nunca era aceita e a decisão
    ficava presa em "pendente" — a consultora clicava e a tela não mudava.
    Nenhuma suíte unitária tinha pego: só clicando, com dado real.
16. Docstring quebrado em `_linhas_de_observacoes` ("Sem\nA orquestração…").

## Item 5 — para onde cada tipo decidido leva a linha

Simulado sobre uma linha REAL do #23 (`staging_id=1606`, matrícula 3.181,
hoje `hipoteca`), trocando o tipo por cada um dos 20 do vocabulário e
recalculando destino (`destino_de`) e chave natural (`_chave_de`) — funções
puras, sem banco. Prova que a reclassificação não cria roteamento maluco: o
consultor muda O QUE o ato é, e a linha vai para a decisão que corresponde.

| tipo decidido | destino (coluna) | decisão resultante |
|---|---|---|
| `hipoteca`, `alienacao_fiduciaria`, `penhora` | — (gravame não tem coluna própria) | `matricula:3181:gravames` |
| `compra_venda`, `sucessao`, `inventario`, `adjudicacao`, `formal_partilha` | — | `matricula:3181:titularidade` |
| `reserva_legal` | `matricula.averbacao_rl` | `matricula:3181:reserva_legal` |
| `app` | `matricula.averbacao_app` | sem agrupamento (grava a coluna, sem decisão própria na Frente G) |
| `aditivo`, `baixa`, `georreferenciamento`, `arrendamento`, `servidao`, `usufruto`, `compromisso_compra_venda`, `area_registrada`, `nao_classificado` | — | sem agrupamento (visível, campo a campo) |

Rótulo fora dos 20 → **422 nomeando o rótulo**; `nao_classificado` só entra
quando pedido por escrito.

## Regressão: gates de C–H

Rodado em 12/09/2026, na máquina do André, com Docker de pé (a virtualização
foi ligada no reboot).

| gate | como | resultado |
|---|---|---|
| **suíte completa do backend** | `pytest tests/` com Testcontainers (Postgres + PostGIS + pgvector) | **1976 passed, 0 failed** (19m30s) — e o mesmo job verde no CI do PR (10m44s) |
| C — contenção da entrada (ADR-064) | `test_contencao_entrada.py` | verde (dentro da suíte) |
| D — fiação da entrada (PR #155) | `test_fiacao_entrada.py` | verde |
| E/F — tipo + temporalidade (ADR-065/066) | `test_observacao_registral.py` | verde — 53 casos (46 anteriores + 7 desta frente) |
| G — decisões (ADR-067) | `test_reconciliation_decisions.py`, `test_staging_decisions.py` | verde |
| H — estado e invalidação (ADR-068) | `test_document_lifecycle.py`, `test_artifact_staleness.py`, `test_process_indicators.py` | verde |
| frontend | `npm test` (26 arquivos) | **167 passed** |
| frontend | `npm run build` (`tsc -b` + vite) — **o gate real do CI** | verde |
| spec do gate E2E | `tsc --noEmit -p tsconfig.e2e.json` | verde |
| backend | `ruff check app/ tests/` | verde |

> **Armadilha registrada:** `npx tsc --noEmit` no `tsconfig.json` da raiz do
> frontend **não checa nada** — é um solution file (só `references`, sem
> `include`). O typecheck que vale é `npm run build` (`tsc -b`). Foi assim que
> um erro de tipo no teste novo passou local e quebrou o CI.

## Gate E2E — ambiente autenticado

**Executado em 12/09/2026.** Relatório completo, com a spec da Isis colada ao
lado de cada resultado, os payloads e os prints:
[`fechamento_contrato/GATE_E2E.md`](./fechamento_contrato/GATE_E2E.md).

Resumo dos três percursos:

| percurso | o que provou |
|---|---|
| 1 — fluxo da consultora | 6 documentos reais → extração real (194 s, LLM real) → **115 linhas = 20 decisões (51 linhas) + 64 sem agrupamento** → 3 decisões, uma com edição de tipo → escolher fonte numa divergência crítica sem fonte autoritativa (**13 irmãos intactos**) → consolidar → F5 → logout/login: **diff vazio nas seis telas** |
| 2 — invalidação | documento novo ⇒ diagnóstico e proposta desatualizados com razão e data; **reextração com texto cacheado** (161,8 s, `ocr_rodou_de_novo=false`, 31 linhas novas) ⇒ diagnóstico validado vira "nova evidência"; aceite da proposta ⇒ **422 com a razão**, proposta segue `sent` |
| 3 — itens 4/6/7 | RL baixada não é promovida nem grava a coluna (vence o ato anterior válido); CNH-e `done` mas **`erro_leitura`**, KML `not_required` mas **`classificado`**; sucessão/formal de partilha levam `titular_atual` ao herdeiro (sem o item 7, apontaria o falecido) |
| **UI (Playwright, 5/5)** | o gesto: cartões na tela, "Aceitar proposta", **"Editar tipo"**, "Gravar na base", F5 e logout/login com os **seis números idênticos**, banner + botão bloqueado na proposta, upload pela tela com selo "Erro de leitura" |

Não provado, com a razão dita por inteiro (retrocesso automático de etapa,
"declarado inexistente", `checklist_documental` do processo do gate, e um
achado lateral no `/auth/me`): seção final do `GATE_E2E.md`.

## Relatório de reconciliação do #23 — completo

Versionado em `docs/trabalhos/reconciliacao_decisoes.md`, seção
"Resultado — medido em 11/09/2026": as **116 linhas** listadas por id, as
**21 decisões** com todas as evidências, e as **66 sem agrupamento** com
motivo. Medido só leitura (Supabase MCP) + `build_decisions` local com o
código desta branch. Achados registrados ali: RL e gravames viraram decisão
como a Frente I previa; RL do imóvel diverge **crítico** (CAR 437,7632 ×
matrículas); titularidade da 3.313 saiu "IZAURA DE FATIMA PEGO (R-11)" porque
o R-20 não veio com os dois lados — não-determinação da entrada, a decidir
na tela (agora editável).
