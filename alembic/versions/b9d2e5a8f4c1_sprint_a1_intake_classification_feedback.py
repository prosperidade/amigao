"""Sprint A1 (Tarefa E) — IntakeClassificationFeedback.

Revision ID: b9d2e5a8f4c1
Revises: a8e1d4c7f3b6
Create Date: 2026-05-08

Cria a tabela ``intake_classification_feedback`` que registra correções
humanas sobre a classificação inicial de demanda (output do AtendimentoAgent).
Cada linha é uma "promoção" do ``Process.demand_type`` feita pelo consultor
via ``POST /processes/{id}/classify``.

VALIDAÇÃO MANUAL (Q6 da Fase 0)::

    docker compose exec api alembic upgrade head
    docker compose exec api alembic downgrade -1
"""

import sqlalchemy as sa
from alembic import op

revision = "b9d2e5a8f4c1"
down_revision = "a8e1d4c7f3b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intake_classification_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "process_id", sa.Integer(),
            sa.ForeignKey("processes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "intake_draft_id", sa.Integer(),
            sa.ForeignKey("intake_drafts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ai_demand_type", sa.String(), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column(
            "ai_run_id", sa.Integer(),
            sa.ForeignKey("ai_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("corrected_demand_type", sa.String(), nullable=False),
        sa.Column(
            "corrected_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "corrected_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_intake_classification_feedback_tenant_id",
        "intake_classification_feedback", ["tenant_id"],
    )
    op.create_index(
        "ix_intake_classification_feedback_process_id",
        "intake_classification_feedback", ["process_id"],
    )
    op.create_index(
        "ix_intake_classification_feedback_intake_draft_id",
        "intake_classification_feedback", ["intake_draft_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_intake_classification_feedback_intake_draft_id",
        table_name="intake_classification_feedback",
    )
    op.drop_index(
        "ix_intake_classification_feedback_process_id",
        table_name="intake_classification_feedback",
    )
    op.drop_index(
        "ix_intake_classification_feedback_tenant_id",
        table_name="intake_classification_feedback",
    )
    op.drop_table("intake_classification_feedback")
