@echo off
chcp 65001 >nul
title Logistics Agent

echo.
echo  ================================
echo   Logistics Agent START
echo  ================================
echo.

echo  [1/2] Backend server (port 8004)...
start "Logistics-Backend" cmd /k "cd /d "%~dp0backend" && uvicorn main:app --reload --port 8004"

timeout /t 2 /nobreak >nul

echo  [2/2] Frontend server (port 3001)...
start "Logistics-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo  [3/3] Waiting for servers to start...
timeout /t 4 /nobreak >nul

echo  Opening browser...
start "" "http://localhost:3001"

echo.
echo  ================================
echo   Servers started!
echo   Backend:   http://localhost:8004
echo   Frontend:  http://localhost:3001
echo   API Docs:  http://localhost:8004/docs
echo  ================================
echo.
pause
