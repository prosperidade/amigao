"""Confronto de identidade da matrícula + cadeia proposta ANTES da decisão.

O erro do caso 15 em uma frase: o CCIR do Lote 1B declara `2923` (número
registral defasado), a certidão do mesmo lote declara `4698` (número atual), e
**a Conferência nunca colocou os dois lado a lado**. O consultor aceitou o CCIR,
rejeitou a certidão, e a base nasceu com o número errado — sem que nada na tela
sugerisse que havia uma escolha de identidade sendo feita.

Duas correções moram aqui:

* **Confronto** — quando dois ou mais documentos **do mesmo lote** declaram
  números de matrícula diferentes, isso vira a primeira coisa da tela, com a
  fonte de cada número e a hierarquia da Ficha 08 §5.1 DECLARADA em texto ("a
  certidão de matrícula é a fonte jurídica; o CCIR está defasado"). É a
  divergência mais cara do domínio: identidade jurídica do imóvel.
* **Cadeia antes da decisão** — a proposta de linhagem (#60) nasce da chegada do
  staging, não depois. No caso 15 o `registro_anterior` (2.923) estava numa
  linha que o consultor rejeitou, e a rejeição matou o sinal que teria evitado
  a própria rejeição errada.

**Agrupamento por lote (requisito da Isis, 21/07):** uma fazenda tem vários
lotes com matrículas distintas — 6776 (Lote 1C) e 4698 (Lote 1B) NÃO estão em
confronto, são lotes diferentes. Confrontar números de lotes distintos seria
veneno novo com cara de feature. Só confrontam números que descrevem O MESMO
lote; a assinatura de lote vem da ÁREA do documento (sinal mais confiável —
mesma terra, mesma área) e, na falta dela, do token de lote/gleba da denominação.
Conservador de propósito: na dúvida NÃO agrupa (perder um confronto real é
tratável pela cadeia; inventar um falso não é).

Nada aqui decide: tudo PROPÕE, com a fonte à vista. O consultor decide.
"""

from __future__ import annotations

import re
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

# Token de lote/gleba da denominação — assinatura de lote secundária (a área é a
# primária). "Lote 1 B" → "lote 1"; zeros à esquerda normalizados ("01" → "1").
_LOTE_RE = re.compile(r"\b(lote|gleba|quadra|chac(?:ara|ára)|s[ií]tio)\s+([0-9a-z]+)\b")


def _peso(doc_type: Optional[str]) -> int:
    return _PESO_JURIDICO.get((doc_type or "").strip().lower(), _PESO_DESCONHECIDO)


def _rotulo(doc_type: Optional[str]) -> str:
    return _ROTULO_FONTE.get((doc_type or "").strip().lower(), doc_type or "documento")


def _numero(valor: Any) -> str:
    """Número da matrícula comparável: só dígitos ('2.923' == '2923')."""
    if isinstance(valor, dict):
        valor = valor.get("value", "")
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def _unwrap(valor: Any) -> Any:
    """Desembrulha o `{'value': ..., 'unidade': ...}` do staging."""
    return valor.get("value") if isinstance(valor, dict) else valor


def _lote_token(denominacao: Any) -> Optional[str]:
    """Token de lote/gleba normalizado da denominação ("Lote 01 B" → "lote 1")."""
    texto = _unwrap(denominacao)
    if not isinstance(texto, str):
        return None
    m = _LOTE_RE.search(texto.lower())
    if not m:
        return None
    numero = m.group(2).lstrip("0") or m.group(2)
    return f"{m.group(1)} {numero}"


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
    lote_sig: Optional[str] = None   # assinatura do lote (área/denominação)


@dataclass
class ConfrontoIdentidade:
    """Números de matrícula concorrentes no MESMO lote."""

    fontes: list[FonteNumero] = field(default_factory=list)
    prevalente: Optional[FonteNumero] = None
    regra: str = ""
    cadeia_proposta: Optional[dict[str, Any]] = None
    lote: Optional[str] = None       # rótulo do lote (contexto na tela)

    @property
    def ha_confronto(self) -> bool:
        """Só é confronto quando os números DIVERGEM entre si."""
        return len({f.numero_norm for f in self.fontes}) > 1


def _lote_signature_map(
    db: Session, tenant_id: int, process_id: int
) -> dict[int, str]:
    """Assinatura de lote por documento — para NÃO confrontar lotes distintos.

    Primário: área do documento (arredondada a 2 casas — mesma terra, mesma
    área). Secundário: token de lote/gleba da denominação. Documento sem
    nenhum dos dois fica de fora do mapa (assinatura própria → não agrupa)."""
    from app.services.inconsistency_matrix import parse_area_ha  # noqa: PLC0415

    rows = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.target_field.in_(("area_ha", "denominacao_imovel")),
        )
        .all()
    )
    area_by_doc: dict[int, float] = {}
    lote_by_doc: dict[int, str] = {}
    for r in rows:
        if r.document_id is None:
            continue
        if r.target_field == "area_ha" and r.document_id not in area_by_doc:
            fv = r.field_value
            ha = parse_area_ha(_unwrap(fv), fv.get("unidade") if isinstance(fv, dict) else None)
            if ha is not None:
                area_by_doc[r.document_id] = round(ha, 2)
        elif r.target_field == "denominacao_imovel" and r.document_id not in lote_by_doc:
            tok = _lote_token(r.field_value)
            if tok:
                lote_by_doc[r.document_id] = tok

    sig: dict[int, str] = {}
    for doc_id in set(area_by_doc) | set(lote_by_doc):
        if doc_id in area_by_doc:
            sig[doc_id] = f"area:{area_by_doc[doc_id]}"
        else:
            sig[doc_id] = f"lote:{lote_by_doc[doc_id]}"
    return sig


def detectar_confrontos(
    db: Session, *, tenant_id: int, process_id: int
) -> list[ConfrontoIdentidade]:
    """Confrontos de identidade do caso, UM POR LOTE com números divergentes.

    Considera TODAS as linhas de `numero_matricula`, independentemente do status
    — inclusive as já rejeitadas. É deliberado: no caso 15 o número correto
    estava justamente na linha rejeitada, e esconder o que foi rejeitado seria
    esconder a própria evidência de que a decisão precisa ser revista.

    Agrupa por lote antes de confrontar: números de lotes distintos da mesma
    fazenda (6776/1C × 4698/1B) NUNCA se confrontam.
    """
    sig_map = _lote_signature_map(db, tenant_id, process_id)
    linhas = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.field_name == "numero_matricula",
        )
        .all()
    )

    # Agrupa por assinatura de lote. A separação exige EVIDÊNCIA POSITIVA de
    # lotes distintos (áreas diferentes): 6776/1C (349 ha) e 4698/1B (660 ha)
    # caem em grupos distintos e não se confrontam. Sem assinatura conhecida, a
    # linha vai para um grupo COMUM ("sem-assinatura") e ainda confronta — a
    # ausência de sinal não é prova de lotes distintos, e o confronto é só um
    # convite a decidir. Conservador: não inventa separação, não inventa união.
    grupos: dict[str, list[FonteNumero]] = {}
    for linha in linhas:
        norm = _numero(linha.field_value)
        if not norm:
            continue
        lote_sig = sig_map.get(linha.document_id) if linha.document_id is not None else None
        chave = lote_sig or "sem-assinatura"
        grupos.setdefault(chave, []).append(FonteNumero(
            numero=str(_unwrap(linha.field_value)),
            numero_norm=norm,
            document_id=linha.document_id, doc_type=linha.source_doc_type,
            rotulo_fonte=_rotulo(linha.source_doc_type),
            peso=_peso(linha.source_doc_type),
            status=linha.status.value if linha.status else "pendente",
            staging_id=linha.id, lote_sig=lote_sig,
        ))

    confrontos: list[ConfrontoIdentidade] = []
    for chave, fontes in grupos.items():
        confronto = ConfrontoIdentidade(
            fontes=sorted(fontes, key=lambda f: f.peso),
            lote=chave if chave != "sem-assinatura" else None,
        )
        if not confronto.ha_confronto:
            continue
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
        confrontos.append(confronto)
    return confrontos


def detectar_confronto(
    db: Session, *, tenant_id: int, process_id: int
) -> ConfrontoIdentidade:
    """Compat: primeiro confronto detectado (ou vazio). Prefira
    ``detectar_confrontos`` — o caso pode ter mais de um lote em confronto."""
    todos = detectar_confrontos(db, tenant_id=tenant_id, process_id=process_id)
    return todos[0] if todos else ConfrontoIdentidade()


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
