# ============================================================
#  STATUS - Kiem tra server
#  Chay: powershell -ExecutionPolicy Bypass -File scripts\status.ps1
# ============================================================
$taskName = "TradeBoardAPI"

Write-Host ""
Write-Host "=== TradeBoardAPI Status ===" -ForegroundColor Cyan

# Task status
$taskInfo = schtasks /query /tn $taskName /fo csv 2>$null | Select-Object -Skip 1
if ($taskInfo) {
    Write-Host "  Task: $taskName - EXISTS" -ForegroundColor Green
} else {
    Write-Host "  Task: $taskName - NOT FOUND" -ForegroundColor Red
}

# Process check
$procs = Get-Process python -ErrorAction SilentlyContinue
if ($procs) {
    Write-Host "  Python processes: $($procs.Count)" -ForegroundColor Green
} else {
    Write-Host "  Python processes: 0" -ForegroundColor Yellow
}

# Health check
$ok = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8502/api/health" -TimeoutSec 3 -UseBasicParsing
    $ok = $true
} catch {}

if ($ok) {
    Write-Host "  Health: OK" -ForegroundColor Green
    Write-Host "  URL: http://localhost:8502" -ForegroundColor White
} else {
    Write-Host "  Health: DOWN" -ForegroundColor Red
}
Write-Host ""
