"""Add agent system columns and enum values to ai_jobs and prompt_templates.

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-04-08

Changes:
- Add agent_name and chain_trace_id columns to ai_jobs
- Add new AIJobType enum values for agents
- Add new PromptCategory enum values for agents
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


# New AIJobType enum values
NEW_JOB_TYPES = [
    "diagnostico_propriedade",
    "consulta_regulatoria",
    "gerar_documento",
    "analise_financeira",
    "acompanhamento_processo",
    "monitoramento_vigia",
    "gerar_conteudo_marketing",
]

# New PromptCategory enum values
NEW_PROMPT_CATEGORIES = [
    "diagnostico",
    "legislacao",
    "redator",
    "financeiro",
    "acompanhamento",
    "vigia",
    "marketing",
]


def upgrade():
    # --- Add new columns to ai_jobs ---
    op.add_column("ai_jobs", sa.Column("agent_name", sa.String(50), nullable=True))
    op.add_column("ai_jobs", sa.Column("chain_trace_id", sa.String(32), nullable=True))
    op.create_index("ix_ai_jobs_agent_name", "ai_jobs", ["agent_name"])

    # --- Add new AIJobType enum values ---
    # PostgreSQL requires ALTER TYPE ... ADD VALUE for enums
    for value in NEW_JOB_TYPES:
        op.execute(f"ALTER TYPE aijobtype ADD VALUE IF NOT EXISTS '{value}'")

    # --- Add new PromptCategory enum values ---
    for value in NEW_PROMPT_CATEGORIES:
        op.execute(f"ALTER TYPE promptcategory ADD VALUE IF NOT EXISTS '{value}'")


def downgrade():
    # --- Remove columns ---
    op.drop_index("ix_ai_jobs_agent_name", "ai_jobs")
    op.drop_column("ai_jobs", "chain_trace_id")
    op.drop_column("ai_jobs", "agent_name")

    # Note: PostgreSQL does not support removing enum values.
    # To fully downgrade, you would need to recreate the enum types.
    # This is intentionally left as a no-op for safety.
