from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.services.identity import normalize_doc


class ClientRepresentativeBase(BaseModel):
    """Representante da PJ (ENT-001). Nunca titular — só representa."""

    full_name: Optional[str] = None
    cpf: Optional[str] = None
    rg: Optional[str] = None
    birth_date: Optional[date] = None
    papel: Optional[str] = "representante_legal"
    email: Optional[str] = None
    phone: Optional[str] = None


class ClientRepresentativeCreate(ClientRepresentativeBase):
    pass


class ClientRepresentativeUpdate(ClientRepresentativeBase):
    pass


class ClientRepresentative(ClientRepresentativeBase):
    id: int
    client_id: int
    source_document_id: Optional[int] = None
    field_sources: Optional[dict] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


def _valida_documento(v: Optional[str]) -> Optional[str]:
    """CPF tem 11 dígitos, CNPJ tem 14. Nada além disso identifica pessoa.

    Guarda a coluna que o índice único indexa: string com 3 dígitos não é
    documento, é digitação pela metade, e deixá-la entrar transforma a unicidade
    num sorteio. Vazio continua permitido (cadastro sem documento é lead real).
    """
    if v is None:
        return None
    bruto = v.strip()
    if not bruto:
        return None
    digitos = normalize_doc(bruto)
    if len(digitos) not in (11, 14):
        raise ValueError(
            "CPF deve ter 11 dígitos e CNPJ 14 — recebido "
            f"{len(digitos)} dígito(s) em {bruto!r}."
        )
    return bruto


class ClientBase(BaseModel):
    full_name: str
    # DATA-001 — razão social existia na coluna e NÃO no schema: o POST recebia
    # e descartava em silêncio, e o GET nunca devolvia. Era essa a causa do
    # "preenchi o cadastro e a aba Dados mostra CNPJ vazio" da ELODI.
    legal_name: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    client_type: Optional[str] = "pf"
    status: Optional[str] = "lead"

    _doc = field_validator("cpf_cnpj")(_valida_documento)


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    full_name: Optional[str] = None
    legal_name: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    client_type: Optional[str] = None
    status: Optional[str] = None

    _doc = field_validator("cpf_cnpj")(_valida_documento)


class Client(ClientBase):
    id: int
    tenant_id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    # ENT-001 — o representante viaja junto do titular em toda tela que consome
    # a pessoa. Lista vazia em PF: é o estado correto, não ausência de dado.
    representatives: list[ClientRepresentative] = []

    model_config = ConfigDict(from_attributes=True)
