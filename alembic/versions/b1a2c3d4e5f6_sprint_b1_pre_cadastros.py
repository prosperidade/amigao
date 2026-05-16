"""Sprint B1 — pre_cadastros (waitlist do Regente Ambiental).

Revision ID: b1a2c3d4e5f6
Revises: b9d2e5a8f4c1
Create Date: 2026-05-13

Cria a tabela ``pre_cadastros`` para captura de leads via
``POST /api/v1/waitlist`` (endpoint público, sem auth).

Sem tenant_id — lead anônimo até conversão em ``users`` (FK opcional
``converted_user_id``). Soft-delete (``deleted_at``) + hard-delete
agendado (``purge_after``) por Celery beat-scan para conformidade LGPD.

VALIDAÇÃO MANUAL::

    docker compose exec api alembic upgrade head
    docker compose exec api alembic downgrade -1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b1a2c3d4e5f6"
down_revision = "b9d2e5a8f4c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pre_cadastros",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Contato — PII
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("telefone", sa.String(length=20), nullable=True),
        # Perfil
        sa.Column("perfil_profissional", sa.String(length=80), nullable=True),
        sa.Column("estado", sa.String(length=2), nullable=True),
        sa.Column("tipo_licenciamento", sa.String(length=120), nullable=True),
        sa.Column("volume_mensal", sa.Integer(), nullable=True),
        sa.Column("ferramenta_atual", sa.String(length=120), nullable=True),
        # Validação de produto
        sa.Column("preco_aceito", JSONB(), nullable=True),
        sa.Column("expectativa", sa.Text(), nullable=True),
        sa.Column("deal_breaker", sa.Text(), nullable=True),
        sa.Column("interesse_grupo", sa.Boolean(), nullable=True, server_default=sa.false()),
        # Tracking
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("utm_source", sa.String(length=120), nullable=True),
        sa.Column("utm_medium", sa.String(length=120), nullable=True),
        sa.Column("utm_campaign", sa.String(length=120), nullable=True),
        sa.Column("utm_term", sa.String(length=120), nullable=True),
        sa.Column("utm_content", sa.String(length=120), nullable=True),
        # Resend
        sa.Column("resend_contact_id", sa.String(length=60), nullable=True),
        # LGPD
        sa.Column(
            "consentimento_dado_em", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True),
        # Conversão
        sa.Column(
            "converted_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Auditoria
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_pre_cadastros_email"),
    )
    op.create_index("ix_pre_cadastros_email", "pre_cadastros", ["email"])
    op.create_index("ix_pre_cadastros_resend_contact_id", "pre_cadastros", ["resend_contact_id"])
    op.create_index("ix_pre_cadastros_deleted_at", "pre_cadastros", ["deleted_at"])
    op.create_index("ix_pre_cadastros_purge_after", "pre_cadastros", ["purge_after"])
    op.create_index("ix_pre_cadastros_converted_user_id", "pre_cadastros", ["converted_user_id"])
    op.create_index("ix_pre_cadastros_created_at", "pre_cadastros", ["created_at"])
    op.create_index(
        "ix_pre_cadastros_utm_campaign",
        "pre_cadastros",
        ["utm_source", "utm_campaign"],
    )


def downgrade() -> None:
    op.drop_index("ix_pre_cadastros_utm_campaign", table_name="pre_cadastros")
    op.drop_index("ix_pre_cadastros_created_at", table_name="pre_cadastros")
    op.drop_index("ix_pre_cadastros_converted_user_id", table_name="pre_cadastros")
    op.drop_index("ix_pre_cadastros_purge_after", table_name="pre_cadastros")
    op.drop_index("ix_pre_cadastros_deleted_at", table_name="pre_cadastros")
    op.drop_index("ix_pre_cadastros_resend_contact_id", table_name="pre_cadastros")
    op.drop_index("ix_pre_cadastros_email", table_name="pre_cadastros")
    op.drop_table("pre_cadastros")
