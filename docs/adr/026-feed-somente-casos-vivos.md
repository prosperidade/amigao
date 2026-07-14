# ADR-026 — O feed do consultor mostra só casos que ainda existem

**Status:** Aceita (André, 2026-07-13)
**Contexto relacionado:** ADR-025 (feed do consultor: filtro de audiência +
tradução), Fase 2 reset-tool + wipe casos 8/13 (`audit_logs` preservado por
design), Princípio 2 (tudo é auditável — hash chain SHA-256).

## Contexto

Depois de limpar casos de teste (ferramenta de reset ou wipe SQL dos casos
8/13), o feed "Atividades Recentes" continuava mostrando atividade desses casos —
com o card caindo em "caso #13" e o clique levando a um 404.

Causa: o feed lê `audit_logs`, e o `audit_logs` é **preservado de propósito** na
limpeza. Apagar linhas quebraria a hash chain SHA-256 (`hash_previous` encadeia
cada registro; `verify_audit_chain` deixaria de validar) e violaria o Princípio 2.
O próprio reset se registra como uma nova linha (`action=reset_casos_teste`). Ou
seja: o wipe remove os **casos**, mas mantém o **histórico** de que existiram — e
essas linhas órfãs vazavam para a vitrine.

Decisão do André (2026-07-13): a vitrine mostra só casos vivos; o `audit_logs`
permanece intocado.

## Decisão

**Evento ligado a um Process só aparece no feed se aquele Process ainda existe.**

Em `_recent_activities` (dashboard), além do filtro de audiência do ADR-025,
adiciona-se um filtro de existência no QUERY (antes do `limit(8)`, para o feed
encher com eventos vivos):

- Para `entity_type in {process, agent}` (cujo `entity_id` é o id do Process),
  exige-se `EXISTS` um `Process` com aquele id, do mesmo tenant, com
  `deleted_at IS NULL`. Cobre tanto o hard-delete do wipe (linha some → EXISTS
  falso) quanto o soft-delete (`deleted_at` preenchido).
- Demais `entity_type` passam direto (não são caso-ligados por process_id).

É **100% camada de apresentação (read-path)**: nenhuma linha de `audit_logs` é
tocada. As órfãs continuam gravadas e consultáveis em `/audit` — só somem da tela
do consultor.

## Consequências

- **Positivas:** o consultor não vê mais fantasma de caso apagado; sem card
  "caso #13" que dá 404. A trilha de auditoria permanece íntegra
  (`verify_audit_chain` continua válido).
- **Auditoria intocada:** a decisão de NÃO apagar `audit_logs` (hash chain +
  Princípio 2) é preservada; a limpeza é só da superfície.
- **Escopo:** o filtro cobre eventos ligados a `Process` (process/agent) — a
  fonte do fantasma reportado. Eventos de outras entidades órfãs (ex.: cliente
  apagado) não são o caso deste ADR; se aparecerem, viram follow-on.
- **Custo:** um `EXISTS` correlacionado por query do feed — barato, indexado por
  `Process.id`.
