@echo off
REM Wrapper batch para scripts/dev-up.ps1 (duplo-clique amigavel).
REM Sobe Docker (db, redis, minio, api, worker, client-portal) + Vite frontend.
REM
REM Flags suportadas:
REM   dev-up.bat              -> sobe tudo (sem rebuild)
REM   dev-up.bat -Build       -> forca rebuild de imagens
REM   dev-up.bat -NoFrontend  -> so backend (sem Vite)

cd /d "%~dp0\.."
powershell -ExecutionPolicy Bypass -NoProfile -File "scripts\dev-up.ps1" %*
if errorlevel 1 (
    echo.
    echo Falhou. Verifique os logs acima.
    pause
    exit /b 1
)
echo.
pause
