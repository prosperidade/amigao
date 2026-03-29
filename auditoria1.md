1) Diagnóstico executivo (estado atual real)
Situação geral: o sistema está em estágio de MVP funcional avançado de backend, com portal cliente e automações básicas, mas com lacunas estruturais importantes para produção (especialmente migrations, confiabilidade de setup, observabilidade real e consistência com as regras de negócio documentadas).

Nível de implementação (estimativa prática)
Backend API (CRUD + auth + escopo tenant/client): ~75%

Banco de dados/modelagem: ~65%

Migrations/versionamento de schema: ~20% (crítico)

Worker assíncrono (Celery + notificações/PDF): ~70%

Observabilidade operacional real (métricas/tracing/alertas): ~30%

Testes automatizados executáveis no ambiente atual: ~35%

Frontend painel interno (Vite): ~40%

Portal cliente (Next): ~70%

Mobile (Expo): ~55% (há estrutura/código, mas README está genérico de template).

2) Problemas reais do sistema hoje (priorizados)
P0 — Críticos (bloqueiam confiabilidade de ambiente/prod)
Estratégia de banco inconsistente: Alembic no deploy, mas sem cadeia de migrations versionadas no checkout atual.

O docker-compose sobe API com alembic upgrade head.

Porém, no diretório alembic há infra (env.py), mas o histórico documentado aponta alembic/versions/... como entregue em sprint — isso não está refletido de forma confiável no estado atual do código analisado.

init_db cria schema por create_all e importa só parte dos modelos.

O script só importa tenant/user/client/process, deixando outros modelos fora do bootstrap explícito e conflitando com fluxo via Alembic.

Isso abre espaço para ambiente “meio configurado”, especialmente em setups manuais.

Dependências faltantes para execução real de fluxos declarados.

tests falham por ausência de httpx (requerido pelo TestClient).

init_db depende de sqlalchemy_utils, mas pacote não está em requirements.txt.

Worker usa litellm e PDF usa fpdf2, ambos não aparecem no requirements.txt.

P1 — Altos (risco funcional/silencioso)
Desalinhamento entre regra de negócio documentada e implementação de tarefas.

Documento define estados backlog/a_fazer/em_progresso/....

Código implementa todo/in_progress/review/done.

Resultado: risco de regra quebrada em integrações, dashboards e automações.

Observabilidade prometida (JSON + métricas + alertas) não está materializada.

Documento exige logs JSON, métricas, traces e alertas.

Implementação atual usa formatter textual simples sem pipeline de métricas/tracing/alerta.

Autenticação de portal cliente é por match de e-mail entre User e Client.

Isso funciona no MVP, mas acopla identidade a e-mail e pode causar comportamento inesperado em cenários de múltiplos contatos/alteração de e-mail.

Segurança operacional frágil por defaults inseguros e seed previsível.

SECRET_KEY default fraca no código e senha seed admin123.

Notificação por e-mail “finge sucesso” quando SMTP não configurado.

O serviço retorna True em modo simulado sem envio real, o que pode mascarar falhas de operação/compliance.

P2 — Médios (qualidade/manutenção)
Documentação de progresso super-otimista versus estado executável.

Docs marcam entregas e validações como 100% concluídas, mas testes não rodam no ambiente atual sem ajustes de dependências e estratégia de migration não está íntegra.

README do frontend/mobile está genérico de template, reduzindo onboarding real da equipe nesses módulos.

3) Banco de dados e migrations — diagnóstico
Modelagem: boa cobertura de entidades núcleo (processes, tasks, documents, audit_logs, communication, properties, etc.).

Risco principal: ausência de trilha Alembic consistente no estado atual + coexistência com create_all parcial no init_db.

Impacto real: drift de schema entre ambientes (dev/staging/prod), falhas silenciosas em deploy, dificuldade de rollback.

4) Bugs silenciosos prováveis (que não explodem de cara)
Envio de e-mail contabilizado como sucesso sem SMTP (falso positivo operacional).

Estados de tarefa incompatíveis com documento de negócio (inconsistência de workflow).

Scripts/infra de setup com caminhos diferentes (alembic vs create_all) gerando ambientes diferentes com “aparência de OK”.

Cobertura de testes existe, mas não é executável out-of-the-box no ambiente atual (dependência ausente), reduzindo confiança de regressão.

5) Plano de solução (objetivo e prático)
Fase 1 (48h) — estabilização mínima
Congelar estratégia de schema em Alembic (proibir create_all fora de teste).

Restaurar/gerar cadeia oficial de migrations (baseline + revisões incrementais).

Fechar requirements.txt com dependências reais de runtime/teste (httpx, sqlalchemy-utils, litellm, fpdf2, pytest).

Trocar defaults inseguros (SECRET_KEY obrigatória, remover seed com senha fixa).

Fail-fast em e-mail: em produção, SMTP inválido deve falhar e alertar (não “simular sucesso”).

Fase 2 (1 semana) — integridade funcional
Unificar máquina de estados de tarefa (documento ↔ backend ↔ frontend).

Criar testes de contrato de estados e transições para processo/tarefa/documento.

Adicionar migration checks no CI (alembic upgrade head + downgrade +1/-1 smoke).

Fase 3 (2 semanas) — operação de produção
Observabilidade real: logs JSON, métricas Prometheus, tracing OpenTelemetry, alertas de erro/fila.

SLOs mínimos com dashboards para API/worker/sync/upload.

Hardening de auth: revisão do vínculo portal por e-mail e política de identidade do cliente.

6) Validações que rodei agora
⚠️ pytest -q
Falhou por dependência ausente (httpx) no ambiente atual.

✅ python -m compileall app tests
Compilação Python concluída.

✅ git status --short
Repositório sem alterações locais.