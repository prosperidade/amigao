# ADR-065 — Observação registral tipada

**Data:** 10/09/2026
**Status:** Aceita
**Frente:** E — tipo de observação (`feat/tipo-observacao`)
**Insumo:** `docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md` (Entrega 2, linha
"Tipo de observação: **AUSENTE**"), `docs/trabalhos/contencao_entrada.md` (dívida
#221), `docs/trabalhos/fiacao_entrada.md` (OCR-002)
**Dívidas fechadas:** #221 (área de RL ocupando `area_registrada_ha`), parte de
OCR-002 (arrendamento em `averbacao_app`)
**Dívida aberta:** nenhuma nova. HIST-001 (temporalidade de ato) permanece aberta
— é a frente seguinte, e depende desta.

**Pendência do #157 — fechada.** O PR #157 (`fix/cobertura-janela`) mergeou em
10/09 e adicionou `completa`/`falhas` a `JanelaResultado`. Rebase feito, gate
dos docs 547 e 548 (os únicos que fatiam nesta frente) refeito exigindo
`completa=True`: **4/4 execuções completas, nenhuma falha.** Tabela em
`docs/trabalhos/tipo_observacao.md`.

---

## Contexto

O ADR-064 (Frente C) e o PR #155 (Frente D) garantiram que o valor certo chegasse
ao staging: âncora, janela, número registral por regra, auditoria. Medido contra
os quatro documentos de matrícula da ELODI (docs 547–550), isso resolveu OCR-001
e a metade de OCR-002 que dependia da janela. Sobrou uma classe de erro que
nenhuma das quatro contenções ataca, porque nenhuma delas pergunta **o que o
número é**:

- **doc 548, `AV.10`** — arrendamento de 50 ha para terceiro, por 15 anos. O
  documento nunca diz APP. Gravado em `matricula.averbacao_app`.
- **doc 549, `R-11`** — preço de uma compra e venda (R$ 657.000,00). Gravado como
  **hipoteca**. `R.15` — alienação fiduciária do **Itaú Unibanco S.A.**. Gravada
  como **hipoteca do Banco do Brasil**. As três hipotecas reais (AV.03/04/05)
  estavam **baixadas** por AV.09/AV.10/AV.12 — a AV.12 diz textualmente *"ficando
  assim, o imóvel livre de hipoteca"* — e nada no staging sabia disso: ausência e
  baixa afirmada eram indistinguíveis.
- **doc 547, `Av.03`** — RELOCAÇÃO de reserva legal, `185,85.60ha`. Entrou como
  `area_registrada_ha`, a área do **imóvel** (dívida #221, medida no gate
  pós-deploy da Frente C). Âncora válida, formato válido, normalização correta
  pela regra do ADR-064 (185,856 ha) — e campo errado. Mais convincente que o
  erro sem regra, não menos.

**O padrão é um só: o modelo acerta o valor e erra o tipo**, e o mapeamento
(`_FIELD_SPECS["matricula"]`, três gavetas: `averbacao_app`, `averbacao_rl`,
`onus`) carimba fielmente o campo errado. Todo ato que não é APP nem RL nem
gravame clássico é espremido numa das três — porque três gavetas é tudo que a
certidão tinha para oferecer, e a certidão não é feita de gavetas. É feita de
**atos**: cada `R-nn` (registro) e `AV.nn` (averbação) tem uma natureza própria,
e essa natureza nunca teve onde ser dita.

## Decisão

A extração de matrícula passa a produzir **observações tipadas**, não mais três
campos fixos. Cada ato vira uma linha com `tipo` (vocabulário fechado), os
`atributos` que o tipo pede, e o **destino é decidido depois, por tipo**, num
mapa explícito e enumerado. Tipo sem coluna correspondente não é erro: é
observação visível sem destino, nunca forçada numa gaveta alheia.

### Por que campo/coluna na `ExtractedFieldStaging`, e não tabela nova

Medido contra o que a tabela já tinha: `field_value` é o envelope do **valor**
(bruto + âncora + normalização — ADR-064); `tipo_observacao` e `atributos` são
ortogonais a ele, como `target_entity`/`confidence` já são. Duas colunas
aditivas (`String(40)` indexada + `JSONB`), sem mexer no que existe. Uma tabela
nova exigiria join em todo lugar que hoje lê staging por processo, para um dado
que é, na prática, "mais uma faceta da mesma linha". `String` e não `Enum`
Postgres: o vocabulário evolui no código (mesma razão de `source_doc_type`,
dívida #216) — tipo novo não deve custar migration.

### Vocabulário fechado, derivado dos documentos reais

14 tipos, cada um com pelo menos uma ocorrência literal nos quatro documentos da
ELODI, mais dois "clássicos" (`servidao`, `usufruto`, `penhora`) que o próprio
prompt antigo já citava sem nunca ter tido casa:

```
area_registrada · reserva_legal · app · georreferenciamento · compra_venda ·
compromisso_compra_venda · arrendamento · servidao · usufruto · hipoteca ·
alienacao_fiduciaria · penhora · baixa · aditivo
```

Rótulo fora do vocabulário → `nao_classificado`, **visível como tal** —
`app/services/observacao_registral.normalizar_tipo`. Fechado por decisão: um
vocabulário aberto reproduz a doença das três gavetas em escala maior — o modelo
inventaria um rótulo e ninguém saberia o que ele quis dizer. O escape existe
para que "eu não sei classificar isto" seja uma resposta honesta do sistema, não
um valor forçado.

### Mapeamento tipo → destino, explícito e enumerado

```python
DESTINO_POR_TIPO = {
    "reserva_legal": ("matricula", "averbacao_rl"),
    "app": ("matricula", "averbacao_app"),
    # gravames não têm destino individual — ver abaixo
}
```

Só entra aqui o tipo com coluna correspondente. Os demais (arrendamento,
servidão, usufruto, compra e venda, compromisso, georreferenciamento, aditivo,
não classificado) nascem **sem destino**, com o motivo escrito em
`field_value.sem_destino_motivo` — a mesma família de sinal que `sem_casa` já
usa na Conferência (âmbar, "dado bom, sem coluna"), distinta do vermelho
`sem_ancora` (ADR-064, "afirmação sem fonte").

**Dois atos do mesmo tipo disputando a mesma coluna** (ex.: uma averbação de RL
e, mais adiante no documento, a relocação dela): vence o **último ato do
documento**. A certidão é cronológica por construção — "mais adiante" é o mais
recente que o próprio documento afirma. É ordem no papel, não vigência inferida:
a temporalidade consultável continua fora desta frente (ver "Fora do escopo").

### Gravames não têm destino individual

`matricula.onus_gravames` é **uma** coluna de texto. N linhas de gravame
disputando a mesma coluna reproduziriam a doença que `proprietarios` já resolveu
no PR #155: a primeira grava, as demais viram reconciliação falsa. Os gravames
(`hipoteca`, `alienacao_fiduciaria`, `penhora`) entram como linhas tipadas
**visíveis** (para a Conferência mostrar "R.15 — Alienação fiduciária — Itaú —
R$ 9.798.869,87" em vez de um blob), mas o destino `matricula.onus_gravames`
recebe uma linha **agregada** só com os gravames que o documento **não** declara
baixados.

### Baixa é observação de primeira classe

`"AV.12 — imóvel livre de hipoteca"` tem que entrar, não só ser ausência. A
reconciliação é por **referência textual escrita no próprio documento**, não por
inferência de data: a averbação de baixa cita o ato que ela baixa —
*"Averba-se para constar a baixa da cédula … constante da **AV.03**, acima"*.
`aplicar_baixas` casa o `ato_referenciado` (ou, na falta dele, a referência
dentro de `descricao`) contra a chave normalizada do ato (`chave_ato`: `"AV.03"`,
`"Av.03"`, `"AV-3"` → `"AV-3"`), e marca `baixado_por`. Só então
`onus_vigentes` calcula os gravames **não baixados** — as três hipotecas do doc
549 (AV.03/04/05), baixadas por AV.09/AV.10/AV.12, deixam de ser afirmadas como
vigentes.

**Isto não é modelar temporalidade.** Não há data, vigência nem "qual é o atual"
como campo consultável — só a declaração explícita de baixa, que o próprio
documento escreve. A distinção importa para a frente seguinte não reabrir o que
esta já fecha.

### A área que é de outro objeto (dívida #221)

`area_de_outro_objeto` compara a área candidata a `area_registrada_ha` (a área
do IMÓVEL) contra a área de cada observação cujo tipo é de um objeto **dentro**
do imóvel (`reserva_legal`, `app`, `arrendamento`, `servidao`, `usufruto`). A
comparação passa pela mesma porta única do ADR-064
(`normalizar_area_registral`/`parse_area_ha`) — `185,85.60` e `185,856` são o
MESMO número. Quando bate, a linha de `area_registrada_ha` perde o destino, com
o motivo nomeando o ato e o tipo verdadeiro. Fecha a dívida #221 sem tocar no
prompt nem na janela: o valor continua certo, o campo deixa de ser forçado.

### O preâmbulo protetor (lição do #155)

O prompt de matrícula ganhou uma seção `atos` inteira, substituindo as três
instruções antigas (`averbacao_rl`, `averbacao_app`, `onus`). O #155 mediu, 3
execuções de cada lado: acrescentar instrução nova SEM preâmbulo fez o modelo
parar de preencher DOIS campos antigos não tocados pelo diff (`app_declarada_ha`,
`rl_declarada_ha`, 3/3 → 0/3) — ele leu a lista de bullets como a lista de campos
que importam. O prompt desta frente **herda** o preâmbulo do #155 ("preencha
TODOS os campos do JSON abaixo que constarem no texto, inclusive os não citados
aqui") e o gate testa TODOS os campos antigos (`numero`, `cartorio`,
`denominacao`, `registro_anterior`, `proprietarios`, `codigo_certificacao`,
`nirf_cib`), não só os novos — ver Gate, abaixo.

## Fora do escopo desta frente (registrado, não esquecido)

- **Temporalidade de ato como campo consultável (HIST-001, parcial).** `data` e
  `prazo` ficam como TEXTO, do jeito que o documento escreve. Não existe
  vigência, cancelamento nem "qual titular é o atual" fora da baixa por
  referência textual acima — que resolve o caso mais grave de HIST-001 (gravame
  baixado afirmado como vigente) sem resolver o requisito inteiro (consultar
  "o que vale hoje" por data). É a frente seguinte, e depende desta: só faz
  sentido perguntar "quando" depois de saber "o quê".
- **Papel de pessoa** (quem dos titulares é vendedor/comprador/credor/devedor
  neste ato). `atributos.partes` guarda os nomes citados no ato, sem papel — a
  Entrega 2 da confirmação de 09/09 já registrava isso como dependente da
  temporalidade.
- **CAR e CCIR.** Só matrícula nesta frente — é o documento com mais atos e onde
  o erro mede maior.

## Gate

Banco descartável `amigao_tipo` (`TEMPLATE amigao_audit`, container
`amigao-tipo-db`, host **55234** — não 55432/55433/55444, que são de outros
projetos/frentes do dev), schema da migration aplicado por DDL direta (não
`alembic upgrade` — CLAUDE.md reserva o comando ao banco de desenvolvimento
`amigao_db:55432`). Alvo impresso e conferido por `assert` antes de qualquer
escrita. `extracted_text` **real** de produção dos docs 545–551, recuperado do
backup `backup_prod_20260909T120549Z.dump` (Desktop do André) restaurado num
Postgres 17 auxiliar — sem tocar produção —, com md5 conferido contra o que o
próprio banco calculou (bate com o relatório de 09/09: 82.117 / 57.090 / 34.815
/ 27.109 chars).

Duas execuções, LLM real (`gpt-4o-mini` via `ai_gateway`), sobre os quatro
documentos de matrícula:

- **#221:** `185,85.60` sai como observação de `reserva_legal` (ato Av.03), não
  como `area_registrada_ha`; `926,36.54` sai como `area_registrada_ha`, com
  âncora e normalização do ADR-064 intactas.
- **doc 548:** AV.10 sai com `tipo=arrendamento`, `prazo`/`partes` preenchidos,
  nunca em `averbacao_app`.
- **doc 549:** R-11 sai como `compra_venda` (não hipoteca); R.15 como
  `alienacao_fiduciaria`, credor Itaú; AV.09/AV.10/AV.12 saem como `baixa`;
  nenhuma hipoteca vigente afirmada.
- **doc 549:** `6.816.752-0` classificado no destino correto
  (`matricula.nirf_cib`, campo antigo, intocado por esta frente).
- **Campos antigos** (`numero_matricula`, `cartorio`, `denominacao`,
  `registro_anterior`, `proprietarios`, `codigo_certificacao`, `nirf_cib`)
  continuam saindo nas duas execuções — tabela campo × antes × depois no
  relatório do gate.
- **Controle negativo:** doc 545 (RG) e doc 551 (CNH-e, OCR vazio) — zero
  observação de matrícula (tipo de documento errado para o vocabulário).

Números completos, por documento e execução: `docs/trabalhos/tipo_observacao.md`.

## Testes

`tests/services/test_observacao_registral.py` — 26 casos, todos com trechos
VERBATIM dos quatro documentos da ELODI (docs 547–550): vocabulário e escape,
baixa por referência, destino por tipo e desempate por ordem, arrendamento fora
de APP, área de outro objeto (#221), ônus derivado dos atos (não hipoteca do
Banco do Brasil), reserva legal pelo ato, e dois controles de não-regressão
(matrícula sem atos, documento que não é matrícula).


---

## Adendo — Frente J (11/09/2026): o tipo é DECIDÍVEL, não só sugerido (CONF-002)

**Insumo:** `docs/auditoria/REAUDITORIA_CODEX_11-09.md`, item 5.
**Branch:** `fix/fechamento-contrato-spec`.

O ADR acima entregou o vocabulário fechado e a normalização (`normalizar_tipo`),
mas o tipo que o modelo sugere era **terminal**: nenhuma ação da Conferência
o corrigia. O padrão medido no próprio Contexto ("o modelo acerta o valor e
erra o tipo") só tinha saída pela reextração — e a reextração não é
determinística (`CONFIRMACAO_ENTRADA_2026-09-09.md`).

**Decisão (aditiva).**

- `StagingDecisionRequest.acao` ganha `reclassificar` com `tipo_observacao`
  obrigatório. `decide_field` normaliza pelo MESMO vocabulário deste ADR
  (rótulo humano ou slug), grava `tipo_observacao` decidido, preserva o
  original em `atributos["tipo_sugerido"]` (só na primeira reclassificação —
  `setdefault`), rerroteia o destino por `DESTINO_POR_TIPO` (RL/APP ganham
  coluna; gravame/evento perdem, com `sem_destino_motivo` escrito), marca
  `field_value["tipo_decidido"]`, **regera o resumo visível** (o texto do
  cartão embute o rótulo do tipo — sem regerar, a linha reclassificada para
  hipoteca continuaria exibindo "APP"; o texto anterior fica em
  `value_sugerido`), zera `consolidated_at` (o "Gravado" da
  rodada anterior deixa de valer) e audita `staging_tipo_reclassificado`.
  Rótulo fora do vocabulário é **422 com o rótulo no detalhe** — não vira
  `nao_classificado` calado; o escape só entra quando pedido por escrito.
- `DecisaoRequest.acao` (cartão agrupado, ADR-067) ganha `escolher_fonte`,
  `editar` e `reclassificar`, com `staging_id` obrigatório (a evidência
  alvo). Quando a reclassificação muda a chave natural (ex.: `app` sem chave
  → `hipoteca` em `gravames`), o endpoint devolve a decisão que passou a
  conter a linha, não 404.
- A reconciliação (`_chave_de`, `_evidencia_de`) consome `tipo_observacao`
  **decidido** — é a mesma coluna; `tipo_sugerido` fica só como memória.
  `Evidencia.tipo_observacao` é exposto para a tela oferecer o gesto sem
  abrir o JSON.
- Tela (`DecisoesPanel`): divergência pendente → "Escolher esta fonte" por
  evidência e "Editar valor"; **qualquer** decisão pendente com evidência
  tipada → "Editar tipo". Corrigir tipo não depende de divergência: uma
  decisão de gravames "concorda" por definição e ainda assim pode ter um
  ato com o tipo errado.

**Vocabulário ampliado (item 7 da reauditoria):** `sucessao`, `inventario`,
`adjudicacao`, `formal_partilha` — atos que transferem domínio *causa
mortis*. Entram em `TIPOS_TRANSFERENCIA_TITULARIDADE` (com `compra_venda`)
e no prompt de matrícula (`adquirentes`/`transmitentes` valem para os
cinco). Sem isto o caso de 3.000 ha (espólio) da Isis não tinha titular.

**Testes:** `tests/api/test_staging_decisions.py` (reclassificar pela
decisão, 422 para rótulo desconhecido, `escolher_fonte` exige `staging_id`),
`tests/services/test_reconciliation_decisions.py` (`tipo_sugerido`
preservado + reconciliação consome o decidido; regressão do `TypeError` na
titularidade), `DecisoesPanel.test.tsx` (tipo editável em decisão
concordante, ausente sem evidência tipada).
