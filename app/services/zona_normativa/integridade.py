"""Original guardado e conferência de adulteração (ADR-075 adendo A5).

Cada versão guarda o hash dos BYTES originais e a chave do objeto no storage
(R2 em produção, MinIO em dev — mesma API S3), além do hash do texto extraído.
A conferência periódica baixa o original, recalcula o hash e compara:

- divergente → a versão fica bloqueada para citação e abre tarefa de revisão.
  "Fonte normativa adulterada" é zero tolerância.
- objeto sumiu do storage → também bloqueia: o que não se consegue conferir não
  se apresenta como conferido.
- confere → carimba `original_conferido_em`.

O prefixo é global (`zona-normativa/originais/`), fora do espaço de tenant: o
catálogo normativo não tem tenant (A3 — dado de caso nunca entra aqui).
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
from datetime import UTC, datetime
from urllib.parse import quote

from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.models.zona_normativa import FonteNormativaVersao, TarefaRevisaoNormativa
from app.services.storage import BUCKET_NAME, StorageService

logger = logging.getLogger(__name__)

PREFIXO_ORIGINAIS = "zona-normativa/originais/"
BLOQUEIO_DIVERGENTE = "original_divergente"
BLOQUEIO_AUSENTE = "original_ausente_no_storage"


def chave_do_original(sha256: str, caminho: pathlib.Path) -> str:
    ext = caminho.suffix.lower() if caminho.suffix else ""
    return f"{PREFIXO_ORIGINAIS}{sha256}{ext}"


def guardar_original(storage: StorageService, caminho: pathlib.Path, sha256: str) -> str:
    """Sobe o original com chave endereçada pelo conteúdo. Idempotente."""
    storage._ensure_bucket_exists()
    chave = chave_do_original(sha256, caminho)
    try:
        storage.s3_client.head_object(Bucket=BUCKET_NAME, Key=chave)
        return chave
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code", "") not in ("404", "NoSuchKey", "NotFound"):
            raise
    dados = caminho.read_bytes()
    if hashlib.sha256(dados).hexdigest() != sha256:
        raise RuntimeError(f"{caminho}: hash mudou entre o planejamento e o upload")
    storage.s3_client.put_object(
        Bucket=BUCKET_NAME, Key=chave, Body=dados,
        # Metadado S3 só aceita ASCII: o nome original vai percent-encoded.
        Metadata={"sha256": sha256, "origem": quote(caminho.name[:200])},
    )
    return chave


def conferir_originais(session: Session, storage: StorageService) -> dict:
    """Recalcula o hash de cada original referido e age sobre a divergência."""
    versoes = (
        session.query(FonteNormativaVersao)
        .filter(FonteNormativaVersao.original_storage_key.isnot(None))
        .all()
    )
    por_chave: dict[tuple[str, str], list[FonteNormativaVersao]] = {}
    for v in versoes:
        por_chave.setdefault((v.original_storage_key, v.hash_original), []).append(v)

    agora = datetime.now(UTC)
    out = {"originais": len(por_chave), "conferem": 0, "divergentes": 0, "ausentes": 0,
           "versoes_bloqueadas": 0}
    for (chave, esperado), grupo in por_chave.items():
        dados = storage.download_bytes(chave)
        if not dados:
            motivo, detalhe = BLOQUEIO_AUSENTE, {"chave": chave, "esperado": esperado}
            out["ausentes"] += 1
        else:
            obtido = hashlib.sha256(dados).hexdigest()
            if obtido == esperado:
                for v in grupo:
                    v.original_conferido_em = agora
                out["conferem"] += 1
                continue
            motivo = BLOQUEIO_DIVERGENTE
            detalhe = {"chave": chave, "esperado": esperado, "obtido": obtido}
            out["divergentes"] += 1
        logger.error("zona_normativa.integridade %s: %s", motivo, detalhe)
        for v in grupo:
            if v.bloqueio_citacao != motivo:
                v.bloqueio_citacao = motivo
                out["versoes_bloqueadas"] += 1
                session.add(TarefaRevisaoNormativa(
                    fonte_versao_id=v.id,
                    tipo="original_divergente" if motivo == BLOQUEIO_DIVERGENTE else "original_ausente",
                    detalhe=detalhe,
                ))
    session.flush()
    return out
