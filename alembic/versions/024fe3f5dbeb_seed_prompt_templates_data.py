"""seed prompt_templates data

Revision ID: 024fe3f5dbeb
Revises: d7f9a24dd5a7
Create Date: 2026-04-03 15:36:42.030946

Migra os prompts hardcoded de llm_classifier.py e document_extractor.py
para a tabela prompt_templates como v1 global (tenant_id=NULL).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '024fe3f5dbeb'
down_revision: Union[str, Sequence[str], None] = 'd7f9a24dd5a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Table reference for bulk_insert
prompt_templates = sa.table(
    'prompt_templates',
    sa.column('tenant_id', sa.Integer),
    sa.column('slug', sa.String),
    sa.column('category', sa.String),
    sa.column('role', sa.String),
    sa.column('version', sa.Integer),
    sa.column('content', sa.Text),
    sa.column('input_schema', sa.JSON),
    sa.column('output_schema', sa.JSON),
    sa.column('is_active', sa.Boolean),
)

SEED_SLUGS = [
    "classify_demand_system",
    "classify_demand_user",
    "extract_document_system",
    "extract_matricula",
    "extract_car",
    "extract_ccir",
    "extract_auto_infracao",
    "extract_licenca",
    "extract_default",
]

_CLASSIFY_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["demand_type", "confidence"],
    "properties": {
        "demand_type": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "diagnosis": {"type": "string"},
        "urgency": {"type": ["string", "null"]},
        "relevant_agencies": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
}

_EXTRACT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "confidence": {"type": "object"},
    },
}


def upgrade() -> None:
    """Seed prompt_templates with hardcoded prompts from services."""
    rows = [
        # --- Classifier ---
        {
            "tenant_id": None,
            "slug": "classify_demand_system",
            "category": "classify",
            "role": "system",
            "version": 1,
            "content": (
                "Voce e um especialista em regularizacao ambiental rural brasileira.\n"
                "Sua tarefa e classificar a demanda de um cliente rural e retornar um JSON estruturado.\n\n"
                "Tipos de demanda validos:\n"
                "- car: Cadastro Ambiental Rural\n"
                "- retificacao_car: Retificacao de CAR\n"
                "- licenciamento: Licenciamento Ambiental\n"
                "- regularizacao_fundiaria: Regularizacao Fundiaria\n"
                "- outorga: Outorga de Uso de Agua\n"
                "- defesa: Defesa Administrativa / Auto de Infracao\n"
                "- compensacao: Compensacao / PRAD\n"
                "- exigencia_bancaria: Exigencia Bancaria / Credito Rural\n"
                "- misto: Demanda Mista\n"
                "- nao_identificado: Nao Identificado\n\n"
                "Retorne APENAS um JSON valido com esta estrutura:\n"
                "{\n"
                '  "demand_type": "<tipo>",\n'
                '  "confidence": "high" | "medium" | "low",\n'
                '  "diagnosis": "<texto de 2-4 frases explicando a situacao>",\n'
                '  "urgency": null | "alta" | "critica",\n'
                '  "relevant_agencies": ["SEMA", "IBAMA", ...],\n'
                '  "next_steps": ["passo 1", "passo 2", ...]\n'
                "}"
            ),
            "input_schema": None,
            "output_schema": _CLASSIFY_OUTPUT_SCHEMA,
            "is_active": True,
        },
        {
            "tenant_id": None,
            "slug": "classify_demand_user",
            "category": "classify",
            "role": "user",
            "version": 1,
            "content": (
                "Classifique esta demanda ambiental:\n\n"
                "DESCRICAO: {description}\n"
                "CANAL: {channel}\n"
                "URGENCIA INFORMADA: {urgency}\n\n"
                "Retorne apenas o JSON."
            ),
            "input_schema": {
                "type": "object",
                "required": ["description"],
                "properties": {
                    "description": {"type": "string"},
                    "channel": {"type": "string"},
                    "urgency": {"type": "string"},
                },
            },
            "output_schema": _CLASSIFY_OUTPUT_SCHEMA,
            "is_active": True,
        },
        # --- Extractor system ---
        {
            "tenant_id": None,
            "slug": "extract_document_system",
            "category": "extract",
            "role": "system",
            "version": 1,
            "content": (
                "Voce e um especialista em documentos fundiarios e ambientais brasileiros.\n"
                "Extraia os campos solicitados do texto do documento e retorne APENAS um JSON valido.\n"
                "Para campos nao encontrados, use null.\n"
                'Inclua um campo "confidence" por campo extraido: "high" | "medium" | "low".\n'
            ),
            "input_schema": None,
            "output_schema": _EXTRACT_OUTPUT_SCHEMA,
            "is_active": True,
        },
        # --- Extractor per doc-type ---
        {
            "tenant_id": None,
            "slug": "extract_matricula",
            "category": "extract",
            "role": "user",
            "version": 1,
            "content": (
                "Extraia do texto desta matricula de imovel:\n"
                "{\n"
                '  "numero_matricula": null, "cartorio": null, "comarca": null, "uf": null,\n'
                '  "proprietario_nome": null, "proprietario_cpf_cnpj": null,\n'
                '  "area_hectares": null, "denominacao_imovel": null, "municipio": null,\n'
                '  "descricao_limites": null, "data_registro": null, "confidence": {}\n'
                "}\n"
                "TEXTO DO DOCUMENTO:\n{text}"
            ),
            "input_schema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
            "output_schema": _EXTRACT_OUTPUT_SCHEMA,
            "is_active": True,
        },
        {
            "tenant_id": None,
            "slug": "extract_car",
            "category": "extract",
            "role": "user",
            "version": 1,
            "content": (
                "Extraia do texto deste documento do CAR (Cadastro Ambiental Rural):\n"
                "{\n"
                '  "numero_car": null, "situacao": null, "cpf_cnpj_proprietario": null,\n'
                '  "nome_proprietario": null, "denominacao_imovel": null, "municipio": null,\n'
                '  "uf": null, "area_total_ha": null, "area_app_ha": null,\n'
                '  "area_reserva_legal_ha": null, "data_inscricao": null, "pendencias": null,\n'
                '  "confidence": {}\n'
                "}\n"
                "TEXTO DO DOCUMENTO:\n{text}"
            ),
            "input_schema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
            "output_schema": _EXTRACT_OUTPUT_SCHEMA,
            "is_active": True,
        },
        {
            "tenant_id": None,
            "slug": "extract_ccir",
            "category": "extract",
            "role": "user",
            "version": 1,
            "content": (
                "Extraia do texto deste CCIR (Certificado de Cadastro de Imovel Rural):\n"
                "{\n"
                '  "numero_ccir": null, "nirf": null, "denominacao_imovel": null,\n'
                '  "municipio": null, "uf": null, "area_total_ha": null,\n'
                '  "fracao_minima_ha": null, "proprietario_nome": null,\n'
                '  "proprietario_cpf_cnpj": null, "data_emissao": null, "confidence": {}\n'
                "}\n"
                "TEXTO DO DOCUMENTO:\n{text}"
            ),
            "input_schema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
            "output_schema": _EXTRACT_OUTPUT_SCHEMA,
            "is_active": True,
        },
        {
            "tenant_id": None,
            "slug": "extract_auto_infracao",
            "category": "extract",
            "role": "user",
            "version": 1,
            "content": (
                "Extraia do texto deste auto de infracao ambiental:\n"
                "{\n"
                '  "numero_auto": null, "orgao_autuante": null, "data_autuacao": null,\n'
                '  "infrator_nome": null, "infrator_cpf_cnpj": null,\n'
                '  "artigo_infringido": null, "descricao_infracao": null,\n'
                '  "valor_multa": null, "prazo_defesa_dias": null, "embargo": null,\n'
                '  "municipio": null, "uf": null, "confidence": {}\n'
                "}\n"
                "TEXTO DO DOCUMENTO:\n{text}"
            ),
            "input_schema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
            "output_schema": _EXTRACT_OUTPUT_SCHEMA,
            "is_active": True,
        },
        {
            "tenant_id": None,
            "slug": "extract_licenca",
            "category": "extract",
            "role": "user",
            "version": 1,
            "content": (
                "Extraia do texto desta licenca ambiental:\n"
                "{\n"
                '  "numero_licenca": null, "tipo_licenca": null, "orgao_emissor": null,\n'
                '  "empreendimento": null, "cnpj_empreendimento": null, "atividade": null,\n'
                '  "municipio": null, "uf": null, "data_emissao": null,\n'
                '  "data_validade": null, "condicionantes_count": null, "confidence": {}\n'
                "}\n"
                "TEXTO DO DOCUMENTO:\n{text}"
            ),
            "input_schema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
            "output_schema": _EXTRACT_OUTPUT_SCHEMA,
            "is_active": True,
        },
        {
            "tenant_id": None,
            "slug": "extract_default",
            "category": "extract",
            "role": "user",
            "version": 1,
            "content": (
                "Extraia os principais campos identificaveis deste documento ambiental/fundiario.\n"
                'Retorne um JSON com os campos encontrados e um campo "confidence" por campo.\n'
                "TEXTO DO DOCUMENTO:\n{text}"
            ),
            "input_schema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
            "output_schema": _EXTRACT_OUTPUT_SCHEMA,
            "is_active": True,
        },
    ]

    op.bulk_insert(prompt_templates, rows)


def downgrade() -> None:
    """Remove seeded prompt_templates."""
    for slug in SEED_SLUGS:
        op.execute(
            sa.text("DELETE FROM prompt_templates WHERE slug = :slug AND version = 1 AND tenant_id IS NULL"),
            {"slug": slug},
        )
