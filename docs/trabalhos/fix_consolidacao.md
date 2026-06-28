# FIX da Consolidação — gate destravado + consolidação parcial + ponte matrícula→imóvel

**Branch:** `fix/consolidacao-gate-divergente` (base `main`)
**Data:** 2026-06-28
**Decisão de domínio:** Isis (opção b) — consolidação parcial, divergente vira ação.
**Relacionado:** Ficha 01 Fase 4 (`ficha01_fase4.md`), Ficha 07 (`ficha07_acoes.md`),
ADR-016 (ação não resolve passivo), ADR-017 (esta entrega), Princípio 11 (fonte).

## Causa-raiz (já medida — não re-investigada)

A consolidação do staging na base real **nunca executou** em produção:
`audit_logs action='consolidar'` = 0; 0 matrículas criadas. O endpoint
`POST /processes/{id}/consolidar` e o serviço `consolidate_process` estavam
**corretos e plugados** — só nunca foram invocados.

O bloqueio estava na UI: `ConsolidacaoPanel.tsx` desabilitava o botão "Consolidar
na base" com `disabled = consolidate.isPending || pendentesObrig > 0`, e
`pendentesObrig` conta campos `divergente_transcricao`. **UM** campo divergente
desabilitava o botão inteiro e prendia os outros 27 campos já aceitos.

## Decisão de produto (Isis, opção b)

Ao consolidar com divergente não resolvido: os campos consistentes **gravam**
(consolidação PARCIAL, não bloqueia) e cada divergente não resolvido **vira uma
Ação/pendência** automática (rastreável, com fonte). Alinhado à Ficha 07
("divergência = escolher valor, digitar manual, ou criar ação").

## O que mudou

### 1. Gate destravado (`ConsolidacaoPanel.tsx`)
- `disabled = consolidate.isPending || consolidaveis === 0` (`consolidaveis` =
  campos `status='aceito'`). `pendentesObrig` não bloqueia mais.
- Texto de apoio: "N campo(s) serão gravados · M divergência(s) virarão ações a
  resolver".
- Mensagem de sucesso e histórico de eventos mencionam as ações criadas.

### 2. Consolidação parcial (`staging_consolidation.py` + `acao_generator.py`)
- Após gravar os aceitos, `generate_acoes_from_divergencias` cria **uma `Acao`**
  por campo ainda em `divergente_transcricao` (agrupado por
  `(entidade, hint, campo)`), `origem=AcaoOrigem.consolidacao`, com `origem_fontes`
  = um `SourceRef` por valor concorrente (doc + valor). **Não grava o valor do
  divergente.** `divergente_fundo` tem caminho próprio (achado roteado pela
  matriz) — **não** vira ação aqui.
- **Idempotente** por `dedupe_key = p{process_id}:divg:{sha1(entity|hint|field)}`:
  re-consolidar não duplica gravação nem ação.

### 3. Ponte matrícula→imóvel — RL (Princípio 11)
- `rl_status` entrou na allowlist `_IMOVEL_FIELDS` (antes, `rl_declarada_ha →
  imovel.rl_status` caía em `ignorados` → Hub mostrava "—").
- Se `prop.rl_status` está vazio e ≥1 matrícula tem `averbacao_rl`, deriva-se
  `rl_status='averbada'` marcando `field_sources['rl_status']='derived_matricula'`
  (transparente; consultor corrige). **APP não** é derivada de texto livre:
  `app_area_ha` (Float) nunca é extraído de `averbacao_app` (texto). Se o caso só
  tem APP como texto, o Hub fica "—" — proposital (não inventar).

### 4. Audit
- `_audit` da consolidação passou a encadear hash SHA-256 (`stamp_audit_hash`,
  Princípio 2). O registro `action='consolidar'` dispara quando há **gravação ou
  ação criada** e inclui `acoes_criadas`/lista.

### 5. Origem `consolidacao` (enum + migration)
- `AcaoOrigem.consolidacao` novo valor; migration `c8d4e1a2f9b0` faz
  `ALTER TYPE acao_origem ADD VALUE IF NOT EXISTS 'consolidacao'` em
  `autocommit_block` (Postgres); SQLite/testes usam VARCHAR.

## Validação

- `pytest tests/api/test_fase4_consolidacao.py` — **9 verdes** (6 antigos + 3
  novos): consolidação parcial (divergente→ação, audit>0, idempotente), ponte RL
  matrícula→imóvel, `rl_status` nível-imóvel via allowlist.
- `tests/api/test_acoes.py` + `test_property_hub_derivacao.py` — 11 verdes (sem
  regressão).
- `tsc --noEmit` + `npm run build` verdes.
- Migration provada em Postgres real (dev): `downgrade -1` → `upgrade head`
  (exercita o `ALTER TYPE`) exit 0.

### Aceite pós-deploy (process 13 real — manual)
- Consolidar o process 13 → 27 campos aceitos gravam (Matrícula criada, Property
  populada); campo 452 (divergente, denominação 4698) vira **Ação** (não bloqueia).
- Imóvel Hub: Matrícula, Área, RL aparecem (fim do "—"; APP só se houver dado
  estruturado nível-imóvel).
- `audit_logs action='consolidar' > 0`. Re-consolidar: idempotente.

## Fora de escopo / proibido
- Não bloquear consolidação por divergente. Não gravar valor de divergente não
  resolvido. Não inventar `app_area_ha`/`rl_status` de texto livre.
- `client-portal/` e `mobile/` congelados (ADR-009) — não tocados.
