# Frente C — contenção da entrada (medição)

**Branch:** `fix/contencao-entrada` · **ADR:** 064 · **Dívidas abertas:** #215, #216
**Insumo:** `docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md`
**Data da medição:** 09/09/2026

---

## Ambiente da medição

| item | valor |
|---|---|
| banco | `amigao_entrada`, container `amigao-audit-db-1`, **host 55433** (não a 55432 do dev) |
| alvo impresso antes de cada escrita | `db=amigao_entrada user=postgres port=5432` — o runner **aborta** se o banco efetivo não for esse |
| entrada | `documents.extracted_text` copiado de produção (mesmo artefato que o extrator consumiu em 07–08/09) |
| LLM | real, `gpt-4o-mini` via `ai_gateway` (`AI_DEFAULT_MODEL` do projeto) |
| produção | **intocada** — nenhuma leitura, nenhuma escrita nesta rodada |

**Paridade do harness.** A primeira rodada saiu desigual e foi descartada: o lado
`main` rodava com CWD no repo (lia o `.env`, `AI_ENABLED=true`) e o lado da branch
rodava no worktree (sem `.env`, `ai_configured=False` ⇒ 0 linhas). Refeita com CWD
neutro e **todas** as variáveis exportadas explicitamente nos dois lados.

---

## ⚠️ O gate NÃO está completo — a premissa do enunciado não se confirmou

O enunciado diz que `amigao_entrada` tem *"o `extracted_text` de produção"* dos
oito documentos. **Tem de dois.** A rodada de 09/09 reproduziu apenas os docs 546
e 549 e foi só o texto deles que ficou no banco:

```
 id  | process_id | document_type | ocr_status | chars
-----+------------+---------------+------------+-------
 546 |         23 | car           | done       |  4267
 549 |         23 | matricula     | done       | 29854
(2 rows)
```

Os outros seis (**544, 545, 547, 548, 550, 551**) não existem neste banco, e o
`extracted_text` deles vive só em produção. Esta máquina **não tem credencial de
produção** — a mesma fronteira declarada pela rodada de 09/09 — e nenhum MCP de
Supabase está conectado nesta sessão.

**Consequência honesta: a tabela abaixo cobre 2 dos 8 documentos.** Onde não deu
para rodar o documento real, está escrito o que foi feito no lugar e o que aquilo
prova e não prova. Para fechar o gate como especificado, falta:

> o `extracted_text` de produção dos docs **544, 545, 547, 548, 550 e 551**
> carregado em `amigao_entrada` — ou uma credencial read-only de produção nesta
> máquina.

Uma diferença adicional a registrar: o doc 549 tem **29.854** chars neste banco e
**34.815** em produção (546: 4.267 vs 4.286). A cópia não é byte-a-byte idêntica à
produção. Não muda nenhuma conclusão desta frente (todas as posições e valores
citados foram reconferidos contra o texto que este banco tem), mas invalida
qualquer comparação de offset absoluto com o relatório de 09/09.

---

## Tabela do gate — por documento, antes × depois, duas execuções de cada

### Doc 546 — CAR (4.267 chars)

| medida | ANTES-1 | ANTES-2 | DEPOIS-1 | DEPOIS-2 |
|---|---|---|---|---|
| linhas de staging | 10 | 10 | 10 | 10 |
| com âncora | 0 (não existia) | 0 | **10** | **10** |
| rejeitadas por falta de âncora | — | — | **0** | **0** |
| fatias / cobertura | 1 (janela de 30k) | 1 | 1 · 4.267/4.267 | 1 · 4.267/4.267 |
| custo (camada staging) | — | — | $0,00036 | $0,00036 |

Todos os 10 campos passaram a carregar posição: `numero_car` char 2.374 (dígitos),
`area_declarada_ha` char 359, `municipio` char 189 (texto), `uf` char 205,
`app_declarada_ha` char 3.506, `rl_declarada_ha` char 3.213, e as 4
`matricula_listada` com cobertura de âncora composta.

### Doc 549 — matrícula 3.673 (29.854 chars)

| medida | ANTES-1 | ANTES-2 | DEPOIS-1 | DEPOIS-2 |
|---|---|---|---|---|
| linhas de staging | 10 | 9 | 7 | 8 |
| com âncora | 0 | 0 | **7** | **8** |
| rejeitadas por falta de âncora | — | — | **0** | **0** |
| fatias / cobertura | 1 (janela de 30k) | 1 | 1 · 29.854/29.854 | 1 · 29.854/29.854 |
| custo (camada staging) | — | — | ~$0,0012–0,0020 | ~$0,0012–0,0020 |

As linhas a menos no DEPOIS **não** são rejeição pela âncora (zero rejeitadas nas
duas execuções): são os campos compostos (`averbacao_app`, `averbacao_rl`) que o
modelo às vezes devolve e às vezes não — a dívida #215, não esta frente.

**A baseline reproduz produção**: 546 → 10 linhas e 549 → 9/10 linhas é exatamente
o que o relatório de 09/09 registrou.

O campo decisivo:

| | ANTES-1 | ANTES-2 | DEPOIS-1 | DEPOIS-2 |
|---|---|---|---|---|
| `nirf_cib` | `950.041.396.737-1` (low, `format_ok:false`) | `950.041.396-737-1` (low, `format_ok:false`) | **`6.816.752-0`** (high, char 10.837) | **`6.816.752-0`** (high, char 10.837) |

Nas duas execuções ANTES o modelo devolveu o **código INCRA** (13 dígitos), que
reprova no formato de NIRF; nas duas DEPOIS devolveu o **NIRF verdadeiro**, que
está no texto e ancora. O `6.442.022-1` de produção (o exemplo do prompt) não
apareceu em nenhuma das quatro execuções — é justamente o achado N2: o valor
varia, a **classe** do erro é que era estável.

### Docs 544, 545, 547, 548, 550, 551

**NÃO RODADOS** — sem `extracted_text` nesta máquina (ver seção acima). O que foi
feito no lugar, e o que cada coisa prova:

| doc | substituto | prova | não prova |
|---|---|---|---|
| 547 (janela) | harness estrutural: o texto REAL do doc 549 empurrado para começar no char 45.000 de um documento de 74.854 chars, com enchimento = o mesmo OCR com todos os códigos NIRF/INCRA neutralizados | que conteúdo além do char 30.000 passou a chegar ao modelo e a vencer | que o LLM leria o doc 547 real do mesmo jeito |
| 547/548 (área) | `926,36.54` e `725,46.63` verbatim do relatório, pela regra e pelo pipeline completo | a conversão e a verificação pelo extenso | nada mais é preciso: a regra é determinística |
| 544, 545, 550, 551 | — | — | — |

**Harness da janela, resultado:**

```
harness: 74854 chars · texto real do doc 549 a partir do char 45000
  NIRF verdadeiro do imóvel no char 55837
  fatias: [(0, 0, 45000), (1, 43000, 74854)]  → o NIRF cai na fatia [1]

--- ANTES (janela de 30.000 chars, como o main faz) ---
  nirf_cib = None                      ← o extrator nunca o vê
--- DEPOIS (documento inteiro, fatiado) ---
  fatias=2 cobertura=74854/74854 truncado=False
  nirf_cib = '6.816.752-0'  (da fatia 1)   ← staging: pos=55837 fatia=1
  >>> GATE janela: OK
```

Duas montagens anteriores do harness foram descartadas por serem instrumento
ruim, e ficam registradas porque a segunda quase passou por boa: o enchimento
tinha código NIRF/INCRA próprio, e o modelo pegou **o do enchimento** (char
1.145) em vez do plantado — o teste teria dado "verde" sem exercitar a janela.

---

## Gate do N1 — o exemplo do prompt, contra o texto real do doc 549

Injetado de propósito: o modelo só devolve `6.442.022-1` às vezes (é o próprio
N2), então testar a **contenção** exige injetar o valor, não torcer pela execução.
Texto: o `extracted_text` real do doc 549.

```
'6.442.022-1' está no texto? False
'6.816.752-0' está no texto? True

  entra    numero_matricula     '3.673'                    destino=matricula.numero_matricula  pos=582 digitos
  entra    area_registrada_ha   '212,3553'                 destino=matricula.area_ha           pos=900 digitos
  BARRADO  denominacao          'Fazenda Santa Inventada'  destino=—.—  [low]
  BARRADO  nirf_cib             '6.442.022-1'              destino=—.—  [low]
           motivo: valor sem âncora no documento — não foi encontrado no texto lido;
                   não é gravado na base sem conferência

  o NIRF que ESTÁ no texto: '6.816.752-0' → pos=10837 destino=matricula.nirf_cib
  >>> GATE N1: OK
```

---

## Gate do N3 — o `AIJob` do extrator, antes e depois

Mesmo documento (549), `ExtratorAgent` real, banco descartável:

```
ANTES (main)  — ai_job 2
  model_used=None provider=None tokens_in=None tokens_out=None cost_usd=None raw_output=0 chars

DEPOIS        — ai_job 3
  model_used = 'gpt-4o-mini'
  provider   = 'gpt'
  tokens_in  = 21140   tokens_out = 1090
  cost_usd   = 0.003009
  raw_output = 3801 chars, em 2 blocos rotulados:
    - doc549:preview:matricula                     · 10212/498 tk · 1405 chars de resposta
    - doc549:staging:matricula:chunk0[0:29854]     · 10928/592 tk · 1652 chars de resposta
```

O JSON que o LLM devolveu é reconferível a partir do próprio job — que é o que
faltava para a auditoria de 09/09 e a obrigou a reproduzir tudo à mão.

---

## Os cinco erros da spec — o que mudou e o que NÃO mudou

| erro | é desta frente? | veredito medido |
|---|---|---|
| **OCR-001** (`926,36.54` → 92.636,54 ha) | **sim** | **MUDOU.** `926,36.54 → 926,3654` e `725,46.63 → 725,4663`, com o extenso do documento confirmando (`metodo=notacao_ha_a_ca+extenso`). `212,3553` e `2.180,8267` **inalterados**. Rodado pelo pipeline completo (`build_staging_fields`) além do unitário |
| **OCR-002** — *parte da janela* (`nirf_cib` = código do confrontante) | **sim** | **MUDOU.** Nas 2 execuções DEPOIS o `nirf_cib` do doc 549 saiu correto e ancorado; no harness da janela o valor além do char 30.000 passou a ser lido |
| **OCR-002** — *parte da categoria* (arrendamento → `averbacao_app`, RL no lugar errado) | **NÃO** | **NÃO MUDOU, e não devia.** `averbacao_rl` seguiu recebendo `42,8070` (o valor do CAR) em vez da AV.02 de 492,9252 ha. Isto é *tipo de observação* — frente seguinte |
| **DATA-002** (área documental do CAR sem slot) | **NÃO** | **NÃO MUDOU, e não devia.** O prompt do CAR continua com um único slot de área; `2180.3923` segue sem para onde ir. Exige mudar o esqueleto de extração — frente seguinte |
| **HIST-001** (averbações sem data/ato/partes/vigência) | **NÃO** | **NÃO MUDOU, e não devia.** `onus` seguiu como `{tipo, credor, valor}`, com os dois ônus errados do relatório. O que mudou é que agora a **cobertura de âncora** do composto é registrada: as folhas que não existem no documento aparecem em `ancora.sem_ancora` — sinal, não conserto |

---

## Variação entre execuções (o número da dívida #215)

Duas execuções do mesmo texto, mesmo código, de cada lado. Campos escalares
(`matricula_listada` excluído por ser lista):

| documento | ANTES | DEPOIS |
|---|---|---|
| 546 (CAR) | 0/6 campos variaram · 10 e 10 linhas | 0/6 · 10 e 10 linhas |
| 549 (matrícula) | **5/10 campos variaram** · 10 e 9 linhas | **1/8** · 7 e 8 linhas |

O que **parou** de variar no doc 549 — e este é o resultado que importa:

| campo | ANTES-1 | ANTES-2 | DEPOIS-1 | DEPOIS-2 |
|---|---|---|---|---|
| `nirf_cib` | `950.041.396.737-1` low, `format_ok:false` | `950.041.396-737-1` low, `format_ok:false` | `6.816.752-0` **high, char 10.837** | `6.816.752-0` **high, char 10.837** |
| `denominacao` | duas redações diferentes | | idêntica | idêntica |
| `onus` | duas redações diferentes | | idêntica | idêntica |

O único campo que variou no DEPOIS foi `cartorio` (presente numa execução,
ausente na outra).

**A variação é ela mesma variável — e isso está medido.** Um par DEPOIS anterior,
rodado na mesma branch minutos antes das correções da auto-revisão, deu **3/10**
(variando `averbacao_app`, `averbacao_rl` e `onus`). Duas medições da mesma
coisa: 3/10 e 1/8. É exatamente por isso que a dívida #215 diz que **um caso de
regressão que compare valores exatos vai piscar** — o que é estável é a CLASSE do
erro, não o valor.

Comparação com o relatório de 09/09, que mediu 3 de 14 campos variando entre duas
execuções em produção: a metodologia é a mesma, o denominador é diferente (campos
escalares do 549, sem a lista). **A variação caiu, não sumiu.**

---

## Suíte

- `tests/services/test_contencao_entrada.py` — 30 casos novos (âncora, janela,
  número registral, N4), todos com valores literais dos documentos da ELODI.
- `tests/agents/test_extrator_auditavel.py` — 2 casos novos (N3).
- 4 testes existentes atualizados ao novo contrato de `_extract_structured`
  (`(parsed, janela)`) e ao gate de âncora — passaram a receber um texto que
  contém os valores, para seguirem testando dedup/persistência/hint em vez de
  testar o gate por acidente.

---

## ⛔ ORDEM DE DEPLOY — este deploy sobe ANTES de qualquer "Gravar na base" no #23

**Não é recomendação, é pré-condição.** No processo **23** (ELODI) as áreas
`926,36.54` (mat. 3.181) e `725,46.63` (mat. 3.313) estão em staging com status
**aceito** e `confidence: high`. Sem a contenção 3, a próxima consolidação as grava
como **92.636,54 ha** e **72.546,63 ha** no imóvel 18 — cem vezes o real, e com
carimbo de validado por humano.

Isto **já aconteceu**, no caso 15: valor errado consolidado com selo de decisão é
muito mais caro de desfazer do que de prevenir, porque a reconciliação da Ficha 05
passa a proteger o valor errado (`human_validated` não é sobrescrito por valor novo
divergente).


**O deploy sozinho basta para as linhas já aceitas.** Medido: a escrita passa por
`_coerce`, que roteia toda coluna de área pela porta única `parse_area_ha` —
`'926,36.54' → 926.3654`, `'725,46.63' → 725.4663`, `'212,3553' → 212.3553`. Ou
seja, **não é preciso re-extrair o #23**: basta que a consolidação aconteça com o
código novo no ar. O que não pode acontecer é consolidar **antes**.

Sequência obrigatória:

1. merge (decisão do André);
2. **limpeza dos cadastros da ELODI** — guard do ENT-002 em zero (a migration da
   ADR-063 para e reporta se houver duplicado por documento; ver dívida #210);
3. deploy;
4. só então reprocessar/consolidar o #23.

---

## Gate de aceite PÓS-DEPLOY — condição de fechamento desta frente

Esta frente **não fecha no merge.** Fecha quando os seis documentos que não puderam
ser rodados aqui forem rodados **em produção, contra os textos reais**, com o código
já em produção. Não é pendência esquecida: é a metade do gate que esta máquina não
tinha como executar.

**Documentos:** `544`, `545` (Valéria) · `547`, `548`, `550`, `551` (ELODI).

**O que medir, por documento — a mesma tabela deste relatório:**

| coluna | o que registrar |
|---|---|
| linhas de staging | quantas, antes × depois |
| com âncora | quantas carregam `field_value.ancora` com `pos` |
| rejeitadas por falta de âncora | quantas, **e quais campos** (o número sozinho não diz nada) |
| fatias / cobertura | `fatias`, `cobertura_chars/total_chars`, `truncado` |

**Os quatro pontos que só o documento real pode responder:**

1. **doc 547** — `nirf_cib` tem que sair `2.974.457-1` (char 53.775), **não**
   `050.041.396.737-1` (o confrontante, char 1.286). É o gate da contenção 2 no
   documento de verdade; aqui ele foi exercitado só por harness estrutural.
2. **docs 547 e 548** — `area_registrada_ha` tem que sair com
   `normalizado_ha = 926,3654` e `725,4663`, método `notacao_ha_a_ca+extenso`.
   A regra é determinística e já está provada; o que falta medir é se o OCR real
   desses documentos entrega o literal na forma que a regra reconhece.
3. **doc 551 (CNH-e)** — a nota de status tem que dizer **"OCR não extraiu texto
   legível"**, não "tipo sem schema de staging". (O documento segue mal
   classificado como `doc_pessoal` — isso é a dívida **#216**, não este gate.)
4. **docs 544 e 545 (Valéria)** — as 3 linhas do RG (nome, CPF, nascimento) têm que
   continuar entrando, agora ancoradas. **Zero rejeição aqui é o controle negativo
   da frente:** se o gate da âncora barrar dado bom, é aqui que aparece.

**Rodar DUAS vezes e colar a diferença**, como nesta rodada — o número da variação
entra na dívida **#215**.

**Sem essa tabela a frente não está fechada**, mesmo com o PR mergeado e o deploy no ar.

---

## Fronteiras declaradas (o que esta frente NÃO alcança)

1. **Camada de preview.** `document_extractor` (que alimenta
   `AIJob.extracted_fields`) segue com janela de 30.000 chars e sem gate de
   âncora. Ela **não escreve no cadastro**; os cinco erros da spec nascem todos
   na camada de staging.
2. **Valores compostos.** Âncora informativa, não gate. Ver ADR-064.
3. **Determinismo.** Dívida #215.
4. **Casos já gravados.** Nada é reescrito para trás: linhas de staging antigas
   não ganham âncora retroativa, e valores sem fonte já consolidados na base
   continuam lá. Detectável por varredura (staging com `created_by_agent='extrator'`
   e `field_value` sem chave `ancora`).
