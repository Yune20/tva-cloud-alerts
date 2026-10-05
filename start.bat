@echo off
title TradingView-Analyzer
cd /d D:\NOTEBOOK\TradingView-Analyzer

echo.
echo === Stopping old server ===
schtasks /end /tn TradeBoardAPI >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo === Starting server ===
schtasks /run /tn TradeBoardAPI >nul 2>&1

echo === Waiting for server... ===
set /a count=0
:wait
timeout /t 1 /nobreak >nul
set /a count+=1
curl -s http://localhost:8502/api/health >nul 2>&1
if %errorlevel%==0 goto ready
if %count% geq 30 goto fail
goto wait

:ready
echo Server is UP at http://localhost:8502
start http://localhost:8502
goto end

:fail
echo Server failed to start after 30s
echo Check: schtasks /query /tn TradeBoardAPI

:end
echo.
pause
