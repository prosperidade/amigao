# ADR-003 · MemPalace abandonado como backend de memória de agentes [REVOKED]

**Status:** **REVOGADO** (substituído por pgvector — ver [`./005-pgvector-rag.md`](./005-pgvector-rag.md))
**Data da revogação:** 2026-04-23
**Substituto:** pgvector como backend único de memória/RAG do produto (entregue na Sprint U)
**Cirurgia final:** executada em 2026-05-15 (limpeza de stub no-op + referências)

---

## Contexto

Durante a evolução inicial dos agentes IA (Sprints IA-1 a IA-4, março-abril/2026), buscamos um backend leve para memória episódica e knowledge graph dos agentes — algo que servisse para `recall_memory()` ("o que esse agente já viu sobre este caso?") e `remember_fact()` ("registrar este aprendizado").

O pacote PyPI `mempalace>=3.0.0` foi considerado pelo conjunto de promessas: memória vetorial + knowledge graph + servidor MCP, tudo num pacote único. Foi instalado e integrado em todos os 10 agentes (`palace_room` por agente, hooks `_mempalace_log` no `BaseAgent.run()`).

Em **2026-04-23**, diligência técnica revelou **sinais fortes de supply-chain attack** no pacote:

- **49 mil stars em 18 dias** — estatisticamente implausível de forma orgânica; padrão de star-farming
- **Wheel de 213 KB** incompatível com escopo prometido (framework completo de KG + vector + MCP server)
- **Autor com metadata ofuscada** — ausência de identidade verificável
- **Primeira release com número alto (v2.0.0 / v3.0.0)** — padrão de evasão de escrutínio
- **README com "scam alert" performativo** — teatro de confiança
- **Zero menções em código real de terceiros** em buscas independentes

## Decisão

**Abandonar o pacote integralmente.** Não instalar nunca. Substituir por pgvector como backend único de memória/RAG do produto.

Plano de execução em duas fases:

### Fase 1 — Stub no-op (executada em 2026-04-23)

Para reduzir superfície de mudança na sprint de remoção emergencial:

- Remover `mempalace>=3.0.0` de `requirements.txt`
- `pip uninstall -y mempalace` em todos os ambientes
- Converter `app/agents/memory.py` em **stub no-op**: mantém assinaturas das funções (`diary_write`, `diary_read`, `kg_add`, `kg_query`, `search`, `save_to_room`, `recall_agent_context`, `log_agent_execution`, `is_available`), mas nenhuma importa o pacote nem toca disco. Todas retornam valores neutros.
- Remover volume Docker `mempalace_data`, montagens em `/root/.mempalace` e comando `python -m mempalace init` do entrypoint
- Apagar diretório local `~/.mempalace/` (25 MB potencialmente contaminados)

### Fase 2 — Cirurgia final (executada em 2026-05-15)

Excisão completa do resíduo arquitetural:

- Deletar `app/agents/memory.py` (stub inteiro)
- Remover atributo `palace_room` de cada um dos 10 agentes
- Remover atributo default `palace_room: str = "agents_core"` de `BaseAgent`
- Remover hooks `recall_memory`, `remember`, `remember_fact`, `_mempalace_log`, `_mempalace_log_failure`, `_build_ctx_summary` de `BaseAgent`
- Remover chamadas a `self._mempalace_log(...)` e `self._mempalace_log_failure(...)` no template method `run()` e bloco de exceção
- Remover chamadas a `self.recall_memory(...)` de `app/agents/diagnostico.py` e `app/agents/legislacao.py`, e blocos que anexavam "DIAGNOSTICOS ANTERIORES SIMILARES" / "CASOS ANTERIORES SIMILARES" ao user_prompt
- Apagar `mempalace.yaml` e `entities.json` da raiz
- Apagar `scripts/cleanup_mempalace_storage.ps1`
- Limpar referências em docs ativos

## Lições aprendidas

Benchmarks e stars não substituem diligência técnica de dependência. Componentes de infraestrutura crítica devem ser avaliados por:

1. **Idade do repo e histórico de commits por humanos** (não bots)
2. **Cobertura independente** — menções em posts, vídeos, repos de terceiros não-relacionados
3. **Tamanho técnico plausível** — promessa de KG + vetor + MCP server não cabe em 213 KB de wheel
4. **Perfil do autor** — identidade verificável, histórico em outros projetos
5. **Padrão de versionamento** — primeira release em v2.0+ é red flag

Essas lições viraram processo interno: nenhuma dependência crítica entra sem checklist desses 5 pontos.

## Distinção importante (não confundir)

No mesmo dia (2026-04-23) foi instalado o pacote **`claude-mem@thedotmack`** (plugin do Claude Code para registrar sessões). **Não é o mesmo pacote.** `claude-mem` vem de `thedotmack/claude-mem` (npm/GitHub), autor identificável, histórico de commits humano, escopo restrito a grabber de transcript. Instalado globalmente no Claude Code, **não é dependência do backend do Regente**, não é afetado por esta revogação.

## Substituto: pgvector

A necessidade original (memória semântica para agentes) foi substituída por **busca semântica no `knowledge_catalog`** via pgvector. Diferenças:

| Aspecto | MemPalace (revogado) | pgvector (atual) |
|---|---|---|
| Modelo de memória | Episódica + KG por agente | Catálogo vetorial unificado |
| Storage | SQLite local + Chroma | PostgreSQL + extensão pgvector |
| Backup | Volume Docker isolado | Backup unificado do Postgres |
| Audit | Próprio (não integrado) | `KnowledgeChunk` + `AIJob` |
| Origem do conhecimento | Auto-aprendido por agente | Curado (legislação, ofícios, manuais, skills) |
| Multi-tenant | Por `palace_room` | `tenant_id` (NULL = global) |

A decisão implícita foi: **memória de agente não é prioridade**; **base de conhecimento curada** sim. Detalhes em [`./005-pgvector-rag.md`](./005-pgvector-rag.md).

## Status

✅ **Cirurgia completa.** Nenhuma menção funcional ao MemPalace permanece no código ativo do Regente. Este ADR fica como registro histórico.

Reversão (improvável): exigiria novo ADR com evidências técnicas auditadas de que os red flags de 2026-04-23 eram falsos positivos, não apenas alegação de popularidade.
