@echo off
REM ========================================
REM  Lanhu MCP Server - Windows 打包脚本
REM ========================================

echo.
echo ========================================
echo   Lanhu MCP Server - 打包构建
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
echo [1/4] 安装依赖...
pip install -r requirements.txt -q
pip install pyinstaller -q
pip install pystray Pillow -q

REM 清理旧的构建
echo [2/4] 清理旧构建...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM 打包
echo [3/4] 开始打包...
pyinstaller lanhu_mcp.spec --clean --noconfirm

REM 检查结果
if exist dist\lanhu_mcp\lanhu_mcp.exe (
    echo.
    echo ========================================
    echo   打包成功！
    echo ========================================
    echo.
    echo 输出目录: dist\lanhu_mcp\
    echo 可执行文件: dist\lanhu_mcp\lanhu_mcp.exe
    echo.
    echo 使用方法:
    echo   1. 双击 lanhu_mcp.exe 启动服务
    echo   2. 首次运行会自动生成配置文件
    echo   3. 运行 lanhu_mcp.exe --setup 进行配置
    echo.
) else (
    echo.
    echo [错误] 打包失败，请检查错误信息
)

pause
