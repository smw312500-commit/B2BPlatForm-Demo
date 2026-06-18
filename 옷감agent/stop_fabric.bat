@echo off
chcp 65001 >nul
title 옷감Agent 종료

echo  FabricAgent 및 백엔드/프론트 프로세스를 종료합니다...

:: 런처 종료
taskkill /F /IM FabricAgent.exe >nul 2>&1

:: 포트 8002(backend) / 3000(frontend) 점유 프로세스 종료
for %%P in (8002 3000) do (
    for /f "tokens=5" %%I in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
        taskkill /F /PID %%I >nul 2>&1
    )
)

echo  [OK] 종료 완료.
timeout /t 2 /nobreak >nul
