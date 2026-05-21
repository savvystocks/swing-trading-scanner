$env:PYTHONIOENCODING = 'utf-8'
Set-Location 'C:\Users\savva\OneDrive\Documents\Swing Trading'

Write-Host 'Starting Swing Trading dashboard...' -ForegroundColor Cyan
Write-Host 'Your browser will open at http://localhost:8501 in a few seconds.' -ForegroundColor Gray
Write-Host 'Keep this window open while the app runs. Close it to stop the app.' -ForegroundColor Gray
Write-Host ''

python -m streamlit run src/terminal/app.py --server.headless=false --browser.gatherUsageStats=false
