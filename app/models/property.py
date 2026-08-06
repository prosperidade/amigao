from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON


class Property(Base):
    """Imóvel rural — entidade central fundiária."""
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)

    name = Column(String, nullable=False)
    registry_number = Column(String, nullable=True)   # matrícula
    ccir = Column(String, nullable=True)
    nirf = Column(String, nullable=True)
    car_code = Column(String, nullable=True)
    car_status = Column(String, nullable=True)         # ativo, pendente, cancelado, etc.

    total_area_ha = Column(Float, nullable=True)
    municipality = Column(String, nullable=True)
    state = Column(String(2), nullable=True)           # UF
    biome = Column(String, nullable=True)

    geom = Column(Geometry(geometry_type="GEOMETRY", srid=4674), nullable=True)

    has_embargo = Column(Boolean, default=False)
    status = Column(String, default="active")         # active, inactive, archived
    notes = Column(Text, nullable=True)

    # Regente Cam2 CAM2IH-007 — origem por campo: raw | ai_extracted | human_validated
    # Ex: {"car_code": "human_validated", "registry_number": "ai_extracted", ...}
    field_sources = Column(PortableJSON, nullable=True, default=dict)

    # Sprint 4 (Ficha 07 §9) — "matrículas contíguas?": grupo de matrículas
    # contíguas do mesmo titular = um imóvel rural, um CAR (Lei 8.629/93 art. 4º I).
    # Tri-state: NULL = não informado (legado, sem backfill); True/False =
    # declaração do consultor (grava selo human_validated em field_sources).
    # False = declarar-e-avisar: a soma derivada é ANOTADA, nunca suprimida;
    # a separação em outro imóvel é orientação, não automação (ADR-023).
    matriculas_contiguas = Column(Boolean, nullable=True)

    # Regente Cam2 CAM2IH-003/004 (Sprint H) — campos técnicos do Dashboard + Aba Informações
    rl_status = Column(String, nullable=True)           # averbada | proposta | pendente | cancelada
    app_area_ha = Column(Float, nullable=True)
    regulatory_issues = Column(PortableJSON, nullable=True, default=list)  # [{tipo, descricao, severidade}]
    area_documental_ha = Column(Float, nullable=True)
    area_grafica_ha = Column(Float, nullable=True)
    tipologia = Column(String, nullable=True)           # agricultura | pecuaria | misto | outro
    # Dívida #200 — módulos fiscais é ATRIBUTO do imóvel (área ÷ módulo fiscal do
    # município), não do documento que o declara. Decide PORTE, e porte decide as
    # exceções do Código Florestal que a skill de diagnóstico aplica ("Exceção por
    # porte — pequeno produtor, agricultura familiar, Módulo Fiscal") e a H19 do
    # auditor ("exige saber bioma e módulos fiscais"). O RAT declara o número e a
    # extração o produzia desde sempre; sem coluna, ele era descartado em silêncio
    # a cada consolidação. Float porque o quociente é fracionário (ex.: 3,7 MF).
    modulos_fiscais = Column(Float, nullable=True)
    strategic_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")
    client = relationship("Client")

    # Ficha 01 (FASE 1) — 1 Imóvel : N Matrículas. A área do imóvel passa a ser
    # a SOMA das áreas das matrículas (derivada). O campo `total_area_ha` acima
    # NÃO é removido nesta fase (compatibilidade); a transição completa é depois.
    matriculas = relationship(
        "Matricula",
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def matriculas_ativas(self) -> list:
        """Matrículas que contam para a soma — exclui as desativadas (forense
        caso Isis): matrícula cuja staging foi REJEITADA na Conferência sai da
        soma sem ser apagada (`deactivated_at` preenchido). Tolerante a modelos
        legados/mocks sem a coluna (getattr → None → ativa)."""
        return [m for m in (self.matriculas or []) if getattr(m, "deactivated_at", None) is None]

    def matriculas_vigentes(self) -> list:
        """Matrículas VIGENTES (Dívida #60) — ativas E não marcadas como histórica.

        Só estas somam a área e contam para lacunas/contiguidade. A ficha
        histórica (anterior na cadeia) é documento VÁLIDO mas não vigente: fica
        de fora da soma sem ser apagada (linhagem preservada). Tolerante a
        modelos legados/mocks sem a coluna `vigencia` (getattr → 'vigente')."""
        return [
            m for m in self.matriculas_ativas()
            if (getattr(m, "vigencia", "vigente") or "vigente") != "historica"
        ]

    def matriculas_historicas(self) -> list:
        """Fichas anteriores da cadeia (Dívida #60) — não somam, não geram lacuna,
        permanecem visíveis como linhagem. Exclui as rejeitadas (essas saíram por
        outro motivo — desativação, não vigência)."""
        return [
            m for m in self.matriculas_ativas()
            if (getattr(m, "vigencia", "vigente") or "vigente") == "historica"
        ]

    def area_total_matriculas(self) -> float:
        """Área total do imóvel = SOMA das áreas das matrículas VIGENTES (Ficha 01
        + Dívida #60).

        Matrícula sem área conta como 0. Matrícula desativada (rejeitada na
        Conferência) OU histórica (ficha anterior da cadeia) NÃO soma. Arredonda
        a 4 casas (precisão cartorial INCRA). Valor DERIVADO — não digitado.
        """
        total = sum((m.area_ha or 0.0) for m in self.matriculas_vigentes())
        return round(total, 4)

    def agregar_das_matriculas(self, campo: str) -> "str | None":
        """Um campo de MATRÍCULA visto no nível do IMÓVEL (regra Isis, 02/08).

        O imóvel é a entidade permanente, mas quase todo dado registral vive na
        matrícula — e um imóvel tem N. Ao subir esse dado para o cabeçalho do
        imóvel havia três saídas possíveis e só uma é honesta:

        * escolher uma das matrículas → INVENTA (a outra some sem aviso);
        * somar/concatenar em um número novo → INVENTA (349,9022 + 660,6561 não
          é "o" número de nada);
        * mostrar as duas → é o que a regra manda: ``"349,9022 | 660,6561"``.

        Portanto: valor único quando todas as matrículas vigentes concordam;
        os valores separados por ``" | "`` quando divergem; ``None`` quando
        ninguém tem o dado. Nunca um valor fabricado.

        Só matrículas VIGENTES entram (ficha histórica é linhagem, não estado
        atual — Dívida #60). Float sai em formato BR (vírgula decimal), que é
        como a consultora lê e digita área.
        """
        vistos: list[str] = []
        for m in self.matriculas_vigentes():
            bruto = getattr(m, campo, None)
            if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
                continue
            if isinstance(bruto, float):
                texto = f"{round(bruto, 4):.4f}".rstrip("0").rstrip(".").replace(".", ",")
            else:
                texto = str(bruto).strip()
            if texto and texto not in vistos:
                vistos.append(texto)
        if not vistos:
            return None
        return vistos[0] if len(vistos) == 1 else " | ".join(vistos)

    def nota_soma_matriculas(self) -> "str | None":
        """Anotação de honestidade da soma (Sprint 4 / Ficha 07 §9).

        Com >1 matrícula e contiguidade não declarada (NULL) ou negada (False),
        a soma única pode não corresponder a um imóvel rural — quem exibe ou
        raciocina sobre ela recebe a ressalva junto. None = nada a ressalvar.
        """
        if len(self.matriculas_vigentes()) <= 1 or self.matriculas_contiguas is True:
            return None
        if self.matriculas_contiguas is False:
            return (
                "Soma de matrículas declaradas NÃO contíguas — não representa um "
                "único imóvel rural; tratar os grupos como imóveis separados "
                "(um CAR por imóvel)."
            )
        return (
            "Soma de matrículas não declaradas contíguas — pode não representar "
            "um único imóvel rural."
        )
