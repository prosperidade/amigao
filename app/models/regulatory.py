"""Modelos regulatórios.

Histórico:
- **Sprint A1 (Tarefa D1)** — cria `RegulatoryDiagnosis` (versionado por processo)
  e `RegulatoryIssue` (vinculado a property). Fecha o gap B3 do audit
  `docs/AUDITORIA_FLUXO_2026-04-29.md`.
- **PROMPT_4 Onda B (2026-05-25)** — `validated_by_user_id` / `validated_at` no
  Diagnosis ganham endpoint `PATCH /validate` (camada 1 do Princípio 1).
- **PROMPT_5 Onda A (2026-05-25)** — remodelagem da taxonomia: o `type` enum
  curto (5 valores, maioria caía em "outro") sai gradualmente — entram
  ``familia`` (enum estável ~11), ``codigo_alerta`` (catálogo evolutivo via
  `RegulatoryIssueCatalog`, NÃO enum — adicionar código novo é INSERT, não
  migration), e os campos ``muda_rota_regulatoria`` / ``muda_escopo_preco_prazo``
  / ``documentos_cruzados``. ``severity`` passa de 3 para 4 níveis
  (`informativo`/`atencao`/`alto`/`critico`) — sai o colapso 4→3 que era a
  dívida #4. Origem da taxonomia: skill
  `app/skills/auditor_imovel/analise_divergencias_documentais/SKILL.md` v1.1.0
  (validada pela sócia).
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.types import PortableJSON

# ---------------------------------------------------------------------------
# Enums (compartilhados pela migration via string values)
# ---------------------------------------------------------------------------


class RegulatoryFamilia(str, enum.Enum):
    """Famílias da taxonomia (PROMPT_5 Onda A).

    11 famílias estáveis derivadas da skill `auditor_imovel/
    analise_divergencias_documentais` (v1.1.0 validada pela sócia). Enum porque
    muda raramente — adicionar família é decisão arquitetural; adicionar
    `codigo_alerta` é INSERT no catálogo.
    """

    identificacao = "identificacao"
    titularidade = "titularidade"
    area = "area"
    geoespacial = "geoespacial"
    geo_incra = "geo_incra"
    car = "car"
    ambiental = "ambiental"
    fiscal = "fiscal"
    restricao_risco = "restricao_risco"
    licenciamento = "licenciamento"
    validade_documental = "validade_documental"


class RegulatoryIssueSeverity(str, enum.Enum):
    """4 níveis de severidade (PROMPT_5 Onda A — substituição do enum de 3).

    Antes era `info`/`warning`/`critical`. A sócia distinguiu alto vs. crítico
    de propósito: **só `critico` dispara o mecanismo de decisão obrigatória
    do consultor (5 ações da P4 — camada 2 do Princípio 1)**. A migração
    `regulatory_severity_v2` mapeia info→informativo, warning→atencao,
    critical→alto (a granularidade `critico` é nova — registros antigos não
    a tinham). Sai `_GRADE_TO_SEVERITY` no `property_audit.py`.
    """

    informativo = "informativo"
    atencao = "atencao"
    alto = "alto"
    critico = "critico"


class RegulatoryAlertFactibilidade(str, enum.Enum):
    """Marcador de factibilidade do `codigo_alerta` no catálogo (PROMPT_5).

    Vem dos marcadores 📄/🛰️/🔌 da skill auditor_imovel:
    - `documental` (📄) — cruzamento documento × documento; **emitido AGORA**
      pelo `AuditorImovelAgent`.
    - `geoespacial` (🛰️) — depende de `Property.geom` + parser shapefile (D1);
      códigos **estão no catálogo** (vocabulário completo) mas **NÃO são
      emitidos** até a infraestrutura existir.
    - `consulta_externa` (🔌) — depende de integração com base externa
      (IBAMA, FUNAI, ANA, etc.); idem (no catálogo, não emitido).
    """

    documental = "documental"
    geoespacial = "geoespacial"
    consulta_externa = "consulta_externa"


class RegulatoryIssueType(str, enum.Enum):
    """**DEPRECATED** (PROMPT_5 Onda A) — substituído por
    ``codigo_alerta`` + ``familia``.

    Mantido como nullable apenas para retrocompat de registros antigos
    (a migration `<hash>_prompt5_remodelar_regulatory_issue.py` converte os
    valores aqui em pares `codigo_alerta`/`familia` durante o upgrade).
    Novos registros NÃO devem preencher este campo — use `codigo_alerta`.
    """

    area_divergente = "area_divergente"
    sobreposicao_app = "sobreposicao_app"
    sobreposicao_reserva = "sobreposicao_reserva"
    poligono_fora_matricula = "poligono_fora_matricula"
    outro = "outro"


# ---------------------------------------------------------------------------
# Enums dos 3 status reconciliados (PROMPT_6 — camada 2 do Princípio 1)
# ---------------------------------------------------------------------------
#
# A reconciliação dos 3 conjuntos de status que circulavam (dívida #5) foi
# resolvida pela **Opção A** do `docs/arquitetura/RECONCILIACAO_STATUS_ALERTAS.md`:
# três campos ortogonais que medem **dimensões diferentes** do mesmo alerta:
#
# 1. ``StatusAchado`` — natureza do indício (preenchido pelo auditor, editável
#    pelo consultor). Responde "esse alerta é real?".
# 2. ``DecisaoConsultor`` — qual ação foi escolhida (P4 — 5 botões da camada 2
#    do Princípio 1). Responde "o que vou fazer com este alerta?". **Só
#    obrigatório para `severity=critico`** — outros níveis podem ficar `NULL`.
# 3. ``StatusSaneamento`` — progresso prático da resolução. Responde "este
#    alerta foi resolvido no mundo?".


class StatusAchado(str, enum.Enum):
    """Estado de confirmação do achado (dimensão 1 — natureza do indício).

    Auditor emite ``suspeita`` por default; consultor edita conforme valida."""

    suspeita = "suspeita"          # auditor emitiu; consultor ainda não olhou
    confirmada = "confirmada"      # consultor confirmou que o alerta é real
    descartada = "descartada"      # consultor descartou (auditor errou)
    resolvida = "resolvida"        # divergência foi sanada no mundo
    ignorada = "ignorada"          # consultor optou por não tratar (ex.: fora_escopo)


class DecisaoConsultor(str, enum.Enum):
    """**Camada 2 do Princípio 1** (dimensão 2 — ação escolhida sobre alerta
    crítico). Os 5 botões da P4 da skill diagnóstico.

    **Obrigatório quando ``severity=critico``** — o ``PATCH /validate`` (PROMPT_4)
    rejeita o diagnóstico se houver crítico sem decisão. Para outros níveis
    (`informativo`/`atencao`/`alto`), preenchimento é opcional."""

    corrigir_antes = "corrigir_antes"              # corrige antes de protocolar
    seguir_com_ressalva = "seguir_com_ressalva"    # segue mesmo com problema, registra
    solicitar_doc = "solicitar_doc"                # exige doc adicional antes de decidir
    fora_escopo = "fora_escopo"                    # alerta existe mas fora do contratado
    ignorar_justificado = "ignorar_justificado"    # ignora intencionalmente, com justificativa


class StatusSaneamento(str, enum.Enum):
    """Progresso prático da resolução (dimensão 3 — saneamento do alerta).

    Default ``pendente``. Pode ser derivado das outras duas dimensões em UI,
    mas mantemos como campo próprio (Opção A) para auditoria explícita."""

    pendente = "pendente"
    em_validacao = "em_validacao"
    saneado = "saneado"
    descartado = "descartado"
    nao_aplicavel = "nao_aplicavel"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RegulatoryDiagnosis(Base):
    """Diagnóstico regulatório versionado de um processo.

    A unicidade ``(process_id, version)`` garante que cada versão é única
    para um dado processo. Versionamento simples (inteiro crescente) — o
    caller é responsável por incrementar quando criar nova versão.
    """

    __tablename__ = "regulatory_diagnoses"
    __table_args__ = (
        UniqueConstraint("process_id", "version", name="uq_regulatory_diagnoses_process_version"),
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

    # Conteúdo livre — typicamente DiagnosticoPreliminarContent (schemas Tarefa C).
    # Pode incluir referência a issues via content["issue_ids"]: list[int].
    content = Column(PortableJSON, nullable=False, default=dict)

    version = Column(Integer, nullable=False, default=1)

    # Validação humana (opcional)
    validated_by_user_id = Column(
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

    process = relationship("Process", foreign_keys=[process_id])
    validated_by = relationship("User", foreign_keys=[validated_by_user_id])


class RegulatoryIssueCatalog(Base):
    """Catálogo evolutivo de ``codigo_alerta`` (PROMPT_5 Onda A).

    NÃO é enum — adicionar um código novo é INSERT, não migration de schema.
    Seed inicial vem da migration `<hash>_prompt5_remodelar_regulatory_issue.py`
    com 40+ entradas derivadas da skill `auditor_imovel/
    analise_divergencias_documentais` (v1.1.0). O `severity_base` aqui é o
    grau **padrão** sugerido pela taxonomia — o caller (auditor, manual) pode
    sobrescrever no `RegulatoryIssue` quando o contexto pedir (ex.: pequena
    sobreposição com terceiro continua `critico` mesmo sendo "informativo"
    por área).

    `factibilidade` separa o que o sistema consegue detectar AGORA (`documental`)
    do que aguarda infraestrutura (`geoespacial` precisa de `Property.geom`,
    `consulta_externa` precisa de integração com base externa). Códigos
    `geoespacial`/`consulta_externa` ficam no catálogo (vocabulário canônico)
    mas o auditor **não os emite** até a infra existir.

    `muda_rota_regulatoria` e `muda_escopo_preco_prazo` são valores **default**
    do código — o `RegulatoryIssue` pode override quando o caso específico
    justificar (ex.: divergência de área pequena que normalmente não muda rota,
    mas neste caso muda porque envolve compensação fora do bioma).
    """

    __tablename__ = "regulatory_issue_catalog"

    # codigo_alerta é PK natural — string curta, MAIÚSCULAS, estável
    # (ex.: "AREA_MATRICULA_X_CAR", "GEO_AUSENTE", "TIT_ESPOLIO_INVENTARIO").
    codigo_alerta = Column(String(80), primary_key=True)
    familia = Column(
        Enum(RegulatoryFamilia, name="regulatory_familia"),
        nullable=False,
        index=True,
    )
    descricao_curta = Column(String, nullable=False)
    factibilidade = Column(
        Enum(RegulatoryAlertFactibilidade, name="regulatory_factibilidade"),
        nullable=False,
        index=True,
    )
    severity_base = Column(
        Enum(RegulatoryIssueSeverity, name="regulatory_severity_v2"),
        nullable=False,
    )
    muda_rota_regulatoria = Column(Boolean, nullable=False, default=False)
    muda_escopo_preco_prazo = Column(Boolean, nullable=False, default=False)
    # documentos_cruzados_default: lista de strings (ex.: ["Matricula", "CAR"])
    # usada como dica do que o finding deveria comparar.
    documentos_cruzados_default = Column(PortableJSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )


class RegulatoryIssue(Base):
    """Inconsistência regulatória detectada em um imóvel.

    Vinculada diretamente a ``Property`` (obrigatório) e opcionalmente a um
    ``Document`` fonte. **Não** se relaciona via FK com ``RegulatoryDiagnosis``
    (Q4): quando um diagnóstico quiser referenciar issues, lista IDs no
    próprio ``content`` JSONB.

    PROMPT_5 Onda A: ganha a taxonomia rica (``codigo_alerta`` + ``familia`` +
    campos `muda_*` + ``documentos_cruzados``) e migra ``severity`` para 4
    níveis. O ``type`` antigo continua nullable para retrocompat — registros
    antigos têm ``type`` preenchido e ``codigo_alerta=NULL``; novos invertem.
    """

    __tablename__ = "regulatory_issues"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    property_id = Column(
        Integer,
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Taxonomia rica (PROMPT_5 Onda A) ──
    codigo_alerta = Column(
        String(80),
        ForeignKey("regulatory_issue_catalog.codigo_alerta", ondelete="RESTRICT"),
        nullable=True,  # nullable só para retrocompat com registros antigos
        index=True,
    )
    familia = Column(
        Enum(RegulatoryFamilia, name="regulatory_familia"),
        nullable=True,
        index=True,
    )
    # Overrides do default do catálogo — NULL = usa o default do catálogo.
    muda_rota_regulatoria = Column(Boolean, nullable=True)
    muda_escopo_preco_prazo = Column(Boolean, nullable=True)
    # documentos_cruzados: lista de strings (ex.: ["Matricula", "CAR"])
    documentos_cruzados = Column(PortableJSON, nullable=True)

    # severity passa a ter 4 níveis (PROMPT_5 Onda A — fecha dívida #4)
    severity = Column(
        Enum(RegulatoryIssueSeverity, name="regulatory_severity_v2"),
        nullable=False,
        default=RegulatoryIssueSeverity.atencao,
    )

    # ── DEPRECATED: type (PROMPT_5 — substituído por codigo_alerta + familia) ──
    # Mantido nullable para retrocompat de registros antigos. Novos registros
    # NÃO devem preencher este campo — use ``codigo_alerta``.
    type = Column(
        Enum(RegulatoryIssueType, name="regulatory_issue_type"),
        nullable=True,
        index=True,
    )

    payload = Column(PortableJSON, nullable=True)
    detected_by = Column(String, nullable=True)  # nome do agente ou "manual"

    # ── Status do achado e saneamento real (perenes — fato do imóvel) ──
    # PROMPT_6 (Opção A) introduziu 3 status reconciliados como campos da
    # issue. ADR-012 (validado pela Isis em 26/05) reclassificou:
    #
    # - `status_achado` (natureza do indício — "auditor errou ou é real?") e
    #   `status_saneamento` (saneamento REAL no mundo — fato corrigido)
    #   ficam aqui em RegulatoryIssue: são **perenes** no imóvel.
    # - `decisao_consultor` (ação escolhida) era campo aqui no PROMPT_6 —
    #   moveu para `ProcessIssueDecision` no PROMPT_7 porque a decisão é
    #   **contextual ao processo** (titularidade torta pesa diferente para
    #   vender e para dar como garantia ao banco; cada trabalho recomeça).
    status_achado = Column(
        Enum(StatusAchado, name="regulatory_status_achado"),
        nullable=False,
        default=StatusAchado.suspeita,
    )
    status_saneamento = Column(
        Enum(StatusSaneamento, name="regulatory_status_saneamento"),
        nullable=False,
        default=StatusSaneamento.pendente,
    )

    detected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    @validates("documentos_cruzados")
    def _normalize_documentos_cruzados(self, _key: str, value: Any) -> Any:
        """Guard write-side: garante ``list[str]`` na origem (causa raiz do 500
        em ``GET /properties/{id}/issues``). Paths guiados por LLM podem produzir
        lista de objetos (ex.: ``[{"doc": "matricula"}]``); aqui cada item é
        achatado para string antes de persistir, espelhando a coerção de leitura
        em ``schemas/regulatory.py``. Linhas legadas já gravadas são tratadas no
        read-side."""
        if not isinstance(value, list):
            return value
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                parts = [str(x) for x in item.values() if x not in (None, "")]
                out.append(" — ".join(parts) if parts else str(item))
            elif item is not None:
                out.append(str(item))
        return out

    property = relationship("Property", foreign_keys=[property_id])
    document = relationship("Document", foreign_keys=[document_id])
    catalog_entry = relationship(
        "RegulatoryIssueCatalog",
        foreign_keys=[codigo_alerta],
    )


class ProcessIssueDecision(Base):
    """Decisão do consultor sobre uma `RegulatoryIssue` no contexto de um
    `Process` específico (PROMPT_7 — implementa ADR-012).

    **Por que separada de `RegulatoryIssue`:** a sócia validou em 26/05 que a
    decisão do consultor é **contextual ao processo**, não perene no imóvel
    (ADR-012). Titularidade torta pesa diferente para venda e para crédito
    — não dá pra herdar a decisão de um trabalho pra outro. Cada processo
    recomeça do zero; o fato da divergência fica em ``RegulatoryIssue``
    (perene), a avaliação fica aqui (contextual).

    **Unique `(process_id, issue_id)`:** uma decisão por par. O `PUT`
    endpoint faz upsert; mudança gera AuditLog granular por campo
    (Princípio 2). DELETE não está no MVP (consultor pode mudar o valor;
    "tirar decisão" é o suficiente).

    **Diferenças relevantes vs PROMPT_6 (que tinha tudo em RegulatoryIssue):**
    - `decisao` NOT NULL — uma linha aqui sempre tem decisão (vs nullable
      no PROMPT_6, que representava "ainda não decidido").
    - `decided_by_user_id` é **novo** — captura quem decidiu (PROMPT_6 só
      tinha o timestamp; agora temos o autor explicito, melhoria
      proporcional ao Princípio 2).
    - Renomeado: `decisao_consultor` → `decisao`, `decisao_consultor_at` →
      `decided_at`, `decisao_consultor_justificativa` → `justificativa`.
      Contexto da tabela já indica; nomes redundantes saem.
    """

    __tablename__ = "process_issue_decisions"
    __table_args__ = (
        UniqueConstraint("process_id", "issue_id", name="uq_process_issue_decisions_pid_iid"),
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
    issue_id = Column(
        Integer,
        ForeignKey("regulatory_issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    decisao = Column(
        Enum(DecisaoConsultor, name="regulatory_decisao_consultor"),
        nullable=False,
    )
    # Texto livre. Obrigatória quando `decisao in {ignorar_justificado,
    # fora_escopo}` — gate enforced no `ProcessIssueDecisionCreate` schema.
    justificativa = Column(String, nullable=True)
    decided_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    process = relationship("Process", foreign_keys=[process_id])
    issue = relationship("RegulatoryIssue", foreign_keys=[issue_id])
    decided_by = relationship("User", foreign_keys=[decided_by_user_id])
