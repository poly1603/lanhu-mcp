@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   Lanhu MCP - Portable EXE + Installer
echo ========================================
echo.

node build.js --clean %*
set "EXIT_CODE=%ERRORLEVEL%"

if "%EXIT_CODE%"=="0" (
    echo.
    echo Outputs:
    echo   dist\LanhuMCP.exe              portable version
    echo   dist\LanhuMCP-Setup-v^<version^>.exe installer with desktop shortcut
)

pause
exit /b %EXIT_CODE%
