"""Portão de empacotamento: roda DENTRO da imagem e diz se ela serve.

Existe por causa de 22/09/2026 (dívida #269). Em um único dia, duas falhas de
empacotamento passaram por um CI inteiramente verde, porque o CI nunca
construiu a imagem:

  1. `docs/arquitetura/ONTOLOGIA_REGENTE_v1.md` ficou de fora e o extrator
     morreu em `capacidade_insuficiente` — em produção, sem leitura nenhuma;
  2. o `COPY` que tentou corrigir isso quebrou o build no Render, porque o
     `.dockerignore` excluía `docs` inteiro. Nenhuma imagem nova subiu.

Teste que lê o `Dockerfile` não pega nenhuma das duas: ele audita a receita, não
o bolo. Este script pergunta ao artefato.

Uso (o job do CI faz exatamente isto):
    docker build -t regente:ci .
    docker run --rm -e SECRET_KEY=<32+ chars> regente:ci python scripts/verificar_imagem.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# Rodado como `python scripts/verificar_imagem.py`, sys.path[0] é a pasta do
# script; a raiz precisa entrar para `app.` resolver (mesmo caso do backup).
sys.path.insert(0, str(RAIZ))
FAMILIAS = ("registral", "cadastral", "pessoal", "geoespacial", "contratual", "cartorario")


def _preparar_ambiente() -> None:
    """Segredos de fachada: aqui se verifica empacotamento, não configuração."""
    os.environ.setdefault("SECRET_KEY", "x" * 48)
    os.environ.setdefault("ENVIRONMENT", "test")
    if not os.environ.get("CREDENTIAL_ENCRYPTION_KEY"):
        from cryptography.fernet import Fernet

        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()


def conferir_manifesto() -> list[str]:
    from app.services.agent_capabilities import capability_manifest

    manifesto = capability_manifest("extrator", {})
    falhas = []
    if manifesto["status"] != "available":
        falhas.append(f"manifesto do extrator: {manifesto['status']} — falta {manifesto['missing']}")
    aplicadas = {a["name"] for a in manifesto["applied"]}
    for familia in FAMILIAS:
        if f"extrator/{familia}" not in aplicadas:
            falhas.append(f"skill ausente na imagem: extrator/{familia}")
    ontologia = [i for i in manifesto["implementation"]
                 if i.get("method") == "ontologia_entrada_semantica" and i.get("hash")]
    if not ontologia:
        falhas.append("ontologia sem hash no manifesto — o vocabulário não está na imagem")
    else:
        print(f"ontologia: hash {ontologia[0]['hash'][:16]}…")
    print(f"manifesto: {manifesto['status']} · {len(aplicadas)} skills de família")
    return falhas


def conferir_pre_deploy() -> list[str]:
    """O pré-deploy precisa do script E do pg_dump da major do servidor."""
    falhas = []
    for caminho in ("scripts/predeploy.sh", "scripts/predeploy_backup.py"):
        if not (RAIZ / caminho).is_file():
            falhas.append(f"arquivo ausente na imagem: {caminho}")
    esperada = os.environ.get("PG_CLIENT_MAJOR", "17")
    try:
        versao = subprocess.run(["pg_dump", "--version"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        return [*falhas, f"pg_dump indisponível na imagem: {exc}"]
    print(f"pg_dump: {versao.strip()}")
    if f" {esperada}." not in versao:
        falhas.append(f"pg_dump não é da major {esperada}: {versao.strip()}")
    return falhas


def main() -> int:
    _preparar_ambiente()
    falhas = conferir_manifesto() + conferir_pre_deploy()
    if falhas:
        print("\nIMAGEM REPROVADA:")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print("\nimagem aprovada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
