@echo off
title Fabric Agent - Fast Start

echo  [Fast Start] Backend + Frontend
echo.

start "Backend :8001" cmd /k "cd /d "%~dp0backend" && call venv\Scripts\activate && uvicorn main:app --host 0.0.0.0 --port 8001 --reload"

timeout /t 2 /nobreak > nul

start "Frontend :3000" cmd /k "cd /d "%~dp0frontend" && npm start"

echo  Backend  : http://localhost:8001
echo  Frontend : http://localhost:3000
echo  API Docs : http://localhost:8001/docs
echo.
pause
