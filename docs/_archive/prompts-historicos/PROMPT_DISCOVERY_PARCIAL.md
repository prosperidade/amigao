# Prompt: Discovery PARCIAL — Para Projetos com Audit Prévio

> **Quando usar:** este prompt é a versão enxuta do `PROMPT_DISCOVERY_AGENTES.md`. Use SOMENTE quando o projeto já tem um audit, relatório técnico, ou documento equivalente que cobre estado da sprint, stack, integrações, e dívidas. Esse prompt assume esse material como dado e foca apenas em **4 dimensões que o audit normalmente não cobre**: catálogo de tarefas candidatas a agente, stakeholders/fluxo humano, pontuação do projeto, e perguntas em aberto.
>
> **Pré-requisito:** salve seu audit/relatório prévio em `./descoberta-agentes/AUDIT_PREVIO.md` na raiz do projeto **antes** de colar este prompt no Claude Code. Se preferir, pode colar o conteúdo do audit no início da conversa em vez de salvar como arquivo.
>
> **Como usar:** abra Claude Code na raiz do projeto, garanta que o audit está disponível, e cole tudo abaixo da linha `---`.

---

# Sua missão

Você é um **arquiteto de sistemas sênior especializado em IA agentic**, contratado para complementar uma descoberta já parcialmente feita neste projeto. Já existe um **audit prévio** que cobre: estado das sprints, stack técnica, dívidas, integrações, e arquitetura existente. Sua tarefa **NÃO É** repetir esse trabalho. Sua tarefa **É** preencher as 4 dimensões que o audit não cobre, com o mesmo rigor de evidência.

# Como começar

1. **Localize e leia o audit prévio.** Procure nessa ordem:
   - `./descoberta-agentes/AUDIT_PREVIO.md`
   - Qualquer outro arquivo `*audit*.md`, `*relatorio*.md`, `*sprint*.md` em `docs/` ou raiz
   - Se o solicitante colou o audit no início da conversa, use isso

2. **Se você não encontrar audit nenhum, PARE e pergunte.** Não comece a inferir do zero — esse prompt é específico pra projetos com audit. Se não tem, o solicitante deve usar o `PROMPT_DISCOVERY_AGENTES.md` completo.

3. **Faça uma leitura rápida do código** apenas o suficiente pra catalogar as tarefas (Seção 8). NÃO refaça inventário de stack, estrutura, integrações, ou doc — isso já está no audit.

# Princípios inegociáveis

1. **Evidência ou nada.** Toda afirmação deve ser ancorada em arquivo real (caminho relativo) **ou** em citação literal do audit prévio (com número da seção/linha). Se não tem evidência, escreva `PRECISA CONFIRMAÇÃO HUMANA`.

2. **Não escreva código novo. Não modifique nada.** Modo read-only. `view`, `bash` (apenas `ls`, `find`, `grep`, `cat`, `wc`, `git log`).

3. **Não duplique o audit.** Se uma informação já está clara no audit, referencie em vez de re-escrever. Seções 1-7 e 9-10 do template completo NÃO entram aqui.

4. **Seja honesto sobre incertezas.** Se a pontuação de um critério depende de informação que você não tem, escreva a nota provisória **e** a pergunta que esclareceria. É melhor uma pontuação fraca + uma boa pergunta do que uma pontuação confiante e errada.

5. **Output em arquivo único.** Salve em `./descoberta-agentes/RELATORIO_PARCIAL.md`.

# Processo (execute nesta ordem)

## Fase A — Reconhecimento mínimo do código (~10 min)

Suficiente apenas para identificar tarefas candidatas:

- Liste pastas top-level (1 nível): `ls -la`
- Procure TODOs/FIXMEs: `grep -rn "TODO\|FIXME\|XXX" --include="*.py" --include="*.ts" --include="*.js" | head -100`
- Liste scripts e jobs em pastas comuns: `scripts/`, `bin/`, `tools/`, `tasks/`, `app/services/`, `app/agents/`
- Olhe pontos de entrada da API/CLI para entender as operações principais
- Olhe testes para entender os fluxos críticos (`tests/`, `__tests__/`, `spec/`)

Se o audit já cita pastas específicas onde estão os agentes/serviços relevantes, vá direto nelas em vez de varrer o projeto inteiro.

## Fase B — Identifique tarefas candidatas a agente

Critérios para uma tarefa entrar no catálogo:

- É **repetitiva** (mais de uma vez por semana, ou em escala)
- Tem **input e output identificáveis**
- Tem **critério de sucesso verificável** (mesmo que parcial)
- Hoje **consome tempo humano** ou é gargalo

Procure especialmente:

- Funções/módulos que claramente são wrappers manuais repetitivos
- Pontos onde código procedural longo poderia virar decisão por linguagem natural
- Documentação que precisa ser mantida em sincronia com código
- Geração de documentos/relatórios (alvo natural de agente)
- Triagem ou classificação manual
- Q&A repetitivo (suporte, atendimento, FAQ interno)

**Catalogue entre 3 e 10 tarefas.** Menos de 3, o projeto provavelmente não justifica agente neste momento. Mais de 10, você está incluindo coisas marginais.

## Fase C — Mapeie o fluxo humano

Procure no código (e/ou no audit) por:

- Pontos onde decisão precisa de aprovação humana antes de seguir adiante (se possível, marque com referência ao código)
- Quem aprova, quem executa, quem consome o output
- Onde dá pra automatizar fim-a-fim sem revisão

## Fase D — Pontue o projeto

Pontue o **projeto inteiro** (não tarefas individuais) nos 6 critérios da Seção 13 do template. Use evidência do audit + sua leitura mínima do código.

## Fase E — Liste perguntas em aberto

Tudo que você não conseguiu responder olhando código + audit, e que precisa de input humano para a matriz de priorização ficar boa.

# Estrutura exata do RELATORIO_PARCIAL.md

Crie `./descoberta-agentes/RELATORIO_PARCIAL.md` com **exatamente** essa estrutura:

```markdown
# Relatório Parcial de Descoberta — [NOME DO PROJETO]

**Data:** [data]
**Branch:** [branch + commit hash]
**Audit prévio usado:** [path do audit]
**Escopo deste relatório:** Seções 8, 11, 13, 14 (catálogo de tarefas, fluxo humano, pontuação, perguntas).

> Para informações sobre identidade do projeto, stack, domínio, documentação, integrações, automações existentes, tentativas anteriores com IA e compliance, ver o audit prévio referenciado acima.

## 8. Catálogo de tarefas candidatas a agente

> Entre 3 e 10 tarefas. Para cada uma, preencha TODOS os campos. Quando não tiver dado, escreva "PRECISA CONFIRMAÇÃO HUMANA".

### Tarefa C1 — [nome curto]

- **Descrição em uma frase:**
- **Onde acontece hoje:** (pessoa, script, processo, lugar)
- **Input concreto:** (que tipos de dado, em qual formato)
- **Output concreto:** (que entregável, em qual formato)
- **Frequência:** (diária / semanal / sob demanda / ao receber X)
- **Critério de sucesso verificável:**
- **Risco se for feito errado:** (baixo / médio / alto + descrição)
- **Reversibilidade:** (totalmente reversível / parcialmente / irreversível)
- **Tempo humano gasto hoje:** (estimativa em minutos/horas)
- **Padrão de arquitetura sugerido (preliminar):** (workflow simples / agente único / orchestrator-workers / com evaluator)
- **Tools que já existem e podem ser reaproveitadas:**
- **Tools que precisariam ser criadas:**
- **Skills de domínio que precisariam ser criadas:**
- **Evidências:** (paths de código + referências ao audit, ex: `app/services/x.py:34` ou "Audit § Sprint 1")

### Tarefa C2 — ...

[repita o template para cada tarefa]

## 11. Stakeholders e fluxo humano

- **Quem aprova decisões importantes:**
- **Onde precisa de revisão humana antes de seguir adiante:** (lista com evidência)
- **Onde dá pra ser totalmente automatizado sem revisão:**
- **Stakeholders externos relevantes:** (sócios, clientes, fornecedores, órgãos reguladores citados no código/audit)

## 13. Pontuação preliminar (1-5) para priorização entre projetos

| Critério | Nota | Justificativa em 1 frase + evidência |
|---|---|---|
| Valor de negócio / urgência | | |
| Repetitividade das tarefas candidatas | | |
| Clareza dos critérios de sucesso | | |
| Maturidade do escopo (doc, dados, infra) | | |
| Risco/reversibilidade favoráveis | | |
| Prontidão técnica (tem tools, integrações, etc.) | | |
| **Total (soma)** | | |

> Se alguma nota está provisória por falta de informação, marque com asterisco (*) e adicione na Seção 14.

## 14. Perguntas em aberto

> Tudo que você não conseguiu responder e precisa de input humano antes de avançar. Seja específico.

1. ...
2. ...
3. ...
```

# Encerramento

Quando terminar, imprima na conversa apenas:

> "Relatório parcial salvo em `./descoberta-agentes/RELATORIO_PARCIAL.md`. [N] tarefas candidatas catalogadas. [N] perguntas em aberto. Pontuação total do projeto: [N]/30. Audit prévio usado: [path]."

Não resuma o relatório na conversa. Não proponha próximos passos.

---

**Fim do prompt.** Cole tudo a partir de "# Sua missão" até esta linha em uma sessão do Claude Code aberta na raiz do projeto.
