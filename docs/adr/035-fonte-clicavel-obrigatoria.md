# ADR-035 — Fonte obrigatória e clicável: acerto sem fonte visível é indistinguível de alucinação

- **Status:** aceita
- **Data:** 2026-07-26
- **Branch:** `fix/validacao-26-07`
- **Origem:** investigação da GO-NOT-2024-001985 (caso 15)
- **Correlata:** Princípio 11 ("nenhuma afirmação sem fonte"), ADR-033, ADR-034

## Contexto

A Análise Legal do caso 15 citou a "Notificação GO-NOT-2024-001985". A consultora
não reconheceu o número e levantou a suspeita mais grave possível: vazamento
entre casos ou alucinação.

A investigação varreu **toda** coluna de texto do schema:

| onde | ocorrências de `001985` |
|---|---|
| `documents.extracted_text` (43 docs do caso, 384.615 chars) | 0 |
| `documents.extracted_text` (base inteira, todos os casos) | 0 |
| `knowledge_catalog` / `legislation_documents` (corpus RAG) | 0 |
| `prompt_templates` + repositório inteiro | 0 |
| **`processes.description` + `intake_drafts.form_data`** | **1 + 1** |
| `ai_jobs.raw_output` | 6 — todos com `entity_id = 15` |

**O sistema estava certo.** O número veio do relato digitado na entrada do caso,
15 minutos antes do primeiro job. Não houve vazamento nem invenção.

E, ainda assim, o episódio custou uma auditoria completa. Porque a tela exibia a
citação com exatamente o mesmo peso visual de um dado extraído de documento, sem
dizer de onde vinha. **Do ponto de vista de quem lê, "certo sem fonte visível" e
"inventado" são o mesmo pixel.** A confiança não se perde quando o sistema erra;
perde-se quando o sistema não consegue mostrar por que acertou.

## Decisão

**1. Toda menção a ato administrativo ou norma exibe sua fonte, clicável.**
Componente único: `frontend/src/components/FonteChip.tsx`.

| tipo de fonte | comportamento do clique |
|---|---|
| `documento` | abre o PDF do caso (link assinado do storage), com página quando conhecida |
| `legislacao` | expande o texto da norma, **ao pé da letra**, do corpus |
| `atendimento` | não é link: exibe *"relato do cliente — não conferido em documento"* |
| `sem_fonte` | não é link: exibe *"sem fonte identificada — confira antes de usar"*, em âmbar |

**2. `sem_fonte` nunca é escondido atrás de um chip bonito.** É a informação mais
importante da lista: significa que o sistema declara não saber de onde tirou
aquilo. Tem tratamento visual de alerta, não de metadado.

**3. Relato do cliente é fonte legítima — com o alcance declarado.** Não se
descarta o que a consultora digitou no intake; marca-se como o que é. A
GO-NOT-2024-001985 é um passivo real do caso e deve continuar aparecendo. O que
faltava era o rótulo.

**4. Regra permanente:** nenhum PR que exiba afirmação de agente na tela mergeia
sem a fonte correspondente renderizada por `FonteChip`. Fonte que não se confere
com um clique não conta como rastreabilidade — conta como promessa.

## Consequências

- `DiagnosisTab` e `AgentResultRenderer` passaram a renderizar `FonteChip` no
  lugar do texto estático "Fonte: …" (que não abria nada).
- A biblioteca qualificada da ADR-033 nasce já dentro desta regra: cada norma sai
  com trecho literal + fonte clicável + data de conferência de vigência.
- Débito conhecido: `SourceRef.pagina` existe no contrato de UI mas os extratores
  ainda não populam página. Registrado no `REGISTRO_DIVIDAS.md`.

## Alternativas descartadas

- **Tooltip com a fonte.** Tooltip é lido por quem já desconfia. A queixa nasce
  justamente de quem *não* desconfiou a tempo.
- **Bloquear afirmação sem fonte.** Silenciaria informação verdadeira (o relato).
  A resposta certa é rotular, não suprimir.
