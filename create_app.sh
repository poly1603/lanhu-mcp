#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "create_app.sh is only for macOS; use build.sh on Linux or Windows." >&2
  exit 1
fi

if [[ ! -x "$ROOT_DIR/dist/LanhuMCP" && ! -d "$ROOT_DIR/dist/LanhuMCP.app" ]]; then
  "$ROOT_DIR/build.sh"
fi

if [[ -d "$ROOT_DIR/dist/LanhuMCP.app" ]]; then
  echo "macOS app bundle: $ROOT_DIR/dist/LanhuMCP.app"
  exit 0
fi

APP_DIR="$ROOT_DIR/dist/Lanhu MCP.app"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
cp "$ROOT_DIR/dist/LanhuMCP" "$APP_DIR/Contents/MacOS/LanhuMCP"
chmod +x "$APP_DIR/Contents/MacOS/LanhuMCP"

cat > "$APP_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>LanhuMCP</string>
  <key>CFBundleIdentifier</key>
  <string>com.lanhu.mcp</string>
  <key>CFBundleName</key>
  <string>Lanhu MCP</string>
  <key>CFBundleDisplayName</key>
  <string>Lanhu MCP</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleVersion</key>
  <string>1.0.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

echo "macOS app bundle: $APP_DIR"
