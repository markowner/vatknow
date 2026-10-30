@echo off
:: VatKnow 本地开发启动脚本（Windows 双击入口）
:: 支持参数：start.bat --local / --docker / --help
:: 实际逻辑在 start.ps1 中

set ARGS=%*
if "%ARGS%"=="" set ARGS=

where pwsh >nul 2>nul
if %errorlevel%==0 (
    pwsh -ExecutionPolicy Bypass -File "%~dp0start.ps1" %ARGS%
    goto :end
)

where powershell >nul 2>nul
if %errorlevel%==0 (
    powershell -ExecutionPolicy Bypass -File "%~dp0start.ps1" %ARGS%
    goto :end
)

echo [ERROR] 未找到 PowerShell，请确认系统包含 PowerShell
pause

:end
