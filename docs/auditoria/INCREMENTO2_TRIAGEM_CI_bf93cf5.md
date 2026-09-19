# Triagem do CI bf93cf5 — Incremento 2

Execução de origem: https://github.com/prosperidade/amigao/actions/runs/35452478844

Resultado original: 2.056 testes passaram, 20 falharam, 1 erro no teardown. Nenhuma suíte executada no agente. Confirmação no CI `92b37d3`: 2.080 passaram, zero falhas e erros; seis jobs aprovados, G1–G9 conferidos no artefato. Execução: https://github.com/prosperidade/amigao/actions/runs/35456567072. Não equivale a gate semântico fechado.

| Falha (teste) | Classificação | Tratamento e prova mantida |
| --- | --- | --- |
| extrator_auditavel: ai_job_do_extrator_guarda_modelo_tokens_custo_e_bruto | Regressão + contrato removido | Corrigir callback inexistente. Contabilizar a única chamada de observação; remover expectativa de duas chamadas preview/staging. Conferir bruto, modelo, tokens, custo e persistência. |
| extrator_cache: caches_text_when_passed_in_metadata | Regressão | Restituir cache inicial; parser único lê documento persistido. Mock somente no parser, mantendo prova do cache. |
| extrator_cache: reads_extracted_text_when_metadata_omits_text | Contrato removido | Trocar mock de preview por parser único e verificar documento/texto recebido. |
| extrator_cache: raises_when_no_text_and_no_cache | Regressão | Falta de OCR continua erro acionável; não aceitar sucesso vazio. |
| extrator_cache: skipped_reason_aponta_caminhos_acionaveis | Regressão | Sem caso, orientar porta de extração e document_id antes de autorizar/consultar. |
| extrator_ficha01_staging: grava_staging_sem_mexer_extracted_fields | Contrato removido + rastreabilidade | Remover segunda verdade extracted_fields; conferir valor, observacao_ref, ai_job_id e destino da projeção. |
| extrator_ficha01_staging: planta_nao_grava_staging_cadastral_e_deixa_nota_visivel | Regressão + contrato removido | Restaurar precedência documental de planta; preservar observação sem destino cadastral e revisão visível. |
| extrator_ficha01_staging: auto_infracao_nao_gera_staging_cadastral_e_grava_fato_no_job | Regressão + contrato removido | Restaurar espécie peça de órgão. Fato durável substitui resultado isolado do job; nenhum destino cadastral. |
| orchestrator_chain: keeps_independent_reading_and_stops_dependent_synthesis | Expectativa removida | Extrator agora possui método; texto controlado sem espécie falha com motivo de classificação, sem LLM. Auditor independente continua; síntese dependente continua bloqueada. |
| evidence_browser: incremento1_gate_nove_provas_no_mesmo_percurso | Regressão | Hash de conteúdo aplicado usava arquivo inteiro com frontmatter. Hash agora identifica conteúdo aplicado; source_hash preserva arquivo integral. Teste G1–G9 intacto, inclusive recarga/nova sessão. |
| observacao_registral: a_alienacao_fiduciaria_sem_baixa_fica_vigente | Expectativa removida | Sem referência: indeterminado. Acrescentar prova positiva com referência explícita: vigente_segundo_o_material. |
| observacao_registral: rl_vigente_e_a_reserva_legal_nao_o_georreferenciamento | Expectativa removida | RL sem data não é vigente; tipo, ato e área da observação permanecem verificáveis e distintos do georreferenciamento. |
| observacao_registral: titular_atual_e_o_adquirente_do_ato_mais_recente | Expectativa removida | Último ato não prova completude; titular atual indeterminado, adquirente histórico preservado. |
| observacao_registral: sucessao_transfere_titularidade_para_o_espolio | Expectativa removida | Preservar sucessão, espólio e papéis; não inferir titularidade atual. |
| observacao_registral: gravame_com_data_sem_referencia_continua_vigente | Expectativa removida | Data do ato não substitui data de referência. |
| observacao_registral: espolio_transmite_a_herdeiro_na_cadeia | Expectativa removida | Preservar três atos e transmitente/adquirente, sem promover último herdeiro a titular atual. |
| reconciliation_decisions: sonia_e_transmitente_nao_titular | Expectativa removida | Sonia permanece transmitente; adquirente permanece evidência. Sem proposta automática de titularidade atual. |
| reconciliation_decisions: titular_e_o_ato_mais_recente_nao_o_primeiro | Expectativa removida | Preservar quatro participações de dois atos, sem escolher titular por ordem. |
| reconciliation_decisions: titularidade_nao_quebra_e_carrega_o_tipo | Expectativa removida | Preservar tipo e ELODI na evidência; não preencher proposta de titularidade atual. |
| audio_tasks: mesmo_audio_no_rascunho_e_no_caso_usa_cache_twin | Contrato removido | Cache exige versão de origem transcrição; teste cobre versão conhecida (reuso sem custo) e legado sem origem (nova transcrição). Inicializar referência opcional explicitamente. |
| ocr_tasks: force_true_reocr_bypass_cache_self (teardown) | Regressão estrutural | Ciclo clients → pessoa → evidence → documents → clients. Nomear FK clients.pessoa e emitir por ALTER no metadata; migration já tem constraint nomeada. Sem alteração de migration aplicada. |

## Autorização e dependência do modelo

André autorizou os nove textos reais via ai_gateway, sem fallback, exclusivamente em dev, modelo gpt-5.6-luna. Em seguida autorizou implementar a configuração nesta worktree e registrá-la em CLAUDE.md, substituindo a dependência de PR do Claude Code. Produção permanece somente SELECT MCP; nenhum texto real em arquivo.

## Limite desta triagem

Atualizar testes de inferências proibidas não implementa por si só uma cadeia dominial completa. As 174 regras e as provas semânticas reais permanecem no gate do Incremento 2. A prova sintética do CI não substitui a extração dos nove textos reais.
