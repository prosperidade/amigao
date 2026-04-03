"""
Tests for prompt_service — lookup, versionamento, cache, fallback.
Roda contra PostgreSQL real via conftest.py (Testcontainers).
Zero consumo de API key.
"""


import pytest

from app.models.prompt_template import PromptCategory, PromptRole, PromptTemplate
from app.services.prompt_service import (
    _cache,
    create_new_version,
    get_active_prompt,
    invalidate_cache,
    render_prompt,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Limpa cache antes de cada teste."""
    invalidate_cache()
    yield
    invalidate_cache()


def _make_prompt(db, slug, version=1, content="test", tenant_id=None, is_active=True):
    """Helper para criar prompts de teste."""
    tpl = PromptTemplate(
        slug=slug,
        category=PromptCategory.classify,
        role=PromptRole.system,
        version=version,
        content=content,
        tenant_id=tenant_id,
        is_active=is_active,
    )
    db.add(tpl)
    db.flush()
    return tpl


class TestGetActivePrompt:
    """Testa busca de prompt ativo com prioridade e versionamento."""

    def test_returns_active_prompt(self, db_session):
        _make_prompt(db_session, "test_slug", content="hello world")

        result = get_active_prompt("test_slug", db_session)
        assert result is not None
        assert result.content == "hello world"

    def test_returns_latest_version(self, db_session):
        _make_prompt(db_session, "versioned", version=1, content="v1", is_active=False)
        _make_prompt(db_session, "versioned", version=2, content="v2", is_active=True)

        result = get_active_prompt("versioned", db_session)
        assert result.version == 2
        assert result.content == "v2"

    def test_returns_none_for_missing(self, db_session):
        result = get_active_prompt("nonexistent", db_session)
        assert result is None

    def test_returns_none_for_inactive(self, db_session):
        _make_prompt(db_session, "inactive_slug", is_active=False)

        result = get_active_prompt("inactive_slug", db_session)
        assert result is None

    def test_tenant_priority_over_global(self, db_session):
        """Prompt tenant-specific tem prioridade sobre global."""
        from app.models.tenant import Tenant

        tenant = Tenant(name="Priority Tenant")
        db_session.add(tenant)
        db_session.flush()

        _make_prompt(db_session, "prio_test", content="global version")
        _make_prompt(db_session, "prio_test", content="tenant version", tenant_id=tenant.id)

        result = get_active_prompt("prio_test", db_session, tenant_id=tenant.id)
        assert result.content == "tenant version"

    def test_fallback_to_global(self, db_session):
        """Se nao existe tenant-specific, retorna global."""
        _make_prompt(db_session, "fallback_test", content="global only")

        result = get_active_prompt("fallback_test", db_session, tenant_id=9999)
        assert result is not None
        assert result.content == "global only"

    def test_cache_hit(self, db_session):
        _make_prompt(db_session, "cached_slug", content="cached")

        r1 = get_active_prompt("cached_slug", db_session)
        assert r1 is not None

        # Segunda chamada deve vir do cache (sem query)
        r2 = get_active_prompt("cached_slug", db_session)
        assert r2 is r1  # mesma instancia = cache hit

    def test_cache_invalidation(self, db_session):
        _make_prompt(db_session, "inv_test", content="original")
        get_active_prompt("inv_test", db_session)

        invalidate_cache("inv_test")

        assert not any(k.startswith("inv_test::") for k in _cache)


class TestCreateNewVersion:
    """Testa criacao de nova versao com auto-increment."""

    def test_first_version(self, db_session):
        result = create_new_version(
            "brand_new",
            db_session,
            content="first version",
        )
        assert result.version == 1
        assert result.is_active is True

    def test_auto_increment_version(self, db_session):
        _make_prompt(db_session, "inc_test", version=1, content="v1")

        result = create_new_version(
            "inc_test",
            db_session,
            content="v2 updated",
        )
        assert result.version == 2
        assert result.content == "v2 updated"
        assert result.is_active is True

    def test_deactivates_previous_version(self, db_session):
        original = _make_prompt(db_session, "deact_test", version=1, content="v1")

        create_new_version("deact_test", db_session, content="v2")
        db_session.flush()

        db_session.refresh(original)
        assert original.is_active is False

    def test_preserves_category_and_role(self, db_session):
        tpl = PromptTemplate(
            slug="preserve_test",
            category=PromptCategory.extract,
            role=PromptRole.user,
            version=1,
            content="v1",
            is_active=True,
        )
        db_session.add(tpl)
        db_session.flush()

        result = create_new_version("preserve_test", db_session, content="v2")
        assert result.category == PromptCategory.extract
        assert result.role == PromptRole.user


class TestRenderPrompt:
    """Testa substituicao de variaveis no template."""

    def test_render_variables(self, db_session):
        tpl = _make_prompt(
            db_session,
            "render_test",
            content="Descricao: {description}\nCanal: {channel}",
        )
        rendered = render_prompt(tpl, {"description": "CAR urgente", "channel": "whatsapp"})
        assert "CAR urgente" in rendered
        assert "whatsapp" in rendered

    def test_render_missing_variable_left_as_is(self, db_session):
        tpl = _make_prompt(
            db_session,
            "partial_render",
            content="Texto: {text}\nExtra: {missing}",
        )
        rendered = render_prompt(tpl, {"text": "conteudo"})
        assert "conteudo" in rendered
        assert "{missing}" in rendered  # nao substituido


class TestSchemaValidation:
    """Testa schemas Pydantic de PromptTemplate."""

    def test_create_schema_valid(self):
        from app.schemas.prompt_template import PromptTemplateCreate

        data = PromptTemplateCreate(
            slug="valid_slug",
            category=PromptCategory.classify,
            role=PromptRole.system,
            content="prompt content",
        )
        assert data.slug == "valid_slug"

    def test_create_schema_invalid_slug(self):
        from pydantic import ValidationError

        from app.schemas.prompt_template import PromptTemplateCreate

        with pytest.raises(ValidationError):
            PromptTemplateCreate(
                slug="Invalid-Slug!",  # uppercase + special chars
                category=PromptCategory.classify,
                role=PromptRole.system,
                content="x",
            )

    def test_create_schema_empty_content_rejected(self):
        from pydantic import ValidationError

        from app.schemas.prompt_template import PromptTemplateCreate

        with pytest.raises(ValidationError):
            PromptTemplateCreate(
                slug="empty_test",
                category=PromptCategory.classify,
                role=PromptRole.system,
                content="",
            )

    def test_create_schema_temperature_bounds(self):
        from pydantic import ValidationError

        from app.schemas.prompt_template import PromptTemplateCreate

        with pytest.raises(ValidationError):
            PromptTemplateCreate(
                slug="temp_test",
                category=PromptCategory.classify,
                role=PromptRole.system,
                content="x",
                temperature=3.0,  # max 2.0
            )

    def test_read_schema_from_orm(self, db_session):
        from app.schemas.prompt_template import PromptTemplateRead

        tpl = _make_prompt(db_session, "orm_test", content="from orm")
        db_session.flush()
        db_session.refresh(tpl)

        dto = PromptTemplateRead.model_validate(tpl)
        assert dto.slug == "orm_test"
        assert dto.content == "from orm"
        assert dto.id == tpl.id
