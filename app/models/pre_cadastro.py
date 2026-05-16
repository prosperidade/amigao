"""Sprint B1 — Waitlist do Regente Ambiental.

Lead anônimo capturado por POST /api/v1/waitlist a partir da página
/lista-de-espera.html em regenteambiental.com.br.

Sem tenant_id: o pré-cadastro existe antes de qualquer relação contratual
(LGPD: base legal é consentimento explícito via checkbox no form).

Modelo de exclusão LGPD (Art. 18 VI):
- ``deleted_at`` != NULL → soft-delete (opt-out exercido)
- ``purge_after`` no futuro → hard-delete agendado por Celery beat-scan
- Após hard-delete, a linha some e o e-mail volta a ser disponível.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class PreCadastro(Base):
    __tablename__ = "pre_cadastros"

    id = Column(Integer, primary_key=True, index=True)

    # Contato — PII identificável (LGPD)
    email = Column(String(254), unique=True, index=True, nullable=False)
    nome = Column(String(120), nullable=False)
    telefone = Column(String(20), nullable=True)

    # Perfil profissional
    perfil_profissional = Column(String(80), nullable=True)
    estado = Column(String(2), nullable=True)  # UF BR
    tipo_licenciamento = Column(String(120), nullable=True)
    volume_mensal = Column(Integer, nullable=True)  # processos/mês declarados
    ferramenta_atual = Column(String(120), nullable=True)

    # Validação de produto
    # preco_aceito: JSON com 4 chaves Van Westendorp (barato_demais, barato, caro, caro_demais)
    # Valores em BRL inteiros. Schema validado em app/schemas/pre_cadastro.py:PrecoVanWestendorp.
    preco_aceito = Column(PortableJSON, nullable=True)
    expectativa = Column(Text, nullable=True)
    deal_breaker = Column(Text, nullable=True)
    interesse_grupo = Column(Boolean, nullable=True, default=False)

    # Tracking de origem
    source = Column(String(80), nullable=True)
    utm_source = Column(String(120), nullable=True)
    utm_medium = Column(String(120), nullable=True)
    utm_campaign = Column(String(120), nullable=True)
    utm_term = Column(String(120), nullable=True)
    utm_content = Column(String(120), nullable=True)

    # Integração Resend (populada async pela task sync_resend_audience)
    resend_contact_id = Column(String(60), nullable=True, index=True)

    # LGPD
    consentimento_dado_em = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    purge_after = Column(DateTime(timezone=True), nullable=True, index=True)

    # Conversão (FK opcional populada quando o lead vira User)
    converted_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Auditoria
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index("ix_pre_cadastros_utm_campaign", "utm_source", "utm_campaign"),
        Index("ix_pre_cadastros_created_at", "created_at"),
    )
