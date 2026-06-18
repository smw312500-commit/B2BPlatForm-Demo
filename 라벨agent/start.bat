@echo off
title Label Agent

echo  [1/4] Checking Python packages...
cd /d "%~dp0backend"
pip install -r requirements.txt -q
if errorlevel 1 ( echo [ERROR] pip install failed & pause & exit /b 1 )

echo  [2/4] Checking Node packages...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo  node_modules not found - running npm install...
    npm install
    if errorlevel 1 ( echo [ERROR] npm install failed & pause & exit /b 1 )
)

if not exist "%~dp0backend\.env" (
    copy "%~dp0backend\.env.example" "%~dp0backend\.env" >nul
    echo  [!] backend\.env created - please set DB_PASSWORD and OPENAI_API_KEY
)

echo  [3/4] Starting Backend  (http://localhost:8001)...
start "Backend" cmd /k "cd /d %~dp0backend && uvicorn main:app --reload --port 8001"

timeout /t 2 /nobreak >nul

echo  [4/4] Starting Frontend (http://localhost:5173)...
start "Frontend" cmd /k "cd /d %~dp0frontend && npx vite"

timeout /t 3 /nobreak >nul

echo.
echo  ================================
echo   Frontend : http://localhost:5173
echo   API Docs : http://localhost:8001/docs
echo  ================================
start http://localhost:5173
