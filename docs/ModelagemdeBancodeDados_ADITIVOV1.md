# Aditivo à Modelagem de Banco de Dados — v1 patch 1
**Projeto:** Plataforma Ambiental SaaS  
**Versão:** 1.0-patch1  
**Data:** 26/03/2026  
**Complementa:** `ModelagemdeBancodeDados.md`

---

## 1. Contexto

Este documento define dois ajustes na modelagem original que precisam ser aplicados antes do Sprint 3 (quando os agentes de IA entram em produção) e do Sprint 5 (quando o sistema começa a ter requisitos de auditoria mais rígidos para GovTech).

Ambos podem ser aplicados como migrations adicionais sem alterar o comportamento atual do sistema.

---

## 2. Ajuste 1 — Tabela `ai.prompts`

### Problema

A tabela atual tem apenas `is_active` para controlar estado. Isso não permite:
- Rollout gradual de um prompt novo sem derrubar o anterior
- Reverter para versão anterior em caso de regressão
- Distinguir prompt em teste controlado de prompt em produção plena
- Rastrear a evolução de um prompt ao longo do tempo

### Migration

```sql
-- Adicionar campos de versionamento e controle de rollout
ALTER TABLE ai.prompts
  ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'experimental', 'deprecated', 'archived')),
  ADD COLUMN version_string VARCHAR(20),
  ADD COLUMN rollout_percent INTEGER NOT NULL DEFAULT 100
    CHECK (rollout_percent BETWEEN 0 AND 100),
  ADD COLUMN previous_version_id UUID REFERENCES ai.prompts(id),
  ADD COLUMN notes TEXT,
  ADD COLUMN created_by_user_id UUID REFERENCES core.users(id),
  ADD COLUMN last_modified_at TIMESTAMPTZ DEFAULT NOW();

-- Migrar dados existentes: is_active=true → status='active', is_active=false → status='deprecated'
UPDATE ai.prompts SET status = 'active'     WHERE is_active = true;
UPDATE ai.prompts SET status = 'deprecated' WHERE is_active = false;

-- Índice para busca eficiente de prompt ativo por agente
CREATE INDEX idx_prompts_agent_status
  ON ai.prompts (agent_type, status)
  WHERE status = 'active';

-- Índice para rollout gradual (busca prompts experimentais por agente)
CREATE INDEX idx_prompts_agent_experimental
  ON ai.prompts (agent_type, status, rollout_percent)
  WHERE status = 'experimental';
```

### Campos adicionados

| Campo | Tipo | Padrão | Descrição |
|-------|------|--------|-----------|
| `status` | VARCHAR(20) | `active` | Estado do prompt: active, experimental, deprecated, archived |
| `version_string` | VARCHAR(20) | NULL | Versão semântica: "1.0.0", "1.1.0", "2.0.0" |
| `rollout_percent` | INTEGER | 100 | % de requisições que usam esse prompt (0-100) |
| `previous_version_id` | UUID | NULL | FK para a versão anterior (permite rollback) |
| `notes` | TEXT | NULL | Descrição do que mudou nessa versão |
| `created_by_user_id` | UUID | NULL | Quem criou/editou esse prompt |
| `last_modified_at` | TIMESTAMPTZ | NOW() | Última modificação |

### Como usar na prática

```python
# Buscar prompt ativo para um agente
def get_active_prompt(agent_type: str, tenant_id: UUID) -> Prompt:
    # Primeiro tenta prompt específico do tenant
    tenant_prompt = db.query("""
        SELECT * FROM ai.prompts
        WHERE tenant_id = :tenant_id
          AND agent_type = :agent_type
          AND status = 'active'
        ORDER BY created_at DESC LIMIT 1
    """, tenant_id=tenant_id, agent_type=agent_type).first()
    
    if tenant_prompt:
        return tenant_prompt
    
    # Fallback para prompt global
    return db.query("""
        SELECT * FROM ai.prompts
        WHERE tenant_id IS NULL
          AND agent_type = :agent_type
          AND status = 'active'
        ORDER BY created_at DESC LIMIT 1
    """, agent_type=agent_type).first()

# Fazer rollout gradual de prompt experimental
def get_prompt_with_rollout(agent_type: str) -> Prompt:
    experimental = db.query("""
        SELECT * FROM ai.prompts
        WHERE agent_type = :agent_type
          AND status = 'experimental'
          AND rollout_percent > 0
        ORDER BY created_at DESC LIMIT 1
    """, agent_type=agent_type).first()
    
    if experimental and random.randint(1, 100) <= experimental.rollout_percent:
        return experimental
    
    return get_active_prompt(agent_type)
```

### Processo de atualização de prompt (operacional)

```
1. Criar novo registro com status='experimental', rollout_percent=10
   (10% do tráfego usa o prompt novo)

2. Monitorar métricas por 48h:
   - taxa de erro
   - taxa de revisão humana
   - custo por chamada
   - qualidade percebida

3. Se OK: aumentar rollout_percent gradualmente (25 → 50 → 100)

4. Quando rollout_percent=100: mudar para status='active'
   e marcar o anterior como status='deprecated'

5. Se regressão: mudar status='archived' e o anterior volta a status='active'
   (o campo previous_version_id facilita identificar qual é o anterior)
```

---

## 3. Ajuste 2 — Tabela `core.audit_log`

### Problema

A tabela atual registra eventos mas não encadeia os registros. Para trilha de auditoria juridicamente defensável — especialmente para GovTech — os registros precisam ser imutáveis e verificáveis. Um banco pode ser adulterado silenciosamente. Com encadeamento por hash, qualquer adulteração retroativa é detectável.

### Princípio

Funciona como uma blockchain simples:
```
log[N].hash = SHA256(log[N].content + log[N-1].hash)
```

Se alguém modificar um registro antigo, o hash da cadeia fica inválido a partir daquele ponto. A violação é detectável.

### Migration

```sql
-- Adicionar campos de encadeamento
-- Nullable por ora — será preenchido pelo worker a partir do Sprint 4/5
ALTER TABLE core.audit_log
  ADD COLUMN hash_sha256 VARCHAR(64),
  ADD COLUMN hash_previous VARCHAR(64);

-- Índice para verificação eficiente da cadeia
CREATE INDEX idx_audit_log_entity_chain
  ON core.audit_log (tenant_id, entity_type, entity_id, created_at);
```

### Como calcular o hash (implementar no Sprint 4)

```python
import hashlib
import json

def calculate_audit_hash(record: dict, previous_hash: str | None) -> str:
    """
    Calcula o hash de um registro de auditoria.
    O hash inclui o conteúdo do registro + o hash do registro anterior.
    """
    content = {
        "tenant_id": str(record["tenant_id"]),
        "user_id": str(record.get("user_id")),
        "action": record["action"],
        "entity_type": record["entity_type"],
        "entity_id": str(record["entity_id"]),
        "before_json": record.get("before_json"),
        "after_json": record.get("after_json"),
        "created_at": record["created_at"].isoformat(),
        "previous_hash": previous_hash or "GENESIS"
    }
    content_str = json.dumps(content, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(content_str.encode()).hexdigest()

def write_audit_log(
    session,
    tenant_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    before: dict | None,
    after: dict | None,
    user_id: UUID | None = None,
    ai_job_id: UUID | None = None,
):
    # Buscar o hash do último registro da mesma entidade
    last_record = session.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id,
    ).order_by(AuditLog.created_at.desc()).first()
    
    previous_hash = last_record.hash_sha256 if last_record else None
    
    record = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before_json": before,
        "after_json": after,
        "created_at": datetime.utcnow(),
    }
    
    record["hash_sha256"] = calculate_audit_hash(record, previous_hash)
    record["hash_previous"] = previous_hash
    
    session.add(AuditLog(**record))
    session.commit()
```

### Como verificar a integridade da cadeia

```python
def verify_audit_chain(session, tenant_id: UUID, entity_type: str, entity_id: UUID) -> bool:
    """
    Verifica se a cadeia de auditoria de uma entidade está íntegra.
    Retorna True se íntegra, False se adulterada.
    """
    records = session.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id,
        AuditLog.hash_sha256.isnot(None),  # apenas registros com hash
    ).order_by(AuditLog.created_at.asc()).all()
    
    previous_hash = None
    for record in records:
        expected_hash = calculate_audit_hash(record.__dict__, previous_hash)
        if expected_hash != record.hash_sha256:
            return False  # adulteração detectada
        previous_hash = record.hash_sha256
    
    return True
```

---

## 4. Ordem de aplicação das migrations

```
Sprint 2 (agora):
  migration_001_prompts_versioning.sql    ← aplica ajuste 1
  migration_002_audit_log_hash_fields.sql ← aplica ajuste 2 (campos nullable)

Sprint 4:
  Implementar calculate_audit_hash() no write_audit_log()
  Preencher hash em novos registros (os antigos ficam com NULL — aceitável)

Sprint 5 (GovTech):
  Implementar verify_audit_chain() para verificação periódica
  Considerar backfill de hashes em registros históricos críticos
```

---

## 5. Impacto em outros documentos

Este aditivo complementa:
- `ModelagemdeBancodeDados.md` — seções 15.3 (ai.prompts) e 17.1 (audit_log)
- `Governança_deIA.md` — seção 4 (estrutura de prompts)
- `SegurançaLGPDeConformidade.md` — seção 11 (auditoria e logs)

Nenhum documento existente precisa ser alterado. Este aditivo é adicionado como complemento.

---

*Documento criado em 26/03/2026. Aplicar migrations antes do Sprint 3.*
