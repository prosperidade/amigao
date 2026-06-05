# ADR-015 — Entidade Matrícula (1 Imóvel : N Matrículas) e staging de campos extraídos

- **Status:** Aceita
- **Data:** 2026-06-04
- **Espec de origem:** Ficha 01 — Dicionário de Extração do Intake (espec FECHADA pela dupla fundadora)
- **Relacionada a:** Princípio 3 do manifesto (Cadastro/Diagnóstico/Coleta separados), Princípio 1 (a IA propõe, o humano decide e assina), ADR-012 (decisão contextual)

## Contexto

A Ficha 01 redefine a fundação do intake. Dois fatos do domínio que o modelo
atual (`Property` plana) não representava:

1. **Um imóvel rural pode ter N matrículas** contíguas sob o mesmo CAR. CAR,
   município e nome são do imóvel; número de matrícula, cartório/registro,
   código INCRA/SNCR, NIRF/CIB, georreferenciamento (SIGEF) e **área** são de
   cada matrícula. A área do imóvel é a SOMA das áreas das matrículas — um valor
   **derivado**, não digitado. No `Property.total_area_ha` plano isso se perdia.

2. **Campo extraído por agente não é base confirmada.** Extrator e Auditor leem
   documentos e propõem valores com confiança variável; alguns divergem entre
   fontes (transcrição vs fundo). Gravar isso direto na base apaga a distinção
   entre "o sistema acha" e "o consultor confirmou".

## Decisão

**1. Entidade `Matricula`** (`matriculas`), `1 Property : N Matricula`. A
`Property` ganha `matriculas` (relationship) e `area_total_matriculas()` (soma
derivada). `total_area_ha` é mantido por compatibilidade — a transição completa
fica para fase posterior.

**2. Tabela de staging `ExtractedFieldStaging`** (`extracted_field_staging`):
agentes escrevem campos extraídos AQUI, nunca na base. Cada campo carrega
`confidence` + `status` (enum `extractedfieldstatus`: `pendente`, `consistente`,
`divergente_transcricao`, `divergente_fundo`, `aceito`, `rejeitado`),
`target_entity`/`target_field` (destino na base), `matricula_hint` (a qual
matrícula o campo se refere, quando identificável) e rastreabilidade
(`created_by_agent`, `ai_job_id`). A base só é gravada na **confirmação do
consultor** (fase 4). Princípio: "agentes propõem (staging), consultor decide
(Alertas), sistema grava (base)".

**3. Campo extraído ≠ derivado no schema.** Extraído carrega confiança +
validação (`ExtractedFieldStaging`); derivado carrega rastreabilidade de qual
agente o produziu e com base em quê.

## Faseamento

Esta ADR cobre a **FASE 1: só o schema**. O comportamento de extrator/auditor
NÃO muda — nada escreve no staging ainda. Fases seguintes (fora desta ADR):

- **Fase 2:** extrator passa a escrever no staging; avaliar migração de dados
  existentes de `Property` para `Matricula`.
- **Fase 3:** auditor faz reconciliação multi-fonte (inclui cruzar
  `proprietarios` da matrícula × Cliente) e marca divergências.
- **Fase 4:** tela de Alertas/consolidação — o consultor decide e o sistema
  grava na base (Cliente/Imóvel/Matrícula).

## Consequências

**Positivas**
- Representa o imóvel real (multi-matrícula) e torna a área do imóvel um valor
  derivado e auditável, não um número digitado solto.
- Materializa o Princípio 1 no schema: proposta de agente (staging) e base
  confirmada são entidades distintas, com a decisão do consultor rastreável.
- Instalação incremental e reversível: FASE 1 não altera fluxo nenhum; a
  migration sobe/desce limpa.

**Custos / dívidas**
- Coexistência temporária de `Property.total_area_ha` (legado) com a soma das
  matrículas até a fase 2 decidir a transição.
- O `cascade_delete` de imóvel ainda não conhece `matriculas`; mitigado por
  `ON DELETE CASCADE` no FK `matriculas.property_id` (limpeza no nível do banco).

## Validação (FASE 1)

- Migration `a1f2c3d4e5f6` testada upgrade → downgrade → upgrade limpos.
- `Property.area_total_matriculas()` valida o caso real da Ficha: matrículas
  4.698 (660,6561 ha) + 6.776 (349,9022 ha) = **1.010,5583 ha**.
- Endpoints de leitura/criação respondendo (`GET`/`POST
  /properties/{id}/matriculas`, `GET /processes/{id}/staging-fields`).

Detalhe de implementação e evidências: `docs/trabalhos/ficha01_fase1.md`.
