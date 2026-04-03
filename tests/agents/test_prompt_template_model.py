"""
Tests for PromptTemplate model — CRUD, versionamento, constraints.
Roda contra PostgreSQL real via conftest.py (Testcontainers).
Zero consumo de API key.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.prompt_template import PromptCategory, PromptRole, PromptTemplate


class TestPromptTemplateModel:
    """CRUD basico da model PromptTemplate."""

    def test_create_prompt(self, db_session):
        tpl = PromptTemplate(
            slug="test_prompt",
            category=PromptCategory.classify,
            role=PromptRole.system,
            version=1,
            content="Voce e um assistente.",
            is_active=True,
        )
        db_session.add(tpl)
        db_session.flush()

        assert tpl.id is not None
        assert tpl.slug == "test_prompt"
        assert tpl.category == PromptCategory.classify
        assert tpl.role == PromptRole.system
        assert tpl.version == 1
        assert tpl.is_active is True
        assert tpl.tenant_id is None

    def test_create_with_tenant(self, db_session):
        """Prompt tenant-specific com tenant_id preenchido."""
        # Cria tenant minimo para FK
        from app.models.tenant import Tenant

        tenant = Tenant(name="Test Tenant")
        db_session.add(tenant)
        db_session.flush()

        tpl = PromptTemplate(
            tenant_id=tenant.id,
            slug="tenant_prompt",
            category=PromptCategory.extract,
            role=PromptRole.user,
            version=1,
            content="Extraia campos do documento:\n{text}",
            input_schema={"type": "object", "required": ["text"]},
            output_schema={"type": "object"},
            model_hint="gpt-4o-mini",
            temperature=0.1,
            max_tokens=2048,
            is_active=True,
        )
        db_session.add(tpl)
        db_session.flush()

        assert tpl.tenant_id == tenant.id
        assert tpl.input_schema["required"] == ["text"]
        assert tpl.model_hint == "gpt-4o-mini"
        assert tpl.temperature == 0.1

    def test_unique_constraint_slug_version_tenant(self, db_session):
        """Nao pode haver duplicata (slug, version, tenant_id) com tenant preenchido."""
        from app.models.tenant import Tenant

        tenant = Tenant(name="Dup Tenant")
        db_session.add(tenant)
        db_session.flush()

        tpl1 = PromptTemplate(
            slug="dup_test",
            category=PromptCategory.classify,
            role=PromptRole.system,
            version=1,
            content="v1",
            tenant_id=tenant.id,
            is_active=True,
        )
        db_session.add(tpl1)
        db_session.flush()

        tpl2 = PromptTemplate(
            slug="dup_test",
            category=PromptCategory.classify,
            role=PromptRole.system,
            version=1,
            content="v1 duplicado",
            tenant_id=tenant.id,
            is_active=True,
        )
        db_session.add(tpl2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_multiple_versions_allowed(self, db_session):
        """Versoes diferentes do mesmo slug sao permitidas."""
        for v in (1, 2, 3):
            tpl = PromptTemplate(
                slug="versioned_prompt",
                category=PromptCategory.summarize,
                role=PromptRole.system,
                version=v,
                content=f"Conteudo v{v}",
                is_active=(v == 3),  # so ultima ativa
            )
            db_session.add(tpl)

        db_session.flush()

        results = (
            db_session.query(PromptTemplate)
            .filter(PromptTemplate.slug == "versioned_prompt")
            .all()
        )
        assert len(results) == 3

    def test_jsonb_fields(self, db_session):
        """input_schema e output_schema armazenam JSON corretamente."""
        schema = {
            "type": "object",
            "properties": {
                "demand_type": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            },
            "required": ["demand_type", "confidence"],
        }
        tpl = PromptTemplate(
            slug="schema_test",
            category=PromptCategory.classify,
            role=PromptRole.system,
            version=1,
            content="test",
            output_schema=schema,
            is_active=True,
        )
        db_session.add(tpl)
        db_session.flush()

        loaded = db_session.query(PromptTemplate).filter_by(slug="schema_test").first()
        assert loaded.output_schema["required"] == ["demand_type", "confidence"]
        assert loaded.output_schema["properties"]["confidence"]["enum"] == ["high", "medium", "low"]

    def test_enum_values(self):
        """Todos os valores dos enums estao corretos."""
        assert set(PromptCategory) == {
            PromptCategory.classify,
            PromptCategory.extract,
            PromptCategory.summarize,
            PromptCategory.proposal,
        }
        assert set(PromptRole) == {
            PromptRole.system,
            PromptRole.user,
            PromptRole.few_shot,
        }
