# Skills procedurais — Sprint A1 (Forma B)

Cada agente pode ter skills procedurais que descrevem **como** executar uma tarefa específica de domínio. As skills moram em filesystem versionado, são descobertas em boot e injetadas no system prompt do agente quando o contexto da execução der match.

## Convenção de pasta

```
app/skills/
  _registry.py            # discoverer + loader + cache
  README.md               # este arquivo
  <agente>/               # ex.: redator, extrator, diagnostico
    <skill>/              # nome curto da skill
      SKILL.md            # manifesto + corpo procedural
```

## Formato do `SKILL.md`

Front-matter YAML obrigatório + corpo markdown.

```markdown
---
name: redator/oficio_semad
agent: redator
version: "0.1.0"
description: "Ofício formal para SEMA/SEMAD estaduais."
applies_to:
  demand_types: ["car", "retificacao_car"]
  doc_types: []
---

# Conteúdo procedural aqui (corpo markdown).
```

### Campos do front-matter

| Campo | Obrigatório | Descrição |
|---|---|---|
| `name` | sim | Identificador único — convenção: `<agente>/<nome_skill>` |
| `agent` | sim | Nome do agente (`redator`, `extrator`, etc.) — confere com `BaseAgent.name` |
| `version` | sim | SemVer livre (não enforced; útil para auditoria) |
| `description` | sim | 1 frase — usada em logs e listagem |
| `applies_to` | não | Mapping de chaves de matching: `demand_types`, `doc_types`, etc. Lista vazia = "não restringe" |

### Regras de matching

`applies_to` usa chaves plurais (`demand_types`, `doc_types`, etc.). Na hora do match, o registry compara o **singular** correspondente em `ctx.metadata` (`demand_type`, `doc_type`).

- Se a lista em `applies_to.<chave>` for vazia/ausente, a chave não restringe.
- Se a lista tiver valores e `ctx.metadata.<chave_singular>` não estiver entre eles, a skill **não** é aplicada.
- Múltiplas chaves são **conjuntivas** (todas precisam casar).

## Skills `_template`

Cada agente tem uma `_template/SKILL.md` que serve apenas como placeholder técnico para validar o pipeline. Não usar em produção (o `applies_to.demand_types: ["template"]` garante que ela só aparece quando `metadata.demand_type == "template"`).

## Adoção pelos agentes

`BaseAgent.call_llm()` injeta automaticamente as skills aplicáveis no `system` prompt, dentro do bloco:

```
<system prompt original>
<!-- skills:start -->
=== Skill: <name> v<version> ===
<corpo da skill 1>

=== Skill: <name> v<version> ===
<corpo da skill 2>
<!-- skills:end -->
```

Agentes não precisam mudar nada — basta que o contexto (`ctx.metadata`) carregue `demand_type`, `doc_type`, etc.

## Como adicionar uma skill nova

1. Crie a pasta `app/skills/<agente>/<skill>/`.
2. Crie `SKILL.md` com front-matter + corpo.
3. Em modo dev, o cache invalida por mtime — a skill aparece na próxima execução do agente.
4. Em produção, restart é necessário (cada worker carrega o próprio cache).

## Próximas sprints

- **Sprint A2** — adoção do `StageOutputContent` para formalizar a saída dos agentes.
- **Sprint A3** — skills de domínio reais (`oficio_semad.md`, `memorial_car.md`, `prad.md`, `car_sicar.md`, `matricula_generica.md`) chegam quando os PDFs-gabarito da sócia chegarem.
