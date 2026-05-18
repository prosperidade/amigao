# scripts/setup-dev.ps1 — provisiona venv local pra rodar pytest no host (Windows).
#
# Uso (PowerShell, na raiz do repo):
#   .\scripts\setup-dev.ps1
#
# Depois:
#   .\.venv\Scripts\Activate.ps1
#   pytest tests/ -q --no-cov
#
# Testcontainers usa o Docker do host (não Docker-in-Docker) — Docker Desktop
# precisa estar rodando. A imagem `amigao_do_meio_ambiente-db:latest` é puxada
# pelo conftest.py; se não existir local, faz fallback para `pgvector/pgvector:pg15`.
# Recomendado: rodar `docker compose build db` uma vez antes do primeiro pytest
# para garantir a imagem completa (postgis + pgvector).

$ErrorActionPreference = "Stop"

Write-Host "[setup-dev] Verificando Python..." -ForegroundColor Cyan
$pyVersion = (python --version) 2>&1
Write-Host "  $pyVersion"

if (-not ($pyVersion -match "Python 3\.(1[1-9]|[2-9]\d)")) {
    Write-Host "[setup-dev] ERRO: Python >=3.11 requerido (achei: $pyVersion)" -ForegroundColor Red
    exit 1
}

if (Test-Path ".venv") {
    Write-Host "[setup-dev] .venv já existe. Apagando para recriar limpo." -ForegroundColor Yellow
    Remove-Item -Recurse -Force .venv
}

Write-Host "[setup-dev] Criando .venv..." -ForegroundColor Cyan
python -m venv .venv

Write-Host "[setup-dev] Atualizando pip..." -ForegroundColor Cyan
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet

Write-Host "[setup-dev] Instalando runtime + dev deps..." -ForegroundColor Cyan
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

Write-Host ""
Write-Host "[setup-dev] OK." -ForegroundColor Green
Write-Host "Próximos passos:"
Write-Host "  1. .\.venv\Scripts\Activate.ps1     # ativa o venv"
Write-Host "  2. docker compose build db          # garante imagem com pgvector (uma vez)"
Write-Host "  3. pytest tests/ -q --no-cov        # roda a suite"
