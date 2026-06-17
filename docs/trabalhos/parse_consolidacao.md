# Parse BR definitivo + Consolidação (Ficha 05) + rastreabilidade total

> PR `fix/parse-br-consolidacao-rastreabilidade` (base main). Origem: validação
> da Isis em 16/06 (ciclo completo no caso real em prod). Três pontos: (1) parse
> de área BR — REGRESSÃO do #72 por outro caminho; (2) consolidação que NÃO
> gravava na base (Imóvel Hub seguia "—"); (3) rastreabilidade parcial no
> diagnóstico. Aditivo: nenhum shape antigo quebra.

## Item 1 — Parse BR definitivo (mata o falso passivo de área)

**Sintoma (caso real):** o passivo nº1 do diagnóstico era "divergência de área
~1010,4 ha" porque o RAT `1.010,7113 ha` foi lido como `1,0107113` ha — o ponto
de milhar (formato BR) foi interpretado como decimal americano. O #72 corrigiu o
caso do dict serializado; a MESMA falha reentrou pela **string crua do OCR**.

**`parse_area_ha` é a porta ÚNICA de conversão de área** (`inconsistency_matrix.py`).
Cobre todas as formas reais do staging:

| entrada | regra | saída (ha) |
|---|---|---|
| `"1.010,7113"` (BR) | vírgula = decimal, ponto = milhar | `1010.7113` |
| `"3.502.445,851"` (BR) | idem | `3502445.851` |
| `"660.6561"` (US/limpo) | só ponto → decimal (não inventa milhar) | `660.6561` |
| `"1,234.56"` (US milhar) | ponto = decimal, vírgula = milhar | `1234.56` |
| `"660,6561 ha"` | unidade ha = no-op | `660.6561` |
| `"6.606.561,00 m²"` | m² → ha (÷10.000) | `660.6561` |
| `{"value": "1.010,7113"}` | desembrulha dict (#72) | `1010.7113` |
| `None/""/"-"/[]/{}/bool` | não-numérico | `None` |

**Regra do separador (documentada em `_normalize_number_str`):** quando `.` e `,`
coexistem, **o separador mais à direita é o decimal** e o outro é milhar (BR e US
se desambiguam pelo último). Só vírgula → decimal. Só ponto → mantém (não inventa
milhar onde não há vírgula).

**Validação de ordem de grandeza** (`is_area_plausible`, `AREA_PLAUSIBLE_MIN/MAX_HA`
= 0,1–100.000 ha): área fora da faixa NÃO é gravada como fato — na consolidação
volta `None` → `ignorados`; na matriz vai pra linha de revisão.

**Defesa relativa na matriz** (`AREA_PARSE_ARTIFACT_RATIO = 100`): quando a área do
imóvel (CAR/RAT) é ≥100× MENOR que a soma das matrículas, é quase certo separador
de milhar perdido (cai DENTRO da faixa plausível, mas é absurdo o imóvel ser 1000×
menor que suas próprias matrículas). Sai do confronto → linha `area_revisao`
(`atencao`), nunca falso passivo de área.

**Anti-invenção na extração** (`ficha01_extraction.py`): o prompt do extrator agora
manda **copiar o número verbatim como STRING** preservando separadores BR — quem
converte é o sistema (a porta única), nunca o LLM.

**Golden tests** (`tests/services/test_parse_area_br.py`): todos os formatos acima +
a regressão exata `"1.010,7113" → 1010.7113` (jamais ~1 ha) + defesa relativa da
matriz. O golden do #71 não pegou porque a string BV crua não estava no fixture —
LIÇÃO: golden só protege o que está no fixture.

## Item 2 — Consolidação (Ficha 05) — fecha o ciclo do intake

**MEDIDO (premissa verificada):** o #63 (Fase 4) já gravava em Cliente/Imóvel/
Matrícula via `consolidate_process`, mas o **Imóvel Hub continuava "—"** por dois
furos:

1. **O Hub lia colunas cruas de `Property`** (`registry_number`, `total_area_ha`)
   que a consolidação NUNCA grava — matrícula vive em `Matricula`, e a área do
   imóvel é **derivada** da soma das matrículas (`area_total_matriculas()`).
   → `properties.py:get_property_hub_summary` agora **deriva** Matrícula
   (`"; ".join` dos números) e Área (soma das matrículas) quando as colunas cruas
   estão vazias. Cobertura: `tests/api/test_property_hub_derivacao.py`.
2. **A consolidação não modelava multi-fonte/versão/reconciliação** (Ficha 05).

**`consolidate_process` reescrito conforme Ficha 05:**

- **Agrupamento por DESTINO** `(entidade, [hint], campo)`: múltiplas fontes para o
  mesmo destino → **uma vencedora**.
- **Âncora SIGEF** (`_SIGEF_ANCHORED = {area_ha, denominacao_imovel}`): sem escolha
  explícita do consultor, vence o SIGEF (Ficha 05). Ordem de desempate em
  `_pick_winner`: edição do consultor > âncora SIGEF > confiança > menor id.
- **Edição manual sobrepõe extraído**, `fonte="consultor"` (`_is_consultor_edit`).
- **Achado não grava valor:** `divergente_fundo` aceito vira achado
  (`decided_value=None`, roteado pela matriz) — não escreve coluna. (Corrigido bug
  em `decide_field`: a checagem de `divergente_fundo` rodava DEPOIS de `status =
  aceito`, então nunca disparava; agora captura o status original antes.)
- **UPSERT versionado + audit por campo:** cada write registra `anterior→novo +
  fonte` no `AuditLog` (hash chain) — o histórico por campo é o próprio audit.
  Matrícula nova → cria; nunca sobrescreve em lugar sem registrar.
- **Idempotência:** chave (caso+entidade+campo+matrícula); re-gravar o MESMO valor
  é no-op (não duplica, não conta como write). `_values_differ` com tolerância
  ~0,01% para float.
- **Reconciliação** (`ConsolidationReconciliation`): doc novo com valor divergente
  de campo JÁ consolidado → NÃO sobrescreve sozinho; volta como alerta pro
  consultor decidir.
- **Não grava derivados** (área do imóvel) — são saída de agente. Área implausível
  não grava (Item 1).

Cobertura nova em `tests/api/test_fase4_consolidacao.py`: âncora SIGEF, reconciliação
não-sobrescreve, achado (`divergente_fundo`) não grava.

## Item 3 — Rastreabilidade total no diagnóstico (Ficha 04, regra de ouro)

**Sintoma:** o diagnóstico citava fonte em ALGUNS passivos, não em TODOS. O #70
implementou o contrato `{afirmação, fonte}`; aqui garantimos **cobertura 100%**.

`diagnostico.py:_build_afirmacoes` agora gera **uma `Afirmacao` por passivo e por
ação** (a lista canônica exibida). Para cada item, casa por **sobreposição de
conteúdo** (coeficiente de overlap ≥ 0,6, dentro da categoria — não cruza
passivo↔ação) a fonte que o LLM atribuiu no campo `afirmacoes`; sem casamento →
piso honesto `sem_fonte` ("sem fonte identificada", jamais inventa). Antes, se o
LLM citasse só alguns, os demais passivos ficavam órfãos.

UI (`AgentResultRenderer.tsx`): a lista crua "Hipóteses / Passivos" só aparece em
payloads antigos sem `afirmacoes` — quando há afirmações, elas cobrem 100% dos
passivos (com fonte ou marcados sem fonte), evitando passivo exibido como fato sem
fonte.

## Validação (aceite — caso real da Isis)

- Área do RAT lida como ~1.010,7 ha (não 1,01); falso passivo de área some.
- "Confirmar e gravar" → Imóvel Hub populado (Matrícula/Área derivadas); audit
  trail gravado; idempotente.
- Diagnóstico: 100% dos passivos com fonte (ou marcados sem fonte).
- Golden tests novos (formatos BR) verdes; suites completas verdes.

Validação LLM end-to-end (diagnóstico no caso real) é **pós-deploy** — o resto é
determinístico e coberto por testes.
