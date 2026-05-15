Governança de IA + Prompts + Política de Custo por Tenant
Projeto: Plataforma Ambiental SaaS (App Ambiental)
Versão: 1.0
________________________________________
1. Objetivo
Definir:
•	como a IA é usada no sistema 
•	como prompts são controlados e versionados 
•	como múltiplos providers são gerenciados 
•	como custo é controlado por tenant 
•	quando IA pode agir automaticamente 
•	quando exige revisão humana 
________________________________________
2. Princípios de Governança de IA
2.1 IA é um componente controlado, não livre
•	nenhuma chamada de IA acontece fora do AI Gateway 
•	nenhum serviço chama provider diretamente 
________________________________________
2.2 Toda chamada de IA é auditada
Registrar:
•	tenant 
•	agente 
•	prompt_version 
•	provider 
•	modelo 
•	tokens 
•	custo 
•	latência 
•	fallback 
________________________________________
2.3 IA é orientada por capability, não vendor
•	escolha por: 
o	structured_output 
o	visão 
o	contexto longo 
o	custo 
o	latência 
________________________________________
2.4 IA nunca altera estado crítico automaticamente
Exemplo:
•	mudar status de processo ❌ 
•	aprovar documento ❌ 
IA pode:
•	sugerir 
•	estruturar 
•	classificar 
________________________________________
2.5 IA é sempre substituível
•	arquitetura multi-provider obrigatória 
•	fallback obrigatório 
________________________________________
3. Arquitetura de IA
3.1 Componentes
Worker AI
   -> AI Gateway / Model Router
        -> Provider Adapter (OpenAI)
        -> Provider Adapter (Gemini)
        -> Provider Adapter (Claude)
________________________________________
3.2 Responsabilidades do AI Gateway
•	roteamento por capability 
•	fallback automático 
•	controle de custo 
•	normalização de resposta 
•	versionamento de prompt 
•	auditoria completa 
________________________________________
4. Estrutura de Prompts
4.1 Cada prompt deve ser tratado como um artefato versionado
Campos obrigatórios:
{
  "id": "extrator_documento_v1",
  "agent": "extrator",
  "version": "1.0.0",
  "description": "Extração de matrícula rural",
  "input_schema": {},
  "output_schema": {},
  "prompt_template": "...",
  "examples": [],
  "temperature": 0.2,
  "max_tokens": 2000,
  "allowed_providers": ["openai", "gemini"],
  "fallback_providers": ["openai"],
  "review_required": true
}
________________________________________
4.2 Tipos de prompt no sistema
1. Classificação (Atendente, Vigia)
•	saída estruturada 
•	baixo custo 
•	alta frequência 
________________________________________
2. Extração (Extrator)
•	JSON obrigatório 
•	pode usar visão 
•	validação crítica 
________________________________________
3. Raciocínio (Regulatório)
•	contexto longo 
•	RAG 
•	saída estruturada + texto 
________________________________________
4. Orquestração
•	tool calling 
•	plano de tarefas 
________________________________________
5. Redação
•	texto longo 
•	documentos formais 
________________________________________
4.3 Versionamento de prompts
•	versão semântica (1.0.0, 1.1.0…) 
•	não sobrescrever prompt antigo 
•	histórico obrigatório 
•	rollback possível 
________________________________________
4.4 Regras críticas
•	mudança de prompt → log obrigatório 
•	mudança pode impactar produção → flag de rollout 
•	prompt pode ser: 
o	ativo 
o	experimental 
o	desativado 
________________________________________
5. Política de uso por agente
________________________________________
5.1 Agente Atendente
•	classificação de mensagens 
•	criação de lead/processo 
Regras
•	sempre structured_output 
•	baixa latência 
•	custo baixo 
________________________________________
5.2 Agente Extrator
•	extração documental 
Regras
•	OCR antes 
•	JSON obrigatório 
•	score de confiança obrigatório 
•	revisão se baixa confiança 
________________________________________
5.3 Agente Regulatório
•	análise normativa 
Regras
•	RAG obrigatório 
•	contexto longo 
•	saída auditável 
________________________________________
5.4 Agente Orquestrador
•	geração de tarefas 
Regras
•	saída estruturada 
•	não cria tarefa automaticamente sem validação 
________________________________________
5.5 Agente Redator
•	documentos técnicos/comerciais 
Regras
•	pode gerar rascunho 
•	humano sempre valida antes de envio 
________________________________________
5.6 Agente Vigia
•	monitoramento de eventos 
Regras
•	custo mínimo 
•	modelo rápido 
•	alta frequência 
________________________________________
6. Política de Custo por Tenant
________________________________________
6.1 Princípio
Cada tenant pode operar em dois modos:
1. Plataforma paga IA
•	custo centralizado 
•	margem embutida 
2. White-label (recomendado)
•	tenant usa suas próprias APIs 
•	custo direto dele 
________________________________________
6.2 Configuração por tenant
{
  "ai_policy": {
    "mode": "white_label",
    "providers": {
      "openai": { "enabled": true },
      "gemini": { "enabled": true },
      "anthropic": { "enabled": false }
    },
    "budget_limits": {
      "daily_usd": 50,
      "monthly_usd": 1000
    },
    "fallback_enabled": true
  }
}
________________________________________
6.3 Controle de custo
Níveis
Hard limit
•	bloqueia novas chamadas 
Soft limit
•	alerta, mas continua 
________________________________________
6.4 Estratégias automáticas
Quando custo sobe:
•	trocar modelo premium → modelo mais barato 
•	reduzir contexto 
•	reduzir temperatura 
•	reduzir frequência de chamadas 
________________________________________
6.5 Ações quando limite excedido
1. tentar modelo mais barato
2. tentar outro provider
3. degradar funcionalidade (ex: sem IA)
4. exigir ação humana
________________________________________
7. Política de Roteamento (Multi-provider)
________________________________________
7.1 Baseado em capability
Capability	Provider preferido
JSON rígido	OpenAI
multimodal	Gemini
contexto longo	Gemini / Claude
redação longa	Claude
baixo custo	modelos rápidos
________________________________________
7.2 Exemplo
{
  "requirements": {
    "structured_output": true,
    "vision": true
  }
}
→ Gateway decide provider automaticamente
________________________________________
7.3 Fallback
provider A falha
-> tenta provider B
-> tenta provider C
-> cria tarefa humana
________________________________________
8. Controle de Qualidade da IA
________________________________________
8.1 Score de confiança
Obrigatório para:
•	extração documental 
•	classificação crítica 
________________________________________
8.2 Revisão humana obrigatória
Quando:
•	score baixo 
•	documento legal 
•	impacto regulatório 
•	envio externo 
________________________________________
8.3 Avaliação contínua
Registrar:
•	taxa de erro por prompt 
•	taxa de revisão 
•	tempo de resposta 
•	custo por fluxo 
________________________________________
9. Observabilidade de IA
________________________________________
9.1 Métricas obrigatórias
•	chamadas por tenant 
•	custo por tenant 
•	custo por agente 
•	custo por provider 
•	latência 
•	taxa de fallback 
•	taxa de erro 
________________________________________
9.2 Logs
Cada chamada deve registrar:
{
  "tenant_id": "...",
  "agent": "extrator",
  "provider": "gemini",
  "model": "gemini-2.5-pro",
  "prompt_version": "1.0.2",
  "input_tokens": 1200,
  "output_tokens": 300,
  "cost": 0.02,
  "latency_ms": 2100,
  "fallback_used": false
}
________________________________________
10. Segurança
________________________________________
10.1 Dados enviados à IA
•	nunca enviar: 
o	credenciais 
o	tokens 
o	dados sensíveis não necessários 
________________________________________
10.2 Isolamento por tenant
•	prompts não misturam dados de tenants 
•	logs segregados 
________________________________________
10.3 Auditoria
•	toda chamada rastreável 
•	histórico imutável 
________________________________________
11. Riscos e Mitigações
________________________________________
Risco: custo explodir
✔ limite + fallback + modelos baratos
________________________________________
Risco: resposta errada
✔ score + revisão humana
________________________________________
Risco: vendor cair
✔ multi-provider
________________________________________
Risco: comportamento inconsistente
✔ versionamento de prompt
________________________________________
Risco: vazamento de dados
✔ controle de payload
________________________________________
12. Relação com GovTech
Esse documento já prepara o sistema para:
•	trilha auditável de IA 
•	decisão humano + IA 
•	rastreabilidade legal 
•	substituição de modelos 
•	controle institucional 
Para GovTech futuro será necessário adicionar:
•	certificação de modelo 
•	validação formal de outputs 
•	logs imutáveis 
•	explicabilidade de decisões 
________________________________________
13. Conclusão
Com essa governança, o sistema:
•	evita dependência de vendor 
•	controla custo de forma real 
•	mantém qualidade operacional 
•	garante auditabilidade 
•	permite escala 
•	viabiliza white-label 
•	prepara para GovTech
