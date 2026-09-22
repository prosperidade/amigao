"""Backup de pré-deploy: pg_dump do schema `public` para o R2, antes do alembic.

Roda como primeira metade do `preDeployCommand` da API no Render
(`python scripts/predeploy_backup.py && alembic upgrade head`). Se o dump, a
verificação ou o upload falharem, o processo sai com código ≠ 0 e o deploy
para ANTES da migration — migration sem cópia do estado anterior não se
desfaz com git.

O que faz, em ordem:
  1. lê a revisão alembic atual (a que o dump representa);
  2. `pg_dump --format=custom --schema=public` para arquivo temporário;
  3. `pg_restore --list` no arquivo — dump que não se lista não é backup;
  4. envia ao bucket de backups (privado), com sha256, revisão e commit nos
     metadados do objeto; confere o tamanho do objeto remoto;
  5. aplica a retenção declarada (ver RETENCAO abaixo).

Escopo: só o schema `public`. Os schemas do Supabase (auth, storage, realtime,
vault…) não são dados do Regente, e as extensões (PostGIS, pgvector, no schema
`extensions`) se recriam com CREATE EXTENSION antes do restore. Procedimento
de restore em docs/operacao/RUNBOOK_OPS.md, seção "Backups e recuperação".

Retenção (RETENCAO): mantém todo dump com menos de BACKUP_RETENTION_DAYS dias
(default 30) e, independentemente da idade, os BACKUP_MIN_KEEP mais recentes
(default 10). Apaga o resto — só objetos sob o prefixo de pré-deploy. Falha na
retenção não derruba o deploy (o backup já está salvo), mas sai em log ERROR.

Uso manual (dump conferido fora do deploy):
    python scripts/predeploy_backup.py            # executa dump + upload
    python scripts/predeploy_backup.py --no-retention
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Rodado como `python scripts/predeploy_backup.py`, sys.path[0] é a pasta do
# script; a raiz do repo precisa entrar para `app.core.config` resolver.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PREFIXO = "predeploy/"
BUCKET_PADRAO = "regente-backups"
DIAS_PADRAO = 30
MINIMO_PADRAO = 10


class BackupFalhou(RuntimeError):
    """Qualquer falha que deve impedir a migration."""


def _log(evento: str, **campos) -> None:
    # JSON numa linha: o log do preDeploy do Render é a trilha desta operação.
    print(json.dumps({"evento": evento, **campos}, ensure_ascii=False, default=str), flush=True)


def url_libpq(url: str) -> str:
    """`postgresql+psycopg2://` (SQLAlchemy) → `postgresql://` (libpq/pg_dump)."""
    return re.sub(r"^postgres(?:ql)?(?:\+\w+)?://", "postgresql://", url.strip())


def nome_do_objeto(momento: datetime, commit: str | None, revisao: str | None) -> str:
    carimbo = momento.strftime("%Y%m%dT%H%M%SZ")
    return f"{PREFIXO}{carimbo}_{(commit or 'semcommit')[:12]}_{revisao or 'semalembic'}.dump"


@dataclass(frozen=True)
class ObjetoBackup:
    chave: str
    modificado_em: datetime


def selecionar_para_apagar(
    objetos: list[ObjetoBackup], agora: datetime, dias: int, minimo: int
) -> list[str]:
    """Retenção: fica o que é recente OU está entre os `minimo` mais novos."""
    if dias < 1 or minimo < 1:
        raise ValueError("retenção exige dias >= 1 e mínimo >= 1")
    corte = agora - timedelta(days=dias)
    ordenados = sorted(objetos, key=lambda o: o.modificado_em, reverse=True)
    return [
        o.chave
        for posicao, o in enumerate(ordenados)
        if posicao >= minimo and o.modificado_em < corte and o.chave.startswith(PREFIXO)
    ]


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _rodar(cmd: list[str], etapa: str) -> str:
    # Nunca logar `cmd`: contém a URL com senha.
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise BackupFalhou(f"{etapa} saiu com {r.returncode}: {r.stderr.strip()[-2000:]}")
    return r.stdout


def revisao_alembic(url: str) -> str | None:
    import psycopg2

    with psycopg2.connect(url, connect_timeout=15) as conn, conn.cursor() as cur:
        cur.execute("select to_regclass('public.alembic_version')")
        if cur.fetchone()[0] is None:
            return None
        cur.execute("select version_num from alembic_version")
        linha = cur.fetchone()
        return linha[0] if linha else None


def gerar_dump(url: str, destino: Path) -> None:
    _rodar(
        [
            "pg_dump",
            "--format=custom",
            "--schema=public",
            "--no-owner",
            "--no-privileges",
            "--lock-wait-timeout=60000",
            f"--file={destino}",
            f"--dbname={url}",
        ],
        "pg_dump",
    )


def conferir_dump(caminho: Path) -> int:
    """Lista o índice do dump; devolve quantas tabelas têm dados nele."""
    indice = _rodar(["pg_restore", "--list", str(caminho)], "pg_restore --list")
    tabelas = sum(1 for linha in indice.splitlines() if " TABLE DATA public " in linha)
    if " TABLE DATA public alembic_version " not in indice:
        # Banco sem alembic_version só é aceitável no primeiríssimo deploy.
        _log("aviso_dump_sem_alembic_version", tabelas_com_dados=tabelas)
    if tabelas == 0:
        raise BackupFalhou("dump sem nenhuma TABLE DATA do schema public")
    return tabelas


def cliente_s3():
    import boto3
    from botocore.config import Config as BotoConfig

    from app.core.config import settings

    return boto3.client(
        "s3",
        endpoint_url=settings.minio_internal_endpoint,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name=settings.S3_REGION,  # R2 exige "auto"
        config=BotoConfig(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=120,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def garantir_bucket(s3, bucket: str) -> None:
    from botocore.exceptions import ClientError

    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as exc:
        codigo = str(exc.response.get("Error", {}).get("Code", ""))
        if codigo not in {"404", "NoSuchBucket", "NotFound"}:
            raise BackupFalhou(f"bucket '{bucket}' inacessível [{codigo}]") from exc
        s3.create_bucket(Bucket=bucket)
        _log("bucket_criado", bucket=bucket)


def enviar(s3, bucket: str, caminho: Path, chave: str, metadados: dict[str, str]) -> None:
    s3.upload_file(str(caminho), bucket, chave, ExtraArgs={"Metadata": metadados})
    remoto = s3.head_object(Bucket=bucket, Key=chave)
    if int(remoto["ContentLength"]) != caminho.stat().st_size:
        raise BackupFalhou(
            f"objeto remoto com {remoto['ContentLength']} bytes; local {caminho.stat().st_size}"
        )


def aplicar_retencao(s3, bucket: str, agora: datetime, dias: int, minimo: int) -> list[str]:
    objetos: list[ObjetoBackup] = []
    for pagina in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=PREFIXO):
        for o in pagina.get("Contents", []):
            objetos.append(ObjetoBackup(o["Key"], o["LastModified"]))
    apagar = selecionar_para_apagar(objetos, agora, dias, minimo)
    for chave in apagar:
        s3.delete_object(Bucket=bucket, Key=chave)
    _log("retencao", total=len(objetos), apagados=apagar, dias=dias, minimo=minimo)
    return apagar


def executar(aplicar_retencao_apos: bool = True) -> dict:
    from app.core.config import settings

    url = url_libpq(os.getenv("MIGRATE_DATABASE_URL") or settings.SQLALCHEMY_DATABASE_URI)
    bucket = os.getenv("BACKUP_BUCKET", BUCKET_PADRAO).strip() or BUCKET_PADRAO
    dias = int(os.getenv("BACKUP_RETENTION_DAYS", DIAS_PADRAO))
    minimo = int(os.getenv("BACKUP_MIN_KEEP", MINIMO_PADRAO))
    commit = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT")
    agora = datetime.now(UTC)

    revisao = revisao_alembic(url)
    chave = nome_do_objeto(agora, commit, revisao)
    _log("inicio", bucket=bucket, chave=chave, alembic_antes=revisao, commit=commit)

    with tempfile.TemporaryDirectory(prefix="predeploy_backup_") as tmp:
        arquivo = Path(tmp) / "regente.dump"
        gerar_dump(url, arquivo)
        tabelas = conferir_dump(arquivo)
        tamanho = arquivo.stat().st_size
        sha = _sha256(arquivo)

        s3 = cliente_s3()
        garantir_bucket(s3, bucket)
        enviar(
            s3,
            bucket,
            arquivo,
            chave,
            {
                "sha256": sha,
                "alembic-version": revisao or "",
                "git-commit": commit or "",
                "schema": "public",
                "tabelas-com-dados": str(tabelas),
            },
        )

    resultado = {
        "bucket": bucket,
        "chave": chave,
        "bytes": tamanho,
        "sha256": sha,
        "alembic_antes": revisao,
        "commit": commit,
        "tabelas_com_dados": tabelas,
    }
    _log("backup_ok", **resultado)

    if aplicar_retencao_apos:
        try:
            aplicar_retencao(s3, bucket, agora, dias, minimo)
        except Exception as exc:  # o backup já está salvo; retenção não bloqueia o deploy
            _log("ERRO_retencao", erro=repr(exc))
    return resultado


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-retention", action="store_true", help="não apagar dumps antigos")
    args = ap.parse_args(argv)
    try:
        executar(aplicar_retencao_apos=not args.no_retention)
    except Exception as exc:
        _log("ERRO_backup_predeploy", erro=repr(exc), consequencia="migration NÃO roda; deploy abortado")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
