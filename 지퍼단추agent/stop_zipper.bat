@echo off
chcp 65001 >nul
echo.
echo  지퍼단추Agent 종료 중...
echo.

taskkill /F /IM ZipperButtonAgent.exe >nul 2>&1 && echo  [OK] ZipperButtonAgent.exe 종료 || echo  [스킵] ZipperButtonAgent.exe 실행 중 아님

for /f "delims=" %%P in ('netstat -ano ^| findstr ":8003 " ^| findstr "LISTENING"') do (
    for /f "tokens=5" %%X in ("%%P") do (
        taskkill /F /PID %%X >nul 2>&1
    )
)
for /f "delims=" %%P in ('netstat -ano ^| findstr ":5175 " ^| findstr "LISTENING"') do (
    for /f "tokens=5" %%X in ("%%P") do (
        taskkill /F /PID %%X >nul 2>&1
    )
)

echo  [OK] 포트 8003 / 5175 프로세스 정리 완료
echo.
pause
