"""documents.ocr_error: motivo legível do OCR falho (fim do failed silencioso)

Adiciona `documents.ocr_error` (String nullable) para registrar a causa do último
OCR falho (storage, formato não suportado, todas as cascatas falharam, etc.).
Limpo no sucesso. Habilita a UI a mostrar "não foi possível ler: motivo" e o
caminho de reprocesso.

Revision ID: b2c3d4e5f6a7
Revises: a1f2c3d4e5f6
Create Date: 2026-06-06

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1f2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("documents")}
    if "ocr_error" not in cols:
        op.add_column("documents", sa.Column("ocr_error", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("documents")}
    if "ocr_error" in cols:
        op.drop_column("documents", "ocr_error")
