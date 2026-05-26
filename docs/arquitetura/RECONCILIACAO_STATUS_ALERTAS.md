# Reconciliação dos 3 status de um alerta — **PROPOSTA** (PROMPT_5 Onda C)

> **Status deste documento:** *proposta* a ser validada pelo Andre antes da
> implementação. PROMPT_5 explicitamente proibiu implementar a modelagem aqui;
> esta rodada só **descreve as opções**.

## O problema

Hoje circulam, sobre o mesmo alerta de divergência, **três campos diferentes
de "status"**, originados em camadas distintas do método:

| Origem | Campo | Valores possíveis |
|---|---|---|
| **Skill diagnóstico** (`situacao_ambiental_imovel_rural`) | `status_saneamento` | `pendente` · `em_validacao` · `saneado` · `descartado` · `nao_aplicavel` |
| **Skill auditor** (`auditor_imovel/analise_divergencias_documentais`) | `status` (do `AuditFinding`) | `suspeita` · `confirmada` · `descartada` · `resolvida` · `ignorada` |
| **Skill diagnóstico (P4 — camada 2 do Princípio 1)** | `decisao_consultor` | `corrigir_antes` · `seguir_com_ressalva` · `solicitar_doc` · `fora_escopo` · `ignorar_justificado` |

Os três descrevem **coisas diferentes**, mas se confundem em conversa porque
todos viraram "status" no jargão da equipe:

1. **`status` (do auditor)** descreve o **estado de confirmação** do achado:
   é suspeita ou já foi confirmada? foi descartada? já está resolvida no
   mundo? O foco é **na natureza do indício** após o consultor olhar.

2. **`decisao_consultor`** descreve **qual ação foi escolhida** sobre um
   alerta crítico: vou corrigir antes? vou seguir com ressalva? preciso de
   mais documento? É **a decisão de conduta** — só aplicável a alertas que
   exigem decisão (críticos, segundo a P4).

3. **`status_saneamento`** descreve o **estado da resolução prática** do
   alerta no mundo: a pendência está em validação? já foi sanada? não se
   aplica ao caso? É o **progresso do saneamento**, derivado das duas
   anteriores + tempo + colaboração com cliente.

Sem reconciliação, o consumidor (UI e relatórios) não sabe qual ler primeiro,
e o auditor/Diagnóstico pode emitir valores inconsistentes (ex.: alerta
`confirmada` + `ignorar_justificado` + `pendente` simultaneamente — humano
fica perdido).

## Princípio condutor

Antes de propor modelagem, fixar o que NÃO mudou:

- **A IA propõe; o humano decide e assina.** Os três status existem porque
  são facetas diferentes do trabalho do consultor — não dá pra colapsar tudo
  num campo só sem perder informação que ele de fato consome.
- **Crítico dispara decisão obrigatória.** Só alertas com `severity=critico`
  exigem `decisao_consultor` (camada 2 do Princípio 1, que ainda não foi
  implementada). Os outros podem viver sem decisão explícita.
- **O catálogo (`regulatory_issue_catalog`) e a família/codigo_alerta**
  (PROMPT_5 Onda A) **não mudam aqui** — esta rodada só endereça o
  vocabulário de estado.

## Opções de modelagem

### Opção A — Três campos ortogonais, sem unificar (recomendada)

Tratar os três como dimensões independentes do mesmo alerta. Cada campo
modela uma faceta diferente; nenhum deriva do outro automaticamente.

```python
class RegulatoryIssue(Base):
    # ... (campos PROMPT_5: codigo_alerta, familia, severity 4, etc.)

    # Dimensão 1 — natureza do indício (preenchida pelo auditor, editável)
    status_achado = Column(
        Enum(StatusAchado, name="regulatory_status_achado"),
        nullable=False,
        default=StatusAchado.suspeita,
    )

    # Dimensão 2 — decisão de conduta sobre alerta crítico (P4)
    # Só preenchida quando severity=critico (NULL para os outros).
    decisao_consultor = Column(
        Enum(DecisaoConsultor, name="regulatory_decisao_consultor"),
        nullable=True,
    )

    # Dimensão 3 — progresso prático do saneamento
    status_saneamento = Column(
        Enum(StatusSaneamento, name="regulatory_status_saneamento"),
        nullable=False,
        default=StatusSaneamento.pendente,
    )
```

**Tabela-verdade do uso real:**

| Cenário | `status_achado` | `decisao_consultor` | `status_saneamento` |
|---|---|---|---|
| Auditor acabou de emitir, consultor ainda não olhou | `suspeita` | `NULL` | `pendente` |
| Consultor confirmou; é severity `alto` (não crítico) | `confirmada` | `NULL` *(não exige decisão)* | `em_validacao` |
| Consultor confirmou; é severity `critico` | `confirmada` | `corrigir_antes` | `em_validacao` |
| Cliente entregou retificação; tudo bate agora | `resolvida` | `corrigir_antes` *(preserva histórico)* | `saneado` |
| Auditor errou, não há divergência real | `descartada` | `NULL` | `descartado` |
| Caso fora do escopo contratado | `ignorada` | `fora_escopo` | `nao_aplicavel` |

**Prós:** preserva todas as nuances que a sócia desenhou; UI pode mostrar
cada faceta separadamente; mudanças futuras numa dimensão não afetam as
outras; auditoria fica clara (quem mudou o quê, quando).

**Contras:** três campos para preencher (UI/UX mais carregada). Demanda
clareza no frontend sobre **quando** cada campo é editável (auditor só toca
`status_achado` na detecção; consultor toca todos na revisão).

### Opção B — Campo único `estado`, máquina de estados explícita

Colapsar tudo numa única coluna `estado` com ~10 valores cobrindo todas as
combinações úteis. A transição entre estados vira máquina de estados (state
machine) — não qualquer valor pode ser definido em qualquer momento.

```python
class EstadoAlerta(str, enum.Enum):
    detectado = "detectado"                    # auditor emitiu, sem revisão
    em_validacao = "em_validacao"              # consultor olhando
    confirmado_pendente = "confirmado_pendente"      # confirmado, aguarda ação
    confirmado_corrigir = "confirmado_corrigir"      # decidido: corrigir antes
    confirmado_com_ressalva = "confirmado_com_ressalva"  # decidido: seguir
    confirmado_solicitar_doc = "confirmado_solicitar_doc"
    saneado = "saneado"
    descartado = "descartado"
    fora_escopo = "fora_escopo"
    ignorado_justificado = "ignorado_justificado"
```

**Prós:** um campo só; máquina de estados garante consistência; relatório
fica simples ("quantos `confirmado_corrigir` por consultor por mês").

**Contras:** explode combinatóriamente quando o domínio cresce (novos
estados intermediários, novos motivos de descarte). Esconde as três
dimensões num único valor — UI tem que decodificar de novo. Quando a sócia
quiser distinguir "saneado por correção" de "saneado por descarte
justificado", a enum cresce em vez de combinar campos.

### Opção C — Híbrida: dois campos (status_achado + decisao), saneamento derivado

`status_saneamento` vira **`computed_field`** (Pydantic) ou view SQL,
derivado dos outros dois + `resolved_at`:

- `status_achado=suspeita` → `pendente`
- `status_achado=confirmada` + `decisao_consultor=NULL` → `em_validacao`
- `status_achado=confirmada` + `decisao_consultor=corrigir_antes` + `resolved_at=NULL` → `em_validacao`
- `status_achado=resolvida` ou `resolved_at!=NULL` → `saneado`
- `status_achado=descartada` → `descartado`
- `status_achado=ignorada` ou `decisao_consultor=ignorar_justificado` → `nao_aplicavel`

**Prós:** Menos colunas no DB; reduz risco de inconsistência (impossível ter
"confirmada + nao_aplicavel" cruzados). UI ainda enxerga os 3 valores como
se fossem campos reais (via computed).

**Contras:** Toda mudança em um campo recalcula o derivado — se a regra de
derivação muda, dados históricos parecem "mudar de status" retroativamente.
Auditoria fica menos óbvia ("quem mudou status_saneamento?" → "ninguém,
foi derivado"). Frontend pode ficar confuso se quiser editar
`status_saneamento` diretamente.

## Recomendação técnica

**Opção A** (três campos ortogonais).

Razões em ordem de força:

1. **Preserva o vocabulário da sócia.** Cada um dos três status apareceu
   num contexto distinto do método dela. Colapsar perde a granularidade que
   distingue um consultor sênior de um júnior — e o sistema existe para
   capturar exatamente essa diferença.

2. **Compatível com o desenho atual.** Hoje o `status_saneamento` já
   aparece no schema da skill diagnostico; o `status` do auditor já está
   especificado na skill auditor; o `decisao_consultor` só falta implementar
   (camada 2 do Princípio 1, rodada seguinte). Opção A é "três PRs
   incrementais", não "uma migração grande".

3. **Auditoria simples.** AuditLog por campo mudado: "consultor X mudou
   `status_achado` de suspeita para confirmada às 14:30" é mais claro que
   "consultor X mudou `estado` de detectado para confirmado_pendente às
   14:30". Princípio 2 do manifesto agradece.

4. **Migração de dados trivial.** Adicionar 3 colunas com defaults sensatos
   é uma migration aditiva. Opção B exigiria mapear cada combinação
   possível dos três conceitos antigos a um valor da nova enum — fica
   forçado.

## Implementação proposta (rodada seguinte, NÃO esta)

Em ordem de pré-requisito:

1. **Onda A1** — adicionar 3 colunas no `RegulatoryIssue`:
   `status_achado` (NOT NULL default `suspeita`), `decisao_consultor`
   (nullable), `status_saneamento` (NOT NULL default `pendente`). Migration
   aditiva.

2. **Onda A2** — auditor preenche `status_achado=suspeita` (default
   explícito) ao gravar findings novos.

3. **Onda B** — endpoint `PATCH /api/v1/properties/{prop}/issues/{id}`
   para o consultor editar os 3 campos. AuditLog separado por mudança de
   campo.

4. **Onda C** — UI consome os 3 campos como facetas independentes. Filtros
   de listagem ganham os 3 critérios.

5. **Onda D** (camada 2 do Princípio 1 — depois desta proposta aprovada):
   na UI de revisão, se `severity=critico`, o consultor é **obrigado** a
   preencher `decisao_consultor` antes de aprovar o diagnóstico via
   `PATCH /validate` (PROMPT_4 Onda B).

## Decisões pendentes do Andre

1. **Aprovar Opção A** (ou contraproposta).
2. **Definir o exato conjunto de valores** das 3 enums com a sócia (a
   listagem acima espelha o que está nas skills hoje — pode ter ajuste de
   nomenclatura).
3. **Definir a transição obrigatória `severity=critico → decisao_consultor`**
   (vai bloquear `PATCH /validate` quando faltar? ou só sinaliza badge?).

## Não-objetivos desta proposta

- Não tocar no `codigo_alerta` / `familia` / `severity` (já modelados pelo
  PROMPT_5 Onda A).
- Não implementar os 5 botões da P4 — depende da decisão acima.
- Não tocar contratos externos (R1).

---

## Status pós-execução (atualizado 2026-05-26)

Opção A **implementada** no PROMPT_6 (merge `08ea537`):
- 3 colunas + 3 enums + `decisao_consultor_justificativa` + `decisao_consultor_at`
  no `RegulatoryIssue` (migration `d2c3e4f5a6b8`).
- `PATCH /properties/{prop}/issues/{id}` para edição parcial com AuditLog
  granular por campo.
- Gate da camada 2 no `PATCH /validate` (422 com lista de pendentes).
- Validator de justificativa obrigatória para `ignorar_justificado` /
  `fora_escopo` (revisão pós-PROMPT_6 — fecha o Princípio 2 no caso de
  descarte).

### Questões pendentes de produto (próxima conversa com Isis)

A implementação do gate seguiu o desenho de schema (Opção A), mas o
**comportamento cross-processo** depende de uma decisão de produto que só
a sócia (Isis) pode tomar. Levar essas perguntas para a próxima
conversa com ela — junto da conferência de fidelidade da skill do auditor:

**Pergunta 1 — `decisao_consultor` é perene ou contextual?**

`RegulatoryIssue` mora em `Property` (perene — vive enquanto o imóvel
existe), mas a **assinatura** é por `Process` (cada demanda é um processo
distinto: venda, crédito, regularização, etc.). A `decisao_consultor` é
campo da issue.

Consequência atual do desenho: uma decisão `seguir_com_ressalva` tomada
no processo A (venda, mês 1) fica gravada na issue. Quando o processo B
(crédito, mês 7, mesmo imóvel) for assinar, o gate vê a issue como **já
decidida** e libera a assinatura — sem o consultor re-olhar.

Só que **titularidade divergente** pesa diferente para venda (compra
direta com pessoa física) e para crédito (banco quer averbação limpa).
"Aceitar o risco" no contexto de venda pode não fazer sentido no de
crédito.

Três posturas possíveis:

- **Perene** (comportamento atual): a decisão é do imóvel, vale para
  sempre. Consultor pode editar via `PATCH /issues/{id}` quando contexto
  novo justificar — mas o sistema não força re-avaliação.
- **Contextual com aviso**: o gate vê a decisão antiga e libera, mas
  sinaliza "esta crítica foi decidida no processo X em tal data — ainda
  vale?" (UI/badge, sem rejeitar).
- **Contextual com força**: o gate **só conta como decidido** se a
  `decisao_consultor_at` for posterior à abertura do processo atual; do
  contrário, exige nova decisão. Mais seguro, mais fricção.

Resposta da Isis define se isso vira ajuste no gate (e em qual direção),
ou se permanece perene + responsabilidade da UI/UX em sinalizar.

**Não bloqueia a UI** — a tela funciona com decisão perene. Mas o
comportamento do gate cross-processo depende dessa resposta.

**Pergunta 2 — fidelidade da skill do auditor.**

A condensação que fizemos da skill `auditor_imovel/
analise_divergencias_documentais` v1.1.0 (40 códigos / 11 famílias / 10
heurísticas / régua de área) é fiel ao documento original v1.0 da Isis
("Instrução operacional para análise de divergências documentais")?
Verificação rápida — não-bloqueante; o conteúdo de domínio já era
"validado por construção" (todo dela), faltou só conferência da redução
feita no `app/skills/auditor_imovel/.../SKILL.md`.
