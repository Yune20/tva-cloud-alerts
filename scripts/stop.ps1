# ============================================================
#  STOP — Tắt server
#  Chạy: powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
# ============================================================
$taskName = "TradeBoardAPI"

Write-Host "`n=== Stopping TradeBoardAPI ===" -ForegroundColor Cyan

schtasks /end /tn $taskName 2>$null | Out-Null
Write-Host "  Task stopped" -ForegroundColor Yellow

Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "  Python processes killed" -ForegroundColor Yellow

Write-Host "  Server stopped.`n" -ForegroundColor Green
