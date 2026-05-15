# Estratégia de Versionamento da API
**Projeto:** Plataforma Ambiental SaaS  
**Versão:** 1.0  
**Data:** 26/03/2026

---

## 1. Por que esse documento existe

Toda a API está definida como `/api/v1/`. Quando a v2 aparecer — e ela vai aparecer, especialmente no momento da expansão white-label e GovTech — tenants que já integraram na v1 não podem ter o sistema quebrado por uma migração silenciosa.

Definir a estratégia agora, antes que exista um segundo tenant, custa praticamente nada. Definir depois custa meses de retrabalho.

---

## 2. Estratégia adotada: versionamento por prefixo de URL

```
/api/v1/clients
/api/v2/clients   ← quando v2 existir
```

**Por que prefixo de URL (e não header ou query param):**
- Mais simples para testar e debugar
- Visível nos logs sem configuração especial
- Padrão mais adotado no ecossistema FastAPI
- Fácil de documentar no Swagger/OpenAPI

---

## 3. Ciclo de vida de uma versão

```
                    VERSÃO DA API
                    
  [launch]  ──►  [active]  ──►  [deprecated]  ──►  [retired]
  
  v1 lançada    v1 em uso      v1 marcada           v1 removida
  hoje          normalmente    como antiga          do servidor
```

| Fase | Descrição | Duração mínima |
|------|-----------|----------------|
| `active` | Versão atual, suporte completo | — |
| `deprecated` | Ainda funciona, mas com aviso. Nova versão disponível | 6 meses |
| `retired` | Removida do servidor | — |

**Regra:** Uma versão nunca vai de `active` direto para `retired`. Sempre passa por `deprecated` com no mínimo 6 meses de aviso.

---

## 4. Quantas versões simultâneas

**Política:** Suporte simultâneo para no máximo 2 versões.

```
Situação atual:    v1 (active)
Quando v2 chegar:  v1 (deprecated) + v2 (active)
Quando v3 chegar:  v1 (retired)    + v2 (deprecated) + v3 (active)
```

Nunca haverá v1 + v2 + v3 ativos ao mesmo tempo.

---

## 5. O que é uma breaking change

**Breaking change** é qualquer mudança que quebra um cliente existente sem alteração no código dele:

| É breaking change | NÃO é breaking change |
|---|---|
| Remover um campo do response | Adicionar campo opcional ao response |
| Renomear um campo | Adicionar novo endpoint |
| Mudar tipo de um campo (string → int) | Tornar um campo obrigatório → opcional |
| Mudar semântica de um status | Adicionar novo valor a um enum |
| Remover um endpoint | Melhorar mensagem de erro |
| Mudar autenticação obrigatória | Adicionar novo método de autenticação |

**Regra:** Qualquer breaking change → novo número de versão maior (v1 → v2).

**Regra:** Mudanças não-breaking podem ser feitas em v1 sem novo versionamento.

---

## 6. Como comunicar deprecação

### 6.1 Header de aviso nas respostas

Quando uma versão entra em `deprecated`, todas as respostas passam a incluir:

```http
HTTP/1.1 200 OK
Deprecation: true
Sunset: Sat, 01 Mar 2027 00:00:00 GMT
Link: <https://docs.plataforma.com.br/api/v2>; rel="successor-version"
```

### 6.2 Notificação por e-mail

- E-mail para o admin de cada tenant no momento da marcação como deprecated
- Lembretes automáticos: 3 meses antes, 1 mês antes, 2 semanas antes do sunset

### 6.3 No painel de configurações

- Banner visível para admins: "A API v1 será descontinuada em [data]. Migre para v2."
- Link para guia de migração

---

## 7. Implementação no FastAPI

### 7.1 Estrutura de pastas

```
app/
├── api/
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── clients.py
│   │   ├── processes.py
│   │   ├── documents.py
│   │   └── ...
│   ├── v2/               ← quando existir
│   │   ├── __init__.py
│   │   └── clients.py    ← apenas os endpoints que mudaram
│   └── shared/           ← lógica de negócio compartilhada entre versões
│       ├── services/
│       └── repositories/
```

**Regra importante:** A lógica de negócio (services, repositories) é **compartilhada** entre versões. O que muda entre v1 e v2 são os schemas de request/response e as rotas. Isso evita duplicação de código.

### 7.2 Registro das versões no FastAPI

```python
from fastapi import FastAPI
from app.api.v1 import router as v1_router

app = FastAPI()

# v1 — ativo
app.include_router(v1_router, prefix="/api/v1")

# v2 — quando existir
# app.include_router(v2_router, prefix="/api/v2")
```

### 7.3 Middleware de deprecação

```python
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime

DEPRECATED_VERSIONS = {
    "v1": {
        "sunset": datetime(2027, 3, 1),
        "successor": "https://docs.plataforma.com.br/api/v2"
    }
}

class DeprecationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        path = request.url.path
        for version, info in DEPRECATED_VERSIONS.items():
            if f"/api/{version}/" in path:
                response.headers["Deprecation"] = "true"
                response.headers["Sunset"] = info["sunset"].strftime(
                    "%a, %d %b %Y %H:%M:%S GMT"
                )
                response.headers["Link"] = (
                    f'<{info["successor"]}>; rel="successor-version"'
                )
        return response
```

---

## 8. Guia de migração

Quando uma nova versão for lançada, um documento de migração deve ser publicado antes de qualquer comunicação de deprecação. O documento deve conter:

```markdown
# Guia de Migração: API v1 → v2

## O que mudou

| Endpoint | v1 | v2 | Tipo de mudança |
|---|---|---|---|
| GET /clients | retorna `name` | retorna `full_name` | Breaking |
| POST /processes | ... | ... | Breaking |

## O que NÃO mudou

Os seguintes endpoints são idênticos entre v1 e v2:
- GET /auth/me
- POST /auth/login
- ...

## Como migrar

### Passo 1: ...
### Passo 2: ...

## Prazo

A v1 será desativada em [data].
```

---

## 9. Política para tenants white-label

Tenants white-label que integraram via API têm proteção adicional:

- **Aviso mínimo de 12 meses** (vs 6 meses padrão) antes do sunset
- Suporte dedicado à migração para clientes de plano enterprise
- Possibilidade de contratação de extended support (manutenção da versão antiga por mais tempo, mediante custo)

---

## 10. Versão atual e roadmap

| Versão | Status | Lançamento | Sunset previsto |
|--------|--------|------------|-----------------|
| v1 | active | 2026 | — |
| v2 | planejada | Fase 5 (escala white-label) | — |

---

*Documento criado em 26/03/2026. Revisar quando a v2 for planejada.*
