#!/bin/bash
# ========================================
#  Lanhu MCP Server - macOS .app 打包
# ========================================

APP_NAME="Lanhu MCP"
APP_VERSION="2.0.0"
ICON_FILE="icon.icns"  # 可选：准备一个 .icns 图标文件

echo "创建 macOS .app 包..."

# 检查可执行文件
if [ ! -f dist/lanhu_mcp/lanhu_mcp ]; then
    echo "错误：请先运行 build.sh 生成可执行文件"
    exit 1
fi

# 创建 .app 目录结构
APP_DIR="dist/${APP_NAME}.app"
mkdir -p "${APP_DIR}/Contents/MacOS"
mkdir -p "${APP_DIR}/Contents/Resources"

# 复制可执行文件
cp dist/lanhu_mcp/lanhu_mcp "${APP_DIR}/Contents/MacOS/"

# 复制依赖文件
cp -r dist/lanhu_mcp/* "${APP_DIR}/Contents/MacOS/"

# 创建 Info.plist
cat > "${APP_DIR}/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>lanhu_mcp</string>
    <key>CFBundleIdentifier</key>
    <string>com.lanhu.mcp-server</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleVersion</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${APP_VERSION}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# 创建启动脚本
cat > "${APP_DIR}/Contents/MacOS/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./lanhu_mcp
EOF
chmod +x "${APP_DIR}/Contents/MacOS/start.sh"

echo ""
echo "========================================"
echo "  .app 创建成功！"
echo "========================================"
echo ""
echo "应用位置: ${APP_NAME}.app"
echo "双击即可运行"
echo ""
