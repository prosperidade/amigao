# Corpus legislativo do Acre — ingestão em prod

**Status: ✅ EXECUTADO EM PROD em 2026-07-13.** `knowledge_catalog` em prod foi de
24.233 → 28.891 chunks (+4.658, idêntico ao dev): `uf='AC'` = 4.634 e a referência
nacional (`CPI-LEG-CONSULTADA-OE-2025`, `uf=NULL`) = +24 no bucket federal (761→785).
11 `LegislationDocument` novos (ids 54–64). Dívida #47 (fatia Acre) fechada em prod.

Histórico: ingerido em DEV (PR #95, 04/07 — 11 docs, 4.658 chunks). O item 0 da Fase 1
(06/07) confirmou que prod tinha **zero `uf='AC'`** — mesmo padrão da dívida #47 (corpus
SEMAD/estadual ausente em prod). O PR #102 preparou os scripts; a execução real foi
2026-07-13.

## Dois gotchas encontrados na execução real (corrigidos)

1. **`reindex_legislation_by_uf.py --uf AC` NÃO indexa a referência nacional** (`uf=NULL`) —
   o filtro é `LegislationDocument.uf == args.uf`. O doc nacional (id 64) foi indexado à
   parte via `index_legislation_document(db, 64)` (24 chunks, bucket federal). Sem isso o
   corpus fica 24 chunks curto (4.634 em vez de 4.658).
2. **`reindex_legislation_by_uf.py` não tinha `sys.path.insert`** — rodado como
   `python scripts/reindex_legislation_by_uf.py` dava `ModuleNotFoundError: No module named
   'app'`. Corrigido nesta mesma branch (mesmo padrão de `sanear_staging.py`). O passo 2 foi
   rodado com `PYTHONPATH=.` como workaround antes do fix.

> **Observação de performance:** o passo 2 (embed de ~4.658 chunks via OpenAI) leva
> ~15 min. Rodar em background / sessão que aguente o tempo. É idempotente (dedup por
> `content_hash` ANTES do embed), então re-rodar retoma sem re-embedar o que já entrou.

Não confundir com a dívida #58 (N7 ausente) — essa é outra coisa e já está
fechada; o André confirmou que a N7 não vai vir e decidiu não reprocessar. O
corpus AC (sem a N7) está completo e pronto — só falta rodar contra prod.

## Runbook (2 passos, idempotentes)

Requer `DATABASE_URL` (prod) + `OPENAI_API_KEY` no ambiente. Pasta fonte:
`Legislações Regente/` (na raiz do repo, já presente, `.gitignore`d).

```bash
# 1. Cria os LegislationDocument (11 docs; pula N11 duplicado e LEG_RURAL) —
#    dry-run primeiro pra conferir antes de gravar.
python scripts/ingest_legislacao_acre.py --pasta "Legislações Regente" --dry-run
python scripts/ingest_legislacao_acre.py --pasta "Legislações Regente"

# 2. Chunk + embedding (OpenAI text-embedding-3-small 768d) no knowledge_catalog.
#    Síncrono (não depende de worker Celery consumindo fila) — script novo
#    scripts/reindex_legislation_by_uf.py, criado para esta rodada.
python scripts/reindex_legislation_by_uf.py --uf AC
```

**Pós-check esperado** (mesma query do item 0):
```sql
SELECT uf, source_type, count(*) FROM knowledge_catalog
WHERE uf = 'AC' GROUP BY uf, source_type;
```
Deve aparecer `AC | compendio_regente | ~4.658` (mais a referência nacional
`LEG-Consultada-OE-2025`, uf=NULL).

## Por que não rodei direto

Não tenho `DATABASE_URL`/`OPENAI_API_KEY` de produção neste ambiente — só o
`.env` de dev (`127.0.0.1:55432`). Rodar contra prod exige esses dois valores
(reais, não os placeholders de `.env.production.example`). Pedido ao André no
mesmo turno em que este documento foi criado.
