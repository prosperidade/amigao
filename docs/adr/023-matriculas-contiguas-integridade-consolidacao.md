# ADR-023 — "Matrículas contíguas?" tri-state + integridade da consolidação multi-documento

- **Status:** Aceita
- **Data:** 2026-07-04
- **Espec de origem:** Ficha 07 §9 (verbatim: "grupo de matrículas contíguas do mesmo
  titular = um imóvel rural, um CAR; Lei 8.629/93 art. 4º I; Estatuto da Terra art. 46
  §3º; IN MMA 02/2014 art. 31–32. Matrículas não contíguas → tratadas separadamente.
  O sistema precisa do campo 'matrículas contíguas?'")
- **Relacionada a:** ADR-015 (1 Imóvel : N Matrículas), ADR-017 (consolidação parcial),
  ADR-022 (selo/field_sources), Princípios 1 (humano decide) e 2 (tudo auditável)
- **Diagnóstico de origem:** read-only 2026-07-04 (caso 13 como espécime)

## Contexto

O modelo assumia contiguidade como PRESSUPOSTO, não como pergunta: o comentário do
`Matricula` dizia "N Matrículas (contíguas sob o mesmo CAR)", `area_total_matriculas()`
somava tudo sem grupo, e `car_code` é um slot único. O caso 13 provou o custo: a
Property 10 agregava 5 matrículas de DUAS fazendas de titulares distintos + uma
"matrícula" fantasma (nº de certidão de embargo), somando 1.713 ha onde o imóvel real
tem ~1.010 ha — e esse número alimentava Hub, dossiê, contrato e prompts de IA.

O mesmo espécime expôs dois defeitos de integridade independentes da contiguidade:

1. **Bucket único por tipo de documento na matriz** (`_group_sources`): dois CCIRs no
   mesmo processo colapsavam numa source "ccir" — `fields[fname]` sobrescrevia o
   primeiro em silêncio e a divergência NUNCA era acusada. Na comparação de área por
   matrícula, keep-max fazia o mesmo. Resultado: dois CCIRs completos e conflitantes na
   matrícula 2923 passaram sem divergência e a consolidação gravou o "vencedor" por
   menor id (um registro frankenstein colhido da legenda de confrontações de uma planta).
2. **Criação de matrícula por hint sem critério de origem**: a certidão de embargo
   classificada como `sigef` criou a matrícula 492262 (nº da certidão).

## Decisão

**1. Campo `matriculas_contiguas` Boolean NULLABLE no `Property` (tri-state).**
`NULL` = não informado (estado de todo o legado — SEM backfill); `True`/`False` =
declaração do consultor. A cópia da UI pergunta a condição legal completa ("contíguas
e do mesmo titular?"); o nome do campo segue a Ficha verbatim. Declarar grava selo
`human_validated` em `field_sources` (padrão ADR-022) + AuditLog hash chain
(`declarar_contiguidade`). Migration `b7c9d1e3f5a7`.

**2. "Não" = declarar-e-avisar (orientação, nunca automação).** Com `False`/`NULL` e
>1 matrícula, a soma derivada é **ANOTADA, nunca suprimida**
(`Property.nota_soma_matriculas()`): a ressalva viaja junto do número no dossiê, no
fallback do Hub, no resultado da consolidação e nos contextos de prompt do diagnóstico
e da legislação (o LLM não raciocina porte/passivo sobre soma possivelmente fictícia
sem saber disso). Lacunas: "contiguidade não declarada" (>1 matrícula, `NULL`) é
informativa em dossiê + can-advance; `False` gera aviso orientando a separação.
**NUNCA trava** (radar-não-cancela). De quebra, a lacuna "área total não informada"
passou a considerar a soma derivada — fim do falso positivo pós-consolidação.

**3. Re-home mínimo.** `PATCH /properties/{pid}/matriculas/{mid}` move a matrícula
para outro imóvel do MESMO tenant, auditado com hash chain — torna acionável o
"tratadas separadamente" da Ficha (cadastrar outro imóvel + mover). Split-wizard de UI
é follow-on (#57).

**4. Fix do bucket — source por (doc_type, document_id).** Tipos com N documentos
distintos ganham chaves por doc (`ccir#228`, `ccir#231`) em `_group_sources` E na
coleta de áreas por matrícula — dois CCIRs viram duas fontes REAIS em confronto
(divergência na matriz, gate no aceitar). Tipos com 1 doc mantêm a chave simples
(labels e comportamento inalterados). Consumidores singleton (car/itr/sigef/rat) usam
a 1ª source do tipo; os confrontos campo-a-campo iteram todas.

**5. Coerência matriz×consolidação.** A consolidação NUNCA escolhe silenciosamente
entre dois valores completos conflitantes de documentos distintos: o grupo volta a
`divergente_transcricao` e vira Ação (caminho da Ficha §3.3 — escolher fonte /
digitar / criar ação). `_pick_winner` só desempata PROVENIÊNCIA do mesmo valor
(edição do consultor > âncora SIGEF > confiança > id). Edição explícita do consultor
É decisão — vence e grava. Área normaliza pela porta única antes de comparar
(`349,9022 ≡ 349.9022` não é conflito).

**6. Guard fantasma.** Só documentos que legitimamente DECLARAM matrícula
(`matricula`/`ccir`/`itr`/`car`) criam `Matricula` nova na consolidação. `sigef` e
demais tipos apenas ATUALIZAM matrícula existente — foi o vetor real da fantasma
492262 (certidão de embargo e contrato PRAD mal-classificados como `sigef`). Hint
órfão fica no staging e é reportado em `ignorados`; o cadastro manual
(`POST /properties/{id}/matriculas`) segue como via legítima.

## Nota sobre contrato (decisão de produto)

`contract_generator.py` segue lendo `total_area_ha` SEM caveat neste sprint: a
honestidade chega por prompts + UI; inserir ressalva automática em peça jurídica é
decisão de produto que a dupla fundadora ainda não tomou. O fix REAL para o caso
não-contíguo é a separação em imóveis distintos (re-home + follow-ons #55–#57), que
zera o problema na origem.

## Consequências

**Positivas**
- O sistema PERGUNTA a condição legal em vez de pressupor; a resposta é auditável e
  selada; a soma nunca mente sem avisar.
- Dois CCIRs conflitantes não passam mais em silêncio — o caso 13 (frankenstein da
  2923 + fantasma 492262) torna-se irrepetível por construção.
- Nenhum gate novo: tudo informativo/orientativo, coerente com radar-não-cancela.

**Custos / riscos residuais**
- `matriculas_contiguas=False` não modela OS GRUPOS (qual matrícula pertence a qual
  imóvel real) — é declaração + orientação. Modelagem por grupo é a dívida #55; N CARs
  é a #56.
- A classificação rule-based ainda pode sequestrar tipos (planta→ccir por menção
  interna) — o guard fantasma e o fix do bucket mitigam o DANO (nada grava sem
  divergência acusada), mas tipos próprios para planta/memorial/auto-de-infração
  continuam desejáveis (registrado no diagnóstico de 04/07).
- Consumidores singleton da matriz usam a 1ª source do tipo quando há N docs; campos
  exclusivos do 2º doc não entram nos confrontos singleton (car_presenca etc.). Dois
  CARs reais = mundo do #56.

## Validação

- `tests/services/test_inconsistency_matrix.py` — fixture com o shape do caso 13
  (2 CCIRs completos conflitantes na 2923): divergência de área/denominação acusada,
  INCRA em atenção, back-compat de chave simples com 1 doc.
- `tests/api/test_sprint4_contiguidade.py` — selo+audit do PATCH, soma anotada
  (Hub/dossiê), lacunas (multi vs 1 matrícula; nunca trava), re-home (move/no-op/404),
  conflito devolvido + edição do consultor resolve, guard fantasma (não cria / atualiza
  existente).
- `tests/api/test_repro_caso13.py` atualizado para o novo contrato: 492262 NÃO nasce,
  proprietarios conflitantes da 2923 devolvidos como divergência (4ª ação).
