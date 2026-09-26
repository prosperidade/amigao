# Métodos e preços do tenant (#282) e o motor comparado pelo conteúdo (#289) — registro

26/09/2026. Empilhado no PR #218 (telas do motor e do comercial). **Só dev**; produção intocada.
Decisões do André em 25/09: #289 compara por conteúdo; #290 vai para a curadoria.

## 1. O que entrou

| Peça | Onde |
|---|---|
| #289 — conteúdo da execução | [avaliador.py](../../app/services/motor_juridico/avaliador.py): `regras_hash` (versões e `hash_conteudo` das regras que a execução avaliou, ordenadas), `conteudo_execucao`, `execucoes_equivalentes` (mesmo caso, mesmo `fatos_hash` e `regras_hash`) |
| #289 — ciência | `ciencias_vigentes`: a ciência da própria avaliação ou, na falta, a da mesma versão de regra numa execução anterior de mesmo conteúdo. `alertas_sem_ciencia`, o `fechar` da Rota, o redator e o detalhe da evidência passam a usá-la. O relatório da execução devolve `ciencia: {id, avaliacao_id, herdada}` |
| #289 — atualidade | [base.py](../../app/services/comercial/base.py): a base do relatório e do escopo guarda `motor: {fatos_hash, regras_hash}` (o ID da execução fica para a auditoria). Motivos novos: "Os fatos lidos pelo motor jurídico mudaram" e "As regras do motor jurídico mudaram". Base gravada antes (só o ID) é lida pelo conteúdo daquela execução |
| #289 — tela | o alerta com ciência herdada aparece como "ciência de execução anterior (mesmos fatos e regras)", com a ciência clicável |
| #282 — métodos e preços | [MetodosPrecos.tsx](../../frontend/src/pages/Settings/MetodosPrecos.tsx), aba de Configurações (`/settings?tab=metodos`, atalho no orçamento): lista com preço, unidade, regras e padrão; novo método com as regras do motor; editar, desativar e reativar como versão nova; histórico de versões; aviso quando não há padrão ativo |

Testes: `tests/comercial/test_conteudo_motor_289.py` (6, banco real: reexecução sem fato novo não
desatualiza; fato novo desatualiza com o motivo; base antiga lida pelo conteúdo; regra diferente
desatualiza; ciência herdada; fato novo reabre a ciência). Frontend: `MetodosPrecos.test.tsx` (5) e
o caso da ciência herdada em `TelasMotorComercial.test.tsx`; total 33 arquivos, 200 testes. Recorte
comercial + motor + Rota: 105 verdes. Suíte e lint completos no CI.

## 2. Percurso em dev, no navegador

Mesmo arranjo do #218 (API da worktree em `:8040`, Vite em `:5182`, banco `127.0.0.1:15432/amigao_db`,
Chromium headless). Roteiro: [scripts/provar_metodos_289.mjs](../../scripts/provar_metodos_289.mjs).
Transcrição (IDs, estados, totais, hashes): [provas/metodos_289_dev_2026-09-26.json](provas/metodos_289_dev_2026-09-26.json).
Commit na tela: **2b966cb** (rodapé "Painel 2b966cb · API 2b966cb · desenvolvimento" em todas as telas).
Passou na primeira rodada.

| Etapa | #23 (processo 65) | #25 (processo 66) |
|---|---|---|
| Gerar pelo motor sem fato novo | execução 17, mesmo `fatos_hash`; relatório, escopo e orçamento 12 **seguem atuais** | execução 18; alerta REG-FUN-012 **sem pedir ciência** — vale a ciência 3 (dada na avaliação 95), mostrada como herdada; cadeia segue atual |
| Base antiga | o escopo 30 e o orçamento 12 foram gravados antes do #289 (só o ID da execução) e foram lidos pelo conteúdo | idem (escopo 32, orçamento 15) |
| Preço novo pela tela | CCIR R$ 900 → **R$ 950** (versão 2) | Inscrição no CAR R$ 1.800 → **R$ 1.900** (versão 2) |
| Orçamento | o 12 saiu desatualizado: "Método "ccir" mudou (v1 → v2)"; v5 gerado, R$ 950, aprovado | o 15 saiu desatualizado pelo método; v12 gerado, R$ 1.900, aprovado |
| Proposta | **proposta 11**, R$ 950, do orçamento 16 | **proposta 12**, R$ 1.900, do orçamento 17 |
| Recarga e nova sessão | orçamento 16 aprovado e atual | orçamento 17 aprovado e atual |

**Estado deixado no dev:** os preços de prova ficaram em R$ 950 (CCIR) e R$ 1.900 (CAR) — devolvê-los
desatualizaria de novo os orçamentos aprovados. Nenhuma escrita direta no banco nesta frente (a senha do
usuário 38 é a do #218).

## 3. O que fica

- **#284** (orçamentos legados de código) está desbloqueada: toda proposta pode nascer do orçamento
  do tenant.
- **#290** está na curadoria da zona normativa como caso de versão de dispositivo
  ([ZONA_NORMATIVA_INCREMENTO4A.md](ZONA_NORMATIVA_INCREMENTO4A.md) §7).
- A comparação cobre fatos e regras, como decidido; a data de referência da execução não entra no
  conteúdo. Se a vigência de uma norma mudar entre duas execuções com os mesmos fatos e regras, isso
  não desatualiza a cadeia por esta via — não medido nesta frente.
- Merge do #218 e deste PR só com a autorização do André.
