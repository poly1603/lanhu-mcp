"""服务层：MCP 工具发现、蓝湖 API、IDE 配置写入、服务进程管理。

从 ``lanhu_mcp_gui.py`` 抽取的纯逻辑（无 Tkinter 依赖），供 Tkinter / Flet GUI
以及 CLI 复用。导入本包不会触发 Tkinter / fastmcp / httpx 等重依赖。
"""
