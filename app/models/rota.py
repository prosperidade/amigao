"""Modelos `Rota` e `RotaPasso` — Rota Regulatória (E5, Sprint 2).

Onde o **caminho regulatório** vira entidade editável. Hoje a ``LegislacaoAgent``
emite ``etapas`` (list[Etapa]) presas dentro do JSON do ``AIJob`` — efêmeras,
sem tela, perdidas ao recarregar (diagnóstico read-only anterior). Esta entidade
**materializa** esses passos como um snapshot que o consultor reordena, classifica
e **assina** (Princípio 1: a IA propõe; o humano decide e assina).

Decisões travadas (André, Ficha 07 §8.1 e §9):

- **DEMAND_TYPE-DRIVEN**: a Rota é uma por ``(tenant, process, demand_type)``.
  A ``LegislacaoAgent`` hoje keia por ``demand_type`` (não pelos passivos do
  auditor). Persistimos o que ela emite HOJE — religar ``auditor→legislacao`` é
  follow-on nomeado (REGISTRO_DIVIDAS), não reescrita agora.
- **LER O TIPADO**: a materialização lê ``EnquadramentoRegulatorioContent.etapas``
  (``Etapa`` tipado, com ``sources``+``prazo_fonte``), NUNCA o bruto top-level
  (``legislacao.py:719-723`` ``"etapas": list(etapas_raw)``). Ver
  ``app/services/rota_materializer.py``.
- **NENHUM PASSO SEM NORMA — na VALIDAÇÃO, não na geração** (radar-não-cancela):
  passo sem fonte entra marcado ``prazo_fonte="estimativa_profissional"`` /
  ``sources=[sem_fonte]``; o consultor reconhece ao validar. A geração nunca
  recusa um passo por falta de norma.
- **CLASSIFICAÇÃO obrigatória pra validar** (Ficha §8.1): cada passo é
  ``item_proposta`` (faturável) ou ``direcao`` (orientação) — ``NULL`` até o
  consultor decidir; um passo só valida com classificação preenchida.
- **dedupe_key é HIGIENE, não oráculo** (dívida #48): constraint desde o commit
  1, mas a reconciliação é **mediada por humano** — a chave só evita duplicar o
  óbvio; nunca rejeita passo legítimo distinto. Espelha ``Acao.dedupe_key`` /
  ADR-016.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RotaStatus(str, enum.Enum):
    """Ciclo de vida do snapshot da Rota.

    - ``proposta``      — recém-materializada pela IA, aguardando trabalho do
      consultor.
    - ``em_validacao``  — consultor começou a validar passos (reservado; a UI
      pode manter ``proposta`` até fechar — mantido para telemetria futura).
    - ``validada``      — consultor fechou a rota (todos os passos validados +
      classificados). Assinatura registrada no AuditLog (hash chain).
    - ``desatualizada`` — a IA re-rodou e trouxe diferença DEPOIS de a rota ter
      sido validada. Não rebaixamos o conteúdo do humano; sinalizamos e travamos
      "Fechar rota" até o consultor aceitar o diff (Ficha §9).
    """

    proposta = "proposta"
    em_validacao = "em_validacao"
    validada = "validada"
    desatualizada = "desatualizada"


class RotaPassoClassificacao(str, enum.Enum):
    """Ficha §8.1: cada passo é faturável (item de proposta) ou direção.

    ``NULL`` até o consultor classificar. OBRIGATÓRIO para validar o passo —
    força a decisão econômica em vez de deixá-la implícita.
    """

    item_proposta = "item_proposta"
    direcao = "direcao"


class RotaPassoOrigem(str, enum.Enum):
    """Como o passo nasceu — rastreabilidade e regra de reconciliação.

    - ``ia``     — materializado da ``LegislacaoAgent``; upsert por ``dedupe_key``.
    - ``manual`` — consultor adicionou (Ficha §9); NUNCA tocado pelo re-run.
    """

    ia = "ia"
    manual = "manual"


class RotaPassoStatus(str, enum.Enum):
    """Estado de validação de um passo (Princípio 1)."""

    proposto = "proposto"
    validado = "validado"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Rota(Base):
    """Snapshot editável do caminho regulatório de um processo (por demanda).

    Uma rota ativa por ``(tenant_id, process_id, demand_type)`` — a IA keia por
    ``demand_type``, então re-rodar a mesma demanda RECONCILIA a rota existente
    (não cria outra). Ver ``app/services/rota_materializer.py``.
    """

    __tablename__ = "rotas"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "process_id",
            "demand_type",
            name="uq_rotas_tenant_process_demand",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    process_id = Column(
        Integer,
        ForeignKey("processes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    demand_type = Column(String(50), nullable=False)

    status = Column(
        Enum(RotaStatus, name="rota_status"),
        nullable=False,
        default=RotaStatus.proposta,
    )

    caminho_regulatorio = Column(Text, nullable=True)
    orgao_competente = Column(String, nullable=True)

    # Proveniência: qual execução da IA propôs/reconciliou esta rota.
    source_ai_job_id = Column(
        Integer,
        ForeignKey("ai_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    validated_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    validated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    tenant = relationship("Tenant")
    process = relationship("Process")
    validator = relationship("User", foreign_keys=[validated_by])
    passos = relationship(
        "RotaPasso",
        back_populates="rota",
        cascade="all, delete-orphan",
        order_by="RotaPasso.ordem",
    )
    versoes = relationship(
        "RotaVersao",
        back_populates="rota",
        cascade="all, delete-orphan",
        order_by="RotaVersao.versao",
    )


class RotaVersao(Base):
    """Foto da Rota ANTES de cada regeneração — histórico que nunca se perde.

    Validação Isis 30/07: *"atualizar da IA apagou toda a rota"*. A reconciliação
    é aditiva por projeto, mas isso não bastava: como a ``dedupe_key`` incluía a
    ``norma_ref`` (que o LLM varia entre execuções), re-rodar duplicava passos
    quase idênticos — e o consultor limpava a mão, apagando trabalho junto. Em
    produção o caso 15 tem os pares 7/12 e 8/13: mesmo título, mesmo órgão,
    chaves diferentes.

    Perda de trabalho do consultor = nunca mais. Antes de qualquer regeneração o
    estado corrente vira uma versão numerada e imutável (rota + passos em JSON),
    consultável na tela. A regeneração deixa de ser uma aposta.
    """

    __tablename__ = "rota_versoes"
    __table_args__ = (
        UniqueConstraint("rota_id", "versao", name="uq_rota_versoes_rota_versao"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rota_id = Column(
        Integer, ForeignKey("rotas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    versao = Column(Integer, nullable=False)
    # Motivo do congelamento — hoje só "regeneracao"; nomeado para o dia em que
    # houver outro (importação, reversão).
    motivo = Column(String(50), nullable=False, default="regeneracao")
    # Snapshot completo: {"rota": {...}, "passos": [...]}. JSON e não FK: uma
    # versão é uma FOTO, não um vínculo vivo — tem de sobreviver ao passo apagado.
    snapshot = Column(PortableJSON, nullable=False, default=dict)

    created_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )

    rota = relationship("Rota", back_populates="versoes")


class RotaPasso(Base):
    """Um passo da Rota — ordenável, classificável e validável pelo consultor.

    ``dedupe_key`` garante idempotência da materialização (passos IA): re-rodar a
    legislação não duplica. Passos ``manual`` recebem uma chave própria (derivada
    do id pós-flush) para nunca colidir entre si nem com passos IA.
    """

    __tablename__ = "rota_passos"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "dedupe_key", name="uq_rota_passos_tenant_dedupe"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rota_id = Column(
        Integer,
        ForeignKey("rotas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Ordem editável pelo consultor; autoritativa pós-validação (o "aprendizado"
    # do MVP é capturar este sinal — feedback-ao-modelo é follow-on).
    ordem = Column(Integer, nullable=False)

    titulo = Column(String, nullable=False)
    descricao = Column(Text, nullable=True)
    orgao = Column(String, nullable=True)
    prazo_estimado_dias = Column(Integer, nullable=True)
    # 'norma' (com source) | 'estimativa_profissional' (sem fonte normativa).
    prazo_fonte = Column(String, nullable=True)

    # Proveniência da norma — list[SourceRef] serializada (shape #70). Vazio +
    # prazo presente → o passo é uma estimativa profissional honesta (marcada).
    sources = Column(PortableJSON, nullable=False, default=list)
    # Citação denormalizada da norma, para display e para o dedupe_key.
    norma_ref = Column(String, nullable=True)

    # Ficha §8.1: faturável vs direção. NULL até o consultor decidir; exigido
    # para validar o passo (ver app/api/v1/rotas.py).
    classificacao = Column(
        Enum(RotaPassoClassificacao, name="rota_passo_classificacao"),
        nullable=True,
    )

    origem = Column(
        Enum(RotaPassoOrigem, name="rota_passo_origem"),
        nullable=False,
        default=RotaPassoOrigem.ia,
    )
    # Ficha §9: fundamento informado quando o consultor adiciona um passo sem
    # base normativa nos autos (ex.: "orientação verbal da secretaria"). Insumo
    # de aprendizado futuro (auto-RAG de fundamento é follow-on).
    origem_manual_nota = Column(Text, nullable=True)

    # ── Proveniência do passo (ADR-039, dívida #102) ────────────────────────
    # De qual ACHADO do diagnóstico e/ou de qual AÇÃO triada este passo nasceu.
    # Fecha a corrente inteira: achado → ação → passo da rota → item da proposta
    # (`ProposalScopeItem.rota_passo_id`, S5-A). Cada elo com FK, nada sem
    # origem — do diagnóstico ao contrato.
    #
    # `SET NULL` pelo mesmo motivo do S5-A: a rota é peça assinada e sobrevive
    # ao desaparecimento da origem. Perder o ponteiro é aceitável; perder o
    # passo que o consultor validou, não.
    #
    # Ambos NULL é legítimo e frequente: passo manual do consultor, ou passo que
    # a IA propôs sem conseguir declarar de onde veio. Nunca se inventa a origem
    # — referência que não casa com achado/ação reais deste caso é descartada.
    origem_issue_id = Column(
        Integer,
        ForeignKey("regulatory_issues.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    origem_acao_id = Column(
        Integer,
        ForeignKey("acoes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = Column(
        Enum(RotaPassoStatus, name="rota_passo_status"),
        nullable=False,
        default=RotaPassoStatus.proposto,
    )

    dedupe_key = Column(String(120), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    tenant = relationship("Tenant")
    rota = relationship("Rota", back_populates="passos")
