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
| Lexical na fusão | só tokens raros (< 1% dos trechos), peso 0,5 | `recuperacao.PESO_LEXICO`, `FRACAO_MAXIMA_TOKEN` | rodada de sondas |
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
| recall@5 | ≥ 0,9 | **0,784** (29/37) |
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
| #260 | Sondas vermelhas: recall@5 0,784 < 0,9. 3 alvos a decidir com a Ísis, 5 falhas de ranking (documento gigante dominando; EC MT 115 com texto da LC 592). Legislação segue desligada |
| #261 | Revisão humana das fronteiras: 101 segmentos não determinados (15% do texto das coletâneas) e 25 fronteiras ambíguas em `tarefa_revisao_normativa`; Q-ISIS-19 encurta |
| #262 | A5 sem original: coletâneas de MS e MT (19), normas federais baixadas do Planalto e 251 das 282 fontes SEMAD (o `MANUAIS_SEMAD.rar` cobriu 31). Sem original a versão não pode ser validada |
| #263 | Vigência não determinada em quase todo o catálogo: peça fica vazia até a curadoria declarar vigência ao propor |
| #264 | As quatro naturezas do §6 com tabela própria, a partir dos insumos da `RegenteLandpage` |
| #265 | Extrator de artigos: citação sem aspas de número maior abre artigo; revisar normas de alteração antes de validar |

Numeradas a partir do maior número visto em todas as branches (#259) em 22/09; a frente 4b
corre em paralelo — se houver colisão, renumerar no merge.
