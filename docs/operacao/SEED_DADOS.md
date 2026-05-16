# Seed de Dados

**Documento:** Operação · seed local e de homologação
**Estado:** vivo · atualizar quando o seed mudar
**Última revisão:** 2026-05-15

---

Como popular um ambiente Regente com dados mínimos para desenvolvimento, demonstração e smoke test. Cobre seed automático no boot, seed de homologação e populador de caso para testes manuais.

## O que é seed

Seed é o **conjunto mínimo de dados** que torna o sistema utilizável para um humano logar e ver tela. Não substitui dados reais — substitui o vazio inicial.

O Regente tem **três caminhos de seed**:

| Caminho | Onde roda | Para que serve |
|---|---|---|
| `seed.py` | Automático no boot do API (Docker) | Dev local imediato |
| `ops/provision_homologation_tenant.py` | Manual em ambiente de homologação | Tenant pronto para demo |
| `scripts/populate_case.py` | Manual quando precisa | Caso completo para teste manual |

## Caminho 1 — `seed.py` automático

### O que cria

Quando o API sobe (via `docker compose up`), o script `seed.py` roda automaticamente. Cria:

| Entidade | Quantidade | Detalhe |
|---|---|---|
| `Tenant` | 1 | "Regente Demo" (idempotente — não duplica) |
| `User` | 4 | admin, consultor, cliente, campo |
| `Client` | 1 | cliente exemplo (PF) |
| `Process` | 1 | processo em estado `diagnostico` |
| `Task` | algumas | tarefas básicas para o Kanban |

### Idempotência

`seed.py` é **idempotente** — pode rodar quantas vezes quiser sem efeito colateral. Para cada entidade:

- Se já existe (`SELECT WHERE email = X`) → não cria, retorna existente
- Se não existe → cria

### Como o seed escolhe a senha

Lógica em `_seed_password(env_name, fallback)`:

1. Se `SEED_<USER>_PASSWORD` está definida no `.env` → usa esse valor
2. Se não está → gera determinístico: `<fallback_prefix>!<sha256(SECRET_KEY + env_name)[:10]>`

O determinístico tem duas funções:
- Senha previsível **dentro do mesmo `.env`** (mesmo `SECRET_KEY` → mesma senha)
- Senha **diferente entre ambientes** com SECRET_KEYs diferentes (não vaza dev → prod)

### Como recuperar a senha (modo determinístico)

```bash
docker compose exec api python -c "
from seed import _seed_password
print(_seed_password('SEED_ADMIN_PASSWORD', 'Seed@2026'))
"
```

### Recomendação para dev

Em `.env`:

```bash
SEED_ADMIN_PASSWORD=Seed@2026
SEED_CONSULTANT_PASSWORD=Seed@2026
SEED_CLIENT_PASSWORD=Seed@2026
SEED_FIELD_PASSWORD=Seed@2026
SEED_RESET_PASSWORDS=false
```

Senha previsível, fácil de logar em dev.

### `SEED_RESET_PASSWORDS=true` — quando usar

Por padrão, se um usuário já existe, o seed **preserva a senha atual** (mesmo que diferente). Útil quando você mudou a senha manualmente e não quer reverter.

Setando `SEED_RESET_PASSWORDS=true`, o seed **sobrescreve** a senha de todos os usuários seed para o valor configurado. Útil:

- Quando você perdeu a senha
- Quando vai entregar dev para outra pessoa e quer alinhar credenciais
- Reset de ambiente compartilhado

⚠️ **Nunca use em produção.** É bloqueado por validação implícita: produção não deveria ter `SEED_*` setado.

### Credenciais padrão (dev, com `Seed@2026`)

| Email | Perfil | Senha |
|---|---|---|
| `admin@regenteambiental.com.br` | superuser | `Seed@2026` |
| `consultor@regenteambiental.com.br` | consultor | `Seed@2026` |
| `cliente@regenteambiental.com.br` | cliente final (portal) | `Seed@2026` |
| `campo@regenteambiental.com.br` | equipe de campo | `Seed@2026` |

> Em ambientes anteriores ao rename, o domínio era `@amigao.com`. Atualizar `seed.py` faz parte da renomeação visível.

## Caminho 2 — `ops/provision_homologation_tenant.py`

### Para que serve

Provisiona um **tenant pronto para demonstração**: usuário admin do tenant, alguns clientes, propriedades com dados realistas, processos em vários estados, e (opcionalmente) skills do agente Redator carregadas.

Usado quando você vai mostrar o Regente para:
- Sócia validando fluxo
- Investidor / parceiro em demo
- Órgão público (SEMAD-GO) em piloto inicial

### Como rodar

```bash
docker compose exec api python ops/provision_homologation_tenant.py \
  --tenant-name "Consultoria Demo SP" \
  --admin-email "admin@consultoria-demo.com.br" \
  --admin-password "Demo@2026"
```

### O que faz

- Cria `Tenant` novo (não conflita com seed default)
- Cria admin do tenant
- Popula 5 clientes exemplo
- Popula 8 propriedades (em UFs variadas — SP, MG, GO, MT)
- Cria 3 processos: 1 em diagnóstico, 1 em execução, 1 aguardando órgão
- Cria tarefas do Kanban com prazos espalhados
- (Se IA habilitada) gera 2 documentos de exemplo via Extrator + 1 ofício pelo Redator

### Quando reusar / quando recriar

Cada execução cria um tenant **novo**. Não sobrescreve tenant existente. Para resetar tenant de homologação:

```bash
# Pelo banco
docker compose exec db psql -U postgres -d amigao_db -c \
  "UPDATE tenants SET is_active = false WHERE name = 'Consultoria Demo SP';"

# E rodar provisão de novo
```

> Não delete `Tenant` em cascata — `ON DELETE RESTRICT` em várias FKs impede. Sempre soft-delete via `is_active = false`.

## Caminho 3 — `scripts/populate_case.py`

### Para que serve

Popula **um caso específico completo** para teste manual de fluxo. Útil quando você está debugando um fluxo end-to-end e não quer fazer o intake manualmente toda vez.

### Como rodar

```bash
docker compose exec api python scripts/populate_case.py \
  --tenant-id 1 \
  --case-type "car_basico"
```

Tipos de caso disponíveis (ver `--help`):

| Tipo | O que cria |
|---|---|
| `car_basico` | Cliente + imóvel + CAR pendente + ofício SEMAD pronto |
| `notificacao_semad` | Caso com notificação recebida + prazo apertado |
| `prad_complexo` | Caso com PRAD + Reserva Legal + APP degradada |
| `exigencia_bancaria` | Caso vindo de banco com tomador + crédito condicionado |

## Seed do `knowledge_catalog` (RAG)

Não faz parte do `seed.py`. É carregado por scripts dedicados de ingestão:

```bash
# Federal canônicos (Lei 12.651/2012, LGPD, etc.)
docker compose exec api python scripts/ingest_federais_canonicos.py

# Estadual
docker compose exec api python scripts/ingest_legislacao_estadual.py --uf GO
docker compose exec api python scripts/ingest_legislacao_estadual.py --uf MS
docker compose exec api python scripts/ingest_legislacao_estadual.py --uf MT
```

> Em dev, considere baixar um snapshot do `knowledge_catalog` do ambiente de staging em vez de reingerir do zero. Reingestão custa em embeddings.

## Limpeza do ambiente

Quando você quer voltar ao zero:

```bash
# Apaga TUDO (banco, volumes, MinIO)
docker compose down -v

# Sobe limpo
docker compose up -d --build
```

⚠️ `-v` apaga volumes — seu banco vai embora. Em ambiente compartilhado, **avise antes**.

## Pendências e dívidas

1. **Seed de `Property.geom`** — todas as propriedades de seed nascem sem polígono. Cria atrito quando você está testando funcionalidade espacial. Roadmap: adicionar polígonos de exemplo no `populate_case.py`.
2. **Seed de `knowledge_catalog` para dev** — não há snapshot leve para dev rodar com base regulatória mínima sem pagar embeddings. Roadmap: snapshot fixture.
3. **Skills do Redator** — não vêm com seed. Após a sócia escrever (reunião 16/05), copiar para `app/skills/redator/` no repositório.

## Próximas leituras

- [`RUNBOOK_DEV.md`](./RUNBOOK_DEV.md) — setup geral de dev
- [`TESTING.md`](./TESTING.md) — fixtures usados em testes (diferente de seed)
- [`../arquitetura/MODELO_DE_DADOS.md`](../arquitetura/MODELO_DE_DADOS.md) — entidades populadas pelo seed
