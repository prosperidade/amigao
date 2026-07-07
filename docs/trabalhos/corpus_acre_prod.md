# Corpus legislativo do Acre — pendência de ingestão em prod

**Status:** ingerido em DEV (PR #95, 04/07 — 11 docs, 4.658 chunks); **NUNCA rodado
em produção** (Supabase `diquycxxkfrjhxtrcmzb`). Confirmado no item 0 da Fase 1
(06/07): `knowledge_catalog` em prod tem 24.233 linhas (GO/MS/MT/Federal), **zero
com `uf='AC'`** — mesmo padrão já visto na dívida #47 (corpus SEMAD/estadual
ausente em prod).

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
