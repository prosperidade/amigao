"""sprint4_proposals_contracts

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-04-02 01:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None

CONTRACT_TEMPLATES_SEED = [
    {
        "demand_type": "car",
        "name": "Contrato de Prestação de Serviços — CAR",
        "content": """CONTRATO DE PRESTAÇÃO DE SERVIÇOS AMBIENTAIS

CONTRATANTE: {{cliente.nome}}, CPF/CNPJ: {{cliente.cpf_cnpj}}, doravante denominado CONTRATANTE.

CONTRATADA: {{empresa.nome}}, inscrita no CNPJ {{empresa.cnpj}}, doravante denominada CONTRATADA.

OBJETO: A CONTRATADA obriga-se a prestar os seguintes serviços ao CONTRATANTE:
{{proposta.escopo}}

IMÓVEL RURAL: {{imovel.nome}}, localizado em {{imovel.municipio}}/{{imovel.uf}}, Matrícula nº {{imovel.matricula}}, área total de {{imovel.area_ha}} hectares.

VALOR TOTAL: R$ {{proposta.valor_total}}

CONDIÇÕES DE PAGAMENTO: {{proposta.condicoes_pagamento}}

PRAZO: Os serviços serão executados no prazo estimado de {{proposta.prazo_dias}} dias a partir da assinatura deste contrato.

OBRIGAÇÕES DA CONTRATANTE:
- Fornecer todos os documentos solicitados pela CONTRATADA no prazo acordado;
- Permitir acesso ao imóvel para levantamentos técnicos;
- Efetuar os pagamentos nas datas acordadas.

OBRIGAÇÕES DA CONTRATADA:
- Executar os serviços com técnica e diligência;
- Manter o CONTRATANTE informado sobre o andamento;
- Comunicar quaisquer obstáculos que possam impactar o prazo.

DISPOSIÇÕES GERAIS:
Este contrato é regido pelas leis brasileiras. As partes elegem o foro da comarca de {{empresa.municipio}} para dirimir eventuais litígios.

Data de emissão: {{contrato.data_emissao}}

_______________________________          _______________________________
CONTRATANTE                              CONTRATADA
{{cliente.nome}}                         {{empresa.nome}}
""",
    },
    {
        "demand_type": "licenciamento",
        "name": "Contrato de Prestação de Serviços — Licenciamento Ambiental",
        "content": """CONTRATO DE PRESTAÇÃO DE SERVIÇOS — LICENCIAMENTO AMBIENTAL

CONTRATANTE: {{cliente.nome}}, CPF/CNPJ: {{cliente.cpf_cnpj}}.

CONTRATADA: {{empresa.nome}}, CNPJ: {{empresa.cnpj}}.

OBJETO: Elaboração e acompanhamento do processo de licenciamento ambiental do empreendimento/atividade descrito abaixo:

{{proposta.escopo}}

LOCAL/EMPREENDIMENTO: {{imovel.nome}} — {{imovel.municipio}}/{{imovel.uf}}

VALOR: R$ {{proposta.valor_total}}

PAGAMENTO: {{proposta.condicoes_pagamento}}

PRAZO ESTIMADO: {{proposta.prazo_dias}} dias úteis após o protocolo do requerimento no órgão competente.

OBSERVAÇÕES: O prazo de análise pelo órgão licenciador não está sujeito ao controle da CONTRATADA e pode impactar o prazo total do processo.

Data de emissão: {{contrato.data_emissao}}

_______________________________          _______________________________
CONTRATANTE                              CONTRATADA
""",
    },
    {
        "demand_type": "regularizacao_fundiaria",
        "name": "Contrato de Prestação de Serviços — Regularização Fundiária",
        "content": """CONTRATO DE PRESTAÇÃO DE SERVIÇOS — REGULARIZAÇÃO FUNDIÁRIA

CONTRATANTE: {{cliente.nome}}, CPF/CNPJ: {{cliente.cpf_cnpj}}.

CONTRATADA: {{empresa.nome}}, CNPJ: {{empresa.cnpj}}.

OBJETO: Prestação de serviços de regularização fundiária do imóvel rural abaixo identificado:

Imóvel: {{imovel.nome}}
Localização: {{imovel.municipio}}/{{imovel.uf}}
Área: {{imovel.area_ha}} ha

ESCOPO DOS SERVIÇOS:
{{proposta.escopo}}

VALOR TOTAL: R$ {{proposta.valor_total}}

CONDIÇÕES DE PAGAMENTO: {{proposta.condicoes_pagamento}}

PRAZO: {{proposta.prazo_dias}} dias corridos.

Data de emissão: {{contrato.data_emissao}}

_______________________________          _______________________________
CONTRATANTE                              CONTRATADA
""",
    },
    {
        "demand_type": None,
        "name": "Contrato Genérico — Consultoria Ambiental",
        "content": """CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE CONSULTORIA AMBIENTAL

CONTRATANTE: {{cliente.nome}}, CPF/CNPJ: {{cliente.cpf_cnpj}}.

CONTRATADA: {{empresa.nome}}, CNPJ: {{empresa.cnpj}}.

OBJETO: Prestação de serviços de consultoria ambiental conforme escopo abaixo:

{{proposta.escopo}}

VALOR TOTAL: R$ {{proposta.valor_total}}

CONDIÇÕES DE PAGAMENTO: {{proposta.condicoes_pagamento}}

PRAZO ESTIMADO: {{proposta.prazo_dias}} dias.

NOTAS ADICIONAIS: {{proposta.notas}}

Data de emissão: {{contrato.data_emissao}}

_______________________________          _______________________________
CONTRATANTE                              CONTRATADA
{{cliente.nome}}                         {{empresa.nome}}
""",
    },
]


def upgrade() -> None:
    # ── contract_templates ──────────────────────────────────────────────────────
    op.create_table(
        'contract_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('demand_type', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('content_template', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_contract_templates_id', 'contract_templates', ['id'])
    op.create_index('ix_contract_templates_demand_type', 'contract_templates', ['demand_type'])

    # ── proposals ───────────────────────────────────────────────────────────────
    op.create_table(
        'proposals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('process_id', sa.Integer(), nullable=True),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('draft', 'sent', 'accepted', 'rejected', 'expired', name='proposalstatus'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('scope_items', sa.JSON(), nullable=False),
        sa.Column('total_value', sa.Float(), nullable=True),
        sa.Column('validity_days', sa.Integer(), nullable=True),
        sa.Column('payment_terms', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('complexity', sa.String(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['process_id'], ['processes.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_proposals_id', 'proposals', ['id'])
    op.create_index('ix_proposals_tenant_id', 'proposals', ['tenant_id'])
    op.create_index('ix_proposals_client_id', 'proposals', ['client_id'])
    op.create_index('ix_proposals_process_id', 'proposals', ['process_id'])

    # ── contracts ───────────────────────────────────────────────────────────────
    op.create_table(
        'contracts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('proposal_id', sa.Integer(), nullable=True),
        sa.Column('process_id', sa.Integer(), nullable=True),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'sent', 'signed', 'cancelled', name='contractstatus'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('pdf_storage_key', sa.String(), nullable=True),
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('signed_by_client', sa.Boolean(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['process_id'], ['processes.id']),
        sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id']),
        sa.ForeignKeyConstraint(['template_id'], ['contract_templates.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_contracts_id', 'contracts', ['id'])
    op.create_index('ix_contracts_tenant_id', 'contracts', ['tenant_id'])
    op.create_index('ix_contracts_client_id', 'contracts', ['client_id'])
    op.create_index('ix_contracts_process_id', 'contracts', ['process_id'])
    op.create_index('ix_contracts_proposal_id', 'contracts', ['proposal_id'])

    # Seed de templates de contrato globais
    for t in CONTRACT_TEMPLATES_SEED:
        demand_val = f"'{t['demand_type']}'" if t['demand_type'] else "NULL"
        content_escaped = t['content'].replace("'", "''")
        name_escaped = t['name'].replace("'", "''")
        op.execute(f"""
        INSERT INTO contract_templates (tenant_id, demand_type, name, content_template, is_active)
        VALUES (NULL, {demand_val}, '{name_escaped}', '{content_escaped}', TRUE)
        """)


def downgrade() -> None:
    op.drop_table('contracts')
    op.execute("DROP TYPE IF EXISTS contractstatus")
    op.drop_table('proposals')
    op.execute("DROP TYPE IF EXISTS proposalstatus")
    op.drop_table('contract_templates')
