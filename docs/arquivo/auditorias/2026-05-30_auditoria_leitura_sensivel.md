# Auditoria — leitura de campo sensível (2026-05-30)

Read-only. Verifica se o uso/leitura de segredos (senha de portal cifrada e
`api_key` de LLM do consultor) é auditado, após PR 2.3 (Credential) e PR LLM.
Nenhuma alteração de código — só apuração e recomendação.

## O que o `AuditLog` grava hoje

`app/models/audit_log.py`: colunas `entity_type`, `entity_id`, `action`,
`old_value`, `new_value`, `details`, `ip_address`, `user_agent`, **`hash_sha256`
+ `hash_previous`** (hash chain SHA-256, carimbada por
`app/services/audit_hash.py:stamp_audit_hash`).

`action` é `String` (não enum). Valores presentes no código (grep `action=`):
`"created"`, `"updated"`, `"deleted"`, `"reconciled"`, `"base_enriched"`. **Todas
orientadas a ESCRITA.** Não há `action="read"` / `"view"` / `"access"`.

## Credenciais de portal (PR 2.3)

- `app/api/v1/credentials.py`: `POST` (create) → AuditLog `action="created"`;
  `PATCH` → `"updated"`; `DELETE` → `"deleted"`. **`GET` (list e por id) NÃO
  audita** — mas também **não expõe a senha**: a resposta traz apenas
  `has_password: bool`. **Não existe** endpoint `GET /secret` / `/reveal`.
- A senha é decifrada pelo ORM (`EncryptedString.process_result_value`) **toda
  vez que uma linha `Credential` é carregada** — mas, hoje, **nenhum consumidor
  usa o plaintext** (não há integração que faça login no portal ainda). O
  plaintext nunca sai da aplicação.
- **Conclusão:** a senha de portal **nunca vaza** (decisão correta do PR 2.3).
  Não há leitura sensível exposta a auditar — porque não há leitura exposta.

## `api_key` de LLM (PR LLM, white label)

- `User.preferences['ai']['api_key_encrypted']` (JSONB) — cifrada via
  `encrypt_str` em `app/services/user_preferences.py:save_ai_preferences`.
- `GET /auth/me/full` e o PATCH retornam **mascarado** (`api_key_masked`,
  `api_key_set`); nunca plaintext.
- **Decifrada server-side** em `get_ai_runtime()` →
  `BaseAgent._resolve_user_ai_preferences()` → passada ao
  `ai_gateway.complete(user_preferences=...)` a cada chamada de agente. **Esse
  uso NÃO é auditado** — não há `AuditLog` registrando "api_key do usuário X foi
  decifrada/usada na chamada Y".

## O que está auditado × o que não está

| Evento | Auditado? |
|---|---|
| Credential create/update/delete | ✅ (`AuditLog` + hash chain) |
| Reconciliação de campo no intake | ✅ (`action="reconciled"`) |
| `GET` de credencial (sem expor senha) | ❌ — mas não expõe segredo |
| Uso server-side da senha de portal decifrada | n/a — sem consumidor hoje |
| Decifragem/uso da `api_key` de LLM do consultor | ❌ **não auditado** |
| Verificação de integridade da hash chain | ❌ (dívida **#18** já existente) |

## Recomendação (sem implementar nesta PR)

1. **Quando** a senha de portal ganhar um consumidor real (login automatizado em
   portal) ou um endpoint de revelação, **adicionar `AuditLog` no ato de uso**
   (`action="secret_read"` ou `"credential_used"`), com entity_type/entity_id.
2. Considerar auditar a decifragem/uso da `api_key` de LLM por chamada — conecta
   com a dívida **#30** (auditoria de uso de IA por usuário/chave).
3. A rotina de verificação da hash chain (dívida **#18**) segue pendente.

Itens 1–2 ficam como **dívida nova** (ver REGISTRO_DIVIDAS) — PR própria, fora
do escopo doc-only desta rodada.

## Atualização (2026-05-31) — item 2 implementado

A recomendação **2** (auditar a decifragem/uso da `api_key` de LLM do consultor) foi
implementada em `feat/divida-33-audit-uso-api-key`: `BaseAgent.call_llm` agora emite `AuditLog`
`action="ai_key_used"` (hash chain) uma vez por execução, com a chave mascarada (`…últimos4`,
nunca plaintext), best-effort. A linha "Decifragem/uso da `api_key`…" da tabela acima passa de
❌ para ✅ a partir desta data. Recomendações **1** (senha de portal — segue sem consumidor) e
**3** (verificação da hash chain, dívida **#18**) permanecem abertas. Ver dívida **#33** (parcial)
no `REGISTRO_DIVIDAS`.
