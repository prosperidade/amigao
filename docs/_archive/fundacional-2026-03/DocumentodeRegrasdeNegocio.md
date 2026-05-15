Documento de Regras de Negócio + Máquina de Estados
________________________________________
1. Princípios gerais
1.1 Fonte de verdade
•	Processo é a entidade central do sistema 
•	tudo gira em torno dele: 
o	tarefas 
o	documentos 
o	comunicação 
o	IA 
o	evidências de campo 
________________________________________
1.2 Estados são obrigatórios
Toda entidade crítica deve ter:
•	estado definido 
•	transições válidas 
•	histórico 
________________________________________
1.3 Nada crítico é sobrescrito
•	tudo é versionado ou append-only 
•	especialmente: 
o	documentos 
o	evidências 
o	decisões 
o	dados de campo 
________________________________________
1.4 IA nunca decide sozinha
•	IA sugere 
•	humano valida quando necessário 
•	sistema registra tudo 
________________________________________
2. Máquina de estados — PROCESSO
2.1 Estados do processo
lead
triagem
diagnostico
planejamento
execucao
protocolo
aguardando_orgao
pendencia_orgao
concluido
arquivado
cancelado
________________________________________
2.2 Descrição dos estados
LEAD
•	origem: WhatsApp, e-mail, manual 
•	ainda não estruturado 
•	sem garantia de continuidade 
________________________________________
TRIAGEM
•	dados mínimos coletados 
•	classificado tipo de demanda 
•	pode virar processo real ou não 
________________________________________
DIAGNOSTICO
•	análise documental inicial 
•	entrada de IA (extrator + regulatório) 
•	identificação de problemas 
________________________________________
PLANEJAMENTO
•	criação de tarefas 
•	definição de estratégia 
•	orquestrador pode atuar aqui 
________________________________________
EXECUCAO
•	tarefas sendo executadas 
•	coleta de documentos 
•	campo ativo 
________________________________________
PROTOCOLO
•	envio para órgão 
•	registro de protocolo externo 
________________________________________
AGUARDANDO_ORGAO
•	esperando retorno 
•	sem ação interna 
________________________________________
PENDENCIA_ORGAO
•	órgão pediu correção 
•	volta para execução 
________________________________________
CONCLUIDO
•	processo finalizado com sucesso 
________________________________________
ARQUIVADO
•	encerrado sem necessidade de ação 
________________________________________
CANCELADO
•	interrompido 
________________________________________
2.3 Transições válidas
lead -> triagem

triagem -> diagnostico
triagem -> cancelado

diagnostico -> planejamento
diagnostico -> cancelado

planejamento -> execucao

execucao -> protocolo
execucao -> cancelado

protocolo -> aguardando_orgao

aguardando_orgao -> pendencia_orgao
aguardando_orgao -> concluido

pendencia_orgao -> execucao

concluido -> arquivado
cancelado -> arquivado
________________________________________
2.4 Regras importantes
•	não pode pular etapas sem log 
•	toda mudança gera evento 
•	toda mudança gera audit log 
•	pode exigir permissão (RBAC) 
________________________________________
3. Máquina de estados — TAREFAS
3.1 Estados
backlog
a_fazer
em_progresso
aguardando
revisao
concluida
cancelada
________________________________________
3.2 Transições
backlog -> a_fazer
a_fazer -> em_progresso
em_progresso -> aguardando
em_progresso -> revisao
revisao -> concluida
aguardando -> em_progresso
qualquer -> cancelada
________________________________________
3.3 Regras
•	tarefa com dependência não pode concluir 
•	tarefa pode ser criada por: 
o	humano 
o	IA (marcar origem_ia = true) 
•	tarefa concluída gera evento 
•	tarefa vencida gera alerta 
________________________________________
4. Máquina de estados — DOCUMENTOS
4.1 Estados
uploaded
processing
processed
review_required
validated
rejected
archived
________________________________________
4.2 Fluxo
uploaded -> processing
processing -> processed
processed -> review_required
review_required -> validated
review_required -> rejected
validated -> archived
________________________________________
4.3 Regras
•	OCR sempre antes da IA 
•	score de confiança decide revisão 
•	documento validado não pode ser alterado 
•	nova versão cria novo registro 
________________________________________
5. Máquina de estados — JOBS DE IA
5.1 Estados
queued
processing
done
failed
timeout
cancelled
________________________________________
5.2 Regras
•	job nunca bloqueia usuário 
•	job sempre auditado 
•	pode ter retry 
•	pode ter fallback provider 
________________________________________
6. Máquina de estados — SINCRONIZAÇÃO MOBILE
6.1 Estados locais
draft
pending_sync
syncing
synced
failed
conflict
________________________________________
6.2 Regras
•	nada depende de internet 
•	tudo primeiro local 
•	sync idempotente 
•	conflito nunca apaga dado 
________________________________________
7. Regras de negócio principais
________________________________________
7.1 Criação de processo
Pode vir de:
•	IA (atendente) 
•	usuário 
•	importação 
Regras:
•	sempre precisa de cliente 
•	imóvel pode ser opcional inicialmente 
•	tipo de processo obrigatório 
________________________________________
7.2 Criação automática de tarefas
Pode ocorrer em:
•	diagnóstico concluído 
•	planejamento iniciado 
•	pendência do órgão 
Origem:
•	IA (orquestrador) 
•	template padrão 
•	usuário 
________________________________________
7.3 Revisão obrigatória
Deve existir quando:
•	OCR com baixa confiança 
•	IA gerou dados críticos 
•	documento legal envolvido 
•	envio para órgão 
________________________________________
7.4 Visibilidade do cliente
Cliente vê:
•	status do processo 
•	documentos liberados 
•	timeline resumida 
Cliente NÃO vê:
•	notas internas 
•	tarefas internas 
•	erros 
•	dados sensíveis 
________________________________________
7.5 Integrações governamentais
Ordem de tentativa:
1. API privada (broker)
2. certificado A1
3. fallback manual
________________________________________
7.6 Cobrança
•	pode nascer da proposta 
•	pode ser manual 
•	pode depender do avanço do processo 
________________________________________
7.7 Uso de IA
•	sempre registrado 
•	sempre com custo associado 
•	pode ser limitado por tenant 
________________________________________
8. Eventos do sistema (fundamental)
Eventos principais
process.created
process.status.changed
task.created
task.completed
document.uploaded
document.validated
ai.job.created
ai.job.completed
sync.completed
integration.failed
deadline.alert
________________________________________
9. Permissões (RBAC simplificado)
Perfis
•	admin 
•	consultor 
•	tecnico_campo 
•	parceiro 
•	cliente_final 
________________________________________
Exemplos
Técnico de campo
•	pode criar evidência 
•	não pode alterar processo 
•	não vê financeiro 
Parceiro
•	vê tarefas atribuídas 
•	não vê tudo do cliente 
Cliente final
•	só leitura do próprio processo 
________________________________________
10. Regras críticas (não podem falhar)
10.1 Integridade do processo
•	sempre tem cliente 
•	sempre tem histórico 
10.2 Evidência de campo
•	nunca sobrescrever 
•	sempre append 
10.3 Auditoria
•	tudo importante registrado 
10.4 IA
•	nunca invisível 
•	sempre rastreável 
10.5 Offline
•	nunca perde dado 
•	sync sempre recuperável 
________________________________________
11. Situações especiais (edge cases)
11.1 Documento ruim
•	OCR falha → revisão manual 
11.2 IA falha
•	fallback provider 
•	fallback humano 
11.3 Integração falha
•	cria tarefa manual 
11.4 Sync falha
•	retry automático 
•	alerta depois 
________________________________________
12. Impacto no sistema
Esse documento afeta diretamente:
•	backend (validação de estados) 
•	frontend (fluxos) 
•	mobile (sync) 
•	IA (gatilhos) 
•	integrações 
•	auditoria
