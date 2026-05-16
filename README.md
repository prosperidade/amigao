# Regente Ambiental

> Sistema operacional da consultoria ambiental brasileira.
> Potencializa o consultor — não substitui.

---

## O que é

O Regente Ambiental é uma plataforma SaaS multi-tenant que organiza, automatiza e escala a operação de consultorias ambientais brasileiras. Nasce dentro de uma operação real (consultoria com anos de campo) e materializa o método dessa operação em software.

Cobre o fluxo completo do caso: entrada do cliente → diagnóstico → coleta documental → caminho regulatório → execução técnica → protocolo → acompanhamento → encerramento. Em cada etapa, há agentes de IA propondo, mas o consultor decide e assina — sempre.

## Princípios inegociáveis

1. **A IA propõe; o humano decide e assina.** Sem exceção em peças formais.
2. **Toda saída é auditável.** Hash chain SHA-256 encadeado, citação rastreável, origem do dado marcada.
3. **Cadastro é entrada. Diagnóstico é inteligência. Coleta é organização.** As três camadas são separadas por design.
4. **Multi-tenant desde o dia 1.** Isolamento de dados por `tenant_id` em toda query.
5. **Multi-provider de IA.** Nenhum fluxo depende de um único vendor (OpenAI, Gemini, Anthropic via LiteLLM).

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11 · FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · Celery |
| Banco | PostgreSQL 15 + PostGIS 3.3 · Redis 7 · pgvector 0.8 |
| Storage | MinIO (S3-compatible) |
| Frente consultor | React 18 + Vite + TypeScript + TailwindCSS |
| Frente cliente | Next.js 16 (congelado — retomada após validação do consultor) |
| Frente campo | Expo / React Native (congelado — idem) |
| IA | LiteLLM multi-provider · pgvector RAG · skills procedurais |
| Infra | Docker Compose |

## Estrutura do repositório

```
app/             Backend FastAPI (agentes, API, serviços, workers)
frontend/        Painel do consultor (React + Vite)
client-portal/   Portal do cliente final (congelado)
mobile/          App de campo offline (congelado)
alembic/         Migrations
docs/            Documentação (ver docs/README.md)
ops/             Scripts operacionais
scripts/         Scripts utilitários
tests/           Testes
```

## Subir local

```bash
# Tudo via Docker
docker compose up --build -d

# Backend isolado
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Worker Celery
celery -A app.core.celery_app worker --loglevel=info --pool=solo

# Painel consultor
cd frontend && npm install && npm run dev
```

Endpoints:
- API: `http://localhost:8000` · OpenAPI: `/docs` · Health: `/health` · Métricas: `/metrics`
- Painel: `http://localhost:5173`
- MinIO Console: `http://localhost:9001`

## Credenciais seed (dev)

- `admin@amigao.com` · `Seed@2026` (superuser)
- `consultor@amigao.com` · `Seed@2026`
- `cliente@amigao.com` · `Seed@2026`
- `campo@amigao.com` · `Seed@2026`

> Os e-mails do seed ainda usam o codinome técnico `amigao.com` enquanto a renomeação visível para `regenteambiental.com.br` está em execução. Ver [`docs/manifesto/02-IDENTIDADE.md`](docs/manifesto/02-IDENTIDADE.md) e [`docs/adr/004-regente-vs-amigao.md`](docs/adr/004-regente-vs-amigao.md). Quando a sprint de renomeação rodar, `seed.py` e este bloco serão atualizados juntos.

## Documentação

A documentação completa está em [`docs/README.md`](docs/README.md) e segue 5 camadas:

| Camada | Pra que serve |
|---|---|
| `docs/manifesto/` | Por que o produto existe, identidade, princípios, roadmap |
| `docs/arquitetura/` | Como o sistema é construído (referência técnica) |
| `docs/operacao/` | Como rodar, testar, fazer deploy, troubleshoot |
| `docs/estado/` | Onde estamos hoje (vivo, atualizado a cada sprint) |
| `docs/adr/` | Decisões arquiteturais importantes (imutáveis) |

## Regras de código

Ver [`CLAUDE.md`](CLAUDE.md) para regras de Python, TypeScript, segurança, multi-tenant, etc.

## Estado atual

Ver [`docs/estado/ESTADO_ATUAL.md`](docs/estado/ESTADO_ATUAL.md) para o instantâneo vivo.

---

**Nome técnico do repositório:** `regente-ambiental`
**Nome do produto:** Regente Ambiental
**Domínio:** [regenteambiental.com.br](https://regenteambiental.com.br)
