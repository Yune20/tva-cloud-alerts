# ============================================================
#  RUN - Khoi dong server
#  Chay: powershell -ExecutionPolicy Bypass -File scripts\run.ps1
# ============================================================
$taskName = "TradeBoardAPI"

Write-Host ""
Write-Host "=== Starting TradeBoardAPI ===" -ForegroundColor Cyan

# Kill old processes
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

# Start task
schtasks /run /tn $taskName 2>$null | Out-Null
Write-Host "  Task started: $taskName" -ForegroundColor Green

# Wait for health check
Write-Host "  Waiting for server..." -ForegroundColor Yellow
$ok = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8502/api/health" -TimeoutSec 2 -UseBasicParsing
        if ($r.StatusCode -eq 200) {
            $ok = $true
            break
        }
    } catch {}
}

if ($ok) {
    Write-Host "  Server is UP on http://localhost:8502" -ForegroundColor Green
    Write-Host ""
    Start-Process "http://localhost:8502"
} else {
    Write-Host "  Timeout - check schtasks" -ForegroundColor Red
}
