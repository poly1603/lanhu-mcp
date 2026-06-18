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
pip install -r requirements.txt -q 2>nul
pip install pyinstaller -q 2>nul

echo [2/4] Cleaning old build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [3/4] Building single exe, please wait...
echo.

pyinstaller ^
    --name LanhuMCP ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --hidden-import lanhu_mcp_server ^
    --hidden-import lanhu_mcp ^
    --hidden-import lanhu_mcp.server ^
    --hidden-import lanhu_mcp.tools ^
    --hidden-import lanhu_mcp.tools.design_system ^
    --hidden-import lanhu_mcp.tools.layout_spec ^
    --hidden-import lanhu_mcp.tools.components ^
    --hidden-import lanhu_mcp.tools.interactions ^
    --hidden-import lanhu_mcp.tools.quality_check ^
    --hidden-import lanhu_mcp.tools.code_gen ^
    --hidden-import lanhu_mcp.tools.compare ^
    --hidden-import lanhu_mcp.tools.batch_download ^
    --hidden-import lanhu_mcp.tools.annotations ^
    --hidden-import lanhu_mcp.tools.version_history ^
    --hidden-import lanhu_mcp.tools.svg_extract ^
    --hidden-import lanhu_mcp.tools.measurements ^
    --hidden-import lanhu_mcp.tools.animation ^
    --hidden-import lanhu_mcp.tools.export_options ^
    --hidden-import lanhu_mcp.tools.responsive ^
    --hidden-import lanhu_mcp.core ^
    --hidden-import lanhu_mcp.converters ^
    --hidden-import lanhu_mcp.utils ^
    --hidden-import lanhu_mcp.prompts ^
    --hidden-import fastmcp ^
    --hidden-import fastmcp.server ^
    --hidden-import fastmcp.utilities ^
    --hidden-import fastmcp.utilities.types ^
    --hidden-import httpx ^
    --hidden-import httpcore ^
    --hidden-import bs4 ^
    --hidden-import lxml ^
    --hidden-import lxml.etree ^
    --hidden-import dotenv ^
    --hidden-import htmlmin ^
    --hidden-import starlette ^
    --hidden-import uvicorn ^
    --hidden-import pydantic ^
    --hidden-import pydantic_core ^
    --hidden-import sse_starlette ^
    --hidden-import mcp ^
    --hidden-import mcp.client.sse ^
    --hidden-import mcp.server.sse ^
    --hidden-import authlib ^
    --hidden-import joserfc ^
    --hidden-import watchfiles ^
    --hidden-import websockets ^
    --hidden-import jsonschema ^
    --hidden-import referencing ^
    --hidden-import typer ^
    --hidden-import ssl ^
    --hidden-import certifi ^
    --hidden-import charset_normalizer ^
    --hidden-import idna ^
    --exclude-module tkinter.test ^
    --exclude-module unittest ^
    --exclude-module pytest ^
    --exclude-module PIL ^
    --exclude-module matplotlib ^
    --exclude-module numpy ^
    --exclude-module pandas ^
    lanhu_mcp_all.py

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
