# Bloco 5 — Plano de Migração

**Documento:** Operação · execução única
**Para:** você (ou o agente com acesso ao repo) executar
**Tempo estimado:** 20-30 minutos
**Risco:** baixíssimo (tudo vai pra `_archive/`, nada é deletado de fato)

---

## Visão geral

Essa é a operação final da Onda 3. Não é mais escrever documentação — é **trocar o que está lá pelo que escrevemos**, preservando 100% do histórico em `docs/_archive/`.

Resultado final: pasta `docs/` limpa com **32 documentos novos** organizados em 5 camadas + `_archive/` com todo o histórico acessível.

## Pré-requisitos

1. Branch limpa (sem alterações pendentes não-commitadas)
2. Bloco 1-4 baixados e prontos para descompactar
3. Acesso ao repo no terminal

## Estratégia

**Tudo da `docs/` antiga vai pra `docs/_archive/`** (preserva histórico) — nada é deletado de fato. **Três exceções** permanecem vivas: `progressoIA.md`, `PROGRESSO_WAITLIST.md` e `descoberta-agentes/RELATORIO_PARCIAL.md`.

Depois, os 32 docs novos descompactam na estrutura limpa.

---

## Passo 1 — Backup

```bash
# Garanta que tudo está commitado
git status

# Se tem mudanças, commite antes
# git add . && git commit -m "WIP: antes da migração de docs"

# Crie uma tag de segurança
git tag pre-onda3-migration

# Confirme
git tag | grep pre-onda3
```

Se algo der errado, `git reset --hard pre-onda3-migration` recupera tudo.

---

## Passo 2 — Criar estrutura `_archive/`

```bash
mkdir -p docs/_archive/{fundacional-2026-03,auditoria-2026-04,progressos,sessoes,sprints-fechadas,prompts-historicos,docs-grandes,adr-historicos,relatorios-fase0}
```

Estrutura resultante:

```
docs/_archive/
├── fundacional-2026-03/        17 docs da gênese (26/03)
├── auditoria-2026-04/          4 auditorias + 2 planos correção
├── progressos/                 7 progressos numerados (IA e Waitlist ficam vivos)
├── sessoes/                    3 resumos de sessão
├── sprints-fechadas/           sprint_*.md + smokes
├── prompts-historicos/         PROMPT_DISCOVERY, prompt_claude_code_sprints, PROMPTS_AGENTES
├── docs-grandes/               CONTEXTO_ARQUITETURAL, MUDANCAS_REGENTE, RunbookOperacional original
├── adr-historicos/             ADR mempalace antigo (substituído por 003-mempalace-REVOKED.md)
└── relatorios-fase0/           SPRINT_A1_FASE0_REPORT, SPRINT_A1_REGENTE_AMBIENTAL, SPRINT_A2_REDATOR_REGENTE, RELATORIO_WAITLIST
```

---

## Passo 3 — Mover documentos para `_archive/`

Use `git mv` (não `mv`) para preservar histórico do git.

### 3.1 — Documentos fundacionais (26/03)

```bash
git mv "docs/Agente_Ambiental.md"                            docs/_archive/fundacional-2026-03/
git mv "docs/ANALISE_E_ORIENTACOES_TIME.md"                  docs/_archive/fundacional-2026-03/
git mv "docs/Aditivo_arquitetural_política_multi_LLM.md"     docs/_archive/fundacional-2026-03/
git mv "docs/AgenteRegulatorio_BaseCuradoria.md"             docs/_archive/fundacional-2026-03/
git mv "docs/Arquiteturadetalhada.md"                        docs/_archive/fundacional-2026-03/
git mv "docs/Backlogfuncionalportela.md"                     docs/_archive/fundacional-2026-03/
git mv "docs/Diagramatextualcompletodaarquitetura.md"        docs/_archive/fundacional-2026-03/
git mv "docs/DocumentodeFluxosEndtoEnd.md"                   docs/_archive/fundacional-2026-03/
git mv "docs/DocumentodeIntegraçõesGovTech.md"               docs/_archive/fundacional-2026-03/
git mv "docs/DocumentodeObservabilidade.md"                  docs/_archive/fundacional-2026-03/
git mv "docs/DocumentodeRegrasdeNegocio.md"                  docs/_archive/fundacional-2026-03/
git mv "docs/EspecificaçãodaAPIv1.md"                        docs/_archive/fundacional-2026-03/
git mv "docs/EstrategiaVersaoAPI.md"                         docs/_archive/fundacional-2026-03/
git mv "docs/Formalizaçãodapolíticawhitelabel.md"            docs/_archive/fundacional-2026-03/
git mv "docs/Governança deIA.md"                             docs/_archive/fundacional-2026-03/
git mv "docs/ModelagemdeBancodeDados.md"                     docs/_archive/fundacional-2026-03/
git mv "docs/ModelagemdeBancodeDados_ADITIVOV1.md"           docs/_archive/fundacional-2026-03/
git mv "docs/PlanodeExecucao.md"                             docs/_archive/fundacional-2026-03/
git mv "docs/PRDPRODUCTREQUIREMENTSDOCUMENT.md"              docs/_archive/fundacional-2026-03/
git mv "docs/PoliticaRetencaoDados.md"                       docs/_archive/fundacional-2026-03/
git mv "docs/SegurançaLGPDeConformidade.md"                  docs/_archive/fundacional-2026-03/
git mv "docs/SeedDadosDev.md"                                docs/_archive/fundacional-2026-03/
git mv "docs/SPRINT1.md"                                     docs/_archive/fundacional-2026-03/
git mv "docs/ObservabilidadeOperacional.md"                  docs/_archive/fundacional-2026-03/
```

### 3.2 — Auditorias e planos (28/03 a 04/04)

```bash
git mv docs/auditoria1.md                       docs/_archive/auditoria-2026-04/
git mv docs/auditoria2.md                       docs/_archive/auditoria-2026-04/
git mv docs/auditoria3implemantation.md         docs/_archive/auditoria-2026-04/
git mv docs/AUDITORIA_FLUXO_2026-04-29.md       docs/_archive/auditoria-2026-04/
git mv docs/PLANO_MESTRE_CORRECOES.md           docs/_archive/auditoria-2026-04/
git mv docs/PLANO_SPRINTS_CORRECOES.md          docs/_archive/auditoria-2026-04/
git mv docs/implementation_plan.md              docs/_archive/auditoria-2026-04/
git mv docs/mvp1_diagnostico.md                 docs/_archive/auditoria-2026-04/
```

### 3.3 — Progressos numerados

`progressoIA.md` e `PROGRESSO_WAITLIST.md` **ficam vivos** — não mexer.

```bash
git mv docs/progresso1.md             docs/_archive/progressos/
git mv docs/progresso1_CORRIGIDO.md   docs/_archive/progressos/
git mv docs/progresso2.md             docs/_archive/progressos/
git mv docs/progresso3.md             docs/_archive/progressos/
git mv docs/progresso4.md             docs/_archive/progressos/
git mv docs/progresso5.md             docs/_archive/progressos/
git mv docs/progresso6.md             docs/_archive/progressos/
```

### 3.4 — Resumos de sessão

```bash
git mv docs/RESUMO_SESSAO_2026-04-23.md   docs/_archive/sessoes/
git mv docs/RESUMO_SESSAO_2026-04-27.md   docs/_archive/sessoes/
git mv docs/RESUMO_SESSAO_2026-04-28.md   docs/_archive/sessoes/
```

### 3.5 — Sprints fechadas

```bash
git mv docs/sprints/sprint_minus1.md                   docs/_archive/sprints-fechadas/
git mv docs/sprints/sprint_0.md                        docs/_archive/sprints-fechadas/
git mv docs/sprints/sprint_a1.md                       docs/_archive/sprints-fechadas/
git mv docs/sprints/sprint_a2_redator.md               docs/_archive/sprints-fechadas/
git mv docs/sprints/sprint_a2_redator_smoke.md         docs/_archive/sprints-fechadas/
git mv docs/sprints/sprint_a2_diagnostico.md           docs/_archive/sprints-fechadas/
git mv docs/sprints/sprint_a2_diagnostico_smoke.md     docs/_archive/sprints-fechadas/

# Após mover tudo, remove pasta vazia se sobrou
rmdir docs/sprints 2>/dev/null || echo "docs/sprints/ não estava vazia — verificar"
```

### 3.6 — Prompts históricos

```bash
git mv docs/PROMPTS_AGENTES.md            docs/_archive/prompts-historicos/
git mv docs/PROMPT_DISCOVERY_PARCIAL.md   docs/_archive/prompts-historicos/
git mv docs/prompt_claude_code_sprints.md docs/_archive/prompts-historicos/
```

### 3.7 — Docs grandes (registro histórico)

```bash
git mv docs/CONTEXTO_ARQUITETURAL.md   docs/_archive/docs-grandes/
git mv docs/MUDANCAS_REGENTE.md        docs/_archive/docs-grandes/
git mv docs/RunbookOperacional.md      docs/_archive/docs-grandes/
git mv docs/PIPELINE_OCR.md            docs/_archive/docs-grandes/   # versão antiga; nova está em arquitetura/
git mv docs/schemas_stage_output.md    docs/_archive/docs-grandes/   # versão antiga; conteúdo absorvido em MODELO_DE_DADOS + GOVERNANCA_IA
```

### 3.8 — ADRs históricos

```bash
git mv docs/adr/adr_mempalace_REVOKED.md   docs/_archive/adr-historicos/
git mv docs/archive/mempalace_REVOKED.md   docs/_archive/adr-historicos/

# Remove a pasta antiga
rmdir docs/archive 2>/dev/null || echo "docs/archive/ não estava vazia — verificar"
```

### 3.9 — Relatórios Fase 0

```bash
git mv docs/SPRINT_A1_FASE0_REPORT.md         docs/_archive/relatorios-fase0/
git mv docs/SPRINT_A1_REGENTE_AMBIENTAL.md    docs/_archive/relatorios-fase0/
git mv docs/SPRINT_A2_REDATOR_REGENTE.md      docs/_archive/relatorios-fase0/
git mv docs/RELATORIO_WAITLIST.md             docs/_archive/relatorios-fase0/
```

---

## Passo 4 — Mover os 3 sobreviventes para suas posições novas

```bash
mkdir -p docs/estado

git mv docs/progressoIA.md          docs/estado/
git mv docs/PROGRESSO_WAITLIST.md   docs/estado/
git mv docs/descoberta-agentes/RELATORIO_PARCIAL.md   docs/estado/RELATORIO_DESCOBERTA_AGENTES.md

rmdir docs/descoberta-agentes 2>/dev/null || echo "docs/descoberta-agentes/ não estava vazia — verificar"
```

---

## Passo 5 — Descompactar os 4 blocos da Onda 3

Coloque os 4 zips na raiz do repo e descompacte:

```bash
# Bloco 1 — Fundação (vai para raiz + docs/)
unzip -o regente_docs_bloco1_fundacao.zip -d .

# Bloco 2 — Arquitetura
unzip -o regente_docs_bloco2_arquitetura.zip -d .
# Conteúdo é só docs/arquitetura/ — confirme que extraiu certo

# Bloco 3 — Operação
unzip -o regente_docs_bloco3_operacao.zip -d .

# Bloco 4 — ADRs (vai para docs/adr/ — atenção: já tem 004 e 009 do bloco 1)
unzip -o regente_docs_bloco4_adrs.zip -d .
```

Se preferir manual: descompacte os 4 zips num diretório temporário e mova as pastas para o repo (preservando estrutura).

---

## Passo 6 — Criar o `docs/_archive/README.md`

Conteúdo recomendado abaixo. Crie o arquivo:

```bash
cat > docs/_archive/README.md << 'EOF'
# Arquivo

Documentos históricos do Regente Ambiental. Preservados para auditoria, contexto histórico e referência ocasional.

**Não use estes documentos como fonte de verdade operacional.** A documentação viva está em `docs/manifesto/`, `docs/arquitetura/`, `docs/operacao/`, `docs/estado/` e `docs/adr/`.

## Organização

| Pasta | Conteúdo |
|---|---|
| `fundacional-2026-03/` | Documentos criados na gênese do projeto (26/03/2026). Muitos refletem decisões que mudaram. |
| `auditoria-2026-04/` | 4 auditorias e 2 planos de correção entre 28/03 e 04/04. Insumo da auditoria atual em `../estado/AUDITORIA_ATUAL.md` (quando for criada). |
| `progressos/` | Progressos numerados 1 a 6. Timeline narrativa do desenvolvimento até o pivô Regente. `progressoIA.md` e `PROGRESSO_WAITLIST.md` permanecem vivos em `../estado/`. |
| `sessoes/` | Resumos de sessões específicas (cirurgia MemPalace, sprint U pgvector). |
| `sprints-fechadas/` | Documentos de planejamento e smoke das sprints já mergeadas (sprint_minus1, sprint_0, sprint_a1, sprint_a2_*). |
| `prompts-historicos/` | Prompts usados para inicializar agentes Claude Code, discovery, e planejamento de sprints históricos. |
| `docs-grandes/` | Documentos gigantes que cumpriram seu papel (CONTEXTO_ARQUITETURAL de 89 KB sobre MemPalace+RAG, MUDANCAS_REGENTE de 115 KB com mapa mental da sócia, RunbookOperacional original de 88 KB). |
| `adr-historicos/` | ADRs antigos que foram reescritos. O ADR atual de MemPalace está em `../adr/003-mempalace-REVOKED.md`. |
| `relatorios-fase0/` | Relatórios de Fase 0 das sprints A1, A2-redator e Waitlist. |

## Política de retenção

Esses documentos ficam acessíveis indefinidamente — `_archive/` é parte do repositório. Não há plano de removê-los.

## Atualização

Esta pasta **não recebe atualização**. Documentos arquivados são imutáveis (a menos que erro factual seja descoberto e justifique correção pontual com nota).

Quando um documento vivo (`docs/`) for descontinuado, ele entra aqui.
EOF
```

---

## Passo 7 — Verificação

```bash
# Estrutura final esperada
tree docs -L 2 -I '_archive'

# Deve mostrar algo como:
# docs
# ├── README.md
# ├── adr/
# │   ├── 001-multitenant.md
# │   ├── 002-multi-llm-gateway.md
# │   ├── 003-mempalace-REVOKED.md
# │   ├── 004-regente-vs-amigao.md
# │   ├── 005-pgvector-rag.md
# │   ├── 006-skills-procedurais.md
# │   ├── 007-stage-output-content.md
# │   ├── 008-resend-vs-smtp.md
# │   └── 009-mobile-clientportal-congelados.md
# ├── arquitetura/
# │   └── (11 arquivos)
# ├── estado/
# │   ├── ESTADO_ATUAL.md
# │   ├── progressoIA.md
# │   ├── PROGRESSO_WAITLIST.md
# │   └── RELATORIO_DESCOBERTA_AGENTES.md
# ├── manifesto/
# │   ├── 01-VISAO_PRODUTO.md
# │   ├── 02-IDENTIDADE.md
# │   ├── 03-PRINCIPIOS.md
# │   └── 04-ROADMAP.md
# └── operacao/
#     ├── RUNBOOK_DEV.md
#     ├── RUNBOOK_OPS.md
#     ├── TROUBLESHOOTING.md
#     ├── SEED_DADOS.md
#     └── TESTING.md

# Contar arquivos vivos (esperado: 32 docs + 2 READMEs = 34)
find docs -type f -name "*.md" -not -path "*_archive*" | wc -l

# Contar arquivos arquivados (esperado: ~62)
find docs/_archive -type f -name "*.md" | wc -l

# README raiz deve existir
ls -la README.md

# Verificar links quebrados (instalar markdown-link-check se preciso):
# npx markdown-link-check docs/**/*.md
```

---

## Passo 8 — Commit estratégico

**Faça em DOIS commits separados** para facilitar revisão e rollback:

### Commit A — Arquivamento

```bash
git add docs/_archive/

git commit -m "docs(onda3): move documentação histórica para _archive/

Preserva 62 documentos como referência histórica em docs/_archive/,
organizados em 9 categorias temáticas:
- fundacional-2026-03/    (17 docs da gênese)
- auditoria-2026-04/      (4 auditorias + 2 planos correção)
- progressos/             (7 progressos numerados)
- sessoes/                (3 resumos de sessão)
- sprints-fechadas/       (7 docs de sprints já mergeadas)
- prompts-historicos/     (3 prompts de inicialização)
- docs-grandes/           (5 docs >50KB que cumpriram seu papel)
- adr-historicos/         (2 ADRs antigos do MemPalace)
- relatorios-fase0/       (4 relatórios de fase 0)

3 documentos vivos movidos para docs/estado/:
- progressoIA.md
- PROGRESSO_WAITLIST.md
- RELATORIO_DESCOBERTA_AGENTES.md (renomeado de descoberta-agentes/RELATORIO_PARCIAL.md)

Nenhum documento foi deletado. Tudo permanece acessível em _archive/.

Refs: docs/_archive/README.md explica a organização."
```

### Commit B — Nova documentação

```bash
git add README.md docs/

git commit -m "docs(onda3): documentação reescrita do Regente Ambiental

Substitui a documentação antiga (agora em docs/_archive/) por uma nova
estrutura em 5 camadas, com 32 documentos focados em decisão e
orientação, não apenas descrição.

Estrutura:
- docs/manifesto/    (4 docs: visão, identidade, princípios, roadmap)
- docs/arquitetura/  (11 docs: visão técnica completa)
- docs/operacao/     (5 docs: runbooks dev/ops/troubleshooting/seed/testing)
- docs/estado/       (4 docs vivos: estado atual + progressos)
- docs/adr/          (9 ADRs: decisões arquiteturais formalizadas)

Identidade clarificada:
- Regente Ambiental é o nome do produto (visível, comercial)
- Amigão do Meio Ambiente é codinome técnico interno
- Detalhes em docs/adr/004-regente-vs-amigao.md

Frentes congeladas formalizadas:
- client-portal/ e mobile/ documentados como congelados em
  docs/adr/009-mobile-clientportal-congelados.md

MemPalace formalmente excisado em docs/adr/003-mempalace-REVOKED.md.

Tag de segurança disponível: pre-onda3-migration

Refs: docs/README.md tem índice navegável."
```

---

## Passo 9 — Push e validação

```bash
# Push
git push origin <sua-branch>

# Push da tag de segurança
git push origin pre-onda3-migration

# Em outra máquina ou no GitHub Web: validar que os links em docs/README.md
# levam aos arquivos certos
```

---

## Em caso de problema

### Voltar tudo

```bash
git reset --hard pre-onda3-migration
git push --force origin <sua-branch>   # cuidado se outros já puxaram
```

### Documentação antiga em conflito

Se houver merge conflict porque outra branch tocou em algo da `docs/` antiga: a antiga venceu na sua branch original — o conflito deve ser resolvido movendo o conteúdo conflitante para `docs/_archive/` também.

### Encontrei doc que deveria estar vivo, não em archive

Mover de volta:

```bash
git mv docs/_archive/<categoria>/<arquivo>.md docs/<destino>/
```

Adicione nota no PR e siga.

---

## Checklist final

Antes de fechar a Onda 3, confirme:

- [ ] `pre-onda3-migration` tag criada
- [ ] `docs/_archive/` com 62 arquivos organizados em 9 pastas
- [ ] `docs/_archive/README.md` explicando a organização
- [ ] `docs/manifesto/` com 4 docs novos
- [ ] `docs/arquitetura/` com 11 docs novos
- [ ] `docs/operacao/` com 5 docs novos
- [ ] `docs/estado/` com 4 docs vivos
- [ ] `docs/adr/` com 9 ADRs (001 a 009)
- [ ] `docs/README.md` (índice navegável)
- [ ] `README.md` raiz do repo
- [ ] Nenhum link quebrado entre os docs novos (verificação manual ou ferramenta)
- [ ] 2 commits separados (arquivamento + nova doc)
- [ ] Push feito
- [ ] Sócia / agente / pessoa nova consegue ler README → docs/README → entender o produto em 30 min

## Próximo passo (fora da Onda 3)

Onda 4 começa naturalmente depois disso: a documentação nova **vira ferramenta de trabalho diário** — atualizada a cada sprint relevante. `ESTADO_ATUAL.md` é o que muda mais. Manifesto muda raramente. ADR novo nasce com toda decisão grande.

Documentação como orientador, não como museu.
