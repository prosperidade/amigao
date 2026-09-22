"""Geometria como evidência (ADR-072): leitura, feição, medição, projeção e confronto.

Todas as tabelas são append-only (trigger ``rejeitar_mutacao_evidencia`` na
migration). ``Property.geom`` é só a projeção da última ``ProjecaoGeometria``.
"""
from datetime import UTC, datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint

from app.models.base import Base
from app.models.types import PortableJSON


class ArquivoGeo(Base):
    __tablename__ = "arquivo_geo"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=True)
    documento_id = Column(Integer, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    numero = Column(Integer, nullable=False)
    sha256_original = Column(String(64), nullable=True)  # ausente só quando os bytes não chegaram
    formato = Column(String(20), nullable=False)
    membro_lido = Column(String, nullable=True)
    inventario = Column(PortableJSON, nullable=False, default=dict)
    crs_origem = Column(String, nullable=True)
    estado = Column(String(10), nullable=False)  # lido | falha
    falha_codigo = Column(String(40), nullable=True)
    falha_detalhe = Column(Text, nullable=True)
    metodo_versao = Column(String(20), nullable=False)
    lido_por_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    lido_em = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    __table_args__ = (UniqueConstraint("documento_id", "numero"),)


class Feicao(Base):
    __tablename__ = "feicao"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    arquivo_geo_id = Column(Integer, ForeignKey("arquivo_geo.id", ondelete="RESTRICT"), nullable=False)
    ordem = Column(Integer, nullable=False)
    identificador_interno = Column(String, nullable=False)
    nome = Column(String, nullable=True)
    tipo = Column(String(20), nullable=False)  # poligono | multipoligono | linha | ponto
    srid_origem = Column(Integer, nullable=False)
    geom_original = Column(Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False), nullable=False)
    geom = Column(Geometry(geometry_type="GEOMETRY", srid=4674, spatial_index=False), nullable=False)
    valida = Column(Boolean, nullable=False)
    motivo_invalidade = Column(String, nullable=True)
    aneis_internos = Column(Integer, nullable=False, default=0)
    __table_args__ = (UniqueConstraint("arquivo_geo_id", "ordem"),)


class Medicao(Base):
    __tablename__ = "medicao"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False, index=True)
    grandeza = Column(String(20), nullable=False, default="area")
    objeto = Column(String(40), nullable=False, default="imovel_total")
    origem_tipo = Column(String(30), nullable=False)  # feicao_calculada | registro | declaracao_textual
    estado = Column(String(20), nullable=False)  # determinado | nao_determinado
    valor_ha = Column(Numeric(20, 8), nullable=True)
    motivo = Column(String, nullable=True)
    metodo = Column(String, nullable=False)
    metodo_versao = Column(String(20), nullable=False)
    crs_calculo = Column(String, nullable=True)
    motor_versao = Column(String, nullable=True)
    documento_id = Column(Integer, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    feicao_id = Column(Integer, ForeignKey("feicao.id", ondelete="RESTRICT"), nullable=True)
    evidence_version_id = Column(Integer, ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=True)
    predicado = Column(String, nullable=True)
    literal = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class ProjecaoGeometria(Base):
    __tablename__ = "projecao_geometria"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False)
    feicao_id = Column(Integer, ForeignKey("feicao.id", ondelete="RESTRICT"), nullable=False)
    regra = Column(String(40), nullable=True)
    autor_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    motivo = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class ConfrontoArea(Base):
    __tablename__ = "confronto_area"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False, index=True)
    execucao = Column(String(32), nullable=False, index=True)
    medicao_calculada_id = Column(Integer, ForeignKey("medicao.id", ondelete="RESTRICT"), nullable=False)
    medicao_referencia_id = Column(Integer, ForeignKey("medicao.id", ondelete="RESTRICT"), nullable=False)
    delta_ha = Column(Numeric(20, 8), nullable=True)
    denominador_regra = Column(String(40), nullable=False)
    denominador_ha = Column(Numeric(20, 8), nullable=True)
    percentual = Column(Numeric(20, 10), nullable=True)
    percentual_sobre_maior = Column(Numeric(20, 10), nullable=True)
    tolerancia_pct = Column(Float, nullable=False)
    tolerancia_origem = Column(String(80), nullable=False)
    resultado = Column(String(30), nullable=False)  # dentro_da_tolerancia | divergente | nao_calculavel
    grau = Column(String(20), nullable=False)
    metodo_versao = Column(String(20), nullable=False)
    executado_por_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
