# ADR-014 — Criptografia de segredos por usuário com Fernet

- **Status:** Aceita
- **Data:** 2026-05-28
- **Relacionada a:** PR LLM (white label — consultor traz própria chave), PR 2.3 (modelo `Credential` — login/senha de portais por cliente), Frente D

## Contexto

O produto está caminhando para dois cenários em que **segredos de terceiros** precisam viver no
banco de dados, não apenas em variáveis de ambiente do sistema:

1. **White label de LLM.** Cada consultoria traz a própria chave de provedor de IA (Anthropic,
   Gemini, OpenAI, provedores chineses). A PR LLM (futura) vai gravar essa chave em
   `User.preferences.ai.api_key`.
2. **Credenciais de portal por cliente.** A PR 2.3 (futura) introduz o modelo `Credential` com
   login/senha de portais externos por cliente — SEMA, banco, SICAR, INCRA etc.

Ambos os casos exigem que o segredo viva **criptografado em repouso** no banco. Hoje o projeto
**não tem padrão de criptografia de segredos**: segredos existem apenas como variáveis de ambiente
do próprio sistema (`SECRET_KEY` do JWT, chaves de MinIO, chaves de LLM do sistema). Nenhum segredo
de terceiro é persistido ainda.

Decisão de sequenciamento: **ADR primeiro** (define o padrão), **infraestrutura depois** (implementa
o mecanismo). **Nenhuma coluna real é alterada nesta PR.** A PR 2.3 e a PR LLM consomem a
infraestrutura criada aqui quando entrarem.

## Decisão

Adotar `cryptography.fernet.Fernet` (AES-128-CBC + HMAC-SHA256) como padrão de criptografia
simétrica autenticada de segredos por usuário/cliente.

- **Chave-mestra em variável de ambiente separada do `SECRET_KEY` do JWT:** `CREDENTIAL_ENCRYPTION_KEY`.
  Escopos de comprometimento ficam isolados — vazar a chave do JWT não expõe os segredos no banco e
  vice-versa.
- **`MultiFernet`** como construção, aceitando a chave atual e, opcionalmente, uma chave antiga
  (`CREDENTIAL_ENCRYPTION_KEY_OLD`) para suportar rotação sem downtime.
- **Type decorator SQLAlchemy `EncryptedString`** para uso transparente em colunas. O round-trip
  acontece no nível do ORM: **encrypt no bind (flush)** e **decrypt no result (load)**. O código de
  negócio lê e escreve plaintext; o ciphertext só existe no banco.
- **Sem fallback inseguro:** se `CREDENTIAL_ENCRYPTION_KEY` não estiver setada, a aplicação **falha
  no startup** com mensagem clara. A chave não é derivada do `SECRET_KEY` nem tem default.

## Alternativas rejeitadas

a) **AWS Secrets Manager / HashiCorp Vault.** Custo recorrente, lock-in de fornecedor e latência de
   uma chamada externa a cada uso (cada chamada de agente teria que ir buscar a chave/segredo no
   cofre). Para o estágio atual do MVP, o overhead operacional e financeiro não se justifica.

b) **Reusar o `SECRET_KEY` do JWT como chave de criptografia.** O comprometimento de uma das chaves
   afetaria a outra — um vazamento do `SECRET_KEY` (que circula em mais lugares: assinatura de
   token, etc.) passaria a expor todos os segredos no banco. Separação de escopos é mais segura.

c) **AES puro sem MAC.** Sem autenticação, há risco de adulteração silenciosa do ciphertext
   (bit-flipping, padding oracle). O Fernet já garante autenticidade (HMAC-SHA256) embutida, sem
   exigir que a gente acerte a composição encrypt-then-MAC manualmente.

## Plano de rotação

- A chave em uso vive em `CREDENTIAL_ENCRYPTION_KEY`.
- Para rotacionar:
  1. Setar `CREDENTIAL_ENCRYPTION_KEY_OLD` com o valor **antigo**.
  2. Atualizar `CREDENTIAL_ENCRYPTION_KEY` com o valor **novo**.
  3. `MultiFernet` aceita ambas durante a transição: dados antigos continuam decriptáveis pela chave
     antiga; dados novos são escritos com a chave nova.
  4. Rodar um script de re-encrypt (a ser criado na **primeira rotação real**, fora do escopo desta
     PR) que relê e regrava cada segredo, migrando o ciphertext para a chave nova.
  5. Remover `CREDENTIAL_ENCRYPTION_KEY_OLD` quando todos os segredos estiverem reescritos.

## Não-escopo desta ADR

- **Criar coluna criptografada em modelo real.** Fica para a PR 2.3 (`Credential`) e a PR LLM
  (`User.preferences.ai.api_key`). Esta PR entrega apenas a infraestrutura (`EncryptedString`,
  módulo `encryption`, config, tooling) e testes em um modelo de teste.
- **HSM ou chave em hardware.** Fora do MVP.
- **Script de re-encrypt.** Será criado na primeira rotação real.

## Consequências

**Positivas**
- Padrão único e transparente de criptografia de segredos, pronto para a PR 2.3 e a PR LLM.
- Escopos de chave isolados (JWT × segredos) — falha de uma não derruba a outra.
- Rotação suportada por construção (`MultiFernet`), sem downtime de leitura.
- Autenticidade garantida (Fernet) — ciphertext adulterado é rejeitado, não decriptado em lixo.

**Negativas / custos**
- Mais uma variável de ambiente obrigatória (`CREDENTIAL_ENCRYPTION_KEY`) no setup e no deploy.
- Perda da chave = perda dos segredos (irrecuperáveis). Mitigação: backup seguro da chave fora do
  banco, documentado no RUNBOOK_OPS.
- Colunas `EncryptedString` não são pesquisáveis por conteúdo no banco (o valor é ciphertext) — o
  que é o comportamento desejado para segredos.
