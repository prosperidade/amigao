# Prompt de execução — Amigão do Meio Ambiente
## Sprints -1, 0 e 1 (Faxina → Ingestão de legislação → Infraestrutura SKILL.md)

**Audiência:** agentes do Claude Code operando no repositório.
**Data de emissão:** 2026-04-23.
**Commits-base:** `3b27516` (Sprint R) / `c33c4ad` (refino UI).
**Condições:** executar em ordem. Nenhum sprint começa sem o anterior ter passado nos critérios de aceite.

---

## 0. Contexto do sistema (leia antes de qualquer ação)

**Stack:** FastAPI + SQLAlchemy 2 + PostgreSQL 15 + PostGIS 3.3 + Redis + Celery + MinIO + litellm + MemPalace.

**Arquitetura dos agentes:**
- 10 agentes herdam de `BaseAgent` (`app/agents/base.py:103`).
- Todos usam `complete()` do `app/core/ai_gateway.py` com fallback OpenAI → Gemini → Claude Haiku.
- Apenas `LegislacaoAgent` sobrescreve provider preferido (Gemini 2.0 Flash via Sprint O).
- Prompts têm fallback hardcoded em `.py` (ex: `_FALLBACK_SYSTEM_PROMPT` em `app/services/llm_classifier.py`).
- `BaseAgent` já tem métodos `recall_memory()`, `remember()`, `remember_fact()` prontos.
- MemPalace é fire-and-forget: failures nunca quebram agentes.

**Estado real do banco (auditoria live de 2026-04-23):**
- 7 propriedades, **0 com `geom` preenchida**.
- 4 propostas (todas seed `accepted`), 4 contratos (todos seed `draft`).
- 24 jobs de IA em 18 dias, custo acumulado **$0.0035**.
- `legislation_documents`: **0 linhas**.
- MemPalace: 3471 embeddings, mas só **10 de diário de agentes** — todos `[INIT]` de 9 de abril.
- Knowledge Graph: **1 triple** (setup).
- **pgvector não instalado.** PostgreSQL 15 com PostGIS 3.3.4 apenas.

**Decisões arquiteturais já tomadas (não revisar neste ciclo):**
1. Gemini é provider default do agente `legislacao` (Sprint O).
2. Gateway multi-provider via litellm com fallback automático.
3. PostgreSQL 15 + PostGIS como banco único.
4. MemPalace local em `~/.mempalace/` (SQLite Chroma).
5. Skills ficam em **disco** (git para públicas, MinIO para do tenant) no V1. Migração para DB fica para V2.
6. SKILL.md é **compilado no system prompt na instanciação do agente**, não exposto como tool call dinâmica.

**Decisões pendentes que exigem PARADA do agente (veja seção 6):**
- Qual bloco das skills carregar primeiro na Sprint 1 (depende de amostras reais de ofícios).
- Ordem de ingestão dos diplomas na Sprint 0 (depende de lista curada pela sócia).

---

## 1. SPRINT -1 — FAXINA

**Objetivo:** corrigir três bugs/dívidas que invalidam decisões arquiteturais já tomadas. Sem isso, tudo depois é teórico.

**Tempo estimado:** 4-6h.

### 1.1 Tarefa A — Ativar Gemini de verdade

**Diagnóstico:** 100% dos $0.0035 gastos foram em `gpt-4o-mini` apesar da Sprint O ter definido Gemini como default do `legislacao`. A `GEMINI_API_KEY` provavelmente não está populada no `.env`, e o fallback chain cai para OpenAI.

**Ações:**
1. Verificar `.env` (e `.env.example`) para presença de `GEMINI_API_KEY`.
2. Se ausente no `.env.example`, adicionar com valor placeholder e documentação inline (formato `AIza...`, link para console Google AI Studio).
3. Adicionar um health-check no startup da aplicação (`app/main.py` ou `app/core/startup.py`) que logue em WARNING se `settings.LEGISLATION_USE_GEMINI_DEFAULT=True` mas `settings.GEMINI_API_KEY` estiver vazio. Log format: `[startup] Sprint O contract violated: LEGISLATION_USE_GEMINI_DEFAULT=True but GEMINI_API_KEY is empty. Legislation agent will fall back to OpenAI.`
4. Criar teste em `tests/core/test_ai_gateway.py` (ou arquivo existente) que valide a ordem do `_build_model_list()` quando todas as 3 keys estão populadas. Ordem esperada: OpenAI (default), Gemini (fallback), Claude Haiku (last resort).
5. Criar teste separado que valide que, quando `AI_DEFAULT_MODEL=gemini/gemini-2.0-flash`, a lista começa com Gemini.

**Critério de aceite:**
- Health-check roda no boot e loga corretamente.
- Testes novos passam.
- `docker compose up api` sobe sem erro e, se `.env` local não tiver Gemini, aparece o WARNING no log.
- **Não** alterar a chave em `.env` de produção/local do usuário — só garantir que o código detecta a ausência.

### 1.2 Tarefa B — Enforce `AI_MAX_COST_PER_JOB_USD`

**Diagnóstico:** `settings.AI_MAX_COST_PER_JOB_USD = 0.10` está declarado mas não há ponto de aplicação no `ai_gateway.complete()`. Quando a legislação começar a enviar 500K tokens ao Gemini, um job mal formatado pode custar $1-2 sozinho.

**Ações:**
1. No `app/core/ai_gateway.py`, após calcular `cost` via `litellm.completion_cost(...)`, adicionar validação:
   ```python
   if cost > settings.AI_MAX_COST_PER_JOB_USD:
       logger.error(
           "ai_gateway.complete cost exceeded max per job: cost=%.4f max=%.4f model=%s tokens_in=%d tokens_out=%d",
           cost, settings.AI_MAX_COST_PER_JOB_USD, attempt_model, tokens_in, tokens_out,
       )
       raise AIGatewayError(
           message=f"Job cost ${cost:.4f} exceeded max ${settings.AI_MAX_COST_PER_JOB_USD:.4f}",
           last_error=f"cost_exceeded model={attempt_model}",
       )
   ```
2. Garantir que a AIResponse **não** é retornada quando o custo estoura — o job deve ser registrado como `failed` com `error="cost_exceeded"` e o custo real registrado mesmo assim (para auditoria).
3. Criar teste em `tests/core/test_ai_gateway.py::test_cost_limit_per_job` usando mock do litellm que simula resposta com custo acima do limite.
4. Adicionar teste de integração em `tests/agents/test_base_agent.py` validando que o AIJob persiste com `status='failed'` quando cost_exceeded ocorre.

**Critério de aceite:**
- Testes passam.
- Logs mostram WARN/ERROR claro quando limite é tocado.
- Jobs falhos aparecem em `/api/v1/ai/jobs` com `error` legível.

### 1.3 Tarefa C — Corrigir bug do `search_legislation`

**Diagnóstico:** `app/services/legislation_service.py:122-209`. O parâmetro `demand_type` é aceito pela assinatura mas nunca aplicado na query. Isso está inócuo hoje (tabela vazia) mas quebra a Sprint 0 inteira se ficar assim.

**Ações:**
1. Adicionar filtro na query:
   ```python
   if demand_type:
       # PortableJSON com lista: checa se o demand_type está contido em demand_types
       q = q.filter(LegislationDocument.demand_types.contains([demand_type]))
   ```
   (Validar a sintaxe compatível com PortableJSON usado no projeto — pode precisar de `func.json_contains` ou adaptação conforme dialect PostgreSQL.)
2. Adicionar teste em `tests/services/test_legislation_service.py` com 3 docs fixture:
   - Doc A com `demand_types=["car", "retificacao_car"]`
   - Doc B com `demand_types=["licenciamento"]`
   - Doc C com `demand_types=NULL`
   - Query com `demand_type="car"` deve retornar só A.
   - Query sem `demand_type` deve retornar A, B, C.
3. Manter docs com `demand_types=NULL` **fora** do filtro quando `demand_type` é especificado (evita entregar diploma genérico quando há especializado).

**Critério de aceite:**
- Teste passa.
- Nenhuma chamada existente quebra (já que hoje o argumento era ignorado).

### 1.4 Tarefa D — Resolver dívida do `Document.extracted_text`

**Diagnóstico:** `app/agents/extrator.py:46-58` busca `Document.extracted_text` do banco, mas o campo não existe no model `Document`. Isso é bug silencioso — hoje só não quebra porque o fluxo sempre passa `text` direto em `metadata`.

**Ações:**
1. Inspecionar `app/models/document.py`. Confirmar ausência do campo.
2. Criar migration Alembic adicionando `extracted_text Text nullable` e `extracted_at DateTime nullable`.
3. Atualizar model e schema Pydantic do documento.
4. Alterar o fluxo de `POST /documents/confirm-upload` para salvar `extracted_text` quando OCR/parse roda.
5. Teste: subir documento, verificar que `extracted_text` é populado, rodar extrator sem passar `text` em metadata, confirmar que ele busca do banco.

**Critério de aceite:**
- Migration aplica limpa.
- Extrator funciona com `document_id` só, sem `text` em metadata.
- Teste novo passa.

### 1.5 Marco Sprint -1

Antes de avançar para Sprint 0, executar:
```bash
docker compose down -v
docker compose up -d db
alembic upgrade head
pytest tests/ -x
docker compose up -d
curl http://localhost:8000/api/v1/agents/budget  # deve responder sem 500
```

Se tudo verde: marcar Sprint -1 concluída e avisar o usuário antes de começar Sprint 0. Se vermelho: **parar e reportar**.

---

## 2. SPRINT 0 — INGESTÃO DE LEGISLAÇÃO

**Objetivo:** popular `legislation_documents` com um corpus mínimo viável. **Este é o destravamento arquitetural mais importante do sistema.** Sem isso, o agente `legislacao` alucina com conhecimento genérico do LLM e todo o restante da plataforma é fachada.

**Tempo estimado:** 20h (80% é curadoria de texto, 20% é código).

### 2.1 PARE E PERGUNTE — antes de começar

Solicite ao usuário a **lista curada de diplomas prioritários**. Sugestão de template (enviar ao usuário para preencher):

```
FEDERAL (mínimo viável):
- [ ] Lei 12.651/2012 (Código Florestal)
- [ ] Lei 9.605/1998 (Crimes Ambientais)
- [ ] Lei 9.985/2000 (SNUC)
- [ ] Lei 6.938/1981 (Política Nacional do Meio Ambiente)
- [ ] Resolução CONAMA 001/1986 (EIA/RIMA)
- [ ] Resolução CONAMA 237/1997 (Licenciamento)
- [ ] Resolução CONAMA 369/2006 (APP)
- [ ] Decreto 7.830/2012 (SICAR)
- [ ] Decreto 8.235/2014 (PRA)
- [ ] Lei Complementar 140/2011 (competências)

ESTADUAL GO (foco inicial da sócia):
- [ ] Lei Estadual 18.102/2013 (Política de Meio Ambiente GO)
- [ ] Decreto GO 1.745/2019 (SEMAD)
- [ ] Instruções Normativas SEMAD relevantes
- [ ] ...

ESTADUAL MT (relevante pelos seeds atuais):
- [ ] ...

ESTADUAL MS:
- [ ] ...

Para cada diploma, solicitar:
- URL oficial (planalto.gov.br, al.go.gov.br, etc.)
- demand_types aplicáveis (escolher de: car, retificacao_car, licenciamento, regularizacao_fundiaria, outorga, defesa, compensacao, exigencia_bancaria)
- agency (IBAMA, SEMAD, SEMA, ICMBio, etc.)
```

**Não iniciar a Sprint 0 sem essa lista.**

### 2.2 Tarefa A — Script de ingestão manual

Criar `scripts/ingest_legislation.py` (CLI) com a assinatura:

```bash
python scripts/ingest_legislation.py \
  --url "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12651.htm" \
  --title "Código Florestal" \
  --identifier "Lei 12.651/2012" \
  --scope federal \
  --source-type lei \
  --agency "Congresso Nacional" \
  --effective-date "2012-05-25" \
  --demand-types car,retificacao_car,compensacao \
  --dry-run   # opcional: valida parsing mas não salva
```

**Pipeline interno:**
1. `httpx.get(url)` com timeout agressivo.
2. Detectar tipo (HTML planalto, PDF, texto bruto).
3. Extrair texto limpo (sem menu, sem navegação, sem rodapé):
   - Planalto: parser BeautifulSoup focado no body com heurísticas específicas do site.
   - PDF: `pypdf` ou `pdfplumber` (já disponível?) com fallback para OCR via `pytesseract` se for imagem.
4. Computar `token_count` via `len(text) // 4` (consistente com `_estimate_tokens`).
5. Salvar em `legislation_documents` com `status='indexed'`, `full_text=text`, `content_hash=sha256(text)`.
6. Se já existe doc com mesmo `identifier` + `content_hash`, skip com log. Se mesmo `identifier` mas hash diferente, criar nova versão (manter antiga como `status='superseded'` com `revoked_at=now()`).

**Critério de aceite:**
- Script roda 10 diplomas federais da lista sem intervenção manual.
- Texto extraído é inspecionável (salvar em `/tmp/legislation_preview/{identifier}.txt` antes de salvar no DB).
- `SELECT COUNT(*) FROM legislation_documents WHERE status='indexed'` > 0.

### 2.3 Tarefa B — Validar que o agente legislacao consome o corpus

Com ao menos 5 diplomas ingeridos:

1. Rodar via `/agents/run` manual:
   ```json
   {
     "agent_name": "legislacao",
     "metadata": {
       "query": "Posso fazer supressão de vegetação em APP para atividade de interesse social?",
       "demand_type": "licenciamento",
       "state": "GO"
     }
   }
   ```
2. Verificar no log que `legislation_context` não está vazio.
3. Verificar no `ai_jobs.tokens_in` que o contexto foi enviado (>10K tokens).
4. Verificar que `raw_output` cita artigos específicos (ex: "Art. 8º da Lei 12.651/2012").
5. Se Gemini key está populada, verificar `model_used='gemini/gemini-2.0-flash'`. Se não, documentar o fallback observado.

### 2.4 Tarefa C — Reativar crawlers Celery Beat

Crawlers já agendados em `app/core/celery_app.py`:
- `monitor-legislation-dou-daily` (06:00 BRT)
- `monitor-legislation-doe-daily` (06:30 BRT)
- `monitor-legislation-agencies-weekly` (segunda 03:00)

**Ações:**
1. Validar que `app/workers/legislation_tasks.py` está implementado (ou criar stub funcional com log).
2. Se crawler DOU/DOE não existe ainda, **não implementar nesta sprint** — só documentar em issue `@TODO Sprint 0.1`. Crawlers oficiais exigem tratamento especial de JusBrasil/IN/portais gov que vai consumir 20h sozinho.
3. Focar a Sprint 0 em ingestão manual via CLI. Crawling automatizado fica para depois.

### 2.5 Marco Sprint 0

- 20-30 diplomas federais + estaduais GO ingeridos.
- Teste manual do agente `legislacao` retorna citação com artigo específico.
- `/api/v1/legislation/documents` (se existir endpoint) lista o corpus.
- Custo acumulado observado em `ai_jobs` depois de ~5 chamadas reais do `legislacao` cabe dentro do `AI_MAX_COST_PER_JOB_USD=0.10` (se não, reportar antes de prosseguir).

---

## 3. SPRINT 1 — INFRAESTRUTURA SKILL.md

**Objetivo:** introduzir camada procedural (skills) que encapsula "como fazer as tarefas" de cada agente. Skills são consumidas em system prompt compilado na instanciação do agente.

**Tempo estimado:** 16h.

**Pré-condições:**
- Sprint -1 concluída (Gemini ativo, cost control enforced).
- Sprint 0 concluída com pelo menos 20 diplomas ingeridos (skills de `legislacao` e `redator` dependem de RAG funcional, mesmo que rudimentar).

### 3.1 PARE E PERGUNTE — antes de começar

Solicite ao usuário:
1. 2-3 PDFs de ofícios "bem feitos" da sócia (que ela usaria como gabarito).
2. Confirmação das 2 decisões arquiteturais abaixo (default sugerido — só prosseguir se usuário confirmar):

**Decisão 1:** Skills públicas em `app/skills/public/` no git. Skills do tenant em MinIO sob a chave `skills/{tenant_id}/{agent}/{skill_name}.md`. **Não** criar tabela `skills` no Postgres no V1.

**Decisão 2:** Skills são compiladas no `system_prompt` no momento da instanciação do `BaseAgent`. O LLM não chama `skill_load()` dinamicamente. Se uma skill não existe para o tenant, fallback para pública; se pública não existe, fallback para o prompt atual (comportamento idêntico a hoje).

**Não iniciar a Sprint 1 sem confirmação dessas duas decisões.**

### 3.2 Tarefa A — Estrutura e formato de skill

Criar estrutura:
```
app/skills/
  public/
    redator/
      SKILL.md               # índice: lista todas as skills disponíveis
      oficio_semad.md        # skill individual
      memorial_car.md
    extrator/
      SKILL.md
      matricula_generica.md
      car_sicar.md
```

**Formato do SKILL.md índice (exemplo `app/skills/public/redator/SKILL.md`):**

```markdown
# Skills do agente Redator

Este arquivo lista as skills procedurais disponíveis para o agente Redator.
Cada skill é um arquivo .md nesta mesma pasta, carregado via skill_registry.

## Skills

### oficio_semad.md
- **name:** oficio_semad
- **version:** 1.0
- **description:** Ofício formal para SEMA/SEMAD estaduais. Cabeçalho + referência processual + fundamentação legal + fechamento.
- **when_to_use:** metadata.document_template in ["oficio","resposta_notificacao"] AND órgão_competente contém "SEMA" ou "SEMAD".
- **consumes:** recall MemPalace (oficios_semad_anteriores) + RAG legislação (estadual + UF do caso).

### memorial_car.md
- **name:** memorial_car
- **version:** 1.0
- **description:** Memorial descritivo de imóvel para submissão/retificação no SICAR.
- **when_to_use:** metadata.document_template in ["memorial"] AND demand_type in ["car","retificacao_car"] AND property.geom IS NOT NULL.
- **consumes:** property.geom, extractor_data.area_hectares, client.cpf.
```

**Formato de skill individual (exemplo `app/skills/public/redator/oficio_semad.md`):**

```markdown
---
name: oficio_semad
version: 1.0
agent: redator
applicable_when:
  document_template: [oficio, resposta_notificacao]
  agency_contains: [SEMA, SEMAD]
---

# Ofício SEMA/SEMAD

## Pre-execução
Antes de redigir, o agente já recebeu no contexto:
- recall_memory com oficios similares anteriores (quando existirem)
- search_legislation filtrado por UF + agency + demand_type

Se algum destes estiver ausente, sinalize no campo `notes` do output.

## Estrutura obrigatória

### 1. Cabeçalho
[Razão social do escritório], CNPJ [xxx], endereço [xxx].
Local, DD de mmmm de AAAA.

### 2. Destinatário
À/Ao [órgão específico — ex: Secretaria de Meio Ambiente do Estado de Goiás — SEMAD-GO]
A/C [nome ou cargo do destinatário, se conhecido]
Ref.: Processo nº [process.numero_processo]

### 3. Abertura
"Em atenção à [tipo de notificação] nº X, de DD/MM/AAAA, referente ao processo em epígrafe, vem o(a) requerente, [razão social/nome], por meio de seu representante técnico abaixo assinado, apresentar..."

### 4. Corpo
- Parágrafo 1: contextualização do processo.
- Parágrafos seguintes: resposta item por item da exigência. Cada item deve começar com "Quanto ao item X..." e fechar com referência legal.
- Parágrafo final: requerimento.

### 5. Fundamentação legal
Citar APENAS artigos presentes no `legislation_context` fornecido. Formato: "nos termos do art. X, [§ Y,] da [Lei/Decreto/Resolução] nº N/AAAA".
É proibido citar lei sem número, ou invocar "legislação pertinente" sem especificar.

### 6. Fechamento
"Diante do exposto, requer a V. Sa. [pedido específico]."
"Termos em que, pede deferimento."
"[Nome do responsável técnico]"
"[Registro profissional — CREA/CAU/OAB, se aplicável]"

## Tom e vocabulário
- Formal, sem rebuscamento.
- Primeira pessoa do plural ("apresentamos", "requeremos") quando há procuração.
- Terceira pessoa ("o requerente apresenta") quando cliente assina diretamente.
- NUNCA prometer prazos que dependem do órgão.
- NUNCA afirmar fatos não documentados.

## Validação antes de retornar
- [ ] Todo artigo citado aparece no `legislation_context`?
- [ ] Todo item da exigência foi respondido?
- [ ] Há assinatura/responsável técnico identificado?
- [ ] `requires_review=True` no output.
```

### 3.3 Tarefa B — Skill registry

Criar `app/skills/registry.py`:

```python
"""
Skill registry — carrega skills públicas (disco) e do tenant (MinIO).

Cache em memória por 5min. Fallback sempre: tenant → public → None.
"""
from __future__ import annotations
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PUBLIC_SKILLS_DIR = Path(__file__).parent / "public"
TENANT_SKILLS_PREFIX = "skills/"  # prefixo MinIO


class SkillRegistry:
    def __init__(self, minio_client=None):
        self.minio = minio_client

    def get_index(self, agent_name: str, tenant_id: int | None = None) -> str:
        """Retorna o SKILL.md do agente, preferindo tenant sobre público."""
        if tenant_id and self.minio:
            tenant_path = f"{TENANT_SKILLS_PREFIX}{tenant_id}/{agent_name}/SKILL.md"
            content = self._load_minio(tenant_path)
            if content:
                return content

        public_path = PUBLIC_SKILLS_DIR / agent_name / "SKILL.md"
        if public_path.exists():
            return public_path.read_text(encoding="utf-8")

        return ""  # fallback: sem skills

    def get_skill(self, agent_name: str, skill_name: str, tenant_id: int | None = None) -> Optional[str]:
        """Retorna o conteúdo de uma skill específica."""
        if tenant_id and self.minio:
            tenant_path = f"{TENANT_SKILLS_PREFIX}{tenant_id}/{agent_name}/{skill_name}.md"
            content = self._load_minio(tenant_path)
            if content:
                return content

        public_path = PUBLIC_SKILLS_DIR / agent_name / f"{skill_name}.md"
        if public_path.exists():
            return public_path.read_text(encoding="utf-8")

        return None

    def list_skills(self, agent_name: str, tenant_id: int | None = None) -> list[str]:
        """Lista nomes de skills disponíveis (tenant + public, sem duplicar)."""
        skills: set[str] = set()
        public_dir = PUBLIC_SKILLS_DIR / agent_name
        if public_dir.exists():
            for f in public_dir.glob("*.md"):
                if f.name != "SKILL.md":
                    skills.add(f.stem)
        if tenant_id and self.minio:
            try:
                objects = self.minio.list_objects(
                    prefix=f"{TENANT_SKILLS_PREFIX}{tenant_id}/{agent_name}/"
                )
                for obj in objects:
                    name = obj.object_name.split("/")[-1].removesuffix(".md")
                    if name and name != "SKILL":
                        skills.add(name)
            except Exception as exc:
                logger.debug("skill_registry.list minio error: %s", exc)
        return sorted(skills)

    def _load_minio(self, path: str) -> Optional[str]:
        if not self.minio:
            return None
        try:
            obj = self.minio.get_object(path)
            return obj.read().decode("utf-8")
        except Exception:
            return None


# Singleton global
_registry: SkillRegistry | None = None

def get_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        from app.services.storage import get_minio_client  # noqa: PLC0415
        _registry = SkillRegistry(minio_client=get_minio_client())
    return _registry
```

### 3.4 Tarefa C — Integração no BaseAgent

Alterar `app/agents/base.py` para compilar skills no system prompt:

```python
# Adicionar ao __init__ ou execute():
def _build_system_prompt_with_skills(self) -> str:
    """Compila o system prompt base + índice de skills + skill específica (se aplicável)."""
    from app.skills.registry import get_registry  # noqa: PLC0415
    base_prompt = self.get_prompt(f"{self.name}_system") or self._default_system

    registry = get_registry()
    skill_index = registry.get_index(self.name, tenant_id=self.ctx.tenant_id)

    if not skill_index.strip():
        return base_prompt

    # Tenta resolver skill específica via metadata
    skill_hint = self.ctx.metadata.get("skill") if self.ctx.metadata else None
    skill_content = ""
    if skill_hint:
        skill_content = registry.get_skill(self.name, skill_hint, tenant_id=self.ctx.tenant_id) or ""

    parts = [base_prompt, "\n\n=== SKILLS DISPONÍVEIS ===\n", skill_index]
    if skill_content:
        parts.extend(["\n\n=== SKILL ATIVA ===\n", skill_content])
    return "".join(parts)
```

Atualizar agentes que hoje fazem `system_prompt = self.get_prompt("xxx_system")` para usarem `self._build_system_prompt_with_skills()`.

**IMPORTANTE:** manter o fallback antigo funcionando. Se a pasta de skills não existir, comportamento é idêntico ao atual. Zero quebra retroativa.

### 3.5 Tarefa D — Primeira skill completa: redator/oficio_semad

Usando os PDFs reais fornecidos pelo usuário (ver 3.1):

1. Extrair manualmente o padrão estrutural dos 2-3 ofícios.
2. Destilar em `app/skills/public/redator/oficio_semad.md` seguindo o template da seção 3.2.
3. Criar `app/skills/public/redator/SKILL.md` com esta skill no índice.

**Teste manual:**
```bash
curl -X POST http://localhost:8000/api/v1/agents/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "redator",
    "metadata": {
      "document_template": "oficio",
      "skill": "oficio_semad",
      "client_data": {"name": "Fazenda Teste LTDA", "cpf_cnpj": "12.345.678/0001-90"},
      "property_data": {"name": "Fazenda Teste", "state": "GO", "municipality": "Goiânia"},
      "instructions": "Responder notificação da SEMAD-GO nº 123/2026 sobre pendência de PRAD"
    }
  }'
```

Validar que o output respeita a estrutura da skill.

### 3.6 Marco Sprint 1

- Pelo menos 3 skills de `redator` criadas (oficio_semad, memorial_car, prad).
- Pelo menos 2 skills de `extrator` criadas (matricula_generica, car_sicar).
- Registry resolvendo tenant > public corretamente (com teste de integração).
- BaseAgent compilando skill no system prompt sem quebrar agentes sem skill.
- Teste manual do `redator` com skill ativa retorna output dentro da estrutura.

---

## 4. O QUE NÃO FAZER NESTE CICLO

**Sob hipótese alguma iniciar:**
1. Instalação de pgvector. Fica para Sprint 3, depois de SKILL.md validado.
2. Ativação de recall do MemPalace nos 8 agentes passivos. Fica para Sprint 2, depois que houver corpus real de diário.
3. Parse de shapefile / overlays PostGIS. Fica para Sprint 4.
4. Migração Docker para imagem com pgvector. Amarrado à Sprint 3.
5. Qualquer refactor não solicitado aqui.
6. Reescrita do gateway LiteLLM.
7. UI/frontend nesta rodada.
8. Crawlers automatizados DOU/DOE — só ingestão manual via CLI (ver 2.4).

---

## 5. REGRAS DE EXECUÇÃO

1. **Ordem é lei.** Sprint 0 não começa antes de Sprint -1 passar em todos os critérios de aceite. Sprint 1 não começa antes de Sprint 0.

2. **Parar e perguntar em 2 pontos:**
   - Antes da Sprint 0: lista curada de diplomas (seção 2.1).
   - Antes da Sprint 1: confirmação das duas decisões arquiteturais + PDFs de ofícios-gabarito (seção 3.1).

3. **Qualquer mudança em migration, schema, ou contrato de API externo: parar e pedir confirmação.**

4. **Cada sprint termina com:**
   - Testes verdes (`pytest tests/ -x`).
   - Lint verde (`ruff check .`).
   - Type check verde (`mypy app/`) se configurado.
   - Smoke test manual descrito no marco da sprint.
   - Commit com mensagem `feat(sprint-X): <resumo>` ou `fix(sprint-X): <resumo>`.

5. **Fire-and-forget em tudo que toca MemPalace.** Falhas em MemPalace nunca quebram fluxo principal.

6. **Não assumir que a GEMINI_API_KEY está populada.** Se estiver, use. Se não, deixe o código detectar e logar corretamente.

7. **Não criar skills sobre tipos de documentos que não existem nos seeds.** Se a sócia não forneceu exemplo real, sinalize em TODO e não chute o formato.

8. **Documentar tudo em `docs/sprints/sprint_minus1.md`, `sprint_0.md`, `sprint_1.md`** ao final de cada uma.

---

## 6. PERGUNTAS QUE EXIGEM PARADA OBRIGATÓRIA

Sempre que bater em uma destas, **parar e aguardar resposta do usuário antes de prosseguir**:

1. Lista curada de diplomas para ingestão (seção 2.1).
2. PDFs-gabarito de ofícios reais (seção 3.1).
3. Confirmação das duas decisões arquiteturais da Sprint 1 (seção 3.1).
4. Qualquer migration Alembic que toque em tabela com dados de produção.
5. Qualquer alteração que afete o formato de `AIJob.result` (quebra backward compat).
6. Qualquer erro persistente em teste que exija mudar expectativa em vez de corrigir código.

---

## 7. ORDEM DE CUTTING (se o tempo apertar)

Se o ciclo precisar ser cortado pela metade, cortar nesta ordem:

1. Primeiro a sair: Sprint 1 Tarefa D (skills de extrator). Mantém só redator.
2. Depois: Sprint 0 Tarefa C (crawlers — já está marcado como fora de escopo, reforçar).
3. Depois: Sprint -1 Tarefa D (Document.extracted_text). Se não tiver bug ativo bloqueando fluxo, pode ir para sprint seguinte.

**Nunca cortar:**
- Sprint -1 Tarefa A (Gemini) — invalida Sprint O inteira.
- Sprint -1 Tarefa B (cost control) — risco financeiro.
- Sprint 0 Tarefa A (script de ingestão) — sem ele, nada da camada legislativa funciona.

---

**Fim do prompt.**

Qualquer desvio deste documento deve ser reportado ao usuário antes de ser executado.
