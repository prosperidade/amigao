# Zona normativa — Incremento 4a (implementação do ADR-075 + A1–A5)

**Data:** 22/09/2026 · **Branch:** `feat/inc4a-zona-normativa` · **Banco:** dev `amigao_db` @
`127.0.0.1:15432` (alembic `073zn001`). **Produção: nada aplicado, nada lido.**
**Decisões:** [ADR-075](../adr/075-zona-normativa-hierarquia-e-recuperacao.md) e adendos A1–A5 —
este documento registra a execução e a medição, não decide nada novo.
**Legislação continua desligada:** as sondas não passaram o portão (§5).

## 1. O que entrou

| Peça | Onde | ADR |
|---|---|---|
| Esquema: `fonte_normativa`, `fonte_normativa_versao`, `fonte_normativa_proveniencia`, `dispositivo`, `trecho_normativo`, `interpretacao_norma`, `validacao_norma`, `papel_curadoria`, `tarefa_revisao_normativa` | `alembic/versions/073zn001_…`, `app/models/zona_normativa.py` | §1, §4, §5, A1, A2, A3, A5 |
| Identidade canônica `tipo\|ente\|órgão\|número\|ano` (função única) | `services/zona_normativa/identidade.py` | §5 |
| Desmembramento das 32 coletâneas por regra fixa, sem LLM/OCR | `desmembramento.py` | §5 |
| Dispositivo (artigo + parágrafo) endereçável | `dispositivos.py` | A1 |
| Nível de autoridade por regra sobre o gravado | `hierarquia.py` | §1 |
| Construção do catálogo (dry-run por padrão) | `catalogo.py`, `scripts/zona_normativa_construir.py` | §5, D2 |
| Recuperação: identidade → elegível → RRF → uma vaga por dispositivo; interpretação anexada; vazio com as 5 razões; nunca relaxa | `recuperacao.py`, `POST /api/v1/acervo-normativo/recuperar` | §3, §7 |
| Citação por ID verificada antes de emitir; menção sem ID bloqueia | `citacao.py`, `POST …/citacoes/verificar` | §8 |
| Curadoria por papel e área; `bruto → proposto → validado`; lote por coletânea; hash chain global append-only | `curadoria.py`, `…/versoes/{id}/propor\|validar\|devolver`, `…/coletaneas/{id}/propor-lote\|validar-lote`, `…/curadores` | §4, A1, A2 |
| A2 no legado: `POST /legislation/documents`, `/upload`, `/reindex`, `POST /knowledge/index`, `/reindex-legislation` exigem `curar_corpus` | `api/deps.py:get_curador_do_corpus` | A2 |
| A5: original guardado em `zona-normativa/originais/<sha256>` + conferência diária (beat 04:15) que bloqueia divergência | `integridade.py`, `workers/zona_normativa_tasks.py` | A5 |
| Sondas (45) + executor com cache de vetores | `tests/recuperacao/sondas.yaml`, `scripts/sondas_recuperacao.py` | §9 |

O legado (`legislation_documents`, `knowledge_catalog`) não recebeu coluna, UPDATE nem
reindex. A recuperação nova lê só as tabelas novas.

## 2. Desmembramento (medido no dev)

Regra: (1) **troca de URL no rodapé de impressão ou paginação voltando a 1** fecha um documento;
(2) nas regiões sem impressão, **cabeçalho formal em maiúsculas seguido de ementa ou preâmbulo**;
(3) o resto fica `nao_determinado`. Achados que mudaram a regra durante a medição:

- a extração coloca cabeçalho **e** rodapé de impressão no fim da página (MS/MT/GO); no Acre
  o `n/m` vem linhas abaixo da URL — o Acre também é impresso (a medição de 18/09 supunha que não);
- URL longa sai truncada com `…` e perde um caractere quando a página passa de `9/18` a `10/18`:
  comparar por prefixo, senão a mesma lei vira quatro;
- paginação solta `1/01` no MT-NUC04 é código CNAE — só conta `n/m` preso a URL;
- o Diário Oficial de MT de 26/09/2018 inteiro está dentro de MT-NUC02 e NUC05 (portarias da
  SEDUC, SEJUDH…): são atos reais, cortados como tal.

| | Resultado |
|---|---|
| Segmentos | 802 (331 por impressão, 413 por cabeçalho, 58 sem sinal) |
| Atos com identidade fechada | **420 distintos**, 496 redações (55 atos com mais de uma = versões) |
| Não determinados | 101 segmentos, **15% do texto** das coletâneas → tarefa de revisão |
| Fronteira a revisar | 25 (início estimado, página 1 ausente, mais de um ato na impressão, título ≠ cabeçalho) |
| Catálogo | **868 fontes** (767 com identidade, 743 buscáveis), 960 versões, 1.165 proveniências, **204 atos com mais de uma proveniência** |
| Nível | norma 481 · exigência 249 · procedimento 7 · interpretação 5 · radar 1 · não determinado 125 |
| Dispositivos / trechos | 29.113 / 20.059 (19.006 embarcados, 1.053 vetores SEMAD reaproveitados) |
| Custo de embedding | ~7,4 M tokens ≈ US$ 0,15 (`text-embedding-3-small`, 768d) |

Os números desta tabela são da **primeira** construção. Depois dos dois cortes novos da segunda
rodada (§8.1) o catálogo foi reconstruído: **878 fontes** (768 com identidade, 744 buscáveis),
972 versões, 1.177 proveniências, 29.157 dispositivos, 19.330 trechos, 421 atos distintos.
A conciliação com a estimativa do ADR está no §8.6.

Relatório por coletânea (sem texto de norma, só cabeçalhos, páginas e motivos):
[provas/inc4a_desmembramento_dryrun_2026-09-22.json](provas/inc4a_desmembramento_dryrun_2026-09-22.json).

**Limite conhecido do extrator de artigos:** citação *sem aspas* de artigo de número maior que o
corrente abre artigo (a regra de ordem só protege número menor). Dois defeitos achados na
medição e corrigidos com regressão: `Art. \n79.` (o art. 79 do Decreto 6.514 sumia) e
`Art. 2º- A licença` lido como art. 2-A (a CONAMA 237 ficava sem artigos).

## 3. Parâmetros provisórios (declarados, num lugar só)

| Parâmetro | Valor | Onde | Resolve |
|---|---|---|---|
| Ficha de tipologia SEMAD | `exigencia` | `hierarquia.NIVEL_TIPOLOGIA_SEMAD` | Q-ISIS-18 |
| Objetivo de ato desmembrado | do núcleo da coletânea | `hierarquia._OBJETIVOS_NUCLEO` | curadoria na validação |
| Fonte sem objetivo declarado | entra marcada `objetivo_nao_declarado` | `recuperacao._filtros` | — |
| Objetivo de origem provisória | **não filtra**; entra marcado `objetivo_provisorio` (§8.2) | `recuperacao.ORIGENS_OBJETIVO_PROVISORIAS` | curadoria declarar o objetivo |
| Lexical na fusão | só **termo raro** (< 1% dos trechos), peso 0,5 (§8.3) | `recuperacao.PESO_LEXICO`, `FRACAO_MAXIMA_TOKEN` | rodada de sondas |
| Segmento absorvedor | acima de 10.000 caracteres por artigo, corte por cabeçalho perde a identidade (§8.1) | `desmembramento.LIMITE_CHARS_POR_ARTIGO` | revisão humana |
| Validação em lote | proposta usa a URL impressa como fonte oficial e vigência "não sei" | `curadoria.propor_lote_coletanea` | Ísis |

Q-ISIS-19 (índice das coletâneas) continua aberta: a lista de atos da Ísis encurtaria a revisão
dos 101 não determinados.

## 4. Percurso autenticado em dev

Login real (admin e consultor do tenant 2), API da worktree em `127.0.0.1:8011`. Transcrição sem
token: [provas/inc4a_percurso_dev_2026-09-22.json](provas/inc4a_percurso_dev_2026-09-22.json).

1. A2: superusuário **sem papel** e consultor recebem 403 ao escrever no corpus legado.
2. Peça em GO antes de validar: vazio `sem_fonte_elegivel`, filtro `status`.
3. Coletânea 13 desmembrada: 39 atos, 25 determinados. Lote sem papel → 403; com papel
   concedido (GO) → 15 propostos, 24 pulados com motivo (fronteira em revisão, identidade não
   fechada), 15 validados.
4. Peça continua vazia — agora pelo filtro `vigencia`: o lote propõe com vigência "não sei", e
   validado sem vigência declarada **não** vira citável em peça. Comportamento do contrato.
5. Lei GO 18.104/2013 proposta com vigência declarada e `validation_keyword`, validada: a peça
   devolve art. 29 em 1º, `validado`, sem marca; "art. 29 da Lei 18.104/2013" vai por identidade.
6. Citação: válida emite; menção à Lei 12.651/2012 sem ID → `citacao_orfa`; art. 25 mencionado
   sem vínculo → bloqueia; art. 999 → `dispositivo_inexistente`.
7. Cadeia do catálogo íntegra (32 eventos). `UPDATE`/`DELETE` em `validacao_norma` → recusados
   pelo gatilho. A5: 76 originais conferidos contra o MinIO, 76 conferem.

O percurso achou dois defeitos, corrigidos com regressão antes de repetir: `validation_keyword`
comparada sem colapsar quebra de linha; "Lei 18.104/2013" sem UF resolvida como federal (agora a
esfera pedida decide; União e UF existindo, o vazio pede a esfera).

Os papéis concedidos ao consultor e as 16 validações são **de prova em dev**, com nota dizendo
isso — não são validação da Ísis.

## 5. Sondas — portão NÃO passou

45 sondas (37 positivas, 8 negativas), alvos `proposto` aguardando a Ísis, uso `descoberta`
(o catálogo está quase todo `bruto`). Relatório:
[provas/inc4a_sondas_dev_2026-09-22.json](provas/inc4a_sondas_dev_2026-09-22.json).

| Métrica | Portão | Medido |
|---|---|---|
| recall@5 | ≥ 0,9 | **0,784** (29/37); depois da segunda rodada (§8): **0,892** (33/37) |
| controle negativo | 100% | **100%** (8/8) |
| groundedness (vaga resolve por ID) | 100% | **100%** (0 falhas) |
| citação órfã | 0 | 0 |

Por grupo: norma federal 10/11 · estadual pós-desmembramento 9/12 · interpretação anexada 3/4 ·
exigência/procedimento 3/6 · vigência 4/4.

Variantes medidas (mesmas sondas): lexical com todas as palavras 0,622; só vetor 0,811; tokens
raros peso 1 0,757; **tokens raros peso 0,5 0,784 (adotado)**. O híbrido fica porque o ADR o
exige para número e sigla; nenhuma variante passa 0,9, e as sondas não foram usadas para
calibrar além disso.

As 8 falhas: **3 são alvo estreito** (a vaga trouxe a fonte certa por outro dispositivo ou por
ficha equivalente: CAR-MS, ficha LAC de suínos, queima controlada) — a Ísis decide o alvo; **5
são ranking** (CONAMA 369 art. 3º perde para a Resolução CMN 5.193, documento de 565 mil
caracteres; LC MT 592 art. 10 perde para a EC MT 115, que absorveu o texto dela no desmembramento;
Lei AC 4.397 art. 100; art. 22 × art. 21 do 6.514; piscicultura REG).

**A OJN 06/2009 não cita o art. 18 do Decreto 6.514** (o exemplo do §7.2 supunha isso): ela
interpreta prescrição e processo — arts. 21, 22, 100, 101, 121 e 126 do 6.514, IN IBAMA 10/2012 e
Lei 9.784. A sonda de anexo mira o art. 21, e passa.

## 6. Fora deste recorte (declarado)

- As quatro naturezas com tabela própria (§6: `exigencia_tr`, `precedente`, `procedimento`,
  `interpretacao_ressalva`). Os insumos estão na pasta `RegenteLandpage` (PROCESSO SEI,
  indeferimentos, roteiros SIGCAR, `MANUAIS_SEMAD.rar`) — ingerir fonte nova é o passo seguinte;
  indeferimento é de cliente e nasce privado do tenant (A3).
- Tela "Acervo normativo" (fila da Ísis): a API está pronta; a tela não.
- Religar a Legislação e trocar o `citation_evaluator`/`persist_object` (#243) pelo detector novo:
  só com sondas verdes (decisão 6).
- Produção: a migration `073zn001` só cria tabelas; roda no deploy quando o André mergear. O
  catálogo de produção nasce vazio — a reconstrução a partir do dev é o Incremento 6 (#185).

## 7. Dívidas abertas

| # | Dívida |
|---|---|
| #260 | Sondas vermelhas: recall@5 **0,892** < 0,9 depois da segunda rodada (§8). Sobram 3 alvos a decidir com a Ísis (Q-ISIS-21) e 1 falha de ranking. Legislação segue desligada |
| #261 | Revisão humana das fronteiras: 101 segmentos não determinados (15% do texto das coletâneas) e 25 fronteiras ambíguas em `tarefa_revisao_normativa`; Q-ISIS-19 encurta |
| #262 | A5 sem original: coletâneas de MS e MT (19), normas federais baixadas do Planalto e 251 das 282 fontes SEMAD (o `MANUAIS_SEMAD.rar` cobriu 31). Sem original a versão não pode ser validada |
| #263 | Vigência não determinada em quase todo o catálogo: peça fica vazia até a curadoria declarar vigência ao propor |
| #264 | As quatro naturezas do §6 com tabela própria, a partir dos insumos da `RegenteLandpage` |
| #265 | Extrator de artigos: citação sem aspas de número maior abre artigo; revisar normas de alteração antes de validar |
| #266 | Dispositivo curto perde nos dois ramos: o art. 22 do Decreto 6.514/2008 (436 caracteres) fica em 78º por vetor e 66º por lexical |
| #267 | Deduplicar por hash de texto: 20 textos idênticos sob identidades diferentes (3 arquivos repetidos da SEMAD, 17 segmentos `nao_determinado` do DOE-MT em duas coletâneas) |

Numeradas a partir do maior número visto em todas as branches (#259) em 22/09; a frente 4b
corre em paralelo — se houver colisão, renumerar no merge.

## 8. Segunda rodada (22/09, depois do merge do #201)

Frente aberta pelo André: os cinco erros de ranking, os três de alvo e a conciliação dos
números. Nada aqui muda o ADR; muda o que o dado mostrou.

### 8.1 Dois eram defeito do corte, não do ranking

| Achado | O que era | O que passou a valer |
|---|---|---|
| **Segmento absorvedor** | o cabeçalho "RESOLUÇÃO CMN Nº 5.193" abriu um segmento de **565 mil caracteres** dentro do MT-NUC07 (a resolução real tem 11,8 mil) e disputava vagas de perguntas alheias | corte por cabeçalho não tem fim confirmado; acima de **10.000 caracteres por artigo** o segmento perde a identidade e vai para revisão. Tamanho sozinho não serve (a Constituição de MT tem 356 mil e é legítima): o critério é a **densidade de articulação** — medida nos segmentos de norma: mediana 898, p95 6.498. **9 segmentos** marcados |
| **Mais de um ato na mesma impressão** | a EC MT 115/2023 vinha com o texto da LC MT 592/2017 dentro; o parser marcava e seguia | a impressão passa a ser **cortada** em cada cabeçalho interno de ato diferente com contexto de abertura |

### 8.2 Dois eram o filtro de objetivo cortando a fonte certa

A Resolução CONAMA 369/2006 (intervenção em APP) ficou fora de uma pergunta de **supressão**
porque o legado só a marcou como licenciamento/compensação; a Lei AC 4.397/2024 (dispensa de
licenciamento) herdou `outorga` do núcleo hídrico da coletânea. **Filtrar por palpite tira fonte
certa.** Agora o objetivo só filtra quando a classificação **não** é provisória; enquanto for, a
fonte entra marcada `objetivo_provisorio`. O filtro segue no contrato, valendo assim que a
curadoria declarar o objetivo.

### 8.3 O ramo lexical: o critério é raridade, não formato

Restringir o lexical a número e sigla (rodada anterior) deixava de fora justamente a palavra que
separa uma ficha de tipologia da outra ("suinocultura") e deixava entrar sigla comum (CAR, APP,
LAC). Agora entra no ramo lexical **o termo raro** — presente em menos de 1% dos trechos, um IDF
declarado. A normalização do `ts_rank` por tamanho (flags 1, 32, 33) foi medida e **não mudou nada**.

| Variante (mesmas 45 sondas, dev) | recall@5 |
|---|---|
| lexical com todas as palavras, peso 1 | 0,622 |
| só vetor | 0,811 |
| lexical = número/sigla raros, peso 1 | 0,757 |
| lexical = número/sigla raros, peso 0,5 | 0,784 |
| + objetivo provisório deixa de filtrar | 0,838 |
| **+ lexical = termo raro, peso 0,5** | **0,892** |

### 8.4 Onde parou

**recall@5 0,892 (33/37)** — o portão de 0,9 exige 34. Controle negativo 100%, groundedness 100%,
zero citação órfã. Por grupo: federal 11/11 · estadual 11/12 · interpretação anexada 3/4 ·
exigência/procedimento 4/6 · vigência 4/4. **A Legislação continua desligada.**

As quatro que faltam: **três são escolha de alvo** e vão para a Ísis como **Q-ISIS-21** (§8.5);
**uma é falha real de ranking** — o art. 22 do Decreto 6.514/2008 ("Interrompe-se a prescrição",
436 caracteres) fica em 78º por vetor e 66º por lexical: dispositivo curto perde para trecho longo
nos dois ramos, e 65 trechos de INs do IBAMA e do ICMBio repetem a matéria com correspondência
mais densa. Registrada como dívida #266, sem remendo.

### 8.5 Q-ISIS-21 — três alvos de sonda para a Ísis decidir

Em cada caso a recuperação trouxe a fonte certa (ou uma equivalente); o que está em jogo é qual
dispositivo ou fonte conta como resposta:

| Sonda | O que o sistema devolveu | Pergunta para a Ísis |
|---|---|---|
| `ms-13977-car-ms` ("CAR-MS e o PRA do estado") | arts. 3, 4, 5 e 53 do Decreto MS 13.977/2014 e a Resolução SEMADE 28/2016 | o alvo é o art. 1º, ou qualquer dispositivo do ato que institui o CAR-MS serve? |
| `exi-ficha-piscicultura-reg` ("piscicultura em tanque escavado, registro eletrônico") | Decreto GO 7.862/2013 (arts. 11, 18, 26, 47, 57), em vez da ficha de tipologia A4.1 | para o consultor, a resposta é a ficha do IPÊ ou o decreto que a fundamenta? |
| `proc-queima-controlada` ("como solicitar autorização de queima controlada no IPÊ") | IN SEMAD 3/2020 (arts. 3, 4, 6) e a ficha Y1.4 de queima controlada, não o Manual | manual, ficha ou IN: qual é o alvo de um procedimento? |

### 8.6 Conciliação: 878 fontes × 258–449 estimadas no ADR-075

O ADR estimou **258 a 449 documentos de legislação** (81 avulsos + 177 a 368 atos) e **540 a 731
fontes** (com as 282 da SEMAD). Medido, o catálogo tem **878 fontes**:

| Parcela | Fontes |
|---|---:|
| Atos vindos das coletâneas | 531 |
| Fontes SEMAD-GO (só existiam como chunk) | 275 |
| Normas avulsas do legado | 81 |
| (−) atos presentes nos dois lugares, que são UMA fonte com duas proveniências | −9 |
| **Total** | **878** |

Contra a estimativa: **493 documentos de legislação com identidade** (81 avulsos + 421 atos − 9
sobrepostos) contra 258–449 — **44 acima do topo**; e 768 fontes com identidade contra 540–731,
mais **110 fontes `nao_determinado`**, que o ADR não previa como linha (ele supunha o não
identificado fora do catálogo; aqui ele entra como fila de revisão, sem nível e sem trecho, logo
sem participar de busca).

**A diferença é granularidade, não duplicata:**

1. **71 emendas constitucionais** entraram como atos próprios — a medição do ADR excluiu
   explicitamente as 217 linhas de `EMENDA CONSTITUCIONAL` da contagem larga.
2. **Atos administrativos do Diário Oficial de MT de 26/09/2018**, que está inteiro dentro de
   MT-NUC02 e MT-NUC05 (portarias de SEDUC, SEJUDH, SINFRA, DETRAN): são atos reais e o corte os
   trata como tal, embora não sejam matéria ambiental. Boa parte das 68 portarias estaduais.
3. **Atos federais impressos dentro de coletâneas estaduais** (Lei 6.938/1981 e LC 140/2011 dentro
   do MS-NUC04), que a conta de "atos estaduais" do ADR não previa.

**Duplicata real existe e é pequena: 20 textos idênticos sob identidades diferentes** — 3 são
arquivos repetidos do lote SEMAD (o catálogo da Ísis avisa dos `(1)`/`(3)`) e 17 são segmentos
`nao_determinado` da edição do Diário Oficial de MT presente em duas coletâneas, cuja chave é por
documento e posição. Nenhum participa de busca. Deduplicar por hash é a dívida #267.

### 8.7 Dois furos fechados no caminho

- **`TRUNCATE` burlava o append-only.** Os gatilhos de imutabilidade são `FOR EACH ROW`; um
  `TRUNCATE` apagaria a trilha inteira sem disparar nada. A migration `074zn001` põe o gatilho de
  statement nas **20 tabelas** que se declaram imutáveis (validação do catálogo, evidência,
  geometria, entrada semântica).
- **FK sem índice.** `trecho_normativo.dispositivo_id` e `dispositivo.parent_id` derrubaram a
  reconstrução do catálogo por `statement_timeout`. Varri a classe inteira: **12 índices** de FK
  criados nas tabelas da zona normativa.
