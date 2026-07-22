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
    # Item 7 (21/07) — número do CCIR (o certificado ANUAL, per-lote). É por ele
    # que a consultora LOCALIZA o documento. Distinto do codigo_incra_sncr (o
    # Código do Imóvel no SNCR) e do Property.ccir depreciado por ambiguidade.
    numero_ccir = Column(String, nullable=True)
    # Fase 0 (gap-analysis Ficha 07, item 8) — exercício (ano) do CCIR mais
    # recente lido para esta matrícula. CCIR é documento ANUAL — permite o
    # auditor emitir CCIR_EXERCICIO_ANTERIOR (catálogo já tinha o código,
    # faltava o emissor) quando `exercicio_ccir < ano corrente`.
    exercicio_ccir = Column(Integer, nullable=True)

    # Área decidida/consolidada da matrícula (a soma compõe a área do imóvel)
    area_ha = Column(Float, nullable=True)
    denominacao_imovel = Column(String, nullable=True)

    # Cadeia de fichas (Dívida #60) — sinais registrais que ligam esta matrícula
    # à ANTERIOR na linhagem. `registro_anterior` é o registro/matrícula de origem
    # citado na certidão (ex.: "R01-Mat. 2.923" na abertura da 4.698);
    # `denominacao_anterior` é o nome ANTERIOR do imóvel ("anteriormente denominada
    # X"). Ambos já entram como fonte/página no staging. São a evidência da
    # detecção de cadeia (ver app/services/matricula_chain.py) — nunca decidem
    # sozinhos: a proposta de cadeia é confirmada pelo consultor (1 clique).
    registro_anterior = Column(String, nullable=True)
    denominacao_anterior = Column(String, nullable=True)

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

    # LINEAGE (item 5 da Fase 2 — caso 15): de qual staging/decisão este
    # registro nasceu. `field_sources` diz o TIPO da fonte (raw/ai/humano);
    # isto diz QUAL linha e QUAL decisão — a certidão de nascimento.
    # Sem ela, a pergunta "de onde veio esse 2923?" só se responde cruzando
    # timestamps na mão, que foi exatamente o que a investigação do caso 15
    # teve de fazer.
    # Shape: {"criada_por": {staging_id, document_id, decided_by_user_id,
    #          decided_at, valor}, "campos": {campo: staging_id}}
    lineage = Column(PortableJSON, nullable=True, default=dict)

    # Desativação REVERSÍVEL (forense caso Isis) — REJEITAR na Conferência a
    # staging que materializou a matrícula a tira da soma sem hard-delete. NULL =
    # ativa; preenchido = fora da soma (`Property.area_total_matriculas`). A
    # consolidação reativa (deactivated_at=None) se a staging voltar a ser aceita.
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    deactivation_reason = Column(String, nullable=True)

    # Vigência da ficha (Dívida #60) — critério de domínio da Isis: "vigente =
    # matrícula da última averbação; a ficha anterior vira HISTÓRICO — não soma,
    # não gera lacuna, permanece visível como linhagem". ORTOGONAL a
    # `deactivated_at`: histórica é documento VÁLIDO (só não vigente); rejeitada é
    # desativação por rejeição na Conferência. Uma ficha pode ser histórica sem
    # nunca ter sido rejeitada. Default 'vigente' (backfill sem custo). A
    # transição vigente→histórica é PROPOSTA pela detecção de cadeia e CONFIRMADA
    # pelo consultor (IA propõe, humano decide) — reversível em Dados.
    vigencia = Column(String, nullable=False, server_default="vigente")
    # Aponta para a matrícula VIGENTE que substituiu esta (a "ficha atual" da
    # cadeia). NULL numa vigente; preenchido numa histórica. SET NULL preserva a
    # histórica se a vigente for removida (a linhagem sobrevive ao encadeamento).
    superseded_by_id = Column(
        Integer, ForeignKey("matriculas.id", ondelete="SET NULL"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    @property
    def is_active(self) -> bool:
        """Matrícula entra na soma da área só se ativa (deactivated_at NULL)."""
        return self.deactivated_at is None

    @property
    def is_vigente(self) -> bool:
        """Vigente = ativa (não rejeitada) E não marcada como histórica.

        Só matrícula vigente soma a área e gera lacunas/checklists (Dívida #60).
        Tolerante a modelos legados/mocks sem a coluna (getattr → 'vigente')."""
        return self.deactivated_at is None and (
            getattr(self, "vigencia", "vigente") or "vigente"
        ) != "historica"

    property = relationship("Property", back_populates="matriculas")
    tenant = relationship("Tenant")

    # Cadeia navegável (auto-referência): `supersedes` = fichas anteriores que
    # esta matrícula substituiu; `superseded_by` = a ficha vigente que a
    # substituiu. Mínimo 1 nível, expansível (o lote 1B tem 3: 2609→2923→4698).
    superseded_by = relationship(
        "Matricula",
        remote_side=[id],
        back_populates="supersedes",
        foreign_keys=[superseded_by_id],
    )
    supersedes = relationship(
        "Matricula",
        back_populates="superseded_by",
        foreign_keys=[superseded_by_id],
    )

    __table_args__ = (
        Index("ix_matriculas_tenant_property", "tenant_id", "property_id"),
    )
