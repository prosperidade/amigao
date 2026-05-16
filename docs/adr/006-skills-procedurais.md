# ADR-006 · Skills procedurais como conhecimento de domínio dos agentes

**Status:** Aceito
**Data:** 2026-05-08 (Sprint A1); formalizada como ADR em 2026-05-15
**Decisores:** sócia + tecnologia
**Relacionado:** [`./002-multi-llm-gateway.md`](./002-multi-llm-gateway.md), [`./005-pgvector-rag.md`](./005-pgvector-rag.md), [`./007-stage-output-content.md`](./007-stage-output-content.md)

---

## Contexto

Os primeiros smokes dos agentes IA (Sprints IA-1 a IA-4) mostraram comportamento consistente: **a IA escrevia texto correto, mas genérico**. Um ofício SEMAD-GO gerado pelo Redator era gramaticalmente impecável, juridicamente plausível, mas **não soava como ofício escrito por consultor ambiental experiente**.

A diferença não estava no modelo. Estava na ausência de **instrução procedural específica de domínio** — o que distingue PRAD bem feito de PRAD genérico, o que separa ofício que protocola sem retorno de ofício que retorna com exigência.

Três caminhos para incorporar esse conhecimento:

1. **Prompt template gigante** — colocar tudo dentro do system prompt em código Python
2. **Conhecimento no `knowledge_catalog`** — armazenar instruções no RAG semântico, recuperar por similaridade
3. **Skills procedurais em arquivos versionados** — Markdown no repositório, com frontmatter YAML declarando aplicabilidade

## Decisão

**Skills procedurais como arquivos Markdown versionados em `app/skills/<agente>/<dominio>.md`**, com frontmatter YAML.

Estrutura:

```markdown
---
name: oficio_semad_go
applies_to:
  - agent: redator
    demand_type: [car, retificacao_car]
    doc_type: oficio
    uf: GO
---

# Ofício SEMAD-GO

[corpo procedural com instruções de como escrever — não exemplos verbatim]
```

Carregamento automático:

- `BaseAgent.call_llm` consulta o registry de skills (`app/skills/registry.py`)
- Filtra skills cujo `applies_to` bate com `self.ctx.metadata` (agente, demand_type, doc_type, uf)
- Injeta skills matched dentro do system prompt entre marcadores `<!-- skills:start -->` e `<!-- skills:end -->`

## Por que esse formato (vs alternativas)

**Por que não prompt template gigante:**
- Não versionável de forma legível (diff de string Python escapada é ruim)
- Mistura código e conhecimento
- Mudança exige refactor de código + deploy
- Não permite override por tenant facilmente

**Por que não no `knowledge_catalog` (RAG):**
- Skill é **instrução procedural**, não **conhecimento factual**
- Recuperação por similaridade não tem sentido para "como escrever ofício" — você quer **a skill inteira aplicável**, não trechos com cosine maior
- `knowledge_catalog` é base curada de **fatos** (lei, ofício-modelo, manual); skills são **regras do agente**

**Por que Markdown versionado:**
- Sócia (não-técnica) pode revisar e editar diretamente
- Diff é legível em PR
- `applies_to` declara matching explícito (não probabilístico)
- Sem deploy para atualizar skill (depois de mecanismo de hot-reload — futuro)

## Distinção crítica: Skills vs Knowledge

Esse é o ponto mais sutil da decisão. Vale insistir:

| Aspecto | Skills | Knowledge Catalog |
|---|---|---|
| O que armazena | **Como** o agente trabalha (procedural) | **O que** existe na realidade (factual) |
| Exemplo | "Em ofício SEMAD-GO sempre cite Art. 26 da Lei 18.104/2013" | Texto integral do Art. 26 da Lei 18.104/2013 |
| Recuperação | Matching explícito por `applies_to` | Busca semântica por similaridade |
| Quem escreve | Especialista de domínio (sócia) | Curadoria + crawlers + ingestão |
| Frequência de mudança | Baixa (mês/trimestre) | Alta (legislação muda; nova jurisprudência) |
| Volume | Dezenas | Dezenas de milhares |
| Storage | Filesystem versionado | Postgres + pgvector |

Confundir os dois leva a sistema ruim. Skills no RAG fica desnecessariamente caro; legislação como skill fica impossível de manter.

## Hierarquia de skills (futura)

Mecanismo desenhado mas ainda não implementado:

- **Skills do repositório** (em `app/skills/`) — padrão da plataforma
- **Skills do tenant** (em coluna `Tenant.custom_skills` JSONB ou tabela `tenant_skills`) — override por tenant
- **Skills experimentais** (com tag `experimental` no frontmatter) — testes A/B

A capacidade está prevista no design; execução depende de demanda real (provavelmente quando primeiro tenant white-label entrar).

## Consequências

**Positivas:**
- **Conhecimento de domínio versionado** — mudança de skill é PR auditável
- **Não-técnico edita direto** — Markdown é universal
- **Matching explícito** — agente sabe exatamente quais skills carregar
- **Hot-reload no futuro** — não precisa rebuildar imagem Docker para atualizar
- **Marketplace possível** (janela 3 do roadmap) — skills viram patrimônio do produto e podem aceitar contribuição curada de consultorias parceiras

**Negativas:**
- **Risco de prompt gigante** — agente que carrega muitas skills pode ter system prompt enorme; controlar tamanho ou usar Gemini quando aplicável
- **Manutenção de matching** — adicionar novo eixo (ex: "applies_to por município") exige código

**Mitigações:**
- Limite implícito de skills por chamada (top-N por especificidade); auditar quando ganhar volume
- Estrutura `applies_to` flexível o suficiente — adicionar eixo é incremento, não refactor

## Estado real (gate aberto)

**Skills reais não existem ainda.** Hoje só há placeholders:

- `app/skills/redator/_template/SKILL.md`
- `app/skills/extrator/_template/SKILL.md`

Bloqueio aguardando **PDFs-gabarito da sócia** (reunião 16/05/2026 destrava). Skills priorizadas:

1. `redator/oficio_semad_go.md`
2. `redator/memorial_car_sicar.md`
3. `redator/resposta_notificacao_semad.md`
4. `redator/prad.md`
5. `extrator/matricula_generica.md`
6. `extrator/car_sicar.md`

Bloqueio mais antigo do projeto (23 dias desde 23/04). Destrava-se nesta semana.

## Status de execução

| Item | Estado |
|---|---|
| Estrutura `app/skills/<agente>/<dominio>.md` | ✅ Sprint A1 |
| Registry com `applies_to` matching | ✅ |
| `BaseAgent.call_llm` injetando skills no system prompt | ✅ |
| Templates `_template/SKILL.md` (placeholders) | ✅ |
| Skills reais escritas pela sócia | ❌ Aguardando 16/05 |
| Hot-reload de skills sem rebuild | ❌ Pendente |
| Skills por tenant | ❌ Capacidade desenhada, não implementada |
| Marketplace de skills | ❌ Janela 3 do roadmap |

## Relação com outros ADRs

- [`./002-multi-llm-gateway.md`](./002-multi-llm-gateway.md) — gateway carrega skills antes da chamada LLM
- [`./005-pgvector-rag.md`](./005-pgvector-rag.md) — RAG é o complemento factual; skills é o complemento procedural
- [`./007-stage-output-content.md`](./007-stage-output-content.md) — schema validado para a saída que a skill orienta
