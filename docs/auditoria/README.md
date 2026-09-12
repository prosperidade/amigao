# docs/auditoria — índice

Auditorias do Regente Ambiental, em ordem cronológica. Cada item registra **o que auditou**, **o SHA sobre o qual leu** e a **conclusão em uma frase**.

Regra da pasta: auditoria é fotografia de um SHA. Não se edita um relatório depois de fechado — nova leitura vira arquivo novo, e o índice ganha uma linha.

---

## 0.1 Auditoria documental — inventário de dívidas e pendências

**SHA:** `7877652` · **Data:** 23/05/2026 · **Arquivo:** [AUDITORIA_DOCUMENTAL_2026-05-23.md](./AUDITORIA_DOCUMENTAL_2026-05-23.md)

Leitura consolidada dos documentos vivos (ESTADO_ATUAL, TESTING, GOVERNANCA_IA, BASE_REGULATORIA, SEED_DADOS, ADRs) sem confrontar o código, marcando com `[CONFIRMAR NO CÓDIGO]` tudo o que as fontes não resolviam sozinhas. Conclusão: as próprias fontes divergiam entre si, e essas divergências não eram dívidas — eram incertezas de estado que só o código resolveria, o que virou a pauta da Fase 0.

## 0.2 Mapa de gaps confirmado — Fase 0 da skill de diagnóstico

**SHA:** `7877652` · **Data:** 23/05/2026 · **Arquivo:** [MAPA_GAPS_CONFIRMADO_2026-05-23.md](./MAPA_GAPS_CONFIRMADO_2026-05-23.md)

Confronto da auditoria documental acima contra o código real, item a item, com o comando objetivo que decidiu cada caso. Conclusão: onde documento e código divergiam, **o código venceu** — e a regra ficou valendo para as auditorias seguintes.

## 0.3 Fonte única de requisitos documentais

**SHA:** `4261b0a` · **Data:** 20/07/2026 · **Arquivo:** [AUDITORIA_REQUISITOS_DOCUMENTAIS_2026-07-20.md](./AUDITORIA_REQUISITOS_DOCUMENTAIS_2026-07-20.md)

Fase 1 (só leitura) do PR `fix/fonte-unica-requisitos-documentais`, disparada por um sintoma concreto: o sistema acusava matrícula ausente num caso em que a certidão de inteiro teor tinha sido enviada. Conclusão: **não existe no código nenhuma noção compartilhada de "requisito documental satisfeito"** — são 8 lugares respondendo à mesma pergunta com fontes da verdade diferentes, e no caso real três deles discordavam entre si.

## 0.4 Auditoria de fluxo — validações da Isis (30/07 e 02/08)

**SHA:** `50d8c7e`, mergeada no PR #145 · **Data:** 06/08/2026 · **Arquivo:** [AUDITORIA_FLUXO_ISIS_2026-08-06.md](./AUDITORIA_FLUXO_ISIS_2026-08-06.md)

Fase 1 em leitura, medida contra **produção** (processo 16, Fazenda São Jorge; processo 17 como controle) para explicar duas queixas da consultora: "gravou só três campos" e "os dados não aparecem no imóvel". Conclusão: a hipótese de que as duas eram a mesma doença estava **parcialmente certa, e a parte certa não era a que parecia** — a consolidação havia gravado 16 campos em 4 matrículas, e os três que ela via eram exatamente os que a tela renderiza; a promoção para `Property` é que de fato não existia. O nome da doença comum ficou: **o sistema grava certo e não sabe mostrar o que gravou**. É a origem direta do `consolidated_at` ("Aceito" ≠ "Gravado"), que o modelo de staging cita até hoje.

---

## 1. Auditoria Codex — inventário e arquitetura real

**SHA:** `11ab1af` · **Data:** 08/2026 · **Arquivo:** [AUDITORIA_CODEX_11ab1af.md](./AUDITORIA_CODEX_11ab1af.md) (idêntico ao `AuditoriaCodexRegente.docx`; versionado como fonte da triagem — sem o bruto não se confere se a triagem leu certo)

Varredura ampla do repositório: inventário de linguagens, migrations, modelos, endpoints e testes, mais os blocos AUD-01 a AUD-10 sobre arquitetura, multi-tenant, contratos de falha e risco estrutural. Conclusão: a arquitetura declarada e a real batem no esqueleto, e as divergências se concentram nos contratos de borda — que foram triados no item seguinte.

## 2. Triagem da Auditoria Codex — Fase 1 (somente leitura)

**SHA:** `88be956` (PR #146) · **Data:** 10/08/2026 · **Arquivo:** [TRIAGEM_AUDITORIA_CODEX.md](./TRIAGEM_AUDITORIA_CODEX.md)

Triagem dos achados do Codex em 4 listas (procede / procede com ressalva / não procede / precisa de medição), sobre AUD-04, AUD-05, AUD-10 e o risco estrutural do AUD-01, sem alterar código nem abrir dívida. Conclusão: 21 achados novos sobreviveram à conferência — com **AUD-04 (isolamento multi-tenant na escrita)** e **AUD-10 (contratos de falha)** como as duas frentes que viraram trabalho real, a primeira delas fechada no PR #147.

## 3. Spec Isis v0.1 — Conferência, Base e Diagnóstico

**SHA:** `130d715`, incorporada a `main` em `87e9d54` · **Data:** 08/09/2026 · **Arquivo:** [SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md](./SPEC_ISIS_v0.1_Conferencia_Base_Diagnostico.md)

Especificação funcional e histórico de validação do MVP1, de autoria da Isis, convertida do `.docx` sem alteração de conteúdo: entrada, OCR, base cadastral, Conferência e diagnóstico, com os 15 requisitos do gate (OCR-001, OCR-002, HIST-001, REC-001, DATA-002, CONF-001/002, SAVE-001, DIAG-001, DOC-001, ENT-001/002, DATA-001, ROUTE-001) e os defeitos observados nos casos reais. Conclusão: é a autoridade de produto da rodada, e fixa **Valéria e ELODI como casos de regressão permanentes do MVP1**.

## 4. Auditoria independente — Fase 1 (leitura)

**SHA:** `3d1a78f` — `HEAD` local no momento da leitura; `origin/main` já estava em `4a96b5d`, ou seja, **#148 estava no remoto e não no checkout auditado** · **Data:** 09/2026 · **Arquivo:** [AUDITORIA_INDEPENDENTE_FASE1_2026-09.md](./AUDITORIA_INDEPENDENTE_FASE1_2026-09.md)

Auditoria de generalidade em modo leitura: percorre o caminho completo do dado (upload → OCR → extração → staging → agrupamento → consolidação → escrita → tela → diagnóstico) anotando onde há perda ou silêncio, e cruza SAVE-001 por perfil, o modelo PF/PJ, DIAG-001, STATE-001 e o que os testes de #141, #143, #144, #147 e #148 realmente provam. Limites que o próprio relatório declara: nenhuma suíte executada, nenhum arquivo alterado, `amigao_db` inexistente na máquina, reprodução contra banco não feita por conflito com "somente leitura" e spec v0.1 ainda não versionada naquele checkout. Conclusão: **as correções recentes não provaram generalidade** — nenhuma das cinco se classifica como correção sistêmica, os testes cobrem fixtures PF com uma ou duas matrículas conhecidas, e a CNH/CPF de um representante tende a ser gravada como dado do próprio `Client`, por não existir separação estrutural entre titular e representante.

## 5. Matriz P1–P7 — Fase 2 (execução)

**SHA:** `4a96b5d` (main com #148; spec commitada isoladamente em `130d715`) · **Data:** 09/2026 · **Arquivo:** [MATRIZ_PERFIS_FASE2_2026-09.md](./MATRIZ_PERFIS_FASE2_2026-09.md)

O que a Fase 1 não pôde executar, executado: os sete perfis rodados de verdade contra banco descartável (`127.0.0.1:55433/amigao_audit`, migration head `e4f6a8c2b1d9`), produção não acessada, chamando `consolidate_process` — o mesmo serviço do `POST /{process_id}/consolidar`. Mede preparados × persistidos × ignorados × divergências, matrículas antes/depois e `consolidated_at` linha a linha. Fronteira declarada: perfis com **staging já formado** — não mede upload, OCR, classificação, extração nem tela. Conclusão: **5 de 7 passaram; P3 e P6 falharam semanticamente** — em P3 a CNH do representante virou dado do `Client` PJ e a ELODI perdeu o CNPJ original; em P6 o mesmo CNPJ existe duas vezes no tenant, por não haver unicidade `tenant_id + cpf_cnpj`; P4 confirmou o guard do #148 (CCIR/CAR não criam matrícula, e as linhas ficam visíveis em `ignorados`); P7 persistiu os 28 campos com carimbo em todos, provando SAVE-001 **no cenário controlado**, não no ELODI real. O achado mais duro é transversal: **`consolidated_at` carimba mesmo quando a gravação semântica está errada**. P3 e P6 foram fechados depois pela Frente A (PR #149, ADR-063).

## 6. Auditoria independente — Regente Ambiental (Astra)

**SHA:** `4a96b5d` (inclui #148; a branch `fix/identidade-pj-representante` fora do escopo) · **Data:** 09/09/2026 · **Arquivo:** [AUDITORIA_INDEPENDENTE_REGENTE_4a96b5d.md](./AUDITORIA_INDEPENDENTE_REGENTE_4a96b5d.md)

Distância entre a intenção de produto (spec do item 3) e a implementação, requisito a requisito, com convenções explícitas de grau de evidência (CONFIRMADO no código / OBSERVADO / HIPÓTESE / DECISÃO DE PRODUTO / EVOLUÇÃO); leitura de código apenas, sem execução, sem banco. Conclusão: o sistema consolida bem quando o staging já chega com significado e destino corretos, mas **não existe um contrato de ponta a ponta que preserve de quem é o dado, o que significa, qual documento o comprova, para qual finalidade vale e qual decisão o tornou canônico** — e a origem dos erros ELODI ficou marcada como **HIPÓTESE**, por faltar o OCR e o JSON originais.

## 7. Confirmação da entrada — ELODI e Valéria, ponta a ponta

**SHA:** `87e9d54` (main, inclui #149) · **Data:** 09/09/2026 · **Arquivo:** [CONFIRMACAO_ENTRADA_2026-09-09.md](./CONFIRMACAO_ENTRADA_2026-09-09.md)

Primeira rodada a olhar o dado **entrando**: leitura read-only dos dois casos em produção (texto OCR, 45 linhas de staging, `ai_jobs`, `audit_logs`) e reprodução da extração em banco descartável com o código da main, para fechar a lacuna que o item 6 deixou aberta. Conclusão: os cinco defeitos da spec ficam **CONFIRMADOS com origem identificada** — nenhum deles é falha de OCR —, a tese "as peças existem, faltam ligações" é **parcial** (números, áreas do CAR e temporalidade exigem mudar a extração, não só ligá-la), e apareceram quatro achados novos, entre eles um valor gravado que **não existe no documento** (o exemplo do prompt vazando para o dado, em três processos) e a **não-determinação da entrada**: mesmo texto e mesmo código produzem observações diferentes a cada execução.

## 8. Gate pós-deploy — Frente C contra os textos reais de produção

**SHA:** ANTES `41e8534` (main antes do #152) · DEPOIS `ed2c327` (o merge do #152) · **Data:** 09/09/2026 (commit `0b3c72a`, PR #156) · **Arquivo:** [contencao_entrada.md](../trabalhos/contencao_entrada.md) (seção "GATE PÓS-DEPLOY — EXECUTADO")

Fecha a condição declarada no item 7: os 8 documentos (544-551) rodados num banco descartável carregado com o `extracted_text` **real** de produção (md5 conferido documento a documento), antes × depois, duas execuções de cada lado; produção só recebeu `SELECT`. Conclusão: a janela (contenção 2, ADR-064) é o achado principal — no doc 547 o lado antigo gravava em `nirf_cib` o código INCRA do confrontante (char 1.286), e o lado novo o valor certo (char 53.774, vindo da fatia 1), numa janela que a checagem **declarava** ter coberto 82.117/82.117 chars. Essa mesma checagem tinha um furo simétrico ao que ela mede: `cobertura_chars` era calculado sobre a última fatia **planejada**, não a última **processada com sucesso** — se a fatia final falhasse no LLM ou no parse, a janela declarava cobertura completa sem ter lido o trecho. Corrigido em `fix/cobertura-janela` (dívida #222, fechada no mesmo PR). Abriu as dívidas #220 (auditor_imovel sobrescreve status aceito) e #221 (fatia errada preenche o campo quando a certa omite a área).

## 9. Reauditoria Codex — os sete contratos pela metade + o gate E2E

**SHA:** `335e9e5` (main após #167) · **Data:** 11/09/2026 · **Arquivo:** [REAUDITORIA_CODEX_11-09.md](./REAUDITORIA_CODEX_11-09.md) (transcrição do escopo passado pelo André — o original do Codex não chegou ao repo como arquivo; versionado como passo zero da Frente J)

Releitura dos contratos que as Frentes C–I (ADRs 064–068) declararam fechados, contra o código e contra o único caso real capaz de exercitá-los (o #23 reextraído: 116 linhas, 57 tipadas). Conclusão: **sete contratos existem pela metade** — a invalidação não enxerga reextração cacheada, "gravada" esconde evidência nova, o aceite de proposta desatualizada é aviso e não bloqueio, `rl_vigente` ignora a vigência derivada, o tipo de observação não é editável, "lido" não exige texto legível, e a titularidade não conhece sucessão — e **nenhum foi atravessado ponta a ponta num ambiente autenticado**. Fechados na Frente J (`fix/fechamento-contrato-spec`, `docs/trabalhos/fechamento_contrato.md`), com adendos aos ADRs 065–068 e o relatório completo do #23.
