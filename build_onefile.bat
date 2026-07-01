@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Lanhu MCP Server - One File Build
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.10+
    pause
    exit /b 1
)

echo [1/4] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -e ".[build,gui]" -q

echo [2/4] Cleaning old build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [3/4] Building single exe, please wait...
echo.

pyinstaller LanhuMCP-onefile.spec --noconfirm --clean

echo.
echo [4/4] Checking result...
echo.

if exist dist\LanhuMCP.exe (
    echo ========================================
    echo   Build Success!
    echo ========================================
    echo.
    echo   Output: dist\LanhuMCP.exe
    echo.
    echo   Usage:
    echo     1. Double click LanhuMCP.exe to start
    echo     2. Config dir: %APPDATA%\LanhuMCP\
    echo     3. Set Cookie then start service
    echo.
) else (
    echo ========================================
    echo   Build Failed! Check errors above
    echo ========================================
)

pause
