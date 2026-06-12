# NetDash — uruchom / zrestartuj serwer
$ErrorActionPreference = "Stop"
$Port = if ($env:NETDASH_LISTEN_PORT) { [int]$env:NETDASH_LISTEN_PORT } else { 18787 }
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe"

Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 1
Set-Location $Root
Start-Process -FilePath $Python -ArgumentList "run.py" -WorkingDirectory $Root -WindowStyle Normal
Start-Sleep -Seconds 4

try {
  $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 15
  Write-Host "NetDash OK v$($health.version) -> http://127.0.0.1:$Port" -ForegroundColor Green
} catch {
  Write-Host "NetDash nie odpowiada na porcie $Port" -ForegroundColor Red
  exit 1
}
