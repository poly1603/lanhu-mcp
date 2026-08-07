"""服务层：MCP 工具发现、蓝湖 API、IDE 配置写入、服务进程管理。

从核心模块抽取的纯逻辑（无界面依赖），供 Flet GUI
以及 CLI 复用。导入本包不会触发 fastmcp / httpx 等重依赖。
"""
