# Governança documental do Regente

Padrão de organização da documentação do projeto. Existe porque documento acumulado sem rumo
vira ruído: ninguém sabe o que é fonte de verdade, o que já cumpriu função, o que pode descartar.
Este é o mapa — e é norma, não sugestão.

## A regra de ouro

> **Documento VIVO é fonte de verdade. Documento EFÊMERO é meio, não fim.**
> Antes de descartar ou arquivar um efêmero, seu conteúdo durável **já tem que estar capturado
> num vivo**. Nenhuma decisão pode morar só num efêmero (um prompt, um relatório, um chat).

Se essa regra for seguida, descartar é seguro e a documentação não incha: o que importa está
sempre num vivo; o resto é descartável por construção.

## Os três estados de um documento

- **VIVO** — fonte de verdade, mantido atualizado, tem dono e cadência. Mora no repo.
- **EFÊMERO** — cumpre função pontual (instruir, reportar, coletar) e é descartável/arquivável
  *depois* que seu durável foi capturado num vivo. Não é fonte de verdade. Geralmente vive na
  conversa/terminal, não no repo.
- **ARQUIVADO** — histórico preservado, read-only, fora do fluxo de trabalho. Mora em `docs/arquivo/`.

## Taxonomia (tipo → local → estado → cadência → dono)

| Categoria | Local | Estado | Quando atualiza | Dono |
|---|---|---|---|---|
| **Manifesto** (visão, identidade, princípios, roadmap) | `docs/manifesto/` | Vivo | Raramente — muda a estratégia | Andre |
| **Arquitetura** (modelo de dados, fluxos, máquina de estados, pipelines, multitenant, observabilidade, whitelabel, API, base regulatória) | `docs/arquitetura/` | Vivo | Quando a arquitetura muda | Coordenador + Andre |
| **Operação** (runbooks ops/dev, troubleshooting, testing, seed) | `docs/operacao/` | Vivo | Quando um procedimento muda | Coordenador |
| **ADR** (decisões arquiteturais) | `docs/adr/` | Vivo (imutável após aceita) | Nunca se reescreve; se cai, marca `REVOKED` | Quem decide |
| **Skills** (método dos agentes) | `app/skills/<agente>/<dominio>/SKILL.md` | Vivo (versionado) | Quando o método muda; validado pela sócia | Coordenador + Isis |
| **Estado — snapshot** (`ESTADO_ATUAL`) | `docs/estado/` | Vivo | Fim de cada sprint — foto do agora | Coordenador |
| **Estado — log** (`progressoIA.md`) | `docs/estado/` | Vivo | Contínuo — diário do que foi feito | Coordenador |
| **Registro de dívidas** | `docs/REGISTRO_DIVIDAS.md` | Vivo | Fim de cada sprint | Coordenador |
| **Prompts para o agente** | conversa / `docs/arquivo/prompts/` se rastrear | **Efêmero** | Descartável após execução | — |
| **Relatórios do agente** | conversa / terminal | **Efêmero** | Durável vira `ESTADO_ATUAL` + dívidas + commits | — |
| **Material de domínio da sócia** (questionários, complementos) | uploads / `docs/arquivo/dominio/` | **Efêmero** | Durável é integrado às skills, depois arquiva | — |

## Cadência de atualização — o pulso e a estrutura

*(Esta é a parte transferível a qualquer projeto. Os documentos mudam de nome; os dois ritmos, não.)*

Todo documento vivo tem um de dois ritmos:

- **Documentos de PULSO** — respondem *"onde estamos agora"*. Mentem rápido se não atualizados. Ritmo: **toda rodada**, por disciplina, mesmo quando parece que pouco mudou. São poucos — se forem muitos, algo está errado.
- **Documentos de ESTRUTURA** — respondem *"como o sistema é / decide"*. Só mudam quando a coisa que descrevem muda. Ritmo: **por evento**. Tocar sem evento é ruído; **não** tocar quando o evento aconteceu é dívida silenciosa (a pior — o documento mente e ninguém percebe).

A disciplina inteira cabe numa pergunta ao fim de cada rodada: *atualizei o pulso (sempre)? e algum evento desta rodada disparou um documento de estrutura?*

### Pulso — atualizar TODA rodada
`ESTADO_ATUAL` (a foto do agora) · `progressoIA` (o log do que foi feito) · `REGISTRO_DIVIDAS` (abriu/fechou dívida) · o **índice deste documento** (nasceu/morreu/mudou de estado algum doc).

### Estrutura — atualizar QUANDO o gatilho dispara
| Gatilho (o que aconteceu na rodada) | Documento a atualizar |
|---|---|
| Decisão arquitetural tomada | novo **ADR** (revoga uma? marca `REVOKED`) |
| Schema / migration muda | `MODELO_DE_DADOS` |
| Estados ou transições do processo mudam | `MAQUINA_DE_ESTADOS` |
| Fluxo ponta a ponta muda (ex.: agente entra na chain) | `FLUXOS_E2E` |
| Endpoint nasce ou muda contrato | `API_v1` |
| Método de um agente muda / sócia valida | a `SKILL` correspondente |
| Procedimento de operação ou deploy muda | `RUNBOOK_OPS` |
| Setup ou processo de desenvolvimento muda | `RUNBOOK_DEV` |
| Componente ou integração adicionado/removido | `ARQUITETURA_GERAL` |
| Política de IA / agentes muda | `GOVERNANCA_IA` |
| Normas ingeridas no RAG | `BASE_REGULATORIA` |
| Problema recorrente novo + solução | `TROUBLESHOOTING` |
| Estratégia de testes muda | `TESTING` |
| Visão / estratégia / posicionamento muda | `manifesto` (01–04) |

### Checklist de fim de rodada (para mim, você e os agentes do Claude Code)
1. **Pulso:** `ESTADO_ATUAL` + `progressoIA` + `REGISTRO_DIVIDAS` + índice — sempre, sem exceção.
2. **Estrutura:** percorrer os gatilhos acima e atualizar só os que esta rodada disparou.
3. **Efêmeros:** o durável dos prompts e relatórios desta rodada já está nos vivos? Se sim, descartar/arquivar; se não, capturar antes.

Os agentes do Claude Code devem rodar essa checklist no fechamento de cada prompt — é a contrapartida documental do "reporte cada commit". Um prompt não está "pronto" só porque o código passou; está pronto quando o pulso foi atualizado e os gatilhos de estrutura foram percorridos.

## Fluxo: o que fazer ao gerar um documento novo

Quatro perguntas, nesta ordem:
1. **É vivo ou efêmero?** Vai ser consultado de novo no futuro como verdade → vivo. Serve uma vez (instruir/reportar) → efêmero.
2. **Se vivo: onde mora e quem mantém?** Encaixar numa categoria acima. Sem categoria → provavelmente não deveria ser vivo.
3. **Se efêmero: qual vivo captura o durável dele?** Um prompt vira ADR + dívidas + commit. Um relatório vira estado. Um questionário vira skill. *Se nada captura, o efêmero não pode ser descartado ainda.*
4. **Substitui ou complementa algo existente?** Se substitui, o antigo vai para `docs/arquivo/` (não se apaga histórico). Se complementa, referenciar mutuamente.

## Índice atual (inventário vivo)

*Atualizado em 2026-05-25 (rodada de governança documental — todos os candidatos
listados antes foram arquivados em `docs/_archive/`).*

**Manifesto:** `01-VISAO_PRODUTO` · `02-IDENTIDADE` · `03-PRINCIPIOS` · `04-ROADMAP` (em `docs/manifesto/`)
**Arquitetura:** `ARQUITETURA_GERAL` · `MODELO_DE_DADOS` · `MAQUINA_DE_ESTADOS` · `FLUXOS_E2E` · `MULTITENANT_LGPD` · `PIPELINE_OCR` · `GOVERNANCA_IA` · `OBSERVABILIDADE` · `WHITELABEL` · `INTEGRACOES_GOVTECH` · `API_v1` · `BASE_REGULATORIA` · **`GOVERNANCA_DOCUMENTAL` (este)** (em `docs/arquitetura/`)
**Operação:** `RUNBOOK_OPS` · `RUNBOOK_DEV` · `TROUBLESHOOTING` · `TESTING` · `SEED_DADOS` · `POS_DEPLOY` (em `docs/operacao/`)
**Estado:** `ESTADO_ATUAL` (snapshot) · `progressoIA` (log) (em `docs/estado/`)
**Dívidas:** `REGISTRO_DIVIDAS` (em `docs/`)
**ADR:** `001`–`011` (em `docs/adr/`; `003-mempalace` está `REVOKED` — exemplo da regra: caiu, mas não some)
**Skills:** `diagnostico/situacao_ambiental_imovel_rural` (v1.1.0) · `auditor_imovel/analise_divergencias_documentais` (v1.1.0, + anexo `bases_car_estaduais`) (em `app/skills/<agente>/<dominio>/`)
**Dados:** `data/normas_k3/MANIFESTO.md` (9 normas indexadas no `knowledge_catalog`; PDFs originais ficam fora do repo)
**Progressos históricos:** `docs/_archive/progressos/progresso1..progresso8.md` (snapshots ao fim de cada rodada — *imutáveis*)

**Arquivados em 2026-05-25** (cumpriram função; duráveis já capturados em vivos):
- `docs/_archive/PROGRESSO_WAITLIST.md` — Waitlist B1 mergeada; histórico cobre no `progressoIA`.
- `docs/_archive/CRUZAMENTO_DOC_X_CODIGO_2026-05-15.md` — snapshot datado; substituído pelos docs reconciliados na Fase 0 do PROMPT_1.
- `docs/_archive/RELATORIO_DESCOBERTA_AGENTES.md` — capturado em `ESTADO_ATUAL` + `progressoIA` + Fase 2.

**Reposicionados nesta rodada** (todos os duráveis vieram da raiz untracked do worktree `Amigao_do_Meio_Ambiente` para o repo versionado em `chore/governanca-documental`):
- `GOVERNANCA_DOCUMENTAL.md` → `docs/arquitetura/GOVERNANCA_DOCUMENTAL.md`
- `REGISTRO_DIVIDAS.md` → `docs/REGISTRO_DIVIDAS.md`
- `MAQUINA_DE_ESTADOS.md` → `docs/arquitetura/` (saiu de `docs/estado/`)
- `SKILL.md` (v1.1.0) → `app/skills/diagnostico/situacao_ambiental_imovel_rural/SKILL.md` (atualizou v1.0.0)
- `SKILL_auditor_imovel.md` → `app/skills/auditor_imovel/analise_divergencias_documentais/SKILL.md` (novo)
- `bases_car_estaduais.md` → `app/skills/auditor_imovel/analise_divergencias_documentais/bases_car_estaduais.md` (anexo da skill)
- `MANIFESTO_NORMAS.md` → `data/normas_k3/MANIFESTO.md` (gitignore ajustado para permitir o manifesto sem versionar os PDFs)
- `011-agentes-nao-bloqueantes-chain.md` → `docs/adr/011-agentes-nao-bloqueantes-chain.md` (promovido a ADR)

**Em aberto (para o próximo ciclo, ou decisão do Andre):**
- `VALIDACAO_DEPLOY.md` (raiz, tracked, do commit `86ae4f7`) — convenção diz `docs/operacao/`. Mover é mudança ortogonal; deixar como dívida.
- `Diagnóstico de Situação Ambiental — Imóvel Rural.docx` + `Complemento SiKILL Auditor.docx` (raiz untracked do worktree dashboard) — material de domínio da sócia; durável já está nas skills. Deixar para o Andre decidir se quer preservar como insumo histórico em `docs/_archive/dominio/`.
- `Licenciamento (SEMAD)/`, `Manuais (SEMAD)/` (raiz untracked) — material de referência regulatória da sócia; sem decisão de destino.
- `normas_k3/` (raiz untracked, 9 PDFs + 1 docx) — PDFs originais. O **MANIFESTO** está no repo (acima); os PDFs vivem fora — já indexados no `knowledge_catalog`.

## Sobre o runbook (a dor que originou este documento)

Os runbooks **já existem** (`RUNBOOK_OPS`, `RUNBOOK_DEV`) e são vivos. Se você sentiu falta deles,
foi sintoma exato do problema que este documento resolve: sem índice, documento existente some de
vista. Ação concreta: confirmar que os dois estão atualizados (deploy no ar mudou a operação —
Render + R2; os runbooks refletem isso?) e mantê-los no índice. Se algum estiver defasado, é dívida
de operação, não falta de documento.

## Manutenção deste documento

O índice se atualiza ao **fim de cada sprint**, junto com o `ESTADO_ATUAL` — mesmo gesto. Quando um
documento nasce, morre ou muda de estado, a linha correspondente aqui acompanha. Um índice
desatualizado é pior que nenhum, porque mente; manter é parte do "fim de sprint", não tarefa extra.
