@echo off
title SIH26124 - Stop Services
color 0C
echo.
echo  Stopping all SIH26124 services ...
echo.

REM Kill uvicorn (AI Service)
echo  [1/3] Stopping AI Service (uvicorn) ...
taskkill /F /FI "WINDOWTITLE eq AI-Service*" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

REM Kill node (Gateway)
echo  [2/3] Stopping Gateway (node) ...
taskkill /F /FI "WINDOWTITLE eq Gateway*" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

REM Kill vite (Frontend)
echo  [3/3] Stopping Frontend (vite) ...
taskkill /F /FI "WINDOWTITLE eq Frontend*" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

echo.
echo  All services stopped.

