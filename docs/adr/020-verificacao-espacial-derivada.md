# ADR-020 — Verificação espacial é DERIVADA na leitura, não armazenada

**Status:** Aceita (André, 2026-06-30)
**Contexto relacionado:** Princípio 11 (nenhuma afirmação sem fonte; estado
derivado calcula-se na leitura), ADR-012 (achado perene no imóvel), gap D1
(parser shapefile/KML + `Property.geom`).

## Contexto

O auditor documental (`auditor_imovel` / `property_audit.audit_property`) emitia,
a cada execução, um `RegulatoryIssue` informativo `VERIFICACAO_ESPACIAL_PENDENTE`
quando `Property.geom IS NULL` (placeholder "a análise espacial não pôde rodar").

Como o auditor re-roda a cada E2/E4 e **não havia idempotência** (nem guard
app-level, nem UNIQUE no banco), o mesmo placeholder **acumulou 11 linhas
idênticas** no caso 13 (property #10, ids 18–28) ao longo de ~2 semanas — poluindo
a Visão geral com "achados" vagos, não-acionáveis, que pediam uma decisão sem
resposta sensata ("confirme ou descarte" algo que não é achado).

Diagnóstico read-only completo: o alerta não é um achado sobre o imóvel — é
**ausência de cobertura de análise** (não há geometria para cruzar). Estado
derivado de um fato (`geom IS NULL`), não um fato novo.

## Decisão

**A verificação espacial pendente é DERIVADA na leitura, nunca armazenada.**

- O auditor **deixa de emitir** `VERIFICACAO_ESPACIAL_PENDENTE` como
  `RegulatoryIssue` (removido o ramo `geom is None` em `property_audit.py`).
- A nota passa a ser **derivada na leitura** pelo backend:
  `GET /properties/{id}/diagnosis-notes` devolve, quando `geom IS NULL`, uma
  **nota não-acionável** `{codigo, titulo, texto, severity=informativo,
  source="derived", acionavel=false}`. Não há linha em `regulatory_issues`.
- A UI (Visão geral / `DiagnosisTab`) separa **achados** (acionáveis →
  `AlertaCard` completo) de **notas** (linha discreta, sem selects de status,
  sem decisão, sem "→ Ações").
- O código `VERIFICACAO_ESPACIAL_PENDENTE` é **aposentado** no catálogo
  (`regulatory_catalog_seed.py`) — mantido só para a FK de linhas legadas até a
  limpeza retroativa; nada mais o emite.

Mesmo padrão já usado para RL "averbada" derivada de averbação na matrícula e APP
exibida como "—" quando só há texto livre (Princípio 11).

## Gatilho de reversão parcial (D1)

Quando o parser de shapefile/KML (gap D1) popular `Property.geom`, a seção 4 de
`audit_property` passa a emitir **achados ESPACIAIS REAIS** (overlay PostGIS: CAR
× APP, sobreposição com UC/terceiros), aí sim **persistidos** como achados com
códigos próprios. A nota derivada some naturalmente (geom deixa de ser NULL).

## Consequências

- **Positivas:** zero acúmulo de placeholders; a Visão geral só mostra achados
  reais + notas discretas; não pede decisão irresolvível; sem dívida de
  idempotência para um estado que nunca deveria ser linha.
- **Limpeza retroativa:** as 11 (e quaisquer outras propriedades afetadas pelo
  mesmo ramo) são apagadas **após o deploy** desta mudança (ordem obrigatória —
  limpar antes faria o auditor recriar no próximo E2/E4). Tipo aposentado →
  DELETE total do código, com dry-run aprovado antes.
- **Follow-up (NÃO neste PR):** a UNIQUE constraint que fecharia o padrão
  recorrente "dedupe sem constraint" (3ª vez) fica registrada no
  `REGISTRO_DIVIDAS.md` — exige desenho de chave estável + varredura table-wide.
