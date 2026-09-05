<div align="center">

# 🎨 Lanhu MCP Server | 蓝湖MCP服务器2.0

**让所有 AI 助手共享团队知识，打破 AI IDE 孤岛**

**lanhumcp | 蓝湖mcp | lanhu-mcp | 蓝湖AI助手 | 蓝湖skills | Lanhu AI Integration**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![FastMCP](https://img.shields.io/badge/FastMCP-Powered-orange.svg)](https://github.com/jlowin/fastmcp)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![GitHub Stars](https://img.shields.io/github/stars/dsphper/lanhu-mcp?style=social)](https://github.com/dsphper/lanhu-mcp/stargazers)
[![GitHub Issues](https://img.shields.io/github/issues/dsphper/lanhu-mcp)](https://github.com/dsphper/lanhu-mcp/issues)
[![GitHub Release](https://img.shields.io/github/v/release/dsphper/lanhu-mcp)](https://github.com/dsphper/lanhu-mcp/releases)
[![Code of Conduct](https://img.shields.io/badge/Contributor%20Covenant-2.0-4baaaa.svg)](CODE_OF_CONDUCT.md)

[English](README_EN.md) | 简体中文

[快速开始](#-快速开始) • [功能特性](#-核心特性) • [使用文档](#-使用指南) • [贡献指南](CONTRIBUTING.md)


</div>

---

## 🌟 项目亮点

一个功能强大的 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 服务器，专为 AI 编程时代设计，完美支持蓝湖（Lanhu）设计协作平台。


🔥 **核心创新**：
- 🖥️ **现代化 Tkinter 桌面工作台**：左侧菜单导航，右侧总览/服务/AI工具/项目/账号/日志六大页面，默认 1360x860 居中打开，支持响应式双栏/单栏切换和滚动容器
- 📋 **智能需求分析**：自动提取 Axure 原型，三种分析模式（开发/测试/探索），需求分析准确率>95%
- � **多账号管理**：一键登录（pywebview WebView2）、浏览器 Cookie 读取、手动输入、多账号切换、Cookie 指纹去重、账号资料（邮箱/手机/头像/公司/团队/角色）展示
- 📁 **蓝湖项目管理**：三路合并项目列表（API 读取/登录缓存提取/手动保存），项目链接打开和复制，团队/负责人/更新时间展示
- 🎨 **35个 MCP 工具矩阵**：需求与原型 5 + UI 设计 5 + 高还原开发 15 + 协作 6 + 代码生成 4，完整覆盖产品设计到前端交付全流程
- 🎨 **高还原设计支持**：设计系统提取、布局规格、组件模式、设计 QA、版本对比、框架代码生成、批量资源下载、SVG 提取、元素测量、动效规格、导出选项、响应式变体
- 🛠️ **20+ AI 工具一键配置**：Cursor、Windsurf、Claude Desktop/Code、VS Code/Cline、Trae、Cherry Studio、ChatBox、Continue、OpenCode、CodeBuddy、MimoCode、Junie、Codex、Gemini CLI、Roo Code、Qoder、Kiro、Zed
- 💬 **团队知识库**：打破 AI IDE 孤岛，让所有 AI 助手共享知识库和上下文
- ⚡ **性能优化**：AST 工具扫描缓存、头像下载大小限制、项目按 tid+pid 去重、防重复点击标记、动画降频与失焦暂停

🎯 **适用场景**：
- ✅ Cursor + 蓝湖：让 Cursor AI 直接读取蓝湖需求文档和设计稿
- ✅ Windsurf + 蓝湖：Windsurf Cascade AI 直接读取蓝湖需求文档和设计稿
- ✅ Claude Code + 蓝湖：Claude AI 直接读取蓝湖需求文档和设计稿
- ✅ OpenClaw + 蓝湖：OpenClaw 原生支持读取蓝湖需求文档和设计稿
- ✅ ClawBot + 蓝湖：ClawBot 智能助手深度集成蓝湖协作
- ✅ Trae + 蓝湖：Trae AI 直接读取蓝湖需求文档和设计稿
- ✅ 通义灵码 + 蓝湖：通义灵码 AI 直接读取蓝湖需求文档和设计稿
- ✅ Cline + 蓝湖：Cline AI 直接读取蓝湖需求文档和设计稿
- ✅ 任何支持 MCP 协议的 AI 开发工具

🎯 **解决痛点**：
- ❌ **旧世界**：每个开发者的 AI 独立工作，重复分析需求，无法共享经验
- ✅ **新世界**：所有 AI 连接同一知识中枢，需求分析一次、全员复用，踩坑经验永久保存

---
## 📑 目录

- [核心特性](#-核心特性)
- [快速开始](#-快速开始)
- [团队留言板：突破 AI 协作的最后一公里](#-团队留言板突破-ai-协作的最后一公里)
- [使用指南](#-使用指南)
- [可用工具列表](#-可用工具列表)
- [系统架构](#-系统架构)
- [项目结构](#-项目结构)
- [高级配置](#-高级配置)
- [性能指标](#-性能指标)
- [常见问题](#-常见问题)
- [安全说明](#-安全说明)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)
- [致谢](#-致谢)
- [联系方式](#-联系方式)
- [路线图](#-路线图)

---

## ✨ 核心特性

### 📋 需求文档分析
- **智能文档提取**：自动下载和解析 Axure 原型的所有页面、资源和交互
- **三种分析模式**：
  - 🔧 **开发视角**：详细字段规则、业务逻辑、全局流程图
  - 🧪 **测试视角**：测试场景、用例、边界值、校验规则
  - 🚀 **快速探索**：核心功能概览、模块依赖、评审要点
- **四阶段工作流**：全局扫描 → 分组分析 → 反向验证 → 生成交付物
- **零遗漏保证**：基于 TODO 驱动的系统化分析流程

### 🎨 UI设计支持
- **设计稿查看**：批量下载和展示 UI 设计图
- **设计图分析升级**：分析时不仅返回设计图预览，还可获取**详细设计参数**（组件尺寸、间距、颜色值、字体大小等），并自动将设计 Schema 转为 **HTML+CSS 代码**，与蓝湖原生导出效果一致，便于 AI 参考实现
- **切图提取**：自动识别和导出设计切图、图标资源
- **智能命名**：基于图层路径自动生成语义化文件名

### 💬 团队协作留言板 - 打破 AI IDE 孤岛
> 🌟 **核心创新**：让每个开发者的 AI 助手都能共享团队知识和上下文

**问题背景**：
- 每个开发者的 AI IDE（Cursor、Windsurf）是独立的，无法共享上下文
- A 开发遇到的坑，B 开发的 AI 不知道
- 需求分析结果无法传递给测试同学的 AI
- 团队知识碎片化在各个聊天窗口，无法沉淀

**创新解决方案**：
- 🔗 **统一知识库**：所有 AI 助手连接同一个 MCP 服务器，共享留言板数据
- 🧠 **上下文传递**：开发 AI 分析的需求，测试 AI 可以直接查询使用
- 💡 **知识沉淀**：坑点、经验、最佳实践以"知识库"类型永久保存
- 📋 **任务协作**：通过"任务"类型留言，让 AI 帮忙查询代码、数据库
- 📨 **@提醒机制**：支持飞书通知，打通 AI 协作与人工沟通
- 👥 **协作追踪**：自动记录谁的 AI 访问过哪些文档，团队透明

### ⚡ 性能优化
- **智能缓存**：基于文档版本号的永久缓存机制
- **增量更新**：只下载变更的资源
- **并发处理**：支持批量页面截图和资源下载

### 🖥️ 桌面工作台（Tkinter 原生 GUI）
- **一体化入口**：默认启动 GUI；`--server` 启动 MCP 服务分支；`--login-helper` 作为登录辅助子进程。
- **六页导航**：总览（账号/服务/项目/方法/AI工具统计）、服务（启停/健康检查/配置片段复制）、AI 工具（20+ IDE 识别与配置写入）、项目（蓝湖项目刷新/合并/打开/复制）、账号（一键登录/多账号切换/Cookie 管理/资料展示）、日志（实时滚动查看）。
- **登录方式**：
  - 🚀 **一键登录**：pywebview WebView2 弹窗登录，自动提取 Cookie/localStorage/sessionStorage/前端状态
  - 📥 **浏览器导入**：自动读取本机已安装浏览器的蓝湖 Cookie
  - ✏️ **手动粘贴**：Cookie 摘要显示 + 内存完整值
- **多账号管理**：`%APPDATA%\LanhuMCP\accounts.json` 持久化，当前账号高亮，切换和单独退出，Cookie 指纹合并重复账号。
- **项目合并**：蓝湖 API + 登录缓存提取 + 手动保存，三路合并按 `team_id + project_id` 去重，支持搜索过滤和最近打开。
- **AI 工具配置**：一键识别安装路径/PATH 命令，按 MCP 客户端格式直接写入 JSON/YAML/TOML 配置文件。
- **视觉体验**：现代化卡片、指标块、装饰线条、侧栏呼吸状态条、页面切换进度线、hover 颜色过渡；Canvas 滚动容器适配小窗口。

![总览页](assets/banner-overview.png)
![服务页](assets/banner-service.png)
![AI 工具页](assets/banner-ai.png)
![项目页](assets/banner-projects.png)
![账号页](assets/banner-accounts.png)
![日志页](assets/banner-logs.png)

## 🚀 快速开始

> ⚠️ **重要提示：必须使用支持视觉功能的AI模型！**
>
> 本项目需要AI模型具备**图像识别和分析能力**，推荐使用以下2026年主流视觉模型：
> - 🤖 **Claude** (Anthropic)
> - 🌟 **GPT** (OpenAI)
> - 💎 **Gemini** (Google)
> - 🚀 **Kimi** (月之暗面)
> - 🎯 **Qwen** (阿里巴巴)
> - 🧠 **DeepSeek** (深度求索)
>
> 不支持纯文本模型（如 GPT-3.5、Claude Instant 等）

---

> 💡 **小白用户？** 直接对 AI 说 "帮我克隆并安装 https://github.com/dsphper/lanhu-mcp 项目"，AI 会引导你完成所有步骤！

### 方式一：让 AI 帮你安装（推荐！！！）

直接在对 AI 说：
```
"帮我克隆并安装 https://github.com/dsphper/lanhu-mcp 项目"
```

AI 会自动完成：克隆项目 → 安装依赖 → 引导获取 Cookie → 配置并启动服务

📖 参考文档：[AI 安装指南](ai-install-guide.md) • [Cookie 获取教程](GET-COOKIE-TUTORIAL.md)

---

### 方式二：手动安装

**2.1 Windows 桌面版（推荐给非开发用户）**

发布包提供单文件 `LanhuMCP.exe`（~85MB，PyInstaller onefile 打包）：

```powershell
# 默认打开 Tkinter 桌面工作台（总览/服务/AI工具/项目/账号/日志 六页导航）
.\LanhuMCP.exe

# 需要作为 MCP HTTP 服务运行时（前台常驻，监听 0.0.0.0:PORT/mcp）
.\LanhuMCP.exe --server

# 登录辅助子进程（通常由 GUI 内部调用）
.\LanhuMCP.exe --login-helper
```

桌面工作台会引导完成蓝湖登录、项目选择、服务启动和 AI 工具配置。本地打包与三分支验证见 [PACKAGING.md](PACKAGING.md)。

**2.2 Docker 部署（推荐给服务器环境）**

优点：环境隔离、一键部署、易于管理

```bash
# 1. 克隆项目
git clone https://github.com/dsphper/lanhu-mcp.git
cd lanhu-mcp

# 2. 配置环境（会引导你输入 Cookie）
bash setup-env.sh        # Linux/Mac
# 或
setup-env.bat           # Windows

# 3. 启动服务
docker-compose up -d
```

> 💡 `setup-env.sh` 会交互式引导你获取并配置蓝湖 Cookie，自动生成 `.env` 文件

📖 详细文档：[Docker 部署指南](DEPLOY.md)

**2.3 源码运行**

前置要求：Python 3.10+

```bash
# 1. 克隆项目
git clone https://github.com/dsphper/lanhu-mcp.git
cd lanhu-mcp

# 2. 一键安装（推荐，会引导你配置 Cookie）
bash easy-install.sh        # Linux/Mac
# 或
easy-install.bat           # Windows
```

> 💡 `easy-install.sh` 会自动安装依赖、引导获取 Cookie 并配置环境

<details>
<summary>或者手动安装（不推荐）</summary>

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 手动配置（见下方"配置"部分）
```
</details>

### 配置（源码运行需要）

1. **设置蓝湖 Cookie**（必需）

```bash
export LANHU_COOKIE="your_lanhu_cookie_here"
```

> 💡 获取 Cookie：登录蓝湖网页版，打开浏览器开发者工具，从请求头中复制 Cookie

2. **配置飞书机器人**（可选）

**方式一：环境变量（推荐，支持 Docker）**
```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-url"
```

**方式二：修改代码**
在 `lanhu_mcp_server.py` 中修改：
```python
DEFAULT_FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-url"
```

3. **配置用户信息映射**（可选）

更新 `FEISHU_USER_ID_MAP` 字典以支持 @提醒功能。

4. **其他环境变量**（可选）

```bash
# 服务器配置
export SERVER_HOST="0.0.0.0"       # 服务器监听地址
export SERVER_PORT=8000            # 服务器端口

# 数据存储
export DATA_DIR="./data"           # 数据存储目录

# 性能调优
export HTTP_TIMEOUT=30             # HTTP请求超时时间（秒）
export VIEWPORT_WIDTH=1920         # 浏览器视口宽度
export VIEWPORT_HEIGHT=1080        # 浏览器视口高度

# 调试选项
export DEBUG="false"               # 调试模式（true/false）
```

> 📝 完整环境变量说明请参考 `config.example.env` 文件

### 运行服务

**桌面工作台源码运行：**
```bash
python lanhu_mcp_gui.py          # 入口一：独立 Tkinter 脚本
# 或
python -m lanhu_mcp.gui          # 入口二：包模式（pyproject.toml console_scripts: lanhu-mcp-gui）
```

**MCP 服务源码运行：**
```bash
python lanhu_mcp_server.py       # 入口一：独立脚本
# 或
python -m lanhu_mcp.runtime      # 入口二：包模式（pyproject.toml console_scripts: lanhu-mcp）
```

**登录辅助源码运行（供 GUI 内部子进程调用）：**
```bash
python lanhu_login_helper.py     # 独立登录 helper
```

**按需启动（stdio，本地 MCP 客户端推荐）：**
```bash
./run-stdio.sh
```

`run-stdio.sh` 会自动进入项目目录、读取 `.env`，并以 stdio 方式启动 MCP 服务。适合 Cursor、Claude Code 等支持 `command` / `args` 配置的客户端按需拉起服务，无需手动常驻启动 HTTP 服务。

**Docker 运行：**
```bash
docker-compose up -d              # 启动
docker-compose logs -f            # 查看日志
docker-compose down              # 停止
```

服务器将在 `http://localhost:8000/mcp` 启动

### 连接到 AI 客户端

在支持 MCP 的 AI 客户端（如 Claude Code、Cursor、Windsurf）中配置：

**Claude Code 配置示例：**
```json
{
  "mcpServers": {
    "lanhu": {
      "type": "http",
      "url": "http://localhost:8000/mcp?role=Developer&name=YourName"
    }
  }
}
```

**Cursor / Windsurf 等其他客户端配置示例：**
```json
{
  "mcpServers": {
    "lanhu": {
      "url": "http://localhost:8000/mcp?role=Developer&name=YourName"
    }
  }
}
```

**按需启动配置示例（无需提前启动服务）：**
```json
{
  "mcpServers": {
    "lanhu": {
      "command": "/bin/bash",
      "args": [
        "<ABSOLUTE_PATH_TO_LANHU_MCP>/run-stdio.sh"
      ],
      "env": {
        "LANHU_USER_NAME": "YourName",
        "LANHU_USER_ROLE": "Developer"
      }
    }
  }
}
```

请将 `<ABSOLUTE_PATH_TO_LANHU_MCP>` 替换为本机 `lanhu-mcp` 项目的绝对路径；macOS/Linux 下可在项目目录执行 `pwd` 获取。

> 📌 URL 参数说明：
> - `role`: 用户角色（Developer/Frontend/Backend/Tester/Product 等）
> - `name`: 用户姓名（用于协作追踪和 @提醒）
> - ⚠️ **注意**：部分 AI 开发工具不支持 URL 中使用中文参数值，建议使用英文

> 📌 stdio 环境变量说明：
> - `LANHU_USER_ROLE`: 用户角色（Developer/Frontend/Backend/Tester/Product 等）
> - `LANHU_USER_NAME`: 用户姓名（用于协作追踪和 @提醒）

## 🎯 提升 UI 还原度

开启蓝湖的**设计稿转代码**功能可以显著提升 UI 还原度。如果遇到提示无法转换的问题，需要让 UI 设计师升级蓝湖插件版本后重新上传设计稿。

---

## ✨保持关注

给我们点个 Star，你将能第一时间从 GitHub 收到所有新版本的发布通知！
<img width="900" alt="Screenshot 2025-06-02 at 3 03 49 PM" src="https://github.com/user-attachments/assets/1c9a3661-80a4-4fba-a30f-f469898b0aec" />
## 📖 使用指南

### 需求文档分析工作流

**1. 获取页面列表**
```
请帮我用mcp看看这个需求文档：
https://lanhuapp.com/web/#/item/project/product?tid=xxx&pid=xxx&docId=xxx
```

**2. AI 自动执行四阶段分析**
- ✅ STAGE 1: 全局文本扫描，建立整体认知
- ✅ STAGE 2: 分组详细分析（根据选择的模式）
- ✅ STAGE 3: 反向验证，确保零遗漏
- ✅ STAGE 4: 生成交付文档（需求文档/测试计划/评审PPT）

**3. 获取交付物**
- 开发视角：详细需求文档 + 全局业务流程图
- 测试视角：测试计划 + 测试用例清单 + 字段校验表
- 快速探索：评审文档 + 模块依赖图 + 讨论要点

### UI 设计稿查看

```
请帮我用mcp看看这个设计稿：
https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx
```

分析结果包含设计图预览、详细参数（尺寸/间距/颜色/字体等）以及转换后的 HTML+CSS 代码，便于还原实现。

### 切图下载

```
帮我用mcp下载"首页设计"的所有切图
```

AI 会自动：
1. 检测项目类型（React/Vue/Flutter 等）
2. 选择合适的输出目录
3. 生成语义化文件名
4. 批量下载切图

### 团队留言

**发布留言：**
```
@张三 @李四 这个登录页面的密码校验规则需要确认一下
```

**查看留言：**
```
查看所有 @我的消息
```

**筛选查询：**
```
查看所有关于"测试"的知识库类型留言
```

## 🛠️ 可用工具列表（共 35 个，按功能分组）

### 📋 需求与原型（5 个）

| 工具名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| `lanhu_resolve_invite_link` | 解析蓝湖邀请/分享链接 | 用户提供分享链接时，提取 tid/pid |
| `lanhu_list_product_documents` | 列出产品文档（原型/需求文档） | 项目下有多个需求文档时，先获取文档清单 |
| `lanhu_get_pages` | 获取原型页面列表 | 分析需求文档前必调用，建立页面树 |
| `lanhu_get_ai_analyze_page_result` | AI 分析原型页面内容 | 提取需求细节、业务逻辑、字段规则 |
| `lanhu_extract_interactions` | 提取 Axure 交互事件 | 获取按钮点击、跳转、校验等交互规格 |

### 🎨 UI 设计（5 个）

| 工具名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| `lanhu_get_designs` | 获取 UI 设计图列表 | 查看设计稿前必调用，获取设计图名称/索引 |
| `lanhu_get_ai_analyze_design_result` | AI 分析 UI 设计图 | 获取设计参数（尺寸/间距/颜色/字体）+ HTML+CSS 参考 |
| `lanhu_get_design_slices` | 获取切图信息 | 查询设计稿切图清单（名称/尺寸/URL） |
| `lanhu_batch_download_slices` | 批量下载切图 | 一键下载所有切图并生成语义化文件名 |
| `lanhu_batch_download_assets` | 分类批量下载资源 | 按 PNG/JPG/SVG/字体等分类，生成资源清单 |

### 🏗️ 高还原开发（15 个）

| 工具名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| `lanhu_extract_design_system` | 提取完整设计系统 | 色板、字体、间距、圆角、阴影、CSS 变量 |
| `lanhu_get_layout_spec` | 提取布局规格 | 栅格、容器、对齐方式、断点、响应式规则 |
| `lanhu_extract_component_patterns` | 识别组件模式 | 按钮/表单/卡片/导航等组件复用模式与变体 |
| `lanhu_design_qa` | 设计质量检查 | 一致性检查、间距对齐、字体规范化、对比度 |
| `lanhu_compare_designs` | 设计版本对比 | 两版设计稿差异高亮，变更点清单 |
| `lanhu_generate_framework_code` | 框架代码生成 | React/Vue/Svelte/Flutter/HTML 多框架输出 |
| `lanhu_extract_svg` | SVG 资源提取 | 导出所有矢量图层为独立 SVG |
| `lanhu_measure_elements` | 全图元素测量 | 每个元素的 x/y/w/h、间距、字体、颜色精确值 |
| `lanhu_extract_animation_specs` | 动效规格提取 | 过渡时间、缓动曲线、触发条件、动画参数 |
| `lanhu_get_export_options` | 导出选项查询 | 支持的导出格式、倍率、切图命名规则 |
| `lanhu_get_responsive_variants` | 响应式变体提取 | 移动端/平板/桌面多尺寸设计差异 |
| `lanhu_get_design_annotations` | 设计标注提取 | 蓝湖设计图上所有文字标注与说明 |
| `lanhu_get_version_history` | 版本历史提取 | 设计稿迭代记录、更新人、更新时间 |

### 💻 代码生成 IR（4 个）

| 工具名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| `lanhu_generate_code` | 基于设计 IR 生成代码 | 设计中间表示 → React/Vue/Svelte 代码 |
| `lanhu_analyze_semantic` | 语义层分析 | 组件语义化识别（Header/Nav/Section/Footer 等） |
| `lanhu_analyze_interaction` | 交互层分析 | 状态机、事件绑定、数据流转识别 |
| `lanhu_preview_ir` | 预览设计 IR | 查看中间表示结构，调试代码生成 |

### 💬 协作与留言板（6 个）

| 工具名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| `lanhu_say` | 发布留言/知识库 | 团队协作、@提醒、知识沉淀（knowledge/task/question/urgent/normal） |
| `lanhu_say_list` | 查看留言列表 | 按项目/类型/关键词筛选，支持正则搜索 |
| `lanhu_say_detail` | 查看留言详情 | 查看完整内容、回复、元数据 |
| `lanhu_say_edit` | 编辑留言 | 修改已发布消息 |
| `lanhu_say_delete` | 删除留言 | 移除消息 |
| `lanhu_get_members` | 查看协作者/访问记录 | 查看团队成员、AI 访问历史、首次/最近访问时间 |

### 🩺 系统（1 个）

| 工具名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| `lanhu_health_check` | MCP 服务健康检查 | 连通性、版本、账号状态、工具数量探测 |
## 🎯 团队留言板：突破 AI 协作的最后一公里

### 为什么需要团队留言板？

在 AI 编程时代，每个开发者都有自己的 AI 助手（Cursor、Windsurf、Claude Code）。但这带来了一个**严重的问题**：

```
🤔 痛点场景：
┌─────────────────────────────────────────────┐
│ 后端小王的 AI：                              │
│ "我已经分析完登录接口的需求，字段校验规则   │
│  都很清楚了，开始写代码..."                  │
└─────────────────────────────────────────────┘
                  ❌ 上下文断层
┌─────────────────────────────────────────────┐
│ 测试小李的 AI：                              │
│ "什么？登录接口？让我重新看一遍需求文档...   │
│  这些字段规则是什么意思？边界值怎么测？"     │
└─────────────────────────────────────────────┘
```

**每个 AI 都在重复工作，无法复用其他 AI 的分析成果！**

### 团队留言板如何解决？

**设计理念：让所有 AI 助手连接同一个"大脑"**

```
          ┌─────────────────────────────┐
          │   Lanhu MCP Server          │
          │   (统一知识中枢)             │
          │                             │
          │  📊 需求分析结果             │
          │  🐛 开发踩坑记录             │
          │  📋 测试用例模板             │
          │  💡 技术决策文档             │
          └──────────┬──────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
   ┌────▼───┐   ┌───▼────┐   ┌──▼─────┐
   │后端 AI │   │前端 AI │   │测试 AI │
   │(小王)  │   │(小张)  │   │(小李)  │
   └────────┘   └────────┘   └────────┘
     Cursor      Windsurf     Claude
```

### 核心使用场景

#### 场景 1：需求分析结果共享

**后端 AI（小王）分析完需求后：**
```
@测试小李 @前端小张 我已经分析完"用户登录"需求，关键信息：
- 手机号必填，11位数字
- 密码6-20位，必须包含字母+数字
- 验证码4位纯数字，5分钟有效
- 错误3次锁定30分钟

[消息类型：knowledge]
```

**测试 AI（小李）查询时：**
```
AI: 查询所有关于"登录"的知识库消息
→ 立即获取小王 AI 的分析结果，无需重新看需求！
```

#### 场景 2：开发踩坑记录

**后端 AI（小王）遇到坑：**
```
【知识库】Redis连接超时问题已解决

问题：生产环境 Redis 频繁超时
原因：连接池配置不当，maxIdle 设置过小
解决：调整为 maxTotal=20, maxIdle=10

[消息类型：knowledge]
```

**其他开发 AI 遇到相同问题：**
```
AI: 搜索"Redis 超时"相关的知识库
→ 找到解决方案，避免重复踩坑！
```

#### 场景 3：跨角色任务协作

**产品 AI 发起查询任务：**
```
@后端小王 请帮我查一下数据库中 user 表有多少条测试数据？

[消息类型：task]  // ⚠️ 安全限制：只能查询，不能修改
```

**后端 AI（小王）看到通知：**
```
AI: 有人 @我了，查看详情
→ 执行 SELECT COUNT(*) FROM user WHERE status='test'
→ 回复留言：共有 1234 条测试数据
```

#### 场景 4：紧急问题广播

**运维 AI 发现生产问题：**
```
🚨 紧急：生产环境支付接口异常，请立即排查！

时间：2026-01-15 14:30
现象：支付成功率从 99% 降至 60%
影响：约 200 笔订单受影响

@所有人

[消息类型：urgent]
→ 自动发送飞书通知给所有人
```

### 消息类型设计

| 类型 | 用途 | 搜索策略 | 生命周期 |
|------|------|----------|----------|
| 📢 **normal** | 普通通知 | 按时间衰减 | 7天后归档 |
| 📋 **task** | 查询任务（安全限制：只读） | 完成后归档 | 任务生命周期 |
| ❓ **question** | 需要回答的问题 | 未回答置顶 | 解答后归档 |
| 🚨 **urgent** | 紧急通知 | 强制推送 | 24小时后降级 |
| 💡 **knowledge** | **知识库（核心）** | **永久可搜索** | **永久保存** |

### 安全机制

**任务类型（task）的安全限制：**
```python
✅ 允许的查询操作：
- 查询代码位置、代码逻辑
- 查询数据库表结构、数据
- 查询测试方法、覆盖率
- 查询 TODO、注释

❌ 禁止的危险操作：
- 修改代码
- 删除文件
- 执行命令
- 提交代码
```

### 搜索和过滤

**智能搜索（防止上下文溢出）：**
```python
# 场景 1：查询所有测试相关的知识库
lanhu_say_list(
    url='all',  # 全局搜索
    filter_type='knowledge',
    search_regex='测试|test|单元测试',
    limit=20
)

# 场景 2：查询某个项目的紧急消息
lanhu_say_list(
    url='项目URL',
    filter_type='urgent',
    limit=10
)

# 场景 3：查找未解决的问题
lanhu_say_list(
    url='all',
    filter_type='question',
    search_regex='待解决|pending'
)
```

### 协作者追踪

**自动记录团队成员访问历史：**
```python
lanhu_get_members(url='项目URL')

返回结果：
{
  "collaborators": [
    {
      "name": "小王",
      "role": "后端",
      "first_seen": "2026-01-10 09:00:00",
      "last_seen": "2026-01-15 16:30:00"
    },
    {
      "name": "小李",
      "role": "测试",
      "first_seen": "2026-01-12 10:00:00",
      "last_seen": "2026-01-15 14:00:00"
    }
  ]
}

💡 用途：
- 了解哪些同事的 AI 看过这个需求
- 发现潜在的协作伙伴
- 团队透明化
```

### 飞书通知集成

**打通 AI 协作与人工沟通：**

```python
# AI 自动发送飞书通知（当 @某人时）
lanhu_say(
    url='项目URL',
    summary='需要你帮忙review代码',
    content='登录模块的密码加密逻辑，麻烦看一下',
    mentions=['小王', '小张']  # 必须是真实姓名
)

# 飞书群收到：
┌──────────────────────────────────┐
│ 📢 蓝湖协作通知                   │
│                                  │
│ 👤 发布者：小李（测试）           │
│ 📨 提醒：@小王 @小张              │
│ 🏷️ 类型：normal                  │
│ 📁 项目：用户中心改版             │
│ 📄 文档：登录注册模块             │
│                                  │
│ 📝 内容：                        │
│ 登录模块的密码加密逻辑，麻烦看一下 │
│                                  │
│ 🔗 查看需求文档                   │
└──────────────────────────────────┘
```

### 技术优势

1. **零学习成本**：AI 自动处理，开发者只需自然对话
2. **实时同步**：所有 AI 助手连接同一数据源
3. **全局搜索**：跨项目查询知识库
4. **版本关联**：留言自动关联文档版本号
5. **元数据完整**：自动记录项目、文档、作者等10个标准字段
6. **智能过滤**：支持正则搜索、类型筛选、数量限制（防止 token 溢出）

---


## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         AI 客户端层                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Cursor   │  │ Windsurf │  │  Claude  │  │   ...    │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │             │              │             │              │
│       └─────────────┴──────────────┴─────────────┘              │
└───────────────────────────┬─────────────────────────────────────┘
                            │ MCP Protocol (HTTP)
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Lanhu MCP Server                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              FastMCP 服务框架                           │    │
│  │  ┌──────────┐  ┌──────────┐  ┌───────────────────┐   │    │
│  │  │ Tool API │  │ Resource │  │  Context Provider  │   │    │
│  │  └────┬─────┘  └────┬─────┘  └─────────┬─────────┘   │    │
│  └───────┼─────────────┼──────────────────┼─────────────┘    │
│          │             │                  │                    │
│  ┌───────▼─────────────▼──────────────────▼─────────────┐    │
│  │              核心业务逻辑层                            │    │
│  │                                                        │    │
│  │  ┌─────────────────┐  ┌──────────────────────────┐  │    │
│  │  │  需求文档分析   │  │  团队协作留言板          │  │    │
│  │  │                 │  │                          │  │    │
│  │  │ • 页面提取      │  │ • 消息存储管理           │  │    │
│  │  │ • 内容分析      │  │ • 类型分类(5种)         │  │    │
│  │  │ • 智能缓存      │  │ • @提醒功能             │  │    │
│  │  │ • 三种模式      │  │ • 搜索筛选               │  │    │
│  │  └────────┬────────┘  └──────────┬───────────────┘  │    │
│  │           │                      │                   │    │
│  │  ┌────────▼──────────┐  ┌───────▼──────────────┐   │    │
│  │  │  UI设计支持       │  │  协作者追踪          │   │    │
│  │  │                   │  │                      │   │    │
│  │  │ • 设计图下载      │  │ • 访问记录            │   │    │
│  │  │ • 切图提取        │  │ • 团队透明            │   │    │
│  │  │ • 智能命名        │  │ • 元数据关联          │   │    │
│  │  └───────────────────┘  └──────────────────────┘   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              数据存储层                                 │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │  │
│  │  │ 留言数据    │  │ 资源缓存    │  │ 截图缓存     │  │  │
│  │  │ (JSON)      │  │ (Files)     │  │ (PNG)        │  │  │
│  │  └─────────────┘  └─────────────┘  └──────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└────────────────┬─────────────────────┬────────────────────────┘
                 │                     │
                 │                     │ 飞书通知
                 │                     ▼
                 │            ┌─────────────────┐
                 │            │  Feishu Webhook │
                 │            └─────────────────┘
                 │
                 │ HTTP/JSON API
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      蓝湖平台 API                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ 文档元数据   │  │ Axure资源    │  │ UI设计图&切图        │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 数据流图

```
用户请求 → AI客户端 → MCP协议
              ↓
         Tool调用
              ↓
    ┌─────────┴─────────┐
    │                   │
检查缓存          提取元数据
    │                   │
命中？              关联版本号
    │                   │
  是/否            记录协作者
    │                   │
    ├─是→返回缓存        │
    │                   │
    └─否→调用蓝湖API ←──┘
              ↓
         下载资源
              ↓
         处理转换
              ↓
         保存缓存
              ↓
         返回结果
              ↓
      AI客户端展示
```

## 📁 项目结构

```
lanhu-mcp/
├── lanhu_mcp_server.py          # MCP 主服务入口（legacy 单文件，含 16 个基础工具）
├── lanhu_mcp_gui.py             # Tkinter GUI 入口（独立脚本）
├── lanhu_login_helper.py        # 登录辅助子进程（pywebview WebView2 弹窗）
├── pyproject.toml               # 项目配置（setuptools / ruff / mypy / pytest / coverage / bandit）
├── requirements.txt              # Python 依赖清单
├── LanhuMCP-onefile.spec        # PyInstaller onefile 打包 spec（生产使用）
├── LanhuMCP.spec / LanhuMCP-GUI.spec / LanhuMCP-CLI.spec  # 其他打包配置
├── hook_*.py                    # PyInstaller 自定义 hooks（Tkinter / FastMCP / Flet 依赖）
├── build_onefile.bat / build.bat / build_full.bat  # Windows 打包脚本
├── Dockerfile                    # Docker 镜像
├── docker-compose.yml            # Docker Compose 配置
├── config.example.env            # 配置文件示例
├── quickstart.sh / quickstart.bat   # 快速启动脚本
├── easy-install.sh / easy-install.bat  # 一键安装脚本
├── setup-env.sh / setup-env.bat       # 环境配置脚本
├── run-stdio.sh                  # 按需 stdio 启动脚本（Cursor/Claude Code 等）
├── .env.example                  # 环境变量示例
├── .gitignore                    # Git 忽略文件
├── LICENSE                       # MIT 许可证
├── README.md                     # 中文文档（本文件）
├── README_EN.md                  # 英文文档
├── CONTRIBUTING.md               # 贡献指南
├── CHANGELOG.md                  # 更新日志
├── PACKAGING.md                  # 打包与验证文档
├── DEPLOY.md                     # Docker 部署指南
├── GET-COOKIE-TUTORIAL.md        # Cookie 获取教程
├── ai-install-guide.md           # AI 安装指南
├── SECURITY.md                   # 安全策略
├── CODE_OF_CONDUCT.md            # 行为准则
├── DEMO.md / RELEASE_NOTES_v1.0.0.md  # 演示与发布说明
├── assets/                       # 静态资源
│   ├── banner-overview.png       # 总览页截图
│   ├── banner-service.png        # 服务页截图
│   ├── banner-ai.png             # AI 工具页截图
│   ├── banner-projects.png       # 项目页截图
│   ├── banner-accounts.png       # 账号页截图
│   ├── banner-logs.png           # 日志页截图
│   ├── banner-shared.png         # 共享用 banner
│   ├── lanhu_mcp_logo.png        # Logo（大）
│   ├── lanhu_mcp_logo_256.png    # Logo（256px）
│   ├── lanhu_mcp.ico             # 程序图标
│   ├── lanhu_mcp_status_idle.ico/png   # 空闲状态图标
│   └── lanhu_mcp_status_running.ico/png # 运行中状态图标
├── images/
│   └── wechat.jpg                # 微信群二维码
├── lanhu_mcp/                    # 核心包（模块化拆分）
│   ├── __init__.py
│   ├── runtime.py                # 包模式 MCP 运行时入口
│   ├── server.py                 # 高还原设计扩展工具（15 个新工具注册）
│   ├── core/                     # 核心领域
│   │   ├── accounts.py           # 多账号管理（APPDATA 持久化、指纹去重）
│   │   ├── avatar.py             # 头像下载与缓存
│   │   ├── cache.py              # 基于版本号的智能缓存
│   │   ├── cleanup.py            # 资源清理
│   │   ├── config.py             # 环境变量与配置
│   │   ├── errors.py             # 错误类型
│   │   ├── messages.py           # 留言板数据层
│   │   ├── paths.py              # 路径常量（APPDATA/data/logs）
│   │   ├── project_types.py      # 项目类型与归一化
│   │   ├── projects.py           # 项目三路合并与去重
│   │   └── user.py               # 用户资料解析（Cookie/JWT/接口）
│   ├── gui/                      # Tkinter GUI 包（与 lanhu_mcp_gui.py 对应）
│   │   ├── __main__.py           # python -m lanhu_mcp.gui 入口
│   │   ├── app.py                # 主窗口与六页导航
│   │   ├── state.py              # GUI 共享状态
│   │   ├── theme.py              # 现代化主题与样式
│   │   ├── branding.py           # 品牌与顶部统计区
│   │   ├── tray.py               # 系统托盘
│   │   ├── floating.py           # 悬浮状态指示器
│   │   ├── components/widgets.py # 自定义控件（卡片/指标块/图标）
│   │   └── pages/                # 六个页面
│   │       ├── overview.py       # 总览页
│   │       ├── service.py        # 服务页
│   │       ├── ide_tools.py      # AI 工具配置页
│   │       ├── projects.py       # 项目页
│   │       ├── accounts.py       # 账号页
│   │       └── logs.py           # 日志页
│   ├── services/                 # 业务服务
│   │   ├── lanhu_api.py          # 蓝湖 Web API 封装（多路候选端点）
│   │   ├── browser_login.py      # 浏览器 Cookie 读取（browser-cookie3）
│   │   ├── login_helper.py       # 登录 helper 子进程封装
│   │   ├── service_manager.py    # 内置 MCP 服务启停
│   │   ├── ide_config.py         # 20+ AI 工具识别与配置写入
│   │   └── tools_registry.py     # AST 扫描工具发现与缓存
│   ├── tools/                    # 高还原设计工具实现
│   │   ├── design_system.py      # 设计系统提取
│   │   ├── layout_spec.py        # 布局规格提取
│   │   ├── components.py         # 组件模式识别
│   │   ├── quality_check.py      # 设计 QA
│   │   ├── compare.py            # 版本对比
│   │   ├── code_gen.py           # 多框架代码生成（轻量版）
│   │   ├── batch_download.py     # 资源分类下载
│   │   ├── interactions.py       # Axure 交互提取
│   │   ├── annotations.py        # 设计标注提取
│   │   ├── version_history.py    # 版本历史提取
│   │   ├── svg_extract.py        # SVG 提取
│   │   ├── measurements.py       # 元素测量
│   │   ├── animation.py          # 动效规格
│   │   ├── export_options.py     # 导出选项
│   │   └── responsive.py         # 响应式变体
│   ├── codegen/                  # IR 代码生成引擎（强化版）
│   │   ├── mcp_tools.py          # 4 个 IR 工具注册
│   │   ├── ir.py                 # 中间表示定义
│   │   ├── pipeline.py           # 设计 → IR → 代码流水线
│   │   ├── semantic.py           # 语义层分析
│   │   ├── interaction.py        # 交互层分析
│   │   ├── style_system.py       # 样式系统
│   │   ├── fidelity_check.py     # 还原度自检
│   │   ├── incremental_gen.py    # 增量代码生成
│   │   ├── project_scaffolder.py # 工程脚手架
│   │   ├── dependency_detector.py # 依赖探测
│   │   └── frameworks/           # 多框架后端
│   │       ├── html_gen.py       # HTML/CSS
│   │       ├── react_gen.py      # React
│   │       ├── vue_gen.py        # Vue
│   │       ├── svelte_gen.py     # Svelte
│   │       └── flutter_gen.py    # Flutter
│   ├── converters/               # 格式转换器
│   ├── prompts/                  # AI Prompt 模板
│   └── utils/                    # 通用工具
├── src/                          # 预留 src 布局（兼容其他打包约定）
├── scripts/                      # 辅助脚本
│   ├── print-mcp-config.sh       # 打印 MCP 配置片段（Linux/Mac）
│   └── print-mcp-config.bat      # 打印 MCP 配置片段（Windows）
├── tests/                        # 测试套件（25+ 测试文件）
│   ├── test_basic.py             # 基础冒烟
│   ├── test_account_*.py         # 账号/Cookie/登录
│   ├── test_gui_*.py             # GUI 构造、交互、视觉、优化
│   ├── test_codegen_*.py         # 代码生成注册与冒烟
│   ├── test_messages.py          # 留言板
│   ├── test_*.py                 # 其他功能
│   └── __init__.py
├── data/                         # 数据存储目录（运行时自动创建）
│   ├── messages/                 # 留言板 JSON
│   ├── accounts.json             # 多账号数据（也可能在 %APPDATA%/LanhuMCP）
│   ├── projects.json             # 手动保存项目
│   ├── axure_extract_*/          # Axure 资源缓存
│   └── lanhu_designs/            # 设计稿缓存
└── logs/                         # 日志文件（自动创建）
    └── *.log
```

## 🔧 高级配置

### 自定义角色映射

在代码中修改 `ROLE_MAPPING_RULES` 以支持更多角色：

```python
ROLE_MAPPING_RULES = [
    (["后端", "backend", "server"], "后端"),
    (["前端", "frontend", "web"], "前端"),
    # 添加更多规则...
]
```

### 缓存控制

缓存目录由环境变量 `DATA_DIR` 控制：

```bash
export DATA_DIR="/path/to/cache"
```

### 飞书通知定制

在 `send_feishu_notification()` 函数中定制消息格式和样式。

## 🤖 AI 助手集成

本项目专为 AI 助手设计，内置"二狗"（ErGou）助手人格：

- 🎯 **专业分析**：自动识别文档类型和最佳分析模式
- 📋 **TODO驱动**：基于任务清单的系统化工作流
- 🗣️ **中文交互**：专业的中文对话体验
- ✨ **自动化服务**：无需手动操作，AI 自动完成全流程
- 🔍 **细致严谨**：专注于准确性和质量，提供高质量技术分析
- 📝 **代码质量**：遵循严格的代码标准，避免AI生成代码的常见问题

## 📊 性能指标

- ⚡ 页面截图：~2秒/页（带缓存）
- 💾 资源下载：支持断点续传和增量更新
- 🔄 缓存命中：基于版本号的永久缓存
- 📦 批量处理：支持并发下载和分析

## 🐛 常见问题

<details>
<summary><b>Q: Cookie 过期怎么办？</b></summary>

A: 桌面工作台会提示 Cookie 失效，点击账号页的「一键登录」重新弹窗登录即可；或重新登录蓝湖网页版后，在账号页使用「浏览器导入」自动读取本机 Cookie；也可以手动粘贴新 Cookie 到账号页「手动输入」区。
</details>

<details>
<summary><b>Q: 一键登录窗口一闪而过 / 黑屏？</b></summary>

A: 登录 helper 会忽略蓝湖首页匿名 Cookie，只在检测到有效 auth/token/session 类 Cookie 后才返回成功。请确保在弹窗中完成真实账号登录（手机扫码 / 密码 / SSO）并进入已登录路由。若持续黑屏或 ERR_TIMED_OUT，可改用浏览器登录后通过「浏览器导入」或「手动 Cookie」方式添加账号。
</details>

<details>
<summary><b>Q: 登录成功但项目列表为空？</b></summary>

A: 项目页采用三路合并：蓝湖 API → 登录缓存提取 → 手动保存。前两种方式失败时：
1. 确认该账号在蓝湖中确实已加入团队/项目
2. 在项目页点击「手动添加项目链接」粘贴项目 URL 兜底
3. 查看日志页的失败原因（接口格式变化 / 权限不足 / 网络代理）
</details>

<details>
<summary><b>Q: AI 工具没有出现在识别列表里？</b></summary>

A: AI 工具页会同时扫描固定安装路径和 `PATH` 环境变量。对于命令行式工具（Claude Code / Codex / MimoCode / Gemini CLI 等），请确保可在终端直接执行对应命令；仍不识别可点击配置区的「手动写入」按钮直接写入 ~/.codex/config.toml、~/.claude.json 等配置文件。
</details>

<details>
<summary><b>Q: 截图失败或显示空白？</b></summary>

A: 确保系统已安装 Playwright 浏览器：
```bash
playwright install chromium
```
</details>

<details>
<summary><b>Q: 飞书通知发送失败？</b></summary>

A: 检查：
1. Webhook URL 是否正确
2. 飞书机器人是否已添加到群组
3. 用户 ID 映射是否正确配置
</details>

<details>
<summary><b>Q: 如何清理缓存？</b></summary>

A: 删除 `data/` 目录下的对应缓存文件即可。系统会自动重新下载。
</details>

<details>
<summary><b>Q: PyInstaller 打包后 exe 启动就崩溃？</b></summary>

A: 打包使用 `LanhuMCP-onefile.spec`，它已显式打包 Tkinter/Tcl/Tk 资源、pywebview WebView2 依赖、PIL 隐式依赖。如果仍有问题：
1. 先运行 `python lanhu_mcp_gui.py` 验证源码是否正常
2. 检查 `dist\warn-LanhuMCP.txt` 中的告警（openai/tzdata/pywebview 多平台属于可选依赖，可忽略）
3. 查看 `%APPDATA%\LanhuMCP\logs\` 下的日志文件
</details>

## 🔒 安全说明

- ⚠️ **Cookie 安全**：请勿将含有 Cookie 的配置文件、`accounts.json`、日志文件提交到公开仓库
- 🔐 **访问控制**：MCP HTTP 服务默认监听 `0.0.0.0`，建议在内网环境部署或配置防火墙规则；仅本地使用可改为 `127.0.0.1`
- 📝 **数据隐私**：留言、账号、项目、头像数据存储在本地（`data/` 或 `%APPDATA%\LanhuMCP`），请妥善保管
- 🛡️ **任务类型限制**：留言板的 `task` 类型仅用于只读查询提示，不会实际执行任何修改代码或删除文件的操作

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 开发指南

```bash
# 安装开发、GUI 与构建依赖
python -m pip install -e ".[dev,gui,build]"

# 入口语法快速检查（无需 pytest）
python -m py_compile lanhu_mcp_gui.py lanhu_login_helper.py lanhu_mcp_server.py

# 静态检查
python -m ruff check .
python -m ruff format --check .
python -m mypy lanhu_mcp

# 运行测试
python -m pytest -q

# 本地 onefile 打包（生产使用的 exe）
python -m PyInstaller LanhuMCP-onefile.spec --clean --noconfirm
# 输出：dist\LanhuMCP.exe（~85MB）

# 打包后快速冒烟验证
.\dist\LanhuMCP.exe --login-helper   # 写入登录结果 JSON
.\dist\LanhuMCP.exe --server         # 启动 HTTP MCP 服务
```

CI 会在 Python 3.10 / 3.11 / 3.12 上执行 ruff、mypy、关键入口 `py_compile` 与 pytest。

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

### 开源项目

- [FastMCP](https://github.com/jlowin/fastmcp) - 优秀的 MCP 服务器框架
- [Playwright](https://playwright.dev/) - 可靠的浏览器自动化工具
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML 解析利器
- [HTTPx](https://www.python-httpx.org/) - 现代化的异步 HTTP 客户端

### 服务平台

- [蓝湖](https://lanhuapp.com/) - 提供优质的设计协作平台
- [飞书](https://www.feishu.cn/) - 提供企业协作和机器人通知

### 贡献者

感谢所有为这个项目做出贡献的开发者！

<!-- ALL-CONTRIBUTORS-LIST:START -->
<!-- 这里将自动生成贡献者列表 -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

### 特别感谢

- 所有提交 Issue 和 PR 的贡献者
- 所有在生产环境使用并提供反馈的团队
- 所有帮助改进文档的朋友

## 📮 联系方式

- 提交 Issue: [GitHub Issues](https://github.com/dsphper/lanhu-mcp/issues)
- 邮件: dsphper@gmail.com
<p align="center"><img src="images/wechat.jpg?v=20260415" alt="微信群二维码" width="400" /></p>

## 🗺️ 路线图

- [ ] 支持更多设计平台（Figma、Sketch）
- [ ] Web 管理界面
- [ ] 更多分析维度（前后端工时估算、技术栈推荐）
- [ ] 支持企业级权限管理
- [ ] API 文档自动生成
- [ ] 国际化支持

---

<p align="center">
  如果这个项目对你有帮助，请给它一个 ⭐️
</p>

<p align="center">
  Made with ❤️ by the Lanhu MCP Team
</p>

---
## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=dsphper/lanhu-mcp&type=date&legend=top-left)](https://www.star-history.com/#dsphper/lanhu-mcp&type=date&legend=top-left)

---

## 🏷️ 标签 Tags

`lanhumcp` `蓝湖mcp` `lanhu-mcp` `蓝湖AI` `蓝湖skills` `lanhu-skills` `cursor-skills` `agent-skills` `lanhu-ai` `mcp-server` `cursor-plugin` `windsurf-integration` `claude-integration` `openclaw-integration` `clawbot-integration` `axure-automation` `requirement-analysis` `design-collaboration` `ai-development-tools` `model-context-protocol` `蓝湖插件` `蓝湖API` `OpenClaw` `ClawBot` `AI助手` `AI编程` `智能协作` `AI需求分析` `设计协作` `前端开发工具` `后端开发工具`

---

## 🔍 常见搜索问题 FAQ Search

- **如何让 Cursor AI 读取蓝湖需求文档？** → 使用 Lanhu MCP Server
- **Windsurf 怎么连接蓝湖？** → 配置本 MCP 服务器
- **Claude Code 如何分析 Axure 原型？** → 通过 Lanhu MCP 集成
- **OpenClaw 如何连接蓝湖？** → 直接配置 Lanhu MCP Server
- **ClawBot 怎么读取蓝湖设计稿？** → 本 MCP 服务器已原生支持
- **蓝湖有 API 吗？** → 本项目提供 MCP 协议接口
- **如何自动提取蓝湖切图？** → 使用本项目的切图工具
- **AI 如何自动生成测试用例？** → 使用测试分析模式
- **How to integrate Lanhu with Cursor?** → Install Lanhu MCP Server
- **Lanhu API for AI tools?** → Use this MCP server
- **OpenClaw Lanhu integration?** → Supported out of box
- **ClawBot design collaboration?** → Use Lanhu MCP Server
- **Automated Axure analysis?** → Use this project

## 🔍 SEO 关键词索引

**中文关键词**: 蓝湖mcp | lanhumcp | 蓝湖AI | 蓝湖skills | 蓝湖Skill | Cursor Skills 蓝湖 | Agent Skills 蓝湖 | 蓝湖插件 | 蓝湖API | 蓝湖Cursor | 蓝湖Windsurf | 蓝湖Claude | 蓝湖OpenClaw | 蓝湖ClawBot | OpenClaw | ClawBot | OpenClaw集成 | ClawBot集成 | AI助手 | 蓝湖需求文档 | 蓝湖Axure | 蓝湖切图 | 蓝湖设计稿 | AI需求分析 | AI测试用例 | MCP服务器 | 模型上下文协议

**English Keywords**: lanhu mcp | lanhu-mcp | lanhu ai | lanhu skills | cursor skills lanhu | agent skills lanhu | lanhu cursor | lanhu windsurf | lanhu claude | lanhu api | lanhu integration | lanhu openclaw | lanhu clawbot | openclaw mcp | clawbot mcp | mcp server | model context protocol | axure automation | design collaboration | requirement analysis | ai development tools

**适用人群**: 产品经理 | 前端开发 | 后端开发 | 测试工程师 | UI设计师 | 使用Cursor的开发者 | 使用Windsurf的开发者 | 使用Claude的开发者 | AI编程爱好者

---
## ⚠️ 免责声明

本项目（Lanhu MCP Server）是一个**第三方开源项目**，由社区开发者独立开发和维护，**并非蓝湖官方产品**。

**重要说明：**
- 本项目与蓝湖公司无任何官方关联或合作关系
- 本项目通过公开的网页接口与蓝湖平台交互，不涉及任何未授权访问
- 使用本项目需要您拥有合法的蓝湖账号和访问权限
- 请遵守蓝湖平台的服务条款和使用政策
- 本项目仅供学习和研究使用，使用者需自行承担使用风险
- 开发者不对因使用本项目导致的任何数据丢失、账号问题或其他损失承担责任

**数据和隐私：**
- 本项目在本地处理和缓存数据，不会向第三方服务器传输您的数据
- 您的蓝湖 Cookie 和项目数据仅存储在您的本地环境中
- 请妥善保管您的凭证信息，不要分享给他人

**开源协议：**
- 本项目采用 MIT 开源协议，按"原样"提供，不提供任何形式的保证
- 详见 [LICENSE](LICENSE) 文件

如有任何疑问或建议，欢迎通过 [GitHub Issues](https://github.com/dsphper/lanhu-mcp/issues) 与我们交流。

<!-- Last checked: 2026-09-05 08:09 -->
