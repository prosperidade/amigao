# ADR-031 — Fonte única de requisitos documentais

- **Status:** aceita
- **Data:** 2026-07-20
- **Branch:** `fix/fonte-unica-requisitos-documentais`
- **Contexto de domínio:** Ficha 08 (`docs/fichas/FICHA_08_BASE_DADOS_CONFERENCIA.md`), §2 e §7
- **Auditoria que motivou:** `docs/auditoria/AUDITORIA_REQUISITOS_DOCUMENTAIS_2026-07-20.md`

## Contexto

O consultor viu "4 documentos pendentes" e "Matrícula do imóvel ausente" num caso
onde a certidão de inteiro teor tinha sido enviada, lida por OCR e já tinha o
número extraído no staging.

A auditoria mostrou que não era um bug: era a ausência de um conceito. **Nove**
pontos do código respondiam "o requisito documental está satisfeito?", cada um
com fonte da verdade própria — `Document.document_type` cru, JSON do
`ProcessChecklist`, `Property.registry_number`, `Matricula` materializada,
`Matricula.codigo_incra_sncr`. No processo 15, três deles discordavam sobre a
mesma matrícula no mesmo instante:

| superfície | resposta |
|---|---|
| checklist (`items[].status`) | SATISFEITO |
| dossiê (`MISSING_MATRICULA`) | AUSENTE, severity `error` |
| realidade | recebido, em processamento |

Nenhuma das duas respostas exibidas era verdadeira.

O forense caso Isis já havia corrigido **um** desses emissores para enxergar
**uma** fonte a mais. Foi correto e insuficiente: sem um lugar onde a resposta
mora, cada superfície nova reimplementa a pergunta, e cada reimplementação nasce
com um recorte diferente. Corrigir o nono ponto produziria o décimo.

## Decisão

**1. Existe um único lugar que responde "este requisito documental está
satisfeito?": `app/services/requisito_documental.py`.** Todos os consumidores
migram para ele. Nenhuma superfície reimplementa a pergunta.

**2. A resposta tem quatro estados, não dois.** O booleano
satisfeito/pendente era a raiz da desonestidade — ele não tinha como expressar o
estado real do caso 15:

| estado | significado |
|---|---|
| `AUSENTE` | nenhum documento na base serve a este requisito |
| `RECEBIDO_EM_PROCESSAMENTO` | arquivo chegou; o sistema ainda não o leu |
| `SATISFEITO_PARCIAL` | lido, mas falta sub-campo essencial (Ficha §7.1) |
| `SATISFEITO` | lido e completo |

**3. Requisito documental é sobre o DOCUMENTO, não sobre o dado consolidado.**
Colapsar os dois eixos foi a causa raiz: o dossiê perguntava "o dado está
materializado?" e imprimia a resposta como "o documento existe?". A consolidação
(Ficha 05) continua sendo o ato que leva o dado à base, e continua sendo cobrada
— mas com o nome certo (`MATRICULA_EM_PROCESSAMENTO`, severity `info`), não como
ausência de documento.

**4. O vocabulário é traduzido num único mapa `doc_type → requisito.`** Comparar
`document_type` por igualdade de string fazia `certidao_inteiro_teor` nunca casar
com `matricula`, e `cpf_cnpj` nunca casar com `doc_pessoal`.

**5. A lista canônica são os 6 da Ficha 08 §2.** A Licença Ambiental (candidata a
7º) está EM ABERTO na Ficha §6.4 e **não** entra até a Isis decidir.

**6. P12 aplicado a requisitos: o consultor nunca lê "ausente" com o documento
visível na tela.** A frase exibida vem pronta do backend (`detalhe`), justamente
para a tela não reimplementar a redação — foi a redação duplicada que produziu as
respostas divergentes.

**7. Nada disto trava mais do que travava antes (radar-não-cancela).** Vencimento
gera alerta (§7.3). `SATISFEITO_PARCIAL` não é pendência de coleta — o documento
chegou; o que falta vira `gaps` nos campos dependentes.

## Consequências

**Boas:**
- A pergunta tem um dono. O décimo consumidor não nasce doente.
- A tela deixa de mentir em três casos medidos no processo 15: matrícula
  ("ausente" com a certidão anexada), `doc_proprietario` (pendente com a CNH
  anexada), e a contagem de pendentes que alimentava o gate de avanço.
- Duas divergências silenciosas morreram junto: a vigência inconsistente dentro
  do próprio `dossier.py` (uma regra usando `matriculas_vigentes()`, outra
  `prop.matriculas`) e a **terceira** cópia do laço de contagem — que a auditoria
  não tinha achado e que alimentava justamente o gate que TRAVA o avanço.

**Custos e limites:**
- `avaliar_requisitos` faz 2 queries por processo. No kanban é lazy: só toca o
  banco quando algum item do checklist é um dos 6.
- O `ProcessChecklist` por demanda continua existindo com itens fora dos 6 (fotos
  da área, laudo, auto de infração). Para esses, o JSON segue sendo a verdade —
  a fonte única só tem palavra final sobre os 6.
- Os 36 documentos com `document_type = NULL` do processo 15 continuam invisíveis
  para o matching: a fonte única lê o tipo persistido, e nada o repara depois da
  classificação por conteúdo. É a dívida **#70**, deliberadamente fora deste PR.

## Alternativas descartadas

- **Corrigir só o emissor do dossiê** (o nono ponto). É o que o forense fez; o
  sintoma reapareceu em outra superfície. Foi o que motivou este ADR.
- **Materializar o estado numa coluna.** Estado derivado gravado precisa de
  invalidação a cada upload/OCR/extração/consolidação — a mesma classe de bug do
  vínculo-como-evento (D4/D5 da auditoria), agora com dado velho persistido.
  Calcular sob demanda é barato e não pode ficar defasado.
- **Fazer a UI decidir a redação.** Foi assim que três telas passaram a dizer
  coisas diferentes sobre o mesmo fato.

## Referências

- Ficha 08 §2 (a lista), §7.1 (sub-campos), §7.2 (equivalência), §7.3 (vencimento)
- ADR-027 (vigência da cadeia de fichas) — presença ≠ vigência
- Princípio 12 (semântica honesta) e radar-não-cancela
- Dívidas abertas por este PR: #70 a #77
