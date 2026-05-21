@echo off
setlocal
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\savva\OneDrive\Documents\Swing Trading"

REM Always try to start the server. If it's already running, this will exit silently
REM because the port is in use. Either way the next step opens the browser.
start "Swing Trading Dashboard" /MIN python -m streamlit run src/terminal/app.py --browser.gatherUsageStats=false --server.headless=true

REM Give the server a moment to come up on a cold start.
timeout /t 4 /nobreak >nul

REM Open the browser to the dashboard. If the server is already running,
REM this just opens a fresh tab to the existing one.
start "" "http://localhost:8501"

exit
