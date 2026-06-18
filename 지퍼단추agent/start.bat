@echo off
title Zipper Agent

echo  [0/4] Stopping previous sessions...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8003 "') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5175 "') do taskkill /f /pid %%a >nul 2>&1
timeout /t 1 /nobreak >nul

echo  [1/4] Checking Python packages...
cd /d "%~dp0backend"
pip install -r requirements.txt
if errorlevel 1 (
    echo  [!] pip install had issues - checking if modules are available...
    python -c "import fastapi, uvicorn, sqlalchemy, pymysql, reportlab, openai" >nul 2>&1
    if errorlevel 1 ( echo [ERROR] Required packages missing & pause & exit /b 1 )
    echo  [!] All modules available - continuing
)

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

echo  [3/4] Starting Backend  (http://localhost:8003)...
start "Backend" cmd /k "cd /d %~dp0backend && uvicorn main:app --reload --port 8003"

timeout /t 2 /nobreak >nul

echo  [4/4] Starting Frontend (http://localhost:5175)...
start "Frontend" cmd /k "cd /d %~dp0frontend && npx vite"

timeout /t 3 /nobreak >nul

echo.
echo  ================================
echo   Frontend : http://localhost:5175
echo   API Docs : http://localhost:8003/docs
echo  ================================
start http://localhost:5175
