# BRIEFING DE SESSÃO — Regente Ambiental (amigao)
> **Como usar:** no INÍCIO de um chat novo, suba este arquivo + (se for tocar código) os arquivos relevantes.
> No FIM da sessão, peça o briefing atualizado e commite em `docs/estado/BRIEFING_SESSAO.md`.
> Última atualização: 2026-06-01

---

## 0. Regras de trabalho com o Claude-chat (coordenador)
- **Claude NÃO tem acesso ao repo.** Coordena cego a menos que arquivos sejam subidos. Quando o trabalho toca código, subir os arquivos relevantes (foi quando os erros pararam).
- **Verificar contra código real, nunca de memória/representação mental.** Erros graves desta sessão vieram de assumir em vez de ler (ex.: afirmei "tema escuro" quando os prints eram claros).
- **VALIDAÇÃO E2E REAL:** tsc/build/unit NÃO encerram trabalho. Toda correção de comportamento exige reproduzir RODANDO antes e revalidar RODANDO depois (request/log/SQL).
- Comunicação: sem bajulação, decisões+impacto no chat, detalhes nos prompts. Uma pergunta por vez. Português.

---

## 1. Estado atual do sistema (o que funciona, com evidência do mergulho 2026-06-01)
Fluxo agêntico **funciona em pedaços** — não é "tudo quebrado":
- ✅ `/intake/classify` (LLM), upload→OCR pypdf→extrator COM document_id (12 campos), create-case (migra docs do draft, checklist auto-link).
- ❌ **Diagnóstico não entrega.** Três camadas somadas (ver §3).
- Produção: deploy recente OK, backend core responde 200, frontend tema claro. WS falhava por path (corrigido em #45, aguardando deploy). "CORS do /threads" é **500 mascarado** (corrigido em #45).

## 2. Mapa do fluxo agêntico (do mergulho, RODANDO)
```
intake → classify(LLM) ✅
  → upload → OCR(pypdf) → extrator(document_id) → 12 campos ✅
  → create-case → process+client+property, docs migrados, checklist ✅
       └─ dispara SÓ atendimento ⚠️  (a chain de diagnóstico NÃO roda sozinha)
  → [só manual hoje] chain diagnostico_completo = [extrator, auditor_imovel, legislacao, diagnostico]
       extrator → SKIP sem document_id  (CORRIGIDO #45: resolve do process)
       auditor_imovel → ok (NON_BLOCKING)
       legislacao → TIMEOUT litellm (bloqueante) → ABORTA a chain
       diagnostico → NÃO RODA → 0 diagnoses
```
**Acoplamento confirmado pela skill:** a legislação roda ANTES e é insumo #5 do diagnóstico ("Contexto legal output do LegislacaoAgent"). Diagnóstico e legislação andam juntos — não independentes.

## 3. Por que o diagnóstico não entrega — TRÊS camadas
1. **Chain não é disparada** — create-case só roda atendimento. Precisa **auto-trigger** (André quer; Isis confirma).
2. **Chain aborta na legislação** — `orchestrator.py:137-142` faz `if not result.success: break`; legislacao dá Timeout/json_parse intermitente. → dívida **#38**.
3. **Skills ignoradas** — 2 SKILL.md inválidos silenciosamente ignorados → diagnóstico e auditor rodam SEM método (raso = "sistema burro"). → dívida **#40**.

## 4. Plano acordado
- **#40 primeiro** (pequeno): validar/corrigir os 2 SKILL.md inválidos + verificar o loader de skills no código. Sem isso, diagnóstico sai raso mesmo com chain ok.
- **#38 depois** (médio): chain robusta (ÊNFASE: robustez da legislação — timeout/parse — porque o acoplamento é real e desejado) + resiliência (não-fatal espelhando NON_BLOCKING_REVIEW_AGENTS) + auto-trigger no create-case. Critério: criar caso → ver diagnóstico entregue COM qualidade, RODANDO.
- Depois: seletor de caso na aba Agentes (hoje não existe — agente roda sem contexto); botão "resumo" do workspace (quebrado, não gera nada).

## 5. PRs recentes
- #44 (mergeado) — Evolution fora do boot do docker (causa: `${EVOLUTION_API_KEY:?}` interpolado no up). `docker compose up` destravado.
- #45 (aberto/aguardando deploy) — 3 P0: CORS-mascara-500 (`ServerErrorMiddleware` acima do `CORSMiddleware`), WS path (`/ws` e `/api/v1/ws`), gap extrator (resolve docs do process).

## 6. Dívidas reais (REGISTRO_DIVIDAS.md)
#37 reintegrar Evolution · **#38 chain aborta na legislacao (ALTA)** · #39 robustez legislacao · **#40 2 SKILL.md inválidos** · #41 auto-trigger pós-case · #42 bucket MinIO presigned · #43 Error Boundary global.

## 7. Bugs de UI apontados pelo André (fora do mergulho)
- Aba **Agentes sem seletor de caso/cliente** — escolhe o agente mas não aponta o caso → agente roda sem contexto.
- Botão **"resumo" do workspace não funciona** — não gera resumo.

## 8. Decisões fechadas (não rediscutir)
Produto: Regente / codinome amigao (ADR-004) · Mobile + client-portal CONGELADOS (ADR-009) — **orquestração de chains NÃO está congelada** · pgvector vector(768) Gemini · Encriptação Fernet API keys/credenciais (ADR-014) · Agentes não-bloqueantes na chain (ADR-011, auditor_imovel é o 1º) · Decisão do consultor é contextual ao processo (ADR-012) · Criação de caso é manual; mensagens inbound integram casos, nunca auto-criam draft.

## 9. Arquivos-chave (paths reais)
- Orquestração: `app/agents/orchestrator.py` (chain, linha ~137 o break), `app/workers/agent_tasks.py` (run_agent, run_agent_chain), `app/workers/ocr_tasks.py` (ocr_then_extract → _dispatch_extrator).
- Agentes: `app/agents/{extrator,legislacao,diagnostico,...}.py`, `app/agents/base.py` (AgentRegistry).
- Intake: `app/api/v1/intake.py` (create-case ~371 dispara só atendimento; /import; /reconcile).
- Docs/extração: `app/api/v1/documents.py`, `app/api/v1/processes.py` (/extract), `app/models/document.py`.
- Transporte: `app/main.py` (middlewares, montagem WS :167), `app/api/websockets.py:126` (rota /ws), `app/core/config.py` (CORS), `render.yaml:46` (CORS prod).
- Front: `frontend/src/App.tsx` (ErrorBoundary raiz :33, QueryClient :22), `useAgentEvents.ts` (WS), `IntakeWizard.tsx`, `DraftDocumentUploader.tsx`.
- Skills: `app/skills/<agente>/<dominio>/SKILL.md` (md com frontmatter applies_to). A do diagnóstico: `situacao-ambiental-imovel-rural` (excelente — 18 heurísticas, cruzamento documental, radar-não-cancela).

## 10. Artefatos de contexto (agora em md — subir estes, não os xlsx)
- `docs/contexto/WORKFLOW.md` (era workflow_regente.xlsx).
- `docs/contexto/ENTRADA_DEMANDA.md` (era 1__Entrada_de_demanda.xlsx).
- Skills do extrator e legislação: **Claude-chat NÃO tem acesso** — subir os SKILL.md quando o trabalho tocar esses agentes.

## 11. Próxima ação
Disparar **#40** (skills + loader) → depois **#38** (auto-trigger + robustez legislação + resiliência). Isis valida só DEPOIS do trabalho entregue.
