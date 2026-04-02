"""Sprint 1 - Intake fields and checklist tables

Revision ID: a1b2c3d4e5f6
Revises: f2a1c4b6d8e9
Create Date: 2026-04-02 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f2a1c4b6d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enums novos ---
    demand_type_enum = postgresql.ENUM(
        "car", "retificacao_car", "licenciamento", "regularizacao_fundiaria",
        "outorga", "defesa", "compensacao", "exigencia_bancaria", "prad",
        "misto", "nao_identificado",
        name="demandtype",
    )
    demand_type_enum.create(op.get_bind(), checkfirst=True)

    intake_source_enum = postgresql.ENUM(
        "whatsapp", "email", "presencial", "banco",
        "cooperativa", "parceiro", "indicacao", "site",
        name="intakesource",
    )
    intake_source_enum.create(op.get_bind(), checkfirst=True)

    # --- Novos campos em processes ---
    op.add_column("processes", sa.Column("intake_source", sa.Enum(
        "whatsapp", "email", "presencial", "banco",
        "cooperativa", "parceiro", "indicacao", "site",
        name="intakesource",
    ), nullable=True))
    op.add_column("processes", sa.Column("demand_type", sa.Enum(
        "car", "retificacao_car", "licenciamento", "regularizacao_fundiaria",
        "outorga", "defesa", "compensacao", "exigencia_bancaria", "prad",
        "misto", "nao_identificado",
        name="demandtype",
    ), nullable=True))
    op.add_column("processes", sa.Column("initial_diagnosis", sa.Text(), nullable=True))
    op.add_column("processes", sa.Column("suggested_checklist_template", sa.String(), nullable=True))
    op.add_column("processes", sa.Column("intake_notes", sa.Text(), nullable=True))

    # --- Tabela checklist_templates ---
    op.create_table(
        "checklist_templates",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("demand_type", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("items", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # --- Tabela process_checklists ---
    op.create_table(
        "process_checklists",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("processes.id"), nullable=False, index=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("checklist_templates.id"), nullable=True),
        sa.Column("items", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    # process_id é único por processo (1 checklist ativo por processo)
    op.create_unique_constraint("uq_process_checklists_process_id", "process_checklists", ["process_id"])

    # --- Seed de templates globais (demand_type por tipo de demanda) ---
    op.execute("""
        INSERT INTO checklist_templates (demand_type, name, description, items, is_active) VALUES
        ('car', 'Checklist CAR', 'Documentos necessários para regularização do CAR', '[
            {"id": "car_numero", "label": "Número do CAR", "doc_type": "car", "category": "ambiental", "required": true},
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": true},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": true},
            {"id": "documento_proprietario", "label": "Documento do Proprietário (RG/CPF)", "doc_type": "doc_pessoal", "category": "pessoal", "required": true},
            {"id": "caf", "label": "CAF (Cadastro Agricultor Familiar)", "doc_type": "caf", "category": "fundiario", "required": false},
            {"id": "mapa_imovel", "label": "Mapa/Shapefile do Imóvel", "doc_type": "mapa", "category": "geoespacial", "required": false},
            {"id": "laudo_anterior", "label": "Laudo Ambiental Anterior", "doc_type": "laudo", "category": "ambiental", "required": false}
        ]'::json, true),
        ('retificacao_car', 'Checklist Retificação CAR', 'Documentos para retificação de CAR', '[
            {"id": "car_atual", "label": "CAR Atual (número e comprovante)", "doc_type": "car", "category": "ambiental", "required": true},
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": true},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": true},
            {"id": "notificacao_orgao", "label": "Notificação do Órgão (se houver)", "doc_type": "notificacao", "category": "administrativo", "required": false},
            {"id": "mapa_atual", "label": "Mapa/Shapefile Corrigido", "doc_type": "mapa", "category": "geoespacial", "required": true}
        ]'::json, true),
        ('licenciamento', 'Checklist Licenciamento Ambiental', 'Documentos para licenciamento ambiental', '[
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": true},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": true},
            {"id": "car", "label": "CAR regularizado", "doc_type": "car", "category": "ambiental", "required": true},
            {"id": "licenca_anterior", "label": "Licença Anterior (se houver)", "doc_type": "licenca", "category": "administrativo", "required": false},
            {"id": "croqui_atividade", "label": "Croqui ou Planta da Atividade", "doc_type": "planta", "category": "tecnico", "required": false},
            {"id": "doc_proprietario", "label": "Documento do Proprietário", "doc_type": "doc_pessoal", "category": "pessoal", "required": true}
        ]'::json, true),
        ('regularizacao_fundiaria', 'Checklist Regularização Fundiária', 'Documentos para regularização fundiária', '[
            {"id": "contrato_compra", "label": "Contrato de Compra e Venda", "doc_type": "contrato", "category": "fundiario", "required": false},
            {"id": "certidao_matricula", "label": "Certidão de Matrícula ou Transcrição", "doc_type": "matricula", "category": "fundiario", "required": false},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": false},
            {"id": "car", "label": "CAR (se houver)", "doc_type": "car", "category": "ambiental", "required": false},
            {"id": "doc_proprietario", "label": "Documentos do Possuidor/Proprietário", "doc_type": "doc_pessoal", "category": "pessoal", "required": true},
            {"id": "declaracao_posse", "label": "Declaração de Posse ou Testemunhos", "doc_type": "declaracao", "category": "fundiario", "required": false}
        ]'::json, true),
        ('outorga', 'Checklist Outorga de Água', 'Documentos para outorga de uso de recursos hídricos', '[
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": true},
            {"id": "car", "label": "CAR", "doc_type": "car", "category": "ambiental", "required": true},
            {"id": "outorga_anterior", "label": "Outorga Anterior (se houver)", "doc_type": "outorga", "category": "administrativo", "required": false},
            {"id": "croqui_captacao", "label": "Croqui do Ponto de Captação", "doc_type": "planta", "category": "tecnico", "required": false},
            {"id": "doc_proprietario", "label": "Documento do Proprietário", "doc_type": "doc_pessoal", "category": "pessoal", "required": true}
        ]'::json, true),
        ('defesa', 'Checklist Defesa Administrativa', 'Documentos para defesa de auto de infração', '[
            {"id": "auto_infracao", "label": "Auto de Infração / Notificação", "doc_type": "auto_infracao", "category": "administrativo", "required": true},
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": true},
            {"id": "car", "label": "CAR", "doc_type": "car", "category": "ambiental", "required": true},
            {"id": "fotos_area", "label": "Fotos Atuais da Área", "doc_type": "foto", "category": "tecnico", "required": true},
            {"id": "doc_proprietario", "label": "Procuração / Documento do Proprietário", "doc_type": "doc_pessoal", "category": "pessoal", "required": true},
            {"id": "laudo_anterior", "label": "Laudo ou Relatório Anterior da Área", "doc_type": "laudo", "category": "ambiental", "required": false}
        ]'::json, true),
        ('compensacao', 'Checklist Compensação / PRAD', 'Documentos para compensação ambiental ou PRAD', '[
            {"id": "car", "label": "CAR", "doc_type": "car", "category": "ambiental", "required": true},
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": true},
            {"id": "exigencia_orgao", "label": "Exigência do Órgão (se houver)", "doc_type": "notificacao", "category": "administrativo", "required": false},
            {"id": "fotos_area_degradada", "label": "Fotos da Área Degradada", "doc_type": "foto", "category": "tecnico", "required": true},
            {"id": "laudo_solo", "label": "Laudo de Solo (se houver)", "doc_type": "laudo", "category": "ambiental", "required": false}
        ]'::json, true),
        ('exigencia_bancaria', 'Checklist Exigência Bancária', 'Documentos para atender exigências de crédito rural', '[
            {"id": "carta_exigencia_banco", "label": "Carta de Exigência do Banco", "doc_type": "carta_banco", "category": "bancario", "required": true},
            {"id": "car", "label": "CAR (atual ou a regularizar)", "doc_type": "car", "category": "ambiental", "required": true},
            {"id": "caf", "label": "DAP/CAF", "doc_type": "caf", "category": "fundiario", "required": false},
            {"id": "matricula", "label": "Matrícula do Imóvel", "doc_type": "matricula", "category": "fundiario", "required": true},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir", "category": "fundiario", "required": true}
        ]'::json, true)
    """)


def downgrade() -> None:
    op.drop_table("process_checklists")
    op.drop_table("checklist_templates")

    op.drop_column("processes", "intake_notes")
    op.drop_column("processes", "suggested_checklist_template")
    op.drop_column("processes", "initial_diagnosis")
    op.drop_column("processes", "demand_type")
    op.drop_column("processes", "intake_source")

    op.execute("DROP TYPE IF EXISTS demandtype")
    op.execute("DROP TYPE IF EXISTS intakesource")
