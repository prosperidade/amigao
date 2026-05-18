#!/usr/bin/env bash
# scripts/setup-dev.sh — provisiona venv local pra rodar pytest no host (bash/CI).
#
# Uso (na raiz do repo):
#   ./scripts/setup-dev.sh
#
# Depois:
#   source .venv/bin/activate   # ou .venv/Scripts/activate no Git Bash Windows
#   pytest tests/ -q --no-cov
#
# Testcontainers usa o Docker do host. Imagem custom `amigao_do_meio_ambiente-db`
# preferida (postgis + pgvector); fallback `pgvector/pgvector:pg15` se não existir.
# Recomendado: `docker compose build db` uma vez antes do primeiro pytest.

set -euo pipefail

echo "[setup-dev] Verificando Python..."
PY_VERSION=$(python --version 2>&1)
echo "  $PY_VERSION"

if ! echo "$PY_VERSION" | grep -qE "Python 3\.(1[1-9]|[2-9][0-9])"; then
    echo "[setup-dev] ERRO: Python >=3.11 requerido (achei: $PY_VERSION)" >&2
    exit 1
fi

if [ -d ".venv" ]; then
    echo "[setup-dev] .venv já existe. Apagando para recriar limpo."
    rm -rf .venv
fi

echo "[setup-dev] Criando .venv..."
python -m venv .venv

if [ -f ".venv/Scripts/python.exe" ]; then
    PY=".venv/Scripts/python.exe"   # Windows Git Bash
else
    PY=".venv/bin/python"
fi

echo "[setup-dev] Atualizando pip..."
"$PY" -m pip install --upgrade pip --quiet

echo "[setup-dev] Instalando runtime + dev deps..."
"$PY" -m pip install -r requirements-dev.txt

echo ""
echo "[setup-dev] OK."
echo "Próximos passos:"
echo "  1. source .venv/bin/activate    # (Linux/Mac) ou .venv/Scripts/activate (Git Bash)"
echo "  2. docker compose build db      # garante imagem com pgvector (uma vez)"
echo "  3. pytest tests/ -q --no-cov    # roda a suite"
