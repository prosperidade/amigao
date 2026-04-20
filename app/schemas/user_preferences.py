"""
Schemas Pydantic para preferências do usuário e edição de perfil.

Regente Sprint F Bloco 2 — Camada 4 Configurações.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ─── Sub-grupos de preferências ───────────────────────────────────────────────

class ProfilePreferences(BaseModel):
    """Campos soltos de perfil (não estruturais)."""
    model_config = ConfigDict(extra="ignore")
    phone: Optional[str] = None
    role: Optional[str] = None        # ex: "Consultor", "Coordenador"
    company: Optional[str] = None
    avatar_url: Optional[str] = None
    language: str = "pt-BR"
    timezone: str = "America/Sao_Paulo"


class NotificationPreferences(BaseModel):
    """Onde e como receber alertas do sistema."""
    model_config = ConfigDict(extra="ignore")
    email: bool = True
    whatsapp: bool = False
    in_app: bool = True
    push: bool = False
    critical_only: bool = False
    daily_summary: bool = False
    weekly_summary: bool = False
    # Tipos de alerta desligáveis individualmente
    disabled_alert_kinds: list[str] = Field(default_factory=list)


class OperationalPreferences(BaseModel):
    """Como o usuário prefere operar dentro do Regente."""
    model_config = ConfigDict(extra="ignore")
    default_view: Literal["dashboard", "quadro_acoes", "cliente_hub"] = "dashboard"
    default_sort: Literal["priority", "urgency", "date", "responsible"] = "priority"
    compact_mode: bool = False
    date_format: Literal["dd/mm/yyyy", "yyyy-mm-dd"] = "dd/mm/yyyy"
    default_state_uf: Optional[str] = None   # UF padrão se o consultor só atua em uma


class AiPreferences(BaseModel):
    """Como a IA deve se comportar no apoio ao trabalho."""
    model_config = ConfigDict(extra="ignore")
    assistance_level: Literal["automatic", "balanced", "manual"] = "balanced"
    summary_length: Literal["short", "medium", "detailed"] = "medium"
    show_suggestions_in_flow: bool = True
    show_auto_summaries: bool = True
    require_human_validation_before_advance: bool = True
    save_ai_readings_history: bool = True


class UserPreferences(BaseModel):
    """Preferências agrupadas — espelha a estrutura do JSON no banco."""
    model_config = ConfigDict(extra="ignore")
    profile: ProfilePreferences = Field(default_factory=ProfilePreferences)
    notifications: NotificationPreferences = Field(default_factory=NotificationPreferences)
    operational: OperationalPreferences = Field(default_factory=OperationalPreferences)
    ai: AiPreferences = Field(default_factory=AiPreferences)


# ─── Patches parciais ─────────────────────────────────────────────────────────

class UserProfileUpdate(BaseModel):
    """Atualiza campos de identidade do usuário (não senha)."""
    full_name: Optional[str] = Field(None, min_length=2)
    email: Optional[EmailStr] = None


class PreferencesUpdate(BaseModel):
    """Merge parcial em qualquer um dos 4 grupos."""
    profile: Optional[ProfilePreferences] = None
    notifications: Optional[NotificationPreferences] = None
    operational: Optional[OperationalPreferences] = None
    ai: Optional[AiPreferences] = None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


# ─── Response compostas ───────────────────────────────────────────────────────

class UserMeResponse(BaseModel):
    """Resposta de GET /auth/me com preferências expandidas."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    preferences: UserPreferences = Field(default_factory=UserPreferences)
