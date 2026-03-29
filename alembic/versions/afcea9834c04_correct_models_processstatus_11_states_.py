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
    op.drop_index(op.f('ix_processes_property_id'), table_name='processes')
    op.alter_column('processes', 'description', existing_type=sa.Text(), type_=sa.VARCHAR(), existing_nullable=True)
    op.drop_column('processes', 'deleted_at')
    op.drop_column('processes', 'risk_score')
    op.drop_column('processes', 'ai_summary')
    op.drop_column('processes', 'closed_at')
    op.drop_column('processes', 'due_date')
    op.drop_column('processes', 'opened_at')
    op.drop_column('processes', 'external_protocol_number')
    op.drop_column('processes', 'destination_agency')
    op.drop_column('processes', 'responsible_user_id')
    op.drop_column('processes', 'urgency')
    op.drop_column('processes', 'priority')
    op.drop_column('processes', 'property_id')

    op.drop_index(op.f('ix_documents_property_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_client_id'), table_name='documents')
    op.execute("UPDATE documents SET s3_key = COALESCE(NULLIF(s3_key, ''), storage_key)")
    op.drop_constraint('documents_storage_key_key', 'documents', type_='unique')
    op.create_unique_constraint('documents_s3_key_key', 'documents', ['s3_key'])
    op.alter_column('documents', 's3_key', existing_type=sa.VARCHAR(), nullable=False)
    op.alter_column('documents', 'process_id', existing_type=sa.INTEGER(), nullable=False)
    op.drop_column('documents', 'uploaded_by_user_id')
    op.drop_column('documents', 'review_required')
    op.drop_column('documents', 'confidence_score')
    op.drop_column('documents', 'extraction_status')
    op.drop_column('documents', 'ocr_status')
    op.drop_column('documents', 'source')
    op.drop_column('documents', 'version_number')
    op.drop_column('documents', 'document_category')
    op.drop_column('documents', 'document_type')
    op.drop_column('documents', 'checksum_sha256')
    op.drop_column('documents', 'file_size_bytes')
    op.drop_column('documents', 'storage_provider')
    op.drop_column('documents', 'storage_key')
    op.drop_column('documents', 'extension')
    op.drop_column('documents', 'mime_type')
    op.drop_column('documents', 'original_file_name')
    op.drop_column('documents', 'property_id')
    op.drop_column('documents', 'client_id')

    op.drop_column('clients', 'deleted_at')
    op.drop_column('clients', 'extra_json')
    op.drop_column('clients', 'notes')
    op.drop_column('clients', 'source_channel')
    op.drop_column('clients', 'status')
    op.drop_column('clients', 'birth_date')
    op.drop_column('clients', 'secondary_phone')
    op.drop_column('clients', 'legal_name')
    op.drop_column('clients', 'client_type')

    op.drop_index(op.f('ix_properties_tenant_id'), table_name='properties')
    op.drop_index(op.f('ix_properties_id'), table_name='properties')
    op.drop_index(op.f('ix_properties_client_id'), table_name='properties')
    op.drop_table('properties')

    old_processstatus = postgresql.ENUM(
        'lead',
        'triagem',
        'diagnostico',
        'planejamento',
        'execucao',
        'protocolo',
        'aguardando_orgao',
        'pendencia_orgao',
        'arquivado',
        'cancelado',
        'iniciado',
        'em_analise',
        'aguardando_documentos',
        'em_protocolo',
        'aprovado',
        'pendente',
        'concluido',
        name='processstatus_old',
    )
    restored_processstatus = postgresql.ENUM(
        'iniciado',
        'em_analise',
        'aguardando_documentos',
        'em_protocolo',
        'aprovado',
        'pendente',
        'concluido',
        name='processstatus',
    )
    op.execute("ALTER TYPE processstatus RENAME TO processstatus_old")
    restored_processstatus.create(op.get_bind(), checkfirst=False)
    op.execute(
        """
        ALTER TABLE processes
        ALTER COLUMN status TYPE processstatus
        USING (
            CASE status::text
                WHEN 'lead' THEN 'iniciado'
                WHEN 'triagem' THEN 'em_analise'
                WHEN 'diagnostico' THEN 'em_analise'
                WHEN 'planejamento' THEN 'em_analise'
                WHEN 'execucao' THEN 'em_analise'
                WHEN 'protocolo' THEN 'em_protocolo'
                WHEN 'aguardando_orgao' THEN 'pendente'
                WHEN 'pendencia_orgao' THEN 'pendente'
                WHEN 'arquivado' THEN 'concluido'
                WHEN 'cancelado' THEN 'pendente'
                ELSE status::text
            END
        )::processstatus
        """
    )
    old_processstatus.drop(op.get_bind(), checkfirst=False)

    process_priority_enum = postgresql.ENUM('baixa', 'media', 'alta', 'critica', name='processpriority')
    ocr_status_enum = postgresql.ENUM('pending', 'processing', 'done', 'failed', 'not_required', name='ocrstatus')
    document_source_enum = postgresql.ENUM('upload_manual', 'email', 'whatsapp', 'integration', 'generated_ai', 'field_app', name='documentsource')
    client_status_enum = postgresql.ENUM('lead', 'active', 'inactive', 'delinquent', name='clientstatus')
    client_type_enum = postgresql.ENUM('pf', 'pj', name='clienttype')

    process_priority_enum.drop(op.get_bind(), checkfirst=True)
    ocr_status_enum.drop(op.get_bind(), checkfirst=True)
    document_source_enum.drop(op.get_bind(), checkfirst=True)
    client_status_enum.drop(op.get_bind(), checkfirst=True)
    client_type_enum.drop(op.get_bind(), checkfirst=True)
