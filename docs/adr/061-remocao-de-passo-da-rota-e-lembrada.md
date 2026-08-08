# ADR-061 — Remover um passo da Rota é decisão que a regeneração respeita

**Status:** aceita
**Data:** 2026-08-07
**Contexto:** Sprint 2 / E5 (Rota Regulatória)
**Relacionadas:** [ADR-039](039-rota-nasce-do-diagnostico-fundamentado.md) ·
[ADR-016](016-acao-nao-resolve-passivo.md) ·
[ADR-017](017-consolidacao-parcial-ponte-matricula-imovel.md)

---

## Contexto

A reconciliação da Rota já era aditiva e não-destrutiva por projeto: re-rodar a
`LegislacaoAgent` preservava ordem, edição, classificação e passo manual do
consultor. Uma coisa ficou de fora — **remover**.

`_reconcile_passos` casa a proposta da IA contra os passos que existem
(`rota.passos`). O passo apagado saía da tabela, logo não estava mais lá para
casar: a etapa caía no ramo "passo novo" e era **recriada**.

A medição, na trilha de auditoria do caso 16 (02/08/2026):

```
15:37:53  rota_materializada     created=5 matched=0
15:43:15  rota_passo_removido    passo 41 · ordem 2
15:43:18  rota_passo_removido    passo 42 · ordem 3
15:43:23  rota_passo_removido    passo 43 · ordem 4
15:43:26  rota_passo_removido    passo 44 · ordem 5
(05/08)   rota_fechada           passos=1
```

A geração funcionou — cinco passos. A consultora removeu quatro em onze
segundos. Qualquer "Atualizar da IA" seguinte traria os quatro de volta, um a
um, e o trabalho dela voltaria desfeito. É o mecanismo por trás da queixa
literal de 02/08: *"gerar rota não deu em nada"*.

O `preservar_versao` (foto antes de cada regeneração) é rede de segurança
posterior ao dano — devolve o estado anterior *depois* que o consultor percebe.
Não impede o desfazer.

## Decisão

**Remover um passo é gesto humano com a mesma força de validar um. A
regeneração nunca o desfaz.**

1. A remoção passa a ser **lembrada**: `RotaPasso.deleted_at` (+
   `deleted_by_user_id`) em vez de `DELETE`. A linha fica, segurando sua
   `dedupe_key` — é a chave ocupada que faz a reconciliação **reconhecer** o
   passo e não recriá-lo.
2. `Rota.passos` filtra as lápides na própria relação. Os ~20 consumidores
   (gate da macroetapa, proposta, snapshot, "fechar rota", contexto) querem a
   rota viva e não precisam saber que lápides existem.
3. A supressão é **contada e reportada** (`suprimidos`), nunca silenciosa: a
   tela diz "N passo(s) que você removeu continuam fora". Sem isso o consultor
   leria "nenhum passo novo" e concluiria que a atualização não rodou.
4. `suprimidos` **não** conta como diff. Um passo removido que a IA insista em
   propor seria diferença eterna, rebaixando a rota assinada para
   `desatualizada` a cada regeneração e travando "Fechar rota" para sempre — o
   mesmo beco sem saída que a validação de 02/08 já custou uma vez.
5. Remover deixa de ser irreversível: `POST /rotas/{id}/passos/{id}/restaurar`
   devolve o passo por UPDATE, com classificação, validação e proveniência
   intactas.

## Consequências

**A favor.** O gesto do consultor sobrevive à regeneração — que é a promessa do
Princípio 1 aplicada ao lado que faltava. A remoção fica auditável em duas
camadas (AuditLog + a própria lápide, com autor e horário). Restaurar preserva
identidade e trabalho, coisa que um re-INSERT não faria.

**Contra, e assumido.** A tabela cresce com linhas que ninguém mais vê. É o
preço de lembrar, e é pequeno diante do custo do esquecimento.

**Consequência que exigiu contrapartida.** Antes desta ADR, regerar funcionava
como um *desfazer acidental*: quem apagava por engano recuperava o passo na
regeneração seguinte. Fechar essa porta sem abrir outra tornaria um clique na
lixeira definitivo. Daí o endpoint de restauração — hoje sem tela (o desenho da
lista de removidos é decisão de produto, em aberto com a Isis).

**Descoberto ao falsificar o teste.** Com as lápides no banco e a supressão
desligada, a regeneração não apenas ressuscitava o passo: ela **quebrava** com
`UniqueViolation` em `uq_rota_passos_tenant_dedupe`. A supressão não é enfeite
do tombstone — é o que o torna viável.

## Alternativas descartadas

**Manter o `DELETE` e confiar no `preservar_versao`.** A versão é foto, não
trava: o consultor teria de perceber o estrago e restaurar à mão, a cada
regeneração. Trata o sintoma.

**Guardar as remoções numa tabela própria de exclusões.** Duas fontes de
verdade sobre o mesmo passo, e a `dedupe_key` livre para ser reocupada por um
INSERT — exatamente a colisão que o `UniqueViolation` acima expôs.

**Não permitir remover, só "ocultar".** É o desenho que a Isis talvez queira
(ver pergunta em aberto sobre "rejeitar"), mas trocar o verbo sem resolver a
memória não conserta nada: o passo oculto voltaria igual.
