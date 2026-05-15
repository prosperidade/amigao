Especificação da API v1 — revisão multi-provider
1. Princípio arquitetural
A API v1 não expõe vendors de IA como dependência estrutural do domínio.
O core do sistema fala com uma camada interna chamada AI Gateway / Model Router, e essa camada decide qual provider e qual modelo usar para cada tarefa, com base em:
•	tipo de fluxo 
•	necessidade de visão 
•	necessidade de saída estruturada 
•	janela de contexto 
•	tool calling 
•	latência 
•	custo 
•	política do tenant 
•	fallback disponível 
Isso está alinhado com o desenho original de microsserviço Python isolado para IA e com a necessidade de manter o core transacional limpo e previsível. 
________________________________________
2. Novo componente lógico obrigatório
2.1 AI Gateway / Model Router
API Core -> fila -> Worker AI -> AI Gateway
                               -> OpenAI Adapter
                               -> Gemini Adapter
                               -> Claude Adapter
                               -> futuros adapters
2.2 Responsabilidades do AI Gateway
•	normalizar contratos de entrada e saída 
•	rotear por capability, não por vendor fixo 
•	aplicar política de custo 
•	aplicar fallback 
•	registrar auditoria por chamada 
•	medir tokens, latência e erro por provider 
•	suportar multimodalidade 
•	suportar tool/function calling 
•	suportar saída JSON estruturada 
•	respeitar política por tenant 
________________________________________
3. Modelo conceitual da IA dentro da API
A tabela de jobs já existe no modelo e deve continuar sendo a unidade rastreável de execução, com tenant_id, agente, entidade, status, payload e custo. 
A diferença agora é que cada job passa a registrar também:
•	provider_strategy 
•	provider_selected 
•	model_selected 
•	fallback_used 
•	capabilities_required 
•	capabilities_used 
________________________________________
4. Registry interno de capabilities
A plataforma não deve decidir “use OpenAI” ou “use Gemini” hardcoded no fluxo.
Ela deve decidir por capacidade.
4.1 Capabilities mínimas
•	text_generation 
•	structured_output 
•	tool_calling 
•	vision 
•	pdf_understanding 
•	long_context 
•	prompt_caching 
•	low_latency 
•	cost_efficient 
•	high_reasoning 
•	grounded_search 
•	file_context 
4.2 Exemplo de registro interno
{
  "provider": "anthropic",
  "model": "claude-sonnet",
  "capabilities": {
    "text_generation": true,
    "structured_output": true,
    "tool_calling": true,
    "vision": true,
    "long_context": true,
    "prompt_caching": true,
    "low_latency": false,
    "cost_efficient": false
  },
  "status": "active"
}
________________________________________
5. Política recomendada por provider
5.1 OpenAI
Preferir quando o fluxo exigir:
•	JSON Schema rígido 
•	tool/function calling forte 
•	saídas estruturadas para automação 
•	orquestração de tarefas 
•	respostas programaticamente confiáveis 
Isso faz sentido porque a OpenAI documenta Responses API, function calling e Structured Outputs com aderência a JSON Schema. 
5.2 Gemini
Preferir quando o fluxo exigir:
•	multimodalidade pesada 
•	leitura de documentos grandes 
•	contexto longo 
•	PDFs e lotes documentais 
•	grounding/search/file context 
Isso faz sentido porque a documentação oficial do Gemini destaca contexto longo, multimodalidade, function calling e structured outputs.
5.3 Claude
Preferir quando o fluxo exigir:
•	redação longa 
•	revisão técnica 
•	síntese extensa 
•	tool use 
•	prompt caching em fluxos repetitivos 
•	contexto longo com boa qualidade de escrita 
Isso faz sentido porque a Anthropic documenta tool use, JSON mode, prompt caching e contexto longo nas docs do Claude. 
________________________________________
6. Matriz recomendada por agente
A base funcional dos agentes permanece a mesma do documento: atendente, extrator, regulatório, orquestrador, redator e vigia. 
6.1 Agente Atendente
Primário:
•	OpenAI ou Claude 
Secundário:
•	Gemini 
Melhor uso:
•	classificação de intake 
•	extração de intenção 
•	geração de resumo estruturado 
•	tool calling para criar lead/processo 
6.2 Agente Extrator
Primário:
•	Gemini 
Secundário:
•	OpenAI 
Fallback humano:
•	revisão documental 
Motivo:
•	o projeto já assume OCR clássico antes do LLM 
•	depois disso, documentos multimodais e longos encaixam melhor em Gemini, enquanto OpenAI pode entrar quando o foco for estrutura JSON rígida. 
6.3 Agente Regulatório
Primário:
•	Gemini ou Claude 
Secundário:
•	OpenAI 
Motivo:
•	base regulatória longa + RAG sobre pgvector já está prevista no projeto 
•	Gemini e Claude ajudam em contexto longo; OpenAI entra quando a saída precisa virar checklist ou JSON operacional. 
6.4 Agente Orquestrador
Primário:
•	OpenAI 
Secundário:
•	Claude 
Motivo:
•	o documento já prevê criação automática de tarefas, prazos e dependências 
•	esse é um fluxo onde structured output e tool calling são centrais. 
6.5 Agente Redator
Primário:
•	Claude 
Secundário:
•	OpenAI ou Gemini 
Motivo:
•	o documento já posiciona o redator como gerador de PRAD, memorial, ofício e resposta a pendência 
•	Claude tende a ser boa escolha para redação longa; OpenAI entra quando a estrutura formal for mais rígida; Gemini quando houver apoio multimodal/documental. 
6.6 Agente Vigia
Primário:
•	modelo rápido e barato do provider habilitado 
•	Gemini Flash / modelo rápido OpenAI / modelo econômico Claude 
Motivo:
•	esse fluxo é recorrente, de alto volume, classificação e alerta, então custo e latência pesam mais. O próprio documento já sugeria modelo rápido para vigia. 
________________________________________
7. Contrato interno padronizado
7.1 Request interno ao AI Gateway
{
  "task_type": "document_extraction",
  "tenant_id": "uuid",
  "entity_type": "document",
  "entity_id": "uuid",
  "agent": "extrator",
  "input": {
    "text": "...",
    "images": [],
    "pdf_refs": [
      "s3://bucket/tenant/.../doc.pdf"
    ],
    "metadata": {
      "document_type": "matricula",
      "municipality": "Rio Verde",
      "uf": "GO"
    }
  },
  "requirements": {
    "structured_output": true,
    "tool_calling": false,
    "vision": true,
    "pdf_understanding": true,
    "long_context": true,
    "low_latency": false,
    "max_cost_tier": "medium"
  },
  "routing": {
    "provider_strategy": "auto",
    "preferred_provider": "gemini",
    "fallback_provider": "openai",
    "allowed_providers": ["gemini", "openai", "anthropic"]
  }
}
7.2 Response normalizada
{
  "provider": "gemini",
  "model": "gemini-2.5-pro",
  "status": "success",
  "output_text": "....",
  "structured_output": {
    "owner_name": "José Pereira",
    "area_ha": 235.43
  },
  "tool_calls": [],
  "usage": {
    "input_tokens": 4312,
    "output_tokens": 682,
    "cached_tokens": 0,
    "estimated_cost_usd": 0.043
  },
  "latency_ms": 4820,
  "fallback_used": false
}
________________________________________
8. Mudanças obrigatórias na API v1
8.1 Padrão novo para recursos de IA
Onde antes a API aceitaria algo como:
{
  "provider": "openai"
}
agora deve aceitar:
{
  "provider_strategy": "auto",
  "preferred_provider": "gemini",
  "fallback_provider": "openai",
  "allowed_providers": ["gemini", "openai", "anthropic"],
  "requirements": {
    "structured_output": true,
    "tool_calling": false,
    "vision": true,
    "pdf_understanding": true,
    "long_context": true,
    "low_latency": false,
    "max_cost_tier": "medium"
  }
}
________________________________________
8.2 POST /ai/jobs
Cria job genérico de IA.
Request
{
  "agent": "extrator",
  "entity_type": "document",
  "entity_id": "uuid",
  "provider_strategy": "auto",
  "preferred_provider": "gemini",
  "fallback_provider": "openai",
  "allowed_providers": ["gemini", "openai", "anthropic"],
  "requirements": {
    "structured_output": true,
    "tool_calling": false,
    "vision": true,
    "pdf_understanding": true,
    "long_context": true,
    "low_latency": false,
    "max_cost_tier": "medium"
  }
}
Response 202
{
  "data": {
    "job_id": "uuid",
    "status": "queued"
  }
}
________________________________________
8.3 GET /ai/jobs/{id}
Response 200
{
  "data": {
    "id": "uuid",
    "agent": "extrator",
    "status": "processing",
    "entity_type": "document",
    "entity_id": "uuid",
    "provider_strategy": "auto",
    "provider_selected": "gemini",
    "fallback_used": false,
    "model_selected": "gemini-2.5-pro",
    "capabilities_required": [
      "vision",
      "pdf_understanding",
      "structured_output",
      "long_context"
    ],
    "capabilities_used": [
      "vision",
      "structured_output",
      "long_context"
    ],
    "usage": {
      "input_tokens": 4312,
      "output_tokens": 682,
      "estimated_cost_usd": 0.043
    },
    "latency_ms": 4820
  }
}
________________________________________
8.4 POST /ai/extractor/run
Executa extração documental com roteamento por capability.
Request
{
  "document_id": "uuid",
  "provider_strategy": "auto",
  "preferred_provider": "gemini",
  "fallback_provider": "openai",
  "requirements": {
    "vision": true,
    "pdf_understanding": true,
    "structured_output": true,
    "long_context": true
  }
}
Regra
O pipeline continua:
1.	OCR clássico 
2.	limpeza de texto 
3.	chamada ao provider selecionado 
4.	score de confiança 
5.	revisão humana se necessário 
Isso preserva o requisito técnico já documentado. 
________________________________________
8.5 POST /ai/orchestrator/plan
Request
{
  "process_id": "uuid",
  "provider_strategy": "auto",
  "preferred_provider": "openai",
  "fallback_provider": "anthropic",
  "requirements": {
    "structured_output": true,
    "tool_calling": true,
    "long_context": false,
    "low_latency": false
  }
}
Response esperada
•	plano de trabalho 
•	tarefas 
•	dependências 
•	prazos sugeridos 
•	responsáveis sugeridos 
Esse endpoint conversa diretamente com o papel do orquestrador no projeto. 
________________________________________
8.6 POST /ai/regulatory/query
Request
{
  "query": "Quais exigências para retificação de CAR em Goiás com APP e RL divergentes?",
  "context": {
    "uf": "GO",
    "municipality": "Rio Verde",
    "process_type": "car_retificacao"
  },
  "provider_strategy": "auto",
  "preferred_provider": "gemini",
  "fallback_provider": "anthropic",
  "requirements": {
    "long_context": true,
    "structured_output": true,
    "grounded_search": false
  }
}
Response esperada
•	fundamentação 
•	checklist 
•	normas relacionadas 
•	precedentes relevantes 
•	alertas de vigência 
Isso respeita a base RAG prevista em ai.normas e ai.norma_chunks. 
________________________________________
8.7 POST /ai/redactor/generate
Request
{
  "document_type": "prad",
  "process_id": "uuid",
  "template_id": "uuid",
  "provider_strategy": "auto",
  "preferred_provider": "anthropic",
  "fallback_provider": "openai",
  "requirements": {
    "text_generation": true,
    "structured_output": false,
    "long_context": true
  }
}
Response 202
Job assíncrono com artefato .docx ou .pdf no storage.
O redator continua alimentado por template + dados do banco + base regulatória, como já previsto. 
________________________________________
8.8 POST /ai/attendant/classify
Request
{
  "thread_id": "uuid",
  "provider_strategy": "auto",
  "preferred_provider": "openai",
  "fallback_provider": "anthropic",
  "requirements": {
    "structured_output": true,
    "tool_calling": true,
    "low_latency": true
  }
}
Response esperada
•	intenção 
•	tipo de demanda sugerido 
•	urgência 
•	dados faltantes 
•	resumo inicial 
•	sugestão de lead/processo 
Isso conversa com o output JSON já previsto para o atendente. 
________________________________________
8.9 POST /ai/watcher/classify-event
Request
{
  "message_id": "uuid",
  "provider_strategy": "auto",
  "preferred_provider": "gemini",
  "fallback_provider": "openai",
  "requirements": {
    "structured_output": true,
    "low_latency": true,
    "cost_efficient": true
  }
}
Response esperada
•	tipo de evento 
•	urgência 
•	prazo identificado 
•	processo correlato 
•	ação sugerida 
________________________________________
9. Novo recurso de governança de providers
9.1 GET /ai/providers
Lista providers e modelos disponíveis ao tenant.
Response 200
{
  "data": [
    {
      "provider": "openai",
      "models": ["gpt-5", "gpt-5-mini", "gpt-4.1"],
      "capabilities": ["structured_output", "tool_calling", "vision"]
    },
    {
      "provider": "gemini",
      "models": ["gemini-2.5-pro", "gemini-2.5-flash"],
      "capabilities": ["vision", "long_context", "structured_output"]
    },
    {
      "provider": "anthropic",
      "models": ["claude-sonnet", "claude-opus"],
      "capabilities": ["tool_calling", "long_context", "prompt_caching"]
    }
  ]
}
________________________________________
9.2 GET /ai/policies/current
Retorna política de roteamento do tenant.
9.3 PATCH /ai/policies/current
Request
{
  "default_provider_strategy": "auto",
  "budget_limits": {
    "daily_usd": 50,
    "monthly_usd": 1000
  },
  "flows": {
    "attendant": {
      "preferred_provider": "openai",
      "fallback_provider": "anthropic"
    },
    "extractor": {
      "preferred_provider": "gemini",
      "fallback_provider": "openai"
    },
    "redactor": {
      "preferred_provider": "anthropic",
      "fallback_provider": "openai"
    }
  }
}
________________________________________
10. Ajustes em integrações por tenant
A API de integrações deve refletir que IA não é uma integração única, e sim uma família de providers configuráveis.
10.1 GET /integrations
Agora deve listar também:
•	openai 
•	google_ai 
•	vertex_ai 
•	anthropic 
10.2 POST /integrations
Exemplo OpenAI
{
  "provider": "openai",
  "label": "OpenAI principal",
  "config": {
    "api_key_ref": "secret://tenant/openai/main"
  }
}
Exemplo Gemini
{
  "provider": "google_ai",
  "label": "Gemini principal",
  "config": {
    "api_key_ref": "secret://tenant/google-ai/main"
  }
}
Exemplo Claude
{
  "provider": "anthropic",
  "label": "Claude principal",
  "config": {
    "api_key_ref": "secret://tenant/anthropic/main"
  }
}
________________________________________
11. Observabilidade obrigatória por chamada de IA
A auditabilidade já é um princípio do projeto. 
Com multi-provider, isso precisa ficar ainda mais forte.
Registrar por chamada
•	tenant_id 
•	job_id 
•	provider_strategy 
•	provider_selected 
•	model_selected 
•	agent 
•	prompt_version 
•	capabilities_required 
•	capabilities_used 
•	input_tokens 
•	output_tokens 
•	cached_tokens 
•	latency_ms 
•	estimated_cost_usd 
•	fallback_used 
•	error_code 
•	input_hash 
•	output_hash 
________________________________________
12. Política de fallback
Regra geral
Se o provider primário falhar por:
•	indisponibilidade 
•	timeout 
•	limite de taxa 
•	custo máximo excedido 
•	ausência da capability exigida 
o AI Gateway tenta o provider secundário.
Exemplo
document_extraction
1.	Gemini 
2.	OpenAI 
3.	revisão humana 
workflow_plan
1.	OpenAI 
2.	Claude 
3.	plano simplificado por regra 
redactor
1.	Claude 
2.	OpenAI 
3.	rascunho mínimo por template 
________________________________________
13. Regras de implementação
13.1 O core não conhece SDKs de vendor
O core só conhece:
•	job 
•	entidade 
•	capability 
•	policy 
•	resultado normalizado 
13.2 SDKs ficam encapsulados no AI Gateway
Isso preserva o princípio arquitetural já definido: se amanhã trocar IA, mexe só no serviço Python, não no sistema inteiro. 
13.3 Prompt governance
Cada fluxo deve ter:
•	nome 
•	versão 
•	agente 
•	schema esperado 
•	política de provider 
•	política de fallback 
•	exemplos de few-shot 
•	critérios de revisão humana 
________________________________________
14. Texto oficial para entrar no documento
Você pode incorporar este trecho literalmente:
A plataforma adotará arquitetura multi-provider de IA, sem dependência exclusiva de um único fornecedor. O motor de IA será implementado por meio de um AI Gateway / Model Router responsável por abstrair provedores como OpenAI, Google Gemini e Anthropic Claude, normalizando contratos de entrada e saída, aplicando políticas de roteamento por capability, custo, latência e contexto, além de executar fallback automático quando necessário.
A seleção de provider ocorrerá por capacidade requerida do fluxo — como structured output, tool calling, contexto longo, visão ou redação longa — e não por acoplamento fixo ao vendor.
Cada chamada de IA deverá ser auditável, registrando provider selecionado, modelo, versão do prompt, capacidades requeridas, tokens, latência, custo, fallback e resultado estruturado.
