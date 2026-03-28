Documento de Integrações GovTech
Projeto: Plataforma Ambiental SaaS (App Ambiental)
Versão: 1.0
________________________________________
1. Objetivo
Definir:
•	como o sistema integra com órgãos governamentais 
•	estratégias por tipo de integração 
•	fallback obrigatório 
•	arquitetura de adapters 
•	confiabilidade e SLA 
•	preparo para evolução GovTech 
________________________________________
2. Princípios fundamentais
2.1 Integração governamental é inerentemente instável
•	APIs mudam 
•	endpoints caem 
•	autenticação quebra 
•	documentação é incompleta 
👉 Portanto:
fallback sempre obrigatório
________________________________________
2.2 Nunca depender de um único canal
Toda integração deve ter:
API → Certificado → Manual
________________________________________
2.3 Sistema deve continuar funcionando sem integração
•	integração acelera 
•	não pode bloquear operação 
________________________________________
2.4 Tudo deve ser auditável
•	envio 
•	resposta 
•	falha 
•	fallback 
________________________________________
3. Tipos de integração GovTech
________________________________________
3.1 Tipo A — APIs privadas (Brokers)
Exemplo
•	APIs que já agregam dados governamentais 
•	provedores privados de CAR, mapas, dados ambientais 
Características
•	mais estáveis 
•	pagas 
•	SLA melhor 
•	suporte técnico 
Uso
👉 PRIMEIRA OPÇÃO sempre que possível
________________________________________
3.2 Tipo B — Integração direta com órgão (API oficial)
Exemplo
•	SICAR 
•	sistemas estaduais 
Características
•	instáveis 
•	pouco documentadas 
•	mudanças frequentes 
Uso
👉 apenas quando necessário
________________________________________
3.3 Tipo C — Certificado digital (A1)
Exemplo
•	login via certificado 
•	automação de envio 
Características
•	complexo 
•	sensível 
•	alto risco operacional 
Uso
👉 fallback estruturado
________________________________________
3.4 Tipo D — Manual assistido
Características
•	operador humano executa 
•	sistema registra e organiza 
Uso
👉 fallback final obrigatório
________________________________________
4. Arquitetura de Integrações
________________________________________
4.1 Camada de integração (Integration Gateway)
Core API
   -> Integration Gateway
        -> Broker Adapter
        -> Gov API Adapter
        -> Certificado Adapter
        -> Manual Handler
________________________________________
4.2 Responsabilidades
•	padronizar chamadas 
•	aplicar retry 
•	aplicar fallback 
•	registrar logs 
•	medir latência 
•	tratar erro 
________________________________________
4.3 Contrato interno
{
  "integration_type": "gov_protocol",
  "entity_id": "process_id",
  "payload": {},
  "strategy": "auto",
  "fallback_enabled": true
}
________________________________________
5. Fluxo padrão de integração
________________________________________
5.1 Envio para órgão
1. tentar broker
2. se falhar → tentar API oficial
3. se falhar → tentar certificado A1
4. se falhar → criar tarefa manual
________________________________________
5.2 Consulta de status
1. tentar broker
2. tentar API oficial
3. fallback manual (upload de retorno)
________________________________________
5.3 Recebimento de resposta
entrada por:
- webhook
- e-mail
- upload manual

-> classificar
-> vincular ao processo
-> atualizar estado
________________________________________
6. Integrações específicas (escopo inicial)
________________________________________
6.1 SICAR
Funções
•	consulta de CAR 
•	envio/retificação 
Estratégia
1. broker (preferencial)
2. certificado A1
3. manual
Riscos
•	instabilidade 
•	bloqueios 
•	autenticação 
________________________________________
6.2 MapBiomas
Funções
•	consulta de uso do solo 
•	validação ambiental 
Estratégia
API direta ou provider
Observação
•	não é transacional 
•	sem necessidade de fallback manual 
________________________________________
6.3 Órgãos estaduais
Exemplos
•	SEMAD 
•	órgãos ambientais locais 
Estratégia
1. API (se existir)
2. certificado
3. manual
________________________________________
6.4 IBAMA (futuro)
Funções
•	processos federais 
Estratégia
•	provavelmente híbrida 
•	alto nível de complexidade 
________________________________________
7. Adapter Pattern (obrigatório)
Cada integração deve seguir padrão:
adapter/
  sicar/
    broker_adapter.py
    api_adapter.py
    certificate_adapter.py
  mapbiomas/
  estadual/
________________________________________
Interface padrão
class GovIntegrationAdapter:
    def send(self, payload): ...
    def status(self, external_id): ...
    def health_check(self): ...
________________________________________
8. Retry e fallback
________________________________________
8.1 Retry policy
•	retry exponencial 
•	limite de tentativas 
•	timeout controlado 
________________________________________
8.2 Fallback automático
falha → próximo método
________________________________________
8.3 Fallback manual
•	criar tarefa automática 
•	atribuir responsável 
•	registrar motivo 
________________________________________
9. Monitoramento e SLA
________________________________________
9.1 Métricas obrigatórias
•	taxa de sucesso por integração 
•	tempo de resposta 
•	taxa de fallback 
•	falhas por tipo 
________________________________________
9.2 Health check
Cada integração deve expor:
status: ok | degraded | down
________________________________________
9.3 Alertas
•	falha contínua 
•	aumento de fallback 
•	tempo de resposta alto 
________________________________________
10. Segurança nas integrações
________________________________________
10.1 Credenciais
•	armazenadas via secret manager 
•	nunca no banco em texto puro 
________________________________________
10.2 Certificado A1
•	criptografado 
•	acesso restrito 
•	auditado 
________________________________________
10.3 Logs
•	não expor credenciais 
•	mascarar dados sensíveis 
________________________________________
11. Auditoria
________________________________________
Registrar:
•	tentativa de integração 
•	método usado 
•	resultado 
•	fallback aplicado 
•	usuário/processo 
•	timestamp 
________________________________________
12. Custos
________________________________________
12.1 Tipos
•	broker (pago) 
•	API (eventual custo) 
•	certificado (operacional) 
•	manual (custo humano) 
________________________________________
12.2 Estratégia
•	usar broker quando custo compensa 
•	medir custo por processo 
•	permitir configuração por tenant 
________________________________________
13. Configuração por tenant
________________________________________
Exemplo
{
  "gov_policy": {
    "prefer_broker": true,
    "allow_certificate": true,
    "allow_manual": true
  }
}
________________________________________
14. Riscos e mitigação
________________________________________
API cair
✔ fallback
________________________________________
mudança de endpoint
✔ adapter isolado
________________________________________
bloqueio por órgão
✔ certificado/manual
________________________________________
erro humano
✔ auditoria
________________________________________
custo alto
✔ controle por tenant
________________________________________
15. Preparação para GovTech
________________________________________
Já atendido
•	arquitetura modular 
•	fallback 
•	auditoria 
•	rastreabilidade 
________________________________________
Fase futura (GovTech real)
•	integração bidirecional 
•	fila institucional 
•	dashboards governamentais 
•	APIs públicas 
•	validação oficial 
________________________________________
16. Conclusão
Esse modelo garante:
•	resiliência real 
•	independência de canais 
•	operação contínua 
•	escalabilidade 
•	base sólida para GovTech
