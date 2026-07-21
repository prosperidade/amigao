"""Confronto de identidade da matrícula + cadeia proposta ANTES da decisão.

O erro do caso 15 em uma frase: o CCIR do Lote 1B declara `2923` (número
registral defasado), a certidão do mesmo lote declara `4698` (número atual), e
**a Conferência nunca colocou os dois lado a lado**. O consultor aceitou o CCIR,
rejeitou a certidão, e a base nasceu com o número errado — sem que nada na tela
sugerisse que havia uma escolha de identidade sendo feita.

Duas correções moram aqui:

* **Confronto** — quando dois ou mais documentos do mesmo caso declaram números
  de matrícula diferentes, isso vira a primeira coisa da tela, com a fonte de
  cada número e a hierarquia da Ficha 08 §5.1 DECLARADA em texto ("a certidão de
  matrícula é a fonte jurídica; o CCIR está defasado"). É a divergência mais
  cara do domínio: identidade jurídica do imóvel.
* **Cadeia antes da decisão** — a proposta de linhagem (#60) nasce da chegada do
  staging, não depois. No caso 15 o `registro_anterior` (2.923) estava numa
  linha que o consultor rejeitou, e a rejeição matou o sinal que teria evitado
  a própria rejeição errada.

Nada aqui decide: tudo PROPÕE, com a fonte à vista. O consultor decide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.extracted_field_staging import ExtractedFieldStaging

# Ficha 08 §5.1 — cadeia jurídica/dominial, do mais forte ao mais fraco.
# Matrícula → SNCR/CCIR → Cafir/CIB → ITR → CAR.
_PESO_JURIDICO: dict[str, int] = {
    "matricula": 1,
    "certidao_matricula": 1,
    "certidao_inteiro_teor": 1,
    "ccir": 2,
    "itr": 3,
    "car": 4,
    "rat": 5,
}
_PESO_DESCONHECIDO = 9

_ROTULO_FONTE: dict[str, str] = {
    "matricula": "certidão de matrícula",
    "certidao_matricula": "certidão de matrícula",
    "certidao_inteiro_teor": "certidão de inteiro teor",
    "ccir": "CCIR",
    "itr": "ITR",
    "car": "CAR",
    "rat": "RAT",
}


def _peso(doc_type: Optional[str]) -> int:
    return _PESO_JURIDICO.get((doc_type or "").strip().lower(), _PESO_DESCONHECIDO)


def _rotulo(doc_type: Optional[str]) -> str:
    return _ROTULO_FONTE.get((doc_type or "").strip().lower(), doc_type or "documento")


def _numero(valor: Any) -> str:
    """Número da matrícula comparável: só dígitos ('2.923' == '2923')."""
    if isinstance(valor, dict):
        valor = valor.get("value", "")
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


@dataclass
class FonteNumero:
    numero: str                  # como aparece no documento
    numero_norm: str
    document_id: Optional[int]
    doc_type: Optional[str]
    rotulo_fonte: str
    peso: int
    status: str                  # status atual da linha de staging
    staging_id: int


@dataclass
class ConfrontoIdentidade:
    """Números de matrícula concorrentes no mesmo caso."""

    fontes: list[FonteNumero] = field(default_factory=list)
    prevalente: Optional[FonteNumero] = None
    regra: str = ""
    cadeia_proposta: Optional[dict[str, Any]] = None

    @property
    def ha_confronto(self) -> bool:
        """Só é confronto quando os números DIVERGEM entre si."""
        return len({f.numero_norm for f in self.fontes}) > 1


def detectar_confronto(
    db: Session, *, tenant_id: int, process_id: int
) -> ConfrontoIdentidade:
    """Monta o confronto de identidade do caso, se houver.

    Considera TODAS as linhas de `numero_matricula`, independentemente do status
    — inclusive as já rejeitadas. É deliberado: no caso 15 o número correto
    estava justamente na linha rejeitada, e esconder o que foi rejeitado seria
    esconder a própria evidência de que a decisão precisa ser revista.
    """
    linhas = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.field_name == "numero_matricula",
        )
        .all()
    )

    fontes: list[FonteNumero] = []
    for linha in linhas:
        norm = _numero(linha.field_value)
        if not norm:
            continue
        bruto = linha.field_value
        if isinstance(bruto, dict):
            bruto = bruto.get("value", "")
        fontes.append(FonteNumero(
            numero=str(bruto), numero_norm=norm,
            document_id=linha.document_id, doc_type=linha.source_doc_type,
            rotulo_fonte=_rotulo(linha.source_doc_type),
            peso=_peso(linha.source_doc_type),
            status=linha.status.value if linha.status else "pendente",
            staging_id=linha.id,
        ))

    confronto = ConfrontoIdentidade(fontes=sorted(fontes, key=lambda f: f.peso))
    if not confronto.ha_confronto:
        return confronto

    confronto.prevalente = confronto.fontes[0]
    perdedores = [
        f for f in confronto.fontes if f.numero_norm != confronto.prevalente.numero_norm
    ]
    outros = ", ".join(sorted({f"{f.numero} ({f.rotulo_fonte})" for f in perdedores}))
    confronto.regra = (
        f"A {confronto.prevalente.rotulo_fonte} é a fonte jurídica do número da "
        f"matrícula (Ficha 08 §5.1: Matrícula → CCIR → ITR → CAR). "
        f"Prevalece {confronto.prevalente.numero}; {outros} "
        "provavelmente traz(em) o número defasado — confirme antes de decidir."
    )
    confronto.cadeia_proposta = _propor_cadeia(db, tenant_id, process_id, confronto)
    return confronto


def _propor_cadeia(
    db: Session, tenant_id: int, process_id: int, confronto: ConfrontoIdentidade
) -> Optional[dict[str, Any]]:
    """Liga os números concorrentes numa LINHAGEM quando o staging já sabe disso.

    Se algum documento declara `registro_anterior` apontando para um dos números
    perdedores, então não são dois imóveis nem um erro: é a mesma terra, antes e
    depois. Essa proposta nasce AQUI, na leitura do staging — antes de qualquer
    decisão campo a campo. No caso 15 ela existia (`registro_anterior` = 2.923)
    e foi destruída pela rejeição antes de virar sinal.
    """
    if confronto.prevalente is None:
        return None

    anteriores = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.field_name == "registro_anterior",
        )
        .all()
    )
    mapa = {_numero(linha.field_value): linha for linha in anteriores}

    for fonte in confronto.fontes:
        if fonte.numero_norm == confronto.prevalente.numero_norm:
            continue
        linha = mapa.get(fonte.numero_norm)
        if linha is None:
            continue
        return {
            "vigente": confronto.prevalente.numero,
            "historica": fonte.numero,
            "evidencia_staging_id": linha.id,
            "evidencia_document_id": linha.document_id,
            "texto": (
                f"A matrícula {fonte.numero} é o registro ANTERIOR da "
                f"{confronto.prevalente.numero} — mesma terra, não são dois imóveis. "
                f"Aceitar a linhagem grava {confronto.prevalente.numero} como vigente "
                f"e {fonte.numero} como histórica (fora da soma de áreas, visível "
                "na linhagem)."
            ),
        }
    return None
