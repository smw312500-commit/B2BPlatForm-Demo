@echo off
title Label Agent Setup

echo.
echo  ================================
echo   Label Agent - Setup
echo  ================================
echo.

if not exist "%~dp0backend\.env" (
    copy "%~dp0backend\.env.example" "%~dp0backend\.env" >nul
    echo  [OK] .env created - please edit backend\.env
) else (
    echo  [SKIP] .env already exists
)

echo.
echo  [1/3] Installing Python packages...
cd /d "%~dp0backend"
pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] pip install failed
    pause
    exit /b 1
)

echo.
echo  [2/3] Inserting initial DB data...
python init_db.py

echo.
echo  [3/3] Installing Node packages...
cd /d "%~dp0frontend"
npm install
if errorlevel 1 (
    echo  [ERROR] npm install failed
    pause
    exit /b 1
)

echo.
echo  ================================
echo   Setup complete! Run start.bat
echo  ================================
echo.
pause
