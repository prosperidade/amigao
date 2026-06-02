# Trabalho — Extrator truncava o texto em 3000 chars

> Arquivo único de trabalho. Problema → causa → fix → validação → status.
> Branch: `fix/extrator-truncamento` (base `main`). Data: 2026-06-02.

## Problema (provado rodando)

Com o OCR multipágina corrigido, o doc 118 (escritura Romilton, 6 págs) passou a
ter `extracted_text` com **~20.8k chars** — área 58,7654 ha, município Uirapuru,
denominação LOTE 32, comarca/cartório, tudo presente. Mas o **extrator** devolvia
só `proprietario_nome` e `proprietario_cpf_cnpj`; os 9 campos de imóvel vinham
`None`.

## Causa raiz (linha exata)

`app/services/document_extractor.py:183`:

```python
prompt = prompt_template.replace("{text}", text[:3000])
```

O extrator só olhava os **primeiros 3.000 chars**. A página 1 do PDF é uma
certidão CNIB (nome + CPF) — por isso só esses 2 campos saíam. Os campos do
imóvel estão **depois** do char 3.000 (escritura + matrícula + memorial), fora da
janela. Truncamento.

## O que mudou

| Arquivo | Mudança |
|---|---|
| `app/core/config.py` | `+ EXTRACTOR_MAX_CHARS: int = 30_000` (configurável). 30k chars ≈ 7,5k tokens no gpt-4o-mini — folgado nos 128k de contexto e cobre escrituras reais (15-25k). |
| `app/services/document_extractor.py` | `text[:3000]` → `text[:settings.EXTRACTOR_MAX_CHARS]`. Prompt da `matricula` reescrito: avisa que o doc tem VÁRIAS SEÇÕES (certidão na capa + escritura + matrícula + memorial) e que os campos do imóvel não estão na capa — procurar em TODO o texto. |

Escopo respeitado: **não** mexi em OCR, chain, diagnóstico, nem criei skill (o
extrator não usa skill procedural — fica como dívida #45). O `cpf_cnpj`/RG usa
outro prompt (default), intocado.

## Validação (rodando — texto real do doc 118, ~20.8k chars)

`extract_document_fields(text=<escritura>, doc_type='matricula', save_job=False)`:

```
ANTES (text[:3000]):   área=None  matrícula=None  município=None  uf=None  denominação=None
DEPOIS (fix, inteiro): área=58.7654   município=UIRAPURU   uf=GO
                       denominação="LOTE 32, PA MÃE MARIA"   comarca=CRIXÁS
                       cartório="...REGISTRO DE IMÓVEIS CRIXÁS-GOIÁS"
                       proprietário="MANOEL SOARES DOS SANTOS"
```

7 campos passaram de `None` a preenchidos. As 3 checagens duras do aceite
(área/município/UF, não `None`) ✅.

**`numero_matricula` segue `None` — e está CORRETO.** A única "Matrícula nº 6253"
do documento aparece amarrada a **LOTE 31** e **LOTE 33** (os confrontantes); o
imóvel objeto é o **LOTE 32**, que no texto é referenciado por CIB (9.806.966-7),
CCIR/INCRA e memorial certificado — **sem matrícula própria** (lote de PA/
assentamento transferido por escritura). O modelo acertou ao não atribuir a
matrícula de um vizinho ao imóvel; forçar 6253 seria injetar valor errado.

**Regressão (doc simples):** RG/CPF sintético com `doc_type='cpf_cnpj'` extraiu os
5 campos (nome, cpf, data_nascimento, filiação, órgão expedidor) — sem regressão.

## Status

✅ Janela de texto elevada e configurável (`EXTRACTOR_MAX_CHARS=30000`).
✅ doc 118: área/município/UF/denominação/comarca/cartório/proprietário preenchidos (provado rodando).
✅ Doc simples não regride.
ℹ️ `numero_matricula=None` é correto p/ este doc (6253 é dos confrontantes; lote 32 sem matrícula própria).
⏳ Em prod: o extrator re-roda ao reprocessar o doc 118 (chain OCR→extrator) ou via `POST /processes/{id}/extract`.
