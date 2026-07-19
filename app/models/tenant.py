from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    # Sprint R — teto mensal de gasto com IA (USD). NULL = usa default global.
    # 0 = ilimitado (tanto aqui quanto no default).
    ai_monthly_budget_usd = Column(Float, nullable=True)
    # S5-B — configuração do tenant. Guarda o "perfil emissor" (chave ``issuer``)
    # usado na proposta/contrato Mirante: razão social, CNPJ, endereço, responsável
    # técnico (nome/título/CREA), dados bancários, foro e condições comerciais
    # padrão. Sem o perfil, a geração do documento é BLOQUEADA (ver ADR-029 e
    # app/services/tenant_profile.py). Dados bancários do PRÓPRIO tenant (não do
    # cliente) — se a operação exigir cifra, plugar EncryptedString (dívida #27).
    settings = Column(PortableJSON, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
