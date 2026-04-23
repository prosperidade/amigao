# Cleanup final do storage local do MemPalace (PyPI) após Sprint Z (2026-04-23).
#
# Rodar após reiniciar IDEs/terminais para liberar locks em ~/.mempalace/knowledge_graph.sqlite3.
# Este script é idempotente: pode ser executado quantas vezes quiser, e só apaga o que consegue.
#
# NÃO toca em ~/.claude-mem/ (plugin Claude Code — é outra coisa, não afetado pela revogação).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts/cleanup_mempalace_storage.ps1

$target = "$env:USERPROFILE\.mempalace"

if (-not (Test-Path $target)) {
    Write-Host "OK: $target já não existe. Nada a fazer." -ForegroundColor Green
    exit 0
}

Write-Host "Tentando remover $target ..."

try {
    Remove-Item -Recurse -Force $target -ErrorAction Stop
    Write-Host "OK: diretorio removido." -ForegroundColor Green
    exit 0
} catch {
    Write-Host "FALHA parcial: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "Arquivos remanescentes:"
    Get-ChildItem $target -Force -Recurse | Select-Object FullName, Length | Format-Table -AutoSize
    Write-Host ""
    Write-Host "Feche todos os processos que podem ter lock em .sqlite3 (editores, IDEs, terminais rodando python com Chroma) e rode este script novamente." -ForegroundColor Yellow
    exit 1
}
