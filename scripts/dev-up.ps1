# Sobe o ambiente de dev completo do Amigao do Meio Ambiente.
#
# Faz, na ordem:
#   1. Garante Docker Desktop rodando e engine pronta
#   2. Detecta arquivos rastreados que ficaram 0 bytes (sintoma de queda de energia / crash)
#   3. docker compose up -d  (sem --build por padrao -- bind mount cuida do hot-reload)
#   4. Aguarda API /health
#   5. Abre Vite (frontend interno) em uma nova janela
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts/dev-up.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/dev-up.ps1 -Build       # forca rebuild de imagens
#   powershell -ExecutionPolicy Bypass -File scripts/dev-up.ps1 -NoFrontend  # so backend
#
# Quando rebuildar imagens (-Build): apenas se mudou requirements.txt, Dockerfile,
# ou docker-compose.yml. Para mudancas em .py o bind mount + uvicorn --reload bastam.

[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$NoFrontend
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "OK  $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "!!  $msg" -ForegroundColor Yellow }
function Write-Err2($msg) { Write-Host "ERR $msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# 1. Docker Desktop / engine
# ---------------------------------------------------------------------------
Write-Step "Verificando Docker engine..."
$dockerOk = $false
try {
    docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch { }

if (-not $dockerOk) {
    Write-Warn2 "Engine offline. Iniciando Docker Desktop..."
    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerExe)) {
        Write-Err2 "Docker Desktop nao encontrado em $dockerExe"
        exit 1
    }
    Start-Process $dockerExe | Out-Null

    $deadline = (Get-Date).AddMinutes(3)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break }
        Write-Host "    aguardando engine..." -ForegroundColor DarkGray
    }
    if (-not $dockerOk) {
        Write-Err2 "Engine nao subiu em 3min. Verifique o Docker Desktop manualmente."
        exit 1
    }
}
Write-Ok "Docker engine pronta"

# ---------------------------------------------------------------------------
# 2. Detectar arquivos rastreados que ficaram 0 bytes
# ---------------------------------------------------------------------------
# Sintoma classico de queda de energia / crash do Windows: o arquivo estava
# aberto em editor com write em buffer, a luz cai e o disco fica com 0 bytes.
# Detectar cedo evita as horas de "por que a pagina esta branca?".
Write-Step "Procurando arquivos rastreados zerados (sinal de crash)..."
$tracked = git -c core.quotepath=false ls-files 2>$null
$emptyFiles = @()
foreach ($f in $tracked) {
    if (Test-Path -LiteralPath $f -PathType Leaf) {
        $len = (Get-Item -LiteralPath $f).Length
        if ($len -eq 0) {
            # Confirma que no HEAD nao era vazio
            $headSize = (git cat-file -s "HEAD:$f" 2>$null)
            if ($headSize -and [int]$headSize -gt 0) {
                $emptyFiles += $f
            }
        }
    }
}
if ($emptyFiles.Count -gt 0) {
    Write-Warn2 "Arquivos zerados detectados (provavel corrupcao por crash):"
    foreach ($f in $emptyFiles) { Write-Host "    - $f" -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "Para restaurar do ultimo commit:" -ForegroundColor Yellow
    foreach ($f in $emptyFiles) { Write-Host "    git checkout HEAD -- $f" -ForegroundColor Gray }
    Write-Host ""
    $resp = Read-Host "Restaurar todos automaticamente do HEAD? [s/N]"
    if ($resp -match '^(s|sim|y|yes)$') {
        foreach ($f in $emptyFiles) {
            git checkout HEAD -- $f
            Write-Ok "restaurado: $f"
        }
    } else {
        Write-Warn2 "Pulei a restauracao. Continue por sua conta."
    }
} else {
    Write-Ok "Nenhum arquivo zerado"
}

# ---------------------------------------------------------------------------
# 3. docker compose up
# ---------------------------------------------------------------------------
Write-Step "Subindo stack (db, redis, minio, api, worker, client-portal)..."
$composeArgs = @("compose", "up", "-d")
if ($Build) {
    $composeArgs += "--build"
    Write-Warn2 "--build ativo (so use se mudou requirements.txt, Dockerfile ou compose.yml)"
}
$start = Get-Date
& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    Write-Err2 "docker compose falhou"
    exit 1
}
$elapsed = [int]((Get-Date) - $start).TotalSeconds
Write-Ok "containers no ar em ${elapsed}s"

# ---------------------------------------------------------------------------
# 4. Aguardar API /health
# ---------------------------------------------------------------------------
Write-Step "Aguardando API em http://localhost:8000/health ..."
$apiOk = $false
$deadline = (Get-Date).AddMinutes(2)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $apiOk = $true; break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if ($apiOk) {
    Write-Ok "API respondendo"
} else {
    Write-Warn2 "API nao respondeu em 2min. Verifique 'docker compose logs api'"
}

# ---------------------------------------------------------------------------
# 5. Vite frontend interno (em janela nova)
# ---------------------------------------------------------------------------
if (-not $NoFrontend) {
    Write-Step "Abrindo Vite em janela separada..."
    $viteCmd = "Set-Location '$projectRoot\frontend'; Write-Host 'Vite dev server' -ForegroundColor Cyan; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $viteCmd | Out-Null
    Write-Ok "Vite iniciando (a janela ficara aberta com os logs)"
}

# ---------------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host " AMBIENTE DE DEV PRONTO" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  API ............ http://localhost:8000  (/health, /metrics, /docs)" -ForegroundColor White
Write-Host "  Frontend interno http://localhost:5173" -ForegroundColor White
Write-Host "  Portal cliente . http://localhost:3000" -ForegroundColor White
Write-Host "  MinIO console .. http://localhost:9001" -ForegroundColor White
Write-Host ""
Write-Host "  Logs:    docker compose logs -f api worker" -ForegroundColor DarkGray
Write-Host "  Parar:   docker compose down" -ForegroundColor DarkGray
Write-Host ""
