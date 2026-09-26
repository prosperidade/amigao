# Telas do motor jurídico e do fechamento comercial — #278 e #282 (registro)

25/09/2026. A UI do painel consultor sai do congelamento **só para isto**: o que o Incremento 4b
(ADR-073) e o Incremento 5 (ADR-074) provaram por API passa a ser feito pela tela. **Só dev**;
produção intocada (nenhuma leitura nem escrita nesta frente).

## 1. O que entrou

| Peça | Onde |
|---|---|
| Evidência por ID clicável | `GET /processes/{id}/evidencias/{tipo}/{ref_id}` ([detalhe.py](../../app/services/comercial/detalhe.py)): os onze tipos do ADR-074 §2, com as **mesmas travas** de tenant e caso da verificação das afirmações — fora delas é 404. Cada detalhe traz `refs` (o que ele mesmo cita), e a tela segue a cadeia. [EvidenciaChip.tsx](../../frontend/src/components/EvidenciaChip.tsx): chip → painel lateral com texto, campos, "Abrir o documento" e "voltar" |
| Rota (#278) | [RotaTab.tsx](../../frontend/src/pages/Processes/RotaTab.tsx) + [MotorExecucaoPanel.tsx](../../frontend/src/pages/Processes/MotorExecucaoPanel.tsx): "Gerar pelo motor"; relatório da última execução (avaliadas, contagem por estado, indeterminadas com os fatos que faltaram, fundamento por ID clicável ou a razão de não ter, fatos lidos); ciência de alerta crítico com justificativa; passo do motor com o dispositivo e a avaliação clicáveis; remover passo pede motivo — obrigatório no passo do motor e em qualquer passo de Rota assinada |
| Relatório e escopo (#282) | [ComercialRotaPanel.tsx](../../frontend/src/pages/Processes/ComercialRotaPanel.tsx): seções e afirmações com a evidência clicável, limites, versões, atualidade com os motivos; aprovar/rejeitar com justificativa; gerar nova versão |
| Orçamento (#282) | Um item por passo com o passo e o fundamento clicáveis; método (select dos métodos correntes) e quantidade — cada mudança gera a versão seguinte pelo servidor; "fora" com o motivo e o passo; ressalvas com as conclusões clicáveis; desatualizado com os motivos; aprovar/rejeitar |
| Proposta | "Criar proposta deste orçamento" só com orçamento aprovado e atual; o servidor copia itens e total (ADR-074 §7). No editor, proposta nascida de orçamento não reenvia itens/total (antes o salvar dava 422) e diz de qual orçamento veio |
| Aba Comercial | aparece com a Rota assinada, antes da E6 (a cadeia nasce da Rota, não da macroetapa) |
| Rodapé com SHA | `RodapeVersao` na Rota e na aba Comercial (já existia na Conferência) |

Testes: `tests/comercial/test_evidencia_detalhe.py` (4, banco real); frontend
`TelasMotorComercial.test.tsx` (11) e `RotaTab.test.tsx` adaptado. Frontend inteiro: 32 arquivos,
194 testes. Recorte de backend comercial + motor + Rota: 99 verdes. Suíte e lint completos no CI.

## 2. Percurso em dev, no navegador

API da worktree em `127.0.0.1:8040` (banco `127.0.0.1:15432/amigao_db`, alembic `076mc001`),
painel Vite em `127.0.0.1:5182` com proxy para ela, Chromium headless (Playwright). Roteiro
versionado: [scripts/provar_telas_282_278.mjs](../../scripts/provar_telas_282_278.mjs) — cada gesto
é clique na tela e espera a resposta da API. Transcrição (IDs, estados, contagens, totais, hashes;
nenhum texto dos casos): [provas/telas_282_278_dev_2026-09-25.json](provas/telas_282_278_dev_2026-09-25.json).
Capturas de tela ficaram fora do repositório (mostram texto dos casos).

**Escritas diretas no banco de dev (declaradas):** senha aleatória no usuário 38 (consultor de gate,
tenant 33), guardada só no scratchpad da sessão. Entre as rodadas, o passo 1 do #23 foi restaurado
pela API (`POST /rotas/1/passos/1/restaurar`) para a rodada seguinte refazer a remoção pela tela.

Rodada final no commit **169bc30** (rodapé "Painel 169bc30 · API 169bc30 · desenvolvimento" em
todas as telas):

| Etapa | #23 (processo 65) | #25 (processo 66) |
|---|---|---|
| Gerar pelo motor | execução 15: 6 regras (3 disparos, 1 indeterminada — REG-FUN-012 sem `titular.falecimento_declarado`, 2 sem disparo); 0 passo novo, 2 removidos continuam fora | execução 16: 6 regras (4 disparos); 0 passo novo, 3 continuam fora; **1 alerta crítico sem ciência** |
| Ciência | — | avaliação 95, justificativa pela tela → ciência 3 |
| Fonte do passo | dispositivo 65677 (Lei 5.868/1972, art. 2º) → fonte 1875 → voltar | dispositivo 41702 (Lei 12.651/2012, art. 29) → fonte 1313 → voltar |
| Remoção | "Mapear os componentes" (passo do motor, Rota assinada): sem motivo o botão fica bloqueado; com motivo → 204 | só o travamento: sem motivo, bloqueado (o único passo cobrado não sai) |
| Relatório e escopo | orçamento v3 estava **desatualizado** com os motivos na tela; relatório v8/escopo v8 gerados; evidências abertas (avaliação, documento, dispositivo); **relatório rejeitado** com justificativa → v9 gerado → relatório e escopo **aprovados** | relatório e escopo v7 gerados e aprovados |
| Orçamento | v4, **R$ 900** (CCIR, por regra); 3 passos em "fora" com o motivo | v9 R$ 1.800 → método trocado para hora técnica (v10, R$ 2.000, `consultor`) → de volta (v11, R$ 1.800); 3 em "fora" |
| Aprovar e proposta | orçamento 12 aprovado → **proposta 9**, `orcamento_id` 12, R$ 900 | orçamento 15 aprovado → **proposta 10**, `orcamento_id` 15, R$ 1.800 |
| Recarga e nova sessão | mesmos IDs e estados (orçamento 12, relatório 29, escopo 30 — aprovados e atuais) | mesmos IDs e estados (orçamento 15, relatório 31, escopo 32) |

Nenhum erro de página nas rodadas. As rodadas anteriores (commits 56250f8 a a72ec24) deixaram
versões superadas e três propostas (7 e 8 além das finais) — preservadas, como o produto faz.

## 3. Achados

1. **Lista de passos vazia com a Rota vinda do cache** (corrigido, d7d8a48). A RotaTab começava a
   ordem vazia e só sincronizava quando os passos mudavam; com o ProcessDetail lendo a Rota antes
   (para liberar a aba Comercial), a lista nunca se preenchia. Teste com o cache pré-populado,
   vermelho sem a correção.
2. **Rota assinada escondia o remover** (corrigido, e04a854). A API aceita remover passo de Rota
   assinada — é o caminho que desatualiza o orçamento e gera o "fora" com motivo (Inc. 5) —, mas a
   tela escondia as ações. Agora só "remover" aparece, com motivo obrigatório.
3. **Reexecutar o motor sem fato novo desatualiza a cadeia comercial e pede nova ciência.** As
   execuções 8 a 15 do #23 e 5, 14 e 16 do #25 têm o **mesmo `fatos_hash`**; ainda assim, cada
   "Gerar pelo motor" deixa escopo e orçamento desatualizados ("Nova execução do motor jurídico") e
   o alerta crítico do #25 volta a pedir ciência. Pela letra do ADR-074 está certo (a base guarda a
   execução); na tela, é um clique que obriga a refazer escopo, orçamento e ciência sem nada ter
   mudado. Dívida **#289** — decisão do André.
4. **O texto do art. 29 da Lei 12.651/2012 no catálogo traz três redações do § 1º** (a original e
   as das MPs/Lei de 2012), como texto compilado. A tela mostra o que está gravado. Curadoria.
   Dívida **#290**.

## 4. O que fica em aberto

- Tela dos **métodos e preços do tenant** (`GET/POST /comercial/metodos`): segue só por API — é o
  que resta da #282. O orçamento já lê os métodos correntes no select.
- #284 (orçamentos legados de código) depende desta frente e não foi tocada.
- Merge só com a autorização do André.
