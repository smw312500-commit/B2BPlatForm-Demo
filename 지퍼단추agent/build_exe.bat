@echo off
chcp 65001 >nul
echo.
echo  [1/3] 프론트엔드 빌드...
cd /d "%~dp0frontend"
call npm run build
if errorlevel 1 (
    echo  [오류] npm run build 실패
    pause
    exit /b 1
)

echo.
echo  [2/3] PyInstaller EXE 패키징...
cd /d "%~dp0"
pyinstaller --onefile --noconsole --name ZipperButtonAgent launcher.py
if errorlevel 1 (
    echo  [오류] PyInstaller 실패
    pause
    exit /b 1
)

echo.
echo  [3/3] dist\ZipperButtonAgent.exe → 루트로 복사
copy /Y dist\ZipperButtonAgent.exe ZipperButtonAgent.exe

echo.
echo  완료! ZipperButtonAgent.exe 생성됨.
pause
