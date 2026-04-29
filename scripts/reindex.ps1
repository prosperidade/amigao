# Dispara re-indexação completa do corpus legislativo no knowledge_catalog.
#
# Idempotente: documentos já indexados (mesmo content_hash) retornam inserted=0.
# Cada chunk leva ~1s (throttle do gemini-embedding-001 free tier ~100 RPM).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts/reindex.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/reindex.ps1 -NoWait    # só dispara, não acompanha

[CmdletBinding()]
param(
    [switch]$NoWait
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "OK  $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "!!  $msg" -ForegroundColor Yellow }
function Write-Err2($msg) { Write-Host "ERR $msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# 1. Stack precisa estar up (api, worker, db)
# ---------------------------------------------------------------------------
Write-Step "Verificando stack..."
$psOutput = docker compose ps --format json 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err2 "docker compose ps falhou. Rode scripts/dev-up.ps1 primeiro."
    exit 1
}
$required = @('api', 'worker', 'db')
$running = @()
foreach ($line in $psOutput) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    try {
        $svc = $line | ConvertFrom-Json
        if ($svc.State -eq 'running') { $running += $svc.Service }
    } catch { }
}
$missing = $required | Where-Object { $_ -notin $running }
if ($missing.Count -gt 0) {
    Write-Err2 "Servicos parados: $($missing -join ', '). Rode scripts/dev-up.ps1 primeiro."
    exit 1
}
Write-Ok "api, worker, db rodando"

# ---------------------------------------------------------------------------
# 2. Count antes
# ---------------------------------------------------------------------------
Write-Step "Estado atual do knowledge_catalog..."
$beforeRaw = docker compose exec -T db psql -U postgres -d amigao_db -At -c "SELECT count(*) FROM knowledge_catalog;" 2>$null
$before = [int]$beforeRaw.Trim()
Write-Host "    chunks indexados: $before" -ForegroundColor White

$docsTotal = docker compose exec -T db psql -U postgres -d amigao_db -At -c "SELECT count(*) FROM legislation_documents;" 2>$null
Write-Host "    docs no corpus:   $($docsTotal.Trim())" -ForegroundColor White

# ---------------------------------------------------------------------------
# 3. Dispara task Celery
# ---------------------------------------------------------------------------
Write-Step "Disparando reindex_all_legislation..."
$pyCmd = @'
from app.workers.knowledge_indexer import reindex_all_legislation
r = reindex_all_legislation.delay()
print(r.id)
'@
$taskId = (docker compose exec -T api python -c $pyCmd 2>$null).Trim()
if (-not $taskId) {
    Write-Err2 "Nao consegui enfileirar a task."
    exit 1
}
Write-Ok "task enfileirada: $taskId"

if ($NoWait) {
    Write-Host ""
    Write-Host "Tarefa rodando em background. Acompanhe com:" -ForegroundColor DarkGray
    Write-Host "  docker compose logs -f worker" -ForegroundColor Gray
    exit 0
}

# ---------------------------------------------------------------------------
# 4. Acompanha progresso
# ---------------------------------------------------------------------------
Write-Step "Acompanhando progresso (Ctrl+C para parar; a task continua no worker)..."
$lastCount = $before
$stableTicks = 0
while ($true) {
    Start-Sleep -Seconds 15
    $nowRaw = docker compose exec -T db psql -U postgres -d amigao_db -At -c "SELECT count(*) FROM knowledge_catalog;" 2>$null
    $now = [int]$nowRaw.Trim()
    $delta = $now - $before
    $tickDelta = $now - $lastCount
    Write-Host ("    chunks: {0}  (+{1} desde inicio, +{2} no ultimo tick)" -f $now, $delta, $tickDelta) -ForegroundColor White
    if ($tickDelta -eq 0) {
        $stableTicks++
        if ($stableTicks -ge 3) {
            Write-Ok "Sem mudancas por 45s -- task aparentemente concluida."
            break
        }
    } else {
        $stableTicks = 0
    }
    $lastCount = $now
}

# ---------------------------------------------------------------------------
# 5. Distribuicao final por documento
# ---------------------------------------------------------------------------
Write-Step "Distribuicao final:"
docker compose exec -T db psql -U postgres -d amigao_db -c "
SELECT source_ref, count(*) AS chunks
FROM knowledge_catalog
WHERE source_type='legislation'
GROUP BY 1
ORDER BY (regexp_replace(source_ref, '\D', '', 'g'))::int;
"

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host " RE-INDEXACAO CONCLUIDA" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
