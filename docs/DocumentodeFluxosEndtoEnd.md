Documento de Fluxos End-to-End (E2E)
Projeto: Plataforma Ambiental SaaS (App Ambiental)
Versão: 1.0
________________________________________
1. Objetivo
Definir os fluxos ponta a ponta do sistema, descrevendo como os módulos interagem desde a entrada da demanda até a entrega final, incluindo:
•	atores envolvidos 
•	gatilhos 
•	estados 
•	automações 
•	decisões humanas 
•	exceções 
•	integrações 
•	pontos de auditoria 
Este documento serve como referência para:
•	produto 
•	backend 
•	frontend 
•	mobile 
•	IA 
•	QA 
•	operação 
________________________________________
2. Atores do sistema
2.1 Atores humanos
•	cliente final / agricultor 
•	consultor 
•	técnico de campo 
•	parceiro terceirizado 
•	gestor 
•	administrador do tenant 
2.2 Atores sistêmicos
•	painel operacional 
•	portal do cliente 
•	app mobile de campo 
•	API Core 
•	workers assíncronos 
•	AI Gateway / Model Router 
•	OCR pipeline 
•	integrações externas 
•	storage 
•	banco de dados 
•	motor de notificações 
________________________________________
3. Visão macro dos fluxos
Os fluxos principais do sistema são:
1.	Entrada da demanda 
2.	Triagem e criação do processo 
3.	Diagnóstico documental 
4.	Planejamento operacional 
5.	Execução interna 
6.	Execução em campo offline 
7.	Protocolo / integração com órgão 
8.	Retorno de órgão e pendências 
9.	Comunicação com cliente 
10.	Geração de proposta/contrato 
11.	Encerramento e arquivamento 
12.	Fallbacks operacionais 
13.	Fluxo futuro GovTech 
________________________________________
4. Fluxo E2E 01 — Entrada da demanda
4.1 Objetivo
Receber uma nova demanda e transformar uma entrada informal em registro estruturado.
4.2 Canais de entrada
•	WhatsApp 
•	e-mail 
•	formulário web 
•	cadastro manual no painel 
•	indicação/parceiro 
•	portal do cliente 
4.3 Fluxo
Cliente envia mensagem/documento
-> provider (WhatsApp/e-mail)
-> webhook chega na API Core
-> thread é criada
-> mensagem é persistida
-> job do Agente Atendente é criado
-> IA classifica intenção
-> sistema sugere lead ou pré-processo
-> consultor revisa
-> lead entra em triagem
4.4 Dados capturados
•	nome do cliente 
•	contato 
•	intenção 
•	tipo de demanda sugerido 
•	urgência 
•	anexos recebidos 
•	origem do lead 
4.5 Pontos de decisão
•	abrir lead 
•	abrir processo diretamente 
•	solicitar mais dados 
•	descartar entrada 
4.6 Exceções
•	mensagem sem contexto suficiente 
•	arquivo ilegível 
•	duplicidade de cliente 
•	provider indisponível 
4.7 Auditoria
Registrar:
•	canal de entrada 
•	payload recebido 
•	classificação da IA 
•	decisão humana 
________________________________________
5. Fluxo E2E 02 — Triagem e criação do processo
5.1 Objetivo
Transformar a demanda em um processo operacional válido.
5.2 Fluxo
Lead em triagem
-> consultor revisa dados
-> cliente é criado ou vinculado
-> imóvel é criado ou vinculado
-> tipo de processo é definido
-> processo é criado
-> status muda para diagnostico
5.3 Regras
•	cliente é obrigatório 
•	tipo de processo é obrigatório 
•	imóvel pode ser opcional no início 
•	processo sempre recebe responsável inicial 
5.4 Saídas
•	processo criado 
•	timeline iniciada 
•	status diagnostico 
•	vínculo com cliente/imóvel 
•	tarefas iniciais opcionais 
5.5 Exceções
•	cliente duplicado 
•	imóvel ainda desconhecido 
•	demanda fora do escopo 
•	documentos faltantes 
________________________________________
6. Fluxo E2E 03 — Diagnóstico documental
6.1 Objetivo
Estruturar os documentos recebidos e gerar diagnóstico inicial.
6.2 Fluxo
Documento enviado
-> upload seguro para storage
-> metadado salvo no banco
-> job OCR criado
-> worker faz pré-processamento
-> OCR extrai texto
-> job do Agente Extrator é criado
-> AI Gateway escolhe provider por capability
-> dados estruturados são gerados
-> score de confiança é calculado
-> se baixa confiança -> revisão humana
-> diagnóstico consolidado no processo
6.3 Regras
•	OCR sempre antes do LLM 
•	documento ruim nunca vai cru para IA 
•	extração crítica exige revisão se confiança baixa 
•	nova versão do documento não sobrescreve anterior 
6.4 Saídas
•	texto bruto 
•	texto normalizado 
•	dados estruturados 
•	inconsistências detectadas 
•	checklist inicial 
•	resumo técnico preliminar 
6.5 Exceções
•	OCR falhou 
•	PDF corrompido 
•	provider de IA indisponível 
•	schema de extração inválido 
•	custo bloqueado por política do tenant 
6.6 Fallback
•	retry automático 
•	troca de provider 
•	revisão manual 
•	marcação de documento como “exige conferência” 
________________________________________
7. Fluxo E2E 04 — Planejamento operacional
7.1 Objetivo
Gerar a sequência de trabalho do processo.
7.2 Fluxo
Diagnóstico concluído
-> job do Agente Regulatório
-> consulta RAG regulatório e precedentes
-> fundamentos e checklist são gerados
-> job do Agente Orquestrador
-> IA sugere plano de execução
-> tarefas são propostas
-> consultor aprova/edita
-> tarefas são criadas
-> processo muda para planejamento ou execucao
7.3 Saídas
•	checklist regulatório 
•	tarefas 
•	dependências 
•	responsáveis sugeridos 
•	prazos estimados 
•	riscos identificados 
7.4 Regras
•	IA sugere, humano aprova 
•	tarefas geradas por IA devem ser marcadas 
•	dependências devem ser respeitadas 
•	alteração do plano fica auditada 
7.5 Exceções
•	base regulatória insuficiente 
•	processo atípico 
•	conflito entre norma e precedente 
•	ausência de imóvel/geometria 
________________________________________
8. Fluxo E2E 05 — Execução interna
8.1 Objetivo
Executar as tarefas operacionais do processo.
8.2 Fluxo
Tarefas criadas
-> equipe executa no painel
-> documentos são anexados
-> comentários e evidências são registrados
-> subtarefas podem ser criadas
-> tarefa vai para revisão ou conclusão
-> processo avança conforme marcos
8.3 Regras
•	tarefa com dependência não conclui antes da anterior 
•	comentário interno não aparece ao cliente 
•	anexos entram vinculados ao processo/tarefa 
•	tarefas vencidas geram alerta 
8.4 Saídas
•	documentação consolidada 
•	marcos cumpridos 
•	pendências identificadas 
•	processo pronto para protocolo ou campo 
________________________________________
9. Fluxo E2E 06 — Execução de campo offline
9.1 Objetivo
Permitir coleta de dados e evidências em ambiente sem internet.
9.2 Fluxo
Gestor/consultor agenda visita
-> visita é atribuída ao técnico
-> app mobile baixa contexto da visita
-> técnico vai a campo
-> registra fotos, áudios, GPS, notas, checklist
-> tudo é salvo localmente em SQLite
-> itens entram na sync_queue
-> quando há conexão, app sincroniza
-> backend grava evidências
-> arquivos sobem ao storage
-> processo é atualizado
9.3 Regras
•	tudo nasce local 
•	sem rede não bloqueia operação 
•	evidência é append-only 
•	mídia sobe separada do metadado 
•	conflitos não apagam dados 
9.4 Saídas
•	evidências de campo vinculadas ao processo 
•	formulários preenchidos 
•	pontos geográficos 
•	conclusão ou pendência de visita 
9.5 Exceções
•	falha de sync 
•	mídia pesada 
•	perda de sinal prolongada 
•	conflito com atualização no servidor 
9.6 Fallback
•	retry automático 
•	resolução de conflito 
•	alerta ao gestor se visita ficar muito tempo sem sync 
________________________________________
10. Fluxo E2E 07 — Protocolo / envio ao órgão
10.1 Objetivo
Submeter documentação e registrar protocolo externo.
10.2 Fluxo oficial
Processo pronto para protocolo
-> sistema verifica rota disponível

1. API privada / broker
   -> consulta ou envia via provider
   -> retorna protocolo
   -> processo vai para aguardando_orgao

2. certificado A1
   -> credencial segura é usada
   -> operação autenticada é executada
   -> retorno é persistido
   -> processo vai para aguardando_orgao

3. fallback manual
   -> sistema cria tarefa para operador
   -> operador protocola externamente
   -> anexa comprovante
   -> protocolo externo é registrado
   -> processo vai para aguardando_orgao
10.3 Regras
•	ordem de tentativa: broker -> A1 -> manual 
•	comprovante sempre deve ficar anexado 
•	protocolo externo precisa de rastreabilidade 
•	decisão de fallback deve ser auditada 
10.4 Saídas
•	número de protocolo 
•	comprovante 
•	data/hora 
•	canal utilizado 
•	status aguardando_orgao 
________________________________________
11. Fluxo E2E 08 — Retorno do órgão / pendência
11.1 Objetivo
Tratar resposta de órgão, exigências e novas etapas.
11.2 Fluxo
Órgão responde
-> entrada por e-mail, broker ou upload manual
-> sistema classifica retorno
-> Agente Vigia ou Atendente identifica pendência
-> thread/documento é vinculada ao processo
-> se houver exigência:
   -> processo vai para pendencia_orgao
   -> tarefas corretivas são criadas
-> se aprovado:
   -> processo vai para concluido
11.3 Regras
•	resposta externa nunca deve ficar solta 
•	precisa vincular ao processo 
•	pendência gera tarefa 
•	aprovação gera marco final 
11.4 Exceções
•	e-mail não identificado 
•	protocolo sem processo correlato 
•	anexo ilegível 
•	retorno ambíguo 
________________________________________
12. Fluxo E2E 09 — Comunicação com cliente
12.1 Objetivo
Manter transparência e reduzir pressão operacional.
12.2 Canais
•	portal do cliente 
•	WhatsApp 
•	e-mail 
12.3 Fluxo
Evento relevante ocorre
-> sistema decide visibilidade
-> timeline do portal é atualizada
-> se configurado, mensagem é enviada
-> cliente visualiza status/documentos
-> cliente pode responder ou anexar documentos
-> nova mensagem entra em thread
-> consultor ou IA trata continuidade
12.4 Regras
•	cliente só vê o que foi liberado 
•	notas internas nunca aparecem 
•	documentos internos não aparecem 
•	evento visível deve ser simples e compreensível 
12.5 Saídas
•	status atualizado 
•	mensagem enviada 
•	anexo recebido 
•	pressão operacional reduzida 
________________________________________
13. Fluxo E2E 10 — Proposta comercial
13.1 Objetivo
Gerar proposta comercial estruturada.
13.2 Fluxo
Lead qualificado ou processo inicial
-> consultor monta proposta manualmente ou com IA
-> Agente Redator pode gerar minuta
-> proposta é revisada
-> proposta é enviada ao cliente
-> cliente aceita, rejeita ou expira
13.3 Regras
•	proposta pode nascer antes ou depois do processo 
•	itens devem ser rastreáveis 
•	valores e condições precisam de versão 
•	aceite deve ficar registrado 
________________________________________
14. Fluxo E2E 11 — Contrato e assinatura
14.1 Objetivo
Formalizar contratação.
14.2 Fluxo
Proposta aceita
-> contrato é gerado
-> contrato é revisado
-> provider de assinatura é acionado
-> cliente assina
-> webhook retorna status
-> contrato assinado é salvo
-> processo ou faturamento é liberado
14.3 Regras
•	contrato assinado é documento versionado 
•	webhook de assinatura precisa ser idempotente 
•	falha na assinatura gera alerta/tarefa 
________________________________________
15. Fluxo E2E 12 — Faturamento e custos variáveis
15.1 Objetivo
Registrar cobrança e custos do processo.
15.2 Fluxo
Contrato ou marco operacional permite cobrança
-> cobrança é gerada
-> gateway do tenant ou da plataforma é acionado
-> pagamento retorna status
-> sistema atualiza processo financeiro
-> custos de IA/broker/assinatura podem ser lançados
15.3 Regras
•	tenant white-label pode usar seu próprio gateway 
•	custos variáveis precisam ser auditáveis 
•	uso de IA por tenant precisa ser visível 
________________________________________
16. Fluxo E2E 13 — Encerramento e arquivamento
16.1 Objetivo
Finalizar o processo mantendo trilha íntegra.
16.2 Fluxo
Processo concluído
-> documentos finais consolidados
-> cliente notificado
-> pendências internas verificadas
-> processo muda para concluido
-> após regra de retenção/encerramento, vai para arquivado
16.3 Regras
•	processo concluído precisa de histórico íntegro 
•	documentos finais devem estar organizados 
•	arquivamento não apaga rastreabilidade 
________________________________________
17. Fluxos de fallback
17.1 Fallback de IA
Provider primário falha
-> tenta provider secundário
-> se falhar, cria revisão/tarefa humana
17.2 Fallback de integração governamental
Broker indisponível
-> tenta A1
-> se falhar, cria tarefa manual
17.3 Fallback de OCR
OCR ruim
-> tenta reprocessamento
-> baixa confiança -> revisão humana
17.4 Fallback de sync mobile
Sync falha
-> retry
-> conflito -> fila de resolução
-> alerta se persistir
________________________________________
18. Pontos obrigatórios de auditoria
Devem ser auditados:
•	criação e mudança de processo 
•	criação e conclusão de tarefa 
•	upload e validação de documento 
•	execução de job de IA 
•	troca de provider / fallback 
•	protocolo externo 
•	uso de certificado A1 
•	resolução de conflito mobile 
•	assinatura de contrato 
•	alteração de integração 
•	alteração de política de IA por tenant 
________________________________________
19. Fluxo futuro GovTech
19.1 O que já está preparado
A arquitetura atual já sustenta evolução para GovTech porque:
•	há trilha de auditoria 
•	há controle de estado 
•	há evidência vinculada ao processo 
•	há integração governamental em camadas 
•	há separação de schemas e serviços 
19.2 O que o fluxo GovTech exigirá depois
•	analista público como ator 
•	supervisor público 
•	fila institucional de análise 
•	parecer oficial 
•	cadeia de custódia de evidência 
•	assinatura forte e carimbo temporal 
•	trilha legal de decisão humano + IA 
•	relatórios oficiais/exportações regulatórias 
19.3 Conclusão
Sim, o projeto já contempla a evolução para GovTech em nível estrutural.
Não, o módulo GovTech ainda não está documentado em profundidade funcional.
________________________________________
20. Resumo executivo
Hoje o projeto já cobre bem:
•	entrada omnichannel 
•	triagem 
•	processo 
•	diagnóstico com OCR + IA 
•	planejamento com agentes 
•	execução interna 
•	campo offline 
•	portal do cliente 
•	integração governamental com fallback 
•	comercial 
•	multi-provider de IA 
•	white-label por tenant
