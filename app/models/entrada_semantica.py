"""Identidades documentais; observações continuam em evidence_versions (ADR-070)."""
from datetime import UTC, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint

from app.models.base import Base
from app.models.types import PortableJSON


class DocumentoVersao(Base):
    __tablename__ = "documento_versao"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    documento_id = Column(Integer, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    numero = Column(Integer, nullable=False)
    sha256_original = Column(String(64), nullable=False)
    texto = Column(Text, nullable=False)
    sha256_texto = Column(String(64), nullable=False)
    metodo = Column(String, nullable=False)
    modelo = Column(String, nullable=True)
    parametros = Column(PortableJSON, nullable=False, default=dict)
    origem = Column(String, nullable=False)
    documento_origem_id = Column(Integer, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    paginas_lidas = Column(Integer, nullable=True)
    paginas_total = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    __table_args__ = (UniqueConstraint("documento_id", "numero"),)


class Fragmento(Base):
    __tablename__ = "fragmento"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    documento_versao_id = Column(Integer, ForeignKey("documento_versao.id", ondelete="RESTRICT"), nullable=False)
    pagina = Column(Integer, nullable=True)
    inicio = Column(Integer, nullable=False)
    fim = Column(Integer, nullable=False)
    trecho = Column(Text, nullable=False)
    sha256_texto = Column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint("documento_versao_id", "inicio", "fim"),)


class ClassificacaoDocumento(Base):
    __tablename__ = "classificacao_documento"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    documento_id = Column(Integer, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    versao = Column(Integer, nullable=False)
    tipo_original = Column(String, nullable=True)
    tipo_proposto = Column(String, nullable=False)
    tipo_revisado = Column(String, nullable=True)
    responsavel_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    motivo = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    __table_args__ = (UniqueConstraint("documento_id", "versao"),)


class Pessoa(Base):
    __tablename__ = "pessoa"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    nome = Column(String, nullable=False)
    natureza = Column(String, nullable=False)
    aliases = Column(PortableJSON, nullable=False, default=list)
    origem_observacao_id = Column(Integer, ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False, unique=True)
    # Estado de domínio declarado; K/R permanecem na evidência referenciada.
    estado = Column(String, nullable=True)
    estado_fundamento_id = Column(Integer, ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=True)


class PessoaIdentificador(Base):
    __tablename__ = "pessoa_identificador"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    pessoa_id = Column(Integer, ForeignKey("pessoa.id", ondelete="RESTRICT"), nullable=False)
    tipo = Column(String, nullable=False)
    valor = Column(String, nullable=False)
    fundamento_id = Column(Integer, ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False)
    estado_confirmacao = Column(String, nullable=False, default="declarado")


class Espolio(Base):
    __tablename__ = "espolio"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    falecido_id = Column(Integer, ForeignKey("pessoa.id", ondelete="RESTRICT"), nullable=False)
    inventario = Column(String, nullable=True)
    fundamento_id = Column(Integer, ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False)


class Serventia(Base):
    __tablename__ = "serventia"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    nome = Column(String, nullable=False)
    cns = Column(String, nullable=True)
    motivo_cns_ausente = Column(String, nullable=True)
    localidade = Column(String, nullable=True)
    especialidade = Column(String, nullable=False, default="registro_imoveis")
    documento_origem_id = Column(Integer, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)


class AtoRegistral(Base):
    __tablename__ = "ato_registral"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    process_id = Column(Integer, nullable=False)
    serventia_id = Column(Integer, ForeignKey("serventia.id", ondelete="RESTRICT"), nullable=False)
    matricula_numero = Column(String, nullable=False)
    rotulo = Column(String, nullable=False)
    especie = Column(String, nullable=False)
    natureza = Column(String, nullable=False)
    data_ato = Column(Date, nullable=True)
    precisao_data = Column(String, nullable=False, default="desconhecida")
    ordem_fonte = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "process_id", "serventia_id", "matricula_numero", "rotulo"),)


class Participacao(Base):
    __tablename__ = "participacao"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    process_id = Column(Integer, nullable=False)
    pessoa_id = Column(Integer, ForeignKey("pessoa.id", ondelete="RESTRICT"), nullable=True)
    espolio_id = Column(Integer, ForeignKey("espolio.id", ondelete="RESTRICT"), nullable=True)
    ato_id = Column(Integer, ForeignKey("ato_registral.id", ondelete="RESTRICT"), nullable=True)
    documento_id = Column(Integer, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    caso_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=True)
    papel = Column(String, nullable=False)
    vocabulario_versao = Column(String, nullable=False, default="071.1")
    estado_confirmacao = Column(String, nullable=False, default="declarado")
    fundamento_id = Column(Integer, ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False)
    representado_pessoa_id = Column(Integer, ForeignKey("pessoa.id", ondelete="RESTRICT"), nullable=True)
    representado_espolio_id = Column(Integer, ForeignKey("espolio.id", ondelete="RESTRICT"), nullable=True)
    alcance = Column(String, nullable=True)
    inicio = Column(Date, nullable=True)
    fim = Column(Date, nullable=True)
    fracao = Column(Numeric(18, 12), nullable=True)


class RelacaoAto(Base):
    __tablename__ = "relacao_ato"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    process_id = Column(Integer, nullable=False)
    origem_id = Column(Integer, ForeignKey("ato_registral.id", ondelete="RESTRICT"), nullable=False)
    destino_id = Column(Integer, ForeignKey("ato_registral.id", ondelete="RESTRICT"), nullable=False)
    tipo = Column(String, nullable=False)
    fundamento_id = Column(Integer, ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False)
