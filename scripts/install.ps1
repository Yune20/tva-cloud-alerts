# ============================================================
#  INSTALL - Cai dat dependencies + build frontend
#  Chay: powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# ============================================================
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "=== TradingView-Analyzer Installer ===" -ForegroundColor Cyan

# Python venv
Write-Host ""
Write-Host "[1/4] Python venv..." -ForegroundColor Yellow
if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
    python -m venv "$root\.venv"
    Write-Host "  Created venv" -ForegroundColor Green
} else {
    Write-Host "  venv exists" -ForegroundColor Green
}

# pip install
Write-Host ""
Write-Host "[2/4] pip install..." -ForegroundColor Yellow
& "$root\.venv\Scripts\python.exe" -m pip install -q -r "$root\requirements.txt"
Write-Host "  Done" -ForegroundColor Green

# npm install
Write-Host ""
Write-Host "[3/4] npm install..." -ForegroundColor Yellow
$npm = "C:\Users\optra\AppData\Local\hermes\node\node_modules\corepack\shims\npm.cmd"
& $npm install --prefix "$root\web" 2>$null | Out-Null
Write-Host "  Done" -ForegroundColor Green

# npm build
Write-Host ""
Write-Host "[4/4] npm build..." -ForegroundColor Yellow
Push-Location "$root\web"
& $npm run build 2>&1 | Out-Null
Pop-Location
Write-Host "  Done" -ForegroundColor Green

# Register schtasks
Write-Host ""
Write-Host "[Bonus] Register scheduled task..." -ForegroundColor Yellow
$taskName = "TradeBoardAPI"
$existing = schtasks /query /tn $taskName 2>$null
if ($LASTEXITCODE -ne 0) {
    $python = "$root\.venv\Scripts\python.exe"
    $cmd = "`"$python`" -m uvicorn server:app --host 0.0.0.0 --port 8502"
    schtasks /create /tn $taskName /tr $cmd /sc onstart /ru "$env:USERDOMAIN\$env:USERNAME" /rl highest /f | Out-Null
    Write-Host "  Registered task: $taskName" -ForegroundColor Green
} else {
    Write-Host "  Task already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Install complete ===" -ForegroundColor Cyan
Write-Host "Run:  powershell -ExecutionPolicy Bypass -File scripts\run.ps1"
Write-Host ""
