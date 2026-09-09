# ADR-064 — Extração ancorada e auditável (contenção da entrada)

**Data:** 09/09/2026
**Status:** Aceita
**Frente:** C — contenção da entrada (`fix/contencao-entrada`)
**Insumo:** `docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md` (achados N1–N4 e os
cinco erros da spec, medidos nos casos ELODI/Valéria)
**Dívida aberta:** #215 (determinismo do LLM, N2)

---

## Contexto

Em 09/09 a entrada foi olhada pela primeira vez com o dado **entrando**, não com
o staging já formado. O relatório fecha com uma frase que reordena o plano:

> Reconciliar, tipar e datar observações que mudam a cada execução é construir
> sobre areia.

Quatro coisas foram medidas, e nenhuma delas é opinião:

1. **N1 — o exemplo do prompt virou dado.** O `nirf_cib` da matrícula 3.673 em
   produção é `6.442.022-1`. Essa string **não existe** no texto do doc 549
   (34.815 chars, `LIKE '%6.442.022%'` = false). É, literal, o exemplo escrito no
   prompt: `"nirf_cib": … (ex.: "6.442.022-1")`. Gravado com `confidence: high`,
   destino `matricula.nirf_cib` — o degrau 1 da cascata ITR↔matrícula. O mesmo
   valor aparece em **três processos** (16, 17 e 23); em um deles é verdadeiro
   (foi de lá que o exemplo nasceu), nos outros dois não está no documento.

2. **OCR-002 — a janela cortava o documento.** `EXTRACTOR_MAX_CHARS = 30.000`
   contra o doc 547, de 82.117 chars. O NIRF verdadeiro (`2.974.457-1`) está no
   **caractere 53.775**: o extrator nunca o viu. O único código INCRA-like dentro
   da janela era o do **confrontante** (`050.041.396.737-1`, char 1.286, na frase
   "cravado na confrontação da Fazenda Posse, da Nascente Agro Industrial, Código
   INCRA nº..."). O modelo respondeu certo sobre o texto que recebeu.

3. **OCR-001 — número registral lido como número comum.** O documento diz
   `926,36.54ha`, e diz **certo**: é a notação registral `hectares,ares.centiares`,
   com o extenso ao lado — *"novecentos e vinte e seis hectares, trinta e seis
   ares e cinquenta e quatro centiares"*. `parse_area_ha` resolve separadores pelo
   último presente (regra correta para número comum) e devolveu **92.636,54** —
   cem vezes o real. `check_format` **aprovou**, e a linha entrou com
   `confidence: high`, status `aceito`. A matriz compararia o CAR (2.180,8267 ha)
   contra uma soma de matrículas de 165.711,73 ha.

4. **N3 — a extração não era auditável.** Nenhum `ai_job` do extrator guardava
   `model_used`, `provider`, `tokens_in/out`, `cost_usd` ou `raw_output` — todos
   nulos (jobs 1467–1471 e 1473). O extrator nunca usou `call_llm`: ele delega a
   chamada a `document_extractor` e a `ficha01_extraction`, que falam com o
   gateway direto, e `BaseAgent._complete_job` só grava o que `call_llm` deixou em
   `_llm_response`. O que o LLM devolveu deixava de existir depois da chamada — e
   é por isso que a origem dos erros da ELODI só pôde ser tratada como hipótese
   até a reprodução manual de 09/09.

---

## Decisão

Quatro contenções na entrada, todas antes do staging.

### 1. Valor sem âncora no texto não entra no staging

Todo valor extraído carrega **onde ele está** no `extracted_text`: posição no
texto original, trecho ao redor e o método usado. Valor que não é encontrado
**não vira campo do cadastro** — vira linha explícita, visível na Conferência,
com `target_entity`/`target_field` nulos e o motivo escrito.

**Por que não descartar em silêncio:** "nada some sem dizer" (P12) vale
principalmente para o que o sistema decidiu não usar. O bruto fica preservado em
`field_value.value`; a consultora vê o que o modelo afirmou, lê que não há fonte
para aquilo, e decide.

**Por que busca normalizada e não igualdade:** o modelo copia `6.816.752-0` de um
texto que pode escrever `6.816.752-0`, `6816752-0` ou `6.816.752 - 0`, e copia
`Fazenda "POSSE OU PORCOS - GLEBA 4"` de um texto que escreve `PORCOS- GLEBA`.
Igualdade exata rejeitaria dado bom. Dois eixos, ambos com mapa de volta para a
posição original: **dígitos** para números e códigos, **palavras** (minúsculas,
sem acento, pontuação virando espaço) para nomes.

**Terceira resposta, deliberada.** A busca tem três saídas, não duas: *achei*,
*não está lá* e **não se aplica**. Valor curto demais para provar qualquer coisa
(`uf` = "GO", um número de um dígito) é marcado `nao_verificavel` e passa. Tratar
"a busca não se aplica" como "não está no documento" seria mentir sobre a
evidência — e produziria pendência falsa em campo correto.

**Fronteira declarada.** A âncora é regra DURA só para valores **escalares**.
Valores **compostos** (`onus`, `averbacao_app`, `matricula_listada`,
`proprietarios`, `pendencias_rat`) são descrições que o modelo redige — não há
literal para casar. Para eles a âncora é **informativa**: as folhas escalares são
ancoradas e a cobertura é registrada (`ancoradas` de `verificaveis`, com a lista
do que não ancorou). É assim que "credor Banco do Brasil" numa alienação
fiduciária do **Itaú** — erro que reproduziu igual nas duas execuções do doc 549
— vira sinal, sem que esta frente precise entender o que é um ônus. Barrar aqui
apagaria o material da frente seguinte (tipo de observação e temporalidade).

**Sem texto em mãos, o gate não julga** — mesma regra do guard de identidade
(`_pode_declarar_identidade`): não é papel deste guard adivinhar.

### 2. A janela cobre o documento inteiro

O extrator de staging percorre o texto em **fatias sequenciais com sobreposição**
e mescla os JSONs por regra. Documento que cabe numa fatia continua sendo uma
chamada só — o caso da maioria.

Três candidatas foram consideradas:

| candidata | por que não / por que sim |
|---|---|
| prompt maior numa tacada | cabe no contexto (82k chars ≈ 20k tokens) e é a mais barata, mas não resolve o documento de 200k e degrada com a distância ("lost in the middle") justamente nos campos que aparecem tarde — os que estamos consertando |
| passes múltiplos, um prompt por campo | melhor qualidade, custo multiplicado pelo número de campos |
| **fatias sequenciais com sobreposição** | **escolhida**: cobre o documento inteiro num número de chamadas proporcional ao TAMANHO (2 para o doc 547, 1 para os de até 45k), e a sobreposição impede que um valor partido na emenda suma dos dois lados |

Parâmetros (`EXTRACTOR_CHUNK_CHARS=45.000`, `EXTRACTOR_CHUNK_OVERLAP_CHARS=2.000`,
`EXTRACTOR_MAX_CHUNKS=8`) saem da medição: 45k ≈ 11k tokens no gpt-4o-mini, e os
documentos reais da ELODI são 4k / 27k / 34k / 57k / 82k — ou seja, 1, 1, 1, 2 e
2 chamadas. Custo medido: o doc 549 (29.854 chars) cabe em **uma** fatia e
custa **$0,0012–0,0020** na camada de staging; o `AIJob` completo do extrator
(preview + staging) somou **$0,0030 / 22.192 tokens**. Cobertura parcial por teto
de fatias é **registrada** (`JanelaResultado.truncado`), nunca silenciosa.

**A mesclagem é o que fecha o caso do doc 547.** Com dois candidatos para
`nirf_cib` — o do confrontante (fatia 0) e o do imóvel (fatia 1) — "o primeiro
vence" manteria o errado. A ordem de preferência é:

1. **passa na validação de formato do campo** (`field_validators.check_format`) —
   `050.041.396.737-1` é código SNCR/INCRA de 13 dígitos e reprova como NIRF;
   `2.974.457-1` passa. A validação de formato já existia e só sinalizava; aqui
   ela **decide entre iguais**;
2. maior confiança declarada pelo modelo;
3. fatia mais cedo — desempate estável, para que duas execuções sobre o mesmo
   texto elejam o mesmo valor.

O que a regra descartou fica em `preteridos`, no log e na janela.

`EXTRACTOR_MAX_CHARS` **segue valendo** para a camada de PREVIEW
(`document_extractor`), que alimenta `AIJob.extracted_fields` e **não** escreve
no cadastro. Fronteira declarada: os cinco erros da spec nascem todos na camada
de staging.

### 3. Número registral é REGRA, não LLM

`parse_area_ha` — a porta única de área — reconhece a notação
`<hectares>,<ares 2 dígitos>.<centiares 2 dígitos>` e converte:
`926,36.54 → 926,3654`. `212,3553` e `2.180,8267` **não casam** o padrão e ficam
intactos, o que é a metade que importa da regra.

**Por que regra e não modelo:** a decodificação é determinística, e o próprio
documento traz o extenso que a confirma, a duas linhas do número. Pedir isso ao
LLM é trocar uma conversão exata por uma que varia entre execuções — a mesma
areia que esta frente existe para tirar do caminho.

**O extenso verifica, não decide.** Quando há extenso no entorno (achado pela
âncora — a posição do número no documento), ele é lido e comparado: bate ⇒ o
método vira `notacao_ha_a_ca+extenso`; não bate ⇒ `extenso_confere=False`,
confiança rebaixada e revisão. O sistema nunca escolhe entre os dois em silêncio.

**O bruto nunca é reescrito** (Item 1 da Isis): `field_value.value` guarda
`"926,36.54"` como o documento escreveu; `normalizado_ha`, `metodo_normalizacao`
e `extenso_confere` entram ao lado.

`check_format` para áreas passou a exigir também a **ordem de grandeza do
domínio** (`is_area_plausible`, 0,1 ha a 100.000 ha) — "positivo" era pouco.
Nota honesta: **não é a faixa que mata o 92.636,54** (ele cabia nela); quem o
mata é a regra da notação, que faz aquele literal valer 926,3654. A faixa fecha a
classe vizinha, do separador de milhar perdido acima de 100.000 ha.

### 4. Extração auditável

`BaseAgent` ganha `registrar_chamada_llm(response, rotulo=…)`: um agente que
delega a chamada a um serviço passa a **somar** essas chamadas num `AIResponse`
agregado, que `_complete_job` grava do jeito de sempre — `raw_output` com CADA
resposta bruta **rotulada** (documento, camada, fatia), tokens e custo somados,
modelos e providers listados. `call_llm` não muda: agentes no caminho normal
seguem gravando a resposta única, com o mesmo shape.

Os três serviços que o extrator orquestra (`document_extractor`,
`ficha01_extraction`, `auto_infracao_extraction`) ganharam um callback opcional
`on_llm_response(response, rotulo)` — aditivo, sem quebrar chamador nenhum.

---

## Consequências

**Ganhos**

- O Princípio 11 ("nenhuma afirmação sem fonte") deixa de ser aspiração na
  entrada e vira **condição de entrada**: o que não tem fonte não chega ao
  cadastro, e diz por quê.
- O que o LLM devolveu é **reconferível** a partir do próprio `AIJob` — a
  próxima auditoria não precisa reproduzir nada à mão.
- Áreas em notação registral param de entrar 100× maiores com status `aceito`.
- Conteúdo além do char 30.000 passa a existir para o extrator.

**Custos**

- **Mais chamadas ao LLM em documentos longos.** 2 chamadas em vez de 1 para
  documentos de 45k–90k chars. Medido: $0,0030/documento de 30k. O teto de fatias
  limita o pior caso.
- **`raw_output` cresce.** Cada job carrega as respostas brutas (teto de 20 KB por
  chamada e 200 KB no total, cortando pelo mais antigo — o corte é declarado no
  próprio bloco).
- **Linha nova na Conferência.** Valor sem âncora aparece como pendência
  vermelha. É trabalho novo para a consultora — e é exatamente o trabalho que
  hoje não é feito porque o erro entra invisível.
- **Falso positivo é possível.** Um valor legítimo que o modelo parafraseou (em
  vez de copiar) será barrado. A saída é a mesma de sempre: a linha fica visível,
  a consultora corrige. Preferimos a pendência visível ao dado sem fonte gravado.
- **Contrato interno mudou:** `_extract_structured` devolve `(parsed, janela)`.
  Quatro testes que mockavam a função foram atualizados.

**O que esta ADR NÃO resolve** (declarado, não esquecido)

- **N2, o determinismo** — dívida **#215**. A âncora e a janela reduzem a
  variação; eliminá-la é outra conversa (temperatura, cache, votação).
- **OCR-002 restante, DATA-002 e HIST-001** — arrendamento em `averbacao_app`, o
  segundo slot de área do CAR, ato sem data/número/partes. São as frentes
  seguintes e **dependem desta**.
- **Papel de pessoa** e **tipo de observação** — idem.
- **A camada de preview** (`document_extractor`) segue com janela de 30.000
  chars. Ela não escreve no cadastro.

---

## Verificação

Medida em banco descartável (`amigao_entrada`, host 55433) com o
`extracted_text` de produção e chamadas reais ao gpt-4o-mini — antes e depois,
duas execuções de cada lado. Tabela completa em
`docs/trabalhos/contencao_entrada.md`.

| gate | resultado |
|---|---|
| N1 — `6.442.022-1` (exemplo do prompt) no doc 549 | **barrado**, sem destino, motivo escrito |
| N1 — `6.816.752-0` (está no texto) | entra, `pos=10837`, método `digitos` |
| janela — valor além do char 30.000 | ANTES `None`; DEPOIS lido da fatia 1 |
| `926,36.54` / `725,46.63` | `926,3654` / `725,4663`, extenso confere |
| `212,3553` / `2.180,8267` | inalterados |
| N3 — `AIJob` do extrator | ANTES 5 campos nulos; DEPOIS modelo, provider, 22.230 tokens, $0,0030, 3.801 chars de bruto em 2 blocos rotulados |
| variação entre 2 execuções (doc 549) | ANTES 5/10 campos; DEPOIS 1/8 — e `nirf_cib` estável e correto nas duas |
