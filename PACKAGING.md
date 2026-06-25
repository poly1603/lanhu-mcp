# Lanhu MCP Server - 打包指南

> 打包统一使用唯一权威配置 `LanhuMCP-onefile.spec`（GUI + Server 合并为单个 exe）。

## 快速打包

```bash
# 1. 安装所有依赖（含 pyinstaller）
pip install -e ".[build]"
# 或
pip install -r requirements.txt pyinstaller

# 2. 打包
pyinstaller LanhuMCP-onefile.spec --clean --noconfirm
```

输出位于 `dist/LanhuMCP.exe`。

## 打包后的使用

### 命令行模式（默认）
```bash
# Windows
dist\lanhu_mcp\lanhu_mcp.exe

# macOS/Linux
./dist/lanhu_mcp/lanhu_mcp
```

### 配置向导
```bash
# 首次运行，配置蓝湖Cookie等信息
lanhu_mcp --setup
```

### 系统托盘模式（可选）
```bash
# 需要安装 pystray: pip install pystray Pillow
lanhu_mcp --tray
```

### 查看配置
```bash
lanhu_mcp --config
```

## 配置文件

配置文件自动保存在：
- **Windows**: `%APPDATA%\LanhuMCP\.env`
- **macOS**: `~/Library/Application Support/LanhuMCP/.env`
- **Linux**: `~/.config/lanhu-mcp/.env`

也可以在程序目录下创建 `.env` 文件。

## MCP 客户端配置

### Cursor / Windsurf
```json
{
  "mcpServers": {
    "lanhu": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Claude Desktop
```json
{
  "mcpServers": {
    "lanhu": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### stdio 模式
```json
{
  "mcpServers": {
    "lanhu": {
      "command": "path/to/lanhu_mcp",
      "args": []
    }
  }
}
```
需要设置 `MCP_TRANSPORT=stdio` 环境变量。

## 文件说明

| 文件 | 说明 |
|------|------|
| `lanhu_mcp_gui.py` | GUI 主入口（亦分发 `--server` / `--login-helper` 子进程） |
| `lanhu_mcp_app.py` | CLI 入口，支持 `--setup` / `--tray` / `--config` |
| `LanhuMCP-onefile.spec` | PyInstaller 唯一打包配置 |

## 故障排除

### 打包失败
1. 确保安装了所有依赖：`pip install -r requirements.txt`
2. 确保安装了 PyInstaller：`pip install pyinstaller`
3. 检查 Python 版本 >= 3.10

### 运行时错误
1. 首次运行需要配置：`lanhu_mcp --setup`
2. 检查 `.env` 文件中的 Cookie 是否正确
3. 确保端口 8000 未被占用

### macOS 安全提示
如果遇到 "无法验证开发者" 提示：
1. 系统偏好设置 → 安全性与隐私
2. 点击 "仍要打开"
