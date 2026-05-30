"""
Schemas de Credential — cofre de logins de portais por cliente (PR 2.3).

A senha entra em plaintext (write-only) e NUNCA volta na resposta: o output
expõe apenas `has_password` (bool). Recuperação da senha para uso é server-side
(o ORM decifra ao carregar). Espelha a postura da PR LLM (nunca plaintext na API).
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CredentialCreate(BaseModel):
    client_id: int = Field(..., description="Cliente dono da credencial.")
    portal: str = Field(..., min_length=1, description="sema | ibama | sicar | incra | banco | cooperativa | outro")
    label: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = None   # write-only — cifrado no storage
    url: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("portal")
    @classmethod
    def _portal_nao_vazio(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not v:
            raise ValueError("portal é obrigatório.")
        return v


class CredentialUpdate(BaseModel):
    """PATCH parcial. `password` ausente/None preserva a senha atual; string
    vazia também NÃO apaga (use delete para remover a credencial)."""
    portal: Optional[str] = None
    label: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None


class CredentialResponse(BaseModel):
    """Saída — NUNCA inclui a senha em plaintext."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    portal: str
    label: Optional[str] = None
    login: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None
    has_password: bool = False
    created_at: Optional[str] = None
