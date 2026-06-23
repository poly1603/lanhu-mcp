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

## 2026-06-19 方法、账号资料、项目页和打包收尾
- GUI 支持方法数已从旧的 13 个改为动态扫描 28 个 MCP 工具，来源包括 lanhu_mcp_server.py 和 lanhu_mcp/server.py；运行时内置服务也会导入扩展模块，确保高还原设计工具实际注册。
- 账号页补充蓝湖邮箱、手机号、用户名、昵称、头像、公司、团队、角色、Cookie 指纹和来源展示；登录成功或手动 Cookie 保存后会异步尝试读取蓝湖用户资料接口补全。
- 多用户账号支持切换、单独退出、Cookie 指纹合并重复账号；服务运行中会阻止切换或退出账号。
- 新增项目菜单，支持当前账号项目刷新、项目归一化展示、团队/负责人/更新时间、打开和复制 tid/pid 项目链接。
- AI 工具识别保留 Codex、Claude Code、MimoCode、Cursor、Trae、Windsurf、Cline/Roo、Continue、Gemini CLI 等，并新增 Qoder、Kiro、Zed；配置写入继续支持 JSON/YAML/TOML 和 Claude Code HTTP MCP。
- 头像缓存支持 Pillow 渲染 PNG/JPG/JPEG/WebP/GIF，requirements.txt 加入 Pillow，onefile spec 加入 PIL 隐式依赖。
- 侧栏和页面布局继续优化：增加项目菜单、菜单分组、选中条、更多内置 lucide 风格线性图标、项目页说明和更丰富的页面信息。
## 2026-06-19 验证
- 使用 PYTHONPYCACHEPREFIX 重定向后执行 py_compile 通过，避免既有 __pycache__ 锁文件影响。
- 源码级 create_gui 构造烟测通过。
- FastMCP list_tools 在导入 lanhu_mcp.server 后返回 28 个工具。
- 用户资料解析、资料合并、项目归一化 smoke 通过。
- PyInstaller onefile 重新打包成功，输出 dist\\LanhuMCP.exe，大小 85,038,010 字节，时间 2026-06-19 00:33:01。
- 打包后 --server 使用隔离 APPDATA 和 8898 端口 smoke 通过，日志确认已加载高还原设计扩展工具并监听 0.0.0.0:8898/mcp。
- 打包后 --login-helper 在 LANHU_LOGIN_HELPER_SMOKE=1 下 Start-Process -Wait smoke 通过，结果 JSON 写出 success。
- 测试结束后已停止残留 LanhuMCP.exe 进程，8897/8898 测试端口未占用。

## 2026-06-21 App 窗口、响应式布局、项目页和账号资料优化
- 主窗口默认尺寸调整为 1360x860，并通过屏幕尺寸计算居中打开；最小尺寸保持 1060x700。
- 右侧所有页面改为 Canvas 可滚动容器，避免小窗口下内容不可见；服务页、项目页、AI 工具页双栏区域会按窗口宽度自动切换为单栏。
- 增加现代化视觉：顶部轻量装饰线条、侧栏呼吸状态条、卡片化空态、指标块、AI 工具图标卡片和更清晰的项目/服务信息层级。
- 项目页改为三路合并：蓝湖 API 读取、登录结果 localStorage/sessionStorage/appState 递归提取项目链接、本地手动保存项目链接；新增项目链接输入和保存按钮。
- 账号资料解析扩大字段别名和递归深度，覆盖 emailAddress、displayName、loginName、company_name、team_name、department、jobTitle 等常见字段。
- 登录 helper 现在会把 sessionStorage 和常见前端全局状态 __INITIAL_STATE__/__NUXT__/__NEXT_DATA__/__LANHU_STATE__ 一起回传给 GUI，用于补全账号和项目线索。
- 已重新打包 dist\\LanhuMCP.exe，大小 85,058,614 字节，时间 2026-06-21 15:25:23。
## 2026-06-21 验证
- py_compile 通过。
- 源码级 create_gui 构造 smoke 通过。
- 几何 smoke 确认默认窗口为 1360x860 并带居中坐标。
- 项目 URL 解析、登录缓存项目提取、账号资料扩展解析 smoke 通过；测试写入 data\\projects.json 后已清理。
- 打包后 --login-helper 在 LANHU_LOGIN_HELPER_SMOKE=1 下 Start-Process -Wait smoke 通过。
- 打包后 --server 使用隔离 APPDATA 和 49177 端口 smoke 通过，日志确认已加载高还原设计扩展工具并监听 0.0.0.0:49177/mcp。
- 测试结束后无 LanhuMCP.exe 残留进程，49177 测试端口已释放。

## 2026-06-21 登录、总览 UI、账号资料与项目页集中修复
- 收紧 `lanhu_login_helper.py` 登录成功判定：只接受严格白名单 Cookie 名称，忽略匿名 Cookie 与 `undefined/null/false`，并移除 `/web/#/` 首页即成功的旧条件。
- 登录 helper 增加 4 秒最小等待和更严格 storage 身份字段校验，避免“添加账号/一键登录”弹窗一闪而过。
- `lanhu_mcp_gui.py` 新增 Cookie/JWT 用户资料解析，可从 `user_token`、用户资料 Cookie 和登录返回 storage 中提取邮箱、用户名、头像、姓名等信息。
- 多账号写入逻辑合并 Cookie/JWT 资料与接口资料，避免接口失败时账号页只显示“蓝湖用户”和空联系方式。
- 主界面新增默认“总览”页，展示账号、服务、项目、方法、AI 工具、当前运行路径和 dist/dist2 同步诊断。
- 侧栏新增“总览”菜单，默认进入总览；首页提供添加账号、启动服务、配置 AI 工具等高频入口。
- 账号页新增邮箱、手机、用户名、头像四格详情区，已登录账号列表仍支持切换和单独退出。
- 项目页补充更多候选项目接口，并显示接口候选数量、合并结果和手动项目链接兜底说明。
- 打包后同步 `dist\LanhuMCP.exe` 到 `dist2\LanhuMCP.exe`，避免用户误开旧目录继续看到旧问题。

## 2026-06-21 验证
- `py_compile` 通过：`lanhu_mcp_gui.py`、`lanhu_login_helper.py`、`hook_tcl_find_executable.py`、`LanhuMCP-onefile.spec`。
- 登录判定 smoke 通过：匿名 Cookie 和蓝湖首页不会触发成功，带有效 token 的项目路由可判定成功。
- Cookie/JWT 用户资料解析 smoke 通过：可提取 email、preferred_username、picture、name。
- 源码级 GUI smoke 通过：`LANHU_GUI_SMOKE_CLOSE=1` 自动启动并关闭。
- PyInstaller onefile 重新打包成功，输出 `dist\LanhuMCP.exe`，大小 `85,079,144` 字节，时间 `2026-06-21 16:16:11`。
- `dist\LanhuMCP.exe --login-helper` smoke 通过，可写出登录结果 JSON。
- `dist\LanhuMCP.exe --server` 在 `49217` 端口 smoke 通过，日志确认加载高还原设计扩展工具并监听 `/mcp`。
- `dist2\LanhuMCP.exe` 已同步为同一大小和时间，并通过 GUI 自动关闭 smoke。
- 测试结束后无 `LanhuMCP.exe` 残留进程，`49217` 端口已释放；有两个历史 `python` 进程系统拒绝结束，但不是 LanhuMCP 进程。

## 2026-06-22 GUI 性能、内存和交互体验优化
- `lanhu_mcp_gui.py` 为 MCP 工具 AST 扫描增加 `_MCP_TOOLS_CACHE` 缓存，`discover_mcp_tools(refresh=True)` 可强制刷新，默认复用扫描结果，减少界面刷新时的重复文件读取和 AST 分配。
- 头像下载增加 `AVATAR_MAX_BYTES` 上限检查；服务端声明或实际响应超过 1MB 时跳过缓存，避免读取大文件占用内存或写入半截图片。
- 项目合并新增 `project_identity_key()`，优先按 `team_id + project_id` 去重，修复同一项目因 `stage/product` 不同路由在项目页重复显示的问题。
- 项目刷新和账号资料刷新增加运行中标记，连续点击时只提示等待，不再重复启动后台线程、重复请求和重复渲染。
- GUI 烟测模式新增 `is_gui_smoke_mode()` 和 `should_show_native_error_dialog()`；`LANHU_GUI_SMOKE_CLOSE=1` 下 Tk/Tcl 初始化失败只写日志并返回，不再弹出阻塞式 Windows MessageBox。
- 新增 `tests/test_gui_optimizations.py`，覆盖工具扫描缓存、强制刷新、项目稳定去重和超大头像跳过读取。

## 2026-06-22 验证
- `python -m py_compile lanhu_mcp_gui.py tests\test_gui_optimizations.py` 通过。
- 核心函数 smoke 通过：工具扫描缓存只扫描一次、`refresh=True` 会重新扫描、同一 `tid/pid` 项目合并为一条、超大头像不会读取和写入。
- `LANHU_GUI_SMOKE_CLOSE=1` 源码级 GUI smoke 已验证不会再被 Tk/Tcl 初始化失败的系统弹窗阻塞；当前自动化 Python 环境缺少可用 `init.tcl`，因此本次未完成真实 Tk 窗口构造。
- `git diff --check -- lanhu_mcp_gui.py tests\test_gui_optimizations.py` 无空白错误，仅提示 Windows CRLF 转换。
- 当前环境未安装 `pytest`，`python -m pytest tests\test_gui_optimizations.py -q` 未运行成功。

## 2026-06-22 GUI 轻量动效和低内存交互增强
- 新增 `animation_interval_ms()`、`should_run_sidebar_pulse()`，侧栏呼吸条刷新间隔从 90ms 降到 180ms，并在窗口失焦、最小化或隐藏时跳过绘制，降低持续 CPU/GDI 开销。
- 顶部标题区新增轻量页面切换进度线，页面切换时只运行 4 帧短动画，增强响应感但不引入常驻高频动画。
- 卡片和总览指标 hover 不再改变边框厚度，只切换边框颜色或浅背景，避免 hover 时布局抖动。
- 新增 `project_rows_signature()` 和 `account_rows_signature()`，项目列表与账号列表在可见字段无变化时跳过销毁重建，减少 widget 创建和内存 churn。
- 项目刷新按钮在后台刷新期间显示“刷新中...”，完成后恢复“刷新项目”；重复点击只更新状态提示，不再重复创建刷新线程。
- `tests/test_gui_optimizations.py` 补充动效间隔、动画暂停、项目摘要和账号摘要测试期望。

## 2026-06-22 验证补充
- `python -m py_compile lanhu_mcp_gui.py tests\test_gui_optimizations.py` 通过。
- 轻量交互 helper smoke 通过：侧栏动画间隔为 180ms，失焦/最小化时暂停；项目/账号摘要忽略 raw 噪声字段，但可见字段变化时会变化。
- `LANHU_GUI_SMOKE_CLOSE=1` 源码级 GUI smoke 未阻塞；当前自动化 Python 环境仍缺少可用 `init.tcl`，因此只验证到 Tk/Tcl 初始化失败被记录并返回。
- `git diff --check -- lanhu_mcp_gui.py tests\test_gui_optimizations.py` 无空白错误，仅提示 Windows CRLF 转换。
- 当前环境未安装 `pytest`，新增 pytest 用例未在本环境完整执行。
