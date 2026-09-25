"""Fechamento comercial (Incremento 5, ADR-074).

A cadeia comercial nasce da Rota validada: o Redator monta o relatório preliminar e a
especificação de escopo (`RedacaoComercial`), o Orçamento precifica cada passo com os
métodos do tenant (`Orcamento`, `OrcamentoItem`, `OrcamentoMetodo`). Tudo versionado:
gerar de novo é versão nova e a anterior fica `superada`, preservada.

Revisão e atualidade são eixos separados (Plano §5.1): `estado_revisao` guarda a decisão
humana; a atualidade (`vigente`/`desatualizado`) é LEITURA — a `base` gravada comparada à
atual (`app/services/comercial/atualidade.py`) — e nunca retrocede etapa.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import declared_attr, relationship
from sqlalchemy.sql import func

from app.models.base import Base

ESTADOS_REVISAO = ("proposta", "aprovada", "rejeitada")
TIPOS_REDACAO = ("relatorio_preliminar", "especificacao_escopo")
UNIDADES = ("hora", "fixo", "unidade")
ESCOLHAS = ("consultor", "regra", "padrao")


def _in(coluna: str, valores: tuple[str, ...]) -> str:
    return f"{coluna} IN (" + ",".join(f"'{v}'" for v in valores) + ")"


class _Revisavel:
    """Revisão humana + eixo de versão, comuns à redação e ao orçamento."""

    estado_revisao = Column(String(20), nullable=False, server_default="proposta", default="proposta")
    revisado_em = Column(DateTime(timezone=True))
    justificativa = Column(Text)
    superada_em = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @declared_attr
    def revisado_por_id(cls):
        return Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), index=True)

    @declared_attr
    def criado_por_id(cls):
        return Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), index=True)


class OrcamentoMetodo(Base):
    """Método e preço do tenant. Mudar preço é versão nova; a anterior fica."""

    __tablename__ = "orcamento_metodo"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    codigo = Column(String(60), nullable=False)
    versao = Column(Integer, nullable=False)
    nome = Column(String(200), nullable=False)
    unidade = Column(String(20), nullable=False)
    valor_unitario = Column(Numeric(12, 2), nullable=False)
    quantidade_padrao = Column(Numeric(10, 2), nullable=False, server_default="1", default=1)
    # Regras do motor (``rule_id``) cujo passo este método precifica por padrão.
    rule_ids = Column(ARRAY(String(60)), nullable=False, server_default="{}", default=list)
    padrao = Column(Boolean, nullable=False, server_default="false", default=False)
    ativo = Column(Boolean, nullable=False, server_default="true", default=True)
    criado_por_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "codigo", "versao", name="uq_orcamento_metodo_versao"),
        CheckConstraint(_in("unidade", UNIDADES), name="ck_orcamento_metodo_unidade"),
        CheckConstraint("valor_unitario >= 0", name="ck_orcamento_metodo_valor"),
        CheckConstraint("quantidade_padrao > 0", name="ck_orcamento_metodo_quantidade"),
    )


class RedacaoComercial(_Revisavel, Base):
    """Relatório preliminar ou especificação de escopo — Redator pré-contratação.

    ``conteudo``: ``{"secoes": [{"chave", "titulo", "afirmacoes": [{id, texto,
    evidencias: [{tipo, id, rotulo}]}]}], "limites": [...]}``. Toda afirmação tem
    evidência por ID resolvida no tenant (``app/services/comercial/evidencia.py``).
    """

    __tablename__ = "redacao_comercial"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False)
    versao = Column(Integer, nullable=False)
    rota_id = Column(Integer, ForeignKey("rotas.id", ondelete="SET NULL"), index=True)
    execucao_motor_id = Column(Integer, ForeignKey("execucao_motor.id", ondelete="RESTRICT"), index=True)
    conteudo = Column(JSONB, nullable=False)
    base = Column(JSONB, nullable=False)
    base_hash = Column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "process_id", "tipo", "versao", name="uq_redacao_comercial_versao"),
        CheckConstraint(_in("tipo", TIPOS_REDACAO), name="ck_redacao_comercial_tipo"),
        CheckConstraint(_in("estado_revisao", ESTADOS_REVISAO), name="ck_redacao_comercial_revisao"),
    )


class Orcamento(_Revisavel, Base):
    """Orçamento derivado da Rota validada: um item por passo faturável validado."""

    __tablename__ = "orcamento"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="CASCADE"), nullable=False, index=True)
    versao = Column(Integer, nullable=False)
    rota_id = Column(Integer, ForeignKey("rotas.id", ondelete="SET NULL"), index=True)
    escopo_id = Column(Integer, ForeignKey("redacao_comercial.id", ondelete="CASCADE"), nullable=False, index=True)
    total = Column(Numeric(14, 2), nullable=False)
    # Passos que NÃO entraram (removidos com motivo, direção) — o orçamento diz o que deixou de fora.
    fora = Column(JSONB, nullable=False, server_default="[]", default=list)
    # Estado do diagnóstico no momento da geração: registrado, nunca bloqueante (ruptura 4).
    ressalvas = Column(JSONB, nullable=False, server_default="[]", default=list)
    base = Column(JSONB, nullable=False)
    base_hash = Column(String(64), nullable=False)

    itens = relationship("OrcamentoItem", order_by="OrcamentoItem.ordem", cascade="all, delete-orphan",
                         back_populates="orcamento")

    __table_args__ = (
        UniqueConstraint("tenant_id", "process_id", "versao", name="uq_orcamento_versao"),
        CheckConstraint(_in("estado_revisao", ESTADOS_REVISAO), name="ck_orcamento_revisao"),
        CheckConstraint("total >= 0", name="ck_orcamento_total"),
    )


class OrcamentoItem(Base):
    """Um passo da Rota precificado. Título, fundamento e preço são FOTO da geração."""

    __tablename__ = "orcamento_item"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    orcamento_id = Column(Integer, ForeignKey("orcamento.id", ondelete="CASCADE"), nullable=False, index=True)
    rota_passo_id = Column(Integer, ForeignKey("rota_passos.id", ondelete="SET NULL"), index=True)
    metodo_id = Column(Integer, ForeignKey("orcamento_metodo.id", ondelete="RESTRICT"), nullable=False, index=True)
    escolha = Column(String(20), nullable=False)
    ordem = Column(Integer, nullable=False)
    descricao = Column(String, nullable=False)
    fundamento = Column(JSONB, nullable=False, server_default="{}", default=dict)
    unidade = Column(String(20), nullable=False)
    quantidade = Column(Numeric(10, 2), nullable=False)
    valor_unitario = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(14, 2), nullable=False)
    calculo = Column(String(200), nullable=False)

    orcamento = relationship("Orcamento", back_populates="itens")
    metodo = relationship("OrcamentoMetodo")

    __table_args__ = (
        CheckConstraint(_in("escolha", ESCOLHAS), name="ck_orcamento_item_escolha"),
        CheckConstraint("quantidade > 0 AND total >= 0", name="ck_orcamento_item_valores"),
    )


class OrcamentoEscolha(Base):
    """Escolha do consultor para um passo — sobrevive às versões seguintes do orçamento."""

    __tablename__ = "orcamento_escolha"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="CASCADE"), nullable=False, index=True)
    rota_passo_id = Column(Integer, ForeignKey("rota_passos.id", ondelete="CASCADE"), nullable=False, index=True)
    metodo_codigo = Column(String(60))
    quantidade = Column(Numeric(10, 2))
    autor_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "rota_passo_id", name="uq_orcamento_escolha_passo"),
        CheckConstraint("quantidade IS NULL OR quantidade > 0", name="ck_orcamento_escolha_quantidade"),
    )
