@echo off
title SIH26124 - Urban Intelligence Platform
color 0A

echo.
echo  ============================================================
echo   SIH26124 Urban Intelligence Platform - STARTUP
echo  ============================================================
echo.
echo  Starting services:
echo    [1] AI Service    (Python FastAPI  - port 8000)
echo    [2] Gateway       (Node.js WS/HTTP - port 5000)
echo    [3] Frontend      (Vite React      - port 3000)
echo    [4] Cloudflare Tunnel (HTTPS for phone camera)
echo.

REM --- Check we are in the project root ---
IF NOT EXIST "backend\ai_service\main.py" (
    echo  ERROR: Run this script from the project root folder.
    echo  Expected: SIH26124-Urban-Intelligence\
    pause
    exit /b 1
)

REM --- Get Local IP for PWA QR ---
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do (
    set LOCAL_IP=%%a
    goto :got_ip
)
:got_ip
set LOCAL_IP=%LOCAL_IP: =%

REM --- 1. AI Service (FastAPI on port 8000) ---
echo  [1/4] Launching AI Service ...
start "AI-Service (port 8000)" cmd /k "echo ===== AI SERVICE (FastAPI:8000) ===== && python -m uvicorn backend.ai_service.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 2 /nobreak >nul

REM --- 2. Gateway (Node.js on port 5000) ---
echo  [2/4] Launching Gateway ...
start "Gateway (port 5000)" cmd /k "echo ===== GATEWAY (Node.js:5000) ===== && cd backend\gateway && node server.js"

timeout /t 2 /nobreak >nul

REM --- 3. Frontend (Vite on port 3000) ---
echo  [3/4] Launching Frontend ...
start "Frontend (port 3000)" cmd /k "echo ===== FRONTEND (Vite:3000) ===== && cd frontend && npm run dev"

timeout /t 2 /nobreak >nul

REM --- 4. Cloudflare Tunnel (HTTPS for phone camera PWA) ---
IF EXIST "cloudflared.exe" (
    echo  [4/4] Launching Cloudflare HTTPS Tunnel ...
    start "Cloudflare-Tunnel (HTTPS)" cmd /k "echo ===== CLOUDFLARE TUNNEL (HTTPS) ===== && echo Tunnel URL will appear below - use it on your phone for live camera && echo. && cloudflared.exe tunnel --url http://localhost:5000"
) ELSE (
    echo  [4/4] cloudflared.exe not found - skipping HTTPS tunnel
    echo  NOTE: Phone camera requires HTTPS. Download cloudflared from:
    echo        https://github.com/cloudflare/cloudflared/releases
)

echo.
echo  ============================================================
echo   All services started in separate windows!
echo.
echo   Dashboard URLs:
echo     Frontend         ->  http://localhost:3000
echo     AI API Docs      ->  http://localhost:8000/docs
echo     Gateway WS       ->  ws://localhost:5000
echo.
echo   📱 Phone Camera PWA (Local Wi-Fi):
echo     http://%LOCAL_IP%:5000/pwa/?device_id=BUS_LIVE_01
echo.
echo   📱 Phone Camera PWA (HTTPS via Cloudflare - preferred):
echo     Check the Cloudflare Tunnel window for the HTTPS URL
echo     then open:  https://<tunnel-url>/pwa/?device_id=BUS_LIVE_01
echo.
echo   IMPORTANT: Phone camera REQUIRES HTTPS on Android/iOS!
echo   Use the Cloudflare Tunnel URL for live camera streaming.
echo  ============================================================
echo.
echo  Press any key to open the frontend in your browser ...
pause >nul
start http://localhost:3000
