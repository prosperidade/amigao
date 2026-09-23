"""Retrato de fatos do caso (ADR-073 §3).

O motor não lê texto. Lê este retrato, montado de forma determinística a partir de:
documentos por espécie (`classificacao_documento`), observações do extrator
(`evidence_versions`), declarações da abertura (`processes`) e cadastro do imóvel.

Cada fato: ``{"valor", "estado": determinado|desconhecido, "origem": {...},
"revisao": revisada|nao_revisada}``.

Fatos ``*.no_dossie`` afirmam o que CONSTA NOS AUTOS, não o que existe no mundo — por
isso são sempre determinados (a ausência nos autos é um fato sobre os autos). Já o
falecimento do titular não é: ausência de observação é desconhecido, nunca "vivo".
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.process import Process

# Demanda de CAR declarada na abertura (o CAR só existe para imóvel rural).
DEMANDAS_CAR = frozenset({"car", "retificacao_car"})

# Rótulo do upload → espécie, para documento que a entrada semântica ainda não
# classificou. Só as espécies que o gate lê; o resto não conta para nenhum fato.
_ESPECIE_DO_UPLOAD = {"matricula": "certidao_matricula", "car": "car", "ccir": "ccir"}


def _fato(valor, estado: str, origem: dict, revisao: str) -> dict:
    return {"valor": valor, "estado": estado, "origem": origem, "revisao": revisao}


def _documentos(session: Session, tenant_id: int, process_id: int) -> list[dict]:
    """Documentos vivos do caso com a espécie vigente (revisada vence proposta)."""
    rows = session.execute(text(
        """
        SELECT d.id, lower(d.document_type) AS upload,
               c.especie, c.revisada
          FROM documents d
          LEFT JOIN LATERAL (
                SELECT coalesce(cd.tipo_revisado, cd.tipo_proposto) AS especie,
                       cd.tipo_revisado IS NOT NULL AS revisada
                  FROM classificacao_documento cd
                 WHERE cd.documento_id = d.id AND cd.tenant_id = d.tenant_id
                 ORDER BY cd.versao DESC LIMIT 1) c ON true
         WHERE d.tenant_id = :t AND d.process_id = :p AND d.deleted_at IS NULL
         ORDER BY d.id
        """
    ), {"t": tenant_id, "p": process_id}).all()
    out = []
    for r in rows:
        if r.especie:
            out.append({"id": r.id, "especie": r.especie, "fonte": "classificacao",
                        "revisada": bool(r.revisada)})
        elif r.upload in _ESPECIE_DO_UPLOAD:
            out.append({"id": r.id, "especie": _ESPECIE_DO_UPLOAD[r.upload], "fonte": "rotulo_upload",
                        "revisada": False})
    return out


def _presenca(docs: list[dict], especie: str) -> tuple[list[int], str]:
    ids = [d["id"] for d in docs if d["especie"] == especie]
    revisao = "revisada" if ids and all(d["revisada"] for d in docs if d["id"] in ids) else "nao_revisada"
    return ids, revisao


def _falecimentos(session: Session, tenant_id: int, process_id: int) -> list[int]:
    """Observações vigentes de falecimento declarado (não invalidadas)."""
    return [r[0] for r in session.execute(text(
        """
        SELECT e.id FROM evidence_versions e
         WHERE e.tenant_id = :t AND e.process_id = :p AND e.kind = 'observacao'
           AND e.predicate = 'falecimento_declarado'
           AND NOT EXISTS (SELECT 1 FROM evidence_invalidations i WHERE i.evidence_id = e.id)
         ORDER BY e.id
        """
    ), {"t": tenant_id, "p": process_id}).all()]


def montar_fatos(session: Session, *, process: Process, tenant_id: int) -> dict[str, dict]:
    docs = _documentos(session, tenant_id, process.id)
    fatos: dict[str, dict] = {}

    uf = None
    if process.property_id is not None:
        uf = session.execute(text(
            "SELECT upper(nullif(trim(state), '')) FROM properties WHERE id = :i AND tenant_id = :t"
        ), {"i": process.property_id, "t": tenant_id}).scalar()
    fatos["caso.uf"] = (
        _fato(uf, "determinado", {"imovel_id": process.property_id}, "nao_revisada") if uf
        else _fato(None, "desconhecido", {"imovel_id": process.property_id}, "nao_revisada")
    )

    car_ids, car_rev = _presenca(docs, "car")
    fatos["car.no_dossie"] = _fato(bool(car_ids), "determinado", {"documentos": car_ids}, car_rev)

    mat_ids, mat_rev = _presenca(docs, "certidao_matricula")
    fatos["dominio.matriculas_no_dossie"] = _fato(len(mat_ids), "determinado", {"documentos": mat_ids}, mat_rev)

    ccir_ids, ccir_rev = _presenca(docs, "ccir")
    fatos["ccir.no_dossie"] = _fato(bool(ccir_ids), "determinado", {"documentos": ccir_ids}, ccir_rev)

    demandas = {
        str(getattr(v, "value", v) or "").lower()
        for v in (process.process_type, getattr(process, "demand_type", None)) if v
    }
    demanda_car = sorted(demandas & DEMANDAS_CAR)
    if demanda_car or car_ids:
        fatos["imovel.natureza"] = _fato(
            "rural", "determinado",
            {"declaracao_abertura": demanda_car, "documentos": car_ids}, car_rev if car_ids else "nao_revisada",
        )
    else:
        # Nem demanda de CAR nem CAR nos autos: a natureza não se decide daqui.
        fatos["imovel.natureza"] = _fato(None, "desconhecido", {"declaracao_abertura": sorted(demandas)},
                                         "nao_revisada")

    obitos = _falecimentos(session, tenant_id, process.id)
    fatos["titular.falecimento_declarado"] = (
        _fato(True, "determinado", {"observacoes": obitos}, "nao_revisada") if obitos
        else _fato(None, "desconhecido", {"observacoes": []}, "nao_revisada")
    )
    return fatos


def hash_fatos(fatos: dict[str, dict]) -> str:
    return hashlib.sha256(json.dumps(fatos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
