# [REVOGADO] 2026-04-23 — Abandono do MemPalace como backend de memória de agentes

**Status:** Revogado
**Data da revogação:** 2026-04-23
**Substituto planejado:** pgvector (Sprint U / Week 1) como backend único de memória do produto.

---

## Motivo

Diligência realizada em 2026-04-23 revelou **sinais fortes de supply-chain attack** no pacote PyPI `mempalace` (ver `requirements.txt` antes deste ADR, onde constava `mempalace>=3.0.0`):

- **49 mil stars em 18 dias** — estatisticamente implausível de forma orgânica; padrão de star-farming.
- **Wheel de 213 KB** incompatível com o escopo técnico prometido (framework completo de memória vetorial + knowledge graph + MCP).
- **Autor com metadata ofuscada** — ausência de verificação de identidade no perfil.
- **Primeira release com número alto (v2.0.0 / v3.0.0)** — padrão clássico de evasão de escrutínio, pulando a fase inicial em que a comunidade costuma auditar.
- **README com "scam alert" performativo** — aviso colocado pelo próprio autor como teatro de confiança.
- **Zero menções em código real de terceiros** em buscas em repositórios públicos independentes.

## Decisão

Abandonar o pacote. Não instalar nunca. Em particular:

- Remover `mempalace>=3.0.0` de `requirements.txt`.
- `pip uninstall -y mempalace` em todos os ambientes.
- Converter `app/agents/memory.py` em **stub no-op interno** (Opção A): mantém as assinaturas das funções `diary_write`, `diary_read`, `kg_add`, `kg_query`, `search`, `save_to_room`, `recall_agent_context`, `log_agent_execution`, `is_available`, mas nenhuma delas importa o pacote `mempalace` nem toca o disco. Todas retornam valores neutros (`None`, `[]`, `{"recent_diary": [], "search_results": []}`).
- Razão da Opção A (stub) em vez de deletar o arquivo: reduz superfície de mudança nesta Sprint Z (apenas 1 arquivo tocado + 1 dep removida + limpeza de infra), mantém os call sites dos 10 agentes e do `BaseAgent.run()` intactos, e dá uma superfície pronta para pluggar o pgvector como novo backend na Sprint U/Week 1 apenas substituindo o conteúdo de `memory.py`.
- Remover volume Docker `mempalace_data`, montagens em `/root/.mempalace` e o comando `python -m mempalace init` no entrypoint do `docker-compose.yml`.
- Apagar o diretório local `~/.mempalace/` (25 MB de dados gerados pelo pacote suspeito — potencialmente contaminados).
- Manter `pgvector` (Sprint U) como solução única de memória do produto quando implementado.

## Lição aprendida

Benchmarks e stars não substituem diligência técnica de dependência. Componentes de infra devem ser avaliados por:

1. **Idade do repo e histórico de commits por humanos** (não apenas bots).
2. **Cobertura independente** — menções em posts, vídeos, repos de terceiros.
3. **Tamanho técnico plausível** — um framework que promete KG + vetor + MCP servidor não cabe em 213 KB.
4. **Perfil do autor** — identidade verificável, histórico em outros projetos.
5. **Padrão de versionamento** — primeira release em v2.0+ é red flag.

## Dívida técnica registrada nesta decisão

A Opção A (stub no-op) deixa um **resíduo arquitetural** planejado para limpeza na próxima rodada:

### Cirurgia completa agendada (próximo sprint dedicado)

- Deletar `app/agents/memory.py` (stub inteiro).
- Remover o atributo de classe `palace_room` de cada um dos 10 agentes (`app/agents/{acompanhamento,atendimento,diagnostico,extrator,financeiro,legislacao,marketing,orcamento,redator,vigia}.py`).
- Remover o atributo default `palace_room: str = "agents_core"` de `BaseAgent` em `app/agents/base.py:112`.
- Remover os hooks `recall_memory`, `remember`, `remember_fact`, `_mempalace_log`, `_mempalace_log_failure`, `_build_ctx_summary` de `BaseAgent`.
- Remover as chamadas a `self._mempalace_log(...)` e `self._mempalace_log_failure(...)` do template method `run()` e do bloco de exceção.
- Remover as chamadas a `self.recall_memory(...)` de `app/agents/diagnostico.py:47-51` e `app/agents/legislacao.py:73-79`, e os blocos que anexam "DIAGNOSTICOS ANTERIORES SIMILARES" / "CASOS ANTERIORES SIMILARES" ao user_prompt.
- Apagar os testes que dependiam de MemPalace se houverem (varrer em `tests/`).

Essa cirurgia deve rodar **antes** de começar a Sprint U (pgvector como memória) para que o novo backend nasça em código limpo, não montado em cima de stub.

## Alternativas a avaliar quando o caso de uso de memória chegar

- **pgvector** (primeira escolha — plano Sprint U já previa isso).
- `mem0` ([mem0ai/mem0](https://github.com/mem0ai/mem0)).
- `letta` / MemGPT (caso a gente precise de hierarquia de memória com paginação contextual).
- MCP Memory Server oficial da Anthropic.

## Resíduo de storage local — cleanup pendente

Durante a execução da Sprint Z, o diretório `~/.mempalace/` tinha 25 MB em
`palace/` (embeddings Chroma) e ~70 KB em `knowledge_graph.sqlite3`. O subdiretório
`palace/` foi removido com sucesso. Os arquivos `knowledge_graph.sqlite3`,
`knowledge_graph.sqlite3-shm` e `knowledge_graph.sqlite3-wal` estavam travados por
processos Python externos (IDE, outro runtime com SQLite aberto) e não puderam ser
deletados no momento.

Para apagar o residual, rodar **após fechar IDEs/terminais Python** (incluindo os
que abriram `knowledge_graph.sqlite3` via Chroma):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/cleanup_mempalace_storage.ps1
```

O script é idempotente. O residual em si é inerte: com o pacote desinstalado,
nada no código consegue abrir ou escrever nesses arquivos mais.

## Distinção importante — NÃO confundir com outro pacote

Neste mesmo projeto foi instalado em 2026-04-23 o pacote **`claude-mem@thedotmack`** (plugin do Claude Code para registrar sessões de desenvolvimento). **Esse não é o mesmo pacote.** `claude-mem` vem de [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) (npm/GitHub, autor identificável, histórico de commits humano, escopo restrito a grabber de transcript), é instalado globalmente no Claude Code, não é dependência do backend do Amigão, e não é afetado por esta revogação.

## Relação com instalações externas

- A raiz do projeto **não contém** o pacote `mempalace` em sub-diretórios (verificado).
- A única referência a `mempalace` no código Python do produto é `app/agents/memory.py`, que passa a ser stub.

---

**Nota:** Este ADR permanece arquivado em `docs/adr/` como registro histórico da decisão. Se no futuro a comunidade demonstrar que o pacote era legítimo e os red flags eram falsos positivos, a reversão desta decisão exige novo ADR com evidências técnicas auditadas, não apenas "parece popular".
