#!/bin/bash
# ========================================
#  Lanhu MCP Server - macOS 打包脚本
# ========================================

echo ""
echo "========================================"
echo "  Lanhu MCP Server - 打包构建"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请先安装 Python 3.10+"
    exit 1
fi

# 安装依赖
echo "[1/4] 安装依赖..."
python3 -m pip install --upgrade pip
python3 -m pip install -e ".[build,gui]" -q

# 清理旧的构建
echo "[2/4] 清理旧构建..."
rm -rf dist build

# 打包
echo "[3/4] 开始打包..."
python3 -m PyInstaller LanhuMCP-onefile.spec --clean --noconfirm

# 检查结果
if [ -f dist/LanhuMCP ]; then
    echo ""
    echo "========================================"
    echo "  打包成功！"
    echo "========================================"
    echo ""
    echo "输出文件: dist/LanhuMCP"
    echo ""
    echo "使用方法:"
    echo "  1. 运行 ./dist/LanhuMCP 启动 GUI"
    echo "  2. 运行 ./dist/LanhuMCP --server 启动 MCP 服务"
    echo ""
else
    echo ""
    echo "[错误] 打包失败，请检查错误信息"
fi
