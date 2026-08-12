#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Set PYTHON_BIN if python3 is not on PATH." >&2
  exit 1
fi

echo "Installing build and GUI dependencies..."
"$PYTHON_BIN" -m pip install -e ".[build,gui]"

echo "Cleaning previous build outputs..."
rm -rf "$ROOT_DIR/dist" "$ROOT_DIR/build"

echo "Building Lanhu MCP for $(uname -s) / $(uname -m)..."
"$PYTHON_BIN" -m PyInstaller LanhuMCP-onefile.spec --noconfirm --clean

if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "macOS build output: $ROOT_DIR/dist/LanhuMCP"
else
  echo "Unix build output: $ROOT_DIR/dist/LanhuMCP"
fi
