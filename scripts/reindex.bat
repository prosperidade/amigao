@echo off
REM Wrapper batch para scripts/reindex.ps1 (duplo-clique amigavel).
REM Sobe a re-indexacao completa do knowledge_catalog.

cd /d "%~dp0\.."
powershell -ExecutionPolicy Bypass -NoProfile -File "scripts\reindex.ps1" %*
if errorlevel 1 (
    echo.
    echo Falhou. Verifique os logs acima.
    pause
    exit /b 1
)
echo.
pause
