"""Pydantic v2 schemas do endpoint público POST /api/v1/waitlist.

Validações relevantes:
- ``email`` normalizado lowercase (idempotência case-insensitive)
- ``estado`` validado contra UFs brasileiras
- ``telefone`` aceita formatado, normaliza para apenas dígitos
- ``preco_aceito`` segue Van Westendorp (4 chaves obrigatórias entre si coerentes)
- ``consentimento`` obrigatório (LGPD)
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator

_UF_VALIDAS = frozenset({
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
})


class PrecoVanWestendorp(BaseModel):
    """Van Westendorp PSM (Price Sensitivity Meter) — 4 perguntas, BRL inteiros."""

    model_config = ConfigDict(extra="forbid")

    barato_demais: int = Field(ge=0, le=99999, description="Tão barato que parece suspeito")
    barato: int = Field(ge=0, le=99999, description="Bom negócio")
    caro: int = Field(ge=0, le=99999, description="Caro mas justifica o valor")
    caro_demais: int = Field(ge=0, le=99999, description="Caro demais pra considerar")

    @field_validator("barato")
    @classmethod
    def _barato_gte_barato_demais(cls, v: int, info: ValidationInfo) -> int:
        if (bd := info.data.get("barato_demais")) is not None and v < bd:
            raise ValueError("barato deve ser >= barato_demais")
        return v

    @field_validator("caro")
    @classmethod
    def _caro_gte_barato(cls, v: int, info: ValidationInfo) -> int:
        if (b := info.data.get("barato")) is not None and v < b:
            raise ValueError("caro deve ser >= barato")
        return v

    @field_validator("caro_demais")
    @classmethod
    def _caro_demais_gte_caro(cls, v: int, info: ValidationInfo) -> int:
        if (c := info.data.get("caro")) is not None and v < c:
            raise ValueError("caro_demais deve ser >= caro")
        return v


class PreCadastroIn(BaseModel):
    """Payload do form de waitlist. LGPD: requer consentimento explícito."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    # Contato
    email: EmailStr
    nome: str = Field(min_length=2, max_length=120)
    telefone: Optional[str] = Field(default=None, max_length=20)

    # Perfil
    perfil_profissional: Optional[str] = Field(default=None, max_length=80)
    estado: Optional[str] = Field(default=None, min_length=2, max_length=2)
    tipo_licenciamento: Optional[str] = Field(default=None, max_length=120)
    volume_mensal: Optional[int] = Field(default=None, ge=0, le=10_000)
    ferramenta_atual: Optional[str] = Field(default=None, max_length=120)

    # Validação produto
    preco_aceito: Optional[PrecoVanWestendorp] = None
    expectativa: Optional[str] = Field(default=None, max_length=2000)
    deal_breaker: Optional[str] = Field(default=None, max_length=2000)
    interesse_grupo: bool = False

    # Consentimento LGPD — bloqueante
    consentimento: bool = Field(
        description="Aceite explícito da política de privacidade. Obrigatório True.",
    )

    # Tracking
    source: Optional[str] = Field(default=None, max_length=80)
    utm_source: Optional[str] = Field(default=None, max_length=120)
    utm_medium: Optional[str] = Field(default=None, max_length=120)
    utm_campaign: Optional[str] = Field(default=None, max_length=120)
    utm_term: Optional[str] = Field(default=None, max_length=120)
    utm_content: Optional[str] = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def _email_lower(cls, v: str) -> str:
        return v.lower()

    @field_validator("estado")
    @classmethod
    def _estado_uf(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        upper = v.upper()
        if upper not in _UF_VALIDAS:
            raise ValueError(f"UF inválido: {v!r}. Use sigla de 2 letras (ex: SP, MG).")
        return upper

    @field_validator("telefone")
    @classmethod
    def _telefone_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        digits = "".join(ch for ch in v if ch.isdigit())
        # 10 dígitos = fixo com DDD; 11 = celular com 9; 12-13 = com DDI
        if len(digits) < 10 or len(digits) > 13:
            raise ValueError("Telefone inválido. Use formato com DDD (ex: 11987654321).")
        return digits

    @field_validator("consentimento")
    @classmethod
    def _consentimento_obrigatorio(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Consentimento LGPD é obrigatório para entrar na lista de espera.")
        return v


class PreCadastroOut(BaseModel):
    """Resposta uniforme do endpoint /api/v1/waitlist.

    Idempotente: a mesma resposta volta tanto para signup novo quanto para
    e-mail já cadastrado (anti-enumeração). Não inclui ``id`` nem timestamps
    porque ambos diferenciariam novo vs existente para um atacante.
    """

    ok: bool = True
    mensagem: str = "Você está na lista de espera do Regente. Em breve entraremos em contato."


class PreCadastroAdmin(BaseModel):
    """Schema interno — não exposto em endpoint público.

    Usado por possível admin endpoint futuro (fora do escopo desta sprint).
    Mantido aqui para tipagem de testes e consumo programático.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nome: str
    telefone: Optional[str] = None
    perfil_profissional: Optional[str] = None
    estado: Optional[str] = None
    tipo_licenciamento: Optional[str] = None
    volume_mensal: Optional[int] = None
    ferramenta_atual: Optional[str] = None
    preco_aceito: Optional[dict] = None
    expectativa: Optional[str] = None
    deal_breaker: Optional[str] = None
    interesse_grupo: Optional[bool] = None
    source: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    resend_contact_id: Optional[str] = None
    consentimento_dado_em: datetime
    deleted_at: Optional[datetime] = None
    converted_user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
