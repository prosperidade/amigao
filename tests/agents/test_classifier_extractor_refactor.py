"""
Tests for refactored llm_classifier and document_extractor.
Valida que os servicos carregam prompts do banco e fazem fallback ao hardcoded.
Mock do ai_gateway.complete — zero consumo de API key.
"""

from unittest.mock import patch

import pytest

from app.models.prompt_template import PromptCategory, PromptRole, PromptTemplate
from app.services.prompt_service import invalidate_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_cache()
    yield
    invalidate_cache()


def _seed_prompt(db, slug, category, role, content):
    tpl = PromptTemplate(
        slug=slug,
        category=category,
        role=role,
        version=1,
        content=content,
        is_active=True,
    )
    db.add(tpl)
    db.flush()
    return tpl


def _make_ai_response(content='{"demand_type": "car", "confidence": "high", "diagnosis": "test"}'):
    """Cria mock de AIResponse."""
    from app.core.ai_gateway import AIResponse
    return AIResponse(
        content=content,
        model_used="mock-model",
        tokens_in=100,
        tokens_out=50,
        cost_usd=0.001,
        duration_ms=200,
        provider="mock",
    )


class TestClassifierUsesDbPrompts:
    """Valida que classify_demand_with_llm carrega prompts do banco."""

    @patch("app.services.llm_classifier.settings")
    @patch("app.core.ai_gateway.complete")
    def test_uses_db_system_prompt(self, mock_complete, mock_settings, db_session):
        mock_settings.ai_configured = True
        mock_complete.return_value = _make_ai_response()

        _seed_prompt(
            db_session,
            "classify_demand_system",
            PromptCategory.classify,
            PromptRole.system,
            "CUSTOM SYSTEM PROMPT FROM DB",
        )
        _seed_prompt(
            db_session,
            "classify_demand_user",
            PromptCategory.classify,
            PromptRole.user,
            "Classifique: {description} canal={channel} urgencia={urgency}",
        )

        from app.services.llm_classifier import classify_demand_with_llm

        result, _ = classify_demand_with_llm(
            description="preciso regularizar area desmatada",
            source_channel="whatsapp",
            save_job=False,
            db_session=db_session,
        )

        mock_complete.assert_called_once()
        call_kwargs = mock_complete.call_args
        assert "CUSTOM SYSTEM PROMPT FROM DB" in call_kwargs.kwargs.get("system", call_kwargs[1].get("system", ""))

    @patch("app.services.llm_classifier.settings")
    @patch("app.core.ai_gateway.complete")
    def test_fallback_to_hardcoded_without_db(self, mock_complete, mock_settings):
        """Sem db_session, usa prompts hardcoded.
        Descricao vaga forca confidence=low nas regras estaticas -> chama LLM.
        """
        mock_settings.ai_configured = True
        mock_complete.return_value = _make_ai_response()

        from app.services.llm_classifier import classify_demand_with_llm

        result, _ = classify_demand_with_llm(
            description="tenho um problema na fazenda",  # vago = low confidence nas regras
            save_job=False,
            db_session=None,
        )

        mock_complete.assert_called_once()
        call_kwargs = mock_complete.call_args
        system_used = call_kwargs.kwargs.get("system", call_kwargs[1].get("system", ""))
        assert "especialista" in system_used.lower()


class TestExtractorUsesDbPrompts:
    """Valida que extract_document_fields carrega prompts do banco."""

    @patch("app.services.document_extractor.settings")
    @patch("app.core.ai_gateway.complete")
    def test_uses_db_extract_prompt(self, mock_complete, mock_settings, db_session):
        mock_settings.ai_configured = True
        mock_complete.return_value = _make_ai_response('{"numero_matricula": "12345", "confidence": {"numero_matricula": "high"}}')

        _seed_prompt(
            db_session,
            "extract_document_system",
            PromptCategory.extract,
            PromptRole.system,
            "CUSTOM EXTRACTOR SYSTEM FROM DB",
        )
        _seed_prompt(
            db_session,
            "extract_matricula",
            PromptCategory.extract,
            PromptRole.user,
            "DB TEMPLATE: Extraia da matricula:\n{text}",
        )

        from app.services.document_extractor import extract_document_fields

        result, _ = extract_document_fields(
            text="Matricula numero 12345 do cartorio de Cuiaba",
            doc_type="matricula",
            save_job=False,
            db_session=db_session,
        )

        mock_complete.assert_called_once()
        call_kwargs = mock_complete.call_args
        assert "CUSTOM EXTRACTOR SYSTEM FROM DB" in call_kwargs.kwargs.get("system", call_kwargs[1].get("system", ""))
        assert result.get("numero_matricula") == "12345"

    @patch("app.services.document_extractor.settings")
    @patch("app.core.ai_gateway.complete")
    def test_fallback_to_hardcoded_prompts(self, mock_complete, mock_settings):
        """Sem db_session, usa prompts hardcoded de fallback.
        Usa doc_type 'default' que nao tem JSON braces no template.
        """
        mock_settings.ai_configured = True
        mock_complete.return_value = _make_ai_response('{"campo": "valor", "confidence": {}}')

        from app.services.document_extractor import extract_document_fields

        result, _ = extract_document_fields(
            text="documento generico de teste",
            doc_type="tipo_sem_template",
            save_job=False,
            db_session=None,
        )

        mock_complete.assert_called_once()
        assert result.get("campo") == "valor"

    @patch("app.services.document_extractor.settings")
    @patch("app.core.ai_gateway.complete")
    def test_unknown_doc_type_uses_default(self, mock_complete, mock_settings):
        """doc_type desconhecido usa prompt default."""
        mock_settings.ai_configured = True
        mock_complete.return_value = _make_ai_response('{"campo": "valor", "confidence": {}}')

        from app.services.document_extractor import extract_document_fields

        result, _ = extract_document_fields(
            text="documento generico",
            doc_type="tipo_desconhecido",
            save_job=False,
            db_session=None,
        )

        mock_complete.assert_called_once()
        assert result.get("campo") == "valor"
