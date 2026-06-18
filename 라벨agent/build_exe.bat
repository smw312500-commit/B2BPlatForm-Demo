@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  ================================================
echo   라벨Agent EXE 빌드
echo  ================================================
echo.

:: ── [1] 프론트엔드 빌드 ──────────────────────────────────
echo  [1/4] 프론트엔드 빌드 중 (npm run build)...
cd frontend
call npm run build
if errorlevel 1 (
    echo.
    echo  [오류] npm run build 실패. Node.js 및 패키지 설치 상태를 확인하세요.
    pause
    exit /b 1
)
cd ..
echo  [OK] frontend/dist 생성 완료.
echo.

:: ── [2] PyInstaller 설치 ────────────────────────────────
echo  [2/4] PyInstaller 설치 확인...
py -m pip install pyinstaller --quiet
if errorlevel 1 (
    echo  [경고] PyInstaller 설치 실패. pip 상태를 확인하세요.
)
echo  [OK]
echo.

:: ── [3] EXE 빌드 ────────────────────────────────────────
echo  [3/4] EXE 빌드 중...
py -m PyInstaller ^
  --onefile ^
  --noconsole ^
  --name LabelAgent ^
  launcher.py

if errorlevel 1 (
    echo.
    echo  [오류] PyInstaller 빌드 실패. 위 로그를 확인하세요.
    pause
    exit /b 1
)
echo  [OK] dist/LabelAgent.exe 생성 완료.
echo.

:: ── [4] EXE 루트에 복사 ─────────────────────────────────
echo  [4/4] 루트 폴더에 EXE 배포...
if exist LabelAgent.exe del LabelAgent.exe
copy dist\LabelAgent.exe LabelAgent.exe >nul
echo  [OK] LabelAgent.exe 배포 완료.
echo.

echo  ================================================
echo   빌드 완료!
echo  ================================================
echo.
echo   실행 방법: LabelAgent.exe 더블클릭
echo   주    소 : http://localhost:8001
echo   로    그 : logs\backend.log / logs\launcher.log
echo   종    료 : 작업 관리자 → LabelAgent.exe 종료
echo.
echo   ※ 데모 모드:
echo      DEMO_MODE=1 자동 주입 — 첫 실행 시 기본/7월 시연 데이터 자동 준비
echo.
pause
