# ADR-027 — Vigência de matrícula por última averbação + cadeia de fichas com confirmação humana

- **Status:** Aceita
- **Data:** 2026-07-18
- **Espec de origem:** Critério de domínio da Isis (forense do teste dela, 2026-07-18,
  verbatim): "vigente = matrícula da última averbação; a ficha anterior vira HISTÓRICO —
  não soma, não gera lacuna, permanece visível como linhagem".
- **Relacionada a:** ADR-015 (1 Imóvel : N Matrículas), ADR-017 (consolidação parcial),
  ADR-022 (selo/field_sources), ADR-023 (contiguidade / integridade), forense caso Isis
  (`deactivated_at`, `norm_compare`), Princípios 1 (IA propõe, humano decide) e 2 (tudo auditável)
- **Fecha:** dívida #60

## Contexto

O modelo tratava cada matrícula como registro independente. Quando um imóvel muda de
número por reabertura/desmembramento cartorial, a ficha ANTERIOR e a VIGENTE são a MESMA
terra em dois números — mas ambas, uma vez materializadas, somavam a área **em dobro**.

Evidência viva (processo 14, Fazenda São Jorge):
- **4655** (Fazenda Shangri-lá, proprietário/nome antigos) é a ficha anterior da **6776**
  (São Jorge, vigente) — mesma área 349,9022 ha.
- Lote 1B: **2609→2923→4698** (linhagem documentada; um CCIR de 2024 ainda cita a 2923).

A mitigação do forense (desativar matrícula rejeitada na Conferência, `deactivated_at`)
resolvia por **rejeição** — mas rejeição ≠ histórico: a ficha anterior é documento
**VÁLIDO** (a cadeia registral inteira importa), só **não vigente**. Rejeitar campo a
campo eram ~12 cliques por cadeia, e apagava a linhagem da vista.

## Decisão

**1. Vigência como dimensão própria do modelo, ORTOGONAL à desativação.**
`Matricula.vigencia` (`'vigente'|'historica'`, default `'vigente'` — backfill sem custo).
Só a **vigente** soma a área e gera lacunas/checklists; a **histórica** fica de fora da
soma sem ser apagada. É independente de `deactivated_at` (rejeição na Conferência):
uma ficha pode ser histórica sem nunca ter sido rejeitada. `Matricula.superseded_by_id`
(FK self, SET NULL) aponta a vigente que a substituiu — cadeia navegável
(2609→2923→4698). `Property.matriculas_vigentes()`/`matriculas_historicas()` derivam a
soma e a linhagem; `area_total_matriculas` e `nota_soma_matriculas` passam a contar só
vigentes. Migration `c7d3e1a9f0b2` (encadeada no forense `fa9c1d3b5e70`).

**2. Sinais de cadeia extraídos, com fonte.** A certidão ganha `registro_anterior` (o
registro de origem citado: "R-01 Mat. 2.923" → "2.923") e `denominacao_anterior`
(nome antigo) — este último deixa de colidir com `denominacao_imovel` (tinha coluna
compartilhada, poluindo a denominação atual). Ambos entram no staging como todo campo
(fonte/página) e no allowlist gravável da consolidação.

**3. Detecção PROPÕE, nunca aplica (Princípio 1).** `matricula_chain.detect_chain_proposals`
compara as matrículas VIGENTES do imóvel por 3 sinais em ordem de força:
(a) `registro_anterior` da vigente == número da anterior (alta; dá a direção — quem
cita é a mais nova); (b) `denominacao_anterior` casa (norm_compare da skill da Isis) +
área ≈ igual (média); (c) mesmo lote/gleba (token da denominação) + área idêntica,
direção pelo maior número (cartório emite crescente) (baixa). Match ⇒ **proposta**,
nunca marcação automática silenciosa.

**4. Curadoria de 1 clique.** A Conferência exibe as cadeias **pré-marcadas**
("2.923 é ficha anterior de 4.698 — confirmar?"). Um clique confirma a cadeia inteira
(`POST /processes/{id}/chain-proposals/aplicar`), marcando cada anterior como histórica
encadeada à vigente — substitui as N rejeições campo-a-campo. Recusa (desmarcar) mantém
ambas vigentes (caso raro; o consultor manda). Idempotente, auditado (hash chain).

**5. Reversível em Dados.** `PATCH /properties/{pid}/matriculas/{mid}/vigencia` devolve
uma histórica a vigente (volta a somar) ou marca manualmente. A aba Dados lista as
vigentes primeiro (com a soma) e as históricas numa seção discreta "Linhagem / fichas
anteriores" ("Ficha anterior de {nº}", não soma), com botão Reverter.

**6. Histórica não gera lacuna.** `MISSING_MATRICULA` e a lacuna de contiguidade contam
só vigentes: uma linhagem 4655→6776 é 1 matrícula vigente, não dispara contiguidade
(não é um segundo imóvel), e os documentos da histórica permanecem vinculados.

## Consequências

**Positivas**
- A soma para de dobrar por cadeia; o caso da Isis (processo 14) fica correto:
  4698 (660,6561) + 6776 (349,9022) = **1.010,5583 ha**.
- 1 clique onde antes eram 12 rejeições; a linhagem fica visível (não some), navegável.
- Rejeição e histórico deixam de se confundir — cada um com sua semântica e seu caminho.

**Custos / riscos residuais**
- A detecção é heurística: o sinal (c) (lote/gleba + área) é o mais fraco e só propõe
  com direção confiável (números comparáveis) — nunca aplica sozinho, então um falso
  positivo custa no máximo um desmarque do consultor.
- `registro_anterior` depende da extração do LLM achar a citação na certidão; quando não
  achar, a cadeia (a) não dispara — os sinais (b)/(c) e o cadastro manual cobrem o resto.
- A cadeia é modelada por par (superseded_by_id); grupos de contiguidade (matrículas
  distintas do mesmo imóvel vigente) seguem sendo a dívida #55, ortogonal a esta.

## Validação

- `tests/api/test_matricula_chain_vigencia.py` (13 casos): extração com coluna própria,
  3 sinais de detecção, soma da histórica fora (660,6561 não 1.321), caso completo da
  Isis (1.010,5583), recusa mantém ambas, reversão restaura, idempotência, histórica sem
  MISSING_MATRICULA/contiguidade, endpoints (proposta/1-clique/reversão), validações
  (422/404/401).
- Migration `c7d3e1a9f0b2` up→down→up limpa (FK SET NULL, default 'vigente').
- Suíte completa: **1186 passed**, cobertura 71,48%. `tsc` verde.
