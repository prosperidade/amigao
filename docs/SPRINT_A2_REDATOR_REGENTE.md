# Sprint A2-redator — Adoção de PecaJuridicaContent no RedatorAgent

> **Status:** proposta — aguarda validação na **Fase 0** antes de qualquer commit.
> **Predecessora:** Sprint A1 (fechada — 6 tarefas, 128 testes, +4.654/-54 linhas, commit `bd47f0c`).
> **Branch sugerida:** `feat/sprint-a2-redator`
> **Esforço estimado:** S/M — 3 tarefas focadas, ~30-50 testes novos.

## Contexto e motivação

Sprint A1 entregou a **infraestrutura** de schemas estruturados (`StageOutputContent` + 3 derivados) mas adoção ficou opt-in — nenhum agente foi migrado. A2-redator é a primeira adoção real, escolhida pelo redator porque:

1. Já tem `CitationRef` integrado via Tarefa B da A1 — adoção natural, sem retrabalho.
2. É o agente mais arriscado (peças vão para órgão regulador) — tipagem rigorosa entrega valor auditável imediato.
3. Migrar 1 agente é exercício controlado; depois replica nos outros 4 com padrão validado.
4. Quando Sprint A3 (skills de domínio) chegar com os PDFs da sócia, vai encontrar `PecaJuridicaContent` em uso e skills encaixam direto sem refator.

## Pré-condições

- [ ] Sprint A1 mergeada na `main` (commit `bd47f0c` ou posterior).
- [ ] `app/skills/` existe e Tarefa A da A1 está em pé.
- [ ] `app/schemas/stage_output.py` tem `PecaJuridicaContent` e `RespostaNotificacaoContent` com campos definidos.
- [ ] `app/services/citation_evaluator.py` existe e o hook no `RedatorAgent` está ativo (Tarefa B da A1).
- [ ] `BaseAgent.run()` aceita tanto `dict` legado quanto `StageOutputContent` (Tarefa C da A1).
- [ ] Branch `main` em estado verde.

## Princípios inegociáveis

1. **Read-then-act.** Fase 0 obrigatória. Não modifique `RedatorAgent`, não toque em `pdf_generator`, não escreva testes até receber sinal verde.
2. **Evidência ou nada.** Toda decisão referencia arquivo + path. Sem evidência → vira pergunta na Fase 0.
3. **Backward compatibility durante transição.** O redator passa a emitir `PecaJuridicaContent` mas consumidores legados que esperam `dict` não devem quebrar — `BaseAgent.run()` já aceita ambos; explore esse adapter.
4. **Não migre os outros 4 agentes.** Escopo é estrito: só RedatorAgent.
5. **Tests obrigatórios.** Caminho feliz por template + ao menos 1 caminho de erro por tarefa.
6. **Lint/typecheck limpos** nos arquivos tocados (ruff, mypy onde configurado).

## Não-objetivos (NÃO faça neste ciclo)

- ❌ Migrar `ExtratorAgent`, `AtendimentoAgent`, `DiagnosticoAgent`, `LegislacaoAgent` — cada um vira sprint própria (A2-extrator, etc.) sob demanda.
- ❌ Modificar `app/services/citation_evaluator.py` — já existe e funciona.
- ❌ Mexer em `app/services/proposal_generator.py` ou `app/services/contract_generator.py` — escopo é só `RedatorAgent`. Se eles substituem o redator para os templates `proposta` e `contrato`, esses templates podem ficar **fora** desta migração (decisão na Fase 0).
- ❌ Criar skills de domínio (`oficio_semad.md`, `prad.md`, etc.) — gate da sócia, virá em A3.
- ❌ Refatorar `PecaJuridicaContent` ou `RespostaNotificacaoContent` além do estritamente necessário. Se aparecer dor real durante a Fase 0, vira pergunta antes de mexer.
- ❌ Trocar provider LLM ou ajustar prompts do redator — escopo é só o **shape do output**, não comportamento de geração.
- ❌ Migrar dados históricos de `AIJob.result` (jobs antigos com `dict` ficam como estão; queries futuras precisarão tolerar ambos os formatos).

## Fase 0 — PARE E PERGUNTE

### Passo 1 — Leia

- `app/agents/redator.py` (lifecycle completo, especialmente `run()` ou equivalente)
- `app/agents/base.py` (entender como `run()` aceita ambos `dict` e `StageOutputContent` após A1)
- `app/schemas/stage_output.py` (`PecaJuridicaContent`, `RespostaNotificacaoContent` — confirmar campos exatos pós-A1)
- `app/services/citation_evaluator.py` (hook que popula `legal_citations`)
- `app/workers/pdf_generator.py` (consumidor crítico do output do redator)
- `app/services/proposal_generator.py` (~301 linhas — confirmar relação com redator)
- `app/services/contract_generator.py` (~243 linhas — idem)
- `app/agents/orchestrator.py` — em particular a chain `diagnostico_completo` (extrator → legislacao → diagnostico → redator?) e como o output do redator é passado adiante (se é).
- `tests/agents/test_redator.py` ou equivalente (entender padrão atual)
- Qualquer endpoint/router que consuma o output do redator (ex: `/agents/run`, exibição em frontend admin)

### Passo 2 — Reporte (4 blocos)

**(a) Divergências** entre o que este prompt assume e o que está no código real. Em particular: confirme os campos exatos de `PecaJuridicaContent` pós-A1 (alguns campos podem ter sido renomeados ou ter validators acrescentados durante a implementação que escapem ao meu conhecimento).

**(b) Confirmações ou correções de suposições** — em particular:
- Padrão de testes do redator (mocks de LLM? VCR? stubs determinísticos?).
- Como o `pdf_generator` lê o output hoje (campo específico? `result["text"]`? `result["content"]`?).
- Se o `proposal_generator` e `contract_generator` substituem o redator para `template="proposta"`/`template="contrato"` ou se eles são complementares (chamados depois do redator).
- Como o orchestrator passa o output do redator pra próximo agente da chain, se houver.
- Se `RespostaNotificacaoContent` foi implementado como **subtype** de `PecaJuridicaContent` ou como **sibling** (ambos derivados de `StageOutputBase`). A migração muda dependendo disso.
- Se há frontend consumindo `AIJob.result` do redator e em qual formato.

**(c) Riscos arquiteturais** que você enxergou e este prompt não cobre. Em especial: se algum consumidor do output do redator faz acesso por chave específica (ex: `result["addressee"]`) que pode quebrar com a migração — listar explicitamente.

**(d) Proposta de execução**:
- Confirme ordem A → B → C ou proponha alternativa.
- Estimativa de esforço relativo por tarefa (XS/S/M/L).
- Se você quer dividir Tarefa C em C1 (testes paramétricos) e C2 (smoke E2E), justifique.

### Passo 3 — Perguntas em aberto

Numeradas, com impacto explícito por questão.

### Passo 4 — PARE

Espere sinal verde explícito.

## Tarefas

### Tarefa A — Migrar `RedatorAgent` para emitir `PecaJuridicaContent`

**Arquitetura proposta:**

`RedatorAgent.run()` (ou método equivalente) passa a:

1. Construir `PecaJuridicaContent` ao final da geração:
   - `content`: o texto da peça (markdown/plain).
   - `metadata`: dict com `template`, `model_used`, `tokens_in`, `tokens_out`, `latency_ms`, qualquer dado auxiliar.
   - `sources`: lista de `Source` derivada do `legislation_context` usado (cada `KnowledgeChunk` ID vira `Source(type="legislation", ref=str(chunk_id), excerpt=...)`).
   - `confidence`: `None` por enquanto (pode evoluir em sprint futura).
   - `legal_citations`: lista de `CitationRef` — já populada pelo citation evaluator hook (Tarefa B da A1). Confirme na Fase 0 se o hook já entrega `list[CitationRef]` ou se ainda é dict.
   - `addressee`: extraído quando aplicável (ofício/comunicação/resposta_notificacao) ou `None`.
   - `template`: literal de 7 valores (`prad`, `memorial`, `oficio`, `proposta`, `resposta_notificacao`, `contrato`, `comunicacao`).

2. Para `template == "resposta_notificacao"`, retornar `RespostaNotificacaoContent` em vez de `PecaJuridicaContent` — com campos extras `prazo_dias` e `ato_regulatorio` populados.

3. Persistir o output:
   - `AIJob.result = peca.model_dump(mode='json')` — JSON-serializable.
   - Validação: antes de persistir, validar via Pydantic (`PecaJuridicaContent.model_validate(...)` faz isso ao construir, então construir já é a validação).
   - Se construção falhar (ex: faltam citações em peça que exige), levantar exceção tipada `RedatorOutputValidationError` com contexto.

4. Flag de rollback rápido (opcional, recomendado): adicionar `legacy_dict_output: bool = False` em `RedatorAgent.__init__()` ou no `OrchestratorConfig`. Quando `True`, comportamento volta ao formato `dict` antigo. Útil pra debug em prod se algo quebrar em consumidor escondido.

**Templates fora do escopo (decisão da Fase 0):**

Se `proposal_generator` e `contract_generator` produzem proposta/contrato hoje sem passar pelo `RedatorAgent`, então `template="proposta"` e `template="contrato"` **podem nunca ser executados** pelo redator e não precisam migrar agora. **Confirmar na Fase 0** quais dos 7 templates o `RedatorAgent` efetivamente serve hoje.

**Não fazer agora:**
- Não trocar a lógica de geração (LLM, prompt, RAG retrieval). Só o **shape do output**.
- Não criar novos templates além dos 7 existentes.
- Não validar `legal_citations` contra `knowledge_catalog` aqui — isso é trabalho do citation evaluator que já existe.
- Não popular `confidence` com algoritmo novo. Deixa `None`.

**Testes obrigatórios** (`tests/agents/test_redator_a2.py` ou estendendo `test_redator.py`):
- Construção de `PecaJuridicaContent` para cada template servido pelo `RedatorAgent` (5-7 casos parametrizados — confirmar lista na Fase 0).
- `RespostaNotificacaoContent` construído quando `template="resposta_notificacao"` com `prazo_dias` e `ato_regulatorio`.
- `legal_citations` recebe a lista do citation evaluator (mock).
- `sources` derivado de `legislation_context` real ou stub.
- `AIJob.result` é JSON-serializable (round-trip via `model_dump_json()` + `model_validate_json()` retorna iguais).
- Caminho de erro: input que faz Pydantic falhar (ex: `template` inválido, `legal_citations` não-lista) levanta `RedatorOutputValidationError`.
- Flag `legacy_dict_output=True` retorna o formato antigo.

**Critério de sucesso verificável:**
- `pytest tests/agents/test_redator_a2.py` 100% verde.
- Smoke manual: rodar redator em modo dry-run (com LLM real ou stub determinístico) num caso conhecido, ver `AIJob.result` no banco com a estrutura nova e citações populadas.

**Commit:** `feat(sprint-a2-redator-A): RedatorAgent emite PecaJuridicaContent`

---

### Tarefa B — Adaptar consumidores do output do redator

**Por que junto com A:** o output mudou; consumidores que liam por chave específica (ex: `result["text"]`) quebram silenciosamente. Tem que adaptar antes de fechar a sprint.

**Consumidores identificados (a confirmar/expandir na Fase 0):**

1. **`app/workers/pdf_generator.py`** — gera PDF a partir do texto da peça. Hoje provavelmente lê algo como `result["text"]` ou `result["content"]`. Adaptar para ler `result["content"]` no novo formato (que é o `content` do `PecaJuridicaContent`). Se já era `content`, não muda nada.

2. **Orchestrator chain `diagnostico_completo`** (se redator alimenta próximo agente) — confirmar na Fase 0 se há próximo agente após redator. Se sim, garantir que `BaseAgent.run()` desserializa o `dict` (vindo de `model_dump`) ao receber, ou que o adapter de A1 cobre esse caso.

3. **Endpoint `/agents/run`** — frontend ou cliente que faz GET no resultado. Como a API retorna JSON, novos campos **opcionais** não quebram clientes que ignoram campos desconhecidos. **MAS** se o cliente faz acesso direto por chave que sumiu (ex: `result.text` → agora `result.content`), quebra. Mitigação: se houver consumidor frontend, manter `text` como **alias deprecated** (campo computed property que retorna `content`) por 1-2 sprints até confirmar zero uso, então remover.

4. **Logs / observabilidade** — qualquer log que printe `result.<chave>` continua funcionando se a chave existe no novo formato. Caso contrário, atualizar.

5. **Testes existentes do redator** — vão precisar de atualização. Lista pra revisar.

**Não fazer agora:**
- Não migrar `proposal_generator.py` / `contract_generator.py`. Eles continuam como estão.
- Não criar adapter universal para qualquer agente. O adapter genérico de A1 (`BaseAgent.run()` aceitando ambos) já cobre.
- Não deprecar campos do schema antes da hora — só add aliases se houver consumidor concreto.

**Testes obrigatórios:**
- `pdf_generator` consome output novo e gera PDF idêntico ao antigo (snapshot test).
- Orchestrator chain `diagnostico_completo` (se aplicável) processa output novo sem erro.
- Endpoint `/agents/run` retorna JSON com novos campos + (se aplicável) campos legacy aliasados.
- Caminho de erro: consumidor recebendo `dict` legado (job antigo no banco) ainda funciona via adapter.

**Critério de sucesso verificável:**
- Todos os testes verdes.
- Smoke: rodar pipeline ponta-a-ponta em 1 caso real com PDF gerado e endpoint retornando ok.
- Inspeção manual de 1 PDF gerado pelo pipeline novo vs antigo — conteúdo equivalente.

**Commit:** `feat(sprint-a2-redator-B): adaptar consumidores do output do RedatorAgent`

---

### Tarefa C — Smoke E2E + testes paramétricos nos templates servidos

**Por que separada de A:** A é shape do output; C é validação que nada quebrou em uso real. Separar ajuda a debugar se algo aparecer.

**Estratégia:**

1. **Bateria paramétrica** (`tests/agents/test_redator_a2_e2e.py`):
   - Para cada template servido pelo `RedatorAgent` (lista confirmada na Fase 0, provavelmente 5 dos 7):
     - Input fake/stub com contexto mínimo (process, client, property, legislation_context).
     - Rodar `RedatorAgent.run()` com LLM stubado (mock que retorna texto previsível por template).
     - Verificar: `PecaJuridicaContent` válido construído, `template` correto, `legal_citations` populado se aplicável, `addressee` populado quando aplicável, `AIJob.result` JSON-serializable.
   - Tabela paramétrica com 1 linha por template — fácil de estender quando templates novos forem adicionados.

2. **Smoke E2E** (manual ou semi-automatizado em `scripts/smoke_a2_redator.py`):
   - Rodar redator em **1 caso real por template** (com LLM real, contexto real do banco de teste).
   - Verificar: peça gerada faz sentido, PDF gera correto, citation evaluator marca/não marca review, AIJob persiste corretamente.
   - Documentar resultados em `docs/sprints/sprint_a2_redator_smoke.md`.

3. **Regressão**: rodar suite completa de testes pré-existentes (`pytest tests/`) e confirmar zero regressão.

**Não fazer agora:**
- Não rodar smoke contra produção. Banco de teste/staging.
- Não criar fixtures gigantes — minimizar setup em cada teste paramétrico.
- Não medir performance/latência — métrica vem em sprint própria de evaluation.

**Testes obrigatórios:**
- Bateria paramétrica verde para todos os templates servidos.
- Smoke E2E documentado em arquivo MD com timestamp + resultados por template.
- Suite completa do projeto verde (zero regressão).

**Critério de sucesso verificável:**
- `pytest tests/` 100% verde.
- `scripts/smoke_a2_redator.py` (ou equivalente) executa sem erro em todos os templates.
- Documento de smoke com observações por template.

**Commit:** `feat(sprint-a2-redator-C): smoke E2E + testes paramétricos`

---

## Sequenciamento

```
Tarefa A (migrar RedatorAgent)     → merge interno → 
Tarefa B (adaptar consumidores)    → merge interno → 
Tarefa C (smoke E2E + paramétrico) → fechar sprint
```

Sequencial. **Não há razão pra paralelizar** — A precede B (consumidores precisam saber o shape novo), B precede C (smoke testa o pipeline completo). Tentar paralelizar gera retrabalho.

Pode ser feito por 1 agente único — o mesmo que fechou A1 mantém o contexto e finaliza em 1-2 dias.

## Encerramento da sprint

Quando A, B, C estiverem completos:

1. Atualize `docs/progressoIA.md` com seção "Sprint A2-redator".
2. Crie `docs/sprints/sprint_a2_redator.md` documentando: o que foi entregue, decisões da Fase 0, dívidas remanescentes (se houver), próximo agente recomendado a migrar.
3. Imprima sumário na conversa: testes adicionados, commits, arquivos novos/modificados, resultado do smoke E2E por template.

## Próximas sprints previsíveis

- **Sprint A3** — Skills de domínio (`oficio_semad.md`, `prad.md`, `memorial_car.md`) quando os PDFs-gabarito da sócia chegarem. **Depende de operacional, não de código.** A2-redator deixa `PecaJuridicaContent` em uso, então skills carregam direto sem refator.
- **Sprint A2-extrator** — adoção de schema no ExtratorAgent. Sem urgência; sob demanda.
- **Sprint A2-diagnostico** — adoção de `DiagnosticoPreliminarContent` no DiagnosticoAgent. Mais valor que extrator porque diagnóstico é input pra peça.
- **Sprint Y** — Auditor de inconsistências C6, depende de `Property.geom` populado + parser shapefile.
- **Sprint W4** — OCR worker, paralela.

---

**Fim do prompt.** Cole tudo a partir de "# Sprint A2-redator — ..." em uma sessão do Claude Code aberta na raiz do projeto Regente Ambiental. **Fase 0 obrigatória — não autorize execução até receber o report estruturado em 4 blocos.**
