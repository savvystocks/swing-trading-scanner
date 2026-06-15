$ErrorActionPreference = "Continue"
$root = "C:\Users\savva\OneDrive\Documents\Swing Trading"
Set-Location $root
$env:ALPACA_API_KEY = [Environment]::GetEnvironmentVariable('ALPACA_API_KEY','User')
$env:ALPACA_SECRET_KEY = [Environment]::GetEnvironmentVariable('ALPACA_SECRET_KEY','User')
$env:UNUSUAL_WHALES_TOKEN = [Environment]::GetEnvironmentVariable('UNUSUAL_WHALES_TOKEN','User')
$env:PYTHONIOENCODING = "utf-8"
$logdir = Join-Path $root "data\ambush_logs"
if (-not (Test-Path $logdir)) { New-Item -ItemType Directory $logdir | Out-Null }
$log = Join-Path $logdir ("ambush_{0:yyyy-MM-dd}.log" -f (Get-Date))
$header = "==== fired {0:yyyy-MM-dd HH:mm:ss} local ====`r`n" -f (Get-Date)
$out = (python "scripts\run_ambush.py" 2>&1 | Out-String)
[System.IO.File]::AppendAllText($log, $header + $out, (New-Object System.Text.UTF8Encoding($false)))
