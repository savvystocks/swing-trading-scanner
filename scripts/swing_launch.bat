@echo off
setlocal
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\savva\OneDrive\Documents\Swing Trading"

REM Pull the latest scan JSON + tracker data from GitHub.
REM CI commits new scans every weekday at 14:00 UTC, so a pull on launch
REM guarantees the dashboard is showing the same tickers as the email.
git pull --rebase --autostash 2>nul

REM Always try to start the server. If it's already running, this exits silently
REM because port 8501 is in use. Either way the next step opens the browser.
start "Swing Trading Dashboard" /MIN python -m streamlit run src/terminal/app.py --browser.gatherUsageStats=false --server.headless=true

REM Give the server a moment to come up on a cold start.
timeout /t 4 /nobreak >nul

REM Open the browser to the dashboard. If the server is already running,
REM this just opens a fresh tab to the existing one.
start "" "http://localhost:8501"

exit
