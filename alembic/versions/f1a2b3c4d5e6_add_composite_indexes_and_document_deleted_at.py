"""Add composite indexes for performance and document deleted_at for soft delete.

Revision ID: f1a2b3c4d5e6
Revises: 024fe3f5dbeb
Create Date: 2026-04-04

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "024fe3f5dbeb"
branch_labels = None
depends_on = None


def upgrade():
    # --- Document soft delete column ---
    op.add_column(
        "documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Composite indexes ---

    # CRITICAL — workflow filtering
    op.create_index("ix_processes_tenant_status", "processes", ["tenant_id", "status"])
    op.create_index("ix_processes_tenant_due_date", "processes", ["tenant_id", "due_date"])
    op.create_index("ix_processes_deleted_at", "processes", ["deleted_at"])

    # CRITICAL — task board
    op.create_index("ix_tasks_tenant_status", "tasks", ["tenant_id", "status"])
    op.create_index("ix_tasks_assigned_status", "tasks", ["assigned_to_user_id", "status"])
    op.create_index("ix_tasks_tenant_due_date", "tasks", ["tenant_id", "due_date"])

    # HIGH — document pipeline
    op.create_index("ix_documents_tenant_ocr_status", "documents", ["tenant_id", "ocr_status"])
    op.create_index("ix_documents_tenant_doc_type", "documents", ["tenant_id", "document_type"])
    op.create_index("ix_documents_process_doc_type", "documents", ["process_id", "document_type"])
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])

    # MEDIUM — filtering
    op.create_index("ix_clients_tenant_status", "clients", ["tenant_id", "status"])
    op.create_index("ix_proposals_tenant_status", "proposals", ["tenant_id", "status"])
    op.create_index("ix_contracts_tenant_status", "contracts", ["tenant_id", "status"])

    # HIGH — audit queries
    op.create_index(
        "ix_audit_logs_tenant_entity_created",
        "audit_logs",
        ["tenant_id", "entity_type", "entity_id", "created_at"],
    )

    # HIGH — recent threads
    op.create_index(
        "ix_comm_threads_tenant_created",
        "communication_threads",
        ["tenant_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_comm_threads_tenant_created")
    op.drop_index("ix_audit_logs_tenant_entity_created")
    op.drop_index("ix_contracts_tenant_status")
    op.drop_index("ix_proposals_tenant_status")
    op.drop_index("ix_clients_tenant_status")
    op.drop_index("ix_documents_deleted_at")
    op.drop_index("ix_documents_process_doc_type")
    op.drop_index("ix_documents_tenant_doc_type")
    op.drop_index("ix_documents_tenant_ocr_status")
    op.drop_index("ix_tasks_tenant_due_date")
    op.drop_index("ix_tasks_assigned_status")
    op.drop_index("ix_tasks_tenant_status")
    op.drop_index("ix_processes_deleted_at")
    op.drop_index("ix_processes_tenant_due_date")
    op.drop_index("ix_processes_tenant_status")

    op.drop_column("documents", "deleted_at")
