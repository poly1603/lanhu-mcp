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
pip3 install -r requirements.txt -q
pip3 install pyinstaller -q
pip3 install pystray Pillow -q

# 清理旧的构建
echo "[2/4] 清理旧构建..."
rm -rf dist build

# 打包
echo "[3/4] 开始打包..."
pyinstaller lanhu_mcp.spec --clean --noconfirm

# 检查结果
if [ -f dist/lanhu_mcp/lanhu_mcp ]; then
    echo ""
    echo "========================================"
    echo "  打包成功！"
    echo "========================================"
    echo ""
    echo "输出目录: dist/lanhu_mcp/"
    echo "可执行文件: dist/lanhu_mcp/lanhu_mcp"
    echo ""
    echo "使用方法:"
    echo "  1. 进入 dist/lanhu_mcp/ 目录"
    echo "  2. 双击 lanhu_mcp 或在终端运行 ./lanhu_mcp"
    echo "  3. 首次运行会自动生成配置文件"
    echo "  4. 运行 ./lanhu_mcp --setup 进行配置"
    echo ""
    echo "创建 .app 包装（可选）:"
    echo "  使用 create_app.sh 脚本"
    echo ""
else
    echo ""
    echo "[错误] 打包失败，请检查错误信息"
fi
