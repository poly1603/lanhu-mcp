# Lanhu MCP Server - 打包指南

> 打包统一使用唯一权威配置 `LanhuMCP-onefile.spec`（Flet GUI + MCP Server + 登录辅助进程合并为单个 exe）。

## 环境要求

- Windows 10/11
- Python 3.10+
- 可访问 PyPI 的网络环境
- 推荐使用干净虚拟环境，避免旧版 Flet / PyInstaller 缓存污染构建

## 快速打包

```powershell
# 1. 安装运行与打包依赖
python -m pip install --upgrade pip
python -m pip install -e ".[build,gui]"

# 2. 清理旧产物
Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue

# 3. 打包 onefile
python -m PyInstaller LanhuMCP-onefile.spec --clean --noconfirm
```

也可以直接执行：

```bat
build.bat
```

输出位于：

```text
dist\LanhuMCP.exe
```

## 打包后三分支验证

> 当前自动化环境缺少 Flet / PyInstaller，无法代替本机验证。发布前必须在 Windows 本机执行以下检查。

### 1. 默认 GUI

```powershell
$env:LANHU_GUI_SMOKE_CLOSE = "1"
Start-Process -FilePath .\dist\LanhuMCP.exe -Wait
Remove-Item Env:\LANHU_GUI_SMOKE_CLOSE -ErrorAction SilentlyContinue
```

检查点：

- 进程能启动并正常退出 smoke 模式。
- 非 smoke 模式双击 `LanhuMCP.exe` 可打开 Flet 桌面工作台。
- 账号页、项目页、服务页、设计稿浏览入口可正常切换。

### 2. MCP Server 分支

```powershell
$env:LANHU_MCP_PORT = "8898"
$p = Start-Process -FilePath .\dist\LanhuMCP.exe -ArgumentList "--server" -PassThru
Start-Sleep -Seconds 5
Invoke-WebRequest http://127.0.0.1:8898/mcp -UseBasicParsing
Stop-Process -Id $p.Id -Force
Remove-Item Env:\LANHU_MCP_PORT -ErrorAction SilentlyContinue
```

检查点：

- 服务监听 `/mcp`。
- 内置基础工具与高还原设计扩展工具均已注册。
- 停止进程后端口释放。

### 3. 登录辅助分支

```powershell
$tmp = Join-Path $env:TEMP "lanhu-login-result.json"
Remove-Item $tmp -ErrorAction SilentlyContinue
$env:LANHU_LOGIN_HELPER_SMOKE = "1"
Start-Process -FilePath .\dist\LanhuMCP.exe -ArgumentList "--login-helper", $tmp, "https://lanhuapp.com/web/" -Wait
Get-Content $tmp -Raw
Remove-Item Env:\LANHU_LOGIN_HELPER_SMOKE -ErrorAction SilentlyContinue
```

检查点：

- 能写出 JSON 结果文件。
- 非 smoke 模式能打开 WebView2 登录窗口。
- 匿名 Cookie 不会被误判为登录成功。

## 运行方式

```powershell
# 默认打开 Flet GUI
.\dist\LanhuMCP.exe

# 启动 MCP HTTP 服务
.\dist\LanhuMCP.exe --server

# 登录辅助子进程（通常由 GUI 自动调用）
.\dist\LanhuMCP.exe --login-helper <result-json-path> [login-url]
```

## 配置文件

配置文件和运行数据自动保存在：

- Windows: `%APPDATA%\LanhuMCP\`
- macOS: `~/Library/Application Support/LanhuMCP/`
- Linux: `~/.config/lanhu-mcp/`

常见文件：

| 文件 | 说明 |
|------|------|
| `accounts.json` | 多账号 Cookie 与用户资料 |
| `projects.json` | 手动保存项目与最近项目 |
| `messages_*.json` | 团队留言板项目数据 |

## MCP 客户端配置

### Cursor / Windsurf / Cline / Roo Code / Continue

```json
{
  "mcpServers": {
    "lanhu": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### Claude Code / Claude Desktop HTTP MCP

```json
{
  "mcpServers": {
    "lanhu": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### Codex TOML

```toml
[mcp_servers.lanhu]
url = "http://127.0.0.1:8000/mcp"
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `lanhu_mcp_gui.py` | onefile 主入口，负责默认 GUI、`--server`、`--login-helper` 分发 |
| `lanhu_mcp_app.py` | 兼容 CLI 入口 |
| `lanhu_mcp_server.py` | MCP 服务入口 |
| `LanhuMCP-onefile.spec` | PyInstaller 唯一打包配置 |
| `build.bat` / `build_onefile.bat` | Windows 本地打包脚本 |

## 故障排除

### 打包失败

1. 确认 Python 版本为 3.10+。
2. 使用干净虚拟环境重新安装：`python -m pip install -e ".[build,gui]"`。
3. 删除 `dist/`、`build/` 后重新执行 PyInstaller。
4. 如果 Flet 运行时缺失，优先在本机补充执行 `flet pack` 路径验证，再同步调整 `LanhuMCP-onefile.spec` 的 `collect_submodules('flet')` / `collect_data_files('flet')`。

### GUI 启动失败

1. 先用 `LANHU_GUI_SMOKE_CLOSE=1` 验证入口是否能启动。
2. 检查系统是否安装 WebView2 Runtime。
3. 检查 `%APPDATA%\LanhuMCP\` 下账号或项目配置是否损坏，可临时备份后重试。

### 服务不可访问

1. 确认端口未被占用。
2. 确认 MCP 客户端 URL 与 GUI 服务页展示一致。
3. 检查日志页或终端输出中的 Cookie 过期、网络失败、蓝湖接口变更提示。
