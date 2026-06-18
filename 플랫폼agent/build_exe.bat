@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  ================================================
echo   플랫폼Agent EXE 빌드
echo  ================================================
echo.

:: ── [1] aiofiles 설치 (StaticFiles 의존성) ───────────────
echo  [1/5] aiofiles 설치 확인...
py -m pip install aiofiles --quiet
echo  [OK]
echo.

:: ── [2] 프론트엔드 빌드 ──────────────────────────────────
echo  [2/5] 프론트엔드 빌드 중 (npm run build)...
cd frontend
call npm run build
if errorlevel 1 (
    echo.
    echo  [오류] npm run build 실패.
    pause
    exit /b 1
)
cd ..
echo  [OK] frontend/dist 생성 완료.
echo.

:: ── [3] PyInstaller 설치 ────────────────────────────────
echo  [3/5] PyInstaller 설치 확인...
py -m pip install pyinstaller --quiet
echo  [OK]
echo.

:: ── [4] EXE 빌드 ────────────────────────────────────────
echo  [4/5] EXE 빌드 중...
py -m PyInstaller ^
  --onefile ^
  --noconsole ^
  --name PlatformAgent ^
  launcher.py

if errorlevel 1 (
    echo.
    echo  [오류] PyInstaller 빌드 실패.
    pause
    exit /b 1
)
echo  [OK] dist/PlatformAgent.exe 생성 완료.
echo.

:: ── [5] EXE 루트에 복사 ─────────────────────────────────
echo  [5/5] 루트 폴더에 EXE 배포...
if exist PlatformAgent.exe del PlatformAgent.exe
copy dist\PlatformAgent.exe PlatformAgent.exe >nul
echo  [OK] PlatformAgent.exe 배포 완료.
echo.

echo  ================================================
echo   빌드 완료!
echo  ================================================
echo.
echo   실행 방법: PlatformAgent.exe 더블클릭
echo   접속 주소: http://localhost:8000
echo   로    그 : logs\backend.log / logs\launcher.log
echo   종    료 : 작업 관리자 → PlatformAgent.exe 종료
echo.
echo   ※ 데모 모드:
echo      backend\.env 에 DEMO_MODE=1 설정 시
echo      첫 실행에서 4년치 공급망 데이터 자동 준비됨
echo.
pause
