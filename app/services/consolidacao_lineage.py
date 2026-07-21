"""Lineage, âncora por INCRA e varredura de aceites perdidos.

Nasce da investigação do caso 15 (20/07), onde três coisas se somaram:

* a matrícula materializada foi a **2923** (número defasado que o CCIR declarava)
  em vez da **4698** (número atual, na certidão) — e ninguém conseguia dizer de
  onde o 2923 tinha vindo sem cruzar timestamps na mão;
* o **NIRF** foi aceito, a coluna existe, e o valor não chegou: as linhas do ITR
  ficam com `matricula_hint` NULL, porque o ITR não declara número de matrícula
  (identifica o imóvel por NIRF/CIB e código INCRA — Ficha 08 §4);
* o **VTN** foi aceito e não tem coluna nenhuma: perdido em silêncio.

Aqui moram as três respostas: certidão de nascimento do registro, âncora do ITR
pelo código INCRA normalizado, e a varredura que transforma aceite perdido em
pendência visível (P12 — nada some sem dizer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.matricula import Matricula

# ---------------------------------------------------------------------------
# Normalização de código (Ficha 08 §8)
# ---------------------------------------------------------------------------

def norm_incra(valor: Any) -> str:
    """Só os dígitos do código INCRA/SNCR.

    `norm_compare` NÃO serve aqui: ela colapsa pontuação em ESPAÇO, então
    ``000.051.123.390-9`` vira ``000 051 123 390 9`` e ``000051.123390-9`` vira
    ``000051 123390 9`` — o mesmo código em dois agrupamentos diferentes, que
    não casam. Foi assim que o ITR do caso 15 ficou órfão de matrícula.

    O código é numérico e a formatação varia por documento (o CCIR pontua, o ITR
    agrupa diferente). Comparar por dígitos é o único critério estável.
    """
    if valor is None:
        return ""
    if isinstance(valor, dict):
        valor = valor.get("value", "")
    return "".join(ch for ch in str(valor) if ch.isdigit())


# ---------------------------------------------------------------------------
# Lineage — certidão de nascimento do registro
# ---------------------------------------------------------------------------

def registrar_lineage_criacao(
    mat: Matricula,
    *,
    staging: Optional[ExtractedFieldStaging],
    motivo: str = "hint_staging_aceito",
) -> None:
    """Carimba de qual staging/decisão a matrícula nasceu.

    `field_sources` responde "que tipo de fonte?"; isto responde "qual linha, qual
    decisão, de quem". A pergunta que a investigação do caso 15 não conseguiu
    responder sem arqueologia de timestamps.
    """
    atual = dict(mat.lineage or {})
    atual["criada_por"] = {
        "motivo": motivo,
        "staging_id": getattr(staging, "id", None),
        "document_id": getattr(staging, "document_id", None),
        "decided_by_user_id": getattr(staging, "decided_by_user_id", None),
        "decided_at": (
            staging.decided_at.isoformat()
            if staging is not None and staging.decided_at is not None
            else None
        ),
        "numero_matricula": mat.numero_matricula,
    }
    mat.lineage = atual


def registrar_lineage_campo(
    mat: Matricula, campo: str, staging: ExtractedFieldStaging, *, extra: Optional[str] = None
) -> None:
    """Carimba qual linha de staging escreveu cada campo."""
    atual = dict(mat.lineage or {})
    campos = dict(atual.get("campos") or {})
    campos[campo] = {
        "staging_id": staging.id,
        "document_id": staging.document_id,
        **({"via": extra} if extra else {}),
    }
    atual["campos"] = campos
    mat.lineage = atual


# ---------------------------------------------------------------------------
# Âncora do ITR pelo código INCRA (Ficha 08 §4)
# ---------------------------------------------------------------------------

@dataclass
class AncoragemIncra:
    """Resultado da tentativa de ancorar linhas órfãs a uma matrícula."""

    matricula: Optional[Matricula] = None
    codigo: str = ""
    ambiguo: bool = False           # o código casa 2+ matrículas
    divergente: bool = False        # o documento traz códigos INCRA diferentes entre si
    candidatas: list[int] = field(default_factory=list)

    @property
    def vinculavel(self) -> bool:
        """Só o caso LIMPO vincula sozinho: casamento único e sem divergência."""
        return self.matricula is not None and not self.ambiguo and not self.divergente


def ancorar_por_incra(
    db: Session,
    *,
    tenant_id: int,
    property_id: int,
    codigos_do_documento: list[Any],
) -> AncoragemIncra:
    """Encontra a matrícula do imóvel cujo código INCRA casa com o do documento.

    Regra (Ficha 08 §4 + salvaguardas da skill da Isis de 20/07):

    * **um** código normalizado, casando **uma** matrícula → vincula;
    * o documento traz códigos INCRA **diferentes entre si** → não vincula
      (é o alerta "matrícula com INCRAs distintos");
    * o código casa **2+** matrículas → não vincula (ambíguo).

    Nos dois últimos casos o chamador emite pendência + proposta de 1 clique.
    O automático só existe no caso limpo.
    """
    normalizados = {norm_incra(c) for c in codigos_do_documento}
    normalizados.discard("")

    if not normalizados:
        return AncoragemIncra()

    if len(normalizados) > 1:
        return AncoragemIncra(divergente=True, codigo=", ".join(sorted(normalizados)))

    codigo = normalizados.pop()
    matriculas = (
        db.query(Matricula)
        .filter(
            Matricula.tenant_id == tenant_id,
            Matricula.property_id == property_id,
            Matricula.deactivated_at.is_(None),
        )
        .all()
    )
    casadas = [m for m in matriculas if norm_incra(m.codigo_incra_sncr) == codigo]

    if len(casadas) == 1:
        return AncoragemIncra(matricula=casadas[0], codigo=codigo, candidatas=[casadas[0].id])
    if len(casadas) > 1:
        return AncoragemIncra(
            codigo=codigo, ambiguo=True, candidatas=[m.id for m in casadas]
        )
    return AncoragemIncra(codigo=codigo)


# ---------------------------------------------------------------------------
# Cascata de vinculação ITR → matrícula (spec da Isis, 20/07)
# ---------------------------------------------------------------------------

@dataclass
class Vinculacao:
    """Resultado da cascata. `nivel` diz por QUAL sinal chegou aqui."""

    matricula: Optional[Matricula] = None
    nivel: int = 0                    # 1=NIRF · 2=INCRA · 3=corroboração · 0=nenhum
    sinal: str = ""
    autolink: bool = False            # só 1 e 2 autolinkam
    candidatas: list[dict[str, Any]] = field(default_factory=list)
    motivo: str = ""


def vincular_itr(
    db: Session,
    *,
    tenant_id: int,
    property_id: int,
    nirf: Any = None,
    codigos_incra: Optional[list[Any]] = None,
    area: Any = None,
    denominacao: Any = None,
) -> Vinculacao:
    """Cascata do mais forte ao mais fraco (spec da Isis, 20/07).

    1. **NIRF normalizado** — se casa UMA matrícula, vincula (alta confiança).
    2. **INCRA normalizado** — só se o match for ÚNICO.
    3. **Corroboração (área + denominação)** — desempate quando o INCRA não
       resolve. **NUNCA autolinka**, mesmo com os dois batendo: é sugestão de
       alta probabilidade. A Isis foi explícita, e nenhuma otimização pode
       promover sugestão a vínculo.
    4. Nada resolveu → o consultor decide, vendo os candidatos e os sinais a
       favor de cada um (a decisão dele vira proveniência).
    """
    matriculas = (
        db.query(Matricula)
        .filter(
            Matricula.tenant_id == tenant_id,
            Matricula.property_id == property_id,
            Matricula.deactivated_at.is_(None),
        )
        .all()
    )
    if not matriculas:
        return Vinculacao(motivo="o imóvel ainda não tem matrícula na base")

    # ---- Degrau 1: NIRF ----------------------------------------------------
    alvo_nirf = norm_incra(nirf)
    if alvo_nirf:
        casadas = [m for m in matriculas if norm_incra(m.nirf_cib) == alvo_nirf]
        if len(casadas) == 1:
            return Vinculacao(
                matricula=casadas[0], nivel=1, sinal="nirf", autolink=True,
                motivo=f"NIRF {nirf} casa com a matrícula {casadas[0].numero_matricula}",
            )

    # ---- Degrau 2: INCRA ---------------------------------------------------
    anc = ancorar_por_incra(
        db, tenant_id=tenant_id, property_id=property_id,
        codigos_do_documento=codigos_incra or [],
    )
    if anc.vinculavel:
        return Vinculacao(
            matricula=anc.matricula, nivel=2, sinal="incra", autolink=True,
            motivo=f"código INCRA casa apenas com {anc.matricula.numero_matricula}",
        )

    # ---- Degrau 3: corroboração — DÍVIDA (recorte do André, 20/07) ---------
    # Área + denominação como desempate ranqueado, e a tela rica de "sinais a
    # favor", ficam para follow-up: é refinamento de UX, e enquanto não existem
    # o caso ambíguo cai no degrau 4 manual, que resolve. A cascata da Isis
    # (20/07) é a spec da dívida.
    # ---- Degrau 4: o consultor decide --------------------------------------
    return Vinculacao(
        candidatas=[
            {"matricula_id": m.id, "numero_matricula": m.numero_matricula, "sinais": []}
            for m in matriculas
        ],
        motivo=(
            "nenhum sinal resolveu com segurança — escolha a matrícula "
            "(a decisão fica registrada como proveniência)"
        ),
    )

# ---------------------------------------------------------------------------
# Varredura de aceites perdidos (P12 — nada some sem dizer)
# ---------------------------------------------------------------------------

@dataclass
class AceitePerdido:
    staging_id: int
    document_id: Optional[int]
    field_name: str
    target_entity: Optional[str]
    target_field: Optional[str]
    motivo: str                       # "sem_coluna" | "sem_dono"
    detalhe: str
    sugestao_matricula_id: Optional[int] = None


def _colunas_de(entidade: Optional[str]) -> set[str]:
    from app.models.client import Client  # noqa: PLC0415
    from app.models.property import Property  # noqa: PLC0415

    modelo = {"matricula": Matricula, "imovel": Property, "cliente": Client}.get(
        (entidade or "").lower()
    )
    if modelo is None:
        return set()
    return {c.name for c in modelo.__table__.columns}


def varrer_aceites_perdidos(
    db: Session,
    *,
    tenant_id: int,
    process_id: int,
    property_id: Optional[int] = None,
) -> list[AceitePerdido]:
    """Toda linha ACEITA ou virou dado na base, ou aparece aqui.

    Duas classes distintas, que um guard só de schema não separaria:

    * **sem_coluna** — o `target_field` não existe no modelo de destino (`vtn`).
      O aceite não tinha para onde ir desde sempre.
    * **sem_dono** — a coluna existe e o aceite é válido, mas a linha não está
      ancorada a nenhuma entidade (`nirf_cib` com `matricula_hint` NULL). Tem
      destino, falta dono.

    A segunda classe é a que o caso 15 revelou e que uma varredura de schema
    deixaria passar em silêncio.
    """
    perdidos: list[AceitePerdido] = []

    linhas = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.status == ExtractedFieldStatus.aceito,
        )
        .all()
    )

    for linha in linhas:
        alvo = (linha.target_field or "").strip()
        if not alvo:
            continue

        colunas = _colunas_de(linha.target_entity)
        if colunas and alvo not in colunas:
            perdidos.append(AceitePerdido(
                staging_id=linha.id, document_id=linha.document_id,
                field_name=linha.field_name, target_entity=linha.target_entity,
                target_field=alvo, motivo="sem_coluna",
                detalhe=(
                    f"campo sem destino: {linha.target_entity}.{alvo} não existe no "
                    "modelo — o aceite não tem onde ser gravado"
                ),
            ))
            continue

        # Sem dono: destino de matrícula, mas a linha não está ancorada a nenhuma.
        if (linha.target_entity or "").lower() == "matricula" and not (
            (linha.matricula_hint or "").strip()
        ):
            perdidos.append(AceitePerdido(
                staging_id=linha.id, document_id=linha.document_id,
                field_name=linha.field_name, target_entity=linha.target_entity,
                target_field=alvo, motivo="sem_dono",
                detalhe=(
                    f"aceito aguardando vínculo: {alvo} — nenhuma matrícula ancorada "
                    "a este documento"
                ),
            ))

    return perdidos

def vincular_manualmente(
    db: Session,
    *,
    tenant_id: int,
    process_id: int,
    document_id: int,
    matricula_id: int,
    user_id: Optional[int],
) -> int:
    """Degrau 4 — o consultor escolhe a matrícula; a escolha vira proveniência.

    Ancora TODAS as linhas de staging daquele documento à matrícula escolhida
    (preenchendo `matricula_hint`), que é o que faltava para o aceite ter onde
    pousar. A decisão fica registrada com quem/quando/sinal — a Isis observou
    que isso é útil se a divergência de INCRA virar retificação formal depois.

    Devolve quantas linhas foram ancoradas.
    """
    mat = (
        db.query(Matricula)
        .filter(Matricula.id == matricula_id, Matricula.tenant_id == tenant_id)
        .first()
    )
    if mat is None:
        raise ValueError(f"matrícula {matricula_id} não encontrada")

    linhas = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.document_id == document_id,
        )
        .all()
    )
    for linha in linhas:
        linha.matricula_hint = mat.numero_matricula

    atual = dict(mat.lineage or {})
    vinculos = list(atual.get("vinculos_manuais") or [])
    vinculos.append({
        "document_id": document_id,
        "user_id": user_id,
        "sinal": "manual",
        "linhas_ancoradas": len(linhas),
    })
    atual["vinculos_manuais"] = vinculos
    mat.lineage = atual
    db.flush()
    return len(linhas)
