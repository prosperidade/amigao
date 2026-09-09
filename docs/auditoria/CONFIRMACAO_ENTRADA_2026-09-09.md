# CONFIRMAÇÃO DA ENTRADA — ELODI e Valéria, ponta a ponta

**Data:** 09/09/2026
**SHA auditado:** `87e9d549` — HEAD de `main`, inclui **#149** (`fix(identidade): representante da PJ, unicidade de documento e razão social — ENT-001, ENT-002, DATA-001`, ADR-063). O código executado na reprodução é este.
**Casos:** processo **23** (ELODI Agropecuária Ltda — PJ, 4 matrículas, CAR, CNH do representante) e processo **22** (Valéria Ruiz / Chácara Avalon Gleba 05 — PF).

## Bancos usados

| banco | acesso | uso |
|---|---|---|
| Produção (Supabase `diquycxxkfrjhxtrcmzb`) | **SELECT apenas**, via MCP read-only | localizar os casos, ler documentos, staging, `ai_jobs`, `audit_logs` |
| `amigao_entrada` (container `amigao-audit-db-1`, porta host **55433** — não 55432) | escrita, descartável | reproduzir extração → staging com o código da main |

`alembic upgrade head` foi aplicado em `amigao_entrada` até `99fb989b546c` (ADR-063). Alvo impresso antes de qualquer escrita: `db=amigao_entrada user=entrada port=5432`. Guarda de nome no script (`assert` sobre o nome do banco) e na criação (aborta se a porta for a de dev). Produção não recebeu nenhuma escrita. Nenhum arquivo de código alterado, nenhum PR de código.

## Fronteira declarada

**Os PDFs originais não foram baixados.** Esta máquina não tem credencial do storage de produção (só MinIO de dev; `S3_ENDPOINT`/R2 vazios), e obter segredo de produção exige autorização explícita, fora do escopo desta rodada. Portanto **o OCR não foi re-executado**.

A entrada da reprodução é `documents.extracted_text` de produção — que é exatamente o artefato que o extrator consumiu em 07–08/09. Para a pergunta "de onde nasce o erro", isso é preferível a um OCR novo: um OCR novo produziria outro texto e não reproduziria o ocorrido.

Foram reproduzidos com o código da main os documentos **546 (CAR)** e **549 (matrícula 3.673)** — o de maior densidade de defeitos. Os documentos 547, 548 e 550 não foram re-executados; para eles a origem foi determinada por construção (código + posição no texto), como registrado no Passo 3.

**Motivo desta rodada.** Toda auditoria anterior leu código ou testou staging já formado. O Astra marcou a origem dos erros ELODI como HIPÓTESE por falta do OCR/JSON originais. Esta é a primeira vez que se olha o dado entrando.

---

## PASSO 0 — LOCALIZAR (produção, leitura)

**Processos:** `22` = Valéria Ruiz / Chácara Avalon Gleba 05 (PF, cliente 19, imóvel 17) · `23` = ELODI Agropecuária (PJ, cliente 20, imóvel 18). Ambos tenant 1, status `triagem`.

| doc | proc | tipo | arquivo | ocr_status | extraction_status | len(extracted_text) |
|---|---|---|---|---|---|---|
| 544 | 22 | cpf_cnpj | cnh-valeria.jpg | **failed** | — | **0** |
| 545 | 22 | doc_pessoal | 01_DOCUMENTOS_PESSOAIS_RG_VALERIA.pdf | done | — | 849 |
| 546 | 23 | car | CAR FAZ B1 B2 B3 E BA - ELODI 2016.pdf | done | — | 4.286 |
| 547 | 23 | matricula | B1 - M3.181 … 926ha.pdf | done | — | 82.117 |
| 548 | 23 | matricula | B2 - M3.313 … 725ha.pdf | done | — | 57.090 |
| 549 | 23 | matricula | B3 - M3.673 … 212ha.pdf | done | — | 34.815 |
| 550 | 23 | matricula | B4 - M4.387 … 316ha.pdf | done | — | 27.109 |
| 551 | 23 | doc_pessoal | CNH-e.pdf.pdf | done | **"recebido, não processado (doc_pessoal) — revisar: tipo sem schema de staging"** | **444** |

`storage_key` de todos: `tenant_1/process_2X/<uuid>.pdf` (544 em `draft_65/`).

Erro do 544, literal: `Não foi possível ler o documento: arquivo não é um PDF (tipo image/jpeg) — converta para PDF e reenvie.`

**Total de linhas de staging — ELODI: 42.** (546→10, 547→5, 548→10, 549→9, 550→8, 551→0). **A spec confere.** Valéria: **3** (só do 545).

---

## PASSO 1 — REPRODUÇÃO

Ver "Fronteira declarada", acima.

**Achado colhido no caminho:** produção **não persiste o JSON bruto da extração**. Os `ai_jobs` do `extrator` (1467–1471, 1473) têm `model_used`, `provider`, `tokens_in/out`, `cost_usd` e `raw_output` **todos nulos/zero**. Só o `ocr_pdf` registra modelo. Foi por isso que ninguém tinha visto o JSON — ele não existe em lugar nenhum depois da chamada. **Os JSONs colados no Passo 2-B são a única cópia existente.**

---

## PASSO 2 — O QUE SAI (colado, sem interpretar)

### A) O texto OCR nos trechos que a spec acusa

**Doc 547, mat. 3.181** (posição 946):
> …MATRICULA Nº 3.181- Data - 01 de Outubro de 2013 - IMÓVEL: UMA GLEBA DE TERRAS , situada na " FAZENDA RETIRO DOS OLHOS D'AGUA- QUINHÃO 1, município de Alto Paraíso de Goiás, **com área de 926,36.54ha(novecentos e vinte e seis hectares, trinta e seis ares e cinquenta e quatro centiares)**…

**Doc 548, mat. 3.313** (posição 940):
> …**com área de 725,46.63ha(setecentos e vinte e cinco hectares, quarenta e seis ares e sessenta e três centiares)**…

**Doc 548, AV.10** (posição 27.150):
> **AV.10 MAT. 3.313:(Averbação Referente a Av.15 Mat. 1908): Averba-se para constar o arrendamento de uma área de 50 hectares para Patrícia Akemi Miaki Botega pelo período de 15 anos com inicio no dia 01/01/2013 a 01/01/2028**, conforme contrato registrado no Lv. 3-F as fls. 115/116 sob o nº 1702…

**Doc 549, AV.01** (posição 10.760):
> …Dito imóvel encontra-se cadastrado no CAR-GO sob o nº 5200605-90AD… , **com sua área de reserva legal de 42,8070ha**, cadastrado em conjunto com outras áres **na Receita Federal sob o nº 6.816.752-0**… e **no INCRA sob o nº 950.041.396-737-1, conforme CCIR de nº 02031617154**…

**Doc 549, AV.02** (a averbação registral de RL, que ninguém extraiu):
> **AV.02 MAT. 3.673 -(Averbação referente a Av.09 Mat. 2007 e Av. 04 Mat. 3.669)- Procede-se a averbação da Reserva Legal desta Matricula em conjunto com as Matriculas nº 1.224 e 1.225, com a área total de 492,9252ha**, não inferior a 20% do total da propriedade…

**Doc 547, o código que virou NIRF** (posição 1.286):
> …cravado na confrontação da **Fazenda Posse, da Nascente Agro Industrial, Código INCRA nº050.041.396.737-1**…

O NIRF verdadeiro do 3.181 está no **caractere 53.775**: `…cadastrado no INCRA sob o nº 000.027.338.958-0, conforme CCIR nº08452657097 … e na Receita Federal sob o nº 2.974.457-1…`

**Doc 546, CAR — as duas áreas, no mesmo parágrafo:**
> **Foi detectada uma diferença entre a área do imóvel rural declarada conforme documentação comprobatória de propriedade/posse/concessão [2180.3923 hectares] e a área do imóvel rural identificada em representação gráfica [2.180,8267 hectares].**

**Doc 551 (CNH-e da ELODI) — o texto OCR inteiro, 444 chars:**
> QR-CODE Documento assinado com certificado digital em conformidade com a Medida Provisória nº 2200-2/2001… REPÚBLICA FEDERATIVA DO BRASIL MINISTÉRIO DOS TRANSPORTES SECRETARIA NACIONAL DE TRÂNSITO - SENATRAN

Nem nome, nem CPF, nem número de registro. O documento do representante da PJ chegou vazio.

**Doc 545 (RG/CNH da Valéria) — texto OCR (849 chars, trecho):**
> PROIBIDO PLASTIFICAR 2715425388 … CARTEIRA NACIONAL DE HABILITACÃO … NOME E SOBRENOME **VALERIA RUIZ** 1ª HABILITAÇÃO 07/01/1993 … LOCAL **GOIANIA, GO** 3 DATA, LOCAL E UF DE NASCIMENTO **19/10/1973 SANTO ANDRE/SP** … 4d CPF **587.049.731-00** …

### B) O JSON bruto da extração (capturado na reprodução — não existe em produção)

**Doc 549, mat. 3.673** — resposta literal do LLM (provider `gpt`, `AI_DEFAULT_MODEL=gpt-4o-mini`):

```json
{
  "numero_matricula": "3673",
  "registro_livro_folha": null,
  "cartorio": "Registro de Imóveis de Alto Paraíso de Goiás",
  "area_registrada_ha": "212,3553",
  "denominacao": "Fazenda \"POSSE OU PORCOS - GLEBA 4\"",
  "denominacao_anterior": null,
  "registro_anterior": "3.669",
  "proprietarios": [
    {"nome": "Nascente Agro-industrial Ltda", "cpf": "25.078.411/0001-20"},
    {"nome": "ALEXANDRE AUGUSTO CLEMENTE", "cpf": "251.076.678-30"},
    {"nome": "KARINA SANTAROSA CLEMENTE", "cpf": "270.654.448-13"},
    {"nome": "ELODI AGROPECUÁRIA", "cpf": "29.091.958/0001-17"}
  ],
  "averbacao_app": null,
  "averbacao_rl": null,
  "numero_geo": null,
  "codigo_certificacao": "ed59189a-9c02-4322-bc6a-9e2906de3105",
  "nirf_cib": "6.816.752-0",
  "onus": [
    {"tipo": "Hipoteca", "credor": "Banco do Brasil S/A Ag. Planaltina – GO", "valor": "R$ 657.000,00"},
    {"tipo": "Hipoteca", "credor": "Banco do Brasil S/A Ag. de Planaltina – GO", "valor": "R$ 9.798.869,87"}
  ],
  "confidence": {
    "numero_matricula": "high",
    "registro_livro_folha": "low",
    "cartorio": "high",
    "area_registrada_ha": "high",
    "denominacao": "high",
    "denominacao_anterior": "low",
    "registro_anterior": "high",
    "proprietarios": "high",
    "averbacao_app": "low",
    "averbacao_rl": "low",
    "numero_geo": "low",
    "codigo_certificacao": "high",
    "nirf_cib": "high",
    "onus": "high"
  }
}
```

**Doc 546, CAR** — resposta literal:

```json
{
  "numero_car": "GO-5200605-82E5.AE14.076B.4637.9900.9C9D.EC86.D700",
  "area_declarada_ha": "2.180,8267",
  "municipio": "Alto Paraíso de Goiás",
  "uf": "Goiás",
  "app_declarada_ha": "90,4225",
  "rl_declarada_ha": "437,7632",
  "status_car": null,
  "matriculas": [
    {"numero": "3181",  "data": "01/10/2013", "livro_folha": "2", "cartorio": "FICHA"},
    {"numero": "4.387", "data": "22/04/2020", "livro_folha": "2", "cartorio": "Registro Geral"},
    {"numero": "3.313", "data": "23/01/2014", "livro_folha": "2", "cartorio": "Registro Geral"},
    {"numero": "3.673", "data": "10/02/2016", "livro_folha": "2", "cartorio": "Registro Geral"}
  ],
  "confidence": {
    "numero_car": "high",
    "area_declarada_ha": "high",
    "municipio": "high",
    "uf": "high",
    "app_declarada_ha": "high",
    "rl_declarada_ha": "high",
    "status_car": "low",
    "matriculas": "high"
  }
}
```

**Uma única área.** O esqueleto do prompt do CAR tem um só slot (`area_declarada_ha`). `2180.3923` está no texto e não tem para onde ir.

### C) As 45 linhas de staging de produção

**ELODI — 42 linhas.** (id · campo = valor · conf · destino · hint)

*doc 546 CAR (10):* `numero_car`=GO-…D700 (low, `format_ok:false` → `imovel.car_code`) · `area_declarada_ha`="2.180,8267" ha (high → `imovel.total_area_ha`) · `municipio`="Alto Paraíso de Goiás" · `uf`="Goiás" · `app_declarada_ha`="90,4225" · `rl_declarada_ha`="437,7632" (→ `imovel.`**`rl_status`**) · 4× `matricula_listada` (hints 3181, 4387, 3313, 3673).

*doc 547 mat 3.181 (5):* `numero_matricula`="3181" · `cartorio`="Registro de Imóveis de Alto Paraíso de Goiás" · **`area_registrada_ha`={"value":"926,36.54","unidade":"ha"} conf=high status=aceito** · `denominacao`="UMA GLEBA DE TERRAS" · **`nirf_cib`="050.041.396.737-1"** (low, `format_ok:false`).

*doc 548 mat 3.313 (10):* `numero_matricula`="3.313" · `cartorio` · **`area_registrada_ha`="725,46.63" conf=high aceito** · `denominacao`="FAZENDA NOVO HORIZONTE II" · `denominacao_anterior`="FAZENDA OLHOS D\`ÁGUA" · `registro_anterior`="1908" · **`averbacao_app`={"area":"50","referencia":"Averba-se para constar o arrendamento de uma área de 50 hectares para Patrícia Akemi Miaki Botega pelo período de 15 anos com inicio no dia 01/01/2013 a 01/01/2028"}** · `codigo_certificacao`="281310000060-08" (low) · `nirf_cib`="4.078.154-2" · `onus`=[2 hipotecas BB].

*doc 549 mat 3.673 (9):* `numero_matricula`="3673" · `cartorio` · `area_registrada_ha`="212,3553" · `denominacao` · `registro_anterior`="3.669" · **`averbacao_app`={"area":"42,8070","referencia":"Reserva Legal"}** · `codigo_certificacao`=UUID SIGEF · **`nirf_cib`="6.442.022-1"** · `onus`=[{Hipoteca, R$ 657.000,00, BB},{Hipoteca, R$ 9.798.869,87, BB}].

*doc 550 mat 4.387 (8):* `numero_matricula`="4387" · `cartorio` · `area_registrada_ha`="316,2053" · `denominacao` · `registro_anterior`="3.672" · `codigo_certificacao`=UUID · `nirf_cib`="9.475.495-0" · `onus`=[5 itens: 3 hipotecas + 2 alienações fiduciárias].

**Nenhuma das 42 tem `consolidated_at`.** Nada foi gravado na base: `properties.18.total_area_ha` = NULL, `field_sources` = `{}`.

**Valéria — 3 linhas** (doc 545): `nome`="VALERIA RUIZ" · `cpf`="587.049.731-00" · `data_nascimento`="19/10/1973". Todas `pendente`, destino `cliente`.

---

## PASSO 3 — OS CINCO ERROS, RASTREADOS

### OCR-001 — "926,36.54" e "725,46.63" · **CONFIRMADO — e não é erro de OCR**

O documento **diz isso**. É a notação registral antiga `hectares,ares.centiares`, e o próprio texto traz o extenso que a decodifica: *"novecentos e vinte e seis hectares, trinta e seis ares e cinquenta e quatro centiares"*. Valor real: **926,3654 ha**. O 725,46.63 = **725,4663 ha**.

O OCR foi fiel. A extração preservou o literal — **correto** conforme o Item 1 da Isis. **Ninguém normaliza depois.** Medido nesta rodada (não derivado estaticamente):

| literal | `parse_area_ha()` | `check_format()` |
|---|---|---|
| `926,36.54` | **92636.54** | **True** |
| `725,46.63` | **72546.63** | **True** |
| `212,3553` | 212.3553 | True |
| `2.180,8267` | 2180.8267 | True |
| `2180.3923` | 2180.3923 | True |

O valor normalizado é **100× o real**, e passa na validação de formato. A matriz compararia o CAR (2.180,8267 ha) contra uma soma de matrículas de **165.711,73 ha**. O extenso está no texto, a duas linhas do número, e não é lido por ninguém.

### OCR-002 — arrendamento como área, RL no lugar errado, códigos INCRA · **CONFIRMADO**

1. **Arrendamento → APP** (mat. 3.313, linha 1572): a AV.10 é um **arrendamento de 50 ha por 15 anos para uma terceira pessoa**. Foi para `averbacao_app` → destino `matricula.averbacao_app`. O documento nunca diz APP. `averbacao_rl` existe no schema e ficou vazio.
2. **RL → APP** (mat. 3.673, linha 1581): `{"area":"42,8070","referencia":"Reserva Legal"}` em `averbacao_app`. E o valor está errado além da categoria: 42,8070 ha é a **RL declarada no CAR**, citada de passagem dentro da averbação de georreferenciamento; a averbação registral de RL é a **AV.02, de 492,9252 ha em conjunto com as matrículas 1.224 e 1.225**. Nenhuma das duas execuções capturou a AV.02.
3. **Código INCRA em categoria errada** (mat. 3.181, linha 1565): `nirf_cib="050.041.396.737-1"`. O texto diz **"Código INCRA nº"** — e é o código **do confrontante** (Nascente Agro Industrial), não do imóvel. Causa raiz medida: `EXTRACTOR_MAX_CHARS=30000`; o NIRF verdadeiro (`2.974.457-1`) está no caractere **53.775** — o extrator **nunca o viu**. O único código INCRA-like dentro da janela era o do vizinho, no caractere 1.286.

**Onde nasce:** o mapeamento `_FIELD_SPECS["matricula"]` é 1:1 (`averbacao_app`→`averbacao_app`, `averbacao_rl`→`averbacao_rl`). Não existe caminho de código que mova RL ou arrendamento para APP. **O erro sai do LLM**, e o mapeamento o carimba fielmente. `check_format` valida formato, não significado.

### REC-001 — matrícula 3.181 em dois campos · **CONFIRMADO**

- linha **1557** (doc 546, CAR): `matricula_listada = {"numero":"3181","data":"01/10/2013","cartorio":"Alto Paraíso de Goiás/GO","livro_folha":"2 FICHA"}` · hint 3181 · status **pendente**
- linha **1561** (doc 547, certidão): `numero_matricula = "3181"` · hint 3181 · status **aceito**

Duas linhas, dois nomes de campo, dois status independentes, mesmo destino `matricula.numero_matricula`. O consultor decide duas vezes sobre o mesmo fato.

### DATA-002 — as três áreas · **CONFIRMADO: colapsa**

| área | está no texto? | está no staging? |
|---|---|---|
| gráfica CAR — 2.180,8267 | sim | **sim** (`area_declarada_ha` → `total_area_ha`) |
| documental CAR — 2180.3923 | sim, no mesmo parágrafo | **não. Nenhuma linha.** |
| soma das matrículas | derivável | não existe como observação |

Não é falha do LLM: **o esqueleto do prompt do CAR tem um único slot de área**. A informação mais importante do parágrafo — *"foi detectada uma diferença"* — é descartada na entrada. E `properties` já tem `area_documental_ha` e `area_grafica_ha`, ambas NULL.

Nota lateral: `Módulos Fiscais: 31,1547` está no texto, `properties.modulos_fiscais` existe, e o prompt do CAR não pede o campo.

### HIST-001 — averbações · **CONFIRMADO, e pior que "vira texto solto"**

O staging **não tem** data, número do ato, partes nem vigência. `averbacao_app` guarda `{"area","referencia"}`; `onus` guarda `{"tipo","credor","valor"}`. `AV.10`, `Av.15 Mat. 1908`, `01/01/2013 a 01/01/2028` sobrevivem apenas dentro de uma string de texto livre.

E o `onus` da 3.673 está **errado, e reproduziu igual nas duas execuções**:

| staging diz | o documento diz |
|---|---|
| Hipoteca · R$ 657.000,00 · Banco do Brasil | **R-11: preço da compra e venda**, não hipoteca |
| Hipoteca · R$ 9.798.869,87 · Banco do Brasil | **R.15: alienação fiduciária**, credor **ITAÚ UNIBANCO S.A.** |

As três hipotecas reais (AV.03, AV.04, AV.05 — Banco do Brasil) foram **todas baixadas** por AV.09, AV.10 e AV.12 — a AV.12 diz textualmente *"ficando assim, o imóvel livre de hipoteca"*. Nenhuma delas deveria constar como vigente, e nenhuma consta. O que consta são dois ônus que não existem.

### Valéria — município Pirenópolis · **INFORMADO. Não extraído, não corrigido.**

`properties.17` já existia (`entry_type = cliente_existente_imovel_existente`), com `municipality='Pirenópolis'`, `state='GO'`, `car_code` e `total_area_ha=3.2945` preenchidos no cadastro. `field_sources = {}` — nenhuma marca de validação humana. **Zero registros em `audit_logs` para a entidade property 17.** Nenhum documento do caso carrega o município: a CNH falhou por ser JPEG, e o RG traz "GOIANIA, GO" (local de emissão) e "SANTO ANDRE/SP" (nascimento). O valor está certo e a origem dele é o cadastro manual — não há rastro no sistema que diga isso.

---

## ACHADOS NOVOS — não estavam na spec

**N1 · Valor sem fonte no documento: o exemplo do prompt vaza para o dado.**
O `nirf_cib` da mat. 3.673 em produção é **`6.442.022-1`**. Essa string **não existe** no texto do doc 549 (`LIKE '%6.442.022%'` = false no texto inteiro, 34.815 chars). Ela é, literal, o exemplo escrito no prompt: `"nirf_cib": o NIRF/CIB … (ex.: "6.442.022-1")`. O mesmo valor aparece em produção em **3 processos diferentes** (16, 17, 23) e num órfão. No processo 16 ele é verdadeiro — o doc 366 (ITR São Jorge) o contém; **foi de lá que o exemplo nasceu**. Nos processos 17 (doc 391) e 23 (doc 549) o valor **não está no documento**. Gravado com `confidence: high`, destino `matricula.nirf_cib` — exatamente o campo do degrau 1 da cascata ITR↔matrícula.

**N2 · A mesma entrada produz observações diferentes a cada execução.**
Doc 549, mesmo texto, mesmo código, duas execuções:

| campo | produção (08/09) | reprodução (09/09) |
|---|---|---|
| `nirf_cib` | `6.442.022-1` (exemplo do prompt) | **`6.816.752-0`** (correto) |
| `averbacao_app` | `{"area":"42,8070","referencia":"Reserva Legal"}` | **`null`** |
| `averbacao_rl` | ausente | `null` |
| `onus` | 2 itens errados | **os mesmos 2 itens errados** |
| linhas gravadas | 9 | 8 |

No doc 546 a variação inverteu de sinal: em produção o `matricula_listada` do 3.181 saiu `{"cartorio":"Alto Paraíso de Goiás/GO","livro_folha":"2 FICHA"}` (certo); na reprodução saiu `{"cartorio":"FICHA","livro_folha":"2"}` — o LLM leu a coluna Livro/Folha como cartório. Isto é relevante para o plano: **um caso de regressão que compare valores exatos vai piscar**. O que é estável é a *classe* do erro, não o valor.

**N3 · A extração não é auditável.**
Nenhum `ai_job` do `extrator` guarda modelo, provider, tokens, custo ou `raw_output`. O que o LLM devolveu em 08/09 não existe mais. Contra o Princípio 11, e é a razão pela qual a origem dos erros ELODI só pôde ser marcada como hipótese até hoje.

**N4 · O documento do representante da PJ chegou vazio e ninguém foi avisado.**
Doc 551: `ocr_status='done'`, 444 chars de boilerplate de assinatura digital, 0 linhas de staging, e `extraction_status` explica pelo motivo errado — *"tipo sem schema de staging"*, quando a causa real é que o OCR não leu a CNH-e (PDF com conteúdo em imagem). O #149 rota `doc_pessoal`→representante em caso PJ; não há o que rotear. Enquanto isso, o nome, CPF, RG e CNH do **JOEL CENCI** estão em texto limpo no doc 549 (R-13 e R.15) — e a extração de matrícula não tem onde pô-los.

---

## ENTREGA 1 — documento × staging × erros reproduzidos

### ELODI (42 linhas)

| doc | linhas | erros confirmados neste documento |
|---|---|---|
| 546 CAR | 10 | **DATA-002** (área documental 2180.3923 sem slot no schema) · **REC-001** (`matricula_listada` 3181 duplica a certidão) · `rl_declarada_ha`→`imovel.rl_status` (área em campo de status) · módulos fiscais não pedidos |
| 547 M3.181 | 5 | **OCR-001** (`926,36.54` → 92.636,54 ha, `check_format`=True, status **aceito**) · **OCR-002** (`nirf_cib` = código INCRA **do confrontante**; causa medida: NIRF real no char 53.775 > `EXTRACTOR_MAX_CHARS=30000`) |
| 548 M3.313 | 10 | **OCR-001** (`725,46.63` → 72.546,63 ha, **aceito**) · **OCR-002** (arrendamento de 3º → `averbacao_app`) · **HIST-001** (AV.10, vigência 2013–2028 e a parte arrendatária só como texto livre) |
| 549 M3.673 | 9 | **OCR-002** (RL → `averbacao_app`, e valor do CAR em vez da AV.02 de 492,9252 ha) · **HIST-001** (3 hipotecas baixadas ignoradas; 2 ônus inexistentes afirmados, credor trocado) · **N1** (`nirf_cib` = exemplo do prompt) · **N2** (variação entre execuções) |
| 550 M4.387 | 8 | **HIST-001** (5 ônus sem data e sem estado) · valores individuais conferem com o texto |
| 551 CNH-e | **0** | **N4** (OCR vazio, mensagem de status pela causa errada) |

### Valéria (3 linhas)

| doc | linhas | erros |
|---|---|---|
| 544 CNH .jpg | 0 | OCR recusa JPEG. `intake_notes` já registrava; nenhuma pendência estruturada existe |
| 545 RG | 3 | nome/CPF/nascimento corretos |
| — | — | Município Pirenópolis: **informado no cadastro**, sem `field_sources`, sem `audit_log` — indistinguível de um dado extraído |

---

## ENTREGA 2 — os cinco conceitos × material que existe hoje

| conceito | veredito | linha que prova |
|---|---|---|
| **Papel de pessoa** | **INSUFICIENTE — material existe, chega até o JSON e é descartado no mapeamento** | JSON bruto do doc 549 traz 4 `proprietarios` (Nascente, Alexandre, Karina, ELODI). `_FIELD_SPECS["matricula"]` **não tem entrada `proprietarios`** → 0 linhas de staging. E o payload é `{nome, cpf}`: sem papel (vendedor/comprador/cônjuge/procurador/sócio/devedor/credor) e sem tempo (quem é o atual). Ligar o destino resolve metade; a outra metade exige tipar a saída. `sigef` mapeia `proprietario`; `matricula` não. |
| **Tipo de observação** | **AUSENTE** — não há como dizer "isto é arrendamento", só qual coluna recebeu | linha 1572: arrendamento inteiro dentro de `averbacao_app`. O schema oferece 3 gavetas (`averbacao_app`, `averbacao_rl`, `onus`); tudo que não é uma delas é forçado numa delas. `CONF-002`: editar muda `decided_value`, não a categoria |
| **Temporalidade de ato** | **AUSENTE** — não há o que ligar | `{"area":"42,8070","referencia":"Reserva Legal"}` e `{"tipo","credor","valor"}` não têm data, número de ato nem cancelamento. AV.09/AV.10/AV.12 (as baixas) **não geram observação nenhuma**. Extrair vem antes de ligar |
| **Decisão agrupada** | **INSUFICIENTE — as evidências existem, o vínculo não** | linhas 1557 e 1561: mesmo número 3181, mesmo `matricula_hint`, mesmo destino, campos e status diferentes. O hint já é a chave natural de agrupamento; falta a decisão que consome as duas |
| **Área por finalidade** | **INSUFICIENTE no modelo, AUSENTE na entrada** | `properties.area_documental_ha` e `area_grafica_ha` **existem e estão NULL**. O prompt do CAR tem **um** slot; `2180.3923` está no texto e não é extraído. Aqui não basta ligar: o esqueleto de extração precisa de um segundo campo |

---

## ENTREGA 3 — veredito sobre "peças existem, faltam ligações"

**PARCIAL.** Ela se sustenta em uma camada e cai em duas.

**Onde se confirma (basta ligar):** colunas de destino já existem e estão vazias — `area_documental_ha`, `area_grafica_ha`, `averbacao_rl`, `modulos_fiscais`, `proprietarios`. `matricula_hint` já agrupa as evidências duplicadas. `matriculas.vigencia`/`superseded_by_id` já modelam cadeia de fichas. Nesses pontos o trabalho é de fiação.

**Onde ela é refutada (o dado não vem, ou vem sem forma):**

1. **Números.** `926,36.54` sai do documento correto e vira 92.636,54 ha porque **falta uma regra**, não uma ligação. O extenso que resolve a ambiguidade está a duas linhas e nunca é lido. Nenhuma tabela ganha isso ligada a nada.
2. **Áreas do CAR.** A segunda área não existe no JSON. Ligar `area_documental_ha` a quê? **O esqueleto de extração precisa mudar antes.**
3. **Temporalidade.** Não há evento com data/ato/partes/cancelamento em lugar nenhum do pipeline. O exemplo do enunciado — *"AV.12 — Reserva Legal 685,3026 ha" como texto único* — é literalmente o que acontece aqui, com AV.10 e AV.02. **Extrair vem antes de ligar.**
4. **Papel de pessoa.** Meio-refuta: a lista chega ao JSON (ligação resolveria a existência), mas sem papel e sem tempo (tipagem resolveria o significado).

**E um quinto ponto que a tese não previa, e que muda a ordem do plano:** a entrada **não é determinística**. Mesmo texto, mesmo código, duas execuções, resultados diferentes em 3 dos 14 campos — inclusive um valor que não estava no documento. Enquanto a extração for uma única chamada de LLM sem `raw_output` persistido, sem verificação de que o valor existe no texto e sem cobertura da janela inteira (`EXTRACTOR_MAX_CHARS=30000` contra documentos de 82k), **qualquer camada construída em cima herda a variação**. Reconciliar, tipar e datar observações que mudam a cada execução é construir sobre areia. A contenção da entrada — normalizar número com regra, ancorar todo valor em um trecho do texto, cobrir o documento inteiro, persistir o bruto — é pré-requisito das outras quatro, não uma delas.

---

## Estado ao fim da rodada

- Produção: intocada. Somente `SELECT`.
- `amigao_entrada`: mantido, com as 18 linhas de staging da reprodução (10 do doc 546 + 8 do doc 549). Container `amigao-audit-db-1`, porta host 55433, role `entrada`.
  Para remover: `docker exec amigao-audit-db-1 psql -U postgres -c "DROP DATABASE amigao_entrada;"`
- Nenhuma dívida aberta, nenhuma correção aplicada, nenhum arquivo de código alterado. Esta rodada parou no relatório, por instrução.
