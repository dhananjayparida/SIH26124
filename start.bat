@echo off
title SIH26124 - Urban Intelligence Platform
color 0A

echo.
echo  ============================================================
echo   SIH26124 Urban Intelligence Platform - STARTUP
echo  ============================================================
echo.
echo  Starting 3 services:
echo    [1] AI Service    (Python FastAPI  - port 8000)
echo    [2] Gateway       (Node.js WS/HTTP - port 5000)
echo    [3] Frontend      (Vite React      - port 3000)
echo.

REM --- Check we are in the project root ---
IF NOT EXIST "backend\ai_service\main.py" (
    echo  ERROR: Run this script from the project root folder.
    echo  Expected: SIH26124-Urban-Intelligence\
    pause
    exit /b 1
)

REM --- 1. AI Service (FastAPI on port 8000) ---
echo  [1/3] Launching AI Service ...
start "AI-Service (port 8000)" cmd /k "echo ===== AI SERVICE (FastAPI:8000) ===== && python -m uvicorn backend.ai_service.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 2 /nobreak >nul

REM --- 2. Gateway (Node.js on port 5000) ---
echo  [2/3] Launching Gateway ...
start "Gateway (port 5000)" cmd /k "echo ===== GATEWAY (Node.js:5000) ===== && cd backend\gateway && node server.js"

timeout /t 2 /nobreak >nul

REM --- 3. Frontend (Vite on port 3000) ---
echo  [3/3] Launching Frontend ...
start "Frontend (port 3000)" cmd /k "echo ===== FRONTEND (Vite:3000) ===== && cd frontend && npm run dev"

echo.
echo  ============================================================
echo   All services started in separate windows!
echo.
echo   URLs:
echo     Frontend      ->  http://localhost:3000
echo     AI Service    ->  http://localhost:8000
echo     API Docs      ->  http://localhost:8000/docs
echo     Gateway WS    ->  ws://localhost:5000
echo  ============================================================
echo.
echo  Press any key to open the frontend in your browser ...
pause >nul
start http://localhost:3000
