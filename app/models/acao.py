"""Modelo `Acao` — Ficha 07 (Aba Ações + Quadro de Ações global).

Onde o **diagnóstico vira trabalho**. Cada ação de remediação proposta pelo
diagnóstico/auditor (com fonte — contrato #70) o consultor **TRIA**: vira
tarefa interna, vira escopo de venda (candidato a item de proposta), ou é
dispensada. Princípio 1 do manifesto: *a IA propõe; o consultor decide*.

Decisões fechadas (Isis, 16/06):

- **RESPONSÁVEL**: sem responsável no MVP. ``responsavel_id`` é **nullable**
  para ligar à entidade Usuário quando o Bloco 0 (multi-tenant) entrar — sem
  bloquear a tela agora.
- **AÇÃO × PASSIVO**: concluir uma ação **NÃO** resolve o passivo. No
  diagnóstico nada se resolve — passivo só é sanado após contratação e
  regularização (pós-MVP). ``vinculo_passivo`` REFERENCIA o passivo de origem
  (rastreabilidade), mas é um JSON solto — **não** há FK que propague status
  para ``RegulatoryIssue``/achado. Concluir é "trabalho interno feito", nunca
  "passivo resolvido". Registrado no ADR-016.

Por que entidade própria (e não reuso de ``Task``):

``Task`` é tarefa genérica (kanban operacional, dependências, backlog). ``Acao``
carrega o que ``Task`` não tem e o método da sócia exige: **origem com fonte**
(rastreabilidade #70), **vínculo ao passivo** e **triagem** (tarefa/escopo/
dispensada). São conceitos distintos — a aba "Ações" do caso é a Ficha 07; a
aba "Tarefas" continua sendo o ``Task``.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    Date,
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


class AcaoPrioridade(str, enum.Enum):
    alta = "alta"
    media = "media"
    baixa = "baixa"


class AcaoStatus(str, enum.Enum):
    """Colunas do Quadro de Ações (kanban global e filtro da aba)."""

    a_fazer = "a_fazer"
    em_andamento = "em_andamento"
    concluida = "concluida"
    bloqueada = "bloqueada"


class AcaoTipoTriagem(str, enum.Enum):
    """Decisão do consultor sobre a ação proposta (Princípio 1).

    - ``pendente``   — gerada pelo diagnóstico, aguardando triagem.
    - ``tarefa``     — vira trabalho interno.
    - ``escopo``     — candidata a item da proposta/Orçamento (a ponte com o
      Orçamento é consumida depois; aqui só MARCA — não constrói o Orçamento).
    - ``dispensada`` — consultor descartou.
    """

    pendente = "pendente"
    tarefa = "tarefa"
    escopo = "escopo"
    dispensada = "dispensada"


class AcaoOrigem(str, enum.Enum):
    """Como a ação nasceu — para rastreabilidade e idempotência da geração."""

    diagnostico = "diagnostico"   # gerada de um risco/afirmação do diagnóstico
    auditor = "auditor"           # gerada de um finding determinístico do auditor
    manual = "manual"             # consultor criou do zero
    consolidacao = "consolidacao"  # gerada de uma divergência não resolvida na consolidação


# Transições válidas no kanban — qualquer coluna alcança qualquer outra
# (o consultor manda; bloqueada não é terminal). Mantido explícito para
# espelhar o padrão de ``Task`` e documentar o domínio.
VALID_ACAO_TRANSITIONS: dict[AcaoStatus, list[AcaoStatus]] = {
    AcaoStatus.a_fazer: [AcaoStatus.em_andamento, AcaoStatus.bloqueada, AcaoStatus.concluida],
    AcaoStatus.em_andamento: [AcaoStatus.a_fazer, AcaoStatus.bloqueada, AcaoStatus.concluida],
    AcaoStatus.bloqueada: [AcaoStatus.a_fazer, AcaoStatus.em_andamento, AcaoStatus.concluida],
    AcaoStatus.concluida: [AcaoStatus.a_fazer, AcaoStatus.em_andamento, AcaoStatus.bloqueada],
}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class Acao(Base):
    """Ação de remediação triável, vinculada a um processo (caso).

    ``dedupe_key`` garante a **idempotência da geração** (Ficha 07 §2): a chave
    é derivada de ``process + passivo + título``, estável entre versões do
    diagnóstico — regerar não duplica. Criação manual deixa ``dedupe_key=NULL``
    (NULLs são distintos no unique de Postgres/SQLite, então manuais nunca
    colidem entre si).
    """

    __tablename__ = "acoes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_acoes_tenant_dedupe"),
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

    titulo = Column(String, nullable=False)
    descricao = Column(Text, nullable=True)

    # ── Origem com fonte (contrato #70 — "nenhuma afirmação sem fonte") ──
    origem = Column(
        Enum(AcaoOrigem, name="acao_origem"),
        nullable=False,
        default=AcaoOrigem.manual,
    )
    # Texto do passivo/achado de origem (ex.: "Área da matrícula diverge do CAR").
    origem_descricao = Column(String, nullable=True)
    # Lista de SourceRef serializados (mesmo shape do #70 em stage_output.py).
    # Nunca inventar fonte: ação gerada sem fonte carrega uma SourceRef
    # ``sem_fonte`` para a UI sinalizar honestamente.
    origem_fontes = Column(PortableJSON, nullable=False, default=list)

    # Ref ao passivo/linha do diagnóstico — rastreabilidade pura.
    # Shape: {"tipo": "risco"|"afirmacao"|"issue"|"manual", "ref": str|None,
    #         "descricao": str|None}. NÃO é FK: concluir a ação JAMAIS altera o
    # passivo (decisão Isis 16/06 / ADR-016).
    vinculo_passivo = Column(PortableJSON, nullable=True)

    # Responsável — nullable no MVP (Bloco 0 ainda não iniciado). Liga à
    # entidade Usuário quando multi-tenant de usuários entrar.
    responsavel_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    prazo = Column(Date, nullable=True)
    prioridade = Column(
        Enum(AcaoPrioridade, name="acao_prioridade"),
        nullable=False,
        default=AcaoPrioridade.media,
    )
    status = Column(
        Enum(AcaoStatus, name="acao_status"),
        nullable=False,
        default=AcaoStatus.a_fazer,
    )
    tipo_triagem = Column(
        Enum(AcaoTipoTriagem, name="acao_tipo_triagem"),
        nullable=False,
        default=AcaoTipoTriagem.pendente,
    )

    # Idempotência da geração (NULL para criação manual).
    dedupe_key = Column(String(120), nullable=True)

    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    concluida_at = Column(DateTime(timezone=True), nullable=True)

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
    responsavel = relationship("User", foreign_keys=[responsavel_id])
    creator = relationship("User", foreign_keys=[created_by_user_id])
