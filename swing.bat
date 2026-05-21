@echo off
setlocal
set PYTHONIOENCODING=utf-8
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
if "%~1"=="tui" (
    python -m src.terminal.tui
) else (
    python -m src.terminal.cli %*
)
endlocal
