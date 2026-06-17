# LIÇÕES APRENDIDAS — protocolo de trabalho Regente (amigao)
> Documento que viaja entre chats. Subir junto com `BRIEFING_SESSAO.md` no início de cada sessão.
> Vive em `docs/estado/LICOES_APRENDIDAS.md`. Cada lição nasceu de um desgaste real — não repetir.
> Última atualização: 2026-06-17

---

## REGRA DE OURO — pacote de contexto no início, não gota a gota
**No começo de QUALQUER trabalho que toca código, o Claude pede de uma vez o que precisa — não arquivo por arquivo.**
- Para coordenar/diagnosticar o backend: subir `app/` compactado (zip).
- Para frontend: subir `frontend/src/` (ou a parte relevante) compactado.
- Artefatos de contexto: `WORKFLOW.md`, `ENTRADA_DEMANDA.md`, `BRIEFING_SESSAO.md` (já em md no repo).
- Skills: os `SKILL.md` dos agentes envolvidos.
> Origem da lição: nesta sessão o Claude pediu arquivo por arquivo, reagindo a cada erro. Custou horas. O certo era pedir o `app.zip` na primeira vez que percebeu estar sem o código.

## O Claude-chat NÃO tem acesso ao repo
Ele coordena cego a menos que arquivos sejam subidos. A memória entre sessões é um RESUMO — não substitui ler o código real. Sempre que uma afirmação depender de código, ou se lê o código subido, ou se diz "não sei, sobe o arquivo X". Nunca afirmar de memória.
> Origem: o Claude afirmou "tema escuro / produção roda código antigo" sem olhar os prints (que eram claros). Erro de representação mental, não de fato.

## VALIDAÇÃO E2E REAL encerra trabalho — não tsc/build/unit
Toda correção de comportamento exige reproduzir RODANDO antes e revalidar RODANDO depois (request/log/SQL real). "Compila" e "passa nos testes" não provam que o comportamento mudou.
> Origem: PRs passavam no build e mesmo assim a Isis via bugs em produção. Faltava reproduzir o fluxo real.

## Causa raiz com evidência, antes de corrigir
Não remediar sintoma. Medir onde quebra (linha de código, request, log) antes de propor fix. Quando não reproduziu, é "pergunta em aberto", não conclusão.
> Origem: ciclos de "corrige isto ou aquilo" sem entender o todo. O mergulho que RODOU o sistema é que destravou.

## Ambiente tem que subir antes de validar
`docker compose up` precisa estar destravado (Evolution fora do boot, #44). Sem o sistema de pé, qualquer agente volta a adivinhar. Pré-requisito de qualquer mergulho.

## Fonte de verdade única — sem duplicar formato
Artefato que o sistema lê fica em UM formato versionado. Skill = `SKILL.md` (o `.docx` se descarta). Workflow/entrada = `.md` no repo (não recompartilhar xlsx). Duas fontes = a que o sistema ignora vira ruído.

## Ritual de início e fim de sessão (contra perda de contexto)
- **Início:** André sobe `BRIEFING_SESSAO.md` + `LICOES_APRENDIDAS.md` (+ código relevante zipado se for tocar código).
- **Fim:** Claude devolve os dois atualizados; André commita em `docs/estado/`.
- Toda lição nova de desgaste entra aqui na hora — não espera o fim.

## Comunicação
Sem bajulação. Decisões + impacto no chat; detalhe técnico nos prompts dos agentes. Uma pergunta por vez. Português. Owning de erro sem auto-flagelo: reconhece, corrige o rumo, segue.

## Numeração de dívidas e PRs é a REAL do repo
Nunca inventar número (#24, #29...). Conferir no `REGISTRO_DIVIDAS.md` / GitHub. Números errados em prompt confundem o agente.

## Orquestração de chains NÃO está congelada
O congelamento (ADR-009) é só mobile + client-portal. Agentes já travaram trabalho por achar que a chain era intocável — não é.

## Deploy de código ≠ migration aplicada — validação de fase inclui o banco de prod
O Render (e qualquer deploy de imagem) sobe **código**, não aplica migration sozinho. Uma fase pode "deployar verde" e mesmo assim o banco de prod estar sem a tabela/coluna nova → o sistema quebra em runtime e alguém valida sobre algo quebrado. **Validar uma fase em prod inclui conferir o schema** (`alembic current` = head, `/health` verde). Migration agora é automática no deploy (`preDeployCommand` na API — ver `docs/trabalhos/hardening_deploy.md`), mas a lição de validação permanece.
> Origem: incidente 2026-06-06 — Fases 1-4 deployaram sem `extracted_field_staging`; extrator explodia (`UndefinedTable`) e a chain entrava em retry storm de 60s; a sócia validou em cima de um sistema quebrado. Corrigido manual no Shell e depois automatizado.

## Retry só resolve erro transitório — determinístico é falha imediata
Retry de exceção genérica esconde erro determinístico (schema ausente, constraint, input inválido) por horas — retry nunca conserta isso. Distinga: `ProgrammingError`/`IntegrityError`/`DataError`/`ValueError`/`PendingRollbackError` → falha rápida e visível (sem retry); rede/timeout/deadlock (`OperationalError`) → retry. Sessão SQLAlchemy abortada faz o `commit` seguinte levantar — não capture isso como "transitório".

## Verificar a premissa do prompt contra o código, não assumir
Premissa de incidente pode estar stale. Antes de "criar a rota que falta", confirme se ela já existe (inspecionar as rotas reais do app). No hardening 2026-06-06 o `/processes/{id}/extract` "fantasma" **existia** — o real era a UI sem tratamento de erro de disparo.

## Mudança de formato de saída do LLM exige redimensionar max_tokens e golden test ANTES do merge
Quando o formato de saída de um agente cresce (ex.: #70 fez cada passivo/ação carregar `{afirmacao, fonte, confianca}` → JSON 2-3× maior), o teto de `max_tokens` de saída tem que ser **redimensionado no mesmo PR** — senão o caso grande estoura, o provider devolve `finish_reason=length` e o JSON chega truncado, falhando no parser de forma INTERMITENTE ("uma hora vai, outra não": só quebra quando a saída passa do teto). E o gateway tem que **capturar `finish_reason`** e tratar truncamento como erro próprio (retry com teto maior → erro legível), nunca confundir com erro de parse. Todo agente LLM precisa de **golden test** (resposta real gravada → parser produz o shape) que rode no CI e barre a regressão antes do merge.
> Origem: caso #12 (São Jorge, 228 campos) falhou 3+× em prod após o #70 — `AI_MAX_TOKENS=2048` global não comportava o formato novo do diagnóstico (gpt-4.1). Fix em `fix/llm-consistencia` (07/06): teto dedicado 32.768 + retry de truncamento + golden tests. Ver `docs/trabalhos/llm_consistencia.md`.

## Validação de fase em prod inclui conferir se o DADO está lá, não só o schema
Schema via migration ≠ dado presente. O corpus de legislação (RAG, ~23k chunks) foi ingerido em dev/local e **nunca em prod** — `knowledge_catalog` ficou com 0 linhas no Supabase prod, o RAG voltava zero trechos (`tokens_in≈600`) e a legislação declarava "ausência de trechos" sem ninguém perceber. Tabela vazia não dá erro: degrada em silêncio. Ao validar uma fase que depende de corpus/seed, **conte as linhas em prod** (`SELECT count(*)`), não confie em "a migration rodou".
> Origem: Item 4 de `fix/llm-consistencia` (07/06). Observabilidade adicionada (log quando RAG=0); ingestão em prod virou dívida #47.

## Golden test só protege o que está no fixture — incluir os formatos REAIS, não os sintéticos
Um golden test trava exatamente os casos que estão no fixture; tudo fora dele continua exposto. O #72
adicionou golden de parse de área mas só com o **dict serializado** (`{value:...}`) — a MESMA falha
reentrou pela **string crua do OCR** em formato BR (`"1.010,7113"` lido como `1,0107113`: ponto de
milhar virou decimal) e nenhum teste pegou, porque essa string não estava no fixture. Ao escrever golden
de parse/normalização, inclua **todas as formas de entrada que o mundo real produz** (BR, US, com
unidade, com envelope dict, lixo) e a regressão exata que motivou o fix — não só o caso que você acabou
de corrigir. Mesma natureza do "valor sentinela tratado como dado" (caso #12, A e E): a porta de
conversão tem que ser ÚNICA e os goldens cobrirem suas bordas.
> Origem: validação Isis 16/06 (`fix/parse-br-consolidacao-rastreabilidade`). `parse_area_ha` consolidada
> como porta única; golden com todos os formatos em `tests/services/test_parse_area_br.py`.

## "Confirmar e gravar" tem que terminar no que a tela LÊ — não só no que o endpoint ESCREVE
A consolidação (#63) gravava corretamente em `Matricula`, mas o Imóvel Hub seguia "—": ele lia as colunas
cruas de `Property` (`registry_number`/`total_area_ha`) que a consolidação **nunca grava** (matrícula
vive em `Matricula`; área do imóvel é derivada da soma). O ciclo só fecha de verdade quando o caminho
**staging→confirmar→base→tela** é validado ponta a ponta no que a UI realmente consome — não basta o
endpoint retornar 200 e gravar "em algum lugar". Ao fechar um fluxo de escrita, confirme qual entidade/
coluna a tela de resultado lê e prove que ela aparece populada.
> Origem: validação Isis 16/06. Fix: `get_property_hub_summary` deriva Matrícula/Área das matrículas;
> Fluxo 8 em `docs/arquitetura/FLUXOS_E2E.md` agora inclui o passo "Imóvel Hub (resultado visível)".

> Atualizado: 2026-06-17.
