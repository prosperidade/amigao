"""Correct models: ProcessStatus 11 states, Client fields, Property model, Document fields

Revision ID: afcea9834c04
Revises: b69a429faaa4
Create Date: 2026-03-26 16:15:51.042100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'afcea9834c04'
down_revision: Union[str, Sequence[str], None] = 'b69a429faaa4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. ENUMS
    client_type_enum = postgresql.ENUM('pf', 'pj', name='clienttype')
    client_status_enum = postgresql.ENUM('lead', 'active', 'inactive', 'delinquent', name='clientstatus')
    document_source_enum = postgresql.ENUM('upload_manual', 'email', 'whatsapp', 'integration', 'generated_ai', 'field_app', name='documentsource')
    ocr_status_enum = postgresql.ENUM('pending', 'processing', 'done', 'failed', 'not_required', name='ocrstatus')
    process_priority_enum = postgresql.ENUM('baixa', 'media', 'alta', 'critica', name='processpriority')
    
    client_type_enum.create(op.get_bind())
    client_status_enum.create(op.get_bind())
    document_source_enum.create(op.get_bind())
    ocr_status_enum.create(op.get_bind())
    process_priority_enum.create(op.get_bind())

    # Update ProcessStatus Enum
    op.execute("ALTER TYPE processstatus ADD VALUE IF NOT EXISTS 'lead';")
    op.execute("ALTER TYPE processstatus ADD VALUE IF NOT EXISTS 'triagem';")
    op.execute("ALTER TYPE processstatus ADD VALUE IF NOT EXISTS 'diagnostico';")
    op.execute("ALTER TYPE processstatus ADD VALUE IF NOT EXISTS 'planejamento';")
    op.execute("ALTER TYPE processstatus ADD VALUE IF NOT EXISTS 'execucao';")
    op.execute("ALTER TYPE processstatus ADD VALUE IF NOT EXISTS 'protocolo';")
    op.execute("ALTER TYPE processstatus ADD VALUE IF NOT EXISTS 'aguardando_orgao';")
    op.execute("ALTER TYPE processstatus ADD VALUE IF NOT EXISTS 'pendencia_orgao';")
    op.execute("ALTER TYPE processstatus ADD VALUE IF NOT EXISTS 'arquivado';")
    op.execute("ALTER TYPE processstatus ADD VALUE IF NOT EXISTS 'cancelado';")

    op.create_table('properties',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('registry_number', sa.String(), nullable=True),
    sa.Column('ccir', sa.String(), nullable=True),
    sa.Column('nirf', sa.String(), nullable=True),
    sa.Column('car_code', sa.String(), nullable=True),
    sa.Column('car_status', sa.String(), nullable=True),
    sa.Column('total_area_ha', sa.Float(), nullable=True),
    sa.Column('municipality', sa.String(), nullable=True),
    sa.Column('state', sa.String(length=2), nullable=True),
    sa.Column('biome', sa.String(), nullable=True),
    sa.Column('has_embargo', sa.Boolean(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_properties_client_id'), 'properties', ['client_id'], unique=False)
    op.create_index(op.f('ix_properties_id'), 'properties', ['id'], unique=False)
    op.create_index(op.f('ix_properties_tenant_id'), 'properties', ['tenant_id'], unique=False)

    op.add_column('clients', sa.Column('client_type', sa.Enum('pf', 'pj', name='clienttype'), server_default='pf', nullable=False))
    op.add_column('clients', sa.Column('legal_name', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('secondary_phone', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('birth_date', sa.Date(), nullable=True))
    op.add_column('clients', sa.Column('status', sa.Enum('lead', 'active', 'inactive', 'delinquent', name='clientstatus'), server_default='lead', nullable=False))
    op.add_column('clients', sa.Column('source_channel', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('clients', sa.Column('extra_json', sa.Text(), nullable=True))
    op.add_column('clients', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    op.add_column('documents', sa.Column('client_id', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('property_id', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('original_file_name', sa.String(), server_default='document', nullable=False))
    op.add_column('documents', sa.Column('mime_type', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('extension', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('storage_key', sa.String(), server_default='', nullable=False))
    op.add_column('documents', sa.Column('storage_provider', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('file_size_bytes', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('checksum_sha256', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('document_type', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('document_category', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('version_number', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('source', sa.Enum('upload_manual', 'email', 'whatsapp', 'integration', 'generated_ai', 'field_app', name='documentsource'), nullable=True))
    op.add_column('documents', sa.Column('ocr_status', sa.Enum('pending', 'processing', 'done', 'failed', 'not_required', name='ocrstatus'), nullable=True))
    op.add_column('documents', sa.Column('extraction_status', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('confidence_score', sa.Float(), nullable=True))
    op.add_column('documents', sa.Column('review_required', sa.Boolean(), nullable=True))
    op.add_column('documents', sa.Column('uploaded_by_user_id', sa.Integer(), nullable=True))
    
    op.alter_column('documents', 'process_id', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('documents', 's3_key', existing_type=sa.VARCHAR(), nullable=True)
    
    op.drop_constraint('documents_s3_key_key', 'documents', type_='unique')
    op.create_unique_constraint(None, 'documents', ['storage_key'])
    
    op.create_index(op.f('ix_documents_client_id'), 'documents', ['client_id'], unique=False)
    op.create_index(op.f('ix_documents_property_id'), 'documents', ['property_id'], unique=False)
    
    op.create_foreign_key(None, 'documents', 'users', ['uploaded_by_user_id'], ['id'])
    op.create_foreign_key(None, 'documents', 'clients', ['client_id'], ['id'])
    op.create_foreign_key(None, 'documents', 'properties', ['property_id'], ['id'])

    op.add_column('processes', sa.Column('property_id', sa.Integer(), nullable=True))
    op.add_column('processes', sa.Column('priority', sa.Enum('baixa', 'media', 'alta', 'critica', name='processpriority'), nullable=True))
    op.add_column('processes', sa.Column('urgency', sa.String(), nullable=True))
    op.add_column('processes', sa.Column('responsible_user_id', sa.Integer(), nullable=True))
    op.add_column('processes', sa.Column('destination_agency', sa.String(), nullable=True))
    op.add_column('processes', sa.Column('external_protocol_number', sa.String(), nullable=True))
    op.add_column('processes', sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('processes', sa.Column('due_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('processes', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('processes', sa.Column('ai_summary', sa.Text(), nullable=True))
    op.add_column('processes', sa.Column('risk_score', sa.Float(), nullable=True))
    op.add_column('processes', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    
    op.alter_column('processes', 'description', existing_type=sa.VARCHAR(), type_=sa.Text(), existing_nullable=True)
    
    op.create_index(op.f('ix_processes_property_id'), 'processes', ['property_id'], unique=False)
    op.create_foreign_key(None, 'processes', 'properties', ['property_id'], ['id'])
    op.create_foreign_key(None, 'processes', 'users', ['responsible_user_id'], ['id'])

def downgrade() -> None:
    pass
