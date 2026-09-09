# ADR-063 — Identidade PF/PJ e representante da pessoa jurídica

- **Status:** Aceita
- **Data:** 2026-09-08
- **Origem:** Spec Isis v0.1 (`docs/auditoria/SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md`),
  requisitos P0 **ENT-001**, **ENT-002** e **DATA-001**; caso de teste ELODI
  Agropecuária Ltda. (§4.2)
- **Branch:** `fix/identidade-pj-representante`
- **Relacionada a:** ADR-062 (fonte única registral — mesma doutrina de "cada
  dado tem a fonte autoritativa da sua natureza"), ADR-017 (consolidação
  parcial e reconciliação), ADR-001 (multi-tenant), Princípio 4 (toda query
  filtra por tenant)

## Contexto

A matriz de perfis de identidade (Fase 2, rodada contra banco descartável)
mediu sete perfis e reprovou dois:

| Perfil | Cenário | Antes |
|---|---|---|
| P3 | Client PJ + CNH de representante | **NÃO** — o `cpf_cnpj` do Client PJ era sobrescrito pelo CPF do representante, com `consolidated_at` carimbado |
| P6 | mesmo CNPJ cadastrado 2× no mesmo tenant | **NÃO** — nada impedia |

O P3 é o mais grave dos dois porque não produz um erro visível: produz um dado
errado **com selo de verificado**. A ELODI perdia o CNPJ, ganhava o CPF do Joel,
e a Conferência mostrava a linha como consolidada com sucesso.

As três causas são de modelagem, não de código isolado:

1. **Não existe representante no modelo.** A única pessoa de um caso é o
   `Client`. Um documento pessoal de terceiro não tinha para onde ir.
2. **`_FIELD_SPECS["rg_cpf"]` mapeia cegamente para `cliente`.** O spec de
   extração é estático (`target_entity="cliente"`), mas de quem é um RG/CPF/CNH
   depende de um fato do caso — se o titular é PF ou PJ — que só se conhece em
   tempo de execução.
3. **`cpf_cnpj` é `String` sem unicidade.** Nem no banco nem no schema. E como a
   coluna guarda o documento *como digitado*, comparar string crua nunca casaria
   `29.091.958/0001-17` com `29091958000117`.

Havia ainda um quarto achado, medido durante a implementação e não previsto no
relatório: **`ClientBase` (Pydantic) não tinha o campo `legal_name`**, embora a
coluna exista desde sempre. O `POST /clients` recebia a razão social e a
descartava em silêncio; o `GET` nunca a devolvia. Era essa — e não uma falha de
gravação — a causa do "preenchi o cadastro e a aba Dados mostra CNPJ vazio e
avisa que a razão social não foi preenchida" (DATA-001, §4.2.3). O formulário do
frontend agravava: um único campo rotulado "Nome Completo / Razão Social",
ligado a `full_name`.

## Decisão

### 1. Representante é entidade própria, subordinada ao Client PJ (ENT-001)

Nova tabela `client_representatives`, com FK `client_id` → `clients`
(`ON DELETE CASCADE`) e `tenant_id`. Colunas: `full_name`, `cpf`, `rg`,
`birth_date`, `papel`, `email`, `phone`, `field_sources`, `source_document_id`.

Representante **não é Client**: não contrata, não tem caso, não tem imóvel.
Documento pessoal de terceiro comprova representação, nunca titularidade.

**Por que tabela e não JSONB no Client** — decidido por medição do uso, não por
gosto:

- A consolidação grava campo a campo por `_write_entity`, que é **genérica sobre
  objeto ORM**: allowlist de colunas, coerção por tipo, guard de reconciliação
  (campo já `human_validated` que diverge não é sobrescrito), `field_sources` por
  campo e AuditLog do `anterior→novo`. Uma tabela herda as cinco garantias sem
  uma linha nova. Um JSONB exigiria um caminho de escrita paralelo — sem
  proveniência por campo e sem reconciliação. Escrita sem guard foi exatamente o
  que produziu o P3; repetir o padrão para consertá-lo seria contraditório.
- A cardinalidade é N e real: PJ com sócio-administrador **e** procurador é o
  caso comum, e a mesma pessoa física representa duas PJs (linhas distintas,
  nenhuma delas titular).
- `field_sources` é por *(entidade, coluna)* — o selo de oficialização (Sprint 3)
  e o "Aceito ≠ Gravado" da Conferência dependem dele.

`papel` é `String(50)` e não Enum: o vocabulário é evolutivo — a própria spec já
cita "inventariante" como referência processual em caso de falecimento (§2.1) — e
o precedente de `knowledge_catalog.source_type` mostra que valor novo em coluna
String não custa migration.

### 2. O documento pessoal é roteado por quem é o titular do caso

`build_staging_fields` passa a receber `titular_tipo` ("pf" | "pj" | None),
resolvido por `titular_tipo_do_processo` a partir do Client do processo:

- titular **PF** → `cliente` (o documento é do próprio titular; comportamento
  anterior preservado);
- titular **PJ** → `representante` (não há outra pessoa física possível no caso);
- **desconhecido** → destino `None`: a linha fica sem casa e vira pendência
  explícita na Conferência. Ambíguo nunca escreve — mesma regra do guard fantasma
  da matrícula.

E, **independentemente do roteamento**, a consolidação carrega um guard de
escrita: linha de `source_doc_type="rg_cpf"` apontando para um titular PJ é
redirecionada para o representante e tem o `target_entity` **corrigido na própria
linha de staging**. Isso cobre o staging legado (gravado pela versão anterior,
como o da ELODI) sem depender de reprocessamento, e a correção fica visível na
tela e no AuditLog — redirecionamento silencioso seria trocar um dado errado por
um invisível. A porta da escrita não pode depender de quem a chama ter
perguntado: é a mesma doutrina já usada em `_write_entity`.

O agrupamento por destino também mudou: para representante a chave inclui o
`document_id`, como a de matrícula inclui o `matricula_hint`. Duas CNHs não são
duas fontes disputando um campo (aí uma venceria e a outra sumiria) — são duas
**pessoas**.

### 3. Unicidade de CPF/CNPJ normalizado por tenant (ENT-002)

Índice único **funcional e parcial** em `clients`:

```sql
UNIQUE (tenant_id, regexp_replace(cpf_cnpj, '[^0-9]', '', 'g'))
WHERE cpf_cnpj IS NOT NULL AND deleted_at IS NULL AND <dígitos> <> ''
```

Sobre a expressão, não sobre a coluna crua: a coluna guarda o documento como o
consultor digitou; a identidade é o conjunto de dígitos. Índice na coluna crua
não teria impedido o duplicado da ELODI.

**Por tenant, nunca global** — o mesmo produtor rural pode ser cliente de duas
consultorias (Princípio 4). O perfil P7 existe para travar essa regra.

Nas duas portas de criação de cliente (`POST /clients` e o intake), a criação
procura correspondência exata antes e devolve **409 com o cadastro existente no
corpo**, para a tela oferecer reutilização. O `PATCH` tem o mesmo guard: mover o
documento de um cadastro para o de outro é criar o duplicado pela porta dos
fundos. `GET /clients/lookup/documento` permite perguntar antes de digitar o
resto.

A migration **para e reporta** se já houver duplicados no banco, em vez de
aplicar: a spec veta fusão automática de registros históricos sem plano de
migração e auditoria. `scripts/relatorio_duplicados_documento.py` inspeciona sem
alterar nada.

### 4. CNPJ e razão social existem de ponta a ponta (DATA-001)

`legal_name` entra em `ClientBase`/`ClientUpdate` e no `IntakeClientCreate`;
o `Client` de resposta passa a carregar `representatives`; o Hub carrega
`representantes` no cabeçalho. No frontend, a PJ ganha campo **próprio** de razão
social (o rótulo duplo virava `full_name`), o Hub mostra a razão social sob o
nome e um bloco **Representação** separado, e o contrato passa a qualificar a PJ
pela razão social, "neste ato representada por …".

## Consequências

- P3 e P6 viram SIM; P1, P2, P4, P5 e P7 continuam SIM (tabela no PR).
- O `rg_cpf` de um caso **sem cliente vinculado** deixa de escrever no cliente e
  passa a aparecer como pendência. É uma mudança de comportamento deliberada: a
  alternativa é adivinhar de quem é o documento.
- Casos PJ já consolidados com o CPF do representante no lugar do CNPJ **não são
  corrigidos automaticamente** — o dado errado continua na base até correção
  manual. Consertar em migration seria fusão/reescrita histórica automática, que
  a spec veta. A nova consolidação do mesmo caso já grava certo.
- `check_autuado_diverge_titular` ganhou dois parâmetros (`titular_nomes`,
  `representantes`): autuado que é o representante deixa de virar a nota
  "difere do titular — confirmar transferência de titularidade", que mandava a
  consultora investigar uma venda que não houve.

## Alternativas descartadas

**Representante como JSONB no Client.** Descartada pela medição do parágrafo
"por que tabela": perderia proveniência por campo, reconciliação e auditoria —
as garantias que impedem justamente o defeito que se está consertando.

**Corrigir só na extração (sem guard na consolidação).** Deixaria o staging já
gravado da ELODI escrevendo no titular na próxima consolidação. O defeito é de
escrita; o conserto tem de estar na porta da escrita.

**Constraint na coluna crua `cpf_cnpj`.** Barata e inútil: não casa formatações
diferentes do mesmo documento, que é como o duplicado real entrou.

**Fundir os duplicados históricos na migration.** Vetada explicitamente pela
spec (ENT-002, observação). Fusão exige decidir qual cadastro é canônico e para
onde vão processos, imóveis e contratos — decisão de produto, com auditoria, não
efeito colateral de `alembic upgrade`.

**Normalizar `cpf_cnpj` na gravação (guardar só dígitos).** Simplificaria o
índice, mas tira do consultor a leitura do documento como ele o conhece e
reescreveria dado histórico de todos os tenants. A coluna guarda o que foi
digitado; a identidade é derivada.
