@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  ================================================
echo   옷감Agent EXE 빌드 (FabricAgent.exe)
echo  ================================================
echo.

:: ── [1] 프론트엔드 빌드 (CRA) ───────────────────────────
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
echo  [OK] frontend/build 생성 완료.
echo.

:: ── [2] PyInstaller 설치 확인 ───────────────────────────
echo  [2/4] PyInstaller 설치 확인...
py -m pip install pyinstaller --quiet
echo  [OK]
echo.

:: ── [3] EXE 빌드 (spec 사용) ────────────────────────────
echo  [3/4] EXE 빌드 중...
py -m PyInstaller FabricAgent.spec --noconfirm
if errorlevel 1 (
    echo.
    echo  [오류] PyInstaller 빌드 실패. 위 로그를 확인하세요.
    pause
    exit /b 1
)
echo  [OK] dist/FabricAgent.exe 생성 완료.
echo.

:: ── [4] EXE 루트에 복사 ─────────────────────────────────
echo  [4/4] 루트 폴더에 EXE 배포...
if exist FabricAgent.exe del FabricAgent.exe
copy dist\FabricAgent.exe FabricAgent.exe >nul
echo  [OK] FabricAgent.exe 배포 완료.
echo.

echo  ================================================
echo   빌드 완료!
echo  ================================================
echo.
echo   실행 방법: FabricAgent.exe 더블클릭
echo   포    트 : backend 8002 / frontend 3000
echo   로    그 : logs\backend.log / logs\frontend.log / logs\launcher.log
echo   종    료 : stop_fabric.bat (또는 작업 관리자에서 FabricAgent.exe 종료)
echo.
echo   ※ 데모 모드: EXE 실행 시 DEMO_MODE=1 로 백엔드를 띄워
echo      첫 실행에서 7월 원단 시연 데이터가 자동 준비됨
echo.
pause
