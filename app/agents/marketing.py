"""
MarketingAgent — Geracao de conteudo para campanhas e marketing.

Gera posts, emails marketing e mensagens WhatsApp para
campanhas de aquisicao e engajamento de clientes rurais.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentRegistry, BaseAgent
from app.models.ai_job import AIJobType


@AgentRegistry.register
class MarketingAgent(BaseAgent):
    name = "marketing"
    description = "Geracao de conteudo para campanhas e marketing"
    job_type = AIJobType.gerar_conteudo_marketing
    prompt_slugs = ["marketing_system", "marketing_post", "marketing_email", "marketing_whatsapp"]
    palace_room = "agent_marketing"

    VALID_CONTENT_TYPES = {"post", "email", "whatsapp", "blog", "banner"}

    def validate_preconditions(self) -> None:
        topic = self.ctx.metadata.get("topic", "")
        if not topic.strip():
            raise ValueError("'topic' obrigatorio em metadata para geracao de conteudo")

    def execute(self) -> dict[str, Any]:
        content_type = self.ctx.metadata.get("content_type", "post")
        if content_type not in self.VALID_CONTENT_TYPES:
            content_type = "post"

        topic = self.ctx.metadata.get("topic", "")
        audience = self.ctx.metadata.get("audience", "produtor_rural")
        tone = self.ctx.metadata.get("tone", "profissional_acessivel")

        system_prompt = self.get_prompt("marketing_system")
        slug = f"marketing_{content_type}"
        user_prompt = self.get_prompt(slug, {
            "topic": topic,
            "audience": audience,
            "tone": tone,
            "extra_instructions": self.ctx.metadata.get("instructions", ""),
        })

        response = self.call_llm(user_prompt, system=system_prompt)

        return {
            "content_type": content_type,
            "generated_content": response.content,
            "topic": topic,
            "audience": audience,
            "requires_review": True,  # Conteudo marketing sempre passa por revisao
            "confidence": "medium",
        }

    def _fallback_prompts(self) -> dict[str, str]:
        return {
            "marketing_system": (
                "Voce e um especialista em marketing para agronegocio e consultoria ambiental no Brasil. "
                "Crie conteudo engajante, informativo e acessivel para produtores rurais. "
                "Use linguagem clara, evite jargao excessivo, e destaque beneficios praticos. "
                "O tom deve ser profissional mas acessivel."
            ),
            "marketing_post": (
                "Crie um post para redes sociais sobre:\n\n"
                "TEMA: {topic}\n"
                "PUBLICO: {audience}\n"
                "TOM: {tone}\n"
                "INSTRUCOES: {extra_instructions}\n\n"
                "Inclua hashtags relevantes e call-to-action."
            ),
            "marketing_email": (
                "Crie um email marketing sobre:\n\n"
                "TEMA: {topic}\n"
                "PUBLICO: {audience}\n"
                "TOM: {tone}\n"
                "INSTRUCOES: {extra_instructions}\n\n"
                "Inclua assunto, corpo e call-to-action."
            ),
            "marketing_whatsapp": (
                "Crie uma mensagem WhatsApp sobre:\n\n"
                "TEMA: {topic}\n"
                "PUBLICO: {audience}\n"
                "TOM: {tone}\n"
                "INSTRUCOES: {extra_instructions}\n\n"
                "Mantenha curto e direto. Maximo 500 caracteres."
            ),
            "marketing_blog": (
                "Crie um artigo de blog sobre:\n\n"
                "TEMA: {topic}\n"
                "PUBLICO: {audience}\n"
                "TOM: {tone}\n"
                "INSTRUCOES: {extra_instructions}\n\n"
                "Inclua titulo, subtitulos e conclusao."
            ),
            "marketing_banner": (
                "Crie texto para banner/anuncio sobre:\n\n"
                "TEMA: {topic}\n"
                "PUBLICO: {audience}\n"
                "TOM: {tone}\n"
                "INSTRUCOES: {extra_instructions}\n\n"
                "Titulo curto (max 10 palavras) e subtitulo."
            ),
        }
