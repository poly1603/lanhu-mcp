# 会话记录

## 2026-06-18 Lanhu MCP App 登录和界面优化
- 修复一键登录：新增 `lanhu_login_helper.py`，通过 pywebview 打开蓝湖并读取 Cookie/localStorage 用户信息。
- 支持打包后登录：`LanhuMCP.exe --login-helper` 可作为登录子进程运行，避免依赖用户机器安装 Python。
- 增加多用户账号：账号保存到 `%APPDATA%\LanhuMCP\accounts.json`，支持切换、退出当前账号，并兼容旧 `cookie.txt`。
- 启动服务前强制检查已登录账号；服务环境会写入 `LANHU_COOKIE`、`LANHU_USER_NAME`、`LANHU_USER_ROLE`。
- 服务启动后展示支持的 MCP 方法列表；MCP URL 带上当前账号角色和姓名查询参数。
- 扩展 AI IDE 识别和配置：Cursor、Windsurf、Claude Desktop、Claude Code、VS Code/Cline、Trae、Cherry Studio、ChatBox、Continue、OpenCode、CodeBuddy、MimoCode、Junie、Codex、Gemini CLI、Roo Code。
- Codex 配置写入 `~/.codex/config.toml` 的 `[mcp_servers.lanhu]`，JSON/YAML 类工具写入 `mcpServers.lanhu.url`。
- 优化 Tkinter UI：重排蓝湖登录/账号区、服务区、方法区、日志区和 IDE 配置区，按钮文案使用 lucide 图标名。
- 修复 Windows Tkinter/PyInstaller 问题：新增 `hook_tcl_find_executable.py`，spec 显式打包 `_tkinter.pyd`、`tcl86t.dll`、`tk86t.dll`、`_tcl_data`、`_tk_data`。
- `build_onefile.bat` 已改为使用 `LanhuMCP-onefile.spec`，避免命令行参数和 spec 分叉。

## 验证
- `python -m py_compile lanhu_mcp_gui.py lanhu_login_helper.py hook_tcl_find_executable.py LanhuMCP.spec LanhuMCP-GUI.spec LanhuMCP-onefile.spec` 通过。
- Python 3.12 下 `bootstrap_tcl_tk_runtime()` 后可成功创建 Tk 窗口。
- 多账号 MCP URL 和 Cookie 读取逻辑已用临时 APPDATA 烟测。
- `python -m PyInstaller LanhuMCP-onefile.spec --noconfirm --clean` 构建成功，输出 `dist\LanhuMCP.exe`。
- exe 启动烟测 8 秒保持运行，说明 GUI 入口没有因 Tkinter 初始化失败退出。

## 已知事项
- PyInstaller 仍会在自己的 hook 探测阶段打印 `tkinter installation is broken`，但 spec 已手动把 Tkinter/TclTk 运行资源打入 exe。
- warn 文件里的 `openai`、`tzdata`、pywebview 多平台依赖缺失属于可选依赖告警。
- 当前未安装 `pytest`，未运行 pytest 测试套件。

## 2026-06-18 继续修复登录黑屏和重排主界面
- 重排 `lanhu_mcp_gui.py` 主界面为左侧菜单导航，右侧分为 `服务`、`AI 工具`、`账号`、`日志` 四个页面。
- 服务页在未登录蓝湖账号时会拦截启动，并自动切换到账号页；启动成功后显示 `MCP_TOOL_NAMES` 全量方法清单。
- 账号页合并蓝湖信息、登录、手动 Cookie、多账号切换和退出当前账号操作。
- AI 工具页增强 Codex、Claude Code、MimoCode 等 CLI 工具识别：除固定安装路径外，还通过 `PATH` 解析命令。
- `lanhu_login_helper.py` 改为每次登录使用独立 WebView2 storage session，避免旧缓存锁导致黑屏；加入 WebView2 地址为空时的错误结果，主界面不会无限等待。
- 打包 spec 补充 `webview.platforms.winforms`、`webview.platforms.edgechromium`、`pythonnet`、`clr_loader` 等隐藏依赖。
- `run_login_helper_from_gui_args()` 新增分支日志和异常兜底，打包后 helper 启动失败也会写入 JSON 错误结果。

## 2026-06-18 验证补充
- `python -m py_compile lanhu_mcp_gui.py lanhu_login_helper.py hook_tcl_find_executable.py LanhuMCP.spec LanhuMCP-GUI.spec LanhuMCP-onefile.spec` 通过。
- 源码级 `create_gui()` 构造烟测通过。
- 源码级登录 helper 分支快速烟测通过。
- `python -m PyInstaller LanhuMCP-onefile.spec --noconfirm --clean` 重新构建成功。
- 打包后 `dist\LanhuMCP.exe --login-helper` 快速烟测通过，能写出登录结果 JSON。
- 最新输出文件：`dist\LanhuMCP.exe`，时间 `2026-06-18 22:00:34`，大小约 `84,971,737` 字节。

## 2026-06-18 启动崩溃修复
- 修复 `NameError: name 'ttk' is not defined`：`apply_modern_style()` 改为函数内显式导入 `ttk`，不再依赖 `create_gui()` 局部导入。
- 重新执行 `py_compile`、源码级 `apply_modern_style()` 烟测和完整 `create_gui()` 构造烟测。
- 重新执行 `PyInstaller LanhuMCP-onefile.spec --noconfirm --clean`，已生成新的 `dist\LanhuMCP.exe`。

## 2026-06-18 继续优化多账号登录和主界面
- 重构账号页：新增“登录地址”“已登录账号”列表和“手动 Cookie”区域，每个账号行支持切换和单独退出，并明确标记当前使用账号。
- Cookie 输入框默认展示摘要，不再把完整 Cookie 长时间明文铺在界面上；保存摘要时会回退使用内存中的完整 Cookie。
- `lanhu_login_helper.py` 支持从主界面传入登录地址，先显示白底加载页再导航蓝湖，避免网络慢时出现黑窗口。
- 登录 helper 增加 Edge/WebView2 错误页检测，遇到 `ERR_TIMED_OUT` 等网络错误时写入明确 JSON 错误，主界面会提示改用系统浏览器打开登录页。
- 主界面新增可保存的 `LANHU_LOGIN_URL`，默认仍为 `https://lanhuapp.com/web/`，方便用户处理代理或企业入口。
- 将左侧导航和卡片标题从裸露 lucide 图标名改为内置 Tk 线性图标/干净中文文案，避免出现 `server-cog`、`key-round` 等调试感文本。
- 优化 AI 工具页显示文案，并按官方 HTTP MCP 结构修正 Claude Code 配置：写入 `~/.claude.json` 的 `mcpServers.lanhu = { type: "http", url: ... }`；Codex 继续写入 `~/.codex/config.toml`。
- 重新生成 `dist\LanhuMCP.exe`，时间为 `2026-06-18 22:47:03`，大小约 `84,989,346` 字节。

## 2026-06-18 验证补充
- `python -m py_compile lanhu_mcp_gui.py lanhu_login_helper.py hook_tcl_find_executable.py LanhuMCP.spec LanhuMCP-GUI.spec LanhuMCP-onefile.spec` 通过。
- 源码级 `create_gui()` 构造烟测通过，覆盖新卡片、多账号列表和内置图标渲染。
- 源码级 `lanhu_login_helper.py` smoke JSON 写出成功结果；当前自动化环境仍会打印 WebView2 `E_ABORT` 内部日志，但不阻塞 JSON 结果。
- `PyInstaller LanhuMCP-onefile.spec --noconfirm --clean` 通过；第一次因旧 `dist\LanhuMCP.exe` 进程占用失败，停止旧进程后重建成功。
- 打包后 `dist\LanhuMCP.exe --login-helper` smoke 通过，能接收登录 URL 参数并写出结果 JSON。

## 2026-06-18 登录窗口一闪而过修复
- 根因：`lanhu_login_helper.py` 把蓝湖首页匿名 Cookie 误判成已登录。实际结果中只有 `SERVERID`、`_bl_uid` 和 `user_token=undefined`，程序仍然返回 success，导致窗口刚打开就被关闭。
- 修复：新增 Cookie 解析和有效登录令牌判断，`undefined/null/空值` 不再算登录；匿名 Cookie 名称 `SERVERID`、`_bl_uid`、`supportWebP` 会被忽略。
- 修复：登录完成判断必须满足蓝湖域名下存在有效 auth/token/session 类 Cookie，并结合用户信息、已登录路由或 Web 首页状态判断。
- 补充诊断：读取到匿名 Cookie 时记录“继续等待用户完成登录”，避免再次误判。
- 验证：最小登录判定测试通过，确认 `user_token=undefined` 不会触发登录成功；源码级 `py_compile`、`create_gui()`、helper smoke 均通过。
- 重新打包 `dist\LanhuMCP.exe`，时间为 `2026-06-18 23:11:32`，大小约 `84,991,425` 字节；打包后 helper smoke 通过。

## 2026-06-19 方法扩展、项目页和界面优化
- 修复方法列表只显示 13 个的问题：GUI 现在通过 AST 扫描 `lanhu_mcp_server.py` 和 `lanhu_mcp/server.py` 中的 `@mcp.tool()`，当前发现 28 个 MCP 方法。
- 内置服务分支不再直接 `runpy` 重跑服务端模块，改为导入同一个 `lanhu_mcp_server.mcp` 实例，并加载 `lanhu_mcp.server` 扩展模块，确保高还原设计工具实际注册到运行中的服务。
- 新增 12 个高还原相关能力展示：设计系统、布局规格、组件模式、设计 QA、设计对比、框架代码生成、批量资源下载、SVG、测量、动效、导出选项、响应式变体。
- 服务页支持按“需求与原型 / UI 设计 / 高还原开发 / 协作”分组展示方法，并显示总数。
- 新增“项目”左侧菜单和项目页：支持当前账号刷新项目、显示项目 ID/团队 ID/项目链接、打开项目、复制项目链接。
- 项目读取采用多个蓝湖 Web API 候选端点尝试；若接口格式变化或权限不足，会在项目页和日志里显示失败原因。
- 账号页新增邮箱、手机号、用户名/昵称、头像读取状态展示；读不到时明确显示“未读取到”。
- 左侧导航和顶部工作台区域优化：新增项目菜单图标、品牌区、当前状态、顶部账号/项目/方法统计。

## 2026-06-19 验证补充
- `python -m py_compile lanhu_mcp_gui.py lanhu_login_helper.py hook_tcl_find_executable.py LanhuMCP.spec LanhuMCP-GUI.spec LanhuMCP-onefile.spec` 通过。
- `discover_mcp_tools()` 发现 28 个方法；分组结果：需求与原型 5、UI 设计 5、高还原开发 12、协作 6。
- FastMCP 实例在导入 `lanhu_mcp.server` 后 `list_tools()` 返回 28 个工具。
- 源码级 `create_gui()` 构造烟测通过，覆盖新增项目页和导航。
- 源码级项目数据归一化测试通过。
- `python -m PyInstaller LanhuMCP-onefile.spec --noconfirm --clean` 重新打包成功。
- 打包后 `dist\LanhuMCP.exe --server` 能启动 HTTP 服务并在日志中确认加载扩展工具。
- 打包后 `dist\LanhuMCP.exe --login-helper` smoke 通过，能写出结果 JSON。
- 最新输出文件：`dist\LanhuMCP.exe`，时间 `2026-06-19 00:06:50`，大小 `85,025,646` 字节。
