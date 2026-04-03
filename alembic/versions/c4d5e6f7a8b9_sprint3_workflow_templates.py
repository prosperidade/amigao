"""sprint3_workflow_templates

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-04-02 00:00:00.000000

Fix: op.bulk_insert() em vez de op.execute() com JSON literals.
SQLAlchemy 2.0 interpreta `:N` (ex: "order":1) em strings raw como
bind parameters nomeados, causando InvalidRequestError.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None

# Tabela auxiliar para op.bulk_insert (não cria nada, só descreve colunas)
_wt = sa.table(
    'workflow_templates',
    sa.column('tenant_id', sa.Integer),
    sa.column('demand_type', sa.String),
    sa.column('name', sa.String),
    sa.column('description', sa.Text),
    sa.column('steps', sa.JSON),
    sa.column('is_active', sa.Boolean),
)

_TEMPLATES = [
    {
        'tenant_id': None,
        'demand_type': 'car',
        'name': 'Trilha CAR — Cadastro Ambiental Rural',
        'description': 'Sequência padrão para registro inicial no SICAR.',
        'steps': [
            {"order": 1, "title": "Levantamento documental", "description": "Coletar matrícula, CCIR, NIRF e documentos do proprietário.", "task_type": "documentacao", "estimated_days": 2, "depends_on": []},
            {"order": 2, "title": "Levantamento GPS / georreferenciamento", "description": "Realizar levantamento de campo com receptor GNSS para delimitação do imóvel.", "task_type": "campo", "estimated_days": 3, "depends_on": [1]},
            {"order": 3, "title": "Análise de passivo ambiental", "description": "Identificar APP, RL, embargo e passivo hídrico na propriedade.", "task_type": "analise", "estimated_days": 2, "depends_on": [2]},
            {"order": 4, "title": "Elaboração do CAR", "description": "Preencher e validar dados no módulo de cadastro do SICAR.", "task_type": "elaboracao", "estimated_days": 2, "depends_on": [3]},
            {"order": 5, "title": "Submissão no SICAR", "description": "Enviar o CAR e obter o recibo de protocolo.", "task_type": "protocolo", "estimated_days": 1, "depends_on": [4]},
            {"order": 6, "title": "Acompanhamento da análise", "description": "Monitorar status do CAR no portal e responder eventuais exigências.", "task_type": "acompanhamento", "estimated_days": 30, "depends_on": [5]},
            {"order": 7, "title": "Entrega do recibo CAR ao cliente", "description": "Enviar recibo e relatório final ao cliente.", "task_type": "entrega", "estimated_days": 1, "depends_on": [6]},
        ],
        'is_active': True,
    },
    {
        'tenant_id': None,
        'demand_type': 'retificacao_car',
        'name': 'Trilha Retificação CAR',
        'description': 'Sequência para retificação de CAR já inscrito.',
        'steps': [
            {"order": 1, "title": "Análise do CAR atual", "description": "Identificar inconsistências e pontos a corrigir.", "task_type": "analise", "estimated_days": 1, "depends_on": []},
            {"order": 2, "title": "Novo levantamento GPS (se necessário)", "description": "Refazer o levantamento de campo para correto georref.", "task_type": "campo", "estimated_days": 3, "depends_on": [1]},
            {"order": 3, "title": "Elaboração da retificação", "description": "Preencher módulo de retificação no SICAR com novos dados.", "task_type": "elaboracao", "estimated_days": 2, "depends_on": [2]},
            {"order": 4, "title": "Submissão da retificação", "description": "Enviar retificação e obter novo protocolo.", "task_type": "protocolo", "estimated_days": 1, "depends_on": [3]},
            {"order": 5, "title": "Acompanhamento da análise", "description": "Monitorar resultado da retificação no portal SICAR.", "task_type": "acompanhamento", "estimated_days": 20, "depends_on": [4]},
            {"order": 6, "title": "Entrega ao cliente", "description": "Enviar novo recibo e relatório ao cliente.", "task_type": "entrega", "estimated_days": 1, "depends_on": [5]},
        ],
        'is_active': True,
    },
    {
        'tenant_id': None,
        'demand_type': 'licenciamento',
        'name': 'Trilha Licenciamento Ambiental',
        'description': 'Sequência padrão para licenciamento ambiental junto ao órgão competente.',
        'steps': [
            {"order": 1, "title": "Diagnóstico ambiental preliminar", "description": "Avaliar porte do empreendimento e definir modalidade de licença (LP, LI, LO ou simplificada).", "task_type": "analise", "estimated_days": 3, "depends_on": []},
            {"order": 2, "title": "Coleta de documentação", "description": "Reunir estudos ambientais, ART, documentos do empreendedor e do terreno.", "task_type": "documentacao", "estimated_days": 5, "depends_on": [1]},
            {"order": 3, "title": "Elaboração dos estudos ambientais", "description": "Elaborar EIA/RIMA, RAS, PCA ou RAP conforme exigência do órgão.", "task_type": "elaboracao", "estimated_days": 15, "depends_on": [2]},
            {"order": 4, "title": "Protocolo junto ao órgão", "description": "Dar entrada no processo administrativo com todos os documentos.", "task_type": "protocolo", "estimated_days": 2, "depends_on": [3]},
            {"order": 5, "title": "Resposta a exigências", "description": "Atender exigências técnicas solicitadas pelo órgão licenciador.", "task_type": "acompanhamento", "estimated_days": 15, "depends_on": [4]},
            {"order": 6, "title": "Vistoria de campo (se aplicável)", "description": "Acompanhar vistoria do técnico do órgão na área.", "task_type": "campo", "estimated_days": 2, "depends_on": [5]},
            {"order": 7, "title": "Emissão e entrega da licença", "description": "Retirar a licença emitida e entregar ao cliente com orientações.", "task_type": "entrega", "estimated_days": 1, "depends_on": [6]},
        ],
        'is_active': True,
    },
    {
        'tenant_id': None,
        'demand_type': 'regularizacao_fundiaria',
        'name': 'Trilha Regularização Fundiária',
        'description': 'Sequência para regularização de imóvel rural sem registro ou com matrícula irregular.',
        'steps': [
            {"order": 1, "title": "Levantamento documental", "description": "Coletar CCIR, NIRF, planta, documentos pessoais e cadeia dominial.", "task_type": "documentacao", "estimated_days": 5, "depends_on": []},
            {"order": 2, "title": "Georreferenciamento certificado", "description": "Realizar o georreferenciamento conforme norma INCRA.", "task_type": "campo", "estimated_days": 5, "depends_on": [1]},
            {"order": 3, "title": "Elaboração do memorial descritivo", "description": "Elaborar memorial e planta georreferenciada conforme NBR.", "task_type": "elaboracao", "estimated_days": 3, "depends_on": [2]},
            {"order": 4, "title": "Certificação no SIGEF/INCRA", "description": "Solicitar certificação do georreferenciamento junto ao INCRA.", "task_type": "protocolo", "estimated_days": 30, "depends_on": [3]},
            {"order": 5, "title": "Registro em cartório", "description": "Dar entrada na matrícula/averbação no Cartório de Registro de Imóveis.", "task_type": "protocolo", "estimated_days": 15, "depends_on": [4]},
            {"order": 6, "title": "Acompanhamento do registro", "description": "Monitorar prazo e responder eventuais exigências do cartório.", "task_type": "acompanhamento", "estimated_days": 20, "depends_on": [5]},
            {"order": 7, "title": "Entrega do título ao cliente", "description": "Entregar certidão atualizada da matrícula ao cliente.", "task_type": "entrega", "estimated_days": 1, "depends_on": [6]},
        ],
        'is_active': True,
    },
    {
        'tenant_id': None,
        'demand_type': 'outorga',
        'name': 'Trilha Outorga de Uso da Água',
        'description': 'Sequência para obtenção de outorga de uso de recursos hídricos.',
        'steps': [
            {"order": 1, "title": "Diagnóstico da necessidade", "description": "Definir tipo de uso (captação superficial, subterrânea, lançamento) e vazão necessária.", "task_type": "analise", "estimated_days": 2, "depends_on": []},
            {"order": 2, "title": "Levantamento hidrológico", "description": "Coletar dados da bacia, disponibilidade hídrica e usos consuntivos existentes.", "task_type": "campo", "estimated_days": 3, "depends_on": [1]},
            {"order": 3, "title": "Elaboração do pedido de outorga", "description": "Preencher formulário, memorial de cálculo de vazão e projeto de captação.", "task_type": "elaboracao", "estimated_days": 3, "depends_on": [2]},
            {"order": 4, "title": "Protocolo junto à ANA/SEMA", "description": "Dar entrada no pedido de outorga no sistema do órgão gestor.", "task_type": "protocolo", "estimated_days": 1, "depends_on": [3]},
            {"order": 5, "title": "Acompanhamento e exigências", "description": "Monitorar o processo e responder exigências técnicas.", "task_type": "acompanhamento", "estimated_days": 30, "depends_on": [4]},
            {"order": 6, "title": "Emissão da portaria de outorga", "description": "Retirar portaria e entregar ao cliente com validade e condicionantes.", "task_type": "entrega", "estimated_days": 1, "depends_on": [5]},
        ],
        'is_active': True,
    },
    {
        'tenant_id': None,
        'demand_type': 'defesa',
        'name': 'Trilha Defesa Administrativa',
        'description': 'Sequência para defesa de auto de infração ou notificação ambiental.',
        'steps': [
            {"order": 1, "title": "Análise do auto de infração", "description": "Revisar os fundamentos legais, prazo recursal e tipo de infração.", "task_type": "analise", "estimated_days": 1, "depends_on": []},
            {"order": 2, "title": "Levantamento de evidências", "description": "Coletar documentos, laudos, fotos e testemunhos para embasar a defesa.", "task_type": "documentacao", "estimated_days": 3, "depends_on": [1]},
            {"order": 3, "title": "Elaboração da defesa administrativa", "description": "Redigir a peça de defesa com argumentação técnica e jurídica.", "task_type": "elaboracao", "estimated_days": 3, "depends_on": [2]},
            {"order": 4, "title": "Protocolo da defesa", "description": "Protocolar a defesa no órgão autuador dentro do prazo legal.", "task_type": "protocolo", "estimated_days": 1, "depends_on": [3]},
            {"order": 5, "title": "Acompanhamento do recurso", "description": "Monitorar o julgamento e elaborar recursos adicionais se necessário.", "task_type": "acompanhamento", "estimated_days": 15, "depends_on": [4]},
            {"order": 6, "title": "Resultado e entrega ao cliente", "description": "Comunicar o resultado e orientar sobre próximos passos.", "task_type": "entrega", "estimated_days": 1, "depends_on": [5]},
        ],
        'is_active': True,
    },
    {
        'tenant_id': None,
        'demand_type': 'compensacao',
        'name': 'Trilha Compensação / PRAD',
        'description': 'Sequência para elaboração e execução de Plano de Recuperação de Área Degradada.',
        'steps': [
            {"order": 1, "title": "Diagnóstico da área degradada", "description": "Realizar vistoria e levantamento fitossociológico da área a recuperar.", "task_type": "campo", "estimated_days": 3, "depends_on": []},
            {"order": 2, "title": "Elaboração do PRAD", "description": "Redigir o Plano de Recuperação com espécies nativas, cronograma e metas.", "task_type": "elaboracao", "estimated_days": 5, "depends_on": [1]},
            {"order": 3, "title": "Aprovação do PRAD pelo órgão", "description": "Protocolar o PRAD e aguardar aprovação do órgão competente.", "task_type": "protocolo", "estimated_days": 15, "depends_on": [2]},
            {"order": 4, "title": "Execução das medidas de recuperação", "description": "Plantar mudas, instalar cercas e executar as medidas previstas no PRAD.", "task_type": "campo", "estimated_days": 30, "depends_on": [3]},
            {"order": 5, "title": "Relatório de monitoramento", "description": "Elaborar relatório de monitoramento conforme cronograma do PRAD.", "task_type": "elaboracao", "estimated_days": 5, "depends_on": [4]},
            {"order": 6, "title": "Emissão de atestado de recuperação", "description": "Obter do órgão o atestado de cumprimento do PRAD.", "task_type": "entrega", "estimated_days": 1, "depends_on": [5]},
        ],
        'is_active': True,
    },
    {
        'tenant_id': None,
        'demand_type': 'exigencia_bancaria',
        'name': 'Trilha Exigência Bancária',
        'description': 'Sequência para atendimento de exigência ambiental de crédito rural.',
        'steps': [
            {"order": 1, "title": "Análise da exigência bancária", "description": "Identificar qual documento ambiental está sendo solicitado pelo banco.", "task_type": "analise", "estimated_days": 1, "depends_on": []},
            {"order": 2, "title": "Verificação de pendências ambientais", "description": "Checar CAR, passivos, embargos e situação do imóvel nos sistemas.", "task_type": "analise", "estimated_days": 1, "depends_on": [1]},
            {"order": 3, "title": "Regularização das pendências", "description": "Executar as ações necessárias para regularização (CAR, licença, etc.).", "task_type": "elaboracao", "estimated_days": 10, "depends_on": [2]},
            {"order": 4, "title": "Elaboração do laudo ou declaração", "description": "Emitir laudo técnico ambiental ou declaração de regularidade.", "task_type": "elaboracao", "estimated_days": 2, "depends_on": [3]},
            {"order": 5, "title": "Entrega ao banco e ao cliente", "description": "Encaminhar documentação ao banco e arquivar cópia para o cliente.", "task_type": "entrega", "estimated_days": 1, "depends_on": [4]},
        ],
        'is_active': True,
    },
]


def upgrade() -> None:
    op.create_table(
        'workflow_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('demand_type', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workflow_templates_demand_type', 'workflow_templates', ['demand_type'])
    op.create_index('ix_workflow_templates_id', 'workflow_templates', ['id'])
    op.create_index('ix_workflow_templates_tenant_id', 'workflow_templates', ['tenant_id'])

    op.bulk_insert(_wt, _TEMPLATES)


def downgrade() -> None:
    op.drop_index('ix_workflow_templates_tenant_id', table_name='workflow_templates')
    op.drop_index('ix_workflow_templates_id', table_name='workflow_templates')
    op.drop_index('ix_workflow_templates_demand_type', table_name='workflow_templates')
    op.drop_table('workflow_templates')
