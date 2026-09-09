<!-- Versionado em docs/auditoria/. Auditoria de generalidade, Fase 1 (só leitura).
Agente: Claude Code. SHA local auditado: 3d1a78f (main sem #148; #148 estava no remoto em 4a96b5d).
Limites declarados pelo próprio relatório: banco amigao_db não existia na máquina; matriz de perfis
não executada (conflito com "somente leitura"); spec v0.1 não estava versionada. -->

# Relatório — auditoria independente

## Resultado executivo

**Conclusão CONFIRMADA:** as correções recentes não provaram generalidade. Os testes cobrem principalmente fixtures de pessoa física, com matrículas conhecidas e casos sintéticos. Não há prova executada para PJ, representante, CNPJ, matrícula criada pela consolidação ou quatro matrículas.

O checkout auditado está em:

- `HEAD`: `3d1a78fed0878626643adfa6f14451713bcdad88`
- `origin/main`: `4a96b5d3e9e3e976f5ee4a3f8a85f8c735f0d948`
- Portanto, o #148 está no remoto, mas não no `HEAD` local.
- Worktree: somente o arquivo pré-existente não rastreado `auditoria_codex_regente.md`.
- Nenhuma suíte foi executada.
- Nenhum arquivo foi alterado.
- O banco `amigao_db` não existe no PostgreSQL local; há apenas `cannabia`, `enjoyfun`, `postgres`, `vereda_c1` e `vereda_ci`.
- A reprodução mutante contra banco não foi executada por conflito direto com "somente leitura".

A especificação v0.1 com os 15 requisitos não está versionada em `docs/auditoria/` no checkout atual. Os identificadores `SAVE-001`, `DATA-001`, `DIAG-001` etc. não aparecem no código nem na documentação rastreada.

---

## A — Caminho completo do dado

| Transição | Evidência | Perda/silêncio |
|---|---|---|
| Upload → `Document` | `app/api/v1/documents.py:201-220` | `storage_key` e `s3_key` vêm diretamente do payload. O upload é confirmado antes de provar que o objeto existe. |
| Upload → fila | `app/api/v1/documents.py:322-353` | Falha ao enfileirar OCR/extrator vira apenas `logger.warning`; o endpoint continua o fluxo de sucesso. |
| PDF → OCR | `app/workers/ocr_tasks.py:91-101`, `147-180` | Há estados `failed` para storage ausente; porém dependência do worker/fila não é refletida no sucesso original do upload. |
| OCR → texto | `app/workers/ocr_tasks.py:294-348` | Texto é salvo em `Document.extracted_text`; falha é registrada em `ocr_error`. |
| Texto → extração | `app/services/ficha01_extraction.py:624-728` | Campos vazios, identidade não comprovada e lixo de código são descartados. Alguns descartes só geram warning/info. |
| Extração → classificação | `app/agents/extrator.py:158-195`, `224-228` | O tipo efetivo pode ser recalculado pelo conteúdo. O staging é adicional e best-effort. |
| Classificação → staging | `app/services/ficha01_extraction.py:794-858` | Linhas vão para `ExtractedFieldStaging`; sem `process_id`, ficam órfãs e invisíveis à Conferência. |
| Staging → agrupamento | `app/services/staging_consolidation.py:468-525` | Agrupamento por entidade, matrícula e campo. Linhas sem valor e achados aceitos não gravam. |
| Agrupamento → consolidação | `app/services/staging_consolidation.py:559-665` | Conflitos retornam a divergência; matrícula sem destino pode virar `ignorados`. |
| Consolidação → escrita | `app/services/staging_consolidation.py:762-824` | Allowlist, coerção e formato podem recusar o valor. O motivo vai para `ignorados`. |
| Escrita → `consolidated_at` | `app/services/staging_consolidation.py:671-682` | O carimbo é por linha que efetivamente corresponde ao valor vencedor. |
| Commit → resposta | `app/services/staging_consolidation.py:719-759` | `campos_gravados` conta `writes`, não todos os campos preparados. `ignorados` e divergências seguem separados. |
| Resposta → tela | `frontend/src/pages/Processes/ConsolidacaoPanel.tsx:181-195`, `392-428` | A tela distingue "aceito", "gravado", "ignorados" e divergências; depende de nova leitura do endpoint. |
| Tela → diagnóstico | `frontend/src/pages/Processes/DiagnosisTab.tsx:206-241` | A UI aceita `afirmacoes` com fonte, mas também exibe payload legado cru sem exigir fonte. |

O sistema hoje avisa em vários pontos da consolidação, mas ainda há falhas caladas na entrada: upload confirmado sem prova do objeto e erro de despacho tratado como warning.

---

## B — SAVE-001: teste de generalidade

Não foi permitido executar a consolidação contra quatro perfis porque ela faz `db.commit()` em `app/services/staging_consolidation.py:741`. Fazer isso violaria "somente leitura".

Não há, portanto, resultados legítimos de `preparados × persistidos` para colar.

O que o código e os testes permitem confirmar:

| Perfil | Evidência disponível | Estado |
|---|---|---|
| PF com matrículas existentes | `tests/api/test_gravado_visivel.py:55-73`; `tests/api/test_fase4_consolidacao.py:45-71` | Coberto em fixture PF |
| PJ com representante | Não há fixture PJ nem modelo de representante | Não coberto |
| Sem matrícula prévia | `tests/services/test_consolidacao_integrada.py:107-124` cobre criação de matrícula sintética | Cobertura unitária, não banco dev |
| N ≥ 4 | Não encontrei teste com quatro matrículas; os testes usam uma ou duas | Não coberto |

### Caminhos de gravação

Há um caminho de produção identificado:

- endpoint: `POST /api/v1/processes/{process_id}/consolidar`, `app/api/v1/processes.py:1699-1743`;
- serviço: `consolidate_process`, chamado em `app/api/v1/processes.py:1718-1720`;
- chamadas diretas adicionais apenas nos testes: `tests/services/test_consolidacao_integrada.py`.

Não encontrei outro worker, retry ou endpoint de produção chamando `consolidate_process`.

`consolidated_at` cobre as linhas processadas pelo serviço, mas não existe prova de que cubra qualquer caminho paralelo porque não foi identificado outro caminho de produção.

---

## C — Pessoa jurídica

O modelo distingue PF/PJ:

- `app/models/client.py:11-14`: `ClientType.pf` e `ClientType.pj`;
- `app/models/client.py:30-42`: `client_type`, `legal_name` e `cpf_cnpj`.

Mas:

- `cpf_cnpj` é apenas `String`, `app/models/client.py:33`;
- não há `UniqueConstraint` para CPF/CNPJ por tenant;
- os schemas não validam formato nem unicidade, `app/schemas/client.py:7-25`;
- o endpoint cria diretamente o registro, `app/api/v1/clients.py:50-62`;
- não existe entidade/campo explícito para representante;
- a extração de documento pessoal envia CPF para `cliente`, `app/services/ficha01_extraction.py:269-273`.

**Conclusão CONFIRMADA:** a CNH/CPF de um representante tende a ser modelada como dado do próprio `Client`; não há separação estrutural entre titular/contratante e representante.

O fluxo de intake ainda nasce com pressupostos cadastrais genéricos:

- `app/api/v1/intake.py:131-143` cria o cliente com `full_name`, `cpf_cnpj` e `client_type`;
- não há representante no objeto de criação;
- o fluxo de consolidação só conhece `cliente`, `imovel` e `matricula`, `app/services/staging_consolidation.py:568-604`.

O CNPJ `29.091.958/0001-17` não foi encontrado em arquivos e não pôde ser consultado: o banco dev esperado não existe localmente. Estado real: **não verificável**.

---

## D — DIAG-001

A string "Demanda Mista / Múltiplos Passivos" existe em:

- `app/services/intake_classifier.py:370-377`.

Ela é um rótulo de `demand_type`, não uma prova de passivos documentais.

O tipo `misto`:

- tem `keywords: []`, `app/services/intake_classifier.py:371-373`;
- pode ser atribuído manualmente;
- possui diagnóstico textual pré-definido em `app/services/intake_classifier.py:374-383`;
- possui checklist pré-definido, `:385-390`.

O diagnóstico técnico, por outro lado, usa passivos derivados ou LLM:

- fallback determinístico em `app/agents/diagnostico.py:915-961`;
- passivos do fallback vêm apenas de flags do imóvel, `:926-935`;
- sem documentos e contexto legal, o sistema cria fonte manual `no_evidence_available`, `app/agents/diagnostico.py:967-1015`;
- a UI ainda exibe payload legado sem fonte, `frontend/src/pages/Processes/DiagnosisTab.tsx:210-241`.

**Achado grave CONFIRMADO:** "Múltiplos Passivos" pode aparecer como classificação de intake sem agente de diagnóstico ter rodado e sem documento de passivo. Isso contradiz a exigência de não afirmar fato sem evidência.

---

## E — STATE-001

Há múltiplas fontes independentes:

1. Checklist: `app/services/checklist_engine.py` e `frontend/src/pages/Processes/ProcessChecklist.tsx`.
2. Barra/etapa macro: `frontend/src/pages/Processes/MacroetapaSidePanel.tsx`.
3. Staging preparado: `frontend/src/pages/Processes/ConsolidacaoPanel.tsx:198-208`.
4. Campos persistidos: `consolidated_at`, `app/api/v1/processes.py:1466-1471`.
5. Resultado da consolidação: `campos_gravados`, `app/services/staging_consolidation.py:743-758`.
6. Dossiê: `checklist_summary`, `frontend/src/pages/Processes/ProcessDossier.tsx:443-459`.

A própria triagem confirma que checklist pode ser marcado como recebido sem documento vinculado e ainda entrar no percentual, `docs/auditoria/TRIAGEM_AUDITORIA_CODEX.md:341-350`.

**Conclusão:** pelo menos seis fontes/indicadores independentes podem divergir.

---

## F — Cruzamento com triagem, dívidas e ADRs

A triagem disponível só cobre achados do documento anterior, não os 15 requisitos solicitados. Ela classifica:

- Lista A — dois achados resolvidos, `docs/auditoria/TRIAGEM_AUDITORIA_CODEX.md:57-82`;
- Lista B — sete achados decididos, `:130-186`;
- Lista C — achados registrados em dívidas, por exemplo `:300-350`;
- Lista D — 21 achados novos, `:400-427`.

Conflitos solicitados:

- **REC-001 / DATA-002 / CONF-001 / REV-001 × ADR-062:** a ADR-062 não existe no `HEAD` atual. Está somente no commit #148 remoto. Não é correto reconciliar esses requisitos com ela como se estivesse no checkout auditado.
- **REC-001 / DATA-002 / CONF-001 / REV-001 × ADR-039:** ADR-039 afirma que a rota nasce de diagnóstico fundamentado e ações validadas, `docs/adr/039-rota-nasce-do-diagnostico-fundamentado.md:1-18`, mas o cruzamento requisito-a-requisito não é possível porque a especificação v0.1 não está presente.

Portanto, o estado correto é **não verificável**, não "resolvido".

---

## G — O que os testes realmente provam

| Correção | Teste | Classificação |
|---|---|---|
| #141 | `tests/api/test_gravado_visivel.py`; `frontend/src/pages/Processes/ConsolidacaoPanel.test.tsx` | Teste de caso/fixture. PF, dados sintéticos, uma/duas matrículas. Prova visibilidade do carimbo, não generalidade. |
| #143 | `tests/api/test_vtn_nao_vira_acao.py`, `tests/services/test_trabalho_impossivel.py` | Teste de regra específica de campo sem destino. Não cobre PF/PJ nem pipeline completo. |
| #144 | `tests/services/test_chunking_guarda_sanidade.py` | Teste de sistema local do chunking, mas não relacionado ao SAVE-001. |
| #147 | `tests/api/test_tenant_smoke_escrita.py`, `tests/e2e/test_document_flow.py` | Isolamento/fluxo de documento; não prova consolidação por perfil. |
| #148 | `tests/api/test_fase4_consolidacao.py`, `tests/services/test_consolidacao_integrada.py` | Commit remoto, não presente no HEAD. Fixtures continuam centradas em PF e uma/duas matrículas. |

O caso mais explícito:

- `tests/api/test_gravado_visivel.py:55` cria `ClientType.pf`;
- `:68-74` usa matrícula conhecida;
- `:103-108` verifica que campos aparecem como gravados;
- `:184-216` cobre duas matrículas, não quatro;
- não há fixture PJ/representante/CNPJ.

**Conclusão:** #141 foi correção de observabilidade para o caso/forma de fixture coberta; não há evidência de correção sistêmica para qualquer perfil.

---

## H — Por que o sistema não funciona para qualquer caso?

A resposta é combinada:

1. **Correções ajustadas ao caso relatado.** Os testes usam PF, fixtures pequenas e matrículas conhecidas. Não cobrem PJ, representante, criação de matrícula nem N≥4.

2. **Suposição de pessoa física embutida.** O modelo tem `client_type`, mas não tem representante, relação titular/representante ou semântica própria para documentos de representante.

3. **Múltiplos estados independentes.** Checklist, macroetapa, staging, `consolidated_at`, resposta da consolidação e dossiê calculam/mostram números diferentes.

4. **Execução confundida com resultado.** O upload registra o documento antes de provar o objeto e continua mesmo se a fila falhar, `app/api/v1/documents.py:258-273`, `322-353`.

5. **Falhas ainda podem ser silenciosas.** A consolidação melhorou seus avisos, mas o pipeline anterior ainda degrada para warning, fallback ou `no_evidence_available`.

6. **O diagnóstico pode afirmar classificação sem evidência.** "Demanda Mista / Múltiplos Passivos" é um tipo de demanda configurado no intake, não prova de passivo documental.

### Resposta direta à pergunta central

Com a evidência atual, **não é possível classificar nenhuma das correções #141, #143, #144, #147 e #148 como correção sistêmica do problema "qualquer caso"**.

A classificação mais precisa é:

- #141: correção de visibilidade comprovada em fixture PF;
- #143: correção de regra específica;
- #144: correção de chunking, fora do SAVE-001;
- #147: correção de escopo tenant, sem prova de consolidação;
- #148: correção de fonte registral, ainda não presente no `HEAD` auditado.

Logo, o lote contém predominantemente **ajustes ao caso ou ao sintoma**, não demonstrações de correção geral.

---

## Plano de frentes por dependência e risco

1. **Entrada e evidência documental — maior risco:** upload, storage, OCR, classificação e fonte documental.
2. **Modelo PF/PJ e identidade — dependência estrutural:** CNPJ, unicidade, representante e documento pertencente à pessoa correta.
3. **Consolidação geral — depende das duas anteriores:** matriz de perfis, sem matrícula, múltiplas matrículas e campos preparados/persistidos.
4. **Estado único de produto — depende da consolidação:** checklist, progresso, carimbo, dossiê e diagnóstico.
5. **Diagnóstico fundamentado — depende de fontes válidas:** impedir rótulo/classificação sem agente, documento ou fonte explícita.
6. **Testes de sistema — último bloqueio de confiança:** matriz de perfis contra banco real, sem suíte completa, com resultado persistido verificável.

Nenhuma correção ou dívida foi aberta.
