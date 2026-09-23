# ADR-077 — Fatiamento da matrícula por ato registral antes do extrator

**Status:** proposto · **Data:** 23/09/2026 · **Dívida:** #271 · **Relacionados:** ADR-064 (janela completa), ADR-070 (fragmento), ADR-071 (motor cartorário)

## Contexto

A leitura semântica da ELODI (#23) em produção, em 22–23/09, mostrou que a
matrícula grande não passa pelo extrator numa chamada:

- A matrícula **3.181** (doc 547, 82.117 caracteres) ia em duas fatias de
  ~45 mil caracteres (fatiamento por tamanho do ADR-064). O Luna estourava o
  timeout de 30 s, o gateway caía no Gemini 3.7 Flash, que voltava **truncado**
  (11.996 de 12.000 tokens), e a repetição com 24.000 tokens custava
  **US$ 0,078 numa chamada**.
- A **3.313** (doc 548, 57.090 caracteres) repetiu o ciclo.

O que estoura é a **saída**, não a entrada. Com `AI_TIMEOUT_SECONDS=30` e o Luna
produzindo ~120–135 tokens por segundo (medido nos logs de produção: 3.609
tokens em 30,4 s), uma chamada só fecha no primário se a resposta couber em
uns 3.000 tokens. E o tamanho da resposta segue o número de **atos** na fatia:
cada ato gera partes, participações, datas, valores e o próprio ato.

Não é caso de retry nem de aumentar o timeout (decisão do André, 22/09):
repetir a chamada gigante repete a falha, e esticar o tempo encarece o
documento em vez de resolver o tamanho.

## Decisão

A matrícula vai ao extrator **ato a ato**.

1. **O ato é a unidade.** Um ato começa no seu cabeçalho — `R-09 MAT. 3.181`,
   `AV.05 Mat.`, `R.06-` — **logo depois da linha de traços** que a serventia
   usa como separador, e termina onde o próximo começa. Menções internas
   ("registrada no R-10", "objeto do R-12 acima") não vêm depois de traços e
   não abrem ato. Tudo antes do primeiro ato é a **abertura** (cabeçalho da
   certidão, descrição do imóvel, memorial descritivo). O encerramento da
   certidão fica com o último ato.
2. **Ato inteiro nunca é partido.** Atos pequenos consecutivos podem dividir
   uma chamada, até o máximo declarado.
3. **Tamanhos máximos de chamada declarados**, dois, porque a densidade de saída
   difere por um fator de cinco (seção *Medição*):
   - `EXTRACTOR_ATO_MAX_CHARS = 4.000` — atos (0,9 a 1,6 token de saída por
     caractere de entrada: cada observação repete o trecho literal);
   - `EXTRACTOR_ABERTURA_MAX_CHARS = 6.000` — abertura/memorial (~0,2 token por
     caractere).
4. **Streaming no extrator** (`AI_EXTRATOR_STREAM`, decisão do André em 23/09).
   Com saída de ~1 token por caractere, um ato de 4.000 caracteres pede uns
   5.000 tokens, e o Luna escreve 115–145 por segundo: ~40–50 s. O **valor** do
   timeout não muda (30 s); o que muda é **o que ele mede**: em streaming, o
   limite vale para o provedor **travado** — nenhum byte por 30 s —, não para a
   geração inteira. A duração de cada chamada fica limitada pelo `max_tokens` de
   saída (12.000), não pelo relógio. O uso de tokens vem no último pedaço
   (`include_usage`), então o custo continua sendo o calculado, não estimado.
5. **Ato maior que o máximo** é cortado na fronteira estrutural mais tardia
   antes do máximo — linha em branco, ou fim de linha terminado em `;` ou `.`;
   sem ela, qualquer fim de linha; sem fim de linha, no próprio máximo. Nunca
   antes da metade do máximo, para não multiplicar chamadas. **Sem
   sobreposição:** a identidade da observação inclui a chave da parte, que é
   prefixada por fatia, e sobreposição duplicaria observação. O que cruzar um
   corte vira **rejeição de âncora** — registrada no relatório, nunca silêncio.
6. **Âncora por fragmento.** Cada fatia é registrada como `Fragmento` da versão
   lida. As fatias ladrilham o texto inteiro, sem lacuna nem sobreposição, então
   a âncora de toda observação cai em exatamente uma fatia: a pertença
   ato↔observação é posição, conferível por consulta. O relatório da extração
   (`extracao:rejeicoes:<doc>`, `normalized.fatiamento`) lista as fatias com
   rótulo, atos, limites e `fragmento_id`, e **cada chamada** com modelo,
   tokens, custo, tempo e `finish_reason`.
7. **Sem ato reconhecível** (outra espécie, formato desconhecido), o extrator
   usa o fatiamento por tamanho do ADR-064 — declarado no relatório
   (`metodo: "tamanho"`), não silencioso.

O contrato da observação não muda: o schema de atributos é fechado
(`extra="forbid"`), e o vínculo com o ato sai do fragmento e do relatório.

## Medição

### Por que o ato inteiro não cabe em 30 s sem streaming (dev, 23/09)

Mesmo prompt de sistema do extrator (skill registral + schema, 14.253
caracteres), Luna sem fallback, timeout folgado **só nesta medição**, fatias
reais da matrícula 3.181:

| Fatia | Caracteres | Tokens de saída | Tempo | Saída por caractere |
|---|---|---|---|---|
| abertura (memorial) #1 | 4.594 | 959 | 11,6 s | 0,21 |
| abertura #6 | 5.477 | 1.009 | 9,8 s | 0,18 |
| AV-01 sozinho | 1.767 | 2.218 | 15,4 s | 1,26 |
| AV-01+R-02+AV-05+R-06 | 5.246 | 4.817 | 42,3 s | 0,92 |
| AV-11+R-12 | 4.629 | 5.634 | 47,5 s | 1,22 |
| R-12, metade | 2.980 | 4.776 | 37,9 s | 1,60 |

Sem streaming, uma fatia de ato só fecha no Luna com até ~1.500–1.800
caracteres. **22 dos 67 atos** das quatro matrículas da ELODI passam disso —
cortá-los no meio separaria parte e participação do mesmo ato em chamadas
diferentes. A primeira rodada em dev, com fatias de 6.000 e sem streaming, caiu
no fallback quatro vezes antes de ser interrompida.

### Streaming com o timeout de 30 s intacto

As duas fatias mais lentas acima, em streaming:

| Fatia | Tempo | Tokens de saída | Custo | Modelo | Resultado |
|---|---|---|---|---|---|
| AV-11+R-12 | 45,3 s | 5.558 | US$ 0,0078 | `gpt-5.6-luna` | `stop`, JSON válido |
| AV-01+R-02+AV-05+R-06 | 43,2 s | 4.613 | US$ 0,0067 | `gpt-5.6-luna` | `stop`, JSON válido |

### Prova do caso inteiro (dev, tenant 34, processo 67 — ELODI)

Caminho de produção (execução persistida do ADR-069, sem Celery), caso inteiro
— seis documentos, quatro matrículas —, configuração final: atos até 4.000
caracteres, abertura até 6.000, streaming, `AI_TIMEOUT_SECONDS=30` e fallback
**habilitado** (a mesma configuração operacional de produção). Script:
`scripts/medir_fatiamento_ato.py`, que confere tudo a partir do que ficou gravado.

| Critério | Resultado |
|---|---|
| Chamadas fechando no Luna, sem fallback | **91 de 91** no `gpt-5.6-luna`; **zero** no fallback; zero truncadas. Um timeout isolado, resolvido na nova tentativa do próprio Luna |
| Custo e tempo por fatia | custo total **US$ 0,3672**, mediana por chamada ~US$ 0,004, máximo **US$ 0,0095**; tempo mediano **25 s**, máximo **108 s** (em streaming, sem corte); caso inteiro em 45 min |
| Âncoras | **755 de 755** observações com versão e fragmento; **755 de 755** com o fragmento idêntico ao texto da versão naquela posição |
| Quatro matrículas independentes | cada documento cita o próprio número (3.313: 46; 3.181: 19; 3.673: 17; 4.387: 15). As sete citações cruzadas são leitura correta: a 4.387 registra as outras três como `confrontante_matricula` (as glebas são contíguas), a 3.673 cita o vizinho "Mat. 3181", e duas são dígitos de coordenada |

Recall, na mesma matrícula e no mesmo caso, contra a leitura por tamanho de 21/09:

| Matrícula | Caracteres | Por tamanho (21/09) | Por ato (23/09) |
|---|---|---|---|
| 3.181 | 82.117 | 42 | **242** |
| 3.313 | 57.090 | 102 | **200** |
| 3.673 | 34.815 | 58 | **131** |
| 4.387 | 27.109 | 31 | **158** |

Diagnóstico e prova somados custaram menos de US$ 0,50 em dev. A primeira
rodada (fatias de 6.000, sem streaming) foi interrompida após quatro quedas no
fallback; a transação foi desfeita e a execução ficou marcada como pendente.

## Consequências

- O timeout do extrator passa a medir provedor travado. Um provedor que para de
  responder ainda cai em 30 s; uma resposta longa que continua chegando, não.
- Mais chamadas por matrícula, cada uma pequena. O custo de entrada cresce pela
  repetição do prompt de sistema (skill + schema) em cada chamada; o de saída
  não cresce, porque o total de atos é o mesmo.
- O tempo total por matrícula passa a ser previsível: soma de chamadas que
  cabem no timeout, em vez de ciclos de timeout, fallback e truncagem.
- O fatiamento por tamanho segue para as outras espécies. Contrato longo e
  escritura extensa têm o mesmo risco de resposta grande; ficam fora deste ADR.

## Fora do escopo

- O teto de custo por job (dívida #272) entra no mesmo PR, mas é decisão
  própria: acumulado por `ai_job`, com o teto do extrator calibrado por esta
  medição (US$ 0,3672 × margem de 2× = **US$ 0,75**).
- A paralelização das fatias de um caso no worker (dívida **#280**), depois da
  homologação: não muda resultado, só tempo.

## Junto com este ADR: a fila lê um documento (dívida #279)

`run_agent` descartava o `metadata`, e a execução conectada relia o **caso
inteiro** a cada tarefa. Com o fatiamento, isso ficaria caro: a cadeia OCR →
extrator enfileira uma tarefa por documento, e seis documentos seriam seis
leituras completas. Decisão do André (23/09): corrigir no mesmo PR.

- O `document_id` atravessa a fila (`run_agent` → `_connected_task` →
  `start_execution`) e fica gravado **no passo** da execução persistida, então
  sobrevive a uma retomada; o `run_step` o põe no contexto do extrator.
- A **qualificação cartorária continua sendo do caso**: numa leitura de um
  documento, ela é montada sobre as observações correntes de todos os documentos
  (a última extração de cada um, pelo relatório de cada documento), nunca só
  sobre o documento recém-lido.
- Documento fora do caso (ou apagado, ou saída de IA) falha **dito**, em vez de
  virar uma rodada vazia.

### Prova em dev: subir seis documentos gera seis leituras parciais

Cadeia do upload reproduzida documento a documento (tarefa de OCR pelo caminho
de cache → extrator), com o código desta mudança, Celery em modo *eager*,
caso ELODI (tenant 34, processo 67). Script: `medir_fatiamento_ato.py
--simular-upload`. "Documentos lidos" vem dos rótulos das chamadas gravadas no
job, não do que o script supõe.

| Documento | Documentos lidos pelo job | Chamadas | Custo | Tempo |
|---|---|---|---|---|
| 154 · CAR | [154] | 1 | US$ 0,0041 | 62 s |
| 155 · matrícula 3.313 | [155] | 24 | US$ 0,1060 | 529 s |
| 156 · matrícula 3.181 | [156] | 29 | US$ 0,1094 | 763 s |
| 157 · matrícula 3.673 | [157] | 17 | US$ 0,0667 | 577 s |
| 158 · CNH | [158] | 1 | US$ 0,0018 | 32 s |
| 159 · matrícula 4.387 | [159] | 14 | US$ 0,0657 | 448 s |
| **Total** | **6 leituras de um documento** | **86** | **US$ 0,3537** | **2.411 s (40 min)** |

Sem a correção, seriam **seis leituras completas** — ~US$ 2,20 e ~4 h 30 de
worker. Com ela, o upload do caso custa uma leitura completa.

Depois da última leitura parcial, a qualificação cartorária do caso tem **700
premissas vindas dos 6 documentos**, e as âncoras seguem **700 de 700**.

*Variação entre rodadas:* o número de observações por documento varia de uma
leitura para outra (o CAR foi de 20 para 5; a 4.387, de 158 para 124). O
caminho do CAR não muda nesta decisão; o Luna só aceita temperatura 1, então
duas leituras do mesmo texto não produzem a mesma lista. É registro, não
conclusão: medir a estabilidade do recall é trabalho próprio.

