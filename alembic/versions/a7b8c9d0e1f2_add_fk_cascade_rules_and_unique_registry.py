"""Add FK cascade/set-null rules and unique constraint on properties(tenant_id, registry_number).

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-04-04

Strategy:
- tenant_id -> RESTRICT (never delete tenant with data)
- process_id on child tables (tasks, documents, process_checklists) -> CASCADE
- process_id on proposals, contracts, communication_threads -> SET NULL (nullable, keep records)
- client_id (non-nullable) -> RESTRICT (prevent accidental orphan)
- client_id (nullable) -> SET NULL
- user_id references -> SET NULL
- proposal_id, template_id -> SET NULL
- thread_id (messages) -> CASCADE
- task_dependencies -> CASCADE

NOTE: If unique constraint fails due to duplicates, run:
  DELETE FROM properties WHERE id NOT IN (
    SELECT MIN(id) FROM properties GROUP BY tenant_id, registry_number
  );
"""
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None

# (table, constraint_name, column, ref_table, on_delete)
FK_RULES = [
    # --- users ---
    ("users", "users_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),

    # --- clients ---
    ("clients", "clients_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),

    # --- properties ---
    ("properties", "properties_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
    ("properties", "properties_client_id_fkey", "client_id", "clients", "RESTRICT"),

    # --- processes ---
    ("processes", "processes_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
    ("processes", "processes_client_id_fkey", "client_id", "clients", "RESTRICT"),
    ("processes", "processes_property_id_fkey", "property_id", "properties", "SET NULL"),
    ("processes", "processes_responsible_user_id_fkey", "responsible_user_id", "users", "SET NULL"),

    # --- tasks ---
    ("tasks", "tasks_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
    ("tasks", "tasks_process_id_fkey", "process_id", "processes", "CASCADE"),
    ("tasks", "tasks_property_id_fkey", "property_id", "properties", "SET NULL"),
    ("tasks", "tasks_document_id_fkey", "document_id", "documents", "SET NULL"),
    ("tasks", "tasks_assigned_to_user_id_fkey", "assigned_to_user_id", "users", "SET NULL"),
    ("tasks", "tasks_created_by_user_id_fkey", "created_by_user_id", "users", "SET NULL"),

    # --- task_dependencies ---
    ("task_dependencies", "task_dependencies_task_id_fkey", "task_id", "tasks", "CASCADE"),
    ("task_dependencies", "task_dependencies_depends_on_task_id_fkey", "depends_on_task_id", "tasks", "CASCADE"),

    # --- documents ---
    ("documents", "documents_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
    ("documents", "documents_process_id_fkey", "process_id", "processes", "CASCADE"),
    ("documents", "documents_client_id_fkey", "client_id", "clients", "SET NULL"),
    ("documents", "documents_property_id_fkey", "property_id", "properties", "SET NULL"),
    ("documents", "documents_uploaded_by_user_id_fkey", "uploaded_by_user_id", "users", "SET NULL"),

    # --- audit_logs ---
    ("audit_logs", "audit_logs_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
    ("audit_logs", "audit_logs_user_id_fkey", "user_id", "users", "SET NULL"),

    # --- ai_jobs ---
    ("ai_jobs", "ai_jobs_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
    ("ai_jobs", "ai_jobs_created_by_user_id_fkey", "created_by_user_id", "users", "SET NULL"),

    # --- checklist_templates ---
    ("checklist_templates", "checklist_templates_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),

    # --- process_checklists ---
    ("process_checklists", "process_checklists_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
    ("process_checklists", "process_checklists_process_id_fkey", "process_id", "processes", "CASCADE"),
    ("process_checklists", "process_checklists_template_id_fkey", "template_id", "checklist_templates", "SET NULL"),

    # --- proposals ---
    ("proposals", "proposals_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
    ("proposals", "proposals_process_id_fkey", "process_id", "processes", "SET NULL"),
    ("proposals", "proposals_client_id_fkey", "client_id", "clients", "RESTRICT"),
    ("proposals", "proposals_created_by_user_id_fkey", "created_by_user_id", "users", "SET NULL"),

    # --- contracts ---
    ("contracts", "contracts_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
    ("contracts", "contracts_proposal_id_fkey", "proposal_id", "proposals", "SET NULL"),
    ("contracts", "contracts_process_id_fkey", "process_id", "processes", "SET NULL"),
    ("contracts", "contracts_client_id_fkey", "client_id", "clients", "RESTRICT"),
    ("contracts", "contracts_template_id_fkey", "template_id", "contract_templates", "SET NULL"),
    ("contracts", "contracts_created_by_user_id_fkey", "created_by_user_id", "users", "SET NULL"),

    # --- contract_templates ---
    ("contract_templates", "contract_templates_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),

    # --- communication_threads ---
    ("communication_threads", "communication_threads_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
    ("communication_threads", "communication_threads_process_id_fkey", "process_id", "processes", "SET NULL"),
    ("communication_threads", "communication_threads_client_id_fkey", "client_id", "clients", "SET NULL"),

    # --- messages ---
    ("messages", "messages_thread_id_fkey", "thread_id", "communication_threads", "CASCADE"),
    ("messages", "messages_sender_id_fkey", "sender_id", "users", "SET NULL"),

    # --- workflow_templates ---
    ("workflow_templates", "workflow_templates_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),

    # --- prompt_templates ---
    ("prompt_templates", "prompt_templates_tenant_id_fkey", "tenant_id", "tenants", "RESTRICT"),
]


def upgrade():
    for table, constraint, column, ref_table, on_delete in FK_RULES:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            table,
            ref_table,
            [column],
            ["id"],
            ondelete=on_delete,
        )

    # Unique constraint: one registry_number per tenant
    op.create_unique_constraint(
        "uq_properties_tenant_registry",
        "properties",
        ["tenant_id", "registry_number"],
    )


def downgrade():
    op.drop_constraint("uq_properties_tenant_registry", "properties", type_="unique")

    # Restore FKs without ondelete (default RESTRICT / NO ACTION)
    for table, constraint, column, ref_table, _on_delete in reversed(FK_RULES):
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            table,
            ref_table,
            [column],
            ["id"],
        )
