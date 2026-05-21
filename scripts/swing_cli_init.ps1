$env:PYTHONIOENCODING = 'utf-8'
Set-Location 'C:\Users\savva\OneDrive\Documents\Swing Trading'

Write-Host ''
Write-Host 'Swing Trading CLI - ready' -ForegroundColor Cyan
Write-Host 'Common commands:' -ForegroundColor Cyan
Write-Host '  .\swing.bat picks                       - todays ranked picks' -ForegroundColor Gray
Write-Host '  .\swing.bat picks --tier A+             - filter by tier' -ForegroundColor Gray
Write-Host '  .\swing.bat picks --catalyst earnings   - filter by catalyst' -ForegroundColor Gray
Write-Host '  .\swing.bat picks --min-score 60        - minimum overall score' -ForegroundColor Gray
Write-Host '  .\swing.bat ticker NVAX                 - drill into one ticker' -ForegroundColor Gray
Write-Host '  .\swing.bat positions                   - open paper trades' -ForegroundColor Gray
Write-Host '  .\swing.bat positions --live            - open live trades' -ForegroundColor Gray
Write-Host '  .\swing.bat closed --limit 10           - recent closed trades' -ForegroundColor Gray
Write-Host '  .\swing.bat exits                       - exit alerts' -ForegroundColor Gray
Write-Host '  .\swing.bat history                     - past scans summary' -ForegroundColor Gray
Write-Host '  .\swing.bat macro                       - VIX/FOMC/regime' -ForegroundColor Gray
Write-Host '  .\swing.bat stats                       - win rate + P&L' -ForegroundColor Gray
Write-Host '  .\swing.bat ask "your question here"    - ask Claude' -ForegroundColor Gray
Write-Host '  .\swing.bat tui                         - launch full TUI' -ForegroundColor Gray
Write-Host ''
Write-Host 'Type a command and press Enter.' -ForegroundColor DarkGray
Write-Host ''
