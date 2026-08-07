# Ingestão das normativas federais (pacote da Isis) — MISSÃO CONGELADA

**Data:** 2026-08-04
**Branch:** `chore/ingestao-normativas-federais-ago26`
**Estado:** ⛔ **congelada na fila** pelo Passo −1 do ADENDO 02.
**Corpus:** intocado — 31.298 chunks / 102 documentos, o mesmo de antes.

Este não é o relatório de uma ingestão concluída. É o relatório de uma ingestão
que **rodou, foi medida e foi revertida** quando um gate posterior a alcançou.
Fica no repositório porque a apuração que ela produziu é o insumo da próxima
tentativa — e porque o ocorrido merece registro, não silêncio.

---

## 1. O gate do Passo −1 (ADENDO 02)

| Verificação exigida | Evidência | Resultado |
|---|---|---|
| `feat/chunking-estrutural` mergeada na main | `git log origin/main..feat/chunking-estrutural` → **vazio**; a branch não existe em `origin` e está parada no HEAD da main (`c752949`) | ❌ |
| Reindexação final concluída | nenhuma; corpus no baseline de 31.298 chunks desde a medição de 03/08 | ❌ |
| Guarda de sanidade ativa no chunker | `app/services/chunking.py` — **nenhum** `raise`, `logger` ou teto de sanidade em todo o arquivo; segue `TARGET_TOKENS = 800` (l. 28), `MAX_TOKENS = 1500` (l. 29) e o regex `^\s*Art\.\s*\d+` MULTILINE (l. 26) | ❌ |

**Três de três reprovados.** A ordem correta é remediação → ingestão.

### Por que isso não foi respeitado

Ordem dos fatos, sem atenuante: o ADENDO 02 chegou **durante** a execução, depois
de o Passo 3 já ter gravado. O prompt original e o ADENDO 01 não continham gate
de sequenciamento; quando ele apareceu, a escrita já estava feita. Não houve
decisão de ignorar o gate — houve um gate que chegou depois da escrita que ele
proibia.

---

## 2. O que foi escrito, medido e revertido

11 documentos (ids 189–199) e 420 chunks entraram no **dev** (`amigao_db`),
com a curadoria de metadados completa. Prod nunca foi tocado.

Antes de apagar, o dano foi medido em vez de presumido — porque a premissa do
gate ("seriam chunkeadas pelo chunker defeituoso, com fatias de até 298k tokens")
merecia conferência:

| norma | arts | chunks | mediana | p95 | máx | >1500 tok |
|---|---:|---:|---:|---:|---:|---:|
| IN INCRA 77/2013 | 23 | 24 | 95 | 256 | 445 | 0 |
| IN RFB 2.203/2024 | 31 | 32 | 163 | 376 | 714 | 0 |
| Resolução CMN 5.193/2024 | 3 | 7 | 451 | 800 | 800 | 0 |
| Resolução CONAMA 406/2009 | 21 | 22 | 58 | 412 | 697 | 0 |
| Resolução CONAMA 411/2009 | 14 | 25 | 627 | 800 | 800 | 0 |
| IN IBAMA 21/2014 | 75 | 81 | 180 | 730 | 800 | 0 |
| IN IBAMA 16/2022 | 22 | 26 | 166 | 800 | 800 | 0 |
| IN IBAMA 11/2025 | 22 | 23 | 92 | 297 | 463 | 0 |
| IN IBAMA 21/2023 | 120 | 125 | 111 | 594 | 1345 | 0 |
| Portaria IBAMA 15/2026 | 9 | 10 | 68 | 210 | 310 | 0 |
| IN IBAMA 24/2024 | 20 | 45 | 800 | 800 | 800 | 0 |
| **global (420 chunks)** | | | **152** | **800** | **1345** | **0** |

**A catástrofe prevista não se materializou neste pacote.** Pior fatia: 1.345
tokens. Nenhuma acima de 1.500. Na maioria das normas a contagem de artigos e a
de chunks andam juntas (23→24, 31→32, 75→81; o `+1` é o preâmbulo/ementa).

Os três descolamentos têm causa identificada, e é **tamanho legítimo**, não
fronteira perdida:

- **IN IBAMA 24/2024** (20 arts → 45 chunks, *todos* no teto de 800): os anexos
  da Convenção de Basileia são listas, não artigos. Janela deslizante pura.
- **Resolução CONAMA 411/2009** (14 → 25): idem, tabela de nomenclatura e
  coeficientes de rendimento.
- **Resolução CMN 5.193/2024** (3 → 7): o corpo normativo é o texto do MCR 2-9,
  que não usa "Art." — o documento tem só 3 artigos próprios.

O que o chunker atual **não** produziu, e o #119 exige: hierarquia
(Título › Capítulo › Seção › Art.) e número do artigo em campo consultável. Isso
não existe hoje em `knowledge_catalog`. Por esse motivo — e não pelo tamanho das
fatias — estas 13 normas teriam de ser re-chunkeadas de qualquer forma.

### Calibração do gate (registrada por decisão do André — o plano da remediação usa)

A premissa de que **"os 420 chunks estão quebrados" NÃO se confirmou**: mediana
152, p95 800, máx 1.345, zero acima de 1.500, nenhuma fatia de 298k tokens.

**O gate segue válido — por #119, não por fronteira perdida.** Sem hierarquia
(Título › Capítulo › Seção › Art.) e sem número de artigo em campo consultável,
o re-chunk é obrigatório de qualquer forma. O que muda é a *justificativa*: a
ordem remediação → ingestão continua certa, mas não porque este pacote seria
estragado.

**Hipótese sugerida pela medição — a confirmar na remediação, não conclusão:**
o defeito de fronteira do regex `^\s*Art\.` MULTILINE parece se concentrar em
PDFs de **compêndio/coletânea estaduais** (documento que empilha várias normas,
onde uma âncora `Art.` falsa emenda dois diplomas), e **não** em norma federal
avulsa bem formada, que tem um único preâmbulo e uma sequência de artigos
limpa. As 11 medidas aqui são todas do segundo tipo, e nenhuma passou de 1.345
tokens. Isso é indício, não prova: a medição da remediação é que decide, e ela
deveria olhar de propósito para as coletâneas (`Coletânea Licenciamento GO
2020+`, `Coletânea Outorga GO 1997+`, `Anexo ATIV-INEX GO 308p`) antes de
generalizar a partir de norma avulsa.

### Revert

Autorizado pelo André com condições (inventário completo antes, só dev, só ids
189–199, transação única, verificação exata).

```
apagados (ainda NA TRANSAÇÃO): 420 chunks, 11 documentos
conferência dentro da transação: 31298 chunks / 102 docs (alvo 31298/102)
COMMIT feito.

=== VERIFICAÇÃO PÓS-COMMIT (sessão nova) ===
chunks: 31298 | alvo 31298
docs  : 102 | alvo 102
sobrou algo em 189..199?: 0
chunks órfãos do pacote?: 0
modelos no índice: [('text-embedding-3-small', 31298)]
```

A conferência roda **dentro** da transação: divergência faria `rollback` em vez
de apagar e corrigir depois. Bateu exato no primeiro commit. Corpus com
fingerprint estável — o baseline do chunking pode começar.

---

## 3. O que a apuração deixou pronto (sobrevive ao congelamento)

### 3.1 Integridade do pacote — Passo 0-bis ✅

13 arquivos, nenhuma subpasta, **13/13 SHA-256 conferem** com o manifesto do
ADENDO 01. O pacote veio como `.rar` e não como o `.zip` prometido; irrelevante,
porque o manifesto assina cada PDF e não o container. Todos os 13 têm camada de
texto — **nenhum precisa de OCR**.

### 3.2 Dedupe — Passo 0 ✅

11 novas, 2 já existentes. Detalhe completo em `INVENTARIO_PRE_INGESTAO.md`.
As duas colisões só apareceram porque o dedupe compara identificador
**normalizado** (tipo+órgão+número+ano), e não string crua:

| pacote | chave normalizada | casou com | similaridade | veredito |
|---|---|---|---|---|
| `IN MMA 02-2014.pdf` → IN MMA 2/2014 | `in\|mma\|2\|2014` | id=1 `IN MMA 02/2014` | **1,0000** | mesmo arquivo, outro nome — duplicata pura |
| `RESOLUCAO CONAMA 369-2006.pdf` → Resolução CONAMA 369/2006 | `resolucao\|conama\|369\|2006` | id=25 `Res. CONAMA 369/2006` | 0,9403 | **pendência humana** |

O `content_hash` do corpus antigo guarda hash do **texto**, não do arquivo — por
isso a comparação é por texto extraído. Hashes completos no inventário.

Defeito encontrado e corrigido no próprio normalizador, antes de commitar:
identificador **sem** número e ano — que no corpus existe, são rótulos e não
normas (`Anexo ATIV-INEX GO 308p`, `AC-N03-florestal_car_pra`) — colapsava numa
chave degenerada e dois rótulos **diferentes** casavam como duplicata.

Antes/depois medido sobre os 102 identificadores do corpus:

| | chaves geradas | colisões falsas | duplicatas verdadeiras achadas |
|---|---:|---:|---:|
| **antes** | 100 | **2** (`Anexo ATIV-INEX GO 308p` × `7p`; `AC-N03-florestal_car_pra` × `AC-N06-florestal_car_pra_2`) | 2 |
| **depois** | **102** | **0** | 2 |

Correção: sem número **ou** sem ano, a chave cai no texto cru normalizado, que só
casa consigo mesmo. Não teria mordido neste pacote (as 13 têm número e ano), mas
morderia na próxima entrega com anexo — e o sintoma seria o pior tipo: o ingestor
**pulando documento legítimo** achando que é duplicata, em silêncio.

Sobre a CONAMA 369/2006: os ~2,4 mil chars a mais da versão do pacote (SIAM/MG)
**não são normativos** — são o aparato de notas de rodapé do SIAM citando normas
correlatas. As duas versões trazem o corpo íntegro (Art. 1 a 18).

> **DECIDIDO pelo André (2026-08-04): manter o id=25 (CETESB).** Não é mais
> pendência. Razão registrada, nas palavras dele: *"A evidência sustenta: 0,94 de
> similaridade e a diferença sendo aparato de notas do SIAM, não conteúdo
> normativo. Trocar uma norma FEDERAL já ingerida por captura de portal estadual
> de outro estado (MG) pioraria a proveniência."*
>
> Consequência operacional: `RESOLUCAO CONAMA 369-2006.pdf` **fica fora do
> corpus em definitivo** — pulada por dedupe, e agora também por decisão. Na
> retomada, o script continua pulando-a sozinho; não há nada a fazer.

### 3.3 Limpeza de moldura — Passo 2 ✅ (validada)

A detecção por repetição entre páginas disparou em **exatamente** os 3 arquivos
de captura web, e em nenhum dos outros 10 — zero falso-positivo:

```
### IN RFB 2.203-2024.pdf  (14 pág)  -2469 chars (8.3%)
    REMOVERIA: '04/08/2026, 11:16 INSTRUÇÃO NORMATIVA RFB Nº 2.203, … – LEX EDITORA'
    REMOVERIA: 'https://www.lex.com.br/instrucao-normativa-rfb-no-2-203-…/ 1/14'
### RESOLUCAO CONAMA 369-2006.pdf  (13 pág)  -1668 chars (5.4%)
    REMOVERIA: '04/08/2026, 11:22 RESOLUÇÃO CONAMA Nº 369, DE 28 DE MARÇO DE 2006'
    REMOVERIA: 'https://www.siam.mg.gov.br/sla/download.pdf?idNorma=5486 1/13'
### Resolução CMN 5.193-2024.pdf  (4 pág)  -520 chars (4.1%)
    REMOVERIA: '04/08/2026, 11:19 Exibe Normativo'
    REMOVERIA: 'https://www.bcb.gov.br/…/exibenormativo?tipo=Resolução CMN&numero=5193 1/4'
```

O detalhe que só apareceu porque foi conferido: a detecção por repetição **não
basta**. O rodapé de site aparece uma vez só, na última página, e escapa dela. No
RFB 2.203/2024 o que escapava não era menu decorativo — eram **títulos de outras
normas** ("Postagens Recentes": Resolução ANA 298/2026, Portaria MIDR 2.458/2026,
Lei 15.481/2026). Sem corte, esses títulos virariam chunk **sob a identidade da
IN RFB 2.203/2024**, e a busca devolveria norma trocada. Resolvido com âncora de
corte (`Post seguinte`), com guarda: âncora que aparece antes de 60% do documento
não corta e emite aviso — perder o corte é ruim, decapitar a norma é pior.

**Amostras de chunk limpo** (2 por documento, como exigido):

`IN RFB 2.203/2024` — chunk 0:
```
INSTRUÇÃO NORMATIVA RFB Nº 2.203, DE 17 DE JULHO DE 2024
19/07/2024 / Legislação
Dispõe sobre o Cadastro de Imóveis Rurais – Cafir.
O SECRETÁRIO ESPECIAL DA RECEITA FEDERAL DO BRASIL, no uso da atribuição que lhe
confere o art. 350, caput, inciso III, do Regimento Interno…
```
`IN RFB 2.203/2024` — chunk 16:
```
Art. 16. No ato de inscrição cadastral, o endereço constante no CPF ou no CNPJ do titular
do imóvel rural será armazenado na base do Cafir para fins de intimação ou para
comunicação de quaisquer outras informações relativas ao ITR.
```

`Resolução CMN 5.193/2024` — chunk 0:
```
Resolução CMN n° 5.193 de 19/12/2024
RESOLUÇÃO CMN Nº 5.193, DE 19 DE DEZEMBRO DE 2024
Altera normas da Seção 9 (Impedimentos Sociais, Ambientais e Climáticos) do Capítulo 2
(Condições Básicas) do Manual de Crédito Rural – MCR.
```
`Resolução CMN 5.193/2024` — chunk 3:
```
Art. 3º Esta Resolução entra em vigor:
I - na data de sua publicação, quanto à revogação do art. 3º da Resolução CMN nº 5.149…
II - em 2 de janeiro de 2025, quanto aos demais dispositivos.
ROBERTO DE OLIVEIRA CAMPOS NETO
```

`Resolução CONAMA 369/2006` — **não ingerida** (duplicata do id=25). A limpeza
rodou e foi conferida mesmo assim, para que a pendência humana seja decidida com
o texto tratado à vista (19 chunks nasceriam):
```
RESOLUÇÃO CONAMA Nº 369, DE 28 DE MARÇO DE 2006
Dispõe sobre os casos excepcionais, de utilidade pública, interesse social ou baixo
impacto ambiental, que possibilitam a intervenção ou supressão de vegetação em
Área de Preservação Permanente-APP.
(Publicação - Diário Oficial da União 29/03/2006)
```
```
Art. 9º A intervenção ou supressão de vegetação em APP para a regularização
fundiária sustentável de área urbana poderá ser autorizada pelo órgão ambiental
competente, observado o disposto na Seção I desta Resolução…
```

Nenhuma data de captura, URL, paginação `N/M` ou menu sobrou em nenhuma amostra.

### 3.4 Espaço vetorial — Regra E1 ✅

Provider resolvido em execução: **openai / `text-embedding-3-small` / 768 dim**,
que é o alvo. `EMBEDDING_PROVIDER` vazio cai no default do produto declarado em
`app/services/embeddings.py`, e a trava do ADR-040 está ativa — a busca filtra
`kc.embedding_model = :embedding_model`. Índice 100% num só espaço, antes e
depois do revert: `[('text-embedding-3-small', 31298)]`.

### 3.5 Custo — Regra E4 ✅

420 chunks, 105.571 tokens embutidos, **US$ 0,0021**. O script aborta acima de
US$ 1,00 (`TETO_CUSTO_USD`). Três ordens de grandeza abaixo do teto.

### 3.6 Buscas de fumaça — Passo 4 / Regra E6 ⚠ parcial

Rodadas **depois** da ingestão (as 3 passaram, top-5); o baseline "antes" que a
Regra E6 exige não foi colhido, porque a regra chegou junto com o adendo, depois
da escrita. Não é recuperável agora por medição direta, mas **é reconstruível**:
o estado anterior é o índice atual, que já voltou a ser exatamente o de antes.
Na retomada, colher o baseline antes de escrever — agora é possível, porque o
revert restaurou o fingerprint.

Resultado pós-ingestão, para registro (top-5, similaridade colada):

```
'intervenção em APP utilidade pública'  -> PASSOU
  1. [0.6318] Coletânea Licenciamento GO 2020+ — Art. 5º prazo de validade do registro
  2. [0.6313] Coletânea Licenciamento GO 2020+ — Art. 2º Registro para intervenção em APP
  3. [0.6242] Res. CONAMA 369/2006 — Art. 11 <<<
  4. [0.6107] Res. CONAMA 369/2006 — Art. 3º  <<<
  5. [0.6101] Res. CONAMA 369/2006 — Art. 4º  <<<

'impedimento crédito rural embargo ambiental'  -> PASSOU
  1. [0.7229] MT-NUC07-credito_pd — Art. 3º Esta Resolução entra em vigor
  2. [0.7229] MT-NUC08-biomas — Art. 3º Esta Resolução entra em vigor
  3. [0.7018] Resolução CMN 5.193/2024 — Art. 3º (parte 3) <<<
  4. [0.6996] MT-NUC07-credito_pd
  5. [0.6996] MT-NUC08-biomas

'DOF transporte produto florestal nativo'  -> PASSOU
  1. [0.7098] IN IBAMA 21/2014 — Art. 36. A emissão do DOF para o transporte <<<
  2. [0.6891] Decreto 6.660/2008 — Art. 11
  3. [0.6858] IN IBAMA 21/2014 — Art. 61 <<<
  4. [0.6855] Decreto 6.660/2008 — Art. 3
  5. [0.6744] IN IBAMA 21/2014 — Art. 37 <<<
```

Três observações honestas sobre esses números, na linha do que o ADENDO 02 pede
("o que a ingestão mudou nas respostas?"):

1. **A query 1 não precisava da ingestão.** Ela é atendida pelo id=25, que já
   estava no corpus desde abril. O pacote não mudou nada nessa resposta — e não
   mudaria, já que sua CONAMA 369 é duplicata. É o caso "mais chunk não é, por
   si, mais valor" acontecendo de novo.
2. **A query 2 mudou de verdade**, mas nem tanto quanto parece: a CMN 5.193/2024
   entrou em 3º com 0,7018, atrás de dois chunks de MT (`MT-NUC07-credito_pd`,
   `MT-NUC08-biomas`) a 0,7229 — que casam pelo *preâmbulo* "Art. 3º Esta
   Resolução entra em vigor", não pelo conteúdo de crédito rural. Sinal de ruído
   de fronteira que a remediação do chunking tende a atacar.
3. **A query 3 mudou claramente**: a IN IBAMA 21/2014 assumiu o 1º lugar
   (0,7098) e ocupou 3 das 5 posições. Este é o ganho real e inequívoco do pacote.

Nota de método: a asserção da query 1 falhou na primeira execução por culpa da
**asserção**, não do corpus — eu comparava a string `Resolução CONAMA 369/2006`
com o identificador gravado `Res. CONAMA 369/2006`. Corrigido aplicando à
verificação a mesma normalização usada no dedupe: se duas grafias são a mesma
norma para decidir duplicata, têm de ser a mesma norma para validar recuperação.

### 3.7 Metadado de origem — Regra E5 ✅

Curadoria pronta, com `fonte_oficial` conservador (o que ninguém conferiu não se
apresenta como oficial) e `fonte_conferida_em = NULL` em todas — nenhuma passou
por conferência humana:

| norma | origem | oficial |
|---|---|---|
| IN RFB 2.203/2024 | captura de `lex.com.br` (LEX EDITORA) — agregador comercial | **não** |
| Resolução CMN 5.193/2024 | captura de `bcb.gov.br/estabilidadefinanceira` | sim |
| Resolução CONAMA 369/2006 | captura de `siam.mg.gov.br/sla` (SEMAD-MG) | sim |
| IN IBAMA 21/2014 | traz "Publicada no DOU de 27/12/2014, Seção 1, p. 102-107" | sim |
| IN IBAMA 16/2022, 11/2025, Portaria 15/2026 | layout DOU/in.gov.br, "não substitui o publicado na versão certificada" | sim |
| IN IBAMA 21/2023, 24/2024 | layout DOU/in.gov.br | sim |
| Resolução CONAMA 406/2009 | "Publicado no DOU nº 26, de 06/02/2009, pág. 100" | sim |
| IN INCRA 77/2013, Resolução CONAMA 411/2009 | sem marcador de publicação no documento | **não** |

### 3.8 Achados de curadoria

- **`IN IBAMA 4-2024.pdf` não é a IN 4/2024.** O arquivo foi nomeado pelo *dia*
  da assinatura (04/12/2024); o documento é a **IN IBAMA 24/2024**. Gate do
  despacho cumprido na curadoria: `identifier = "IN IBAMA 24/2024"`.
- **Dois textos são consolidados, não a redação original.** IN IBAMA 21/2014 já
  incorpora as IN 9/2016 e 13/2017 (rodapé cita os três DOUs); IN IBAMA 21/2023
  traz alterações "publicada no DOU de 5 de janeiro de 2026". Registrado em
  `extra_metadata.nota_curadoria` — muda o que se pode citar.
- **Falta o Anexo Único da IN RFB 2.203/2024.** A captura da LEX o marca como
  *"(exclusivo para assinantes)"*. Entra o corpo (Art. 1 a 31), sem o anexo. Quem
  for citá-lo precisa da fonte oficial.

---

## 4. Decisão de modelagem que fica registrada

`content_hash` destas 13 recebe o **SHA-256 do PDF**, não do texto extraído como
faz o resto do corpus. É o que o ADENDO 01 determina e é o que torna o dedupe do
Passo 0 possível numa próxima entrega do mesmo pacote: o texto muda com a versão
do `pypdf`, o arquivo não. O hash do texto não se perde — vai em
`extra_metadata.texto_sha256`, ao lado de `arquivo_sha256`.

---

## 5. Retomada — o que fazer quando o Passo −1 abrir

1. Conferir de novo o gate: merge de `feat/chunking-estrutural`, reindexação
   concluída, guarda de sanidade viva no código. Colar as evidências.
2. Colher o **baseline E6** das 3 queries (top-8 com similaridade) **antes** de
   escrever. Agora é possível: o revert restaurou o fingerprint de 31.298.
3. Rodar `scripts/ingest_normativas_federais_ago26.py --inventario`, depois
   `--dry-run`, depois valendo. O script é idempotente por identificador
   normalizado + SHA-256 do arquivo.
4. Refazer E3 com o chunker novo: contagem de artigos × chunks, distribuição de
   tokens, e separar "partido por tamanho legítimo" de "fronteira perdida".
5. Repetir as 3 buscas e responder o que mudou em relação ao baseline.
6. Só então atualizar `BASE_REGULATORIA.md` e `ESTADO_ATUAL.md` — **nada foi
   atualizado agora, porque nenhuma contagem mudou.**

Dívidas a registrar na faixa do corpus (#100–199) no momento da retomada — não
abertas agora, por determinação de congelar a missão:

- ~~Pendência humana da CONAMA 369/2006~~ — **resolvida em 2026-08-04**: manter
  o id=25 (CETESB). Não gera dívida. Ver seção 3.2.
- **Anexo Único da IN RFB 2.203/2024** ausente; buscar fonte oficial.
- `IN MMA 02/2014` (id=1) e `Res. CONAMA 369/2006` (id=25) têm grafia de
  identificador fora do padrão do resto do corpus. O dedupe normalizado
  contorna, mas a inconsistência continua lá.

---

## 6. Estado final

| | |
|---|---|
| Corpus (dev) | **31.298 chunks / 102 documentos** — idêntico ao de antes |
| Prod | intocado |
| Normas ingeridas | **0** (11 gravadas e revertidas) |
| Custo gasto | US$ 0,0021 (embeddings descartados no revert) |
| Código entregue | `scripts/ingest_normativas_federais_ago26.py`, pronto e ensaiado |
| PR | **não aberto** — por decisão, a entrega espera a remediação |

---

# EXECUÇÃO — 06/08/2026

O congelamento acabou. A ingestão rodou depois que o pré-requisito duro foi
cumprido: **rebase sobre a main pós-remediação do chunking**.

## Por que o rebase era pré-requisito, e não formalidade

O script sempre importou o chunker compartilhado (`from app.services.chunking
import chunk_text`) e nunca teve lógica própria — o desenho estava certo. Mas a
worktree congelada carregava o chunker **antigo**:

```
app/services/chunking.py:31:  _CHARS_PER_TOKEN = 4
app/services/chunking.py:35:  return max(1, len(text) // _CHARS_PER_TOKEN)
```

Rodar dali faria as 11 normas nascerem com os defeitos recém-corrigidos: régua
que subestima até **2,44×**, sem guarda contra o teto de 8.192 da API, sem
`dispositivo`/`hierarquia`/`referencias`, e com material não articulado herdando
rótulo falso de artigo.

Depois do rebase (limpo, sem conflito) a worktree tem `contar_tokens` via
`tiktoken`, `MAX_ARTIGO_TOKENS = 7000`, `LIMITE_ARTIGO_TOKENS = 8000`,
`LIMITE_API_TOKENS = 8192`, a guarda `chunking.fatia_absorvedora` e a
normalização de ligaduras. **Esta é a primeira ingestão do projeto a rodar sobre
o chunker corrigido.**

## Fingerprint — previsto ANTES, conferido depois

| | declarado antes de executar | observado |
|---|---:|---:|
| chunks | **32.161** | **32.161** ✅ |
| documentos | **113** | **113** ✅ |
| max id | 210 | 210 |
| espaço vetorial | `text-embedding-3-small` 768d | único, mesmo |

Nenhum ajuste. Divergência aqui seria achado, não correção.

## As 11, uma transação por norma — zero rollback

| identificador | id | chunks previstos | chunks efetivos | maior chunk |
|---|---:|---:|---:|---:|
| IN IBAMA 21/2023 | 208 | 121 | **121** | 3.849 |
| IN IBAMA 21/2014 | 205 | 76 | **76** | 5.778 |
| IN IBAMA 24/2024 | 210 | 54 | **54** | 892 |
| IN RFB 2.203/2024 | 201 | 32 | **32** | 888 |
| Resolução CONAMA 411/2009 | 204 | 28 | **28** | 923 |
| IN INCRA 77/2013 | 200 | 24 | **24** | 526 |
| IN IBAMA 11/2025 | 207 | 23 | **23** | 550 |
| IN IBAMA 16/2022 | 206 | 23 | **23** | 3.458 |
| Resolução CONAMA 406/2009 | 203 | 22 | **22** | 822 |
| Portaria IBAMA 15/2026 | 209 | 10 | **10** | 448 |
| Resolução CMN 5.193/2024 | 202 | 4 | **4** | 2.903 |
| **total** | | **417** | **417** | |

**Custo real: US$ 0,0026** (129.841 tokens embarcados) — teto era US$ 1,00.
Maior chunk do lote: 5.778 tokens reais, sob o teto do artigo e bem sob o da API.
A guarda dura não disparou nenhuma vez.

**Aditiva, sem exclusão e sem deduplicação**, conforme determinado.

## Um dado que confirma o revert de ontem

As 11 apareceram como **NOVA** no inventário. São exatamente os 11 documentos que
a ingestão anterior gravou (ids 189–199) e que o revert removeu. Se tivesse
sobrado resíduo, elas apareceriam como "JÁ EXISTE". **O revert foi completo.**

## Buscas de fumaça — antes × depois

### 1. `impedimento crédito rural embargo ambiental` — MUDOU

| antes | depois |
|---|---|
| 0,6087 IN ICMBio 9/2023 | **0,6665 Resolução CMN 5.193/2024** ← nova |
| 0,6029 Lei 12.651/2012 | **0,6446 Resolução CMN 5.193/2024** ← nova |
| 0,5938 Lei 12.651/2012 | 0,6087 IN ICMBio 9/2023 |
| 0,5921 Lei 12.651/2012 | 0,6029 Lei 12.651/2012 |
| 0,5846 Decreto 6.514/2008 | 0,5939 Lei 12.651/2012 |

**Ganho qualitativo:** a pergunta saía respondida por **analogia com o Código
Florestal**; passou a ser respondida pela **resolução do Conselho Monetário
Nacional**, que é a norma que efetivamente disciplina o crédito rural. E com
similaridade maior que o topo anterior.

### 2. `DOF transporte produto florestal nativo` — MUDOU

| antes | depois |
|---|---|
| 0,6887 Decreto 6.660/2008 | **0,7097 IN IBAMA 21/2014** ← nova |
| 0,6866 Decreto 6.660/2008 | 0,6888 Decreto 6.660/2008 |
| 0,6691 Decreto 6.660/2008 | 0,6866 Decreto 6.660/2008 |
| 0,6522 Decreto 5.975/2006 | **0,6857 IN IBAMA 21/2014** ← nova |
| 0,6507 Decreto 6.660/2008 | **0,6838 IN IBAMA 21/2014** ← nova |

**Ganho qualitativo:** saía do **Decreto 6.660/2008**, que é da **Mata
Atlântica** — plausível, próximo do tema, e **errado** para uma pergunta sobre
DOF em geral. Passou a vir da **IN que institui o DOF**.

### 3. `intervenção em APP utilidade pública` — **NÃO MUDOU**

As cinco posições seguem 100% `Res. CONAMA 369/2006`, com variação de 0,0001 na
similaridade — ruído numérico do IVFFlat, não deslocamento.

**É controle negativo, não falha.** A CONAMA 369/2006 é justamente uma das duas
puladas por dedupe (id=25), e nenhuma das 11 normas novas trata de intervenção
em APP por utilidade pública. **Se essa busca tivesse mudado, seria sinal de
problema** — de norma nova sendo recuperada para pergunta que não é dela.

## O que estas duas mudanças significam

Nos dois casos que mudaram, **resposta certa substituiu resposta plausível**.
Esse é o erro que o consultor **não pegaria**: o Decreto 6.660/2008 fala de
transporte de produto florestal, cita DOF, tem tudo para parecer a norma
aplicável — e é de outro bioma. Uma peça fundamentada nele passaria em qualquer
leitura apressada.

Corpus incompleto não produz resposta vazia; produz resposta **quase certa**.

## Aprendizado de método: o controle negativo foi acidental

A busca de APP funcionou como **controle negativo** — a pergunta cujo resultado
esperado é *nenhuma mudança*, e que por isso detecta ganho inventado.

**Mas ela não foi desenhada para isso.** A CONAMA 369/2006 ficou de fora por uma
decisão de **proveniência** (manter a versão id=25, do CETESB, em vez da captura
SIAM/MG do pacote), tomada por outro motivo. O controle apareceu de brinde: como
nenhuma das 11 normas novas trata de intervenção em APP por utilidade pública, a
pergunta que já era respondida pela 369/2006 continuou sendo.

Deu certo por acaso, e acaso não é método. **Toda ingestão futura deveria levar
uma pergunta de controle EXPLÍCITA**, escolhida de propósito: um tema que o
pacote comprovadamente **não** cobre, com resultado esperado declarado como
"nenhuma mudança".

Sem ela, a medição só sabe dizer que algo mudou — não sabe distinguir **ganho
real** de **norma nova sendo recuperada para pergunta que não é dela**. As duas
coisas aparecem como "mudou", e só a segunda é defeito.

É o mesmo princípio do `art. 71` na remediação do chunking: experimento só com
casos que devem melhorar não detecta regressão.
