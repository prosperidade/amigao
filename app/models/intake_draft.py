"""
IntakeDraft — Rascunho de cadastro (Regente Cam1 CAM1-008/CAM1-009).

Permite "salvar e continuar depois" no wizard de entrada. Estados:
  - rascunho: faltam dados mínimos
  - pronto_para_criar: base mínima OK, pode virar processo
  - card_criado: já foi commitado num Process (guarda link)
  - base_complementada: documentos anexados depois do commit

Sprint F Bloco 3 (Camada 1 — decisão sócia 2026-04-19):
  Rascunhos expiram em 15 dias. Campo `expires_at` calculado ao criar/atualizar.
  Task Celery `cleanup_expired_intake_drafts` roda 1x/dia removendo expirados
  (apenas drafts em estado `rascunho` — card_criado nunca expira).
"""

from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


# Regra de negócio: rascunho expira em 15 dias após a última edição.
INTAKE_DRAFT_TTL_DAYS = 15

from app.models.base import Base
from app.models.types import PortableJSON


class IntakeDraftState(str, enum.Enum):
    rascunho = "rascunho"
    pronto_para_criar = "pronto_para_criar"
    card_criado = "card_criado"
    base_complementada = "base_complementada"


class IntakeDraft(Base):
    __tablename__ = "intake_drafts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    state = Column(
        Enum(IntakeDraftState),
        nullable=False,
        default=IntakeDraftState.rascunho,
        index=True,
    )
    entry_type = Column(String, nullable=True)

    # Snapshot do estado do wizard (client, property, description, etc.)
    form_data = Column(PortableJSON, nullable=False, default=dict)

    # Se o draft foi commitado, referência ao Process criado
    linked_process_id = Column(
        Integer,
        ForeignKey("processes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Sprint F Bloco 3 — prazo de expiração do rascunho (15 dias por padrão).
    # Renovado automaticamente a cada update. Drafts em estado `card_criado`
    # ignoram este campo (já viraram processo).
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    tenant = relationship("Tenant")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    linked_process = relationship("Process", foreign_keys=[linked_process_id])

    def refresh_expiration(self, ttl_days: int = INTAKE_DRAFT_TTL_DAYS) -> None:
        """Estende a data de expiração para agora + ttl_days. Chame ao criar/editar."""
        self.expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        ref = now or datetime.now(timezone.utc)
        return self.expires_at < ref


def has_minimal_base(form_data: dict) -> bool:
    """
    Regra Regente Cam1 — dados mínimos para o card nascer:
      Cliente: nome + telefone + e-mail + tipo PF/PJ
      Imóvel: nome
    """
    if not isinstance(form_data, dict):
        return False
    client = form_data.get("new_client") or {}
    prop = form_data.get("new_property") or {}
    # Se cliente/imóvel são existentes (client_id/property_id), também conta como OK
    client_ok = bool(form_data.get("client_id")) or all(
        client.get(k) for k in ("full_name", "phone", "email", "client_type")
    )
    prop_ok = bool(form_data.get("property_id")) or bool(prop.get("name"))
    return client_ok and prop_ok
