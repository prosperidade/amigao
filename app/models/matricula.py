"""
Matrícula imobiliária — Ficha 01 (Dicionário de Extração do Intake), FASE 1.

Modelagem decidida pela dupla fundadora:
  1 Imóvel (Property) : N Matrículas (contíguas sob o mesmo CAR).

CAR / município / nome do imóvel ficam na ``Property``. Número da matrícula,
cartório / registro, código INCRA/SNCR, NIRF/CIB, geo (SIGEF) e área ficam aqui.
A área do imóvel é a SOMA das áreas das matrículas (derivada, não digitada) —
ver ``Property.area_total_matriculas()``.

Esta FASE 1 instala só o schema; o comportamento de extrator/auditor NÃO muda
(fases 2-3). Ver ``docs/trabalhos/ficha01_fase1.md`` e ADR-015.
"""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class Matricula(Base):
    """Matrícula imobiliária (seções 5.4-5.7 da Ficha 01)."""

    __tablename__ = "matriculas"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Matrícula é filha do imóvel: removida junto com a Property (CASCADE no DB).
    property_id = Column(
        Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Identificação registral
    numero_matricula = Column(String, nullable=True, index=True)
    cartorio = Column(String, nullable=True)
    registro_livro_folha_ficha = Column(String, nullable=True)

    # Cadastros rurais
    codigo_incra_sncr = Column(String, nullable=True)
    nirf_cib = Column(String, nullable=True)
    # Fase 0 (gap-analysis Ficha 07, item 8) — exercício (ano) do CCIR mais
    # recente lido para esta matrícula. CCIR é documento ANUAL — permite o
    # auditor emitir CCIR_EXERCICIO_ANTERIOR (catálogo já tinha o código,
    # faltava o emissor) quando `exercicio_ccir < ano corrente`.
    exercicio_ccir = Column(Integer, nullable=True)

    # Área decidida/consolidada da matrícula (a soma compõe a área do imóvel)
    area_ha = Column(Float, nullable=True)
    denominacao_imovel = Column(String, nullable=True)

    # Georreferenciamento (SIGEF)
    geo_certificacao_codigo = Column(String, nullable=True)
    geo_certificacao_status = Column(String, nullable=True)

    # Averbações e ônus (texto livre nesta fase; estruturação fica para depois)
    averbacao_app = Column(Text, nullable=True)
    averbacao_rl = Column(Text, nullable=True)
    onus_gravames = Column(Text, nullable=True)

    # Proprietários conforme a certidão: [{"nome": ..., "cpf": ...}, ...].
    # O cruzamento com Cliente é achado do auditor (fase 3), não aqui.
    proprietarios = Column(PortableJSON, nullable=True, default=list)

    # Sprint 3 (Selo) — proveniência por campo, espelha Client/Property:
    # {field: "raw"|"ai_extracted"|"human_validated"|"pendente_oficializacao"}.
    # Fecha o ponto cego que obrigava a consolidação ao fallback `old is not None`.
    field_sources = Column(PortableJSON, nullable=True, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    property = relationship("Property", back_populates="matriculas")
    tenant = relationship("Tenant")

    __table_args__ = (
        Index("ix_matriculas_tenant_property", "tenant_id", "property_id"),
    )
