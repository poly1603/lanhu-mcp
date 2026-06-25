"""共享路径、数据目录、日志与运行时探测。

从 ``lanhu_mcp_gui.py`` 抽取的纯逻辑（无 Tkinter 依赖），供 Tkinter / Flet GUI
以及 CLI 复用。仅依赖标准库，可在无第三方依赖的环境中导入与测试。
"""
from __future__ import annotations

import logging
import os
import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

__all__ = [
    "APP_DIR",
    "FROZEN_TEMP_DIR",
    "DATA_DIR",
    "ENV_FILE",
    "COOKIE_FILE",
    "ACCOUNTS_FILE",
    "PROJECTS_FILE",
    "WEBVIEW_STORAGE_DIR",
    "AVATAR_CACHE_DIR",
    "LOG_FILE",
    "DEFAULT_LANHU_LOGIN_URL",
    "AVATAR_MAX_BYTES",
    "ensure_writable_data_dir",
    "flog",
    "is_gui_smoke_mode",
    "should_show_native_error_dialog",
    "first_existing_path",
    "now_text",
    "is_port_in_use",
    "validate_port",
    "find_server_exe",
    "find_server_dir",
    "app_runtime_label",
    "compare_packaged_outputs",
]


# ============================================
# 应用根目录
# ============================================
# 打包后 APP_DIR 指向 exe 所在目录；源码模式指向仓库根目录
# （本文件位于 ``<repo>/lanhu_mcp/core/paths.py``，故向上三级即仓库根）。
if getattr(sys, "frozen", False):
    APP_DIR = Path(os.path.dirname(sys.executable))
else:
    APP_DIR = Path(__file__).resolve().parent.parent.parent

FROZEN_TEMP_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))


def ensure_writable_data_dir() -> Path:
    """选择并创建可写的数据目录。"""
    candidates = [
        Path(os.environ.get("APPDATA", "~")) / "LanhuMCP",
        Path(os.environ.get("LOCALAPPDATA", "~")) / "LanhuMCP",
        APP_DIR / "data",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe_file = candidate / ".write-test"
            probe_file.write_text("ok", encoding="utf-8")
            probe_file.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    return APP_DIR


DATA_DIR = ensure_writable_data_dir()
ENV_FILE = DATA_DIR / ".env"
COOKIE_FILE = DATA_DIR / "cookie.txt"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
PROJECTS_FILE = DATA_DIR / "projects.json"
WEBVIEW_STORAGE_DIR = DATA_DIR / "webview"
AVATAR_CACHE_DIR = DATA_DIR / "avatars"
LOG_FILE = DATA_DIR / "app.log"
DEFAULT_LANHU_LOGIN_URL = "https://lanhuapp.com/web/"
AVATAR_MAX_BYTES = 1024 * 1024


# ============================================
# 文件日志（所有操作记录到文件）
# ============================================
_logger = logging.getLogger("LanhuMCP")
_logger.setLevel(logging.DEBUG)
if not _logger.handlers:
    try:
        _log_handler: logging.Handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    except OSError:
        # 日志文件被占用或无权限时，不能阻断主程序启动。
        _log_handler = logging.StreamHandler(sys.stderr)
    _log_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    _logger.addHandler(_log_handler)


def flog(msg: str, level: str = "info") -> None:
    """写日志到文件 + 控制台。"""
    getattr(_logger, level, _logger.info)(msg)
    print(f"[{level.upper()}] {msg}")


def is_gui_smoke_mode() -> bool:
    """判断当前是否处于 GUI 自动化烟测模式。"""
    return os.environ.get("LANHU_GUI_SMOKE_CLOSE") == "1"


def should_show_native_error_dialog() -> bool:
    """判断 GUI 启动失败时是否允许弹出阻塞式系统错误框。"""
    return not is_gui_smoke_mode()


def first_existing_path(candidates: list[Path]) -> Optional[Path]:
    """从候选路径中返回第一个存在的路径。"""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def now_text() -> str:
    """返回用于账号记录的当前时间字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================
# 端口与服务定位
# ============================================
def is_port_in_use(port: int) -> bool:
    if not (1 <= port <= 65535):
        return True  # 非法端口视为占用
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("localhost", port)) == 0


def validate_port(port_str: str) -> tuple[bool, int, str]:
    """校验端口，返回 (valid:bool, port:int, error:str)。

    valid=True 表示端口格式合法（未检查是否被占用）。
    """
    try:
        p = int(port_str)
        if not (1 <= p <= 65535):
            return False, 0, f"端口范围: 1-65535，当前值: {p}"
        return True, p, ""
    except ValueError:
        return False, 0, "端口必须是数字"


def find_server_exe() -> Optional[Path]:
    """在多个位置查找 server exe。"""
    candidates = [
        APP_DIR / "lanhu_mcp.exe",
        APP_DIR / "dist" / "lanhu_mcp.exe",
        APP_DIR / "dist" / "lanhu_mcp" / "lanhu_mcp.exe",
        APP_DIR / "lanhu_mcp_server.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def find_server_dir() -> Optional[Path]:
    exe = find_server_exe()
    return exe.parent if exe else None


def app_runtime_label() -> str:
    """返回当前程序启动来源，帮助定位是否打开了旧版 exe。"""
    executable_path = (
        Path(sys.executable).resolve() if getattr(sys, "frozen", False) else Path(sys.argv[0]).resolve()
    )
    try:
        modified_text = datetime.fromtimestamp(executable_path.stat().st_mtime).strftime("%m-%d %H:%M")
    except OSError:
        modified_text = "未知时间"
    mode_text = "打包版" if getattr(sys, "frozen", False) else "源码版"
    return f"{mode_text} · {modified_text} · {executable_path}"


def compare_packaged_outputs() -> str:
    """比较 dist 与 dist2 输出，减少用户误开旧文件的排障成本。"""
    root_dir = APP_DIR.parent if APP_DIR.name.lower() in {"dist", "dist2"} else APP_DIR
    primary = root_dir / "dist" / "LanhuMCP.exe"
    secondary = root_dir / "dist2" / "LanhuMCP.exe"
    if not primary.exists() or not secondary.exists():
        return ""
    try:
        primary_time = primary.stat().st_mtime
        secondary_time = secondary.stat().st_mtime
    except OSError:
        return ""
    if abs(primary_time - secondary_time) < 2:
        return "dist 与 dist2 已同步"
    if secondary_time < primary_time:
        return "注意: dist2\\LanhuMCP.exe 比 dist 旧，请使用最新 dist 或重新同步。"
    return "注意: dist 与 dist2 时间不同，请确认当前打开的是最新构建。"
