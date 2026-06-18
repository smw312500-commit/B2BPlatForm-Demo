@echo off
chcp 65001 >nul
echo.
echo  물류Agent 종료 중...
echo.

taskkill /F /IM LogisticsAgent.exe >nul 2>&1 && echo  [OK] LogisticsAgent.exe 종료 || echo  [스킵] LogisticsAgent.exe 실행 중 아님

taskkill /F /FI "WINDOWTITLE eq Logistics-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Logistics-Frontend*" >nul 2>&1

for /f "delims=" %%P in ('netstat -ano ^| findstr ":8004 " ^| findstr "LISTENING"') do (
    for /f "tokens=5" %%X in ("%%P") do (
        taskkill /F /PID %%X >nul 2>&1
    )
)
for /f "delims=" %%P in ('netstat -ano ^| findstr ":3001 " ^| findstr "LISTENING"') do (
    for /f "tokens=5" %%X in ("%%P") do (
        taskkill /F /PID %%X >nul 2>&1
    )
)

echo  [OK] 포트 8004 / 3001 프로세스 정리 완료
echo.
pause
