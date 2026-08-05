# Inventário pré-ingestão — pacote NORMATIVAS (federais)

**Data:** 2026-08-04
**Pacote:** `legislacao/NORMATIVAS.rar` (13 PDFs, entregue pela Isis)
**Branch:** `chore/ingestao-normativas-federais-ago26`
**Ambiente medido:** dev local — `amigao_db` @ `127.0.0.1:55432`
**Baseline do corpus antes de qualquer escrita:** 102 documentos em `legislation_documents`, **31.298 chunks** em `knowledge_catalog` (100% `text-embedding-3-small`, 768 dim)

Este documento é o gate do Passo 0: **nada foi inserido antes dele existir.**

> ⚠ **A ingestão está CONGELADA.** O ADENDO 02 chegou depois desta apuração e
> criou um Passo −1 (remediação do chunking #117→#118→#119 mergeada antes de
> qualquer escrita no corpus) que está **reprovado**. A ingestão chegou a rodar e
> **foi integralmente revertida**. O que este inventário apura — dedupe,
> caracterização das duas colisões, divergências de nomenclatura — continua
> valendo e é insumo da ingestão futura. Ver
> `RELATORIO_INGESTAO_NORMATIVAS_FEDERAIS.md`.

---

## Passo 0-bis — integridade do pacote

O despacho veio com a promessa de `NORMATIVAS.zip`; o que chegou foi o `.rar`
original. Como o manifesto é de hash **por PDF**, e não do container, a troca é
irrelevante para a verificação — foi exatamente por isso que o adendo mandou
assinar os arquivos, e não o pacote.

| Verificação | Esperado | Obtido | Resultado |
|---|---|---|---|
| Contagem de arquivos | 13 | 13 | ✅ |
| Subpastas | nenhuma | nenhuma | ✅ |
| Nomes conferem com a tabela do Passo 1 | 13/13 | 13/13 | ✅ |
| SHA-256 contra o manifesto | 13/13 | **13/13** | ✅ |

Nenhuma divergência. Extração de trabalho em `legislacao/NORMATIVAS/` (pasta
já coberta pelo `.gitignore` — PDF de corpus não entra no Git desde o incidente
do clone no Render).

Todos os 13 PDFs têm camada de texto: **nenhum precisa de OCR.**

---

## Passo 0 — dedupe

Critério: identificador **normalizado** (tipo + órgão + número + ano) e hash
SHA-256 do arquivo, ambos contra `legislation_documents` inteira.

A normalização não é preciosismo. O corpus já convive com `Res. CONAMA 369/2006`
e `Resolução CONAMA 428/2010` para o mesmo tipo de norma; comparar string crua
deixaria passar a duplicata que este passo existe para pegar — e foi o que
aconteceu nas duas linhas marcadas abaixo. Número perde zeros à esquerda e ponto
de milhar (`02` ≡ `2`, `2.203` ≡ `2203`).

| # | Arquivo no pacote | Identificador canônico | Situação |
|---|---|---|---|
| 1 | `IN MMA 02-2014.pdf` | IN MMA 2/2014 | **JÁ EXISTE** — id=1 (`IN MMA 02/2014`), hash de texto **idêntico** |
| 2 | `IN INCRA 77-2013.pdf` | IN INCRA 77/2013 | NOVA |
| 3 | `IN RFB 2.203-2024.pdf` | IN RFB 2.203/2024 | NOVA |
| 4 | `Resolução CMN 5.193-2024.pdf` | Resolução CMN 5.193/2024 | NOVA |
| 5 | `RESOLUCAO CONAMA 369-2006.pdf` | Resolução CONAMA 369/2006 | **JÁ EXISTE** — id=25 (`Res. CONAMA 369/2006`), hash **diferente** |
| 6 | `RESOLUCAO CONAMA 406-2009.pdf` | Resolução CONAMA 406/2009 | NOVA |
| 7 | `RESOLICAO CONAMA 411-2009.pdf` | Resolução CONAMA 411/2009 | NOVA |
| 8 | `IN IBAMA 21-2014.pdf` | IN IBAMA 21/2014 | NOVA |
| 9 | `IN IBAMA 16-2022.pdf` | IN IBAMA 16/2022 | NOVA |
| 10 | `IN IBAMA 11-2025.pdf` | IN IBAMA 11/2025 | NOVA |
| 11 | `IN IBAMA 21-2023.pdf` | IN IBAMA 21/2023 | NOVA |
| 12 | `PORTARIA IBAMA 15-2026.pdf` | Portaria IBAMA 15/2026 | NOVA |
| 13 | `IN IBAMA 4-2024.pdf` | **IN IBAMA 24/2024** ⚠ | NOVA |

**NOVA: 11 · JÁ EXISTE: 2 · total: 13**

---

## As duas colisões, caracterizadas

O despacho manda pular e relatar. Pular é barato; relatar sem dizer *o que* se
está pulando não serve para ninguém decidir nada. As duas foram abertas:

### 1. IN MMA 2/2014 — mesma norma, **mesmo arquivo**

| | corpus (id=1) | pacote |
|---|---|---|
| chars do texto extraído | 38.902 | 38.902 |
| SHA-256 do texto | `005aa28bd915eb45…` | `005aa28bd915eb45…` |
| origem | `legislacao/IN_CAR.pdf` (Sprint 0, 2026-04-23) | `IN MMA 02-2014.pdf` |

Similaridade **1,000**. O PDF do pacote é bit a bit o mesmo `IN_CAR.pdf` já
ingerido em abril, com outro nome. **Não há divergência e não há decisão a
tomar** — é duplicata pura.

### 2. Resolução CONAMA 369/2006 — mesma norma, fontes diferentes ⚠ *pendência humana*

| | corpus (id=25) | pacote |
|---|---|---|
| chars do texto extraído | 26.570 | 28.982 |
| fonte | CETESB (`licenciamento.cetesb.sp.gov.br`) | SIAM/SEMAD-MG (`siam.mg.gov.br/sla`) |
| SHA-256 do texto | `11c8f0e09647952f…` | `fd81337b61631080…` |

Similaridade **0,94**. Divergência de hash com mesmo identificador — o caso que
o despacho manda listar como pendência de decisão humana.

Aberta a diferença, ela **não é normativa**: as duas versões trazem o corpo
íntegro da resolução (Art. 1 a 18, assinatura da Marina Silva). Os ~2,4 mil
chars a mais da versão SIAM são o aparato de notas de rodapé que o SIAM anexa,
citando normas correlatas:

```
[6] A Lei nº 6.938, de 31 de agosto de 1981. (Publicação - Diário Oficial da União - 02/09/1981)
Dispõe sobre a Política Nacional do Meio Ambiente… O Decreto nº 3.179, de 21 de setembro de
1999… Este foi revogado pelo decreto nº 6.514, de 22 de julho de 2008.
```

**Recomendação:** manter o id=25 como está. A versão do corpus vem de espelho
oficial de órgão ambiental e não perde nada de normativo; e as normas citadas no
aparato do SIAM (Lei 6.938/1981, Decreto 3.179/1999, Decreto 6.514/2008) já estão
no corpus **com texto próprio**, o que é melhor que tê-las como menção de rodapé.
A decisão é do André — enquanto não vier, o registro fica como está.

---

## Divergências de nomenclatura no pacote

**`IN IBAMA 4-2024.pdf` não é a IN 4/2024.** O arquivo foi nomeado pelo **dia**
da assinatura (04/12/2024); o documento é a **IN IBAMA 24/2024** (controle
ambiental da importação de resíduos). Ingerido com o identificador correto, por
gate do despacho. Ingerir com o número do arquivo plantaria no corpus uma norma
que não existe — e o sistema cita norma em peça que a consultora assina.

Duas normas do pacote são **textos consolidados**, não a redação original — o que
muda o que se cita:

- **IN IBAMA 21/2014**: o rodapé declara não substituir os publicados no DOU de
  27/12/2014, 13/12/2016 **e** 20/12/2017 — ou seja, o PDF já incorpora as IN
  9/2016 e 13/2017 mencionadas na ementa do despacho.
- **IN IBAMA 21/2023**: traz alterações "publicada no DOU de 5 de janeiro de
  2026". É a versão atualizada, não a de junho/2023.

Ambas ficam registradas em `extra_metadata.nota_curadoria`.

---

## O que não veio no pacote

O `ANEXO ÚNICO` da **IN RFB 2.203/2024** não está na captura: a página da LEX
EDITORA o marca como *"(exclusivo para assinantes)"*. O que entra no corpus é o
corpo da IN (Art. 1 a 31) **sem o anexo**. Quem for citar o Anexo Único precisa
buscá-lo na fonte oficial.

---

## Passo seguinte

Gate do Passo 0 cumprido: 11 normas apuradas como novas, 2 puladas e
caracterizadas.

O que **não** está cumprido é o Passo −1 do ADENDO 02. Enquanto a remediação do
chunking não estiver na main e reindexada, essas 11 continuam fora do corpus.
O ocorrido está em `RELATORIO_INGESTAO_NORMATIVAS_FEDERAIS.md`.
