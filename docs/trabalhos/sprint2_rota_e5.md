# Sprint 2 — Rota / E5

**Branch:** `feat/rota-e5-reordenacao` · **Data:** 07/08/2026
**ADR:** [061 — Remoção de passo da Rota é lembrada](../adr/061-remocao-de-passo-da-rota-e-lembrada.md)
**Dívidas abertas:** #304 (dnd-kit como opção), #305 (tela dos removidos)

---

## O que o retrato mudou no sprint

O sprint entrou assumindo que a Rota era "o maior vazio de valor da Ficha 07" e
que faltava construí-la: persistência, drag-and-drop, validação. O Passo 0
mediu, e a premissa não se sustentou.

**Já existia, funcionando:** os 3 modelos (`Rota`, `RotaPasso`, `RotaVersao`),
10 endpoints, materialização com reconciliação aditiva, versionamento antes de
cada regeneração, guard de esfera (ADR-034), o gate `has_rota_validada` lendo o
estado certo, 8 arquivos de teste — e a tela inteira, `RotaTab.tsx` com 464
linhas, **com drag-and-drop já implementado** sobre o `Reorder` do framer-motion.

Isso derrubou o item central do escopo. A migração para `@dnd-kit` tinha sido
aprovada na crença de que não havia arrasto nenhum; havia. O André reverteu a
aprovação com o motivo escrito, e a acessibilidade de teclado — o buraco real —
foi resolvida por botões ↑/↓ chamando o mesmo endpoint. Registrado em #304.

## A queixa da Isis, medida

*"Gerar rota não deu em nada."* A leitura natural é que a geração falhou. A
trilha de auditoria do caso 16 diz outra coisa:

```
15:37:53  rota_materializada     created=5 matched=0
15:43:15  rota_passo_removido    passo 41 · ordem 2
15:43:18  rota_passo_removido    passo 42 · ordem 3
15:43:23  rota_passo_removido    passo 43 · ordem 4
15:43:26  rota_passo_removido    passo 44 · ordem 5
(05/08)   rota_fechada           passos=1
```

O job 1181 emitiu 5 etapas (CAR → validação → PRA → aprovação → DAI) e as 5
foram persistidas. **A geração funcionou.** A consultora removeu 4 em 11
segundos e fechou a rota com 1 passo.

O defeito estava no passo seguinte: `_reconcile_passos` casava a proposta da IA
contra os passos existentes, e o passo apagado não existia mais para casar — era
**recriado**. Qualquer "Atualizar da IA" traria os 4 de volta, um a um. É aí que
regerar "não dá em nada": desfaz o trabalho em vez de somar a ele.

## O que foi entregue

**1. Remoção lembrada (ADR-061).** `RotaPasso.deleted_at` em vez de `DELETE`. A
linha fica segurando a `dedupe_key` — é a chave ocupada que faz a reconciliação
reconhecer o passo e não recriá-lo. `Rota.passos` filtra as lápides na própria
relação, então os ~20 consumidores (gate, proposta, snapshot, fechar) continuam
vendo só a rota viva. A supressão é contada (`suprimidos`) e dita na tela, nunca
silenciosa; e **não** conta como diff, senão a rota assinada seria rebaixada para
`desatualizada` a cada regeneração e "Fechar rota" travaria para sempre.

**2. Feedback de estado.** `commitOrder` só tinha voz no erro. Agora sucesso fala
(`toast.success('Ordem salva.')`), há indicador "salvando ordem…" no cabeçalho, e
**falha devolve a lista à ordem do servidor** — manter na tela uma ordem que não
gravou é a mentira que o #141 ensinou a não contar.

**3. Teclado.** Botões ↑/↓ ao lado do handle, mesma função `salvarOrdem`, mesmo
`PATCH /reordenar`. O número do passo passou a vir do índice, não de `passo.ordem`
— entre o gesto e a resposta, a `ordem` gravada ainda é a antiga e dois passos
apareciam com o mesmo número.

**4. Restaurar.** `POST /rotas/{id}/passos/{id}/restaurar`. Sem tela (#305): a
remoção lembrada fechou o *desfazer acidental* que a regeneração fazia sem
querer, e deixar isso sem contrapartida tornaria um clique na lixeira definitivo.

## Medição — o teste falsificado

O sprint pedia regerar a rota do caso 16 em DEV e contar passos antes e depois.
**Não é reproduzível:** o processo 16 do banco de dev é `Smoke Homologacao`, dado
de fumaça sem relação com o caso de produção, e dev tem **zero** rotas. A
pergunta que a medição responderia já tinha resposta melhor — a trilha de
auditoria acima, com número exato.

No lugar, foi medido o que importa: **o teste do gate falha sem o fix?**
Desligada apenas a supressão, com as lápides no banco, o teste não só falha —
a regeneração **quebra**:

```
sqlalchemy.exc.IntegrityError: (psycopg2.errors.UniqueViolation)
duplicate key value violates unique constraint "uq_rota_passos_tenant_dedupe"
```

Ou seja: a supressão não é enfeite do tombstone, é o que o torna viável. E o
teste não é vacuoso — ele reprova a ausência do fix.

## Suítes — números conferidos

| Suíte | Arquivos | Testes | Resultado |
|---|---|---|---|
| Frontend (`npm test`, runner do projeto) | **23** | **148** | verde |
| Backend — Rota (`test_rota_materializer` + `test_rota_e5`) | 2 | **26** | verde |

Os 23 arquivos executados batem com os 23 no disco (`find src -name "*.test.ts*"`),
e os **12** arquivos `@vitest-environment jsdom` estão entre eles. Conferido por
contagem, não por leitura do "verde" — a lição de 06/08 foi que 11 arquivos jsdom
não rodavam e o resumo imprimia verde do mesmo jeito.

## Pergunta de produto — para a Isis, não para o código

**Falta um gesto de "rejeitar" ao lado da lixeira.**

A trilha mostra 4 remoções em 11 segundos. Apagar era o único gesto disponível:
se ela quisesse dizer *"este passo não se aplica a este caso"* — que é
informação, e informação que o sistema deveria aprender — não tinha como. Só
tinha como fazer o passo sumir.

São coisas diferentes:

- **remover** — "isto não deveria estar aqui" (erro da IA, ruído);
- **rejeitar** — "isto é um passo válido, mas não neste caso" (decisão técnica,
  com motivo, que vale registrar e um dia realimentar o modelo).

Hoje as duas saem pela mesma porta e o sistema não distingue. Não foi
implementado por conta própria: é desenho de produto. A resposta também decide o
#305 — se "rejeitar" existir, a lista de removidos provavelmente vira "passos
recusados, com motivo", e o restaurar ganha lugar natural ali.
