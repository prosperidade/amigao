"""Serviço geoespacial determinístico (ADR-072). O chamador faz commit/rollback.

Leitura → feições (PostGIS valida e transforma) → medição calculada →
projeção em ``Property.geom``. Medições declaradas saem do literal ancorado das
observações; o confronto é do auditor (``property_audit.confrontar_areas``).
Nenhum número passa por LLM.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.document import Document
from app.models.evidence import EvidenceInvalidation, EvidenceVersion
from app.models.geometria import ArquivoGeo, ConfrontoArea, Feicao, Medicao, ProjecaoGeometria
from app.models.process import Process
from app.models.property import Property
from app.services import geo_leitura
from app.services.geo_files import extension_of, is_geospatial
from app.services.inconsistency_matrix import is_area_plausible, parse_area_ha
from app.services.property_audit import DENOMINADOR_REFERENCIA_DOCUMENTAL, confrontar_areas

logger = get_logger(__name__)

METODO_AREA = "postgis_st_area_geography_spheroid"
METODO_AREA_VERSAO = "072.1"
CRS_CALCULO = "EPSG:4674 (geografia, elipsoide GRS80)"
METODO_DECLARADA = "literal_ancorado_parse_area_ha"
METODO_DECLARADA_VERSAO = "072.1"
METODO_CONFRONTO_VERSAO = "072.1"
REGRA_PROJECAO_UNICA = "feicao_poligonal_unica"

# Escritura é negócio notarial, não registro (Princípio 7): fica como declaração textual.
ESPECIES_REGISTRAIS = ("matricula", "certidao_matricula", "registro", "transcricao")
_UNIDADES_HA = {"ha", "hectare", "hectares", "hec", "h"}
_UNIDADES_M2 = {"m2", "m²", "metros quadrados", "metro quadrado"}
# Predicado de área que não é a do imóvel inteiro (ADR-072 §5, "Objeto").
_MARCADORES_SUBAREA = (
    "arrend", "reserva", "rl_", "_rl", "app", "preserv", "consolid", "remanesc", "veget", "uso",
    "servid", "hipotec", "garantia", "lavoura", "pastag", "benfeit", "construid", "desmat", "embarg",
    "modulo", "fiscal", "utiliz", "aproveit", "nativa", "recomp", "compens", "parcela",
)
_NUMERO = re.compile(r"\d[\d.,]*\d|\d")


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


# ---------------------------------------------------------------------------
# Leitura do arquivo
# ---------------------------------------------------------------------------

def _formato(doc: Document) -> str:
    return (doc.extension or extension_of(doc.original_file_name) or extension_of(doc.filename) or "").lower()


def eh_arquivo_geo(doc: Document) -> bool:
    return is_geospatial(doc.original_file_name or doc.filename, doc.mime_type) or doc.document_type in (
        "geoespacial", "kml_sigef", "kml", "shapefile")


def _baixar(doc: Document) -> bytes:
    from app.services.storage import StorageDownloadError, get_storage_service
    try:
        dados = get_storage_service().download_bytes(doc.storage_key)
    except StorageDownloadError as exc:
        raise geo_leitura.GeoFalha("storage_indisponivel", f"storage respondeu {exc.code}") from None
    if not dados:
        raise geo_leitura.GeoFalha("arquivo_ausente", "objeto não existe no storage")
    return dados


def processar_documento(db: Session, doc: Document, *, user_id: int | None = None,
                        dados: bytes | None = None) -> ArquivoGeo:
    """Lê o arquivo e grava leitura, feições, medições e (se regra) projeção.

    ``dados`` só é passado por quem já tem os bytes (teste, gate); o caminho
    normal baixa do storage. Mesma leitura bem-sucedida com o mesmo método é
    devolvida sem duplicar; falha sempre gera linha nova (pode ser transitória).
    """
    db.query(Document).filter_by(id=doc.id, tenant_id=doc.tenant_id).with_for_update().one()
    anterior = db.query(ArquivoGeo).filter_by(tenant_id=doc.tenant_id, documento_id=doc.id).order_by(
        ArquivoGeo.numero.desc()).first()
    numero = anterior.numero + 1 if anterior else 1
    formato = _formato(doc)
    base = dict(tenant_id=doc.tenant_id, process_id=doc.process_id, documento_id=doc.id, numero=numero,
                formato=formato or "?", metodo_versao=geo_leitura.METODO_LEITURA_VERSAO, lido_por_user_id=user_id)
    sha = None
    try:
        if formato not in geo_leitura.FORMATOS_LIDOS:
            raise geo_leitura.GeoFalha("formato_nao_suportado",
                                       f"formato '{formato or '?'}' ainda não é lido (só KMZ e KML)")
        if dados is None:
            dados = _baixar(doc)
        sha = hashlib.sha256(dados).hexdigest()
        if doc.checksum_sha256 and doc.checksum_sha256 != sha:
            raise geo_leitura.GeoFalha("hash_divergente", "bytes do storage diferem do checksum gravado no upload")
        existente = db.query(ArquivoGeo).filter_by(tenant_id=doc.tenant_id, documento_id=doc.id, estado="lido",
            sha256_original=sha, metodo_versao=geo_leitura.METODO_LEITURA_VERSAO).order_by(ArquivoGeo.numero.desc()).first()
        if existente is not None:
            _medir_e_projetar(db, existente, doc)
            return existente
        leitura = geo_leitura.ler_arquivo(dados, formato)
    except geo_leitura.GeoFalha as falha:
        row = ArquivoGeo(**base, sha256_original=sha, inventario={}, estado="falha",
                         falha_codigo=falha.codigo, falha_detalhe=falha.detalhe)
        db.add(row)
        db.flush()
        logger.info("geometria: doc=%s leitura %s falhou [%s]", doc.id, numero, falha.codigo)
        return row

    row = ArquivoGeo(**base, sha256_original=sha, membro_lido=leitura.membro_lido, inventario=leitura.inventario,
                     crs_origem=geo_leitura.CRS_KML, estado="lido")
    db.add(row)
    db.flush()
    for f in leitura.feicoes:
        _gravar_feicao(db, row, f)
    db.flush()
    _medir_e_projetar(db, row, doc)
    return row


def _medir_e_projetar(db: Session, arquivo: ArquivoGeo, doc: Document) -> None:
    # Arquivo lido ainda no rascunho (sem caso) é medido quando ganha caso.
    if doc.process_id:
        _medir_feicoes(db, arquivo, doc)
        _projetar_se_regra(db, arquivo, doc)


def _gravar_feicao(db: Session, arquivo: ArquivoGeo, f: geo_leitura.FeicaoLida) -> None:
    db.execute(text("""
        WITH g AS (SELECT ST_GeomFromText(:wkt, :srid) AS o)
        INSERT INTO feicao (tenant_id, arquivo_geo_id, ordem, identificador_interno, nome, tipo, srid_origem,
                            geom_original, geom, valida, motivo_invalidade, aneis_internos)
        SELECT :tenant, :arquivo, :ordem, :ident, :nome, :tipo, :srid, g.o, ST_Transform(g.o, 4674),
               ST_IsValid(g.o), CASE WHEN ST_IsValid(g.o) THEN NULL ELSE ST_IsValidReason(g.o) END, :internos
        FROM g"""), {"wkt": f.wkt, "srid": geo_leitura.SRID_KML, "tenant": arquivo.tenant_id, "arquivo": arquivo.id,
                     "ordem": f.ordem, "ident": f.identificador_interno, "nome": f.nome, "tipo": f.tipo,
                     "internos": f.aneis_internos})


def _medir_feicoes(db: Session, arquivo: ArquivoGeo, doc: Document) -> None:
    motor = db.execute(text("SELECT postgis_lib_version()")).scalar()
    for feicao in db.query(Feicao).filter_by(tenant_id=arquivo.tenant_id, arquivo_geo_id=arquivo.id).order_by(Feicao.ordem):
        if feicao.tipo not in ("poligono", "multipoligono"):
            continue
        ja = db.query(Medicao).filter_by(tenant_id=arquivo.tenant_id, feicao_id=feicao.id,
                                         metodo_versao=METODO_AREA_VERSAO).first()
        if ja is not None:
            continue
        comum = dict(tenant_id=arquivo.tenant_id, process_id=doc.process_id, grandeza="area", objeto="imovel_total",
                     origem_tipo="feicao_calculada", metodo=METODO_AREA, metodo_versao=METODO_AREA_VERSAO,
                     crs_calculo=CRS_CALCULO, motor_versao=f"PostGIS {motor}", documento_id=doc.id, feicao_id=feicao.id)
        if not feicao.valida:
            db.add(Medicao(**comum, estado="nao_determinado",
                           motivo=f"geometria inválida: {feicao.motivo_invalidade}"))
            continue
        m2 = db.execute(text("SELECT ST_Area(geom::geography, true) FROM feicao WHERE id = :id"),
                        {"id": feicao.id}).scalar()
        valor = Decimal(str(m2)) / Decimal(10000)
        if valor <= 0:
            db.add(Medicao(**comum, estado="nao_determinado", motivo="área calculada nula"))
        else:
            db.add(Medicao(**comum, estado="determinado", valor_ha=valor))
    db.flush()


def _projetar_se_regra(db: Session, arquivo: ArquivoGeo, doc: Document) -> None:
    case = db.query(Process).filter_by(id=doc.process_id, tenant_id=doc.tenant_id).first()
    property_id = (case.property_id if case else None) or doc.property_id
    if not property_id:
        return
    poligonais = db.query(Feicao).filter(Feicao.tenant_id == arquivo.tenant_id, Feicao.arquivo_geo_id == arquivo.id,
                                         Feicao.tipo.in_(("poligono", "multipoligono"))).all()
    if len(poligonais) != 1 or not poligonais[0].valida:
        return
    if db.query(ProjecaoGeometria).filter_by(tenant_id=doc.tenant_id, property_id=property_id).first():
        return
    _projetar(db, doc.tenant_id, property_id, doc.process_id, poligonais[0],
              regra=REGRA_PROJECAO_UNICA, autor_id=None,
              motivo=f"Única feição poligonal válida de {doc.original_file_name}")


def _projetar(db, tenant_id, property_id, process_id, feicao, *, regra, autor_id, motivo):
    db.add(ProjecaoGeometria(tenant_id=tenant_id, property_id=property_id, process_id=process_id,
                             feicao_id=feicao.id, regra=regra, autor_id=autor_id, motivo=motivo))
    db.flush()
    db.execute(text("UPDATE properties SET geom = (SELECT geom FROM feicao WHERE id = :f AND tenant_id = :t) "
                    "WHERE id = :p AND tenant_id = :t"), {"f": feicao.id, "p": property_id, "t": tenant_id})


def escolher_projecao(db: Session, tenant_id: int, user_id: int, process_id: int, feicao_id: int, motivo: str):
    """Decisão do consultor: qual feição é o imóvel. Motivo obrigatório."""
    if not motivo or not motivo.strip():
        raise HTTPException(422, "Motivo obrigatório para escolher a geometria do imóvel")
    case = db.query(Process).filter_by(id=process_id, tenant_id=tenant_id).first()
    if case is None or not case.property_id:
        raise HTTPException(404, "Caso sem imóvel vinculado")
    feicao = (db.query(Feicao).join(ArquivoGeo, ArquivoGeo.id == Feicao.arquivo_geo_id)
              .join(Document, Document.id == ArquivoGeo.documento_id)
              .filter(Feicao.id == feicao_id, Feicao.tenant_id == tenant_id, Document.tenant_id == tenant_id,
                      Document.process_id == process_id).first())
    if feicao is None:
        raise HTTPException(404, "Feição não encontrada neste caso")
    if feicao.tipo not in ("poligono", "multipoligono") or not feicao.valida:
        raise HTTPException(422, "Só feição poligonal válida pode ser a geometria do imóvel")
    _projetar(db, tenant_id, case.property_id, process_id, feicao, regra=None, autor_id=user_id, motivo=motivo.strip())


# ---------------------------------------------------------------------------
# Medições declaradas: literal ancorado → número, sem LLM
# ---------------------------------------------------------------------------

def predicado_de_area_total(predicado: str | None) -> bool:
    p = _sem_acento(predicado or "")
    return "area" in p and not any(m in p for m in _MARCADORES_SUBAREA)


def _valor_normalizado(normalized) -> Decimal | None:
    valor = (normalized or {}).get("valor") if isinstance(normalized, dict) else None
    if isinstance(valor, dict):
        valor = next((valor[k] for k in ("area", "area_ha", "valor", "value") if k in valor), None)
    if valor is None or isinstance(valor, (dict, list)):
        return None
    ha = parse_area_ha(valor)
    return Decimal(str(ha)) if ha is not None else None


def valor_declarado(literal: str | None, unidade: str | None, normalized=None) -> tuple[Decimal | None, str | None]:
    """(valor em ha, motivo quando não determinado). O LLM só desempata."""
    if not literal or not literal.strip():
        return None, "observação sem literal ancorado"
    u = _sem_acento((unidade or "").strip())
    if u in _UNIDADES_M2:
        fator = Decimal(1) / Decimal(10000)
    elif u in _UNIDADES_HA or u == "":
        fator = Decimal(1)
    else:
        return None, f"unidade '{unidade}' não é hectare nem m²; conversão não é feita pelo sistema"
    candidatos = []
    for token in _NUMERO.findall(literal):
        ha = parse_area_ha(token)
        if ha is not None and ha > 0:
            valor = Decimal(str(ha)) * fator
            if valor not in candidatos:
                candidatos.append(valor)
    if not candidatos:
        return None, "literal sem número de área"
    if len(candidatos) > 1:
        proposto = _valor_normalizado(normalized)
        if proposto is not None:
            proposto *= fator
        if proposto is None or proposto not in candidatos:
            return None, f"literal com {len(candidatos)} números; nenhum identificado sem ambiguidade"
        candidatos = [proposto]
    if not is_area_plausible(float(candidatos[0])):
        return None, f"{candidatos[0]} ha fora da faixa plausível de imóvel"
    return candidatos[0], None


def _observacoes_de_area(db: Session, tenant_id: int, process_id: int) -> list[EvidenceVersion]:
    rows = db.query(EvidenceVersion).filter(EvidenceVersion.tenant_id == tenant_id,
        EvidenceVersion.process_id == process_id, EvidenceVersion.kind == "observacao",
        EvidenceVersion.predicate.ilike("%area%")).all()
    ultimas: dict[str, EvidenceVersion] = {}
    for r in rows:
        if r.object_id not in ultimas or r.version > ultimas[r.object_id].version:
            ultimas[r.object_id] = r
    invalidadas = {i.evidence_id for i in db.query(EvidenceInvalidation.evidence_id).filter(
        EvidenceInvalidation.tenant_id == tenant_id, EvidenceInvalidation.process_id == process_id)}
    from app.services.evidence import reviews_by_evidence
    revisoes = reviews_by_evidence(db, tenant_id, process_id)
    vivas = []
    for r in ultimas.values():
        ultima_revisao = (revisoes.get(r.id) or [None])[-1]
        if r.id in invalidadas or (ultima_revisao and ultima_revisao.action in ("rejeitar", "nao_aplicavel")):
            continue
        if predicado_de_area_total(r.predicate):
            vivas.append(r)
    return sorted(vivas, key=lambda r: r.id)


def _especie(db: Session, doc: Document) -> str:
    from app.services.entrada_semantica import classificacao_atual
    c = classificacao_atual(db, doc)
    return ((c.tipo_revisado or c.tipo_proposto) if c else doc.document_type) or "indeterminada"


def medir_declaracoes(db: Session, tenant_id: int, process_id: int) -> list[Medicao]:
    novas = []
    for obs in _observacoes_de_area(db, tenant_id, process_id):
        if db.query(Medicao).filter_by(tenant_id=tenant_id, evidence_version_id=obs.id,
                                       metodo_versao=METODO_DECLARADA_VERSAO).first():
            continue
        attrs = (obs.content or {}).get("attributes") or {}
        doc_id = obs.source_document_id or attrs.get("document_id")
        doc = db.query(Document).filter_by(id=doc_id, tenant_id=tenant_id).first() if doc_id else None
        if doc is None:
            continue
        especie = _especie(db, doc)
        origem = "registro" if any(e in _sem_acento(especie) for e in ESPECIES_REGISTRAIS) else "declaracao_textual"
        valor, motivo = valor_declarado(attrs.get("literal"), attrs.get("unit"), attrs.get("normalized"))
        m = Medicao(tenant_id=tenant_id, process_id=process_id, grandeza="area", objeto="imovel_total",
                    origem_tipo=origem, estado="determinado" if valor is not None else "nao_determinado",
                    valor_ha=valor, motivo=motivo, metodo=METODO_DECLARADA, metodo_versao=METODO_DECLARADA_VERSAO,
                    documento_id=doc.id, evidence_version_id=obs.id, predicado=obs.predicate,
                    literal=attrs.get("literal"))
        db.add(m)
        novas.append(m)
    db.flush()
    return novas


# ---------------------------------------------------------------------------
# Confronto (auditor determinístico) e leitura para a tela
# ---------------------------------------------------------------------------

def _calculadas_vigentes(db: Session, tenant_id: int, process_id: int) -> list[Medicao]:
    """Medições calculadas da leitura bem-sucedida mais recente de cada arquivo."""
    ultimas = (db.query(ArquivoGeo.documento_id, func.max(ArquivoGeo.numero).label("n"))
               .filter(ArquivoGeo.tenant_id == tenant_id, ArquivoGeo.estado == "lido")
               .group_by(ArquivoGeo.documento_id).subquery())
    return (db.query(Medicao).join(Feicao, Feicao.id == Medicao.feicao_id)
            .join(ArquivoGeo, ArquivoGeo.id == Feicao.arquivo_geo_id)
            .join(ultimas, (ultimas.c.documento_id == ArquivoGeo.documento_id) & (ultimas.c.n == ArquivoGeo.numero))
            .filter(Medicao.tenant_id == tenant_id, Medicao.process_id == process_id,
                    Medicao.origem_tipo == "feicao_calculada")
            .order_by(Medicao.id).all())


def executar_confronto(db: Session, tenant_id: int, process_id: int, *, user_id: int | None = None) -> str | None:
    """Nova avaliação append-only. Devolve o id da execução, ou None sem geometria medida."""
    medir_declaracoes(db, tenant_id, process_id)
    calculadas = [m for m in _calculadas_vigentes(db, tenant_id, process_id) if m.estado == "determinado"]
    # Observação invalidada, superada ou rejeitada depois de medida sai do confronto.
    vivas = {o.id for o in _observacoes_de_area(db, tenant_id, process_id)}
    referencias = [m for m in db.query(Medicao).filter(Medicao.tenant_id == tenant_id,
        Medicao.process_id == process_id, Medicao.origem_tipo != "feicao_calculada",
        Medicao.estado == "determinado").order_by(Medicao.id) if m.evidence_version_id in vivas]
    if not calculadas:
        return None
    execucao = uuid4().hex
    tol = Decimal(str(settings.AUDITOR_AREA_TOLERANCIA_PCT))
    for c in calculadas:
        for r in referencias:
            res = confrontar_areas(c.valor_ha, r.valor_ha, tolerancia_pct=tol, denominador=DENOMINADOR_REFERENCIA_DOCUMENTAL)
            db.add(ConfrontoArea(tenant_id=tenant_id, process_id=process_id, execucao=execucao,
                medicao_calculada_id=c.id, medicao_referencia_id=r.id, delta_ha=res.delta_ha,
                denominador_regra=res.denominador_regra, denominador_ha=res.denominador_ha,
                percentual=res.percentual, percentual_sobre_maior=res.percentual_sobre_maior,
                tolerancia_pct=float(res.tolerancia_pct), tolerancia_origem=settings.AUDITOR_AREA_TOLERANCIA_ORIGEM,
                resultado=res.resultado, grau=res.grau, metodo_versao=METODO_CONFRONTO_VERSAO,
                executado_por_user_id=user_id))
    db.flush()
    return execucao


def _num(v) -> str | None:
    return None if v is None else format(Decimal(v).normalize(), "f")


def painel(db: Session, tenant_id: int, process_id: int) -> dict:
    case = db.query(Process).filter_by(id=process_id, tenant_id=tenant_id).first()
    docs = [d for d in db.query(Document).filter(Document.tenant_id == tenant_id, Document.process_id == process_id,
                                                 Document.deleted_at.is_(None)).order_by(Document.id) if eh_arquivo_geo(d)]
    nomes = {d.id: d.original_file_name for d in db.query(Document).filter(
        Document.tenant_id == tenant_id, Document.process_id == process_id)}
    arquivos = []
    for d in docs:
        leituras = db.query(ArquivoGeo).filter_by(tenant_id=tenant_id, documento_id=d.id).order_by(ArquivoGeo.numero).all()
        ultima = leituras[-1] if leituras else None
        feicoes = []
        if ultima is not None and ultima.estado == "lido":
            for f in db.query(Feicao).filter_by(tenant_id=tenant_id, arquivo_geo_id=ultima.id).order_by(Feicao.ordem):
                med = db.query(Medicao).filter_by(tenant_id=tenant_id, feicao_id=f.id).order_by(Medicao.id.desc()).first()
                feicoes.append({"id": f.id, "ordem": f.ordem, "identificador": f.identificador_interno, "nome": f.nome,
                    "tipo": f.tipo, "valida": f.valida, "motivo_invalidade": f.motivo_invalidade,
                    "aneis_internos": f.aneis_internos, "medicao_id": med.id if med else None,
                    "area_ha": _num(med.valor_ha) if med else None,
                    "area_estado": med.estado if med else None, "area_motivo": med.motivo if med else None})
        arquivos.append({"documento_id": d.id, "nome": d.original_file_name, "formato": _formato(d),
            "estado": ultima.estado if ultima else "nao_lido", "leituras": len(leituras),
            "leitura": None if ultima is None else {"id": ultima.id, "numero": ultima.numero,
                "sha256": ultima.sha256_original, "membro": ultima.membro_lido, "crs_origem": ultima.crs_origem,
                "metodo_versao": ultima.metodo_versao, "falha_codigo": ultima.falha_codigo,
                "falha_detalhe": ultima.falha_detalhe, "lido_em": ultima.lido_em.isoformat()},
            "feicoes": feicoes})

    medicoes = db.query(Medicao).filter_by(tenant_id=tenant_id, process_id=process_id).order_by(Medicao.id).all()
    projecao = None
    if case and case.property_id:
        p = db.query(ProjecaoGeometria).filter_by(tenant_id=tenant_id, property_id=case.property_id).order_by(
            ProjecaoGeometria.id.desc()).first()
        tem_geom = db.query(Property.geom.isnot(None)).filter_by(id=case.property_id, tenant_id=tenant_id).scalar()
        if p:
            projecao = {"feicao_id": p.feicao_id, "regra": p.regra, "autor_id": p.autor_id, "motivo": p.motivo,
                        "criada_em": p.created_at.isoformat(), "property_geom_gravada": bool(tem_geom)}
    ultima_exec = db.query(ConfrontoArea.execucao, ConfrontoArea.created_at).filter_by(
        tenant_id=tenant_id, process_id=process_id).order_by(ConfrontoArea.id.desc()).first()
    execucoes = db.query(func.count(func.distinct(ConfrontoArea.execucao))).filter_by(
        tenant_id=tenant_id, process_id=process_id).scalar()
    por_id = {m.id: m for m in medicoes}
    confrontos = []
    if ultima_exec:
        for c in db.query(ConfrontoArea).filter_by(tenant_id=tenant_id, process_id=process_id,
                                                   execucao=ultima_exec.execucao).order_by(ConfrontoArea.id):
            ref = por_id.get(c.medicao_referencia_id)
            confrontos.append({"id": c.id, "calculada_id": c.medicao_calculada_id,
                "referencia_id": c.medicao_referencia_id,
                "referencia_fonte": nomes.get(ref.documento_id) if ref else None,
                "referencia_origem": ref.origem_tipo if ref else None,
                "calculada_ha": _num(por_id[c.medicao_calculada_id].valor_ha),
                "referencia_ha": _num(ref.valor_ha) if ref else None,
                "delta_ha": _num(c.delta_ha), "delta_m2": _num(c.delta_ha * 10000) if c.delta_ha is not None else None,
                "denominador_regra": c.denominador_regra, "denominador_ha": _num(c.denominador_ha),
                "percentual": _num(c.percentual), "percentual_sobre_maior": _num(c.percentual_sobre_maior),
                "tolerancia_pct": c.tolerancia_pct, "tolerancia_origem": c.tolerancia_origem,
                "resultado": c.resultado, "grau": c.grau})
    calculadas = [m for m in medicoes if m.origem_tipo == "feicao_calculada" and m.estado == "determinado"]
    return {
        "process_id": process_id,
        "arquivos": arquivos,
        "medicoes": [{"id": m.id, "origem_tipo": m.origem_tipo, "estado": m.estado, "valor_ha": _num(m.valor_ha),
                      "motivo": m.motivo, "metodo": m.metodo, "metodo_versao": m.metodo_versao,
                      "crs_calculo": m.crs_calculo, "motor_versao": m.motor_versao, "documento_id": m.documento_id,
                      "fonte": nomes.get(m.documento_id), "feicao_id": m.feicao_id,
                      "observacao_id": m.evidence_version_id, "predicado": m.predicado, "literal": m.literal}
                     for m in medicoes],
        "projecao": projecao,
        "confronto": {
            "estado": "nao_verificado" if not calculadas else ("avaliado" if ultima_exec else "nao_executado"),
            "execucao": ultima_exec.execucao if ultima_exec else None,
            "executado_em": ultima_exec.created_at.isoformat() if ultima_exec else None,
            "execucoes": execucoes or 0,
            "linhas": confrontos,
        },
        "parametros": {"tolerancia_pct": settings.AUDITOR_AREA_TOLERANCIA_PCT,
                       "tolerancia_origem": settings.AUDITOR_AREA_TOLERANCIA_ORIGEM,
                       "denominador": DENOMINADOR_REFERENCIA_DOCUMENTAL,
                       "metodo_area": METODO_AREA, "crs_calculo": CRS_CALCULO},
        "sobreposicao": {"estado": "nao_verificado", "motivo": "Nenhuma camada de sobreposição carregada."},
    }
