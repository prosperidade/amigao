# ADR-017 — Consolidação parcial (divergente → ação) + ponte matrícula→imóvel (RL)

- **Status:** Aceita — **ponto 1 (concorrência simétrica de fontes) SUPERADO por ADR-062** (2026-08-25)
- **Data:** 2026-06-28
- **Validada por:** Isis (sócia, validadora de domínio) — decisão "opção b"; André (decisões técnicas 28/06)
- **Relacionada a:** Ficha 01 Fase 4 (decisão + consolidação), Ficha 07 (`Acao`), ADR-015 (matrícula/staging), ADR-016 (ação não resolve passivo), contrato de fontes #70, Princípio 11 ("nenhuma afirmação sem fonte"), Princípio 3 (camadas separadas)

> ⚑ **Superação parcial (ADR-062, 2026-08-25 — fonte única registral na E2):**
> o **ponto 1** deste ADR (divergência entre fontes ACEITAS no mesmo destino →
> devolve a `divergente_transcricao` → vira `Acao`) tratava matrícula, CCIR,
> SIGEF, ITR e CAR como concorrentes simétricos por um mesmo campo registral.
> Isso mudou: para os 7 campos de `target_entity=matricula` que descrevem o
> registro jurídico do imóvel (área, denominação, titular, INCRA/SNCR, NIRF,
> RL averbada, geo_certificação), **só a certidão de matrícula escreve** — as
> demais fontes não competem mais, e a divergência delas em relação à
> matrícula vira achado do diagnóstico (matriz de inconsistências →
> `RegulatoryIssue`), não mais `Acao` de consolidação. O mecanismo deste ADR
> (guard de conflito → `Acao`) **continua vigente** para o que sobrou: duas
> certidões de matrícula discordando entre si, e a concorrência não-registral
> em `target_entity=imovel` (CAR × ITR × RAT). O **ponto 2** (ponte RL
> matrícula→imóvel) não é afetado. Ver ADR-062 para o desenho completo.

## Contexto

A consolidação do staging na base real (Ficha 01 Fase 4) **nunca executou** em
produção (`audit_logs action='consolidar'` = 0). Causa medida: a UI desabilitava
o botão "Consolidar na base" quando havia **qualquer** campo
`divergente_transcricao` não resolvido — um único divergente prendia todos os
campos já aceitos.

Além disso, dois dados do imóvel chegavam só no nível da matrícula
(`averbacao_rl`/`averbacao_app`, texto livre) enquanto o Imóvel Hub lê do nível
imóvel (`prop.rl_status`, `prop.app_area_ha`), deixando "—".

Duas perguntas precisavam de decisão:

1. **Consolidar com divergente não resolvido bloqueia tudo, ou grava o que dá?**
2. **Como levar RL/APP da matrícula para o que o Hub lê, sem inventar valor?**

## Decisão

### 1. Consolidação PARCIAL — divergente vira ação (opção b)

A consolidação **não bloqueia** por divergência. Os campos `aceito` gravam; cada
campo ainda em `divergente_transcricao` no momento da consolidação **vira uma
`Acao`** (`origem=consolidacao`, `tipo_triagem=pendente`), com fonte (os valores
concorrentes e seus documentos — `SourceRef`, contrato #70). O valor do divergente
**não** é gravado na base. Idempotente por `dedupe_key` (re-consolidar não duplica).

`divergente_fundo` **não** entra nesse caminho: já é roteado como achado pela
matriz de inconsistências (Ficha 02) — não duplicamos como ação.

Coerente com a Ficha 07 ("divergência = escolher valor, digitar manual, ou criar
ação") e com o ADR-016 (a ação é trabalho rastreável; concluí-la não resolve o
dado/passivo).

### 2. Ponte matrícula→imóvel: derivar RL com fonte, nunca inventar APP

- `rl_status` entra na allowlist de gravação do imóvel (antes era descartado).
- Quando o imóvel não tem RL e ≥1 matrícula tem `averbacao_rl`, deriva-se
  `prop.rl_status = "averbada"` marcando `field_sources['rl_status'] =
  "derived_matricula"` — origem **derivada** explícita (não `human_validated`),
  transparente e corrigível pelo consultor.
- **APP não é derivada de texto livre.** `prop.app_area_ha` é numérico;
  `averbacao_app` é texto. Extrair um número de texto livre seria **inventar**
  (viola o Princípio 11). `app_area_ha` só é populado por dado estruturado no
  nível imóvel (`app_declarada_ha → app_area_ha`). Sem isso, o Hub mostra "—" —
  e isso é **correto**, não um bug.

## Consequências

**Positivas**
- A consolidação passa a executar (item zero do MVP destravado): consistentes
  gravam mesmo com divergências pendentes.
- Nenhuma divergência se perde: cada uma vira trabalho rastreável com fonte.
- RL aparece no Hub; a proveniência derivada é auditável (`field_sources`).
- `action='consolidar'` passa a existir, com hash chain (Princípio 2).

**Custos / limites**
- Novo valor de enum `acao_origem` exige migration (`ALTER TYPE ADD VALUE`).
- A derivação de RL assume "averbação presente = averbada". É um default honesto
  e corrigível, não uma verdade absoluta — marcado como `derived_matricula`.
- APP permanece "—" quando só há texto de averbação. É uma decisão consciente
  (não inventar), não uma lacuna a "corrigir" depois com parsing.

## Alternativas descartadas

- **Reusar `AcaoOrigem.auditor`** para as ações da consolidação — descartado:
  misturaria proveniências em queries por origem. Optou-se por valor próprio.
- **Parsear `averbacao_app`/`averbacao_rl` (texto) em número/status** — descartado
  por violar o Princípio 11 (inventar dado a partir de texto não estruturado).
- **Manter o gate tudo-ou-nada** — descartado: era a causa-raiz do MVP travado.
