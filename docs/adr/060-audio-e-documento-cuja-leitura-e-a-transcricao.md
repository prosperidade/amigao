# ADR-060 — Áudio é um documento cuja leitura é a transcrição

- **Status:** aceita
- **Data:** 2026-08-03
- **Contexto:** dívida #103 · validação da Isis de 02/08 (item 4)
- **Substitui:** nada. **Fecha:** o `audio_url` que era gravado e nunca lido.

> **Nota de numeração.** Esta ADR abre a faixa **060+**, e as dívidas desta
> frente abrem a faixa **200-299**. Regra nova, adotada depois de duas colisões
> em dois dias: dois agentes escrevendo no mesmo `REGISTRO_DIVIDAS.md` leem o
> "próximo número livre" ao mesmo tempo, e "próximo livre" resolve conflito
> sequencial, não simultâneo. Faixa por frente resolve.

---

## O problema

A consultora sobe o áudio da reunião com o cliente **achando que o sistema
ouve**. Ele não ouvia.

Medição desta rodada, em três achados que se somam:

1. `IntakeDraft.audio_url` era gravado e **não era lido por serviço algum**. A
   menção a Whisper em `app/schemas/intake.py:101` era **comentário**, não código.
2. Na porta do caso (`POST /documents/confirm-upload`), o seletor "🎙️ Áudio de
   reunião/ligação" existia na tela desde a rodada anterior — mas a allowlist do
   backend (`ALLOWED_EXTENSIONS`) nunca ganhou as extensões de áudio. O upload
   morria com **400 "Extensão '.m4a' não permitida"** antes de qualquer discussão
   sobre transcrição.
3. A tela dizia "🎙️ Áudio anexado — transcrição não disponível". Honesto enquanto
   não havia pipeline; a partir de agora, mentira.

O que se perdia com isso é a **fonte primária do caso**: o que o cliente contou,
o que prometeu enviar, o que ficou combinado. Nada disso está em documento
nenhum — só na conversa. E era exatamente o material que sumia.

## A decisão

**O áudio não ganha um pipeline paralelo. Ele entra no pipeline que já existe,
com outra forma de leitura.**

Concretamente: um áudio é um `Document` como qualquer outro, e a transcrição
pousa em `Document.extracted_text` — a mesma coluna onde o OCR de um PDF pousa.

Consequências diretas, todas **de graça**:

| O que o documento já tinha | O que o áudio ganha sem código novo |
|---|---|
| `_documentos_com_trecho` (diagnóstico) | a reunião entra na análise, incremental |
| `id` no contexto → "doc. N" | a citação da reunião vira **fonte clicável** (ADR-035) |
| `ocr_status` / `ocr_error` | estado e motivo da falha na tela, sem inventar campo |
| evento `document.ocr.*` | a tela já escutava; não precisa saber a diferença |
| cache SHA-256 (self e twin) | o mesmo áudio no rascunho e no caso não paga 2× |
| budget guard mensal por tenant | reunião longa não fura o teto do escritório |
| `AIJob` | custo e duração auditáveis por reunião |

O nome dos campos ficou `ocr_*` de propósito, apesar de transcrição não ser OCR.
Renomear para `leitura_*` seria mais bonito e custaria uma migração em uma coluna
lida por dezenas de lugares, para ganhar zero — o significado real da coluna
sempre foi *"em que pé está a leitura deste arquivo"*. O que foi renomeado são os
**helpers compartilhados** (`emit_leitura_event`, `mark_leitura_failed`), onde o
nome custa nada e vale como documentação.

### O que a transcrição NÃO faz: acionar o extrator

O pipeline de OCR termina despachando o agente `extrator`, que garimpa campos
cadastrais (matrícula, área, CCIR) para o staging. **A transcrição não faz isso.**

Fala espontânea não é documento cadastral. Deixar o extrator trabalhar sobre uma
conversa encheria o staging de campo inventado a partir de *"acho que é uns
quatrocentos hectares"* — e o staging é justamente onde o consultor confia que
cada linha veio de um papel. A transcrição chega ao diagnóstico pelo canal de
**texto**, que é onde ela vale como fonte, e não pelo canal de **fato cadastral**.

### Marcação de origem no próprio texto

A transcrição é gravada com um cabeçalho:

```
[TRANSCRIÇÃO DE ÁUDIO — REUNIÃO · arquivo: reuniao-2026-08-03.m4a]

Consultor: e o CAR do lote 1-C, foi retificado? …
```

O cabeçalho viaja **no texto**, não ao lado dele, porque o texto é o que atravessa
as superfícies: prompt do diagnóstico, busca, cópia manual do consultor. Quem lê
tem que saber que aquilo foi **dito**, não escrito num documento oficial — peso
probatório diferente. E `confidence_score = 0.70` (o patamar do OCR por visão, não
o 0.95 do pypdf determinístico) sinaliza "confira antes de tratar como fato":
transcrição erra nome próprio, número e sigla com frequência.

## Provedor e custo

Whisper (`whisper-1`) via **LiteLLM**, atrás de `ai_gateway.transcribe()` — mesma
camada dos demais modelos, nenhuma chave nova em código, BYOK do consultor
respeitado. O modelo vem de `AUDIO_TRANSCRIPTION_MODEL` **por env**: o hardcode de
`gemini-2.0-flash` já derrubou o worker em produção duas vezes quando o Google
descontinuou o modelo, e o próximo deprecation aqui tem que ser troca de variável.

**Não há cadeia de fallback entre providers**, diferente de `complete()`: dos
quatro providers suportados, só a OpenAI expõe endpoint de transcrição. Sem chave
OpenAI a função levanta erro **explícito e acionável**, em vez de tentar um Gemini
que recusaria o formato da requisição. Isso deixa o consultor BYOK-só-Gemini sem
transcrição — registrado como dívida #202, não escondido.

Custo é calculado por **duração**, porque o LiteLLM não precifica transcrição:
`AUDIO_TRANSCRIPTION_USD_PER_MINUTE` × minutos. A duração real vem do
`verbose_json` do provedor; quando não vem, é estimada pelo tamanho do arquivo e
o campo `duracao_fonte` registra a diferença — **custo estimado apresentado como
medido é auditoria mentindo** (Princípio 2).

### Medição real (03/08, ponta a ponta pelo caminho de produção)

Áudio de 35,4 s de diálogo de reunião em pt-BR, passado por
`transcrever_audio()`:

| medida | valor |
|---|---|
| `duracao_fonte` | **`provedor`** — o `verbose_json` devolve `duration`, então o custo é MEDIDO, não estimado |
| custo | $0,003542 ⇒ **$0,006 por minuto**, exatamente a tabela |
| reunião de 30 min | **$0,18** |
| wall clock | 3,1 s para 35 s de áudio ⇒ ~0,09 s por segundo ⇒ **~2,7 min** para uma reunião de 30 min (dentro do timeout de 300 s, com folga) |

**O erro que a medição pegou:** na primeira rodada, *"auto de infração"* saiu
**"alto de infração"** — justo o termo que dispara prazo de defesa, esfera e rota.
A correção foi passar o vocabulário do domínio no parâmetro `prompt` do Whisper
(`VOCABULARIO_DOMINIO`: auto de infração, CAR, SICAR, RAT, averbação, reserva
legal, NIRF, CCIR, SIGEF, módulo fiscal, PRAD, SEMAD…). Na segunda rodada o termo
saiu certo, **ao mesmo custo** — a cobrança é por duração do áudio, não por
tokens, então o vocabulário é de graça.

Isso reforça o `confidence_score = 0.70`: mesmo com o vocabulário, transcrição de
fala não é documento assinado.

## Visibilidade: `Document.is_internal`

Decisão 3b, pendente de resposta da Isis, implementada no **default conservador**:
o áudio entra como **documento normal do caso**, com a origem marcada. A coluna
`is_internal` (default `false`) dá ao consultor o interruptor de "material
interno": marcado, o documento some da listagem do **portal do cliente**;
continua valendo integralmente para o consultor e para o **diagnóstico** — é
material de trabalho dele, não material que o sistema esconde de quem trabalha.

Marcar/desmarcar grava `AuditLog` (`visibility_changed`): o cliente deixar de ver
uma peça do próprio caso não pode ser evento sem rastro.

Se a resposta dela for diferente ("material interno por default"), o ajuste é o
default da coluna — não a modelagem.

## O gancho do resumo (decisão 3a, pendente)

Esta rodada entrega a **transcrição bruta**. O resumo estruturado (o que o cliente
pediu · o que prometeu enviar · prazos · decisões) está implementado e **desligado**
em `AUDIO_TRANSCRICAO_RESUMO_ENABLED=false`. Ligado, roda uma chamada extra sobre a
transcrição pronta e prefixa o bloco ao texto. Falha nele nunca derruba a
transcrição — o resumo é acréscimo (radar não cancela voo).

A resposta da Isis vira **troca de variável**, não sprint nova.

## Alternativas descartadas

**Entidade `AudioTranscript` própria.** Modelo mais "limpo" no papel e pior em
tudo que importa: exigiria reimplementar a entrada no diagnóstico, a fonte
clicável, a busca, o cache e o estado na tela — cinco integrações para ganhar uma
tabela. O teste `test_transcricao_entra_no_diagnostico.py` existe para quebrar se
alguém tentar.

**Transcrever no upload, síncrono.** Uma reunião de 30 min leva de 40 a 90
segundos. Segurar o request tanto tempo transformaria o upload num sorteio.

**Segmentar áudio grande com ffmpeg.** O limite do provedor é 25 MB, e uma reunião
de 30 min em WAV passa disso. Adicionar `ffmpeg` à imagem é mudança de infra
(Dockerfile + build do Render) e ficou fora desta frente: acima do teto, a task
falha com motivo **acionável** ("divida a gravação ou reenvie em mono, 64 kbps").
Registrado como dívida **#201**.

## Como saber que quebrou

- `tests/workers/test_audio_tasks.py` — o ciclo inteiro, incluindo falha visível
  e ausência de dispatch do extrator.
- `tests/agents/test_transcricao_entra_no_diagnostico.py` — a herança que
  justifica a modelagem.
- `tests/services/test_transcricao_audio.py` — falha nunca é silêncio.
- `tests/services/test_audio_files.py` — o roteamento não confunde PDF com áudio.
