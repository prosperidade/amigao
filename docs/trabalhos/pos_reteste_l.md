# Frente L — três correções independentes

Branch `fix/pos-reteste-l` · worktree `wt-pos-reteste` · dívidas faixa 200-299.
Medido em 12/09/2026.

Três itens sem dependência entre si. Dois entregues e provados; o terceiro
parado numa credencial que não existe nesta máquina — dito onde parou e o que
falta, não contornado.

---

## 1 — O `except` que grava numa sessão envenenada

### A classe

A Frente K mediu a primeira ocorrência em `consolidate_process_endpoint`: um
`DataError` no `flush` abortou a transação, o bloco de resgate leu
`current_user.tenant_id` (lazy-load numa sessão morta) e caiu de
`PendingRollbackError` **antes** de registrar a auditoria. A consultora recebeu
`Internal Server Error` no lugar da frase que aquele bloco existe para dar.

O Codex apontou o mesmo desenho em `legislation_service.py:82-113`. A varredura
desta frente foi atrás da CLASSE inteira, não do ponto: um script AST percorreu
`app/` procurando `try` que toca o banco com um `except` que escreve no ORM sem
`rollback` antes — incluindo o caso transitivo, em que quem toca o banco no
`try` é uma função que recebe `db` como argumento.

### O que a varredura achou

**Cinco pontos da classe — todos corrigidos:**

| ponto | o que o `try` derruba | o que o `except` perdia |
|---|---|---|
| `app/services/legislation_service.py:113` | `db.flush()` do texto extraído | status `failed` + causa; documento ficava `processing` |
| `app/workers/ai_tasks.py:100` (`run_llm_classification`) | `db.commit()` do processo + job | AIJob ficava `running` **para sempre**, engolido por `except Exception: pass` |
| `app/workers/ai_tasks.py:193` (`run_document_extraction`) | idem | idem |
| `app/workers/audio_tasks.py:210` (budget guard) | `check_tenant_monthly_budget` CONSULTA o banco | `ocr_status=failed`; documento preso em `processing` |
| `app/workers/ocr_tasks.py:267` (budget guard) | idem | idem — mesmo sintoma que o PR #69 caçou por outra causa |

**Cinco candidatos examinados e descartados, com razão:**

| ponto | por que NÃO é da classe |
|---|---|
| `app/api/v1/contracts.py:386` | o `try` é `render_pdf` — renderização pura, não toca sessão |
| `app/api/v1/processes.py:1153` | o `try` é `run_agent_chain.delay` — fila Celery; falha de fila não aborta transação |
| `app/api/websockets.py:43` | Redis, não banco |
| `app/workers/audio_tasks.py:130` | o `try` é `storage.download_bytes` — rede/S3, não sessão |
| `app/workers/ocr_tasks.py:153` | idem |

### Os dois desenhos de conserto

Não é um só, porque não é um problema só — **de quem é a transação** muda a
resposta:

- **Worker dono da própria sessão** (`SessionLocal()`): porta nova
  `app/core/db_rescue.py::gravar_desfecho_de_falha` — desfaz a transação morta,
  recarrega a linha **pelo identificador** (nunca pelo objeto ORM expirado),
  escreve e commita. O `except Exception: pass` que havia nos workers virou
  `logger.exception`: socorro que falha grita, não some.

- **Serviço dentro da transação de outro** (`legislation_service`, chamado pelo
  endpoint que acabou de criar a própria linha): `rollback` ali apagaria o
  documento que se quer marcar como falho. O trecho arriscado passou a rodar em
  `db.begin_nested()` — o SAVEPOINT desfaz só o que caiu, a transação de fora
  sobrevive, e com ela a linha que recebe o carimbo.

### De brinde, um motivo que mentia

O guard de orçamento tratava "orçamento esgotado" e "não consegui consultar o
orçamento" como a mesma coisa. Agora o documento recebe o motivo certo e o
retorno distingue `budget_exceeded` de `budget_check_failed`. Antes do conserto
isso era inócuo (a escrita morria de qualquer jeito); depois dele, a frase
errada ficaria gravada na base.

### O teste

`tests/services/test_frente_l_sessao_envenenada.py` — 8 testes, **o veneno é
real**:

- byte NUL no texto (o que um PDF com camada de texto corrompida entrega) →
  o `flush` cai de verdade;
- `SELECT 1/0` dentro do guard de orçamento → o Postgres aborta a transação de
  verdade.

E cobra o desfecho: o AIJob sai `failed` com a causa, o documento sai `failed`
com o motivo, e **a causa real sobe** — não o `PendingRollbackError` genérico.

Dois achados do próprio teste, que valem mais que o verde:

1. **O fixture compartilhado escondia o mecanismo.** `tests/conftest.py` faz
   `sessionmaker(bind=connection)`, e o default do SQLAlchemy 2 nesse arranjo é
   `join_transaction_mode="rollback_only"`: um `rollback()` desfaz a transação
   externa do teste inteiro. Com ele, o socorro "não achava a linha" — sintoma
   do harness, não do código. O módulo sobrepõe `db_session` com
   `create_savepoint`, que é o modo que a documentação recomenda para esse
   padrão e o que reproduz a semântica de produção. (As outras suítes de worker
   vão além: neutralizam `rollback()` para no-op — o que tornaria este conserto
   invisível.)

2. **O teste caiu no próprio bug que testa**: lia `processo.id` DEPOIS de
   envenenar a sessão. Os inteiros saem do ORM antes — a mesma regra que o
   código passou a seguir.

---

## 2 — As 57 unidades soltas da Conferência

### O número de partida

O percurso de navegador da Frente K terminou com
`Conferência: 19/76 decisão(ões) · 57 pendente(s)`: 20 decisões agrupadas e o
resto cobrado como clique avulso. O razão linha a linha daquela rodada
(`docs/trabalhos/consolidacao_real/razao_linha_a_linha.json`, 118 linhas do
staging **real** de produção da ELODI, 5 a mais que as 113 do percurso de
navegador) registra **58 soltas**. É contra esse arquivo — dado de produção,
não fixture — que esta frente mede.

### Os três grupos

**Grupo A — merecem chave natural (30 linhas → 12 decisões). Implementado.**

| o que era | quantas linhas | vira | por quê |
|---|---:|---|---|
| cartório, denominação, denominação anterior, registro anterior, NIRF/CIB | 17 | `matricula:<n>:identificacao_matricula` (4 decisões) | tudo responde UMA pergunta: "que matrícula é esta?". Eram 5 cliques por matrícula |
| código de certificação + averbação de georreferenciamento | 7 | `matricula:<n>:georreferenciamento` (4) | o código (que GRAVA) e a AV que o registra são o MESMO ato — mesma correção que a Frente K fez em `gravames` |
| arrendamento, compromisso de compra e venda (+ servidão e usufruto por vocabulário) | 4 | `matricula:<n>:limitacoes` (3) | atos que PESAM sobre a matrícula, com prazo ou sem; nenhuma regra os alcançava |
| município + UF | 2 | `imovel:<id>:localizacao` (1) | um fato locativo só, e que compete entre fontes |

Chave própria para `limitacoes`, e não fusão com `gravames`: arrendamento não é
garantia real, e misturá-lo faria a decisão de ônus da base — que só reúne
gravame — parecer incompleta.

**Grupo B — corretamente fora (28 linhas). Cada uma diz a razão.**

| sobra | linhas | razão (aparece na tela) |
|---|---:|---|
| `baixa` | 18 | é a **aresta** de outro ato: entra na decisão do ato que encerra, pela vigência que cancela |
| `nao_classificado` | 5 | ato que o vocabulário não cobre — reclassifique para que uma chave o alcance |
| `aditivo` | 3 | altera outro ato, e a extração **não registra qual**; agrupar seria adivinhar |
| `app_declarada_ha` | 1 | assimetria conhecida — ver abaixo |
| `modulos_fiscais` | 1 | declaração de fonte única do CAR; agrupar não pouparia gesto |

Antes desta frente as 28 caíam todas na mesma frase genérica *"tipo sem chave
natural mapeada nesta frente"*. "Continuar individual" e "ninguém pensou nisso"
apareciam iguais na tela; agora não.

E a frase chega à tela: o backend sempre mandou `sem_agrupamento[].motivo` e
**ninguém o lia** — `ConsolidacaoPanel` usava a resposta só para saber que
staging_ids tirar da lista. Dar razão própria a cada sobra e deixá-la no payload
seria decoração. A linha solta passa a mostrar *"Decisão individual: <razão>"*,
no mesmo desenho dos selos que já existem ali (`sem_casa`, `sem_ancora`).

**Grupo C — precisam da Isis. Não inventado.**

1. **As 18 baixas** (13 só na matrícula 3.313). O sistema já usa a baixa para
   calcular o que está vigente; a tela mostra cada uma solta. A pergunta é de
   produto: a consultora quer **decidir** cada baixa, ou ver só o resultado
   líquido dentro da decisão de gravames do ato que ela encerra? As duas são
   defensáveis e mudam o número de gestos.
2. **Os 3 aditivos.** Mesma pergunta, mais um bloqueio técnico: o aditivo não
   carrega referência ao ato que altera. Dobrá-lo na decisão do ato exigiria a
   Isis dizer que quer isso E uma mudança na extração para gravar o vínculo.
3. **`denominacao_anterior`** entrou em "identificação da matrícula". É
   identidade ou nota histórica? Chamada menor, mas é dela.

### Achado fora do recorte

**APP não tem chave; Reserva Legal tem duas.** A RL ganhou chave por matrícula
(regra 2a) e por imóvel (2b). APP — que está no mesmo `TIPOS_AREA_PARCIAL`, tem
a mesma coluna (`averbacao_app`) e o mesmo par CAR × matrícula — não tem
nenhuma. No caso #23 isso custa 1 linha solta (`app_declarada_ha`) e nada mais,
porque não há averbação de APP no caso. Num caso que tenha, custa exatamente a
divisão que a regra da RL já conserta. Ficou de fora por disciplina de recorte
(implementá-la puxa `_ASPECTOS_NUMERICOS`, `_injetar_*` e rótulos), e está
registrada aqui em vez de resolvida em silêncio.

### O gate

`tests/services/test_frente_l_soltas.py` replica as 118 linhas reais contra
`build_decisions`:

```
soltas   58 → 28
decisões 20 → 32
118 linhas: nenhuma fora de decisão E fora das soltas
toda solta que sobra tem razão própria (nenhuma na frase genérica)
```

### Um defeito do próprio conserto, achado antes do PR

Dar chave a `limitacoes` criou, de graça, um problema que `gravames` já tinha
resolvido: as duas averbações de arrendamento da 3.181 caem no mesmo `campo`
(`observacao`) e o ramo de texto de `_comparar` as poria **uma contra a
outra** — "divergem" entre dois contratos que coexistem, e uma proposta que
descartaria o outro. Dois atos não são duas versões de um fato.

`_ASPECTOS_DE_ATO = {gravames, limitacoes}` passou a reger os três pontos que
já tratavam gravame assim: a evidência é rotulada pelo ATO (AV.10, R.15), a
comparação não põe atos em competição, e a proposta é a síntese, não um
vencedor. A averbação dentro de `georreferenciamento` também deixou de se
chamar "observacao" na tela.

O replay de produção **não pegaria isso**: o `razao_linha_a_linha.json` não
guarda `atributos`, então ali as duas averbações chegam sem `ato` e sem
`vigencia`. O teste que fecha esse caminho
(`test_dois_arrendamentos_na_mesma_matricula_nao_competem`) traz os `atributos`
que a produção grava — é a fronteira do harness, dita em voz alta em vez de
descoberta pela consultora.

### Dois testes de terceiro reprovaram o conserto — e estavam certos

1. `test_campos_sem_regra_de_chave_aparecem_visiveis` usava `cartorio` como
   exemplo de campo sem chave. Deixou de ser: a mudança é exatamente esta.
   O teste ficou guardando o mesmo mecanismo com os campos que **seguem** sem
   regra (`modulos_fiscais`, `numero_ccir`, `app_declarada_ha`), e ganhou o
   contraexemplo (`cartorio` agora cai em `identificacao_matricula`) para que a
   mudança seja deliberada, não deriva.
2. `test_reclassificar_que_tira_a_linha_da_decisao_nao_e_erro` reclassificava
   hipoteca → **arrendamento** para provar que esvaziar uma decisão não é erro.
   Arrendamento passou a ter chave (`limitacoes`), então o teste mediria outra
   coisa e continuaria verde. Passou a usar `baixa`, que segue de fora de
   propósito.

Nos dois casos o teste foi ajustado porque o CONTRATO mudou de propósito, não
para calar vermelho — e o motivo está escrito no próprio teste.

---

## 3 — OCR dos PDFs originais — PARADO, com o que falta nomeado

**O que está pronto:** `scripts/gate_ocr_originais.py`. Baixa cada original do
storage, roda a cascata REAL (`extract_text_from_pdf`: pypdf → Gemini Vision →
OpenAI Vision) e monta a tabela produção × OCR-do-arquivo por documento:
caracteres, método, modelo, custo, similaridade normalizada e presença das
áreas `926,3654` / `725,4663` — inclusive com outra pontuação, que é
exatamente o achado que a frente procura.

Não usa banco descartável: usa **banco nenhum**. `extract_text_from_pdf` é
função pura sobre bytes, e o lado "produção" entra por arquivo exportado. Assim
o gate não tem como escrever onde não deve.

**O que falta, e por isso não rodou:**

1. **Credencial de leitura do R2 de produção.** O `.env` desta máquina aponta
   para o MinIO local (`localhost:9000`) — os originais do #23 não estão nele.
   Preciso de `MINIO_SERVER` (`<account>.r2.cloudflarestorage.com`),
   `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` e o bucket, com `S3_REGION=auto`
   (R2 recusa `us-east-1` no GET — dívida já registrada).
2. **O lado de produção da tabela.** Existe local: o backup
   `backups_amigao/backup_prod_20260909T120549Z.dump` tem a tabela `documents`
   com `storage_key` e `extracted_text` dos 6 documentos. O `pg_restore` já
   extraiu a tabela; **ler o conteúdo foi barrado pelo classificador de
   auto-modo** ("Production Reads"). Basta a liberação (ou o export dos 6
   registros por outro caminho) para essa metade ficar pronta sem nenhuma
   credencial nova.

Com as duas coisas o gate roda em uma passagem e responde as três perguntas do
enunciado: o texto bate com o de produção, as áreas saem iguais, e o doc 551
continua ilegível (confirmando o limite) ou o Vision o lê — caso em que o
representante Joel entra, e isso é achado, não escopo.

---

## Verificação

| | |
|---|---|
| `tests/services/test_frente_l_sessao_envenenada.py` | 8 passed |
| `tests/services/test_frente_l_soltas.py` | 8 passed |
| `tests/workers/` (suíte existente, tocada pelo item 1) | 20 passed |
| `frontend/src/pages/Processes/ConsolidacaoPanel.test.tsx` | 4 passed (1 novo) |
| `cd frontend && npm run build` (o gate real: `tsc -b`) | ✓ built |
| suíte de backend | ver PR |
