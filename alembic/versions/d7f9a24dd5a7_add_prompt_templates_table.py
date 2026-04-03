"""add prompt_templates table

Revision ID: d7f9a24dd5a7
Revises: e5f6a7b8c9d0
Create Date: 2026-04-03 15:20:31.938258

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd7f9a24dd5a7'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum types gerenciados manualmente para controle no downgrade
_promptcategory = postgresql.ENUM('classify', 'extract', 'summarize', 'proposal', name='promptcategory', create_type=False)
_promptrole = postgresql.ENUM('system', 'user', 'few_shot', name='promptrole', create_type=False)


def upgrade() -> None:
    """Create prompt_templates table and enum types."""
    _promptcategory.create(op.get_bind(), checkfirst=True)
    _promptrole.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('category', _promptcategory, nullable=False),
        sa.Column('role', _promptrole, nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('input_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('model_hint', sa.String(length=100), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', 'version', 'tenant_id', name='uq_prompt_slug_version_tenant'),
    )
    op.create_index(op.f('ix_prompt_templates_category'), 'prompt_templates', ['category'], unique=False)
    op.create_index(op.f('ix_prompt_templates_id'), 'prompt_templates', ['id'], unique=False)
    op.create_index(op.f('ix_prompt_templates_slug'), 'prompt_templates', ['slug'], unique=False)
    op.create_index(op.f('ix_prompt_templates_tenant_id'), 'prompt_templates', ['tenant_id'], unique=False)


def downgrade() -> None:
    """Drop prompt_templates table and enum types."""
    op.drop_index(op.f('ix_prompt_templates_tenant_id'), table_name='prompt_templates')
    op.drop_index(op.f('ix_prompt_templates_slug'), table_name='prompt_templates')
    op.drop_index(op.f('ix_prompt_templates_id'), table_name='prompt_templates')
    op.drop_index(op.f('ix_prompt_templates_category'), table_name='prompt_templates')
    op.drop_table('prompt_templates')
    _promptrole.drop(op.get_bind(), checkfirst=True)
    _promptcategory.drop(op.get_bind(), checkfirst=True)
