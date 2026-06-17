@echo off
REM ========================================
REM  Lanhu MCP Server - 完整打包脚本
REM  包含：服务端 + GUI管理面板 + 安装包
REM ========================================

echo.
echo ========================================
echo   Lanhu MCP Server - 完整打包构建
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/5] 安装依赖...
pip install -r requirements.txt -q
pip install pyinstaller -q
pip install pystray Pillow -q

REM 清理旧的构建
echo [2/5] 清理旧构建...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM 打包服务端
echo [3/5] 打包服务端...
pyinstaller lanhu_mcp.spec --clean --noconfirm

REM 打包GUI管理面板
echo [4/5] 打包GUI管理面板...
pyinstaller ^
    --name LanhuMCP-GUI ^
    --onefile ^
    --windowed ^
    --icon icon.ico ^
    --add-data "dist\lanhu_mcp\lanhu_mcp.exe;." ^
    --hidden-import lanhu_mcp ^
    --hidden-import lanhu_mcp.gui ^
    lanhu_mcp_gui.py

REM 检查NSIS
echo [5/5] 检查NSIS安装包工具...
where makensis >nul 2>&1
if errorlevel 1 (
    echo.
    echo [提示] NSIS 未安装，跳过安装包生成
    echo 下载NSIS: https://nsis.sourceforge.io/
    echo 安装NSIS后运行: makensis installer.nsi
    echo.
) else (
    echo 正在生成安装包...
    makensis installer.nsi
    echo.
    echo 安装包已生成: LanhuMCP-Setup.exe
)

REM 检查结果
echo.
echo ========================================
if exist dist\lanhu_mcp\lanhu_mcp.exe (
    echo   打包成功！
    echo ========================================
    echo.
    echo 输出文件:
    echo   服务端: dist\lanhu_mcp\lanhu_mcp.exe
    echo   GUI面板: dist\LanhuMCP-GUI.exe
    if exist LanhuMCP-Setup.exe (
        echo   安装包: LanhuMCP-Setup.exe
    )
    echo.
    echo 使用方法:
    echo   1. 双击 LanhuMCP-GUI.exe 启动管理面板
    echo   2. 或运行 dist\lanhu_mcp\lanhu_mcp.exe 启动服务
    echo.
) else (
    echo   打包失败，请检查错误信息
    echo ========================================
)

pause
