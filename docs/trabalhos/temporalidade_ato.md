# Frente F — temporalidade de ato (medição)

**Branch:** `feat/temporalidade-ato` · **ADR:** 066 · **Dívida fechada:** HIST-001 (parcial)
**Insumo:** `docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md` (HIST-001),
`docs/adr/065-observacao-registral-tipada.md` ("Fora do escopo")
**Data da medição:** 10/09/2026

---

## Ambiente da medição

| item | valor |
|---|---|
| banco | **nenhum.** `_extract_structured` e `build_staging_fields` são funções puras — não tocam `ExtractedFieldStaging` nem qualquer tabela. O gate desta frente valida prompt + parsing + derivação por regra, não persistência (o shape das colunas `tipo_observacao`/`atributos` não mudou desde a Frente E — sem migration, sem escrita nova para gatear) |
| entrada | `extracted_text` **real** de produção, docs 548/549, lido via Supabase MCP (projeto "Regente Ambiental", tabela `documents`, **read-only**) — mesma fonte das frentes C/D/E. Doc 549 usado num recorte que remove o bloco de vértices geodésicos e a repetição de cabeçalho de página (22.203 dos 34.815 chars originais) — todo ATO fica intacto e verbatim; só descrição de perímetro/rodapé repetido foi cortada. Doc 548 usado **completo** (57.090 chars) |
| LLM | real, `gpt-4o-mini` via `ai_gateway`, chamado por `_extract_structured` (o mesmo caminho de produção — fatiamento ADR-064 incluso) |
| produção | não acessada para escrita; leitura via MCP read-only, mesmo padrão das frentes anteriores |

Script: `scratch_gate_temporalidade.py` (não commitado — descartável, mesmo
padrão de gate das frentes anteriores). Duas execuções por documento; a
derivação de vigência roda sobre o MESMO resultado extraído com datas de
referência diferentes (não reextrai — é o próprio ponto do ADR-066: fatos
extraídos uma vez, estado rederivado sem custo de LLM).

---

## doc 549 (mat. 3.673) — o caso central do HIST-001

### Hipotecas baixadas e alienação vigente

| execução | hipotecas | baixadas | vigentes | alienação fiduciária |
|---|---|---|---|---|
| 1 | AV.03, AV.04, AV.05 | 3/3 (`AV.09`, `AV.10`, `AV.12`) | **0** | R.15 → `vigente` |
| 2 | AV.03, AV.04, AV.05 | 3/3 (`AV.09`, `AV.10`, `AV.12`) | **0** | R.15 → `vigente` |

Nas duas execuções, `data_ato` saiu preenchido em TODAS as sete observações
com estado de vigência (as 3 hipotecas + R.15), e `altera_ato` das três
baixas apontou exatamente para a hipoteca certa — `AV.09→AV.03`,
`AV.10→AV.04`, `AV.12→AV.05` — sem nenhuma citada por engano à referência de
arquivamento que abre cada AV. (`"Averbação referente a Av.09 Mat. 2007..."`,
que aponta para OUTRA matrícula — ver ADR-066, "cuidado medido"). Fecha o
caso mais grave do HIST-001, medido em 09/09: *"duas hipotecas do Banco do
Brasil que não existem"* — agora **zero** hipotecas afirmadas vigentes, nas
duas execuções.

### RL vigente — o tipo barra, não a coluna

| execução | RL vigente | área |
|---|---|---|
| 1 | `AV.02` | `492,9252` |
| 2 | `AV.02` | `492,9252` |

A AV.01 (georreferenciamento) cita "área de reserva legal de 42,8070ha" — o
número do CAR dentro de um ato que não é `reserva_legal` — e `rl_vigente`
**nunca a considera**, nas duas execuções: `destino_de` só entra em disputa
para `TIPO_RESERVA_LEGAL`, e o tipo do AV.01 continua `georreferenciamento`.
Mesma classe do #221 (forma certa, tipo errado), fechada pelo mesmo mecanismo
sem código novo — só o filtro por tipo que a Frente E já tinha.

### Titularidade — a cadeia real, ponta a ponta

| execução | titular atual | ato | anteriores |
|---|---|---|---|
| 1 | **ELODI AGROPECUÁRIA** | R-13 (10/12/2019) | Alexandre Augusto Clemente + Karina Santarosa Clemente (adquirentes R-11, transmitentes R-13); Nascente Agro-industrial Ltda (transmitente R-11) |
| 2 | **ELODI AGROPECUÁRIA** | R-13 | idêntico |

Quatro titulares, cada um com o ato que o inscreveu e o papel — **nas duas
execuções, idêntico**. `adquirentes`/`transmitentes` saíram corretos sem
inversão (o achado do #185/partes[0] da Frente E não se repetiu aqui: o
prompt pede os dois papéis separados, não um índice de lista).

### O achado do gate: quitação de dívida ≠ baixa de compra e venda

A AV.14 (real, fora do recorte que a Frente E testou) — *"para constar a
QUITAÇÃO da dívida mencionada no R-13 acima"* — saiu tipada `baixa`
(sinônimo "quitação") com `altera_ato="R-13"`. **O texto está certo**: o
preço da venda foi pago, a venda não foi desfeita. A primeira versão de
`aplicar_alteracoes` marcava `R-13.baixado_por = "AV.14"` sem olhar o tipo do
alvo — e `resumo()` (sem filtro de tipo) produzia **"R-13 · Compra e venda ·
... · baixado por AV.14"**, uma frase que a Conferência mostraria como se a
venda tivesse sido anulada.

**Corrigido no próprio gate, antes do merge:** `aplicar_alteracoes` só marca
o alvo quando ele está em `TIPOS_COM_VIGENCIA` — `compra_venda` nunca é alvo
válido de baixa/retificação, porque não tem estado de vigência para alterar.
Testado em `tests/services/test_observacao_registral.py::TestQuitacaoDeDividaNaoBaixaACompraEVenda`,
com o trecho real do doc 549. Reconferido pós-fix (execução única, offline,
sem nova chamada de LLM — os fatos já estavam salvos): `R-13.baixado_por is
None`, `"baixado por" not in R-13.resumo()`.

### Campos antigos — sem regressão

| campo | execução 1 | execução 2 |
|---|---|---|
| `numero_matricula`, `cartorio`, `denominacao`, `registro_anterior`, `proprietarios`, `codigo_certificacao`, `nirf_cib` | ✓ todos | ✓ todos |

---

## doc 548 (mat. 3.313) — arrendamento com prazo

### O caso do gate original: prazo com termo final explícito

A AV.10 (arrendamento, "15 anos com início no dia 01/01/2013 a 01/01/2028")
foi isolada em `tests/services/test_observacao_registral.py::TestVigenciaArrendamento`
(fixture sintética, sem baixa) — prova a REGRA isoladamente:

| `data_referencia` | vigência |
|---|---|
| 2026-01-01 | `vigente` |
| 2029-01-01 | `expirado` |

### O que o documento REAL mostra, além do que o teste sintético cobre

O doc 548 completo tem uma **AV.19** — *"rescisão de arrendamento"* — que o
vocabulário da Frente E já cobria (`"rescisão de arrendamento" → baixa`) mas
que o excerto usado nos testes da Frente E nunca incluía. Na execução 1, a
AV.19 saiu com `altera_ato="AV.10"`, e a ordem de decisão do ADR-066 (alteração
antes de prazo) respondeu certo: `AV.10.vigencia == "baixado"`, não
`"vigente"`/`"expirado"` — a REGRA correta é "o arrendamento foi rescindido",
não "o prazo ainda não venceu". Na execução 2 a mesma AV.19 saiu **sem**
`altera_ato` preenchido (variação de determinismo, dívida #215) e, como o
`prazo` desta execução saiu como texto solto ("15 anos", sem as datas), a
derivação caiu na regra 3 (`data_ato` presente ⇒ `vigente`) — nunca
`expirado` por default, porque não há termo para comparar.

**Fronteira medida, não fechada:** quando `prazo` traz só a DURAÇÃO ("15
anos") sem a data final explícita, `derivar_vigencia` não soma
`data_ato + duração` — fica `vigente` enquanto não houver baixa, o que é
honesto (a regra não inventa uma data que o texto não escreveu) mas é menos
informativo que quando o termo final está escrito por extenso. Calcular
"início + duração" é outra regra, de escopo maior (parsing de duração em
português, "15 anos", "5 anos", "temporada 2020/2021"...) — registrado aqui,
não puxado para dentro desta frente.

### Titularidade — estável nas duas execuções

| execução | titular atual | ato |
|---|---|---|
| 1 | ELODI AGROPECUÁRIA | R-20 (07/02/2020) |
| 2 | ELODI AGROPECUÁRIA | R-20 |

Cadeia idêntica nas duas execuções: IZAURA DE FATIMA PEGO (adquirente R-11,
transmitente R-20) ← SONIA INÊS GONDIM (transmitente R-11); ELODI
AGROPECUÁRIA (adquirente R-20, atual).

### O que a variação entre execuções expôs (dívida #215, não desta frente)

O número de atos capturados variou fortemente: **16 na execução 1, 33 na
execução 2** — a execução 1 não capturou as hipotecas AV.02–AV.08 (que a
execução 2 capturou inteiras). Dentro da execução 2, o ato `R-23` saiu
**duplicado** — duas observações com o mesmo rótulo, uma sem `baixado_por` e
outra com `baixado_por="AV.29"` — sintoma de mesclagem de fatias (ADR-064)
não deduplicando por `ato` quando o LLM produz uma leitura quase idêntica em
duas fatias sobrepostas. Efeito visível: `onus_vigentes` da execução 2 lista
um gravame (`R-23`, R$ 425.000,00) que a OUTRA cópia do mesmo ato já mostra
baixado. **Isto é a dívida #215** ("a mesma entrada ainda produz observações
diferentes a cada execução") na sua forma mais aguda — uma mesma execução
discordando de si mesma sobre o mesmo ato — e não é desta frente: a
deduplicação de `atos` entre fatias mescladas é `extraction_window.mesclar`
(ADR-064), e #215 já é o lugar certo para isso. Registrado aqui como medição,
não como dívida nova.

---

## O que NÃO foi medido nesta rodada (fronteira desta frente)

- **Persistência.** `extract_and_stage` (grava em `ExtractedFieldStaging`)
  não foi exercitado — o shape das colunas não mudou desde a Frente E, e o
  novo conteúdo do JSON (`data_ato`, `altera_ato`, `adquirentes`,
  `transmitentes`, `vigencia`) já é coberto em
  `tests/services/test_observacao_registral.py::TestAtributosTemporaisNaLinhaDeStaging`
  via `build_staging_fields` (função pura, mesmo caminho até a linha de
  staging, sem banco).
- **Reconciliação entre documentos** (REC-001) e **tela** (CONF-001) — fora
  do escopo, dependem desta frente, não o contrário.
- **`data_referencia` do caso como campo persistido** — `derivar_vigencia`
  aceita o parâmetro; nenhum lugar do sistema hoje o alimenta fora do
  `date.today()` da extração.

---

## Suíte

`tests/services/test_observacao_registral.py` — **44 passed** (26 da Frente E
+ 18 novos da Frente F, incluindo o achado da quitação de dívida medido
acima). Recorte de vizinhança também verde: `tests/services/test_contencao_entrada.py`,
`tests/services/test_fiacao_entrada.py`, `tests/agents/test_extrator_auditavel.py`
— **89 passed** no total do recorte (economia de sessão: suíte completa não
rodada nesta rodada, roda no CI do PR).
