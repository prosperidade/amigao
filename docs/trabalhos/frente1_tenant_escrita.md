# Frente 1 — Integridade de tenant na escrita

**Data:** 2026-08-10 · **Branch:** `fix/tenant-integridade-escrita` · **Base:** `88be956`
**Origem:** Frente 1 do §E da [triagem da auditoria Codex](../auditoria/TRIAGEM_AUDITORIA_CODEX.md) (PR #146)
**Achados fechados:** D1, D2, D3, D7 — **mais** a classe inteira (ver "Escopo expandido")

---

## O princípio que rege a frente

**Entidade de outro tenant responde 404, nunca 403.** Decisão do André, 10/08.

Um 403 confirma que a entidade existe. O endpoint vira oráculo de enumeração: varre-se
o espaço de ids e aprende-se o tamanho e o mapa do outro tenant sem ler um byte de dado.
"Não existe para você" é a semântica correta.

Não é convenção nova. `BaseRepository.get_or_404` já respondia 404 para a entidade
principal desde sempre; o que faltava era aplicá-la às **relações**.

## Escopo expandido — por decisão, não por deriva

A triagem listou quatro achados (D1, D2, D3, D7). O **Passo 0** desta frente varreu a
classe inteira e encontrou mais. O André decidiu incluir tudo, com a razão escrita:

> *"Conhecer o bug e não consertá-lo por não estar na lista original não é opção."*
> *"Fechar escrita e deixar leitura atravessando tenant deixa o dado torto VISÍVEL por
> outro caminho — meia correção numa fronteira de segurança é falsa segurança."*

| Origem | Itens |
|---|---|
| Triagem (D1, D2, D3, D7) | `POST /processes`, `POST /contracts` (3 pontos), `storage_key` (2 pontos), 4 endpoints assíncronos + task |
| **Varredura de classe (novo)** | `POST /tasks`, `POST /threads`, `POST /properties`, `POST /proposals` |
| **Decisão 1 (leituras)** | `processes.py` ×4, `dossier.py` ×1 |
| **Achados durante a implementação** | `template_id` do contrato (tenancy dual) · `PATCH /tasks/{id}` |

### Os dois que a implementação revelou

Nenhum dos dois estava na auditoria nem na triagem — apareceram porque, ao aplicar o
validador, foi preciso responder "que outras FKs este endpoint aceita?".

**`template_id` no contrato — tenancy dual não é passe livre.**
`ContractTemplate.tenant_id` é *nullable*, e `None` significa "template global do produto".
A leitura apressada é "nullable ⇒ não dá para validar por tenant". A leitura correta é que
o template **privado do vizinho** continua sendo dado alheio — e num contrato ele vira o
texto de uma peça assinada. Daí `exigir_do_tenant_ou_global`: global passa, do vizinho não.

**`PATCH /tasks/{id}` — a porta dos fundos da criação.**
`TaskUpdate` carrega `process_id`, `property_id`, `document_id` e `assigned_to_user_id`.
Fechar só o `POST` deixaria o caminho "criar limpo, repontar depois" aberto. A varredura
de PATCH/PUT que isso motivou cobriu os 15 endpoints com corpo tipado; **este era o único
com FK**. `ProposalUpdate`, `PropertyUpdate` e `ClientUpdate` não têm FK; o re-home de
matrícula (`MatriculaMoveRequest.property_id`) **já validava** o destino com
`PropertyRepository(...).get_or_404`.

## O padrão já existia — em um lugar só

O achado que definiu o desenho do Passo 1: `credentials.py:78-85` **já fazia certo**,
com o comentário e tudo:

```python
# Tenant isolation: o cliente precisa ser do mesmo tenant.
client = db.query(ClientModel).filter(
    ClientModel.id == payload.client_id,
    ClientModel.tenant_id == current_user.tenant_id,
).first()
if not client:
    raise HTTPException(status_code=404, detail="Cliente não encontrado.")
```

`intake.py:665-686` (enrich) faz o mesmo para cliente e imóvel. `properties.py:153-178`
traz o vínculo do **path** e valida com `get_or_404`, com o docstring dizendo
*"`tenant_id` vem do JWT (nunca do corpo)"*. O re-home de matrícula
(`properties.py:210-212`) valida o imóvel de destino pelo repositório tenant-scoped.

Ou seja: a casa sabia. O padrão estava aplicado em 4 de ~18 pontos. O validador
**generaliza um precedente**, não inventa um — e o docstring de
`app/services/tenant_guard.py` cita a origem para que isso não se perca.

## Por que o validador não vive no `BaseRepository`

Porque metade dos endpoints não passa por repositório:

| Tem repo | Não tem repo (ORM cru no router) |
|---|---|
| client, document, matricula, process, property, staging, task | **proposal, contract, credential, thread, acao, rota, regulatory** |

É função livre, sem `Depends` e sem herança, chamável de router e de repo.

## O que foi entregue

**`app/services/tenant_guard.py`** — três funções:

- `exigir_do_tenant(db, model, id, tenant_id)` → entidade ou 404. `id=None` devolve
  `None` sem consultar (FK opcional ausente é ausência legítima).
- `exigir_do_tenant_ou_global(...)` → para tenancy **dual** (`tenant_id IS NULL` =
  compartilhado). Só `ContractTemplate`, `PromptTemplate` e `knowledge_catalog` têm
  esse desenho, todos por decisão registrada.
- `exigir_relacoes_do_tenant(db, tenant_id, dados)` → valida **toda** FK conhecida
  presente no payload, percorrendo um catálogo de 13 campos.

> **Por que catálogo e não lista por endpoint.** A classe de bug nasceu de endpoints que
> **esqueceram** de validar. Uma guarda que também dependesse de alguém lembrar de listar
> o campo reintroduziria o mesmo modo de falha uma camada acima. Campo novo num schema
> que já esteja no catálogo passa a ser validado sem que ninguém encoste no guard.

**`validar_storage_key`** (`app/services/storage.py`) — a chave devolvida na confirmação
tem de casar `tenant_{quem_chama}/{process|draft}_{id_correto}/{uuid}`. Fecha cross-tenant
**e** cross-processo. Regex ancorado nas duas pontas — sem isso, `tenant_5` casaria o
prefixo de `tenant_55`.

## Decisões tomadas no caminho

**`storage_key`: validar (b), não derivar (a).** O prompt preferia (a). Medi antes de
escolher: `generate_presigned_put_url` devolve a chave e **não persiste nada**, e a chave
carrega um UUID aleatório — o backend não tem como reconstruí-la na confirmação. (a) exige
tabela de uploads pendentes ou chave assinada, e as duas mudam o contrato com o frontend.
(b) fecha o buraco medido pelo mesmo efeito prático. Registrado como **dívida #129**.

**`storage_key` inválida responde 400, não 404.** A chave não é entidade cuja existência
se possa vazar — é campo malformado do próprio payload. 404 ali seria mentira sobre a
natureza do erro, e não protege nada a mais.

**FK composta `(tenant_id, id)` fica de fora.** É o AUD-02-003, exige migration em todas
as tabelas tenantizadas. A validação na aplicação cobre a escrita nova; a constraint é o
cinto para depois. **Dívida #128.**

**RLS continua fora.** Adotá-la reabriria a ADR-001, que decidiu isolamento lógico com a
negativa assumida por escrito. Fora do que este achado sustenta.

## O gate anti-regressão

`tests/api/test_tenant_smoke_escrita.py` — a promessa que a **ADR-001 fez em 26/03/2026**
e deixou como ❌ Pendente por quatro meses e meio. Nesse intervalo nasceram os achados
AUD-04-01/02/04/07.

Entregue como **fumaça**, não como lint: uma regra estática que procurasse `query()` sem
filtro teria falso positivo demais (busca global legítima no corpus, agregação já escopada)
e nenhum poder sobre o caso que causou dano — a FK que **chega no corpo**.

Contrato exercitado por endpoint: FK do outro tenant → **404**; FK do próprio tenant →
**2xx** (não-regressão). Mais o teste de D2, que cria a relação torta **direto no banco**
(representando contrato gravado antes desta frente) e prova que assinar devolve 404 **e**
que o `closed_at` do processo alheio permanece intocado — o conserto protege o dado
legado, não só barra a entrada nova.

## Documentos corrigidos

`ARQUITETURA_GERAL.md:131` e `MULTITENANT_LGPD.md` (Camada 4) afirmavam que relação
cross-tenant retornava **403**. Era falso nos dois sentidos: não havia validação de
relação, e a resposta pretendida estava errada. Corrigidos no mesmo PR, com nota de
histórico — documento que promete garantia inexistente é pior que omisso.

A ADR-001 ganhou nota de execução registrando que a mitigação prometida foi entregue, e
o que custou o atraso.

## Dívidas abertas

| # | Item |
|---|---|
| **128** | FK composta `(tenant_id, id)` — o cinto embaixo da validação |
| **129** | `storage_key` ainda é aceita do cliente (validada, não derivada) |
