# docs/auditoria — índice

Auditorias do Regente Ambiental, em ordem cronológica. Cada item registra **o que auditou**, **o SHA sobre o qual leu** e a **conclusão em uma frase**.

Regra da pasta: auditoria é fotografia de um SHA. Não se edita um relatório depois de fechado — nova leitura vira arquivo novo, e o índice ganha uma linha.

---

## Anteriores (2026-05 / 2026-07)

- **[AUDITORIA_DOCUMENTAL_2026-05-23.md](./AUDITORIA_DOCUMENTAL_2026-05-23.md)** — leitura consolidada dos docs vivos, sem tocar o código; levantou divergências entre as próprias fontes para a Fase 0 resolver.
- **[MAPA_GAPS_CONFIRMADO_2026-05-23.md](./MAPA_GAPS_CONFIRMADO_2026-05-23.md)** — confronto daquela auditoria documental contra o código real; onde os dois divergiam, o código venceu.
- **[AUDITORIA_REQUISITOS_DOCUMENTAIS_2026-07-20.md](./AUDITORIA_REQUISITOS_DOCUMENTAIS_2026-07-20.md)** — origem do "4 documentos pendentes" com a matrícula já enviada; achou 8 lugares respondendo "requisito documental satisfeito" com fontes da verdade diferentes, três deles discordando no caso real.

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

**Arquivo:** *ainda não versionado — texto com o André.*

Fase de leitura que precedeu a execução da matriz de perfis. É citada como insumo pela auditoria independente do item 6 ("os cinco documentos de validação de 20/07, 21/07, 26/07, 30/07 e 02/08"), mas o texto não está no repositório. **Pendente de versionamento neste diretório.**

## 5. Matriz P1–P7 — Fase 2 (execução)

**Arquivo:** *ainda não versionado — texto com o André.*

Execução dos sete perfis de caso (P1 a P7) contra o sistema, com staging preparado, para medir o que a consolidação de fato grava. Conclusão, conforme citada pela auditoria do item 6: **P1/P2/P5/P7 passaram, P4 verificou criação por certidão e guard, P3 gravou na pessoa errada e P6 expôs duplicidade** — o "5 de 7" não é taxa de confiabilidade do produto, e sim o resultado de sete cenários preparados. **Pendente de versionamento neste diretório.**

## 6. Auditoria independente — Regente Ambiental (Astra)

**SHA:** `4a96b5d` (inclui #148; a branch `fix/identidade-pj-representante` fora do escopo) · **Data:** 09/09/2026 · **Arquivo:** [AUDITORIA_INDEPENDENTE_REGENTE_4a96b5d.md](./AUDITORIA_INDEPENDENTE_REGENTE_4a96b5d.md)

Distância entre a intenção de produto (spec do item 3) e a implementação, requisito a requisito, com convenções explícitas de grau de evidência (CONFIRMADO no código / OBSERVADO / HIPÓTESE / DECISÃO DE PRODUTO / EVOLUÇÃO); leitura de código apenas, sem execução, sem banco. Conclusão: o sistema consolida bem quando o staging já chega com significado e destino corretos, mas **não existe um contrato de ponta a ponta que preserve de quem é o dado, o que significa, qual documento o comprova, para qual finalidade vale e qual decisão o tornou canônico** — e a origem dos erros ELODI ficou marcada como **HIPÓTESE**, por faltar o OCR e o JSON originais.

## 7. Confirmação da entrada — ELODI e Valéria, ponta a ponta

**SHA:** `87e9d54` (main, inclui #149) · **Data:** 09/09/2026 · **Arquivo:** [CONFIRMACAO_ENTRADA_2026-09-09.md](./CONFIRMACAO_ENTRADA_2026-09-09.md)

Primeira rodada a olhar o dado **entrando**: leitura read-only dos dois casos em produção (texto OCR, 45 linhas de staging, `ai_jobs`, `audit_logs`) e reprodução da extração em banco descartável com o código da main, para fechar a lacuna que o item 6 deixou aberta. Conclusão: os cinco defeitos da spec ficam **CONFIRMADOS com origem identificada** — nenhum deles é falha de OCR —, a tese "as peças existem, faltam ligações" é **parcial** (números, áreas do CAR e temporalidade exigem mudar a extração, não só ligá-la), e apareceram quatro achados novos, entre eles um valor gravado que **não existe no documento** (o exemplo do prompt vazando para o dado, em três processos) e a **não-determinação da entrada**: mesmo texto e mesmo código produzem observações diferentes a cada execução.
