"""Uma escrita de leitura, uma projeção legada; nunca inventar hash ou página."""
import hashlib
import re
from datetime import UTC, datetime

from fastapi import HTTPException

from app.models.document import Document
from app.models.entrada_semantica import DocumentoVersao, Fragmento


def registrar_leitura(db, doc, texto, *, metodo, modelo=None, parametros=None,
                     origem="leitura", documento_origem_id=None, sha256_original=None):
    digest = sha256_original or doc.checksum_sha256
    if not digest or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Versão documental exige hash dos bytes originais; recupere o arquivo")
    # The document identity serializes numbering, including the first version.
    db.query(Document).filter_by(id=doc.id, tenant_id=doc.tenant_id).with_for_update().one()
    latest = db.query(DocumentoVersao).filter_by(documento_id=doc.id,
        tenant_id=doc.tenant_id).order_by(DocumentoVersao.numero.desc()).first()
    text_hash = hashlib.sha256(texto.encode()).hexdigest()
    if latest and (latest.sha256_texto, latest.sha256_original, latest.metodo, latest.modelo,
                   latest.parametros, latest.origem, latest.documento_origem_id) == (
                   text_hash, digest, metodo, modelo, parametros or {}, origem, documento_origem_id):
        return latest
    row = DocumentoVersao(tenant_id=doc.tenant_id, documento_id=doc.id,
        numero=latest.numero + 1 if latest else 1, sha256_original=digest, texto=texto,
        sha256_texto=text_hash, metodo=metodo, modelo=modelo, parametros=parametros or {},
        origem=origem, documento_origem_id=documento_origem_id)
    db.add(row)
    db.flush()
    doc.extracted_text, doc.version_number = row.texto, row.numero
    doc.extracted_at = datetime.now(UTC)
    db.flush()
    return row


def registrar_fragmento(db, versao, inicio, fim, *, pagina=None):
    if not 0 <= inicio < fim <= len(versao.texto):
        raise HTTPException(422, "Fragmento fora do texto versionado")
    existing = db.query(Fragmento).filter_by(tenant_id=versao.tenant_id,
        documento_versao_id=versao.id, inicio=inicio, fim=fim).first()
    if existing:
        return existing
    row = Fragmento(tenant_id=versao.tenant_id, documento_versao_id=versao.id,
        inicio=inicio, fim=fim, pagina=pagina, trecho=versao.texto[inicio:fim], sha256_texto=versao.sha256_texto)
    db.add(row)
    db.flush()
    return row
