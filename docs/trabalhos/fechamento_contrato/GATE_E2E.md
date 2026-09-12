# Gate E2E autenticado — Frente J (12/09/2026)

O que nenhuma rodada anterior tinha feito: atravessar **tela → decisão →
consolidação → recarga → nova sessão** como UM percurso, em ambiente
autenticado, com a pilha real de pé. A reauditoria Codex de 11/09 recusou
liberar a Isis por causa disso.

**A régua é a spec da Isis** (`docs/auditoria/SPEC_ISIS_v0.1_Conferencia_Base_
Diagnostico.md`), não o enunciado da frente: onde a spec diz "impedir", o
resultado abaixo mostra o impedimento, não um aviso. O trecho da spec vem
colado ao lado de cada bloco.

## Ambiente medido

| item | valor |
|---|---|
| banco | `amigao_e2e_frente_j` — **descartável**, criado por `tests/e2e/frente_j/setup_db.py` (recusa nome que não comece com `amigao_e2e`; schema por `create_all`, nunca `alembic` fora do banco de dev) |
| API / worker | `uvicorn` + `celery --pool=solo`, apontados para o banco descartável e **Redis DB 5** (índice próprio: nenhum worker de dev consome as tarefas do gate) |
| storage | MinIO local, bucket `regente-docs` |
| frontend | Vite dev server (`127.0.0.1:5173`), proxy para a API do gate |
| LLM | **real** (`gpt-4o-mini` via `ai_gateway`), como em produção |
| entrada | os 6 documentos da ELODI em PDF de texto, gerados a partir do `extracted_text` **real de produção** dos docs 546–551 (md5 conferido contra o banco: 4286 / 82117 / 57090 / 34815 / 27109 / 444 chars) |
| produção | **não tocada.** Leitura do texto por MCP read-only; nenhuma escrita |

Scripts: `tests/e2e/frente_j/gate_api.py` (percursos 1 e 2),
`gate_complemento.py` (passos 5 e 11), `gate_percurso3.py` (itens 4/6/7),
`frontend/e2e/frente-j.spec.ts` (o gesto na UI). Payloads nesta pasta.

---

## PERCURSO 1 — o fluxo da consultora, ponta a ponta

| # | passo | resultado | evidência |
|---|---|---|---|
| 1 | subir os 6 documentos na pilha autenticada | 6 uploads `202`, todos `lifecycle_status="recebido"` no ato | `log.json` |
| 2 | extrair | **194 s**, OCR `pypdf` em todos; 115 linhas de staging: doc 1 (CAR) 12 · doc 2 (M3.181) 23 · doc 3 (M3.313) 42 · doc 4 (M3.673) 23 · doc 5 (M4.387) 15 · doc 6 (CNH-e) **0** | `seis_telas.json` |
| 3 | abrir a Conferência | **20 decisões + 64 sem agrupamento**; as 20 decisões cobrem **51** linhas; 51 + 64 = **115 = total de linhas**. Nenhuma linha perdida | `seis_telas.json` |
| 4 | decidir três, uma com EDIÇÃO DE TIPO | `matricula:3181:composicao` aceitar → decidida · `imovel:1:car` aceitar → decidida · `matricula:3181:gravames` **reclassificar** staging 25: `hipoteca` → `alienacao_fiduciaria`, com `tipo_sugerido="hipoteca"` preservado, depois aceitar → decidida | `decisoes_feitas.json` |
| 5 | escolher a fonte numa divergência sem fonte autoritativa | ver bloco abaixo | `complemento.json` |
| 6 | consolidar | `campos_gravados=1`, `matriculas_criadas=1`, `imovel_atualizado=true` | `consolidacao.json` |
| 7 | recarregar | idem, **diff vazio** | `seis_telas.json` |
| 8 | logout / login | idem, **diff vazio** | `seis_telas.json` |

### Passo 5 — escolher a fonte, e o que ela NÃO pode derrubar

**(a) divergência sem fonte autoritativa.** No caso real é a Reserva Legal
do imóvel: CAR declara **437,7632 ha**, a soma das matrículas dá **492,9252
ha** — **11,19%, crítico**, nenhuma evidência marcada como autoritativa. A
ação existe no cartão agrupado; escolher a fonte do CAR (staging 6) deixou a
linha `aceito` e a decisão `decidida`.

**(b) o que a validação desta frente achou.** Escolher a fonte de uma
evidência de **gravame** — linha SEM destino, porque gravame nunca tem coluna
própria (ADR-065) — faria `_reject_siblings` casar `target_field IS NULL` e
rejeitar **todas** as outras observações daquela matrícula de uma vez.
Medido na matrícula 3.313, que tem 13 irmãos:

```
escolhida: staging 46
irmãos:    47, 48, 49, 50, 51, 52, 64, 65, 66, 67, 68, 69, 70
status dos irmãos depois: todos "pendente"
IRMÃOS REJEITADOS: nenhum
rejeitados no processo inteiro: nenhum
```

### Os seis números, lado a lado, depois do logout/login

Cada um **rotulado pela pergunta que responde** (STATE-001: "não são seis
números que devam ser iguais — são famílias de cálculo que respondem
perguntas diferentes"). Os quatro instantes: após extração, após consolidar,
após F5, em sessão nova.

| pergunta | fonte canônica | após extração | após consolidar | F5 | sessão nova |
|---|---|---|---|---|---|
| quantas decisões a Conferência agrupa? | `build_decisions` | 20 | 20 | 20 | 20 |
| quantas linhas ficam visíveis sem agrupamento? | idem | 64 | 64 | 64 | 64 |
| a soma fecha com o staging? | idem | 51+64=115 = 115 | 115 = 115 | 115 = 115 | 115 = 115 |
| quanto da Conferência está resolvido? | `process_indicators.progresso_conferencia` | 0/84 decididas, 0 gravadas | 2/84, 1 gravada | 2/84, 1 gravada | 2/84, 1 gravada |
| em que estado está cada decisão? | `Decisao.estado` | 20 pendentes | 17 pend · 1 decidida · 1 **parcialmente gravada** · 1 gravada | idem | idem |
| em que estado está cada documento? | `document_lifecycle` (DOC-001) | 5 `extraido` · 1 `erro_leitura` | idem | idem | idem |

> **Fronteira declarada:** `checklist_documental` vem `null` nos quatro
> instantes — o processo do gate foi criado direto pelo seed, sem
> `ProcessChecklist` materializado. O indicador continua nomeado e a função
> canônica é a mesma (`checklist_engine.get_checklist_status`); o que falta é
> o objeto, não a conta. Não é regressão: nasce assim.

**Comparação automática, campo a campo, das 6 telas** (`/processes/{id}`,
diagnoses, issues, notas, rota, documentos, staging-decisions, staging-fields,
progresso, requisitos, confronto-identidade, matrículas vigentes, dossiê,
ações, artefatos), ignorando só carimbos de tempo e URLs presignadas:

```
recarregar_vs_consolidar : []   (nenhuma diferença)
sessao_nova_vs_consolidar: []   (nenhuma diferença)
```

> **Spec, STATE-001 — critério de aceite:** *"Após cada evento, todas as telas
> devem refletir o mesmo estado e contagem. Reteste deve incluir atualização
> de página e nova sessão."* ✅

> **Spec, CONF-001 — critério de aceite:** *"O usuário pode concluir cada
> bloco com uma decisão e visualizar claramente: proposta do sistema, fontes,
> divergências, impacto, pendências e ação disponível."* ✅ — 115 linhas
> viraram 20 decisões + 64 linhas visíveis; cada decisão traz
> `valor_proposto`, `evidencias`, `concordancia`/`nivel_divergencia` e as
> ações.

---

## PERCURSO 2 — invalidação, o que a Frente H não provou

| # | passo | resultado |
|---|---|---|
| 9 | gerar diagnóstico e proposta | diagnóstico v1 validado, proposta #1 enviada — **sem aviso** nos dois |
| 10 | subir documento novo | diagnóstico **e** proposta marcados desatualizados, com razão e data; nada regenerado, nada apagado |
| 11 | reextrair documento antigo com texto **cacheado** | ver abaixo |
| 12 | tentar aceitar a proposta desatualizada | **422**, com a razão; proposta continua `sent` |

**Passo 10 — o aviso, literal:**

```json
{"tipo": "documento_novo",
 "motivo": "documento \"CAR FAZ B1 B2 B3 E BA - ELODI 2016.pdf\" entrou no processo depois desta versão",
 "desde": "2026-09-12T03:28:25.972353Z"}
```

**Passo 11 — o falso negativo que o Codex achou (item 1).** Diagnóstico **v2**
criado e validado DEPOIS de todo documento do processo (`aviso_antes = null`,
conferido). Então o extrator foi rodado **por processo** — o gesto do painel
"Rodar no processo", que relê o `extracted_text` já gravado:

```
segundos_reextracao : 161.8
ocr_rodou_de_novo   : false        ← nenhum re-OCR, nenhum download do storage
staging_antes       : 115
staging_depois      : 146
linhas_novas        : 31           ← nascem com created_at novo e updated_at NULL
aviso_depois        : {"tipo": "decisao_alterada",
                       "motivo": "nova evidência da Conferência sobre \"observacao\" entrou depois desta versão",
                       "desde": "2026-09-12T03:31:41.396825Z"}
```

Com a régua anterior (só `updated_at`), essas 31 linhas seriam invisíveis
para a invalidação e o diagnóstico continuaria "válido".

**Passo 12 — o aceite recusado, literal:**

```json
{"status": 422,
 "detail": "Proposta desatualizada: documento \"CAR FAZ B1 B2 B3 E BA - ELODI 2016.pdf\" entrou no processo depois desta versão. Aceitar agora fecharia contrato sobre escopo vencido. Recuse esta proposta e gere a nova versão (Recusar → Nova versão), ou reveja o processo antes."}
status da proposta depois: "sent"
```

> **Spec, REV-001 — critério de aceite:** *"Ao anexar nova matrícula após
> diagnóstico validado, o caso muda para etapa 3, cria nova revisão, preserva
> a anterior e impede aceite da proposta desatualizada."*
> — **"cria nova revisão, preserva a anterior"** ✅ (v1 e v2 coexistem, a v1
> intacta). **"impede aceite da proposta desatualizada"** ✅ (422 acima).
> **"o caso muda para etapa 3"** ❌ **não implementado** — ver "O que NÃO foi
> provado", abaixo.

---

## PERCURSO 3 — os itens que faltavam

### 13. RL com baixa referenciada não é promovida (item 4)

Atos na forma que a extração produz, com os números do doc 547 (matrícula
3.181, onde a `Av.03` é a relocação de RL de `185,85.60ha` — a dívida #221):

```
Av.02  reserva_legal  150,0000     12/03/2008   → vigencia: vigente
Av.03  reserva_legal  185,85.60    18/09/2013   → vigencia: BAIXADO
AV.06  baixa  (altera Av.03)       04/02/2020

rl_vigente            : Av.02  (150,0000)   ← o ato anterior VÁLIDO, não a última do papel
quem grava averbacao_rl: Av.02              ← a baixada não leva a coluna
```

> **Spec, HIST-001 — critério de aceite:** *"Um cancelamento posterior deve
> alterar o estado, preservando o histórico."* ✅ — a Av.03 continua visível,
> com `vigencia="baixado"`; não é apagada, só deixa de ser afirmada.

### 14. Estado do documento: legível ≠ processado (item 6)

Medido pela API autenticada, no `lifecycle_status` do `DocumentResponse` — a
projeção que a tela lê:

| documento | `ocr_status` | `tem_texto` | `lifecycle_status` |
|---|---|---|---|
| `CNH-e.pdf.pdf` (444 chars de boilerplate de assinatura digital) | `done` | `false` | **`erro_leitura`** |
| `Perimetro-ELODI.kml` (subido no gate; leitura textual não se aplica) | `not_required` | `false` | **`classificado`** |

A `extraction_status` do CNH-e diz a mesma coisa, com as mesmas palavras:
*"recebido, não processado (doc_pessoal) — revisar: OCR não extraiu texto
legível deste documento…"*. Antes do item 6, `done` bastava para o documento
aparecer como **lido**, contradizendo a própria mensagem ao lado.

> **Spec, CONF-002 — regra funcional:** *"Usar estados distintos para
> documento: apresentado/recebido; processando; lido; erro de leitura; não
> apresentado; declarado inexistente; dispensado por decisão; substituído;
> desatualizado."* — 8 dos 9 no vocabulário; ver fronteira abaixo.

### 15. Titularidade por sucessão (item 7)

**Fixture declarada como tal:** nenhum dos 6 documentos da ELODI tem ato
*causa mortis* (R-11/R-13/R-20 são todos compra e venda). A entrada abaixo
usa a forma dos atos reais do doc 549, com os verbos de sucessão da spec.

```
R-11  compra_venda     NASCENTE AGRO-INDUSTRIAL → ALEXANDRE AUGUSTO CLEMENTE
R-18  sucessao         ALEXANDRE → ESPÓLIO DE ALEXANDRE AUGUSTO CLEMENTE
R-21  formal_partilha  ESPÓLIO → KARINA SANTAROSA CLEMENTE

titular_atual                    : KARINA SANTAROSA CLEMENTE (ato R-21)
o que seria SEM o item 7         : ALEXANDRE AUGUSTO CLEMENTE (ato R-11)
cadeia                           : 6 linhas (pessoa × papel × ato), todas com papel explícito
```

É o caso de 3.000 ha da Isis: sem sucessão no vocabulário, o titular
apontado seria o falecido.

---

## CAMADA UI — o gesto humano (Playwright, 5/5)

A camada acima mede payloads. Esta clica: `frontend/e2e/frente-j.spec.ts`,
Chromium, contra o Vite real e a API real. **5 de 5 passaram (4,4 min).**
Prints em `prints/`.

| teste | o que o clique provou |
|---|---|
| 1. a Conferência mostra as decisões | cada decisão tem cartão com o seu rótulo na tela; **20 decisões + 71 sem agrupamento = 91** (o processo já tinha as 31 linhas da reextração do passo 11) |
| 2. decidir e gravar | "Aceitar proposta" fecha a decisão · **"Editar tipo"** troca o tipo da evidência escolhida e o `tipo_sugerido` original fica na linha · "Gravar na base" carimba |
| 3. F5 e logout/login | os seis números **idênticos** nos três instantes (`base == recarregado == nova_sessao`, comparação de objeto) |
| 4. proposta desatualizada | banner na tela, **botão "Aceitar" desabilitado**, e a chamada forçada volta **422** com a razão; proposta segue `sent` |
| 5. upload pela tela | documento entra pelo input real; o CNH-e (444 chars de boilerplate) aparece com o selo **"Erro de leitura"** na aba Documentos |

### Os seis números medidos PELA UI, nos três instantes

| pergunta | base | após F5 | sessão nova |
|---|---|---|---|
| quantos documentos entraram (checklist) | `null` (processo sem checklist — fronteira declarada) | idem | idem |
| quanto da Conferência está resolvido | 7 decididas · 5 gravadas · 84 pendentes de 91 | idem | idem |
| quantas decisões a Conferência agrupa | 20 + 71 = 91 | idem | idem |
| quantas linhas de staging existem | 146 (`staging-fields`: 146) | idem | idem |
| estado de cada documento (DOC-001) | 5 `extraido` · 2 `classificado` · 1 `erro_leitura` | idem | idem |
| estado de cada decisão | 5 `gravada` · 1 `parcialmente_gravada` · 2 `decidida` · 12 `pendente` | idem | idem |

### O que a camada UI achou (e que a de payload não tinha achado)

**O botão "Aceitar" não fechava a decisão de titularidade.**
`decidir_decisao_agrupada` percorria as **evidências**, e nem todo membro da
decisão vira evidência: a titularidade monta a lista a partir da CADEIA
(`cadeia_titularidade`), então um ato de `compra_venda` que não nomeia
adquirente/transmitente entra no grupo e **não aparece** na lista. Medido no
caso real:

```
matricula:3181:titularidade  membros=[22, 27, 117]  evidências=[22, 117]  órfã=27
matricula:3673:titularidade  membros=[95, 97, 143, 144]  evidências=[143, 144]  órfãs=[95, 97]
```

A linha órfã nunca era aceita e a decisão ficava **presa em "pendente" para
sempre** — a consultora clicava e a tela não mudava. Corrigido (o laço
percorre os membros; a evidência só informa se é autoritativa) + teste
`TestFrenteJAceitarCobreTodosOsMembros`. Depois do conserto:
`estado: decidida | membros: [22, 27, 117]`.

Este é o achado que justifica a exigência do Codex: nenhuma suíte unitária,
nenhuma medição de payload e nenhum gate anterior tinha pego — porque
nenhum tinha **clicado no botão** com dado real onde a lista de evidências
não cobre o grupo.

## Fecho

Os três percursos completos, mais a camada de UI. Depois dos consertos que
o próprio gate revelou: **suíte do backend 1976 passed** (local, 19m30s; e o
mesmo job verde no CI do PR), **frontend 167 passed**, `npm run build` verde,
`ruff` verde, **Playwright 5/5**.

O que nenhuma rodada anterior tinha feito passou a existir: a sequência
inteira, no ambiente autenticado, com dado real — e ela achou três bugs que
seis frentes de teste unitário não tinham achado.

## O que NÃO foi provado (e por quê)

1. **REV-001, "o caso muda para etapa 3"** — retrocesso automático de etapa
   **não está implementado**, e não é omissão desta frente: a ADR-068 já o
   declarou fora do escopo ("o Astra classificou como decisão de PRODUTO
   nova, não conserto; REV-001 entrega o aviso; regredir etapa sozinho exige
   validação da Isis"). O gate prova as outras três partes do critério.
2. **CONF-002, "declarado inexistente"** — o vocabulário tem
   `nao_apresentado`, `dispensado` e `substituido`, mas não "declarado
   inexistente". E `nao_apresentado`/`dispensado` estão no enum **sem serem
   derivados**: são estados do REQUISITO (checklist, por ação registrada do
   consultor), não de uma linha de `Document`. O critério de aceite da spec
   ("CCIR e ITR não enviados devem aparecer como não apresentados até decisão
   explícita") é do checklist e fica para a frente que mexer nele.
3. **`checklist_documental` no processo do gate** — `null`, porque o processo
   nasceu do seed sem `ProcessChecklist`. Fronteira declarada acima.
4. **Achado lateral, fora do escopo:** `GET /auth/me` responde **500** quando
   o e-mail do usuário no banco não passa no validador do response model
   (medido com `@regente.local`, domínio reservado). O caminho normal de
   cadastro valida antes de gravar; só aparece com dado inserido direto no
   banco — como o seed deste gate fazia. Corrigido no seed; **não** corrigido
   no endpoint (é contrato de saída de outra frente, e mexer nele aqui seria
   escopo novo).
