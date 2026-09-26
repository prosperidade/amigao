# Motor jurídico — Incremento 4b (registro)

23/09/2026. Implementação do [ADR-073](../adr/073-motor-juridico-deterministico.md). **Só dev**;
produção intocada (lida apenas pelo `supabase-prod-ro`, metadados do #22, sem texto).

## 1. O que entrou

| Peça | Onde |
|---|---|
| Migration `075mj001` | `regra`, `regra_versao` (conteúdo imutável por gatilho; estado só sai de `rascunho`), `conjunto_regras` (um ativo por escopo), `conjunto_regras_item`, `execucao_motor`, `avaliacao_regra` e `ciencia_alerta` (append-only, sem `TRUNCATE`); papel `homologar_regra`; `rota_passo_origem` ganha `motor`; `rota_passos` ganha avaliação e fundamento por ID. FK com índice em todas |
| Linguagem | `app/services/motor_juridico/linguagem.py` — árvore JSON fechada, lógica de Kleene, recusa na publicação com motivo |
| Fatos | `fatos.py` — retrato com valor, estado, origem e revisão |
| Avaliação | `avaliador.py` — aplicabilidade antes da condição, seis estados, indeterminado vira coleta, erro vira estado |
| Fundamento | `fundamento.py` — resolução por identidade com a política `interno`; `verificar_passo` reusa `citacao.verificar` |
| Tradução do gate | `regras/gate_4b.yaml` — seis regras, identidades curadas, recorte declarado |
| Ciclo | `importador.py` (idempotente por hash) e `ciclo.py` (homologar, conjunto, publicar, ativar, rollback) |
| Rota | `rota.py` — `gerar_rota_pelo_motor` reusa versão, `_upsert_rota`, `_reconcile_passos` e guarda de esfera |
| API | `POST /processes/{id}/rota/gerar-motor`, `POST /processes/{id}/motor/avaliar`, `GET .../motor/execucoes/ultima`, `POST .../motor/alertas/{av}/ciencia`; `/motor-juridico/regras/importar-gate`, `/regras`, `/regras/versoes/{id}/homologar`, `/conjuntos`, `/conjuntos/{id}/publicar`, `/conjuntos/{id}/ativar` |
| Rota existente | `validar` de passo `motor` reverifica o fundamento; `fechar` exige ciência dos alertas críticos da execução corrente; passo `motor` só sai com `motivo` |

Testes: `tests/motor_juridico/` (60). Recortes de regressão: Rota, curadoria, recuperação e
modelos (243). Suíte e lint completos no CI.

## 2. Correções no ADR feitas ao implementar

Duas linhas do recorte do gate estavam erradas e foram corrigidas antes de valer:

- **REG-FUN-012 não é regra de espólio.** Na Fundiária v03 ela diz "pessoa na posse não corresponde
  ao beneficiário/titular → classificar possível cessão, **sucessão** ou ocupação" (Crítica, decisão
  jurídica). Não existe regra de espólio nas 325. A tradução passou a ser: falecimento declarado do
  titular (um gatilho suficiente de sucessão) → **alerta crítico + coleta da prova da sucessão**. O
  "regularizar a representação do espólio" que o ADR propunha era da engenharia, não da Ísis.
- **O CCIR não está no art. 22 da Lei 5.868/1972.** O artigo que exige o certificado para alienar é
  o art. 22 da **Lei 4.947/1966**, que não está no catálogo. Na 5.868, o art. 2º obriga a declaração
  de cadastro e o art. 3º dá ao INCRA o certificado. Ficou o art. 2º, como `proposta_engenharia`.
  Foi a checagem `dispositivo_ausente` que pegou o erro — o motor recusaria citar o artigo inexistente.

Quatro das seis traduções cobrem só um ramo do texto da matriz; o YAML declara cada `recorte`
(ADR-073 §13).

## 3. Percurso autenticado em dev

API da worktree em `127.0.0.1:8040`, banco `127.0.0.1:15432/amigao_db`. Transcrição completa em
[provas/inc4b_percurso_dev_2026-09-23.json](provas/inc4b_percurso_dev_2026-09-23.json).

**Preparação direta no banco de dev (declarada):** um consultor de gate no tenant 33, onde estão os
casos 65 (#23) e 66 (#25) do Inc2, e o caso **#22 de dev** (processo 69), montado com o que a
produção mostra do #22 pelo canal somente-leitura: `misto`, GO, código de CAR **no cadastro** do
imóvel (aqui sintético) e, nos autos, só CPF e documento pessoal sem classificação. Documentos só
com metadados — o motor lê classe, não texto.

**Prova de engenharia, não de curadoria.** O consultor de dev recebeu `curar_corpus` (federal) e
`homologar_regra` (`*`) do superusuário; propôs as três fontes e homologou as seis regras com nota
"PROVA DE ENGENHARIA — não é a homologação da Ísis (Q-ISIS-22)". A homologação real é dela.

| Etapa | Resultado |
|---|---|
| Curadoria | Lei 12.651/2012 (v1313), IN MMA 2/2014 (v1216) e Lei 5.868/1972 (v1875): `bruto → proposto`, eventos 33–35 da cadeia do catálogo (a cadeia estava vazia desde a reconstrução da 4a; o 33 é a gênese) |
| Regras | 6 importadas em `rascunho`, homologadas, conjunto 1 publicado e ativo |
| **#23** (65) | CAR + 4 matrículas. Disparou CAR-007, FUN-002, GO-CAR-001; não disparou CAR-001 e CAR-002; FUN-012 **indeterminado** (falecimento não observado). Validados: "Mapear os componentes" (IN MMA 2/2014, art. 2º) e "Emitir ou regularizar o CCIR" (Lei 5.868/1972, art. 2º). Recusados na validação (409) e removidos com motivo: SIGCAR (IN SEMAD 22/2025 ausente) e "Confirmar: situação do titular" (Código Civil ausente). **Rota validada** |
| **#25** (66) | Escritura, sem CAR, falecimento declarado. Disparou CAR-001, FUN-002, FUN-012 (alerta crítico + coleta) e GO-CAR-001. Validados: "Verificar inscrição no CAR" (Lei 12.651/2012, art. 29) e CCIR. Removidos com motivo: sucessão e SIGCAR (norma ausente). Fechar sem ciência → **409**; ciência registrada; **Rota validada** |
| **#22** (69) | Natureza do imóvel **desconhecida**. Quatro regras **indeterminadas**, duas não dispararam. Rota de coleta: "Confirmar: natureza do imóvel" validado (Lei 12.651/2012, art. 29); "Confirmar: situação do titular" removido com motivo. **Rota validada** |
| Idempotência | regenerar depois das remoções: `created 0`, os removidos voltam como `suprimidos` (2, 2 e 1), versão da Rota preservada antes |
| Remoção sem motivo | **400** em todo passo do motor |
| Isolamento | usuário de outro tenant lendo a execução do #23: **404** |
| Imutabilidade (banco de dev, em transação desfeita) | `UPDATE`/`DELETE` em `avaliacao_regra` e `ciencia_alerta` recusados; `TRUNCATE` em `avaliacao_regra` e `execucao_motor` recusado; mudar a condição de `regra_versao` recusado ("crie uma versão nova"); voltar homologada para rascunho recusado; `DELETE` de `regra_versao` recusado |

Todo passo validado das três Rotas tem `fundamento_fonte_versao_id` e `fundamento_dispositivo_id`.
Nenhum passo foi validado sem fundamento por ID; nenhum fundamento veio por semelhança.

**O que o gate não provou em dev:** `nao_aplicavel` e `erro_execucao` (os três casos são de GO e
nenhuma regra falhou). Os dois estão nos testes de contrato (`test_regra_de_go_nao_se_aplica_a_imovel_de_mt`,
`test_erro_de_execucao_e_estado_registrado_nunca_silencio`).

## 4. Achados

1. **A falta de norma é o que mais pesa na Rota.** Das 10 propostas de passo nas três Rotas, 5 não
   puderam ser validadas porque a fonte não está no catálogo: IN SEMAD 22/2025 (SIGCAR, no #23 e no
   #25) e Código Civil (sucessão ou situação do titular, nos três). É o caminho "norma ausente" funcionando como o ADR
   quer — mas o SIGCAR é passo real de todo caso de GO. Dívida **#276**.
2. **69 fontes têm duas versões correntes** (a mesma norma vinda avulsa e de coletânea, sem relação
   de substituição). A Lei 12.651/2012 é uma delas (v1313 avulsa e v1314 da coletânea MT-NUC12).
   O motor desempata de forma determinística (mais curada, depois mais nova), mas a escolha certa é
   da curadoria. Dívida **#273**.
3. **Citação a outra lei virou artigo da fonte.** Na Lei 5.868/1972, "Art. 29 da Lei número 5.172…"
   (uma remissão dentro do art. 6º) foi cortado como **art. 29 da própria Lei 5.868**. Classe medida
   no catálogo de dev: **11 dispositivos espúrios em 7 fontes**. Uma regra que citasse esse artigo
   resolveria para o texto errado — por identidade, com todas as travas verdes. Dívida **#274**. *(Fechada em
   23/09: a varredura completa achou 16 espúrios e 94 artigos reais engolidos em 12 versões — ver o
   registro de dívidas.)*
4. **A IN MMA 2/2014 do catálogo é cópia de trabalho**, não a edição do DOU: o texto começa com o
   cabeçalho de um arquivo Word do MMA (`est3049 - h:\in car sicar 24-04-2014.doc`) e não tem URL na
   proveniência. Foi proposta em dev com o domínio oficial que o próprio texto cita e nota dizendo
   isso; validar exige o original (A5). Dívida **#275**.
5. **O cadastro do imóvel não é fato do vocabulário.** O #22 de produção tem código de CAR no cadastro
   do imóvel, mas nenhum CAR nos autos; o motor lê só os autos e pede "Confirmar: natureza do imóvel".
   Se o código do cadastro conta como prova de natureza rural é pergunta para a Ísis (entra na
   Q-ISIS-22). Dívida **#277**.
6. **A tela não conhece o motor.** O painel mostra os passos (`origem: 'motor'` entrou no tipo), mas
   não tem "gerar pelo motor", relatório da execução, ciência de alerta nem motivo na remoção — a
   remoção pela tela atual recebe **400** num passo do motor. O percurso do gate foi por API. Dívida **#278**.
   *(Fechada em dev em 25/09: [TELAS_COMERCIAL_MOTOR_282_278.md](TELAS_COMERCIAL_MOTOR_282_278.md).)*
7. **O container `api` do compose não sobe com o dev em `075mj001`**: ele roda a `main`, que não
   conhece a revisão. Efeito de ambiente até o merge (ou `alembic downgrade 074zn001`), não do código.

## 5. Q-ISIS-22 — homologação do gate

Para a Ísis, com o YAML e a planilha lado a lado:

1. **As seis traduções servem?** Em especial os quatro recortes: CAR-002 ("concluir titularidade só
   pelo CAR" = "há CAR e nenhuma matrícula nos autos"), FUN-002 (só CCIR ausente), FUN-012 (só
   falecimento declarado) e GO-CAR-001 (+ imóvel rural).
2. **Os três dispositivos propostos pela engenharia:** IN MMA 2/2014, art. 2º para a CAR-007 ("Dados
   do imóvel"); Lei 5.868/1972, art. 2º para a FUN-002 ("Orientações INCRA"); Código Civil, art.
   1.784 para a FUN-012 ("Regras de titulação").
3. **O código de CAR no cadastro do imóvel prova que ele é rural?** (achado 5.)
4. **Quem homologa:** a titularidade do papel `homologar_regra` é dela hoje; um advogado ambiental
   entra por concessão, sem mudar o desenho.

## 6. Parâmetros provisórios (ADR-073 §12)

- **Q-ISIS-18:** nenhuma regra do gate cita ficha de tipologia.
- **Q-ISIS-19:** o motor só resolve fundamento em fonte com identidade determinada. Nenhuma das
  fontes do gate está em segmento `nao_determinado`.
