Aditivo arquitetural — política multi-LLM
1. Princípio
Nenhum fluxo de IA do sistema deve depender exclusivamente de um único vendor.
A arquitetura deve suportar:
•	OpenAI 
•	Google Gemini 
•	Anthropic Claude 
•	futuros providers via adapter 
2. Objetivo da camada de abstração
A plataforma precisa decidir, por fluxo:
•	qual modelo usar 
•	quando trocar de provedor 
•	quando usar fallback 
•	quando usar modelo barato 
•	quando usar modelo premium 
•	quando exigir JSON rígido 
•	quando priorizar contexto longo 
•	quando priorizar visão/documento multimodal 
•	quando priorizar custo 
________________________________________
3. Novo componente obrigatório na arquitetura
3.1 AI Gateway / Model Router
Adicionar um serviço lógico entre workers e provedores:
[ API Core ]
   -> cria job
   -> publica fila

[ Worker AI ]
   -> chama AI Gateway / Model Router
          -> Provider Adapter: OpenAI
          -> Provider Adapter: Gemini
          -> Provider Adapter: Claude
          -> Fallback / Retry Policy
          -> Cost Policy
          -> Observabilidade
3.2 Responsabilidades do AI Gateway
•	abstrair SDKs dos vendors 
•	normalizar request/response 
•	aplicar política de roteamento 
•	medir custo, latência e erro por provider/modelo 
•	aplicar fallback automático 
•	versionar prompts por fluxo 
•	suportar tools/function calling 
•	suportar multimodalidade 
•	suportar structured outputs 
•	registrar auditoria por chamada 
________________________________________
4. Contrato interno padronizado
A API interna de IA não deve expor “OpenAIRequest”, “ClaudeRequest” ou “GeminiRequest” para o resto do sistema.
Ela deve trabalhar com um contrato interno como:
{
  "task_type": "document_extraction",
  "tenant_id": "uuid",
  "entity_type": "document",
  "entity_id": "uuid",
  "input": {
    "text": "...",
    "images": [],
    "pdf_refs": []
  },
  "requirements": {
    "json_schema": true,
    "vision": true,
    "long_context": false,
    "tool_calling": false,
    "low_latency": false,
    "max_cost_tier": "medium"
  },
  "policy": {
    "preferred_provider": "auto",
    "fallback_enabled": true
  }
}
E a resposta normalizada:
{
  "provider": "gemini",
  "model": "gemini-2.5-pro",
  "status": "success",
  "output_text": "...",
  "structured_output": {},
  "tool_calls": [],
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "estimated_cost_usd": 0
  },
  "latency_ms": 0
}
________________________________________
5. Matriz de uso por provedor
5.1 OpenAI — melhor encaixe
Usar preferencialmente em:
•	saídas JSON muito rígidas 
•	fluxos com function/tool calling 
•	orquestração agentic 
•	classificação estruturada 
•	automações com schema forte 
•	planejamento multi-etapas 
•	workflows com respostas previsíveis de máquina 
Motivo
A OpenAI documenta function calling/tools e Structured Outputs com aderência a JSON Schema, além da Responses API para fluxos agentic e modelos de raciocínio para planejamento complexo. 
Exemplos no projeto
•	Agente Orquestrador 
•	classificação de intake 
•	geração de tarefas estruturadas 
•	resposta JSON para document_extraction 
•	roteamento de ações do sistema 
________________________________________
5.2 Gemini — melhor encaixe
Usar preferencialmente em:
•	documentos longos 
•	PDFs extensos 
•	análise multimodal rica 
•	cenários com contexto muito longo 
•	fluxos que se beneficiem de grounding/search/contexto URL 
•	processamento de lotes documentais grandes 
Motivo
A documentação oficial do Gemini API destaca janelas de contexto muito longas, modelos com suporte a texto, imagem, vídeo, áudio e PDF, além de function calling, structured outputs, file search e search grounding em linhas recentes de modelo. 
Exemplos no projeto
•	Agente Extrator em dossiês longos 
•	Agente Regulatório com base normativa extensa 
•	análise de processo com muitos anexos 
•	revisão de PDFs complexos 
________________________________________
5.3 Claude — melhor encaixe
Usar preferencialmente em:
•	redação técnica longa 
•	revisão de texto/código/documentos 
•	raciocínio com contexto extenso 
•	visão em imagens e páginas 
•	fluxos em que prompt caching ajude a reduzir custo de contexto estático repetido 
Motivo
A Anthropic documenta contexto de 200k para Claude 4 no overview, suporte a visão em Claude 3 e 4, e prompt caching para reaproveitar prefixos estáticos como instruções, tools e contexto recorrente. 
Exemplos no projeto
•	Agente Redator 
•	revisão de pareceres e memoriais 
•	comparação entre versões de documentos 
•	fluxos longos com instruções fixas repetidas 
________________________________________
6. Roteamento recomendado por fluxo do sistema
6.1 Agente Atendente
Primário
•	OpenAI ou Claude 
Secundário
•	Gemini 
Critério
•	classificação + JSON: OpenAI 
•	resposta conversacional mais longa e refinada: Claude 
•	multimodal com anexos pesados: Gemini 
________________________________________
6.2 Agente Extrator
Primário
•	Gemini 
Secundário
•	OpenAI 
Critério
•	PDF/multimodal/contexto longo: Gemini 
•	extração rigidamente estruturada: OpenAI 
Observação
OCR continua separado do LLM. O modelo entra depois do OCR e da limpeza, como já definimos.
________________________________________
6.3 Agente Regulatório
Primário
•	Gemini ou Claude 
Secundário
•	OpenAI 
Critério
•	base longa / muitos documentos: Gemini 
•	síntese argumentativa longa: Claude 
•	resposta estruturada/checklist JSON: OpenAI 
________________________________________
6.4 Agente Orquestrador
Primário
•	OpenAI 
Secundário
•	Claude 
Critério
•	tool calling e saídas determinísticas pesam mais aqui. 
________________________________________
6.5 Agente Redator
Primário
•	Claude 
Secundário
•	OpenAI ou Gemini 
Critério
•	redação longa e revisão: Claude 
•	documento com forte estrutura e campos formais: OpenAI 
•	apoio multimodal/documental pesado: Gemini 
________________________________________
6.6 Agente Vigia
Primário
•	OpenAI mini/nano ou equivalente econômico 
•	Gemini Flash / modelos rápidos 
•	Claude mais econômico quando o fluxo justificar 
Critério
•	classificação barata 
•	alto volume 
•	baixa latência 
•	custo controlado 
________________________________________
7. Política de fallback
Regras
Se o provider primário falhar por:
•	indisponibilidade 
•	timeout 
•	limite de rate 
•	custo estourado 
•	incapacidade da capability exigida 
o AI Gateway tenta o provider secundário.
Exemplo
document_extraction
1. Gemini
2. OpenAI
3. fila para revisão humana
workflow_plan
1. OpenAI
2. Claude
3. plano simplificado baseado em regra
________________________________________
8. Política de capabilities
O roteamento não deve ser por nome de fornecedor, e sim por capacidade requerida.
Capacidades que o registry deve armazenar
•	text_generation 
•	structured_output 
•	tool_calling 
•	long_context 
•	vision 
•	pdf_understanding 
•	code_reasoning 
•	search_grounding 
•	prompt_caching 
•	latency_tier 
•	cost_tier 
Exemplo de registry interno
{
  "provider": "anthropic",
  "model": "claude-sonnet-4",
  "capabilities": {
    "structured_output": true,
    "tool_calling": true,
    "vision": true,
    "long_context": true,
    "prompt_caching": true,
    "cost_tier": "medium",
    "latency_tier": "medium"
  }
}
________________________________________
9. Ajuste na especificação da API v1
A API deve deixar de ter integrações de IA amarradas a um único vendor.
Em vez de:
{
  "provider": "openai"
}
Passar a aceitar:
{
  "provider_strategy": "auto",
  "preferred_provider": "gemini",
  "fallback_provider": "openai",
  "requirements": {
    "vision": true,
    "structured_output": true,
    "long_context": true
  }
}
________________________________________
10. Endpoints que precisam mudar
10.1 POST /ai/jobs
Adicionar:
{
  "agent": "extrator",
  "entity_type": "document",
  "entity_id": "uuid",
  "provider_strategy": "auto",
  "preferred_provider": "gemini",
  "fallback_provider": "openai",
  "requirements": {
    "vision": true,
    "structured_output": true,
    "long_context": false,
    "tool_calling": false
  }
}
10.2 GET /ai/jobs/{id}
Retornar também:
{
  "provider_selected": "gemini",
  "fallback_used": false,
  "model": "gemini-2.5-pro",
  "capabilities_used": [
    "vision",
    "structured_output"
  ]
}
10.3 GET /integrations
Deve listar também providers de IA por tenant:
•	openai 
•	anthropic 
•	google_ai 
•	vertex_ai 
•	openrouter futuramente, se quiserem brokerizar 
________________________________________
11. Configuração por tenant
Cada tenant poderá definir:
•	provider padrão 
•	provider por fluxo 
•	limites de custo por dia/mês 
•	uso de chave própria 
•	modelos permitidos 
•	fallback permitido ou não 
Exemplo
{
  "ai_policy": {
    "default_provider_strategy": "auto",
    "flows": {
      "attendant": {
        "preferred_provider": "openai"
      },
      "extractor": {
        "preferred_provider": "gemini"
      },
      "redactor": {
        "preferred_provider": "anthropic"
      }
    },
    "budget_limits": {
      "daily_usd": 50,
      "monthly_usd": 1000
    }
  }
}
________________________________________
12. Observabilidade obrigatória por vendor
Registrar por chamada:
•	provider 
•	model 
•	versão do prompt 
•	capability requerida 
•	capability usada 
•	input tokens 
•	output tokens 
•	cache hit, quando existir 
•	latência 
•	custo 
•	fallback 
•	erro 
Isso é especialmente importante porque cada provedor tem pontos fortes diferentes, e a arquitetura deve aprender com a operação real.
________________________________________
13. Redação oficial para entrar no documento
Você pode incorporar este texto:
A plataforma adotará arquitetura multi-LLM e multi-provider, sem dependência exclusiva de um único fornecedor de IA. A camada de IA será implementada por meio de um AI Gateway/Model Router responsável por abstrair provedores como OpenAI, Google Gemini e Anthropic Claude, normalizar contratos de entrada e saída, aplicar políticas de roteamento por capacidade, custo, latência e contexto, além de executar fallback automático quando necessário.
Cada fluxo do sistema poderá utilizar provedores distintos conforme sua natureza: saídas estruturadas e tool calling, análise multimodal e contexto extenso, redação técnica longa, revisão documental ou classificação de alto volume. A seleção de modelo será orientada por capability requirements e não por acoplamento fixo a vendor específico.
O sistema deverá registrar auditoria completa por chamada de IA, incluindo provider, modelo, versão de prompt, consumo, latência, custo, fallback e resultado estruturado.
