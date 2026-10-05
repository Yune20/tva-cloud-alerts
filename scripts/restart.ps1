# ============================================================
#  RESTART — Restart server
#  Chạy: powershell -ExecutionPolicy Bypass -File scripts\restart.ps1
# ============================================================
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

& "$root\scripts\stop.ps1"
Start-Sleep -Seconds 2
& "$root\scripts\run.ps1"
