"""
Identidade da pessoa principal — normalização e busca por CPF/CNPJ (ENT-002).

Porta ÚNICA de normalização de documento de pessoa. A regra é uma só: o que
identifica uma pessoa é a sequência de DÍGITOS, não a string digitada. O mesmo
CNPJ chega como "29.091.958/0001-17", "29091958000117" e "29 091 958/0001-17";
comparar string crua é o que deixou o mesmo CNPJ entrar quatro vezes no tenant
da ELODI (spec Isis §4.2.3).

Casa com a lição já registrada em `dedupe por identificador normalizado`: comparar
identificador cru é ilusão de unicidade.
"""

from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

_NAO_DIGITO = re.compile(r"\D")

# Comprimentos canônicos brasileiros.
CPF_LEN = 11
CNPJ_LEN = 14


def normalize_doc(value: Optional[str]) -> str:
    """CPF/CNPJ → só dígitos. `None`/vazio/pontuação pura → "".

    Devolve string (nunca None) porque o resultado é chave de comparação: o
    vazio é "não identificado", não "identificado como nada".
    """
    if value is None:
        return ""
    return _NAO_DIGITO.sub("", str(value))


def doc_kind(value: Optional[str]) -> Optional[str]:
    """"cpf" | "cnpj" | None (quando o comprimento não é nenhum dos dois)."""
    d = normalize_doc(value)
    if len(d) == CPF_LEN:
        return "cpf"
    if len(d) == CNPJ_LEN:
        return "cnpj"
    return None


def same_doc(a: Optional[str], b: Optional[str]) -> bool:
    """Dois documentos são a MESMA pessoa? Vazio nunca casa com vazio."""
    na, nb = normalize_doc(a), normalize_doc(b)
    return bool(na) and na == nb


def find_client_by_doc(db: Session, tenant_id: int, value: Optional[str],
                       exclude_id: Optional[int] = None):
    """Cliente do tenant cujo cpf_cnpj normalizado é igual ao informado.

    Busca EXATA por dígitos (ENT-002: "o sistema procura correspondência exata
    e oferece reutilização"). Ignora excluídos (soft delete) — um cadastro
    apagado não bloqueia o novo. `exclude_id` serve ao PATCH, para o registro
    não colidir consigo mesmo.

    Filtra por `tenant_id` sempre: a unicidade é POR TENANT, nunca global —
    o mesmo produtor rural pode ser cliente de duas consultorias (Princípio 4).
    """
    from app.models.client import Client  # noqa: PLC0415

    alvo = normalize_doc(value)
    if not alvo:
        return None

    q = db.query(Client).filter(
        Client.tenant_id == tenant_id,
        Client.deleted_at.is_(None),
        Client.cpf_cnpj.isnot(None),
    )
    if exclude_id is not None:
        q = q.filter(Client.id != exclude_id)
    # Comparação em Python: a coluna guarda o valor COMO DIGITADO (o consultor
    # quer reler "29.091.958/0001-17", não 29091958000117) e o índice único do
    # banco é funcional sobre os dígitos. O universo é o de clientes de um
    # tenant — dezenas a milhares, não milhões.
    for c in q.all():
        if normalize_doc(c.cpf_cnpj) == alvo:
            return c
    return None
