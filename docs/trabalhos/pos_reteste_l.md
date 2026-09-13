# Frente L — três correções independentes

Branch `fix/pos-reteste-l` · worktree `wt-pos-reteste` · dívidas faixa 200-299.
Medido em 12/09/2026, e **revisado no mesmo dia depois de uma auditoria de
terceiro que reprovou meia frente**. Este documento é a versão pós-auditoria.

O que a auditoria derrubou, e que aqui está corrigido:

| reprovado | o que era | o que é agora |
|---|---|---|
| varredura sem instrumento | "um script AST percorreu `app/`" — e o script não estava na árvore | `scripts/varredura_except_envenenado.py`, versionado, com 2 regras e a fronteira declarada |
| savepoint como socorro | o serviço tentava carimbar `failed` confiando em `begin_nested()` | **medido: `begin_nested` não recupera flush falho.** O carimbo passou para o dono da transação |
| retorno ignorado | `gravar_desfecho_de_falha` podia devolver `False` e ninguém lia | os 4 chamadores leem e levantam |
| cabeçalho como decisão única | 5 atributos numa chave só | uma decisão POR ATRIBUTO, como a SPEC manda |
| "corretamente fora" | APP e módulos fiscais como desenho | **lacuna assumida**, com a SPEC citada |
| replay como prova semântica | "30 linhas → 12 decisões corretas" | o replay prova ROTEAMENTO; a semântica está bloqueada e dita como tal |
| regex do gate | não achava `926,36.54` | comparação NUMÉRICA por `parse_area_ha`, com teste |

---

## 1 — O `except` que grava numa sessão envenenada

### O instrumento, agora na árvore

`scripts/varredura_except_envenenado.py`. Duas regras explícitas:

- **R1** — `try` que toca a sessão (inclusive o caso transitivo: função que
  recebe `db`) com `except` que escreve no ORM sem `rollback` antes. É o
  desenho do caso que a Frente K achou.
- **R2** — função que recebe `db`, cujo `try` toca a sessão e cujo `except`
  **não re-levanta e não faz rollback**: devolve o controle com uma sessão que
  pode estar abortada. Esta regra não existia na primeira passagem — foi a
  auditoria que mostrou o caso (`_preferencias_ia`), e a regra veio depois.

E a fronteira, escrita no topo do arquivo: só um arquivo por vez, não segue
cadeia de chamada, não avalia decorator nem context manager próprio, não
distingue erro de banco de erro de rede. **Reduz o espaço de busca e torna o
resultado reproduzível; não prova ausência.**

Estado hoje: **R1 = 0** (os cinco fechados), **R2 = 11** — classe nova,
registrada como dívida **#229**, com a lista. Um deles foi fechado aqui
(`_preferencias_ia`, o confirmado pela auditoria): erro de banco ao ler
preferência de IA não é "preferência indisponível" — a transcrição seguia e só
descobria a sessão morta no commit, depois de já ter gasto o LLM.

O instrumento também deixou de isentar `try` com `begin_nested()`, porque a
medição abaixo mostrou que savepoint não é tratamento. A versão anterior
isentava — e teria escondido exatamente o defeito que esta frente acabara de
introduzir.

### Os cinco pontos da R1

| ponto | o que se perdia |
|---|---|
| `legislation_service` | status `failed` + causa; o erro que subia era o do SQLAlchemy, não a causa |
| `ai_tasks:100` / `:193` | AIJob ficava `running` **para sempre**, engolido por `except Exception: pass` |
| `ocr_tasks` / `audio_tasks` (budget guard) | documento preso em `processing` — mesmo sintoma que o PR #69 caçou por outra causa |

Cinco candidatos descartados com razão (render de PDF, fila Celery, Redis,
download de storage ×2): o `try` deles não tem como envenenar sessão. A
auditoria conferiu os cinco descartes e confirmou todos.

### A aposta que a medição derrubou

A primeira versão desta frente pôs o socorro **dentro** do
`legislation_service`, com `db.begin_nested()`, argumentando que o savepoint
desfaria só o trecho que caiu e deixaria a transação de fora viva. Parecia
certo. Medido contra o Postgres de dev:

```python
o.txt = "mau" + chr(0) + "byte"     # pendência de quem CHAMOU
with db.begin_nested():
    db.query(T)...                  # autoflush cai aqui
# depois do `with`:  db.is_active -> False
# no_autoflush + expire -> NÃO recuperam.  Só db.rollback() recupera.
```

**`begin_nested()` não torna um flush falho recuperável.** E `rollback()` é de
quem é DONO da transação — nunca de um serviço que a pegou emprestada, porque
desfazer tudo apagaria o trabalho de quem chamou.

Então o desenho mudou:

- **`legislation_service`** faz o trabalho e, se cair, garante a única coisa
  que consegue garantir sempre: **a causa real sobe**, nunca um
  `PendingRollbackError` genérico. Não tenta mais carimbar.
- **`legislation_monitor`** (dono da sessão) faz `rollback()`, carimba `failed`
  pela porta de `db_rescue`, e commita por documento. Um documento ruim custa
  um documento — antes custava o crawler inteiro, porque tudo vivia numa
  transação só e o `db.commit()` do fim morria junto.

Um teste revelou uma distinção que ninguém tinha nomeado: documento **novo**
que falha nunca chega a existir (o `add`+`flush` morre no mesmo rollback), então
não há o que carimbar — e isso está certo, não é falha do socorro. O caminho
que a auditoria confirmou é o de **atualização**, e é lá que o carimbo pousa.

### O retorno não é decorativo

`gravar_desfecho_de_falha` devolve `bool`, e os quatro chamadores passaram a
ler:

- **ocr/audio (budget guard)**: `False` → `raise`. Devolver
  `{"status": "budget_check_failed"}` seria dizer "tratei" sobre um documento
  que continua em `processing` — a mesma falha silenciosa que a frente veio
  fechar, um nível acima.
- **ai_tasks ×2**: `False` → levanta a **causa original**, sem `self.retry`.
  Retry com o banco fora cria um AIJob órfão NOVO a cada tentativa e esconde a
  causa atrás de um "Retry".

E a trava de concorrência que a auditoria levantou como hipótese: o socorro
recarrega a linha depois do rollback, e nesse intervalo outra execução pode
tê-la concluído. `nao_sobrescrever={"ocr_status": done}` impede carimbar
`failed` por cima de trabalho bom — devolvendo `True`, porque o desfecho
existe, só não é este.

### Os testes

`test_frente_l_sessao_envenenada.py` (8) e `test_frente_l_auditoria.py` (7).
O veneno é real: byte NUL vindo do texto (PDF real faz isso) e `SELECT 1/0`
dentro do guard de orçamento. O teste do monitor roda o **laço de verdade**
(`_run_single_crawler` com crawler falso), não uma imitação do laço.

Dois achados dos próprios testes: o fixture compartilhado usa
`join_transaction_mode` default (`rollback_only`), em que um rollback desfaz o
teste inteiro — com ele o socorro "não achava a linha", sintoma do harness; e
um teste caiu no bug que testa, lendo `processo.id` depois de envenenar.

---

## 2 — As soltas da Conferência: 58 → 28

Medido replayando as **118 linhas reais de produção** do caso #23
(`razao_linha_a_linha.json`) contra `build_decisions`.

### A fronteira desta medição — dita antes do número

O arquivo guarda **roteamento, não conteúdo**: não tem `atributos`,
`field_value` real, `decided_value` nem `consolidated_at`. Então o replay prova
**para qual decisão cada linha vai**, e só isso. Concordância, divergência,
proposta, vigência, titularidade e estado da decisão **não são medidos aqui** —
afirmá-los a partir deste replay seria inventar, e a versão anterior deste
documento inventou ("30 linhas → 12 decisões semanticamente corretas").

A prova semântica pede o staging completo do #23. Ele existe no dump de
produção local; **a leitura está barrada pelo classificador de auto-modo** (ver
item 3). O banco de DEV está vazio — conferido, não suposto.

### O que ganhou chave

| o que era | linhas | vira | por quê |
|---|---:|---|---|
| cartório · denominação · denominação anterior · registro anterior · NIRF/CIB | 17 | **uma decisão por ATRIBUTO** (17) | a SPEC agrupa evidências do MESMO atributo; "divergência" entre um cartório e um NIRF não significa nada |
| código de certificação + averbação de georreferenciamento | 7 | `georreferenciamento` (4) | o código (que GRAVA) e a AV que o registra são o MESMO ato |
| arrendamento, compromisso de compra e venda (+ servidão, usufruto) | 4 | `limitacoes` (3) | atos que PESAM sobre a matrícula e que nenhuma regra alcançava |
| município · UF | 2 | uma decisão cada (2) | mesma régua do cabeçalho: dois atributos, duas perguntas |

**Resultado: soltas 58 → 28, decisões 20 → 46.**

E o número é honesto sobre o que mudou: só **13 linhas colapsam**. As 17 do
cabeçalho viram 17 decisões — nenhum clique a menos no caso #23, onde cada
atributo tem uma fonte só. O ganho ali é outro: a linha deixa de ser solta e
vira FATO, com proposta, fonte autoritativa e estado; quando um segundo
documento declarar o mesmo cartório, as duas evidências caem sozinhas na mesma
decisão e a divergência aparece. Solta não acumula fonte; decisão acumula.

### Pergunta para a Isis (não decidida aqui)

**A consultora quer um BLOCO "identificação da matrícula" na tela?** Se sim,
isso é apresentação — agrupar cartões por prefixo de chave —, não chave
natural. A chave continua por atributo de qualquer forma; o que ela decide é se
os cinco cartões aparecem juntos sob um título. Não dá para inventar por ela.

### O que fica de fora, e a diferença entre "fora" e "lacuna"

| sobra | linhas | classificação |
|---|---:|---|
| `baixa` | 18 | **fora por desenho** — não é fato próprio; o efeito dela (o ato deixar de vigorar) já aparece na decisão de gravames |
| `nao_classificado` | 5 | **fora por desenho** — reclassifique antes que qualquer chave a alcance |
| `aditivo` | 3 | **fora por limitação** — altera outro ato e a extração não registra qual (dívida #226) |
| `app_declarada_ha` | 1 | **LACUNA ASSUMIDA** — a SPEC nomeia APP no bloco mínimo; a RL tem duas chaves e a APP nenhuma (dívida #225) |
| `modulos_fiscais` | 1 | **LACUNA ASSUMIDA** — a SPEC inclui cadastro rural no bloco mínimo (dívida #225) |

A auditoria estava certa nos dois últimos: "fonte única, nenhum ganho de
clique" é fato, e não é justificativa. Economia de gesto não decide o que a
SPEC manda conferir. As frases na tela dizem "LACUNA" e citam a dívida.

Também estava certa sobre a `baixa`: a frase anterior dizia que ela "entra na
decisão do ato que encerra", e não entra — a linha continua solta, o que chega
lá é o efeito. Motivo que descreve o desejo em vez do código é a mesma doença
que esta frente veio tratar. Corrigida.

### Um defeito do próprio conserto, achado antes do PR

Dar chave a `limitacoes` recriou o problema que `gravames` já resolvia: as duas
averbações de arrendamento da 3.181 caem no mesmo `campo` e o ramo de texto as
punha **uma contra a outra**. `_ASPECTOS_DE_ATO` passou a reger os três pontos
que já tratavam gravame assim. O replay **não pegaria isso** (não tem
`atributos`); o teste que fecha traz os `atributos` que a produção grava.

---

## 3 — OCR dos originais: PARADO, com o que falta nomeado

`scripts/gate_ocr_originais.py` responde as três perguntas **com veredito**,
não com tabela para alguém julgar depois:

1. **o texto bate?** similaridade normalizada contra `LIMIAR_SIMILARIDADE`
   (0,90), APROVADO/REPROVADO, e as maiores diferenças no JSON;
2. **as áreas saem iguais?** comparação **numérica** via `parse_area_ha` — as
   quatro matrículas do #23 e o total. `926,36.54` (notação registral: 926 ha,
   36 a, 54 ca) é o MESMO número que `926,3654`, e a versão anterior comparava
   string e não achava justamente o exemplo do enunciado. Cobrado só do
   documento que declara a área, para não reprovar por pergunta errada;
3. **o doc 551 continua ilegível?** procura o representante e marcas de CNH. Se
   o Vision ler, o gate DIZ que leu — achado, não escopo.

Antes de tudo confere o **SHA-256 dos bytes baixados** contra o
`checksum_sha256` de produção: sem isso, todo o resto podia estar comparando
outro arquivo.

`tests/services/test_gate_ocr_areas.py` (10 testes) fecha as funções que
decidem o veredito — o gate não roda em CI, então elas precisam de rede
própria. Um deles registra uma escolha: notação americana (`926.3654`) **não**
é aceita, de propósito, porque em português o ponto é separador de milhar e um
extrator frouxo faria `2.180` casar por acidente. OCR em notação americana
REPROVA e um humano olha — falha barulhenta em vez de silenciosa.

### O que falta

1. **Credencial de leitura do R2 de produção.** Não precisa ir para disco:
   variável de ambiente vence o `.env` no pydantic-settings (medido), como o
   `PGPASSWORD`. `--env-file` existe para quem prefere não colar segredo no
   terminal; `.env.prod-readonly` já é bloqueado pelo `.gitignore` linha 34.
2. **O lado de produção da tabela.** O backup
   `backups_amigao/backup_prod_20260909T120549Z.dump` tem `documents` (com
   `storage_key`, `checksum_sha256`, `extracted_text`) e
   `extracted_field_staging` (o que o item 2 precisa para a prova semântica).
   O `pg_restore` extrai; **ler o conteúdo foi barrado pelo classificador de
   auto-modo** ("Production Reads"), duas vezes.

### Achado do pré-voo → dívida #228

`download_bytes` devolve `b""` tanto para `NoSuchKey` quanto para
`NoSuchBucket`. Um bucket errado sairia na tabela como "arquivo ausente" —
conclusão errada vestida de achado. O gate pergunta pelo bucket com
`head_bucket` antes de baixar. O conserto na função é uma linha, mas muda I/O
em produção: merece ser o assunto do PR que o fizer.

---

## Verificação

| | |
|---|---|
| `pytest tests/ -q` — suíte inteira | ver PR |
| `test_frente_l_sessao_envenenada.py` | 8 passed |
| `test_frente_l_auditoria.py` (novo) | 7 passed |
| `test_frente_l_soltas.py` | 9 passed |
| `test_gate_ocr_areas.py` (novo) | 10 passed |
| `ConsolidacaoPanel.test.tsx` | 4 passed (1 novo) |
| `cd frontend && npm run build` (o gate real) | ✓ built |
| `ruff check` | All checks passed |
| `scripts/varredura_except_envenenado.py` | R1 = 0 · R2 = 11 (dívida #229) |

Dívidas abertas: **#225** (APP/cadastro rural sem chave — lacuna assumida),
**#226** (aditivo sem referência ao ato), **#227** (suítes de worker
neutralizam `rollback()`), **#228** (`NoSuchBucket` confundido com
`NoSuchKey`), **#229** (11 pontos da classe R2).

O que esta frente **não** move: nenhum dos 15 da matriz. Não há percurso
autenticado, DOM, F5 nem sessão nova para estas mudanças — REC-001 e CONF-001
melhoram por dentro e continuam PARCIAL.
