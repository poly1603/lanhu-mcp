"""
Lanhu MCP Server - 管理面板 v5 (优化版)

优化内容：
1. 现代化UI设计 - 自定义配色、圆角风格、视觉层次清晰
2. 修复Cookie截断保存Bug
3. 修复服务启动/停止逻辑
4. 增加端口范围校验和DPI感知
5. 完善异常处理和线程安全
6. MCP配置代码动态跟随端口号
7. 改进IDE检测路径
8. 增加日志级别分类显示
"""
import os
import sys
import json
import ast
import base64
import time
import socket
import threading
import subprocess
import webbrowser
import traceback
import hashlib
import shutil
import re
import ctypes
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import quote, unquote, urlencode, urlparse

# ============================================
# DPI 感知（高分屏适配）
# ============================================
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# 路径配置
if getattr(sys, 'frozen', False):
    APP_DIR = Path(os.path.dirname(sys.executable))
else:
    APP_DIR = Path(__file__).parent

FROZEN_TEMP_DIR = Path(getattr(sys, '_MEIPASS', APP_DIR))


def ensure_writable_data_dir() -> Path:
    """选择并创建可写的数据目录。"""
    candidates = [
        Path(os.environ.get('APPDATA', '~')) / 'LanhuMCP',
        Path(os.environ.get('LOCALAPPDATA', '~')) / 'LanhuMCP',
        APP_DIR / 'data',
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe_file = candidate / '.write-test'
            probe_file.write_text('ok', encoding='utf-8')
            probe_file.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    return APP_DIR


DATA_DIR = ensure_writable_data_dir()
ENV_FILE = DATA_DIR / '.env'
COOKIE_FILE = DATA_DIR / 'cookie.txt'
ACCOUNTS_FILE = DATA_DIR / 'accounts.json'
PROJECTS_FILE = DATA_DIR / 'projects.json'
WEBVIEW_STORAGE_DIR = DATA_DIR / 'webview'
AVATAR_CACHE_DIR = DATA_DIR / 'avatars'
LOG_FILE = DATA_DIR / 'app.log'
DEFAULT_LANHU_LOGIN_URL = 'https://lanhuapp.com/web/'
AVATAR_MAX_BYTES = 1024 * 1024

# ============================================
# 文件日志（所有操作记录到文件）
# ============================================
import logging

_logger = logging.getLogger('LanhuMCP')
_logger.setLevel(logging.DEBUG)
try:
    _log_handler = logging.FileHandler(str(LOG_FILE), encoding='utf-8')
except OSError:
    # 日志文件被占用或无权限时，不能阻断主程序启动。
    _log_handler = logging.StreamHandler(sys.stderr)
_log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
_logger.addHandler(_log_handler)

def flog(msg: str, level: str = 'info') -> None:
    """写日志到文件 + 控制台"""
    getattr(_logger, level, _logger.info)(msg)
    print(f"[{level.upper()}] {msg}")


def is_gui_smoke_mode() -> bool:
    """判断当前是否处于 GUI 自动化烟测模式。"""
    return os.environ.get("LANHU_GUI_SMOKE_CLOSE") == "1"


def should_show_native_error_dialog() -> bool:
    """判断 GUI 启动失败时是否允许弹出阻塞式系统错误框。"""
    return not is_gui_smoke_mode()


flog(f"=== LanhuMCP GUI 启动 ===")
flog(f"APP_DIR: {APP_DIR}")
flog(f"DATA_DIR: {DATA_DIR}")
flog(f"LOG_FILE: {LOG_FILE}")
flog(f"sys.executable: {sys.executable}")
flog(f"sys.frozen: {getattr(sys, 'frozen', False)}")
flog(f"sys.version: {sys.version}")
if getattr(sys, 'frozen', False):
    flog(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")


def _first_existing_path(candidates: list[Path]) -> Optional[Path]:
    """从候选路径中返回第一个存在的路径。"""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def bootstrap_tcl_tk_runtime() -> None:
    """在导入 Tkinter 前修复 Tcl/Tk 初始化路径。"""
    if sys.platform != 'win32':
        return

    python_base = Path(getattr(sys, 'base_prefix', sys.prefix))
    dll_dir = _first_existing_path([
        FROZEN_TEMP_DIR,
        APP_DIR,
        python_base / 'DLLs',
    ])
    if dll_dir:
        try:
            os.add_dll_directory(str(dll_dir))
        except (AttributeError, OSError):
            pass

    tcl_dll = _first_existing_path([
        FROZEN_TEMP_DIR / 'tcl86t.dll',
        APP_DIR / 'tcl86t.dll',
        python_base / 'DLLs' / 'tcl86t.dll',
    ])
    if tcl_dll:
        try:
            # Python 嵌入式和 PyInstaller 环境下需要先告知 Tcl 宿主 exe。
            tcl = ctypes.CDLL(str(tcl_dll))
            tcl.Tcl_FindExecutable.argtypes = [ctypes.c_wchar_p]
            tcl.Tcl_FindExecutable(sys.executable)
        except Exception as error:
            flog(f"Tcl/Tk 初始化补丁失败: {error}", 'warning')

    tcl_dir = _first_existing_path([
        FROZEN_TEMP_DIR / '_tcl_data',
        APP_DIR / '_tcl_data',
        python_base / 'tcl' / 'tcl8.6',
    ])
    tk_dir = _first_existing_path([
        FROZEN_TEMP_DIR / '_tk_data',
        APP_DIR / '_tk_data',
        python_base / 'tcl' / 'tk8.6',
    ])

    if tcl_dir:
        os.environ['TCL_LIBRARY'] = str(tcl_dir)
    if tk_dir:
        os.environ['TK_LIBRARY'] = str(tk_dir)

# ============================================
# 现代配色方案 + 设计Token
# ============================================

# ============================================
# TDesign 风格设计令牌
# ============================================

# 颜色系统 - TDesign 调色板
COLORS = {
    # 背景色
    'bg': '#F5F7FA',           # 主背景 - TDesign 浅灰
    'sidebar': '#00112E',      # 侧边栏背景 - TDesign 深蓝黑
    'sidebar_hover': '#0A1E3D', # 侧边栏悬停
    'sidebar_active': '#0F2A4A', # 侧边栏选中
    'sidebar_text': '#E8EDF4',  # 侧边栏文字
    'card': '#FFFFFF',          # 卡片背景
    'card_hover': '#F8F9FB',    # 卡片悬停
    'surface': '#F5F7FA',       # 表面背景
    'surface_hover': '#EDF0F5', # 表面悬停
    'input_bg': '#FFFFFF',      # 输入框背景
    'input_bg_disabled': '#F5F7FA', # 输入框禁用

    # 主色调 - TDesign Blue
    'primary': '#0052D9',       # TDesign 品牌蓝
    'primary_hover': '#0045B5', # 主色悬停
    'primary_active': '#003A99', # 主色点击
    'primary_light': '#E8F0FF', # 主色浅色背景
    'primary_light_hover': '#D0E0FF', # 主色浅色悬停

    # 语义色
    'success': '#00A870',       # 成功绿 - TDesign
    'success_hover': '#009966', # 成功悬停
    'danger': '#E34D59',        # 错误红 - TDesign
    'danger_hover': '#CD2E3A',  # 错误悬停
    'warning': '#ED7B2F',       # 警告橙 - TDesign
    'warning_hover': '#D96A20', # 警告悬停
    'accent': '#00809A',        # 强调青
    'accent_light': '#E3F5F8',  # 强调浅色
    'accent_warm': '#F59D0A',   # 温暖琥珀
    'accent_warm_light': '#FEF3CD', # 温暖浅色

    # 文字色 - TDesign 中性色
    'text_primary': '#1A2332',  # 主文字
    'text_secondary': '#5B6B7F', # 次要文字
    'text_muted': '#8C9BAC',    # 弱化文字
    'text_disabled': '#BFC9D6', # 禁用文字
    'text_on_primary': '#FFFFFF', # 主色背景上的文字
    'text_on_dark': '#E8EDF4',  # 深色背景上的文字

    # 边框色
    'border': '#DDE1E8',        # 默认边框
    'border_light': '#EBEEF3',  # 浅边框
    'border_hover': '#C4CBD6',  # 悬停边框
    'border_focus': '#0052D9',  # 焦点边框
    'border_error': '#E34D59',  # 错误边框

    # 日志背景
    'log_bg': '#0D1117',        # 日志背景
    'log_text': '#E2E8F0',      # 日志文字

    # 阴影色
    'shadow_sm': '#F0F2F5',
    'shadow_md': '#E4E8ED',
    'shadow_lg': '#D0D5DD',
    'shadow_color': 'rgba(0, 0, 0, 0.06)',
    'shadow_color_hover': 'rgba(0, 0, 0, 0.10)',

    # 焦点环
    'focus_ring': 'rgba(0, 82, 217, 0.25)',
}

# 间距系统 (4px基准, TDesign 规范)
SPACING = {
    '0': 0,
    '1': 4,
    '2': 8,
    '3': 12,
    '4': 16,
    '5': 20,
    '6': 24,
    '8': 32,
    '10': 40,
    '12': 48,
}

# 圆角系统 - TDesign 规范
RADIUS = {
    'none': 0,
    'sm': 2,
    'md': 4,
    'lg': 6,
    'xl': 8,
    '2xl': 12,
    'full': 9999,
}

# 阴影系统
SHADOW = {
    'none': {'offset': 0, 'blur': 0, 'color': 'transparent'},
    'sm': {'offset': 1, 'blur': 2, 'color': COLORS['shadow_sm']},
    'md': {'offset': 2, 'blur': 6, 'color': COLORS['shadow_md']},
    'lg': {'offset': 4, 'blur': 12, 'color': COLORS['shadow_lg']},
}

# 字体系统 - TDesign 规范
FONT = {
    'family': 'Segoe UI',
    'mono': 'Cascadia Code',
    'sizes': {
        'xs': 8,
        'sm': 9,
        'base': 10,
        'md': 11,
        'lg': 12,
        'xl': 14,
        '2xl': 16,
        '3xl': 18,
        '4xl': 20,
        '5xl': 24,
    },
    'weights': {
        'normal': 'normal',
        'medium': 'normal',
        'semibold': 'bold',
        'bold': 'bold',
    },
}

# 动画时长（毫秒）
ANIMATION = {
    'fast': 100,
    'normal': 200,
    'slow': 300,
}


ANIMATION_INTERVALS = {
    'sidebar_pulse': 180,
    'page_transition': 120,
}


def animation_interval_ms(animation_name: str) -> int:
    """返回指定动画的刷新间隔，集中控制持续动画开销。"""
    return int(ANIMATION_INTERVALS.get(animation_name, ANIMATION['normal']))


def should_run_sidebar_pulse(window_state: str, has_focus: bool) -> bool:
    """判断侧栏呼吸条是否需要继续刷新。"""
    return bool(has_focus and window_state in ("normal", "zoomed"))


def project_rows_signature(projects: list[dict]) -> tuple[tuple[str, ...], ...]:
    """生成项目列表可见字段摘要，用于跳过无变化重渲染。"""
    signature_rows: list[tuple[str, ...]] = []
    for project in projects:
        signature_rows.append((
            str(project.get("id") or ""),
            str(project.get("team_id") or ""),
            str(project.get("name") or ""),
            str(project.get("type") or ""),
            str(project.get("updated_at") or ""),
            str(project.get("team_name") or ""),
            str(project.get("owner_name") or ""),
            str(project.get("source") or ""),
            str(project.get("url") or ""),
        ))
    return tuple(signature_rows)


def account_rows_signature(accounts: list[dict], active_id: str) -> tuple[tuple[str, ...], ...]:
    """生成账号列表可见字段摘要，用于避免重复销毁和创建账号行。"""
    signature_rows: list[tuple[str, ...]] = []
    for account in accounts:
        cookie = str(account.get("cookie") or "")
        fingerprint = str(account.get("cookie_fingerprint") or cookie_fingerprint(cookie) or "")
        account_id = str(account.get("id") or "")
        signature_rows.append((
            account_id,
            "1" if account_id == active_id else "0",
            str(account.get("name") or ""),
            str(account.get("email") or ""),
            str(account.get("mobile") or ""),
            str(account.get("username") or ""),
            str(account.get("nickname") or ""),
            str(account.get("avatar") or ""),
            str(account.get("company") or ""),
            str(account.get("team") or account.get("team_name") or ""),
            str(account.get("role") or ""),
            fingerprint,
            str(len(cookie)),
            str(account.get("updated_at") or ""),
            str(account.get("source_url") or ""),
        ))
    return tuple(signature_rows)


# ============================================
# UI 交互增强函数
# ============================================

def add_button_hover_effect(button, bg_normal=None, bg_hover=None, bg_active=None):
    """为按钮添加 TDesign 风格 hover/active 效果。"""
    import tkinter as tk

    current_style = str(button.cget('style'))

    if bg_normal is None:
        if 'Primary' in current_style:
            bg_normal = COLORS['primary']
            bg_hover = COLORS['primary_hover']
            bg_active = COLORS['primary_active']
        elif 'Success' in current_style:
            bg_normal = COLORS['success']
            bg_hover = COLORS['success_hover']
            bg_active = '#008F65'
        elif 'Danger' in current_style:
            bg_normal = COLORS['danger']
            bg_hover = COLORS['danger_hover']
            bg_active = '#B8323C'
        elif 'Ghost' in current_style:
            bg_normal = 'transparent'
            bg_hover = COLORS['surface_hover']
            bg_active = COLORS['border_light']
        elif 'Small' in current_style:
            bg_normal = COLORS['surface']
            bg_hover = COLORS['surface_hover']
            bg_active = COLORS['border_light']
        else:
            bg_normal = COLORS['card']
            bg_hover = COLORS['primary_light']
            bg_active = COLORS['primary_light_hover']

    def on_enter(event):
        if str(button.cget('state')) != 'disabled':
            button.config(background=bg_hover)

    def on_leave(event):
        if str(button.cget('state')) != 'disabled':
            button.config(background=bg_normal)

    def on_press(event):
        if str(button.cget('state')) != 'disabled':
            button.config(background=bg_active)

    def on_release(event):
        if str(button.cget('state')) != 'disabled':
            button.config(background=bg_hover)

    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)
    button.bind("<ButtonPress>", on_press)
    button.bind("<ButtonRelease>", on_release)


def add_entry_focus_effect(entry, focus_border_color=None):
    """为输入框添加 TDesign 风格 focus 效果。"""
    import tkinter as tk

    if focus_border_color is None:
        focus_border_color = COLORS['border_focus']

    def on_focus_in(event):
        entry.config(highlightbackground=focus_border_color, highlightthickness=2)

    def on_focus_out(event):
        entry.config(highlightbackground=COLORS['border'], highlightthickness=1)

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)


# ============================================
# 工具函数
# ============================================

def find_server_exe() -> Optional[Path]:
    """在多个位置查找server exe"""
    candidates = [
        APP_DIR / 'lanhu_mcp.exe',
        APP_DIR / 'dist' / 'lanhu_mcp.exe',
        APP_DIR / 'dist' / 'lanhu_mcp' / 'lanhu_mcp.exe',
        APP_DIR / 'lanhu_mcp_server.exe',
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def app_runtime_label() -> str:
    """返回当前程序启动来源，帮助定位是否打开了旧版 exe。"""
    executable_path = Path(sys.executable).resolve() if getattr(sys, 'frozen', False) else Path(__file__).resolve()
    try:
        modified_text = datetime.fromtimestamp(executable_path.stat().st_mtime).strftime("%m-%d %H:%M")
    except OSError:
        modified_text = "未知时间"
    mode_text = "打包版" if getattr(sys, 'frozen', False) else "源码版"
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


def find_server_dir() -> Optional[Path]:
    exe = find_server_exe()
    return exe.parent if exe else None


def find_server_script() -> Optional[Path]:
    """查找源码模式下可直接运行的 MCP 服务脚本。"""
    candidates = [
        APP_DIR / 'lanhu_mcp_server.py',
        Path(__file__).with_name('lanhu_mcp_server.py'),
    ]
    return _first_existing_path(candidates)


def build_server_start_command() -> tuple[list[str], Path, str]:
    """构造服务启动命令，打包后优先复用当前 exe 的内置服务分支。"""
    if getattr(sys, 'frozen', False):
        # 单文件打包后没有独立服务 exe，直接拉起自身的 --server 分支。
        return [sys.executable, '--server'], APP_DIR, '内置服务'

    gui_script = Path(__file__).resolve()
    if gui_script.exists():
        # 源码开发时也走同一个 --server 分支，确保扩展 MCP 工具被加载。
        return [sys.executable, str(gui_script), '--server'], gui_script.parent, '源码内置服务'

    server_script = find_server_script()
    if server_script:
        # 源码开发时直接运行服务脚本，方便当前代码改动立即生效。
        return [sys.executable, str(server_script)], server_script.parent, '源码服务'

    server_exe = find_server_exe()
    if server_exe:
        # 兼容旧版独立服务端 exe 的部署方式。
        return [str(server_exe)], server_exe.parent, '独立服务端'

    raise FileNotFoundError(
        "未找到可启动的 MCP 服务。\n"
        "已检查: 内置服务分支、lanhu_mcp_server.py、lanhu_mcp.exe、lanhu_mcp_server.exe。"
    )


def is_port_in_use(port: int) -> bool:
    if not (1 <= port <= 65535):
        return True  # 非法端口视为占用
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(('localhost', port)) == 0


def validate_port(port_str: str) -> tuple[bool, int, str]:
    """校验端口，返回 (valid:bool, port:int, error:str)
    valid=True 表示端口格式合法（未检查是否被占用）"""
    try:
        p = int(port_str)
        if not (1 <= p <= 65535):
            return False, 0, f"端口范围: 1-65535，当前值: {p}"
        return True, p, ""
    except ValueError:
        return False, 0, "端口必须是数字"


def now_text() -> str:
    """返回用于账号记录的当前时间字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def cookie_fingerprint(cookie: str) -> str:
    """根据Cookie生成稳定账号ID，避免保存明文ID依赖。"""
    normalized = (cookie or "").strip()
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def normalize_cookie_value(cookie: object) -> str:
    """把 pywebview 或 document.cookie 返回值统一转换为 Cookie 字符串。"""
    if isinstance(cookie, str):
        return cookie.strip()
    if isinstance(cookie, list):
        parts = []
        for item in cookie:
            if isinstance(item, dict) and item.get("name") and item.get("value") is not None:
                parts.append(f"{item.get('name')}={item.get('value')}")
        return "; ".join(parts)
    if isinstance(cookie, dict):
        parts = []
        for name, value in cookie.items():
            if value is not None:
                parts.append(f"{name}={value}")
        return "; ".join(parts)
    return ""


def parse_cookie_pairs(cookie: str) -> dict[str, str]:
    """把 Cookie 字符串解析成键值映射，便于提取非敏感资料。"""
    pairs: dict[str, str] = {}
    for part in (cookie or "").split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        normalized_name = name.strip()
        if normalized_name:
            pairs[normalized_name] = value.strip()
    return pairs


def decode_jwt_payload(token: str) -> dict:
    """解析 JWT payload；只用于展示资料，不做安全鉴权。"""
    parts = (token or "").split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1].strip()
    if not payload:
        return {}
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(f"{payload}{padding}".encode("utf-8"))
        parsed = json.loads(raw.decode("utf-8", errors="replace"))
    except (ValueError, json.JSONDecodeError, OSError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_cookie_json_value(value: str) -> object:
    """解析 Cookie 中可能 URL 编码或 Base64 编码的 JSON 资料。"""
    candidates = [value, unquote(value or "")]
    stripped = (value or "").strip()
    if stripped and len(stripped) % 4 in (0, 2, 3):
        padding = "=" * (-len(stripped) % 4)
        try:
            decoded = base64.urlsafe_b64decode(f"{stripped}{padding}".encode("utf-8"))
            candidates.append(decoded.decode("utf-8", errors="replace"))
        except (ValueError, OSError):
            pass
    for candidate in candidates:
        parsed = parse_json_object(candidate)
        if isinstance(parsed, (dict, list)):
            return parsed
    return value


def user_info_from_cookie(cookie: str) -> dict:
    """从 Cookie 的 JWT 或用户资料字段里提取可展示账号信息。"""
    candidates: list[dict] = []
    for name, value in parse_cookie_pairs(cookie).items():
        lowered_name = name.lower()
        if any(word in lowered_name for word in ("token", "auth", "jwt")):
            payload = decode_jwt_payload(value)
            if payload:
                candidates.append(payload)
        if any(word in lowered_name for word in ("user", "member", "account", "profile")):
            parsed_value = parse_cookie_json_value(value)
            collect_user_candidates(parsed_value, candidates)
    if not candidates:
        return {}
    user_info = parse_user_payload({"cookie": candidates})
    if user_info.get("name") == "蓝湖用户" and not any(
        user_info.get(key) for key in ("email", "mobile", "username", "avatar", "id")
    ):
        return {}
    if user_info:
        user_info["source_url"] = "Cookie/JWT"
    return user_info


def mask_cookie_value(cookie: str) -> str:
    """生成仅用于界面展示的 Cookie 摘要，避免把密钥长时间明文铺在屏幕上。"""
    normalized = (cookie or "").strip()
    if not normalized:
        return ""
    if len(normalized) <= 32:
        return normalized
    return f"{normalized[:16]}...{normalized[-12:]}"


def get_saved_login_url() -> str:
    """读取用户保存的蓝湖登录地址，默认使用官网 Web 入口。"""
    if not ENV_FILE.exists():
        return DEFAULT_LANHU_LOGIN_URL
    try:
        for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
            if line.startswith('LANHU_LOGIN_URL='):
                value = line.split('=', 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    except OSError:
        return DEFAULT_LANHU_LOGIN_URL
    return DEFAULT_LANHU_LOGIN_URL


def save_login_url(login_url: str) -> None:
    """把登录地址保存到环境文件，方便用户处理网络代理或企业私有入口。"""
    normalized = (login_url or DEFAULT_LANHU_LOGIN_URL).strip()
    if not normalized:
        normalized = DEFAULT_LANHU_LOGIN_URL
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env_content = ENV_FILE.read_text(encoding='utf-8') if ENV_FILE.exists() else ''
    if 'LANHU_LOGIN_URL=' in env_content:
        lines = env_content.split('\n')
        for index, line in enumerate(lines):
            if line.startswith('LANHU_LOGIN_URL='):
                lines[index] = f'LANHU_LOGIN_URL={normalized}'
        env_content = '\n'.join(lines)
    else:
        if env_content and not env_content.endswith('\n'):
            env_content += '\n'
        env_content += f'LANHU_LOGIN_URL={normalized}\n'
    ENV_FILE.write_text(env_content, encoding='utf-8')


USER_CONTAINER_KEYS = (
    "user",
    "userInfo",
    "USER_INFO",
    "currentUser",
    "current_user",
    "loginUser",
    "login_user",
    "member",
    "account",
    "accountInfo",
    "profile",
    "data",
    "result",
    "payload",
    "state",
    "props",
    "initialState",
    "initial_state",
    "currentTeam",
    "current_team",
    "workspace",
    "organization",
)

PROJECT_CONTAINER_KEYS = (
    "project",
    "projectInfo",
    "project_info",
    "currentProject",
    "current_project",
    "projects",
    "projectList",
    "project_list",
    "items",
    "list",
    "records",
    "data",
    "result",
    "teams",
    "team",
    "workspace",
)


def parse_json_object(value: object) -> object:
    """把可能是 JSON 字符串的字段解析成对象。"""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "{[":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def collect_user_candidates(value: object, candidates: list[dict], depth: int = 0) -> None:
    """递归收集登录结果里可能代表用户资料的字典。"""
    if depth > 8:
        return
    parsed = parse_json_object(value)
    if isinstance(parsed, dict):
        candidates.append(parsed)
        for key in USER_CONTAINER_KEYS:
            if key in parsed:
                collect_user_candidates(parsed.get(key), candidates, depth + 1)
        for storage_key in ("storage", "sessionStorage", "localStorage"):
            storage_value = parsed.get(storage_key)
            if isinstance(storage_value, dict):
                for item_value in storage_value.values():
                    collect_user_candidates(item_value, candidates, depth + 1)
        for item_value in parsed.values():
            if isinstance(item_value, (dict, list)):
                collect_user_candidates(item_value, candidates, depth + 1)
        return
    if isinstance(parsed, list):
        for item_value in parsed[:20]:
            collect_user_candidates(item_value, candidates, depth + 1)


def user_candidate_score(candidate: dict) -> int:
    """按字段特征给候选用户资料打分，优先选择真正的用户对象。"""
    score = 0
    for key, value in candidate.items():
        if value in (None, ""):
            continue
        lowered_key = str(key).lower()
        if lowered_key in {
            "id",
            "uid",
            "userid",
            "user_id",
            "memberid",
            "member_id",
            "accountid",
            "account_id",
            "uuid",
        }:
            score += 4
        if lowered_key in {
            "name",
            "nickname",
            "nick",
            "realname",
            "real_name",
            "displayname",
            "display_name",
            "username",
            "user_name",
            "preferred_username",
            "loginname",
            "login_name",
        }:
            score += 3
        if lowered_key in {
            "email",
            "mail",
            "mobile",
            "phone",
            "telephone",
            "avatar",
            "avatarurl",
            "avatar_url",
            "picture",
            "image",
            "headimg",
            "headimgurl",
            "portrait",
        }:
            score += 2
        if lowered_key in {
            "company",
            "companyname",
            "company_name",
            "team",
            "teamname",
            "team_name",
            "rolename",
            "role_name",
            "role",
            "position",
            "department",
            "departmentname",
            "deptname",
        }:
            score += 1
    return score


def merge_user_candidates(candidates: list[dict]) -> dict:
    """把多个候选用户对象合并为一个稳定的资料字典。"""
    merged: dict = {}
    scored_candidates = [
        (user_candidate_score(item), item)
        for item in candidates
    ]
    positive_candidates = [item for score, item in scored_candidates if score > 0]
    sorted_candidates = sorted(positive_candidates, key=user_candidate_score, reverse=True)
    for item in sorted_candidates:
        for key, value in item.items():
            if value in (None, "") or key in merged:
                continue
            merged[key] = value
    return merged


def text_from_detail(value: object) -> str:
    """把嵌套对象里的名称字段转换为适合界面展示的文本。"""
    parsed = parse_json_object(value)
    if parsed in (None, ""):
        return ""
    if isinstance(parsed, dict):
        for key in (
            "name",
            "title",
            "label",
            "nickname",
            "nickName",
            "realName",
            "displayName",
            "userName",
            "teamName",
            "companyName",
            "roleName",
            "departmentName",
            "value",
        ):
            nested_value = parsed.get(key)
            if nested_value not in (None, ""):
                return str(nested_value)
        return ""
    if isinstance(parsed, list):
        parts = [text_from_detail(item) for item in parsed[:3]]
        return "、".join(part for part in parts if part)
    return str(parsed)


def first_detail_value(source: dict, keys: tuple[str, ...]) -> str:
    """按别名顺序读取第一个非空字段。"""
    for key in keys:
        if key in source:
            text = text_from_detail(source.get(key))
            if text:
                return text
    lowered_map = {str(key).lower(): value for key, value in source.items()}
    for key in keys:
        value = lowered_map.get(key.lower())
        text = text_from_detail(value)
        if text:
            return text
    return ""


def merge_identity_info(primary: dict, secondary: dict) -> dict:
    """合并两份账号资料，优先保留 primary 里的非空字段。"""
    merged = dict(secondary or {})
    for key, value in (primary or {}).items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def parse_user_payload(user_payload: object) -> dict:
    """从蓝湖 localStorage 结果中提取尽量稳定的用户信息。"""
    payload = parse_json_object(user_payload)
    candidates: list[dict] = []
    collect_user_candidates(payload, candidates)
    positive_candidates = [
        item for item in candidates
        if user_candidate_score(item) > 0
    ]
    sorted_candidates = sorted(positive_candidates, key=user_candidate_score, reverse=True)
    primary = sorted_candidates[0] if sorted_candidates else {}
    merged = merge_user_candidates(candidates)

    def read_identity(keys: tuple[str, ...]) -> str:
        """优先从最高分用户对象读取字段，再回退到合并资料。"""
        return first_detail_value(primary, keys) or first_detail_value(merged, keys)

    name = (
        read_identity((
            "name",
            "nickname",
            "nickName",
            "nick",
            "realName",
            "real_name",
            "displayName",
            "display_name",
            "fullName",
            "full_name",
            "username",
            "userName",
            "preferred_username",
            "loginName",
            "login_name",
        ))
        or read_identity(("mobile", "phone", "email", "mail"))
        or "蓝湖用户"
    )
    email = read_identity(("email", "mail", "emailAddress", "email_address"))
    mobile = read_identity(("mobile", "phone", "tel", "telephone", "cellphone"))
    username = read_identity(("username", "userName", "preferred_username", "account", "loginName", "login_name"))
    nickname = read_identity(("nickname", "nickName", "nick"))
    user_id = read_identity((
        "id",
        "userId",
        "uid",
        "user_id",
        "memberId",
        "member_id",
        "accountId",
        "account_id",
        "uuid",
        "sub",
        "subject",
    ))
    avatar = read_identity((
        "avatar",
        "avatarUrl",
        "avatar_url",
        "headImg",
        "head_img",
        "headimgurl",
        "portrait",
        "photo",
        "photoUrl",
        "picture",
        "image",
    ))
    company = read_identity((
        "company",
        "companyName",
        "company_name",
        "enterprise",
        "organization",
        "orgName",
        "corpName",
    ))
    team = read_identity((
        "team",
        "teamName",
        "team_name",
        "space",
        "workspace",
        "projectTeam",
        "department",
        "departmentName",
        "deptName",
    ))
    role = read_identity(("role", "roleName", "role_name", "identity", "permission", "position", "jobTitle"))
    source_url = ""
    if isinstance(payload, dict):
        source_url = str(payload.get("url") or payload.get("login_url") or "")

    return {
        "id": str(user_id) if user_id else "",
        "name": str(name),
        "email": str(email) if email else "",
        "mobile": str(mobile) if mobile else "",
        "username": str(username) if username else "",
        "nickname": str(nickname) if nickname else "",
        "avatar": str(avatar) if avatar else "",
        "company": str(company) if company else "",
        "team": str(team) if team else "",
        "role": str(role) if role else "",
        "source_url": source_url,
        "raw": payload,
    }


def read_accounts_data() -> dict:
    """读取多用户账号文件，并兼容文件损坏时的空状态。"""
    if not ACCOUNTS_FILE.exists():
        return {"active_id": "", "accounts": []}
    try:
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"active_id": "", "accounts": []}
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list):
        accounts = []
    return {
        "active_id": str(data.get("active_id", "")),
        "accounts": [item for item in accounts if isinstance(item, dict)],
    }


def write_accounts_data(data: dict) -> None:
    """保存多用户账号文件。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_legacy_cookie() -> dict:
    """把旧版 cookie.txt 迁移成默认账号，确保老用户升级后无需重登。"""
    data = read_accounts_data()
    if data["accounts"] or not COOKIE_FILE.exists():
        return data
    legacy_cookie = COOKIE_FILE.read_text(encoding="utf-8").strip()
    if not legacy_cookie:
        return data
    account_id = cookie_fingerprint(legacy_cookie)
    account = {
        "id": account_id,
        "name": "已登录账号",
        "email": "",
        "mobile": "",
        "company": "",
        "team": "",
        "role": "Developer",
        "cookie": legacy_cookie,
        "cookie_fingerprint": account_id,
        "created_at": now_text(),
        "updated_at": now_text(),
    }
    data = {"active_id": account_id, "accounts": [account]}
    write_accounts_data(data)
    return data


def get_accounts() -> list:
    """返回当前所有蓝湖登录账号。"""
    return migrate_legacy_cookie().get("accounts", [])


def get_active_account() -> Optional[dict]:
    """返回当前选中的蓝湖账号。"""
    data = migrate_legacy_cookie()
    active_id = data.get("active_id", "")
    accounts = data.get("accounts", [])
    for account in accounts:
        if account.get("id") == active_id:
            return account
    return accounts[0] if accounts else None


def set_active_account(account_id: str) -> bool:
    """切换当前蓝湖账号，并同步服务环境文件。"""
    data = migrate_legacy_cookie()
    if not any(account.get("id") == account_id for account in data["accounts"]):
        return False
    data["active_id"] = account_id
    write_accounts_data(data)
    active = get_active_account()
    if active:
        save_cookie(active.get("cookie", ""))
    return True


def upsert_account(cookie: object, user_info: Optional[dict] = None) -> Optional[dict]:
    """新增或更新蓝湖账号，并自动设为当前账号。"""
    cookie = normalize_cookie_value(cookie)
    if not cookie:
        return None
    cookie_user_info = user_info_from_cookie(cookie)
    provided_user_info = dict(user_info or {})
    if provided_user_info.get("name") == "蓝湖用户" and cookie_user_info.get("name"):
        provided_user_info.pop("name", None)
    user_info = merge_identity_info(provided_user_info, cookie_user_info)
    fallback_id = cookie_fingerprint(cookie)
    account_id = str(user_info.get("id") or fallback_id)
    data = migrate_legacy_cookie()
    accounts = data["accounts"]
    existing = next(
        (
            item for item in accounts
            if item.get("id") == account_id or item.get("cookie_fingerprint") == fallback_id
        ),
        None,
    )
    account = existing or {"id": account_id, "created_at": now_text()}
    account["id"] = account_id
    account.update({
        "name": user_info.get("name") or account.get("name") or "蓝湖用户",
        "email": user_info.get("email") or account.get("email") or "",
        "mobile": user_info.get("mobile") or account.get("mobile") or "",
        "username": user_info.get("username") or account.get("username") or "",
        "nickname": user_info.get("nickname") or account.get("nickname") or "",
        "avatar": user_info.get("avatar") or account.get("avatar") or "",
        "company": user_info.get("company") or account.get("company") or "",
        "team": user_info.get("team") or account.get("team") or "",
        "role": user_info.get("role") or account.get("role") or "Developer",
        "source_url": user_info.get("source_url") or account.get("source_url") or "",
        "raw": user_info.get("raw") or account.get("raw") or {},
        "cookie": cookie,
        "cookie_fingerprint": fallback_id,
        "updated_at": now_text(),
    })
    if existing is None:
        accounts.append(account)
    data["active_id"] = account_id
    write_accounts_data(data)
    save_cookie(cookie)
    return account


def remove_account(account_id: str) -> Optional[dict]:
    """退出指定蓝湖账号。"""
    data = migrate_legacy_cookie()
    accounts = [account for account in data["accounts"] if account.get("id") != account_id]
    data["accounts"] = accounts
    if data.get("active_id") == account_id:
        data["active_id"] = accounts[0].get("id", "") if accounts else ""
    write_accounts_data(data)
    active = get_active_account()
    if active:
        save_cookie(active.get("cookie", ""))
    else:
        save_cookie("")
    return active


def load_cookie() -> str:
    """加载完整Cookie（不截断）"""
    active = get_active_account()
    if active and active.get("cookie"):
        return active.get("cookie", "").strip()
    if COOKIE_FILE.exists():
        return COOKIE_FILE.read_text(encoding='utf-8').strip()
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('LANHU_COOKIE='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


def save_cookie(cookie: str) -> None:
    """保存完整Cookie"""
    cookie = (cookie or "").strip()
    if cookie:
        COOKIE_FILE.write_text(cookie, encoding='utf-8')
    elif COOKIE_FILE.exists():
        COOKIE_FILE.write_text("", encoding='utf-8')
    # 确保DATA_DIR存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env_content = ''
    if ENV_FILE.exists():
        env_content = ENV_FILE.read_text(encoding='utf-8')
    if 'LANHU_COOKIE=' in env_content:
        lines = env_content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('LANHU_COOKIE='):
                lines[i] = f'LANHU_COOKIE={cookie}'
        env_content = '\n'.join(lines)
    elif cookie:
        if env_content and not env_content.endswith('\n'):
            env_content += '\n'
        env_content += f'LANHU_COOKIE={cookie}\n'
    ENV_FILE.write_text(env_content, encoding='utf-8')


def active_user_query_suffix() -> str:
    """生成 MCP URL 上的当前用户查询参数。"""
    active = get_active_account()
    if not active:
        return ""
    name = quote(active.get("name") or "LanhuUser")
    role = quote(active.get("role") or "Developer")
    return f"?role={role}&name={name}"


def current_mcp_url(port: int) -> str:
    """生成当前端口和当前用户身份对应的 MCP 地址。"""
    return f"http://localhost:{port}/mcp{active_user_query_suffix()}"


def account_primary_contact(account: dict) -> str:
    """返回账号最适合展示的联系方式。"""
    return (
        str(account.get("email") or "")
        or str(account.get("mobile") or "")
        or str(account.get("username") or "")
        or "未读取联系方式"
    )


def account_detail_line(account: dict) -> str:
    """生成账号详细资料行，避免界面重复拼接。"""
    parts = [
        f"ID {account.get('id') or '-'}",
        f"联系 {account_primary_contact(account)}",
        f"用户名 {account.get('username') or account.get('nickname') or '未读取到'}",
    ]
    if account.get("company"):
        parts.append(f"公司 {account.get('company')}")
    if account.get("team"):
        parts.append(f"团队 {account.get('team')}")
    if account.get("role"):
        parts.append(f"角色 {account.get('role')}")
    return "  |  ".join(parts)


def account_profile_line(account: dict) -> str:
    """生成账号个人资料补充行。"""
    avatar = str(account.get("avatar") or "")
    avatar_text = "已读取" if avatar else "未读取到"
    if avatar and len(avatar) > 44:
        avatar_text = f"{avatar[:28]}...{avatar[-12:]}"
    return (
        f"邮箱 {account.get('email') or '未读取到'}  |  "
        f"手机号 {account.get('mobile') or '未读取到'}  |  "
        f"头像 {avatar_text}"
    )


def account_cookie_line(account: dict) -> str:
    """生成账号 Cookie 和来源摘要，不展示完整 Cookie。"""
    cookie = str(account.get("cookie") or "")
    fingerprint = str(account.get("cookie_fingerprint") or cookie_fingerprint(cookie) or "-")
    parts = [
        f"Cookie {len(cookie)} 字符",
        f"指纹 {fingerprint}",
        f"更新 {account.get('updated_at', '-')}",
    ]
    if account.get("source_url"):
        parts.append(f"来源 {account.get('source_url')}")
    return "  |  ".join(parts)


def avatar_cache_path(account: dict) -> Path:
    """生成账号头像缓存路径。"""
    avatar = str(account.get("avatar") or "")
    account_id = str(account.get("id") or cookie_fingerprint(str(account.get("cookie") or "")) or "account")
    suffix = Path(urlparse(avatar).path).suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".gif"):
        suffix = ".png"
    return AVATAR_CACHE_DIR / f"{account_id}{suffix}"


def download_avatar(account: dict) -> Optional[Path]:
    """下载账号头像到本地缓存，失败时返回 None。"""
    avatar = str(account.get("avatar") or "").strip()
    if not avatar.startswith(("http://", "https://")):
        return None
    cache_path = avatar_cache_path(account)
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path
    try:
        AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(avatar, headers={"User-Agent": "Mozilla/5.0 LanhuMCP Desktop"})
        with urllib.request.urlopen(request, timeout=10) as response:
            content_length = int(response.headers.get("Content-Length") or "0")
            if content_length > AVATAR_MAX_BYTES:
                flog(f"头像文件超过缓存上限，已跳过: {content_length} bytes", "warning")
                return None
            content = response.read(AVATAR_MAX_BYTES + 1)
        if content and len(content) <= AVATAR_MAX_BYTES:
            cache_path.write_bytes(content)
            return cache_path
        if len(content) > AVATAR_MAX_BYTES:
            flog(f"头像文件超过缓存上限，已跳过: {len(content)} bytes", "warning")
    except (OSError, ValueError, urllib.error.URLError, TimeoutError):
        return None
    return None


# ============================================
# MCP 方法与项目数据
# ============================================

TOOL_DESCRIPTIONS = {
    "lanhu_resolve_invite_link": "解析蓝湖邀请链接",
    "lanhu_list_product_documents": "列出项目 PRD/原型文档",
    "lanhu_get_pages": "获取 PRD/原型页面列表",
    "lanhu_get_ai_analyze_page_result": "分析 PRD/原型页面并生成开发/测试视角结果",
    "lanhu_get_designs": "获取 UI 设计图列表",
    "lanhu_get_ai_analyze_design_result": "分析 UI 设计图并输出视觉与代码规格",
    "lanhu_get_design_slices": "获取设计切图、图标和素材",
    "lanhu_say": "给项目留言/通知团队",
    "lanhu_say_list": "查看留言列表",
    "lanhu_say_detail": "查看留言详情",
    "lanhu_say_edit": "编辑留言",
    "lanhu_say_delete": "删除留言",
    "lanhu_get_members": "查看项目协作者",
    "lanhu_extract_design_system": "提取颜色、字体、间距等设计系统",
    "lanhu_get_layout_spec": "提取布局结构、尺寸和间距规格",
    "lanhu_extract_component_patterns": "识别可复用组件、按钮、卡片和表单模式",
    "lanhu_design_qa": "检查设计一致性、对比度和质量问题",
    "lanhu_compare_designs": "对比设计版本和变更点",
    "lanhu_generate_framework_code": "按 React/Vue/Flutter 等框架生成还原代码",
    "lanhu_batch_download_assets": "批量下载设计资源和切图",
    "lanhu_extract_interactions": "提取交互、点击区域和表单规则",
    "lanhu_get_design_annotations": "读取设计评论和标注",
    "lanhu_get_version_history": "查看设计版本历史",
    "lanhu_extract_svg": "提取 SVG/矢量图形",
    "lanhu_measure_elements": "测量元素尺寸、距离和位置",
    "lanhu_extract_animation_specs": "提取动效、过渡和微交互规格",
    "lanhu_get_export_options": "读取导出格式和切图配置",
    "lanhu_get_responsive_variants": "分析响应式、多设备和断点适配",
}

TOOL_GROUPS = {
    "需求与原型": (
        "lanhu_resolve_invite_link",
        "lanhu_list_product_documents",
        "lanhu_get_pages",
        "lanhu_get_ai_analyze_page_result",
        "lanhu_extract_interactions",
    ),
    "UI 设计": (
        "lanhu_get_designs",
        "lanhu_get_ai_analyze_design_result",
        "lanhu_get_design_slices",
        "lanhu_get_design_annotations",
        "lanhu_get_version_history",
    ),
    "高还原开发": (
        "lanhu_extract_design_system",
        "lanhu_get_layout_spec",
        "lanhu_extract_component_patterns",
        "lanhu_design_qa",
        "lanhu_compare_designs",
        "lanhu_generate_framework_code",
        "lanhu_batch_download_assets",
        "lanhu_extract_svg",
        "lanhu_measure_elements",
        "lanhu_extract_animation_specs",
        "lanhu_get_export_options",
        "lanhu_get_responsive_variants",
    ),
    "协作": (
        "lanhu_say",
        "lanhu_say_list",
        "lanhu_say_detail",
        "lanhu_say_edit",
        "lanhu_say_delete",
        "lanhu_get_members",
    ),
}

PROJECT_ENDPOINTS = [
    "/api/project/team_projects",
]

USER_PROFILE_ENDPOINTS = [
    "/api/user/info",
    "/api/user/profile",
    "/api/user/current",
    "/api/user/getCurrentUser",
    "/api/user/get_current_user",
    "/api/users/current",
    "/api/member/info",
    "/api/member/current",
    "/api/account/info",
    "/api/account/profile",
    "/api/session",
]

PROJECT_URL_PATTERN = re.compile(
    r"https?://lanhuapp\.(?:com|cn)/web/#/item/project/"
    r"(?:stage|product|detailDetach)[^\s\"'<>，。；、]*"
)
_MCP_TOOLS_CACHE: Optional[list[tuple[str, str]]] = None


def tool_source_candidates() -> list[Path]:
    """返回可能包含 MCP 工具定义的源码文件。"""
    return [
        APP_DIR / 'lanhu_mcp_server.py',
        APP_DIR / 'lanhu_mcp' / 'server.py',
        FROZEN_TEMP_DIR / 'lanhu_mcp_server.py',
        FROZEN_TEMP_DIR / 'lanhu_mcp' / 'server.py',
        Path(__file__).with_name('lanhu_mcp_server.py'),
        Path(__file__).parent / 'lanhu_mcp' / 'server.py',
    ]


def extract_doc_summary(docstring: str) -> str:
    """从工具 docstring 提取第一句可读摘要。"""
    for line in (docstring or "").splitlines():
        text = line.strip().strip("[]")
        if text and not text.startswith("USE THIS WHEN"):
            return text[:80]
    return ""


def scan_mcp_tools_from_file(source_path: Path) -> list[tuple[str, str]]:
    """用 AST 扫描源码中的 @mcp.tool 工具，避免界面方法数量过期。"""
    if not source_path.exists():
        return []
    try:
        tree = ast.parse(source_path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    tools: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(target, ast.Attribute) and target.attr == 'tool':
                summary = TOOL_DESCRIPTIONS.get(node.name) or extract_doc_summary(ast.get_docstring(node) or "")
                tools.append((node.name, summary or "MCP 工具方法"))
                break
    return tools


def discover_mcp_tools(refresh: bool = False) -> list[tuple[str, str]]:
    """发现当前服务支持的全部 MCP 工具。"""
    global _MCP_TOOLS_CACHE
    if _MCP_TOOLS_CACHE is not None and not refresh:
        return list(_MCP_TOOLS_CACHE)
    discovered: dict[str, str] = {}
    for source_path in tool_source_candidates():
        for tool_name, description in scan_mcp_tools_from_file(source_path):
            discovered.setdefault(tool_name, description)
    if not discovered:
        discovered = TOOL_DESCRIPTIONS.copy()
    _MCP_TOOLS_CACHE = sorted(discovered.items(), key=lambda item: tool_sort_key(item[0]))
    return list(_MCP_TOOLS_CACHE)


def tool_sort_key(tool_name: str) -> tuple[int, str]:
    """按业务分组顺序排序工具名。"""
    for index, group_tools in enumerate(TOOL_GROUPS.values()):
        if tool_name in group_tools:
            return index, f"{group_tools.index(tool_name):03d}"
    return len(TOOL_GROUPS), tool_name


def group_mcp_tools(tools: list[tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    """把 MCP 工具按使用场景分组。"""
    grouped = {group_name: [] for group_name in TOOL_GROUPS}
    grouped["其他"] = []
    for tool_name, description in tools:
        target_group = "其他"
        for group_name, group_tools in TOOL_GROUPS.items():
            if tool_name in group_tools:
                target_group = group_name
                break
        grouped[target_group].append((tool_name, description))
    return {name: items for name, items in grouped.items() if items}


MCP_TOOL_NAMES = discover_mcp_tools()


def lanhu_api_headers(cookie: str) -> dict[str, str]:
    """生成访问蓝湖 Web API 的基础请求头。

    蓝湖 Web API 使用 HTTP Basic Auth 认证：
    Authorization: Basic base64(user_token + ":")
    其中 user_token 从 Cookie 中的 user_token 字段提取。
    """
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": DEFAULT_LANHU_LOGIN_URL,
        "real-path": "/item/project/all",
    }
    # 从 Cookie 中提取 user_token，构造 Basic Auth header
    token = ""
    for pair in cookie.split("; "):
        parts = pair.split("=", 1)
        if len(parts) == 2 and parts[0] == "user_token":
            token = parts[1]
            break
    if token:
        basic_auth = base64.b64encode(f"{token}:".encode()).decode()
        headers["Authorization"] = f"Basic {basic_auth}"
    return headers


def read_projects_data() -> dict:
    """读取本地项目缓存，文件损坏时返回空结构。"""
    if not PROJECTS_FILE.exists():
        return {"projects": []}
    try:
        data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"projects": []}
    projects = data.get("projects", [])
    return {"projects": [item for item in projects if isinstance(item, dict)]}


def write_projects_data(data: dict) -> None:
    """保存本地项目缓存。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    projects = data.get("projects", [])
    PROJECTS_FILE.write_text(
        json.dumps({"projects": projects}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_lanhu_project_url(project_url: str) -> Optional[dict]:
    """从蓝湖项目链接中解析 tid、pid、docId 等关键信息。"""
    text = (project_url or "").strip()
    if not text:
        return None
    matched = PROJECT_URL_PATTERN.search(text)
    normalized_url = matched.group(0) if matched else text
    if "lanhuapp." not in normalized_url or "pid=" not in normalized_url:
        return None
    parsed_url = urlparse(normalized_url)
    query_text = parsed_url.query
    if parsed_url.fragment and "?" in parsed_url.fragment:
        query_text = parsed_url.fragment.split("?", 1)[1]
    params = {}
    for part in query_text.split("&"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        params[key] = value
    project_id = params.get("pid") or params.get("project_id")
    if not project_id:
        return None
    team_id = params.get("tid") or params.get("team_id") or ""
    doc_id = params.get("docId") or params.get("doc_id") or params.get("image_id") or ""
    if "/product" in normalized_url:
        project_type = "原型"
    elif "/detailDetach" in normalized_url:
        project_type = "详情"
    else:
        project_type = "设计"
    name = f"蓝湖项目 {project_id}"
    return {
        "id": project_id,
        "team_id": team_id,
        "doc_id": doc_id,
        "name": name,
        "type": project_type,
        "updated_at": now_text(),
        "team_name": "",
        "owner_name": "",
        "url": normalized_url,
        "source": "手动链接",
    }


def save_manual_project(project_url: str, account_id: str = "") -> tuple[bool, str, Optional[dict]]:
    """保存用户手动粘贴的蓝湖项目链接。"""
    project = parse_lanhu_project_url(project_url)
    if not project:
        return False, "请输入包含 tid/pid 的蓝湖项目链接。", None
    project["account_id"] = account_id
    data = read_projects_data()
    projects = data["projects"]
    key = project.get("url") or f"{project.get('team_id')}:{project.get('id')}"
    existing = next(
        (
            item for item in projects
            if (item.get("url") or f"{item.get('team_id')}:{item.get('id')}") == key
        ),
        None,
    )
    if existing:
        existing.update(project)
    else:
        projects.append(project)
    write_projects_data(data)
    return True, "项目链接已保存到本地列表。", project


def cached_projects_for_account(account_id: str = "") -> list[dict]:
    """读取当前账号可见的本地项目缓存。"""
    projects = read_projects_data()["projects"]
    if not account_id:
        return projects
    return [
        project for project in projects
        if not project.get("account_id") or project.get("account_id") == account_id
    ]


def fetch_lanhu_user_profile(cookie: str) -> tuple[bool, str, dict]:
    """尝试用 Cookie 补全蓝湖账号邮箱、头像、用户名等资料。"""
    if not cookie:
        return False, "缺少蓝湖 Cookie，无法读取用户资料。", {}
    errors: list[str] = []
    for endpoint in USER_PROFILE_ENDPOINTS:
        url = f"https://lanhuapp.com{endpoint}"
        request = urllib.request.Request(url, headers=lanhu_api_headers(cookie))
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode('utf-8', errors='replace')
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            errors.append(f"{endpoint}: {error}")
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            errors.append(f"{endpoint}: 返回不是 JSON")
            continue
        user_info = parse_user_payload(payload)
        has_detail = any(
            user_info.get(key)
            for key in ("email", "mobile", "username", "avatar", "id", "name")
        )
        if has_detail:
            user_info["source_url"] = endpoint
            return True, f"已从 {endpoint} 补全账号资料", user_info
        errors.append(f"{endpoint}: 未发现用户资料字段")
    return False, "；".join(errors[-3:]) if errors else "未读取到用户资料", {}


def collect_dict_items(value: object) -> list[dict]:
    """递归收集响应中可能代表项目的字典项。"""
    items: list[dict] = []
    if isinstance(value, dict):
        has_project_marker = any(
            key in value
            for key in ("project_id", "projectId", "projectID", "pid", "id", "project")
        ) and any(
            key in value
            for key in ("name", "project_name", "projectName", "projName", "title", "displayName")
        )
        if has_project_marker:
            items.append(value)
        for key in PROJECT_CONTAINER_KEYS:
            if key in value:
                items.extend(collect_dict_items(value.get(key)))
        for nested_value in value.values():
            if isinstance(nested_value, (dict, list)):
                items.extend(collect_dict_items(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            items.extend(collect_dict_items(nested_value))
    return items


def collect_project_urls(value: object, found_urls: list[str], depth: int = 0) -> None:
    """从登录缓存或接口响应中递归提取蓝湖项目链接。"""
    if depth > 8:
        return
    parsed = parse_json_object(value)
    if isinstance(parsed, str):
        for matched in PROJECT_URL_PATTERN.findall(parsed):
            found_urls.append(matched)
        return
    if isinstance(parsed, dict):
        for item_value in parsed.values():
            collect_project_urls(item_value, found_urls, depth + 1)
        return
    if isinstance(parsed, list):
        for item_value in parsed[:100]:
            collect_project_urls(item_value, found_urls, depth + 1)


def normalize_project_item(item: dict) -> dict:
    """把蓝湖不同接口返回的项目字段统一为界面可用结构。"""
    team_payload = parse_json_object(item.get("team") or item.get("workspace") or {})
    owner_payload = parse_json_object(item.get("owner") or item.get("creator") or item.get("user") or {})
    project_id = (
        item.get("project_id")
        or item.get("projectId")
        or item.get("pid")
        or item.get("projectID")
        or item.get("project")
        or item.get("id")
        or ""
    )
    team_id = (
        item.get("team_id")
        or item.get("teamId")
        or item.get("tid")
        or (team_payload.get("id") if isinstance(team_payload, dict) else "")
        or ""
    )
    name = (
        item.get("project_name")
        or item.get("projectName")
        or item.get("projName")
        or item.get("name")
        or item.get("displayName")
        or item.get("title")
        or item.get("folder_name")
        or item.get("save_path")
        or "未命名项目"
    )
    project_type = item.get("type") or item.get("project_type") or item.get("projectType") or item.get("category") or ""
    updated_at = (
        item.get("updated_at")
        or item.get("updatedAt")
        or item.get("updatedTime")
        or item.get("modify_time")
        or item.get("modifyTime")
        or item.get("gmtModified")
        or item.get("lastUpdateTime")
        or ""
    )
    team_name = ""
    owner_name = ""
    if isinstance(team_payload, dict):
        team_name = first_detail_value(team_payload, ("name", "teamName", "title"))
    if isinstance(owner_payload, dict):
        owner_name = first_detail_value(owner_payload, ("name", "nickname", "userName", "realName"))
    url = ""
    if project_id:
        base_url = "https://lanhuapp.com/web/#/item/project/stage"
        query = {"pid": project_id}
        if team_id:
            query["tid"] = team_id
        url = f"{base_url}?{urlencode(query)}"
    return {
        "id": str(project_id),
        "team_id": str(team_id),
        "name": str(name),
        "type": str(project_type) if project_type else "项目",
        "updated_at": str(updated_at) if updated_at else "",
        "team_name": team_name,
        "owner_name": owner_name,
        "url": url,
        "source": str(item.get("source") or "蓝湖接口"),
        "raw": item,
    }


def projects_from_payload(payload: object, account_id: str = "") -> list[dict]:
    """从登录缓存或接口响应里提取项目对象和项目链接。"""
    projects = [
        normalize_project_item(item)
        for item in collect_dict_items(payload)
    ]
    found_urls: list[str] = []
    collect_project_urls(payload, found_urls)
    for project_url in found_urls:
        parsed_project = parse_lanhu_project_url(project_url)
        if parsed_project:
            parsed_project["source"] = "登录缓存"
            projects.append(parsed_project)
    normalized_projects = merge_project_lists(projects)
    for project in normalized_projects:
        if account_id and not project.get("account_id"):
            project["account_id"] = account_id
    return normalized_projects


def project_identity_key(project: dict) -> str:
    """生成项目稳定身份键，优先按团队和项目 ID 去重。"""
    project_id = str(project.get("id") or project.get("project_id") or "").strip()
    team_id = str(project.get("team_id") or project.get("tid") or "").strip()
    if project_id:
        return f"project:{team_id}:{project_id}"
    project_url = str(project.get("url") or "").strip()
    if project_url:
        parsed_project = parse_lanhu_project_url(project_url)
        if parsed_project and parsed_project.get("id"):
            return f"project:{parsed_project.get('team_id') or ''}:{parsed_project.get('id')}"
        return f"url:{project_url}"
    project_name = str(project.get("name") or "").strip()
    if project_name:
        return f"name:{team_id}:{project_name}"
    return ""


def merge_project_lists(projects: list[dict]) -> list[dict]:
    """按项目链接或 pid/tid 合并项目列表。"""
    unique_projects: dict[str, dict] = {}
    for project in projects:
        if not project:
            continue
        key = project_identity_key(project)
        if not key:
            continue
        if key in unique_projects:
            unique_projects[key] = merge_identity_info(project, unique_projects[key])
        else:
            unique_projects[key] = dict(project)
    return list(unique_projects.values())


def fetch_lanhu_projects(cookie: str) -> tuple[bool, str, list[dict]]:
    """尝试读取当前账号可访问项目列表。

    蓝湖 API 流程：
    1. GET /api/project/team_projects — 返回所有团队及其项目
    2. 数据结构: {"result": {"team_projects": [{"tid": "...", "team_name": "...", "projects": [...]}]}}
    """
    if not cookie:
        return False, "缺少蓝湖 Cookie，请先登录账号。", []
    errors: list[str] = []
    for endpoint in PROJECT_ENDPOINTS:
        url = f"https://lanhuapp.com{endpoint}"
        request = urllib.request.Request(url, headers=lanhu_api_headers(cookie))
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                body = response.read().decode('utf-8', errors='replace')
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            errors.append(f"{endpoint}: {error}")
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            errors.append(f"{endpoint}: 返回不是 JSON")
            continue
        # 蓝湖 team_projects API 返回 {"code": "00000", "result": {"team_projects": [...]}}
        # 手动从 team_projects 结构中提取项目（避免通用提取误识别 team 对象为项目）
        projects: list[dict] = []
        if isinstance(payload, dict):
            result = payload.get("result") or payload
            team_projects = result.get("team_projects") or []
            if isinstance(team_projects, list):
                for team_entry in team_projects:
                    if not isinstance(team_entry, dict):
                        continue
                    team_id = team_entry.get("tid") or team_entry.get("team_id") or ""
                    team_name = team_entry.get("team_name") or team_entry.get("name") or ""
                    for proj in (team_entry.get("projects") or []):
                        if not isinstance(proj, dict):
                            continue
                        proj_copy = dict(proj)
                        proj_copy.setdefault("team_id", team_id)
                        proj_copy.setdefault("tid", team_id)
                        normalized = normalize_project_item(proj_copy)
                        if not normalized.get("team_name"):
                            normalized["team_name"] = team_name
                        projects.append(normalized)
        # 回退到通用提取
        if not projects:
            projects = projects_from_payload(payload)
        if projects:
            return True, f"已从 {endpoint} 读取项目", projects
        errors.append(f"{endpoint}: 未发现项目字段")
    return False, "；".join(errors[-3:]) if errors else "未读取到项目", []


def load_projects_for_account(account: dict) -> tuple[bool, str, list[dict]]:
    """合并 API、登录缓存和本地保存的项目来源。"""
    account_id = str(account.get("id") or "")
    cached_projects = cached_projects_for_account(account_id)
    raw_projects = projects_from_payload(account.get("raw", {}), account_id)
    api_ok, api_message, api_projects = fetch_lanhu_projects(str(account.get("cookie") or ""))
    all_projects = merge_project_lists(cached_projects + raw_projects + api_projects)
    if all_projects:
        data = read_projects_data()
        persisted = merge_project_lists(data["projects"] + all_projects)
        data["projects"] = persisted
        write_projects_data(data)
        if api_ok:
            return True, f"{api_message}，共合并 {len(all_projects)} 个项目。", all_projects
        return True, f"已从本地缓存/登录记录合并 {len(all_projects)} 个项目；API 提示: {api_message}", all_projects
    return api_ok, api_message, api_projects


# ============================================
# AI IDE 检测（增强版）
# ============================================


IDE_REGISTRY = {
    'Cursor': {
        'icon': 'mouse-pointer-2',
        'exe': [
            Path('D:/Apps/nodejs/cursor.cmd'),
            Path('D:/Apps/nodejs/cursor.exe'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Cursor' / 'Cursor.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'cursor' / 'Cursor.exe',
            Path('D:/Apps/cursor/Cursor.exe'),
            Path('D:/Apps/Cursor/Cursor.exe'),
            Path('D:/Apps/Cursor/resources/app/bin/cursor.cmd'),
        ],
        'config': [
            Path.home() / '.cursor' / 'mcp.json',
            Path(os.environ.get('APPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
            Path(os.environ.get('APPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
        ],
        'format': 'json',
        'commands': ['cursor'],
    },
    'Windsurf': {
        'icon': 'waves',
        'exe': [
            Path('D:/Apps/nodejs/windsurf.cmd'),
            Path('D:/Apps/nodejs/windsurf.exe'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Windsurf' / 'Windsurf.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'windsurf' / 'Windsurf.exe',
            Path('D:/Apps/Windsurf/Windsurf.exe'),
            Path('D:/Apps/windsurf/Windsurf.exe'),
        ],
        'config': [
            Path.home() / '.codeium' / 'windsurf' / 'mcp_config.json',
            Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
            Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
        ],
        'format': 'json',
        'commands': ['windsurf'],
    },
    'Claude Desktop': {
        'icon': 'message-circle',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Claude' / 'Claude.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Claude' / 'Claude.exe',
            Path('D:/Apps/Claude/Claude.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Claude' / 'claude_desktop_config.json',
        ],
        'format': 'json',
    },
    'Claude Code': {
        'icon': 'terminal',
        'exe': [
            Path('D:/Apps/nodejs/claude.cmd'),
            Path('D:/Apps/nodejs/claude.exe'),
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'claude.cmd',
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'claude.exe',
            Path('D:/Apps/Claude/claude.cmd'),
        ],
        'config': [
            Path.home() / '.claude.json',
        ],
        'format': 'claude-cli',
        'commands': ['claude'],
    },
    'VS Code + Cline': {
        'icon': 'code-2',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe',
            Path(os.environ.get('PROGRAMFILES', '')) / 'Microsoft VS Code' / 'Code.exe',
            Path('D:/Apps/Microsoft VS Code/Code.exe'),
            Path('D:/Apps/VS Code/Code.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
            Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
        ],
        'format': 'json',
        'commands': ['code'],
    },
    'Trae': {
        'icon': 'sparkles',
        'exe': [
            Path('D:/Apps/nodejs/trae.cmd'),
            Path('D:/Apps/nodejs/trae.exe'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Trae' / 'Trae.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Trae' / 'Trae.exe',
            Path('D:/Apps/Trae/Trae.exe'),
            Path('D:/Apps/trae/Trae.exe'),
        ],
        'config': [
            Path.home() / '.trae' / 'mcp.json',
            Path(os.environ.get('APPDATA', '')) / 'Trae' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        ],
        'format': 'json',
        'commands': ['trae'],
    },
    'Cherry Studio': {
        'icon': 'bot',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'cherry-studio' / 'Cherry Studio.exe',
            Path(os.environ.get('APPDATA', '')) / 'cherry-studio' / 'Cherry Studio.exe',
            Path('D:/Apps/CherryStudio/Cherry Studio/Cherry Studio.exe'),
            Path('D:/Apps/CherryStudio/Cherry Studio.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'cherry-studio' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['cherry-studio'],
    },
    'ChatBox': {
        'icon': 'messages-square',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'chatbox' / 'Chatbox.exe',
            Path('D:/Apps/ChatBox/Chatbox.exe'),
            Path('D:/Apps/chatbox/Chatbox.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'chatbox' / 'config.json',
        ],
        'format': 'json',
        'commands': ['chatbox'],
    },
    'Continue': {
        'icon': 'circle-fading-arrow-up',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe',
            Path('D:/Apps/Microsoft VS Code/Code.exe'),
        ],
        'config': [
            Path.home() / '.continue' / 'config.yaml',
        ],
        'format': 'yaml',
        'commands': ['continue'],
    },
    'Cline (OpenCode)': {
        'icon': 'braces',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'opencode' / 'OpenCode.exe',
            Path('D:/Apps/OpenCode/OpenCode.exe'),
            Path('D:/Apps/opencode/OpenCode.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'opencode' / 'mcp.json',
            Path.home() / '.opencode' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['opencode'],
    },
    'CodeBuddy': {
        'icon': 'handshake',
        'exe': [
            Path('D:/Apps/CodeBuddyCN/CodeBuddy CN.exe'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'CodeBuddy' / 'CodeBuddy CN.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'CodeBuddy' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['codebuddy'],
    },
    'MimoCode': {
        'icon': 'blocks',
        'exe': [
            Path('D:/Apps/nodejs/mimo.cmd'),
            Path('D:/Apps/nodejs/mimo.exe'),
            Path('D:/Apps/mimocode-windows-x64/mimo.exe'),
            Path('D:/Apps/MimoCode/mimo.exe'),
            Path('D:/Apps/mimocode/mimo.exe'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'mimocode' / 'mimo.exe',
        ],
        'config': [
            Path.cwd() / '.mimocode' / 'mcp.json',
            Path.home() / '.mimocode' / 'mcp.json',
            Path(os.environ.get('APPDATA', '')) / 'mimocode' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['mimo', 'mimocode'],
    },
    'Junie (JetBrains)': {
        'icon': 'badge-code',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'JetBrains' / 'Toolbox' / 'apps' / 'Junie' / 'ch-0' / 'Junie.exe',
            Path('D:/Apps/JetBrains/Toolbox/apps/Junie/ch-0/Junie.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'JetBrains' / 'Junie' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['junie'],
    },
    'Codex': {
        'icon': 'square-terminal',
        'exe': [
            Path('D:/Apps/nodejs/codex.cmd'),
            Path('D:/Apps/nodejs/codex.exe'),
            Path('D:/Apps/CodexApp/codex.bat'),
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'codex.cmd',
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'codex.exe',
            Path('D:/Apps/Codex/codex.cmd'),
            Path('D:/Apps/codex/codex.cmd'),
        ],
        'config': [
            Path.home() / '.codex' / 'config.toml',
        ],
        'format': 'toml',
        'commands': ['codex'],
    },
    'Gemini CLI': {
        'icon': 'gem',
        'exe': [
            Path('D:/Apps/nodejs/gemini.cmd'),
            Path('D:/Apps/nodejs/gemini.exe'),
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'gemini.cmd',
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'gemini.exe',
            Path('D:/Apps/Gemini/gemini.cmd'),
        ],
        'config': [
            Path.home() / '.gemini' / 'settings.json',
        ],
        'format': 'json',
        'commands': ['gemini'],
    },
    'Roo Code': {
        'icon': 'route',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Cursor' / 'Cursor.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
            Path(os.environ.get('APPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
        ],
        'format': 'json',
        'commands': ['code', 'cursor'],
    },
    'Qoder': {
        'icon': 'blocks',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Qoder' / 'Qoder.exe',
            Path('D:/Apps/Qoder/Qoder.exe'),
            Path('D:/Apps/qoder/Qoder.exe'),
        ],
        'config': [
            Path.home() / '.qoder' / 'mcp.json',
            Path(os.environ.get('APPDATA', '')) / 'Qoder' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['qoder'],
    },
    'Kiro': {
        'icon': 'sparkles',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Kiro' / 'Kiro.exe',
            Path('D:/Apps/Kiro/Kiro.exe'),
            Path('D:/Apps/kiro/Kiro.exe'),
        ],
        'config': [
            Path.home() / '.kiro' / 'mcp.json',
            Path(os.environ.get('APPDATA', '')) / 'Kiro' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['kiro'],
    },
    'Zed': {
        'icon': 'code-2',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Zed' / 'Zed.exe',
            Path('D:/Apps/Zed/Zed.exe'),
            Path('D:/Apps/zed/Zed.exe'),
        ],
        'config': [
            Path.home() / '.config' / 'zed' / 'settings.json',
            Path(os.environ.get('APPDATA', '')) / 'Zed' / 'settings.json',
        ],
        'format': 'json',
        'commands': ['zed'],
    },
}


class IDEManager:
    @staticmethod
    def _is_valid_executable_path(exe_path: Path) -> bool:
        """判断候选可执行文件是否真实可用。"""
        if not exe_path.exists() or not exe_path.is_file():
            return False
        # 命令脚本通常很小，二进制程序需要做一个基础大小判断。
        if exe_path.suffix.lower() in ('.cmd', '.bat', '.ps1'):
            return True
        return exe_path.stat().st_size > 1024 * 32

    @staticmethod
    def _resolve_command_path(command_name: str) -> Optional[Path]:
        """通过 PATH 解析 CLI 工具真实路径。"""
        resolved = shutil.which(command_name)
        return Path(resolved) if resolved else None

    @staticmethod
    def _find_executable(info: dict) -> Optional[Path]:
        """从固定路径和 PATH 中找到第一个可用程序。"""
        for exe_path in info['exe']:
            if IDEManager._is_valid_executable_path(exe_path):
                return exe_path
        for command_name in info.get('commands', []):
            resolved_path = IDEManager._resolve_command_path(str(command_name))
            if resolved_path and IDEManager._is_valid_executable_path(resolved_path):
                return resolved_path
        return None

    @staticmethod
    def _check_ide_installed(info: dict) -> bool:
        """真实检测IDE是否已安装（检查exe文件、PATH和配置目录）"""
        if IDEManager._find_executable(info):
            return True
        for config_path in info.get('config', []):
            if config_path.exists() or config_path.parent.exists():
                return True
        return False

    @staticmethod
    def _check_config_exists(info: dict) -> bool:
        """检查IDE的MCP配置目录是否存在"""
        for config_path in info['config']:
            if config_path.parent.exists():
                return True
        return False

    @staticmethod
    def detect_all() -> dict:
        results = {}
        for name, info in IDE_REGISTRY.items():
            installed = IDEManager._check_ide_installed(info)
            results[name] = installed
        return results

    @staticmethod
    def get_detection_details() -> dict:
        """获取详细的检测信息（用于调试）"""
        details = {}
        for name, info in IDE_REGISTRY.items():
            exe_found = IDEManager._find_executable(info)
            
            config_found = None
            for config_path in info['config']:
                if config_path.parent.exists():
                    config_found = config_path
                    break
            
            details[name] = {
                'installed': exe_found is not None or config_found is not None,
                'exe_path': str(exe_found) if exe_found else None,
                'config_dir': str(config_found.parent) if config_found else None,
                'config_path': str(config_found) if config_found else None,
                'icon': info.get('icon', 'plug'),
            }
        return details

    @staticmethod
    def _select_config_path(info: dict) -> Optional[Path]:
        """选择最合适的配置路径，优先使用已存在文件，其次使用已存在目录。"""
        for path in info['config']:
            if path.exists():
                return path
        for path in info['config']:
            if path.parent.exists():
                return path
        return info['config'][0] if info.get('config') else None

    @staticmethod
    def _load_json_config(config_path: Path) -> dict:
        """读取 JSON 配置文件，失败时返回空配置。"""
        if not config_path.exists():
            return {}
        try:
            content = config_path.read_text(encoding='utf-8').strip()
            return json.loads(content) if content else {}
        except json.JSONDecodeError:
            backup_path = config_path.with_suffix(config_path.suffix + f".bak-{int(time.time())}")
            try:
                shutil.copy2(config_path, backup_path)
            except OSError:
                pass
            return {}

    @staticmethod
    def _dump_json_config(config_path: Path, config: dict) -> None:
        """写入 JSON 配置文件。"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')

    @staticmethod
    def _configure_json(config_path: Path, port: int) -> None:
        """为 JSON 配置写入 lanhu MCP 服务。"""
        config = IDEManager._load_json_config(config_path)
        if not isinstance(config, dict):
            config = {}
        server_url = current_mcp_url(port)
        if 'mcpServers' not in config or not isinstance(config.get('mcpServers'), dict):
            config['mcpServers'] = {}
        config['mcpServers']['lanhu'] = {
            'url': server_url,
            'disabled': False,
        }
        IDEManager._dump_json_config(config_path, config)

    @staticmethod
    def _configure_claude_cli(config_path: Path, port: int) -> None:
        """为 Claude Code 写入用户级 HTTP MCP 配置。"""
        config = IDEManager._load_json_config(config_path)
        if not isinstance(config, dict):
            config = {}
        mcp_servers = config.get("mcpServers")
        if not isinstance(mcp_servers, dict):
            mcp_servers = {}
        mcp_servers["lanhu"] = {
            "type": "http",
            "url": current_mcp_url(port),
        }
        config["mcpServers"] = mcp_servers
        IDEManager._dump_json_config(config_path, config)

    @staticmethod
    def _configure_yaml(config_path: Path, port: int) -> None:
        """为 YAML 配置写入 lanhu MCP 服务。"""
        config = {}
        if config_path.exists():
            try:
                import yaml
                config = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
            except Exception:
                config = {}
        if 'mcpServers' not in config or not isinstance(config.get('mcpServers'), dict):
            config['mcpServers'] = {}
        config['mcpServers']['lanhu'] = {
            'url': current_mcp_url(port),
            'disabled': False,
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import yaml
            config_path.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False), encoding='utf-8')
        except Exception:
            lines = ["mcpServers:"]
            for name, server in config.get('mcpServers', {}).items():
                lines.append(f"  {name}:")
                lines.append(f"    url: {server.get('url', '')}")
                lines.append(f"    disabled: {str(server.get('disabled', False)).lower()}")
            config_path.write_text("\n".join(lines) + "\n", encoding='utf-8')

    @staticmethod
    def _configure_toml(config_path: Path, port: int) -> None:
        """为 Codex TOML 配置写入 lanhu MCP 服务。"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        content = config_path.read_text(encoding='utf-8') if config_path.exists() else ""
        server_block = (
            "[mcp_servers.lanhu]\n"
            f'url = "{current_mcp_url(port)}"\n'
        )
        pattern = r'(?ms)^\[mcp_servers\.lanhu\]\s*.*?(?=^\[|\Z)'
        if re.search(pattern, content):
            content = re.sub(pattern, server_block, content)
        else:
            if content and not content.endswith("\n"):
                content += "\n"
            if "[mcp_servers]" not in content:
                content += "\n[mcp_servers]\n"
            content += "\n" + server_block
        config_path.write_text(content, encoding='utf-8')

    @staticmethod
    def configure(ide_name: str, port: int = 8000) -> tuple[bool, str]:
        if ide_name not in IDE_REGISTRY:
            return False, "未知IDE"

        ide_info = IDE_REGISTRY[ide_name]
        config_path = IDEManager._select_config_path(ide_info)
        if not config_path:
            return False, f"{ide_name} 配置目录不存在"

        try:
            config_format = ide_info.get('format', config_path.suffix.lower().lstrip('.'))
            if config_format == 'claude-cli':
                IDEManager._configure_claude_cli(config_path, port)
            elif config_format == 'toml' or config_path.suffix.lower() == '.toml':
                IDEManager._configure_toml(config_path, port)
            elif config_format == 'yaml' or config_path.suffix.lower() in ('.yaml', '.yml'):
                IDEManager._configure_yaml(config_path, port)
            else:
                IDEManager._configure_json(config_path, port)
            return True, f"已配置 {ide_name}: {config_path}"
        except PermissionError:
            return False, f"权限不足，无法写入 {config_path}"
        except Exception as e:
            return False, f"写入失败: {e}"

    @staticmethod
    def configure_all(port: int = 8000) -> list:
        results = []
        detected = IDEManager.detect_all()
        for name, installed in detected.items():
            if installed:
                ok, msg = IDEManager.configure(name, port)
                results.append((name, ok, msg))
        return results


# ============================================
# 服务管理（子进程）- 增强版
# ============================================

class ServiceManager:
    _process = None
    _running = False
    _port = 8000
    _stop_event = threading.Event()
    _lock = threading.RLock()

    @staticmethod
    def is_running() -> bool:
        with ServiceManager._lock:
            if ServiceManager._process is None:
                return False
            if ServiceManager._process.poll() is not None:
                ServiceManager._running = False
                return False
            return ServiceManager._running

    @staticmethod
    def start(port: int = 8000, on_output=None, on_error=None) -> tuple[bool, str]:
        with ServiceManager._lock:
            if ServiceManager.is_running():
                return False, "服务已在运行"

            valid, p, err = validate_port(str(port))
            if not valid:
                return False, err
            if is_port_in_use(p):
                return False, f"端口 {port} 已被占用，请更换端口或关闭占用程序"

        try:
            server_command, server_dir, server_source = build_server_start_command()
        except FileNotFoundError as error:
            return False, str(error)

        # 准备环境变量
        env = os.environ.copy()
        if ENV_FILE.exists():
            try:
                with open(ENV_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            env[k.strip()] = v.strip().strip('"').strip("'")
            except Exception as e:
                if on_error:
                    on_error(f"读取环境变量失败: {e}")

        active_account = get_active_account()
        if active_account:
            env['LANHU_COOKIE'] = active_account.get("cookie", "")
            env['LANHU_USER_NAME'] = active_account.get("name", "蓝湖用户")
            env['LANHU_USER_ROLE'] = active_account.get("role", "Developer")

        env['SERVER_PORT'] = str(port)
        env['MCP_TRANSPORT'] = 'http'

        ServiceManager._stop_event.clear()

        try:
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW

            flog(f"启动 MCP 服务({server_source}): {' '.join(server_command)}")
            ServiceManager._process = subprocess.Popen(
                server_command,
                cwd=str(server_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            ServiceManager._running = True
            ServiceManager._port = port

            # 读取输出线程
            def read_output() -> None:
                try:
                    for line in iter(ServiceManager._process.stdout.readline, b''):
                        if ServiceManager._stop_event.is_set():
                            break
                        if on_output:
                            decoded = line.decode('utf-8', errors='replace').rstrip('\n\r')
                            on_output(decoded)
                except Exception:
                    pass

            threading.Thread(target=read_output, daemon=True).start()

            # 等待启动（最多15秒）
            for i in range(30):
                time.sleep(0.5)
                if ServiceManager._stop_event.is_set():
                    return False, "已取消启动"
                if is_port_in_use(port):
                    return True, "服务已启动"

            # 检查进程是否退出
            if ServiceManager._process.poll() is not None:
                ServiceManager._running = False
                rc = ServiceManager._process.returncode
                return False, f"服务启动失败（进程退出码: {rc}，请检查日志）"

            return True, "服务启动中..."

        except OSError as e:
            ServiceManager._running = False
            return False, f"启动失败(权限/路径): {e}"
        except Exception as e:
            ServiceManager._running = False
            return False, f"启动失败: {type(e).__name__}: {e}"

    @staticmethod
    def stop() -> tuple[bool, str]:
        if ServiceManager._process is None:
            return False, "服务未运行"

        ServiceManager._stop_event.set()
        ServiceManager._running = False

        try:
            ServiceManager._process.terminate()
            try:
                ServiceManager._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ServiceManager._process.kill()
                ServiceManager._process.wait(timeout=3)
        except Exception:
            try:
                ServiceManager._process.kill()
            except Exception:
                pass

        ServiceManager._process = None
        return True, "服务已停止"


# ============================================
# 现代化 GUI
# ============================================

def apply_modern_style(root: object) -> object:
    """应用 TDesign 风格主题样式"""
    from tkinter import ttk

    style = ttk.Style()

    available_themes = style.theme_names()
    if 'clam' in available_themes:
        style.theme_use('clam')

    # ===== 全局配置 =====
    style.configure('.',
                    background=COLORS['bg'],
                    foreground=COLORS['text_primary'],
                    font=(FONT['family'], FONT['sizes']['sm']))
    style.map('.',
              background=[('active', COLORS['bg'])],
              foreground=[('disabled', COLORS['text_disabled'])])

    # ===== Frame =====
    style.configure('TFrame', background=COLORS['bg'])
    style.configure('Card.TFrame', background=COLORS['card'])
    style.configure('Surface.TFrame', background=COLORS['surface'])
    style.configure('Sidebar.TFrame', background=COLORS['sidebar'])

    # ===== Label =====
    style.configure('TLabel',
                    background=COLORS['bg'],
                    foreground=COLORS['text_primary'],
                    font=(FONT['family'], FONT['sizes']['sm']))

    style.configure('Title.TLabel',
                    background=COLORS['bg'],
                    foreground=COLORS['text_primary'],
                    font=(FONT['family'], FONT['sizes']['5xl'], 'bold'))

    style.configure('Subtitle.TLabel',
                    background=COLORS['bg'],
                    foreground=COLORS['text_secondary'],
                    font=(FONT['family'], FONT['sizes']['base']))

    style.configure('Status.TLabel',
                    background=COLORS['card'],
                    foreground=COLORS['text_primary'],
                    font=(FONT['family'], FONT['sizes']['md'], 'bold'))

    style.configure('StatusRunning.TLabel',
                    background=COLORS['card'],
                    foreground=COLORS['success'],
                    font=(FONT['family'], FONT['sizes']['md'], 'bold'))

    style.configure('StatusError.TLabel',
                    background=COLORS['card'],
                    foreground=COLORS['danger'],
                    font=(FONT['family'], FONT['sizes']['md'], 'bold'))

    style.configure('StatusWarn.TLabel',
                    background=COLORS['card'],
                    foreground=COLORS['warning'],
                    font=(FONT['family'], FONT['sizes']['md'], 'bold'))

    style.configure('Hint.TLabel',
                    background=COLORS['card'],
                    foreground=COLORS['text_muted'],
                    font=(FONT['family'], FONT['sizes']['xs']))

    style.configure('Disabled.TLabel',
                    background=COLORS['card'],
                    foreground=COLORS['text_disabled'],
                    font=(FONT['family'], FONT['sizes']['sm']))

    # ===== LabelFrame =====
    style.configure('Card.TLabelframe',
                    background=COLORS['card'],
                    foreground=COLORS['text_primary'])
    style.configure('Card.TLabelframe.Label',
                    background=COLORS['card'],
                    foreground=COLORS['primary'],
                    font=(FONT['family'], FONT['sizes']['base'], 'bold'),
                    padding=(SPACING['3'], SPACING['2'], 0, SPACING['2']))
    style.configure('TLabelframe',
                    background=COLORS['card'],
                    foreground=COLORS['text_primary'])
    style.configure('TLabelframe.Label',
                    background=COLORS['card'],
                    foreground=COLORS['primary'],
                    font=(FONT['family'], FONT['sizes']['base'], 'bold'))

    # ===== Button - TDesign 默认 =====
    style.configure('TButton',
                    font=(FONT['family'], FONT['sizes']['sm']),
                    padding=(SPACING['3'], SPACING['2']),
                    background=COLORS['card'],
                    foreground=COLORS['text_primary'],
                    borderwidth=1,
                    relief='flat')
    style.map('TButton',
              background=[('active', COLORS['primary_light']),
                         ('pressed', COLORS['primary_light_hover']),
                         ('disabled', COLORS['input_bg_disabled'])],
              foreground=[('active', COLORS['primary']),
                         ('pressed', COLORS['primary_active']),
                         ('disabled', COLORS['text_disabled'])],
              relief=[('pressed', 'sunken')])

    # ===== Button - TDesign Primary =====
    style.configure('Primary.TButton',
                    font=(FONT['family'], FONT['sizes']['base'], 'bold'),
                    padding=(SPACING['4'], SPACING['3']),
                    background=COLORS['primary'],
                    foreground=COLORS['text_on_primary'],
                    borderwidth=0,
                    relief='flat')
    style.map('Primary.TButton',
              background=[('active', COLORS['primary_hover']),
                         ('pressed', COLORS['primary_active']),
                         ('disabled', COLORS['text_disabled'])],
              foreground=[('active', COLORS['text_on_primary']),
                         ('pressed', COLORS['text_on_primary']),
                         ('disabled', COLORS['text_on_primary'])])

    # ===== Button - TDesign Success =====
    style.configure('Success.TButton',
                    font=(FONT['family'], FONT['sizes']['sm']),
                    padding=(SPACING['3'], SPACING['2']),
                    background=COLORS['success'],
                    foreground=COLORS['text_on_primary'],
                    borderwidth=0,
                    relief='flat')
    style.map('Success.TButton',
              background=[('active', COLORS['success_hover']),
                         ('pressed', '#008F65'),
                         ('disabled', COLORS['text_disabled'])],
              foreground=[('active', COLORS['text_on_primary']),
                         ('pressed', COLORS['text_on_primary']),
                         ('disabled', COLORS['text_on_primary'])])

    # ===== Button - TDesign Danger =====
    style.configure('Danger.TButton',
                    font=(FONT['family'], FONT['sizes']['sm']),
                    padding=(SPACING['3'], SPACING['2']),
                    background=COLORS['danger'],
                    foreground=COLORS['text_on_primary'],
                    borderwidth=0,
                    relief='flat')
    style.map('Danger.TButton',
              background=[('active', COLORS['danger_hover']),
                         ('pressed', '#B8323C'),
                         ('disabled', COLORS['text_disabled'])],
              foreground=[('active', COLORS['text_on_primary']),
                         ('pressed', COLORS['text_on_primary']),
                         ('disabled', COLORS['text_on_primary'])])

    # ===== Button - TDesign Ghost =====
    style.configure('Ghost.TButton',
                    font=(FONT['family'], FONT['sizes']['sm']),
                    padding=(SPACING['3'], SPACING['2']),
                    background='transparent',
                    foreground=COLORS['text_secondary'],
                    borderwidth=0,
                    relief='flat')
    style.map('Ghost.TButton',
              background=[('active', COLORS['surface_hover']),
                         ('pressed', COLORS['border_light'])],
              foreground=[('active', COLORS['text_primary']),
                         ('pressed', COLORS['text_primary'])])

    # ===== Button - TDesign Small =====
    style.configure('Small.TButton',
                    font=(FONT['family'], FONT['sizes']['xs']),
                    padding=(SPACING['2'], SPACING['1']),
                    background=COLORS['surface'],
                    foreground=COLORS['text_secondary'],
                    borderwidth=1,
                    relief='flat')
    style.map('Small.TButton',
              background=[('active', COLORS['surface_hover']),
                         ('pressed', COLORS['border_light']),
                         ('disabled', COLORS['input_bg_disabled'])],
              foreground=[('active', COLORS['text_primary']),
                         ('pressed', COLORS['text_primary']),
                         ('disabled', COLORS['text_disabled'])])

    # ===== Entry - TDesign 输入框 =====
    style.configure('TEntry',
                    font=(FONT['mono'], FONT['sizes']['sm']),
                    padding=(SPACING['3'], SPACING['2']),
                    fieldbackground=COLORS['input_bg'],
                    insertcolor=COLORS['text_primary'],
                    borderwidth=1,
                    relief='flat')
    style.map('TEntry',
              fieldbackground=[('focus', '#FFFFFF'),
                             ('disabled', COLORS['input_bg_disabled'])],
              bordercolor=[('focus', COLORS['border_focus']),
                          ('disabled', COLORS['border'])],
              foreground=[('disabled', COLORS['text_disabled'])])

    # ===== Combobox - TDesign 下拉框 =====
    style.configure('TCombobox',
                    font=(FONT['family'], FONT['sizes']['sm']),
                    padding=(SPACING['3'], SPACING['2']),
                    fieldbackground=COLORS['input_bg'],
                    background=COLORS['surface'],
                    borderwidth=1,
                    relief='flat')
    style.map('TCombobox',
              fieldbackground=[('focus', '#FFFFFF'),
                             ('readonly', COLORS['input_bg_disabled'])],
              bordercolor=[('focus', COLORS['border_focus'])],
              foreground=[('readonly', COLORS['text_disabled'])])

    # ===== Notebook - TDesign 选项卡 =====
    style.configure('TNotebook',
                    background=COLORS['bg'],
                    borderwidth=0)
    style.configure('TNotebook.Tab',
                    font=(FONT['family'], FONT['sizes']['sm']),
                    padding=(SPACING['4'], SPACING['2']),
                    background=COLORS['surface'],
                    foreground=COLORS['text_secondary'],
                    borderwidth=0)
    style.map('TNotebook.Tab',
              background=[('selected', COLORS['card']),
                         ('active', COLORS['card_hover'])],
              foreground=[('selected', COLORS['primary']),
                         ('active', COLORS['text_primary'])])

    # ===== Scrollbar - TDesign 滚动条 =====
    style.configure('Vertical.TScrollbar',
                    background=COLORS['border_light'],
                    troughcolor=COLORS['bg'],
                    borderwidth=0,
                    arrowcolor=COLORS['text_muted'],
                    relief='flat')
    style.map('Vertical.TScrollbar',
              background=[('active', COLORS['border']),
                         ('!active', COLORS['border_light'])])

    # ===== Checkbutton =====
    style.configure('TCheckbutton',
                    font=(FONT['family'], FONT['sizes']['sm']),
                    background=COLORS['bg'],
                    foreground=COLORS['text_primary'])
    style.map('TCheckbutton',
              background=[('active', COLORS['bg'])],
              foreground=[('active', COLORS['text_primary'])])

    # ===== Radiobutton =====
    style.configure('TRadiobutton',
                    font=(FONT['family'], FONT['sizes']['sm']),
                    background=COLORS['bg'],
                    foreground=COLORS['text_primary'])
    style.map('TRadiobutton',
              background=[('active', COLORS['bg'])],
              foreground=[('active', COLORS['text_primary'])])

    # ===== Progressbar - TDesign 进度条 =====
    style.configure('Horizontal.TProgressbar',
                    background=COLORS['primary'],
                    troughcolor=COLORS['border_light'],
                    borderwidth=0,
                    thickness=4)

    # ===== Separator =====
    style.configure('TSeparator',
                    background=COLORS['border_light'])

    # ===== Log日志区域 =====
    style.configure('Log.TFrame', background=COLORS['log_bg'])

    return style


def center_window(root: object, width: int, height: int) -> None:
    """按屏幕尺寸居中打开主窗口。"""
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    left = max((screen_width - width) // 2, 0)
    top = max((screen_height - height) // 2, 0)
    root.geometry(f"{width}x{height}+{left}+{top}")


def _fetch_designs_api(cookie: str, project_id: str, team_id: str = "") -> dict:
    """调用蓝湖 API 获取设计图列表和分区信息。"""
    headers = lanhu_api_headers(cookie)
    # 获取设计图列表
    api_url = f"https://lanhuapp.com/api/project/images?project_id={project_id}"
    if team_id:
        api_url += f"&team_id={team_id}"
    api_url += "&dds_status=1&position=1&show_cb_src=1&comment=1"

    request = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode('utf-8', errors='replace')
    data = json.loads(body)

    if data.get('code') != '00000':
        return {'status': 'error', 'message': data.get('msg', 'Unknown error')}

    project_data = data.get('data', {})
    images = project_data.get('images', [])

    # 获取分区信息
    sectors = []
    image_sector_map = {}
    try:
        sector_url = f"https://lanhuapp.com/api/project/project_sectors?project_id={project_id}"
        sector_req = urllib.request.Request(sector_url, headers=headers)
        with urllib.request.urlopen(sector_req, timeout=15) as sector_resp:
            sector_body = sector_resp.read().decode('utf-8', errors='replace')
        sector_data = json.loads(sector_body)
        if sector_data.get('code') == '00000':
            raw_sectors = sector_data.get('data', {}).get('sectors', [])
            for sec in raw_sectors:
                sec_id = sec.get('id', '')
                sec_name = sec.get('name', '未分组')
                sectors.append({'id': sec_id, 'name': sec_name})
                for img_id in sec.get('images', []):
                    if img_id not in image_sector_map:
                        image_sector_map[img_id] = []
                    image_sector_map[img_id].append({'id': sec_id, 'name': sec_name})
    except Exception:
        pass

    # 组装设计图列表
    design_list = []
    for idx, img in enumerate(images, 1):
        img_id = img.get('id', '')
        design_sectors = image_sector_map.get(img_id, [])
        design_list.append({
            'index': idx,
            'id': img_id,
            'name': img.get('name', f'设计图{idx}'),
            'width': img.get('width', 0),
            'height': img.get('height', 0),
            'url': img.get('url', ''),
            'update_time': img.get('update_time', ''),
            'sectors': [s.get('name') for s in design_sectors if s.get('name')],
            'sector_ids': [s.get('id') for s in design_sectors if s.get('id')],
        })

    return {
        'status': 'success',
        'project_name': project_data.get('name', ''),
        'total_designs': len(design_list),
        'sectors': sectors,
        'designs': design_list,
    }


def _download_image_bytes(url: str, cookie: str = "") -> bytes:
    """下载图片字节。"""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    if cookie:
        headers["Cookie"] = cookie
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def open_design_browser(parent_root, project_id: str, team_id: str, project_name: str,
                        get_active_account_fn, log_fn) -> None:
    """打开设计稿浏览窗口。

    左侧渲染分组，右侧渲染设计稿缩略图，支持多选，右上角生成提示词。
    """
    import tkinter as tk
    from tkinter import ttk, messagebox
    from PIL import Image, ImageTk
    import io

    active = get_active_account_fn()
    if not active or not active.get('cookie'):
        messagebox.showwarning("提示", "请先登录蓝湖账号。")
        return
    cookie = active['cookie']

    # 创建窗口
    win = tk.Toplevel(parent_root)
    win.title(f"设计稿浏览 - {project_name}")
    win.geometry("1200x750")
    win.minsize(900, 600)
    win.configure(bg=COLORS['bg'])
    win.transient(parent_root)
    win.grab_set()

    # 顶部工具栏
    toolbar = tk.Frame(win, bg=COLORS['card'], highlightbackground=COLORS['border_light'], highlightthickness=1)
    toolbar.pack(fill=tk.X, padx=12, pady=(12, 0))
    toolbar_inner = tk.Frame(toolbar, bg=COLORS['card'])
    toolbar_inner.pack(fill=tk.X, padx=16, pady=10)

    tk.Label(
        toolbar_inner,
        text=f"🎨 {project_name}",
        bg=COLORS['card'],
        fg=COLORS['text_primary'],
        font=('Segoe UI', 14, 'bold'),
    ).pack(side=tk.LEFT)

    status_var = tk.StringVar(value="正在加载设计稿...")
    tk.Label(
        toolbar_inner,
        textvariable=status_var,
        bg=COLORS['card'],
        fg=COLORS['text_muted'],
        font=('Segoe UI', 9),
    ).pack(side=tk.LEFT, padx=(16, 0))

    # 右上角操作区
    action_frame = tk.Frame(toolbar_inner, bg=COLORS['card'])
    action_frame.pack(side=tk.RIGHT)

    selected_designs: list[dict] = []
    selected_set: set[str] = set()  # 用 design id 跟踪选中状态
    all_designs_data: list[dict] = []  # 全部设计稿数据
    sector_buttons: dict[str, tk.Frame] = {}
    design_widgets: list[dict] = []  # [{widget, design, checkbox_var}]
    thumbnail_cache: dict[str, ImageTk.PhotoImage] = {}  # url -> PhotoImage

    # 提示词文本区（底部可折叠）
    prompt_frame = tk.Frame(win, bg=COLORS['card'], highlightbackground=COLORS['border_light'], highlightthickness=1)
    prompt_text = tk.Text(prompt_frame, height=8, bg=COLORS['card'], fg=COLORS['text_primary'],
                          font=('Consolas', 10), wrap=tk.WORD, relief=tk.FLAT, padx=12, pady=10)
    prompt_scroll = tk.Scrollbar(prompt_frame, orient=tk.VERTICAL, command=prompt_text.yview)
    prompt_text.configure(yscrollcommand=prompt_scroll.set)
    prompt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    prompt_text.pack(fill=tk.BOTH, expand=True)
    prompt_frame.pack_forget()  # 默认隐藏

    def generate_prompt():
        """生成提示词。"""
        if not selected_designs:
            messagebox.showwarning("提示", "请先选择设计稿。", parent=win)
            return

        prompt_lines = []
        prompt_lines.append(f"# 设计稿还原任务")
        prompt_lines.append(f"")
        prompt_lines.append(f"项目: {project_name}")
        prompt_lines.append(f"选中设计稿数量: {len(selected_designs)}")
        prompt_lines.append(f"")
        prompt_lines.append(f"## 选中的设计稿")
        prompt_lines.append(f"")

        for i, design in enumerate(selected_designs, 1):
            prompt_lines.append(f"### 设计稿 {i}: {design.get('name', '未命名')}")
            dims = f"{design.get('width', '?')}x{design.get('height', '?')}"
            prompt_lines.append(f"- 尺寸: {dims}")
            if design.get('sectors'):
                prompt_lines.append(f"- 分组: {', '.join(design['sectors'])}")
            if design.get('url'):
                prompt_lines.append(f"- 图片URL: {design['url']}")
            if design.get('update_time'):
                prompt_lines.append(f"- 更新时间: {design['update_time']}")
            prompt_lines.append("")

        prompt_lines.append(f"## 任务要求")
        prompt_lines.append(f"")
        prompt_lines.append(f"1. 请根据以上设计稿，生成对应的前端页面代码")
        prompt_lines.append(f"2. 使用 HTML + CSS 实现，保持与设计稿一致的视觉效果")
        prompt_lines.append(f"3. 注意响应式布局和跨浏览器兼容性")
        prompt_lines.append(f"4. 图片资源请使用设计稿中的 URL")
        prompt_lines.append(f"5. 保持设计稿中的字体、颜色、间距等细节")
        prompt_lines.append(f"")
        prompt_lines.append(f"## 设计稿图片")
        prompt_lines.append(f"")
        for i, design in enumerate(selected_designs, 1):
            if design.get('url'):
                prompt_lines.append(f"设计稿 {i}: {design.get('name', '')}")
                prompt_lines.append(f"![{design.get('name', '')}]({design['url']})")
                prompt_lines.append("")

        prompt_text.delete('1.0', tk.END)
        prompt_text.insert('1.0', '\n'.join(prompt_lines))
        prompt_frame.pack(fill=tk.X, padx=12, pady=(8, 12), side=tk.BOTTOM)
        win.update_idletasks()
        log_fn(f"已生成 {len(selected_designs)} 个设计稿的提示词", 'success')

    def copy_prompt():
        """复制提示词到剪贴板。"""
        content = prompt_text.get('1.0', tk.END).strip()
        if not content:
            messagebox.showwarning("提示", "还没有生成提示词。", parent=win)
            return
        parent_root.clipboard_clear()
        parent_root.clipboard_append(content)
        log_fn("提示词已复制到剪贴板", 'success')

    gen_btn = ttk.Button(action_frame, text="生成提示词", style='Accent.TButton', command=generate_prompt)
    gen_btn.pack(side=tk.LEFT)
    ttk.Button(action_frame, text="复制提示词", style='Small.TButton', command=copy_prompt).pack(side=tk.LEFT, padx=(8, 0))

    # 主内容区：左侧分组 + 右侧设计稿
    main_paned = tk.Frame(win, bg=COLORS['bg'])
    main_paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    # 左侧分组栏
    sidebar_frame = tk.Frame(main_paned, bg=COLORS['card'], highlightbackground=COLORS['border_light'],
                             highlightthickness=1, width=200)
    sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
    sidebar_frame.pack_propagate(False)

    sidebar_header = tk.Frame(sidebar_frame, bg=COLORS['card'])
    sidebar_header.pack(fill=tk.X, padx=12, pady=(12, 8))
    tk.Label(sidebar_header, text="分组", bg=COLORS['card'], fg=COLORS['text_primary'],
             font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT)

    sidebar_list = tk.Frame(sidebar_frame, bg=COLORS['card'])
    sidebar_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 12))

    # 右侧设计稿区
    right_frame = tk.Frame(main_paned, bg=COLORS['bg'])
    right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

    # 设计稿网格容器（带滚动）
    canvas_frame = tk.Frame(right_frame, bg=COLORS['bg'])
    canvas_frame.pack(fill=tk.BOTH, expand=True)

    design_canvas = tk.Canvas(canvas_frame, bg=COLORS['bg'], highlightthickness=0, bd=0)
    design_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=design_canvas.yview)
    design_grid = tk.Frame(design_canvas, bg=COLORS['bg'])
    design_window_id = design_canvas.create_window((0, 0), window=design_grid, anchor='nw')

    def _sync_scroll(event=None):
        design_canvas.configure(scrollregion=design_canvas.bbox('all'))

    def _sync_width(event):
        design_canvas.itemconfigure(design_window_id, width=event.width)

    def _on_wheel(event):
        design_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    design_grid.bind('<Configure>', _sync_scroll)
    design_canvas.bind('<Configure>', _sync_width)
    design_canvas.bind('<MouseWheel>', _on_wheel)
    design_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    design_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    design_canvas.configure(yscrollcommand=design_scroll.set)

    current_sector_filter: dict = {'value': None}  # None = 全部

    def render_sidebar(sectors: list[dict]):
        """渲染左侧分组列表。"""
        for widget in sidebar_list.winfo_children():
            widget.destroy()
        sector_buttons.clear()

        def select_sector(sector_id, label_text):
            """选中分组。"""
            current_sector_filter['value'] = sector_id
            for sid, btn in sector_buttons.items():
                btn.configure(bg=COLORS['card'])
                for child in btn.winfo_children():
                    child.configure(bg=COLORS['card'])
            btn = sector_buttons.get(sector_id)
            if btn:
                btn.configure(bg=COLORS['primary_light'])
                for child in btn.winfo_children():
                    child.configure(bg=COLORS['primary_light'])
            render_designs(all_designs_data, sector_id, label_text)

        # "全部" 按钮
        all_btn = tk.Frame(sidebar_list, bg=COLORS['primary_light'], cursor='hand2')
        all_btn.pack(fill=tk.X, pady=2)
        tk.Label(all_btn, text=f"全部设计稿", bg=COLORS['primary_light'], fg=COLORS['primary'],
                 font=('Segoe UI', 9, 'bold'), anchor='w').pack(fill=tk.X, padx=12, pady=8)
        sector_buttons['__all__'] = all_btn
        all_btn.bind('<Button-1>', lambda e: select_sector(None, '全部设计稿'))
        for child in all_btn.winfo_children():
            child.bind('<Button-1>', lambda e: select_sector(None, '全部设计稿'))

        for sector in sectors:
            sid = sector.get('id', '')
            sname = sector.get('name', '未分组')
            count = sum(1 for d in all_designs_data if sid in d.get('sector_ids', []))
            btn = tk.Frame(sidebar_list, bg=COLORS['card'], cursor='hand2')
            btn.pack(fill=tk.X, pady=2)
            label = tk.Label(btn, text=f"{sname} ({count})", bg=COLORS['card'], fg=COLORS['text_secondary'],
                             font=('Segoe UI', 9), anchor='w')
            label.pack(fill=tk.X, padx=12, pady=8)
            sector_buttons[sid] = btn
            btn.bind('<Button-1>', lambda e, sid=sid, sname=sname: select_sector(sid, sname))
            label.bind('<Button-1>', lambda e, sid=sid, sname=sname: select_sector(sid, sname))

        # 未分组
        ungrouped = sum(1 for d in all_designs_data if not d.get('sectors'))
        if ungrouped > 0:
            ungrouped_btn = tk.Frame(sidebar_list, bg=COLORS['card'], cursor='hand2')
            ungrouped_btn.pack(fill=tk.X, pady=2)
            tk.Label(ungrouped_btn, text=f"未分组 ({ungrouped})", bg=COLORS['card'], fg=COLORS['text_muted'],
                     font=('Segoe UI', 9), anchor='w').pack(fill=tk.X, padx=12, pady=8)
            sector_buttons['__ungrouped__'] = ungrouped_btn
            ungrouped_btn.bind('<Button-1>', lambda e: select_sector('__ungrouped__', '未分组'))
            for child in ungrouped_btn.winfo_children():
                child.bind('<Button-1>', lambda e: select_sector('__ungrouped__', '未分组'))

    def _get_design_sectors_raw(design: dict) -> list[dict]:
        """获取设计稿的分区原始数据。"""
        sector_names = design.get('sectors', [])
        return [{'id': name, 'name': name} for name in sector_names]

    def render_designs(designs: list[dict], sector_filter: str = None, sector_label: str = '全部设计稿'):
        """渲染右侧设计稿网格。"""
        for widget in design_grid.winfo_children():
            widget.destroy()
        design_widgets.clear()

        # 按分组筛选
        if sector_filter is None:
            filtered = designs
        elif sector_filter == '__ungrouped__':
            filtered = [d for d in designs if not d.get('sectors')]
        else:
            filtered = [d for d in designs if sector_filter in d.get('sectors', []) or sector_filter in d.get('sector_ids', [])]

        status_var.set(f"{sector_label}: {len(filtered)} 个设计稿，已选 {len(selected_designs)} 个")

        if not filtered:
            tk.Label(design_grid, text="该分组下暂无设计稿", bg=COLORS['bg'], fg=COLORS['text_muted'],
                     font=('Segoe UI', 11)).pack(pady=60)
            return

        # 网格布局：每行 3 个
        cols = 3
        for idx, design in enumerate(filtered):
            row = idx // cols
            col = idx % cols
            cell = tk.Frame(design_grid, bg=COLORS['card'], highlightbackground=COLORS['border_light'],
                            highlightthickness=1, padx=8, pady=8)
            cell.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
            design_grid.grid_columnconfigure(col, weight=1, minsize=280)

            # 复选框 + 名称
            top_bar = tk.Frame(cell, bg=COLORS['card'])
            top_bar.pack(fill=tk.X)
            check_var = tk.BooleanVar(value=design.get('id', '') in selected_set)
            checkbox = tk.Checkbutton(top_bar, variable=check_var, bg=COLORS['card'],
                                      activebackground=COLORS['card'])
            checkbox.pack(side=tk.LEFT)

            def toggle_design(d=design, cv=check_var):
                """切换选中状态。"""
                if cv.get():
                    if d.get('id', '') not in selected_set:
                        selected_designs.append(d)
                        selected_set.add(d.get('id', ''))
                else:
                    if d.get('id', '') in selected_set:
                        selected_set.discard(d.get('id', ''))
                        selected_designs[:] = [x for x in selected_designs if x.get('id') != d.get('id')]
                status_var.set(f"{sector_label}: {len(filtered)} 个设计稿，已选 {len(selected_designs)} 个")

            checkbox.config(command=toggle_design)

            tk.Label(top_bar, text=design.get('name', '未命名')[:20], bg=COLORS['card'],
                     fg=COLORS['text_primary'], font=('Segoe UI', 9, 'bold'), anchor='w').pack(side=tk.LEFT, padx=(4, 0))

            # 缩略图区域
            thumb_frame = tk.Frame(cell, bg=COLORS['surface'], width=240, height=160)
            thumb_frame.pack(fill=tk.X, pady=(8, 0))
            thumb_frame.pack_propagate(False)

            thumb_label = tk.Label(thumb_frame, text="加载中...", bg=COLORS['surface'],
                                   fg=COLORS['text_muted'], font=('Segoe UI', 8))
            thumb_label.pack(expand=True)

            # 尺寸信息
            dims_text = f"{design.get('width', '?')}x{design.get('height', '?')}"
            if design.get('sectors'):
                dims_text += f"  |  {', '.join(design['sectors'][:2])}"
            tk.Label(cell, text=dims_text, bg=COLORS['card'], fg=COLORS['text_muted'],
                     font=('Segoe UI', 7), anchor='w').pack(fill=tk.X, pady=(4, 0))

            # 异步加载缩略图
            def load_thumbnail(url=design.get('url', ''), label=thumb_label, design_id=design.get('id', '')):
                """后台加载缩略图。"""
                if not url:
                    label.configure(text='无图片')
                    return

                def _download():
                    try:
                        img_data = _download_image_bytes(url, cookie)
                        img = Image.open(io.BytesIO(img_data))
                        img.thumbnail((240, 160))
                        photo = ImageTk.PhotoImage(img)
                        thumbnail_cache[url] = photo
                        win.after(0, lambda: _update_thumb(label, photo))
                    except Exception as e:
                        win.after(0, lambda: label.configure(text='加载失败'))

                threading.Thread(target=_download, daemon=True).start()

            def _update_thumb(label, photo):
                """更新缩略图标签。"""
                try:
                    label.configure(image=photo, text='')
                    label.image = photo
                except tk.TclError:
                    pass

            load_thumbnail()

            # 点击缩略图也可切换选中
            def on_thumb_click(e, d=design, cv=check_var):
                cv.set(not cv.get())
                toggle_design(d, cv)

            thumb_label.bind('<Button-1>', on_thumb_click)

            design_widgets.append({'widget': cell, 'design': design, 'checkbox_var': check_var})

    def select_all_visible():
        """全选当前可见设计稿。"""
        for dw in design_widgets:
            dw['checkbox_var'].set(True)
            did = dw['design'].get('id', '')
            if did not in selected_set:
                selected_designs.append(dw['design'])
                selected_set.add(did)
        status_var.set(f"已选 {len(selected_designs)} 个设计稿")

    def deselect_all_visible():
        """取消全选当前可见设计稿。"""
        for dw in design_widgets:
            dw['checkbox_var'].set(False)
            did = dw['design'].get('id', '')
            if did in selected_set:
                selected_set.discard(did)
                selected_designs[:] = [x for x in selected_designs if x.get('id') != did]
        status_var.set(f"已选 {len(selected_designs)} 个设计稿")

    # 工具栏下方的操作行
    select_bar = tk.Frame(win, bg=COLORS['bg'])
    select_bar.pack(fill=tk.X, padx=12, pady=(8, 0))
    ttk.Button(select_bar, text="全选", style='Small.TButton', command=select_all_visible).pack(side=tk.LEFT)
    ttk.Button(select_bar, text="取消全选", style='Small.TButton', command=deselect_all_visible).pack(side=tk.LEFT, padx=(8, 0))

    def _load_designs():
        """后台加载设计稿数据。"""
        try:
            result = _fetch_designs_api(cookie, project_id, team_id)
            win.after(0, lambda: _on_loaded(result))
        except Exception as e:
            win.after(0, lambda: _on_error(str(e)))

    def _on_loaded(result: dict):
        """设计稿加载完成。"""
        if result.get('status') != 'success':
            status_var.set(f"加载失败: {result.get('message', '未知错误')}")
            messagebox.showerror("错误", f"加载设计稿失败:\n{result.get('message', '')}", parent=win)
            return

        nonlocal all_designs_data
        all_designs_data = result.get('designs', [])
        sectors = result.get('sectors', [])
        total = result.get('total_designs', 0)
        status_var.set(f"共 {total} 个设计稿，已选 {len(selected_designs)} 个")

        render_sidebar(sectors)
        render_designs(all_designs_data, None, '全部设计稿')
        log_fn(f"已加载项目 [{project_name}] 的 {total} 个设计稿", 'success')

    def _on_error(msg: str):
        """加载失败。"""
        status_var.set(f"加载失败: {msg}")
        messagebox.showerror("错误", f"加载设计稿失败:\n{msg}", parent=win)

    # 启动加载
    threading.Thread(target=_load_designs, daemon=True).start()


def create_gui() -> None:
    """创建 Lanhu MCP 桌面控制台。"""
    bootstrap_tcl_tk_runtime()
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        flog("GUI 启动失败: 需要安装 tkinter", "error")
        if should_show_native_error_dialog():
            ctypes.windll.user32.MessageBoxW(0, "需要安装 tkinter", "错误", 0)
        return

    try:
        root = tk.Tk()
    except Exception as error:
        flog(f"Tkinter 窗口创建失败: {error}", 'error')
        if should_show_native_error_dialog():
            ctypes.windll.user32.MessageBoxW(0, f"GUI 启动失败:\n{error}", "错误", 0)
        return

    root.title("Lanhu MCP 控制台")
    icon_path = APP_DIR / 'icon.ico'
    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass
    center_window(root, 1360, 860)
    root.minsize(1060, 700)
    root.configure(bg=COLORS['bg'])

    # 主题样式统一由 ttk 接管，普通 tk 控件只保留必要颜色。
    apply_modern_style(root)
    # Tcl 字体名包含空格时需要加花括号，否则会被拆成错误参数。
    root.option_add("*Font", "{Segoe UI} 9")

    port_var = tk.StringVar(value="8000")
    cookie_var = tk.StringVar()
    account_var = tk.StringVar()
    project_status_var = tk.StringVar(value="登录后可读取当前账号项目")
    project_count_var = tk.StringVar(value="0 个项目")
    login_status_var = tk.StringVar(value="未登录")
    header_title_var = tk.StringVar(value="总览")
    header_desc_var = tk.StringVar(value="集中查看蓝湖账号、MCP 服务、项目和 AI 工具配置状态。")
    service_status_var = tk.StringVar(value="● 未运行")
    service_hint_var = tk.StringVar(value="请先登录蓝湖账号，然后启动 MCP 服务。")
    account_count_var = tk.StringVar(value="0 个账号")
    ide_count_var = tk.StringVar(value="0 / 0")
    overview_account_var = tk.StringVar(value="未登录")
    overview_service_var = tk.StringVar(value="未运行")
    overview_project_var = tk.StringVar(value="0 个项目")
    overview_tools_var = tk.StringVar(value=f"{len(MCP_TOOL_NAMES)} 个方法")
    overview_ide_var = tk.StringVar(value="0 / 0")
    runtime_var = tk.StringVar(value=app_runtime_label())
    package_status_var = tk.StringVar(value=compare_packaged_outputs() or "当前运行路径已记录在日志中")
    account_options: list[dict] = []
    full_cookie = load_cookie()
    is_refreshing_projects = False
    is_refreshing_profile = False
    window_focus_state = {"focused": True}
    project_rows_state: dict[str, object] = {"signature": None}
    account_rows_state: dict[str, object] = {"signature": None}
    page_transition_state: dict[str, object] = {"after_id": None, "step": 0}
    cookie_var.set(full_cookie)

    main = tk.Frame(root, bg=COLORS['bg'])
    main.pack(fill=tk.BOTH, expand=True)

    sidebar = tk.Frame(main, width=228, bg=COLORS['sidebar'])
    sidebar.pack(side=tk.LEFT, fill=tk.Y)
    sidebar.pack_propagate(False)

    content = tk.Frame(main, bg=COLORS['bg'])
    content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    bg_deco = tk.Canvas(content, bg=COLORS['bg'], height=1, highlightthickness=0, bd=0)
    bg_deco.place(relx=0, rely=0, relwidth=1, height=140)

    def draw_background_decor(event: object = None) -> None:
        bg_deco.delete("all")
        width = max(bg_deco.winfo_width(), 1)
        for index in range(0, width, 34):
            color = "#E8ECF2" if (index // 34) % 2 == 0 else "#EFF2F7"
            bg_deco.create_line(index, 0, index + 92, 140, fill=color, width=1)
        bg_deco.create_rectangle(0, 0, width, 140, outline="", fill="", stipple="gray75")

    bg_deco.bind("<Configure>", draw_background_decor)

    brand = tk.Frame(sidebar, bg=COLORS['sidebar'])
    brand.pack(fill=tk.X, padx=18, pady=(22, 20))
    brand_mark = tk.Frame(brand, bg=COLORS['sidebar'])
    brand_mark.pack(anchor='w', fill=tk.X)
    mark_box = tk.Frame(brand_mark, bg=COLORS['primary'], width=34, height=34)
    mark_box.pack(side=tk.LEFT)
    mark_box.pack_propagate(False)
    tk.Label(mark_box, text="L", fg="#FFFFFF", bg=COLORS['primary'], font=('Segoe UI', 15, 'bold')).pack(expand=True)
    tk.Label(
        brand_mark,
        text="Lanhu MCP",
        fg="#FFFFFF",
        bg=COLORS['sidebar'],
        font=('Segoe UI', 13, 'bold'),
    ).pack(side=tk.LEFT, padx=(10, 0))
    tk.Label(
        brand,
        text="设计还原与项目协作控制台",
        fg="#8CA0B8",
        bg=COLORS['sidebar'],
        font=('Segoe UI', 9),
    ).pack(anchor='w', pady=(3, 0))

    nav_host = tk.Frame(sidebar, bg=COLORS['sidebar'])
    nav_host.pack(fill=tk.X, padx=10)
    sidebar_footer = tk.Frame(sidebar, bg=COLORS['sidebar'])
    sidebar_footer.pack(side=tk.BOTTOM, fill=tk.X, padx=18, pady=18)
    tk.Label(
        sidebar_footer,
        text="当前状态",
        fg="#6CA0D9",
        bg=COLORS['sidebar'],
        font=('Segoe UI', 8, 'bold'),
    ).pack(anchor='w', pady=(0, 5))
    tk.Label(
        sidebar_footer,
        textvariable=login_status_var,
        fg="#B0C4DE",
        bg=COLORS['sidebar'],
        font=('Segoe UI', 9),
        wraplength=184,
        justify=tk.LEFT,
    ).pack(anchor='w')
    tk.Label(
        sidebar_footer,
        textvariable=package_status_var,
        fg="#7A8FA3",
        bg=COLORS['sidebar'],
        font=('Segoe UI', 8),
        wraplength=184,
        justify=tk.LEFT,
    ).pack(anchor='w', pady=(8, 0))

    sidebar_pulse = tk.Canvas(sidebar_footer, width=184, height=18, bg=COLORS['sidebar'], highlightthickness=0, bd=0)
    sidebar_pulse.pack(anchor='w', pady=(10, 0))
    pulse_step = {"value": 0}

    def animate_sidebar_pulse() -> None:
        if should_run_sidebar_pulse(root.state(), bool(window_focus_state["focused"])):
            pulse_step["value"] = (pulse_step["value"] + 1) % 36
            sidebar_pulse.delete("all")
            sidebar_pulse.create_line(0, 9, 184, 9, fill="#1A2E4A", width=2)
            start = pulse_step["value"] * 5
            sidebar_pulse.create_line(start % 184, 9, min((start % 184) + 34, 184), 9, fill=COLORS['primary'], width=2)
        root.after(animation_interval_ms("sidebar_pulse"), animate_sidebar_pulse)

    header = tk.Frame(content, bg=COLORS['bg'])
    header.pack(fill=tk.X, padx=24, pady=(22, 14))
    header_text = tk.Frame(header, bg=COLORS['bg'])
    header_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Label(
        header_text,
        textvariable=header_title_var,
        bg=COLORS['bg'],
        fg=COLORS['text_primary'],
        font=('Segoe UI', 20, 'bold'),
    ).pack(anchor='w')
    tk.Label(
        header_text,
        textvariable=header_desc_var,
        bg=COLORS['bg'],
        fg=COLORS['text_secondary'],
        font=('Segoe UI', 10),
    ).pack(anchor='w', pady=(4, 0))
    page_transition_bar = tk.Canvas(header_text, height=2, bg=COLORS['bg'], highlightthickness=0, bd=0)
    page_transition_bar.pack(fill=tk.X, pady=(10, 0))
    header_stats = tk.Frame(header, bg=COLORS['bg'])
    header_stats.pack(side=tk.RIGHT)
    header_stat_cells: list[tk.Frame] = []
    for stat_label, stat_var in (
        ("账号", account_count_var),
        ("项目", project_count_var),
        ("方法", tk.StringVar(value=str(len(MCP_TOOL_NAMES)))),
    ):
        stat_cell = tk.Frame(header_stats, bg=COLORS['card'], highlightbackground=COLORS['border_light'], highlightthickness=1)
        stat_cell.pack(side=tk.LEFT, padx=(8, 0))
        header_stat_cells.append(stat_cell)
        tk.Label(stat_cell, text=stat_label, bg=COLORS['card'], fg=COLORS['text_muted'], font=('Segoe UI', 8)).pack(padx=12, pady=(7, 0))
        tk.Label(stat_cell, textvariable=stat_var, bg="#FFFFFF", fg=COLORS['text_primary'], font=('Segoe UI', 10, 'bold')).pack(padx=12, pady=(1, 7))

    def layout_header(event: object = None) -> None:
        """根据窗口宽度调整顶部统计区位置。"""
        root_width = root.winfo_width()
        header_stats.pack_forget()
        if root_width < 1180:
            header_stats.pack(anchor='w', pady=(12, 0))
            return
        header_stats.pack(side=tk.RIGHT)

    root.bind("<Configure>", layout_header)

    page_shell = tk.Frame(content, bg=COLORS['bg'])
    page_shell.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 18))
    pages: dict[str, tk.Frame] = {}
    page_canvases: dict[str, tk.Canvas] = {}
    nav_buttons: dict[str, tk.Frame] = {}
    icon_images: dict[str, object] = {}
    avatar_images: dict[str, object] = {}

    def mark_window_focused(event: object = None) -> None:
        """记录窗口聚焦状态，供持续动画判断是否暂停。"""
        window_focus_state["focused"] = True

    def mark_window_blurred(event: object = None) -> None:
        """记录窗口失焦状态，暂停非必要的持续动画。"""
        window_focus_state["focused"] = False

    root.bind("<FocusIn>", mark_window_focused, add="+")
    root.bind("<FocusOut>", mark_window_blurred, add="+")

    def create_page(page_key: str) -> tk.Frame:
        """创建一个可滚动右侧页面容器。"""
        viewport = tk.Frame(page_shell, bg=COLORS['bg'])
        canvas = tk.Canvas(viewport, bg=COLORS['bg'], highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(viewport, orient=tk.VERTICAL, command=canvas.yview)
        page = tk.Frame(canvas, bg=COLORS['bg'])
        window_id = canvas.create_window((0, 0), window=page, anchor='nw')

        def _sync_scroll_region(event: object = None) -> None:
            """同步滚动区域，确保窗口缩放后仍可访问全部内容。"""
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _sync_page_width(event: object) -> None:
            """让页面宽度跟随可视区域变化。"""
            canvas.itemconfigure(window_id, width=event.width)

        def _on_mousewheel(event: object) -> None:
            """支持鼠标滚轮滚动页面。"""
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        page.bind("<Configure>", _sync_scroll_region)
        canvas.bind("<Configure>", _sync_page_width)
        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        pages[page_key] = viewport
        page_canvases[page_key] = canvas
        return page

    def create_lucide_icon(
        parent: tk.Misc,
        icon_name: str,
        color: str,
        size: int = 18,
        bg: str = COLORS['card'],
    ) -> tk.Canvas:
        """用 Tk 画布生成内置线性图标，避免打包依赖外部 SVG 文件。"""
        cache_key = f"{icon_name}:{color}:{size}:{bg}"
        icon_images[cache_key] = icon_images.get(cache_key, cache_key)
        canvas = tk.Canvas(
            parent,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )
        stroke = max(1, size // 9)

        def line(points: list[int]) -> None:
            """绘制图标线段。"""
            canvas.create_line(*points, fill=color, width=stroke, capstyle=tk.ROUND, joinstyle=tk.ROUND)

        def oval(box: tuple[int, int, int, int]) -> None:
            """绘制图标圆形轮廓。"""
            canvas.create_oval(*box, outline=color, width=stroke)

        def rect(box: tuple[int, int, int, int]) -> None:
            """绘制图标矩形轮廓。"""
            canvas.create_rectangle(*box, outline=color, width=stroke)

        if icon_name in ("overview", "layout-dashboard"):
            rect((3, 3, size // 2 - 1, size // 2 - 1))
            rect((size // 2 + 2, 3, size - 3, size // 2 + 4))
            rect((3, size // 2 + 2, size // 2 + 3, size - 3))
            rect((size // 2 + 4, size // 2 + 6, size - 3, size - 3))
        elif icon_name in ("service", "server-cog", "settings"):
            oval((4, 4, size - 4, size - 4))
            oval((size // 2 - 3, size // 2 - 3, size // 2 + 3, size // 2 + 3))
            line([size // 2, 1, size // 2, 5])
            line([size // 2, size - 5, size // 2, size - 1])
            line([1, size // 2, 5, size // 2])
            line([size - 5, size // 2, size - 1, size // 2])
        elif icon_name in ("tools", "bot"):
            rect((4, 7, size - 4, size - 3))
            line([size // 2, 3, size // 2, 7])
            line([7, size - 3, 7, size - 1])
            line([size - 7, size - 3, size - 7, size - 1])
            oval((7, 10, 9, 12))
            oval((size - 9, 10, size - 7, 12))
        elif icon_name in ("account", "user", "shield-check"):
            oval((size // 2 - 4, 4, size // 2 + 4, 12))
            line([5, size - 4, 7, size - 8, size // 2, size - 10, size - 7, size - 8, size - 5, size - 4])
        elif icon_name in ("projects", "folder-kanban"):
            line([3, 6, 7, 6, 9, 8, size - 3, 8])
            rect((3, 7, size - 3, size - 3))
            line([6, 12, size - 6, 12])
        elif icon_name in ("logs", "scroll-text"):
            rect((5, 3, size - 4, size - 3))
            line([8, 8, size - 7, 8])
            line([8, 12, size - 7, 12])
            line([8, 16, size - 9, 16])
        elif icon_name in ("activity", "pulse"):
            line([2, size // 2, 6, size // 2, 9, 5, size - 9, size - 5, size - 6, size // 2, size - 2, size // 2])
        elif icon_name in ("database", "layers"):
            oval((4, 3, size - 4, 8))
            line([4, 6, 4, size - 5])
            line([size - 4, 6, size - 4, size - 5])
            oval((4, size - 8, size - 4, size - 3))
            line([4, size // 2, size - 4, size // 2])
        elif icon_name in ("login", "key-round"):
            oval((3, 6, 10, 13))
            line([10, 10, size - 3, 10])
            line([size - 7, 10, size - 7, 14])
            line([size - 4, 10, size - 4, 13])
        elif icon_name in ("play",):
            line([6, 4, size - 4, size // 2, 6, size - 4, 6, 4])
        elif icon_name in ("stop", "square"):
            rect((5, 5, size - 5, size - 5))
        elif icon_name in ("copy", "file-json"):
            rect((6, 3, size - 3, size - 6))
            rect((3, 6, size - 6, size - 3))
        elif icon_name in ("list-checks",):
            line([4, 6, 6, 8, 9, 4])
            line([11, 6, size - 3, 6])
            line([4, size // 2, 6, size // 2 + 2, 9, size // 2 - 2])
            line([11, size // 2, size - 3, size // 2])
            line([4, size - 6, 6, size - 4, 9, size - 8])
            line([11, size - 6, size - 3, size - 6])
        elif icon_name in ("wand-sparkles",):
            line([5, size - 5, size - 5, 5])
            line([size - 7, 3, size - 7, 7])
            line([size - 9, 5, size - 5, 5])
            line([5, 4, 5, 8])
            line([3, 6, 7, 6])
        elif icon_name in ("plug-zap",):
            rect((6, 7, size - 6, size - 4))
            line([8, 3, 8, 7])
            line([size - 8, 3, size - 8, 7])
            line([size // 2, size - 4, size // 2, size - 1])
            line([size - 6, size // 2, size - 10, size // 2 + 4, size - 7, size // 2 + 4])
        elif icon_name in ("check", "check-circle"):
            oval((3, 3, size - 3, size - 3))
            line([6, size // 2, size // 2 - 1, size - 7, size - 5, 7])
        elif icon_name in ("logout", "log-out"):
            rect((3, 4, size - 8, size - 4))
            line([size - 11, size // 2, size - 3, size // 2])
            line([size - 7, size // 2 - 4, size - 3, size // 2, size - 7, size // 2 + 4])
        elif icon_name in ("refresh", "refresh-cw"):
            oval((4, 4, size - 4, size - 4))
            line([size - 7, 4, size - 4, 4, size - 4, 7])
        elif icon_name in ("trash", "trash-2"):
            line([5, 6, size - 5, 6])
            rect((7, 7, size - 7, size - 3))
            line([8, 4, size - 8, 4])
        elif icon_name in ("external", "external-link"):
            rect((4, 7, size - 7, size - 4))
            line([size - 10, 4, size - 4, 4, size - 4, 10])
            line([size - 4, 4, size - 11, 11])
        else:
            oval((4, 4, size - 4, size - 4))
        return canvas

    def make_icon_label(parent: tk.Misc, icon_name: str, color: str) -> tk.Canvas:
        """创建只显示图标的标签控件。"""
        return create_lucide_icon(parent, icon_name, color, 18, COLORS['card'])

    def make_card(parent: tk.Misc, title: str, icon_name: str, padding: int = 16) -> tk.Frame:
        """创建 TDesign 风格卡片容器。"""
        card = tk.Frame(
            parent,
            bg=COLORS['card'],
            highlightbackground=COLORS['border_light'],
            highlightcolor=COLORS['primary'],
            highlightthickness=1,
            bd=0,
        )

        header_frame = tk.Frame(card, bg=COLORS['card'])
        header_frame.pack(fill=tk.X, padx=padding, pady=(padding, SPACING['2']))

        icon_canvas = make_icon_label(header_frame, icon_name, COLORS['primary'])
        icon_canvas.pack(side=tk.LEFT)

        tk.Label(
            header_frame,
            text=title,
            bg=COLORS['card'],
            fg=COLORS['text_primary'],
            font=(FONT['family'], FONT['sizes']['base'], 'bold'),
        ).pack(side=tk.LEFT, padx=(SPACING['2'], 0))

        separator = tk.Frame(card, bg=COLORS['border_light'], height=1)
        separator.pack(fill=tk.X, padx=padding, pady=(0, SPACING['2']))

        body = ttk.Frame(card, style='Card.TFrame')
        body.pack(fill=tk.BOTH, expand=True, padx=padding, pady=(0, padding))

        def on_enter(event):
            card.config(highlightbackground=COLORS['primary'], highlightthickness=2)

        def on_leave(event):
            card.config(highlightbackground=COLORS['border_light'], highlightthickness=1)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        setattr(card, "body", body)
        setattr(card, "header", header_frame)
        setattr(card, "separator", separator)
        return card

    def make_metric_tile(parent: tk.Misc, label: str, value_var: object, accent: str) -> tk.Frame:
        """创建 TDesign 风格指标块。"""
        tile = tk.Frame(
            parent,
            bg=COLORS['card'],
            highlightbackground=COLORS['border_light'],
            highlightthickness=1,
        )

        accent_bar = tk.Frame(tile, bg=accent, width=3)
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        content_frame = tk.Frame(tile, bg=COLORS['card'])
        content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=SPACING['3'], pady=SPACING['3'])

        tk.Label(
            content_frame,
            text=label,
            bg=COLORS['card'],
            fg=COLORS['text_muted'],
            font=(FONT['family'], FONT['sizes']['xs'])
        ).pack(anchor='w')

        tk.Label(
            content_frame,
            textvariable=value_var,
            bg=COLORS['card'],
            fg=COLORS['text_primary'],
            font=(FONT['family'], FONT['sizes']['xl'], 'bold')
        ).pack(anchor='w', pady=(SPACING['1'], 0))

        def on_enter(event):
            tile.config(highlightbackground=accent, highlightthickness=2)
            tile.config(bg=COLORS['card_hover'])
            content_frame.config(bg=COLORS['card_hover'])
            for child in content_frame.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=COLORS['card_hover'])

        def on_leave(event):
            tile.config(highlightbackground=COLORS['border_light'], highlightthickness=1)
            tile.config(bg=COLORS['card'])
            content_frame.config(bg=COLORS['card'])
            for child in content_frame.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=COLORS['card'])

        tile.bind("<Enter>", on_enter)
        tile.bind("<Leave>", on_leave)

        return tile

    def make_overview_tile(
        parent: tk.Misc,
        title: str,
        value_var: object,
        detail: str,
        icon_name: str,
        accent: str,
    ) -> tk.Frame:
        """创建 TDesign 风格总览指标块。"""
        tile = tk.Frame(
            parent,
            bg=COLORS['card'],
            highlightbackground=COLORS['border_light'],
            highlightthickness=1,
        )

        top = tk.Frame(tile, bg=COLORS['card'])
        top.pack(fill=tk.X, padx=SPACING['4'], pady=(SPACING['4'], SPACING['2']))

        icon_shell = tk.Frame(top, bg=COLORS['primary_light'], width=40, height=40)
        icon_shell.pack(side=tk.LEFT)
        icon_shell.pack_propagate(False)
        create_lucide_icon(icon_shell, icon_name, accent, 24, COLORS['primary_light']).pack(expand=True)

        tk.Label(
            top,
            text=title,
            bg=COLORS['card'],
            fg=COLORS['text_secondary'],
            font=(FONT['family'], FONT['sizes']['sm'], 'bold')
        ).pack(side=tk.LEFT, padx=(SPACING['3'], 0))

        tk.Label(
            tile,
            textvariable=value_var,
            bg=COLORS['card'],
            fg=COLORS['text_primary'],
            font=(FONT['family'], FONT['sizes']['4xl'], 'bold'),
        ).pack(anchor='w', padx=SPACING['4'])

        tk.Label(
            tile,
            text=detail,
            bg=COLORS['card'],
            fg=COLORS['text_muted'],
            font=(FONT['family'], FONT['sizes']['xs']),
            wraplength=220,
            justify=tk.LEFT,
        ).pack(anchor='w', padx=SPACING['4'], pady=(SPACING['2'], SPACING['4']))

        def on_enter(event):
            tile.config(highlightbackground=accent, highlightthickness=2)
            tile.config(bg=COLORS['card_hover'])
            for child in tile.winfo_children():
                if isinstance(child, tk.Frame):
                    child.config(bg=COLORS['card_hover'])
                elif isinstance(child, tk.Label):
                    child.config(bg=COLORS['card_hover'])

        def on_leave(event):
            tile.config(highlightbackground=COLORS['border_light'], highlightthickness=1)
            tile.config(bg=COLORS['card'])
            for child in tile.winfo_children():
                if isinstance(child, tk.Frame):
                    child.config(bg=COLORS['card'])
                elif isinstance(child, tk.Label):
                    child.config(bg=COLORS['card'])

        tile.bind("<Enter>", on_enter)
        tile.bind("<Leave>", on_leave)

        return tile

    def make_empty_state(parent: tk.Misc, icon_name: str, title: str, detail: str) -> tk.Frame:
        """创建 TDesign 风格空状态块。"""
        state = tk.Frame(
            parent,
            bg=COLORS['card'],
            highlightbackground=COLORS['border_light'],
            highlightthickness=1,
        )
        state.pack(fill=tk.X)

        state_inner = tk.Frame(state, bg=COLORS['card'])
        state_inner.pack(fill=tk.X, padx=SPACING['6'], pady=SPACING['8'])

        create_lucide_icon(
            state_inner,
            icon_name,
            COLORS['text_disabled'],
            48,
            COLORS['card']
        ).pack(side=tk.LEFT, padx=(0, SPACING['4']))

        text_frame = tk.Frame(state_inner, bg=COLORS['card'])
        text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            text_frame,
            text=title,
            bg=COLORS['card'],
            fg=COLORS['text_primary'],
            font=(FONT['family'], FONT['sizes']['xl'], 'bold')
        ).pack(anchor='w')

        tk.Label(
            text_frame,
            text=detail,
            bg=COLORS['card'],
            fg=COLORS['text_muted'],
            font=(FONT['family'], FONT['sizes']['sm']),
            wraplength=760,
            justify=tk.LEFT
        ).pack(anchor='w', pady=(SPACING['2'], 0))

        return state

    def pack_responsive_pair(
        host: tk.Misc,
        left: tk.Widget,
        right: tk.Widget,
        breakpoint: int = 980,
    ) -> None:
        """根据窗口宽度在双栏和单栏之间切换。"""
        layout_state = {"mode": ""}

        def _apply_layout(event: object = None) -> None:
            """响应窗口尺寸变化重排两个卡片。"""
            host_width = host.winfo_width() or root.winfo_width()
            target_mode = "single" if host_width < breakpoint else "double"
            if layout_state["mode"] == target_mode:
                return
            layout_state["mode"] = target_mode
            left.pack_forget()
            right.pack_forget()
            if target_mode == "single":
                left.pack(fill=tk.X, expand=False, pady=(0, 12))
                right.pack(fill=tk.X, expand=False)
                return
            left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
            right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        host.bind("<Configure>", _apply_layout)
        root.after(50, _apply_layout)

    def card_body(card: tk.Frame) -> ttk.Frame:
        """返回卡片内容区。"""
        return getattr(card, "body")

    def set_nav_active(page_key: str) -> None:
        """更新左侧导航选中态 - 优化版。"""
        for key, button in nav_buttons.items():
            is_active = key == page_key
            button.is_active = is_active
            
            # 设置背景色
            if is_active:
                bg_color = COLORS['sidebar_active']
                fg_color = '#FFFFFF'
                indicator_color = COLORS['primary']
            else:
                bg_color = COLORS['sidebar']
                fg_color = COLORS['sidebar_text']
                indicator_color = COLORS['sidebar']
            
            # 更新按钮背景
            button.config(bg=bg_color)
            
            # 更新左侧指示条
            indicator = getattr(button, "indicator", None)
            if indicator:
                indicator.config(bg=indicator_color)
            
            # 更新所有子控件
            for child in button.winfo_children():
                child.config(bg=bg_color)
                if isinstance(child, tk.Label):
                    child.config(fg=fg_color)
                elif hasattr(child, 'config'):
                    # Canvas图标需要特殊处理
                    try:
                        child.config(bg=bg_color)
                    except:
                        pass

    def start_page_transition() -> None:
        """播放短促页面切换反馈，避免主内容硬切时缺少响应感。"""
        after_id = page_transition_state.get("after_id")
        if after_id:
            try:
                root.after_cancel(str(after_id))
            except tk.TclError:
                pass
        page_transition_state["step"] = 0
        page_transition_bar.delete("all")

        def _tick() -> None:
            """推进页面切换进度线。"""
            step = int(page_transition_state["step"])
            width = max(page_transition_bar.winfo_width(), 1)
            if step >= 4:
                page_transition_bar.delete("all")
                page_transition_state["after_id"] = None
                return
            page_transition_bar.delete("all")
            progress_width = int(width * ((step + 1) / 4))
            page_transition_bar.create_rectangle(0, 0, progress_width, 2, outline="", fill=COLORS['primary'])
            page_transition_state["step"] = step + 1
            page_transition_state["after_id"] = root.after(animation_interval_ms("page_transition"), _tick)

        _tick()

    def show_page(page_key: str) -> None:
        """切换主内容页面。"""
        page_meta = {
            "overview": ("总览", "集中查看蓝湖账号、MCP 服务、项目和 AI 工具配置状态。"),
            "service": ("服务", "登录蓝湖后启动 MCP 服务，启动成功后显示全部可用方法。"),
            "projects": ("项目", "读取当前蓝湖账号可访问的项目，便于复制项目链接给 AI 使用。"),
            "tools": ("AI 工具", "自动识别 Codex、Claude、Mimo、Cursor、Trae 等工具并写入 MCP 配置。"),
            "account": ("账号", "蓝湖登录信息集中管理，支持多用户保存、切换和退出。"),
            "logs": ("日志", "查看服务输出、登录诊断和配置写入记录。"),
        }
        for page in pages.values():
            page.pack_forget()
        pages[page_key].pack(fill=tk.BOTH, expand=True)
        page_canvases[page_key].yview_moveto(0)
        header_title_var.set(page_meta[page_key][0])
        header_desc_var.set(page_meta[page_key][1])
        set_nav_active(page_key)
        start_page_transition()

    nav_items = [
        ("overview", "layout-dashboard", "总览"),
        ("service", "service", "服务"),
        ("projects", "projects", "项目"),
        ("tools", "tools", "AI 工具"),
        ("account", "account", "账号"),
        ("logs", "logs", "日志"),
    ]
    
    # 菜单标题
    tk.Label(
        nav_host,
        text="导航",
        anchor='w',
        fg="#8EA0B8",
        bg=COLORS['sidebar'],
        font=(FONT['family'], FONT['sizes']['xs'], 'bold'),
    ).pack(fill=tk.X, padx=SPACING['3'], pady=(0, SPACING['2']))
    
    for key, icon_name, title in nav_items:
        # 导航按钮容器
        nav_button = tk.Frame(
            nav_host,
            bg=COLORS['sidebar'],
            cursor='hand2',
        )
        nav_button.pack(fill=tk.X, pady=SPACING['1'])
        
        # 左侧选中指示条
        nav_indicator = tk.Frame(nav_button, width=3, bg=COLORS['sidebar'])
        nav_indicator.pack(side=tk.LEFT, fill=tk.Y, padx=(0, SPACING['2']))
        setattr(nav_button, "indicator", nav_indicator)
        
        # 图标
        nav_icon = create_lucide_icon(
            nav_button, 
            icon_name, 
            COLORS['sidebar_text'], 
            18, 
            COLORS['sidebar']
        )
        nav_icon.pack(side=tk.LEFT, padx=(SPACING['2'], SPACING['2']), pady=SPACING['3'])
        
        # 文字标签
        nav_label = tk.Label(
            nav_button,
            text=title,
            anchor='w',
            bg=COLORS['sidebar'],
            fg=COLORS['sidebar_text'],
            cursor='hand2',
            font=(FONT['family'], FONT['sizes']['base'], 'bold'),
        )
        nav_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=SPACING['3'])
        
        # hover效果
        def on_enter_nav(event, button=nav_button, icon=nav_icon, label=nav_label):
            if not getattr(button, 'is_active', False):
                button.config(bg=COLORS['sidebar_hover'])
                icon.config(bg=COLORS['sidebar_hover'])
                label.config(bg=COLORS['sidebar_hover'])
        
        def on_leave_nav(event, button=nav_button, icon=nav_icon, label=nav_label):
            if not getattr(button, 'is_active', False):
                button.config(bg=COLORS['sidebar'])
                icon.config(bg=COLORS['sidebar'])
                label.config(bg=COLORS['sidebar'])
        
        nav_button.bind("<Enter>", on_enter_nav)
        nav_button.bind("<Leave>", on_leave_nav)
        nav_icon.bind("<Enter>", on_enter_nav)
        nav_icon.bind("<Leave>", on_leave_nav)
        nav_label.bind("<Enter>", on_enter_nav)
        nav_label.bind("<Leave>", on_leave_nav)
        
        # 点击事件
        nav_button.bind("<Button-1>", lambda event, page_key=key: show_page(page_key))
        nav_icon.bind("<Button-1>", lambda event, page_key=key: show_page(page_key))
        nav_label.bind("<Button-1>", lambda event, page_key=key: show_page(page_key))
        
        nav_buttons[key] = nav_button

    overview_page = create_page("overview")
    service_page = create_page("service")
    projects_page = create_page("projects")
    tools_page = create_page("tools")
    account_page = create_page("account")
    logs_page = create_page("logs")

    # 总览页：作为默认入口，把常用状态和动作集中在第一屏。
    overview_hero = tk.Frame(overview_page, bg=COLORS['primary'], highlightbackground=COLORS['primary_active'], highlightthickness=1)
    overview_hero.pack(fill=tk.X)
    overview_hero_inner = tk.Frame(overview_hero, bg=COLORS['primary'])
    overview_hero_inner.pack(fill=tk.X, padx=22, pady=20)
    overview_hero_text = tk.Frame(overview_hero_inner, bg=COLORS['primary'])
    overview_hero_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Label(
        overview_hero_text,
        text="Lanhu MCP 工作台",
        bg=COLORS['primary'],
        fg="#FFFFFF",
        font=('Segoe UI', 20, 'bold'),
    ).pack(anchor='w')
    tk.Label(
        overview_hero_text,
        text="登录蓝湖账号后启动服务，把项目、设计稿、切图和团队消息交给 AI IDE 直接调用。",
        bg=COLORS['primary'],
        fg="#D0E0FF",
        font=('Segoe UI', 10),
        wraplength=760,
        justify=tk.LEFT,
    ).pack(anchor='w', pady=(6, 0))
    overview_runtime = tk.Frame(overview_hero_text, bg=COLORS['primary_active'])
    overview_runtime.pack(fill=tk.X, pady=(14, 0))
    tk.Label(
        overview_runtime,
        textvariable=runtime_var,
        bg=COLORS['primary_active'],
        fg="#C0D8FF",
        font=('Consolas', 8),
        wraplength=760,
        justify=tk.LEFT,
    ).pack(anchor='w', padx=12, pady=8)
    overview_actions = tk.Frame(overview_hero_inner, bg=COLORS['primary'])
    overview_actions.pack(side=tk.RIGHT, padx=(18, 0))

    overview_login_btn = ttk.Button(overview_actions, text="添加账号", style='Primary.TButton', width=14)
    overview_login_btn.pack(fill=tk.X, pady=(0, 8))
    add_button_hover_effect(overview_login_btn)

    overview_start_btn = ttk.Button(overview_actions, text="启动服务", style='Success.TButton', width=14)
    overview_start_btn.pack(fill=tk.X, pady=(0, 8))
    add_button_hover_effect(overview_start_btn)

    overview_config_btn = ttk.Button(overview_actions, text="配置 AI 工具", style='Ghost.TButton', width=14)
    overview_config_btn.pack(fill=tk.X)
    add_button_hover_effect(overview_config_btn)

    overview_metrics = tk.Frame(overview_page, bg=COLORS['bg'])
    overview_metrics.pack(fill=tk.X, pady=(14, 0))
    metric_specs = (
        ("账号", overview_account_var, "多账号可切换，服务启动前会强制检查登录态。", "user", COLORS['primary']),
        ("服务", overview_service_var, "HTTP MCP 服务启动后可被 Codex、Claude、Mimo 等工具调用。", "activity", COLORS['success']),
        ("项目", overview_project_var, "自动接口、登录缓存和手动链接三路合并项目。", "folder-kanban", COLORS['accent_warm']),
        ("方法", overview_tools_var, "动态扫描当前服务注册的全部 MCP 方法。", "list-checks", COLORS['accent']),
    )
    for index, (title, value_var, detail, icon_name, accent) in enumerate(metric_specs):
        tile = make_overview_tile(overview_metrics, title, value_var, detail, icon_name, accent)
        tile.grid(row=0, column=index, sticky='nsew', padx=(0 if index == 0 else 12, 0))
        overview_metrics.columnconfigure(index, weight=1)

    overview_main = tk.Frame(overview_page, bg=COLORS['bg'])
    overview_main.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
    overview_left = make_card(overview_main, "下一步操作", "wand-sparkles")
    overview_right = make_card(overview_main, "诊断与能力", "database")
    pack_responsive_pair(overview_main, overview_left, overview_right)
    overview_left_body = card_body(overview_left)
    overview_right_body = card_body(overview_right)
    quick_rows = [
        ("完成蓝湖登录", "添加或切换蓝湖账号，登录成功后才能启动服务。", "account"),
        ("刷新项目列表", "项目页会尝试接口、登录缓存和本地手动链接三种来源。", "projects"),
        ("写入 AI 工具配置", "检测 Codex、Claude、Mimo、Cursor、Trae、Windsurf 等常见开发工具。", "tools"),
        ("查看服务日志", "启动失败、登录诊断和配置结果都会写到日志页。", "logs"),
    ]
    for row_index, (title, detail, target_page) in enumerate(quick_rows):
        row = tk.Frame(overview_left_body, bg=COLORS['surface'], highlightbackground=COLORS['border_light'], highlightthickness=1)
        row.pack(fill=tk.X, pady=(0 if row_index == 0 else 8, 0))
        row_inner = tk.Frame(row, bg=COLORS['surface'])
        row_inner.pack(fill=tk.X, padx=12, pady=10)
        tk.Label(row_inner, text=title, bg=COLORS['surface'], fg=COLORS['text_primary'], font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        tk.Label(row_inner, text=detail, bg=COLORS['surface'], fg=COLORS['text_muted'], font=('Segoe UI', 8), wraplength=520, justify=tk.LEFT).pack(anchor='w', pady=(3, 0))
        def _make_row_hover(row_frame, inner_frame):
            def on_enter(e):
                row_frame.config(bg=COLORS['primary_light'], highlightbackground=COLORS['primary'])
                inner_frame.config(bg=COLORS['primary_light'])
                for c in inner_frame.winfo_children():
                    if isinstance(c, tk.Label):
                        bg_c = COLORS['primary_light']
                        fg_c = COLORS['primary'] if c.cget('font').split()[-1] == 'bold' else COLORS['text_primary']
                        c.config(bg=bg_c, fg=fg_c)
            def on_leave(e):
                row_frame.config(bg=COLORS['surface'], highlightbackground=COLORS['border_light'])
                inner_frame.config(bg=COLORS['surface'])
                for c in inner_frame.winfo_children():
                    if isinstance(c, tk.Label):
                        c.config(bg=COLORS['surface'], fg=COLORS['text_primary'] if c.cget('font').split()[-1] == 'bold' else COLORS['text_muted'])
            row_frame.bind("<Enter>", on_enter)
            row_frame.bind("<Leave>", on_leave)
        _make_row_hover(row, row_inner)
        row.bind("<Button-1>", lambda event, page_key=target_page: show_page(page_key))
        row_inner.bind("<Button-1>", lambda event, page_key=target_page: show_page(page_key))

    tk.Label(
        overview_right_body,
        textvariable=package_status_var,
        bg=COLORS['card'],
        fg=COLORS['warning'] if "注意" in package_status_var.get() else COLORS['text_secondary'],
        font=('Segoe UI', 9, 'bold'),
        wraplength=520,
        justify=tk.LEFT,
    ).pack(anchor='w')
    tk.Label(
        overview_right_body,
        textvariable=overview_ide_var,
        bg=COLORS['card'],
        fg=COLORS['text_primary'],
        font=('Segoe UI', 16, 'bold'),
    ).pack(anchor='w', pady=(12, 2))
    tk.Label(
        overview_right_body,
        text="已识别 AI 开发工具数量。点击 AI 工具页可查看每个工具的安装路径、配置路径和写入结果。",
        bg=COLORS['card'],
        fg=COLORS['text_muted'],
        font=('Segoe UI', 8),
        wraplength=520,
        justify=tk.LEFT,
    ).pack(anchor='w')
    method_groups_frame = tk.Frame(overview_right_body, bg=COLORS['card'])
    method_groups_frame.pack(fill=tk.X, pady=(14, 0))
    for group_index, (group_name, group_tools) in enumerate(group_mcp_tools(MCP_TOOL_NAMES).items()):
        group_chip = tk.Frame(method_groups_frame, bg=COLORS['primary_light'])
        group_chip.pack(side=tk.LEFT, padx=(0 if group_index == 0 else 8, 0), pady=(0, 8))
        tk.Label(
            group_chip,
            text=f"{group_name} {len(group_tools)}",
            bg=COLORS['primary_light'],
            fg=COLORS['primary'],
            font=('Segoe UI', 8, 'bold'),
            padx=9,
            pady=4,
        ).pack()

    overview_metric_layout = {"mode": ""}

    def layout_overview_metrics(event: object = None) -> None:
        """根据窗口宽度重排总览指标卡。"""
        mode = "two" if root.winfo_width() < 1180 else "four"
        if overview_metric_layout["mode"] == mode:
            return
        overview_metric_layout["mode"] = mode
        tiles = list(overview_metrics.winfo_children())
        for tile in tiles:
            tile.grid_forget()
        columns = 2 if mode == "two" else 4
        for index, tile in enumerate(tiles):
            row = index // columns
            col = index % columns
            tile.grid(row=row, column=col, sticky='nsew', padx=(0 if col == 0 else 12, 0), pady=(0 if row == 0 else 12, 0))
        for col in range(4):
            overview_metrics.columnconfigure(col, weight=1 if col < columns else 0)

    root.bind("<Configure>", layout_overview_metrics, add="+")
    root.after(80, layout_overview_metrics)

    # 日志页需要先创建，后续所有回调都会写日志。
    log_card = make_card(logs_page, "运行日志", "scroll-text", padding=12)
    log_card.pack(fill=tk.BOTH, expand=True)
    log_body = card_body(log_card)
    log_toolbar = ttk.Frame(log_body, style='Card.TFrame')
    log_toolbar.pack(fill=tk.X, pady=(0, 10))
    ttk.Label(
        log_toolbar,
        text="日志会自动滚动到底部",
        style='Hint.TLabel',
        background=COLORS['card'],
    ).pack(side=tk.LEFT)
    clear_log_btn = ttk.Button(log_toolbar, text="清空", style='Small.TButton', width=12)
    clear_log_btn.pack(side=tk.RIGHT)
    log_container = ttk.Frame(log_body, style='Log.TFrame')
    log_container.pack(fill=tk.BOTH, expand=True)
    log_scrollbar = tk.Scrollbar(
        log_container,
        bg=COLORS['log_bg'],
        troughcolor=COLORS['log_bg'],
        activebackground=COLORS['text_muted'],
        highlightthickness=0,
        relief='flat',
    )
    log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    log_text = tk.Text(
        log_container,
        font=('Consolas', 9),
        bg=COLORS['log_bg'],
        fg=COLORS['log_text'],
        insertbackground=COLORS['log_text'],
        selectbackground=COLORS['primary'],
        wrap=tk.WORD,
        state=tk.DISABLED,
        padx=12,
        pady=10,
        relief='flat',
        borderwidth=0,
        highlightthickness=0,
        yscrollcommand=log_scrollbar.set,
    )
    log_scrollbar.config(command=log_text.yview)
    log_text.pack(fill=tk.BOTH, expand=True)
    log_text.tag_configure('timestamp', foreground=COLORS['text_muted'])
    log_text.tag_configure('info', foreground='#93C5FD')
    log_text.tag_configure('success', foreground='#86EFAC')
    log_text.tag_configure('error', foreground='#FCA5A5')
    log_text.tag_configure('warn', foreground='#FCD34D')
    log_text.tag_configure('server', foreground='#C4B5FD')

    def log(msg: str, level: str = 'info') -> None:
        """写入界面日志。"""
        ts = datetime.now().strftime("%H:%M:%S")
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, f"[{ts}] ", 'timestamp')
        log_text.insert(tk.END, f"{msg}\n", level)
        log_text.see(tk.END)
        log_text.config(state=tk.DISABLED)

    def do_clear_log() -> None:
        """清空日志面板。"""
        log_text.config(state=tk.NORMAL)
        log_text.delete(1.0, tk.END)
        log_text.config(state=tk.DISABLED)
        log("日志已清空", 'info')

    clear_log_btn.config(command=do_clear_log)

    def on_server_output(line: str) -> None:
        """把服务端输出转到日志面板。"""
        root.after(0, lambda l=line: log(f"[server] {l}", 'server'))

    def on_server_error(err: str) -> None:
        """把服务端错误转到日志面板。"""
        root.after(0, lambda e=err: log(f"[ERROR] {e}", 'error'))

    # 服务页
    service_top = tk.Frame(service_page, bg=COLORS['bg'])
    service_top.pack(fill=tk.X)
    status_card = make_card(service_top, "服务状态", "server-cog")
    method_card = make_card(service_top, f"支持的方法 ({len(MCP_TOOL_NAMES)})", "list-checks")
    pack_responsive_pair(service_top, status_card, method_card)
    status_body = card_body(status_card)
    method_body = card_body(method_card)

    service_status_row = ttk.Frame(status_body, style='Card.TFrame')
    service_status_row.pack(fill=tk.X)
    status_lbl = ttk.Label(service_status_row, textvariable=service_status_var, style='StatusError.TLabel')
    status_lbl.pack(side=tk.LEFT)
    ttk.Label(
        service_status_row,
        text="端口",
        style='TLabel',
        background=COLORS['card'],
    ).pack(side=tk.LEFT, padx=(24, 6))
    port_entry = ttk.Entry(service_status_row, textvariable=port_var, width=8, font=(FONT['mono'], FONT['sizes']['md'], 'bold'))
    port_entry.pack(side=tk.LEFT)
    add_entry_focus_effect(port_entry)

    service_actions = ttk.Frame(status_body, style='Card.TFrame')
    service_actions.pack(fill=tk.X, pady=(18, 0))
    
    start_btn = ttk.Button(service_actions, text="启动服务", style='Primary.TButton', width=15)
    start_btn.pack(side=tk.LEFT)
    add_button_hover_effect(start_btn)
    
    stop_btn = ttk.Button(service_actions, text="停止", style='Danger.TButton', width=10, state=tk.DISABLED)
    stop_btn.pack(side=tk.LEFT, padx=(10, 0))
    add_button_hover_effect(stop_btn)
    
    open_btn = ttk.Button(
        service_actions,
        text="打开",
        style='Small.TButton',
        width=13,
        command=lambda: webbrowser.open(f"http://localhost:{port_var.get()}/"),
    )
    open_btn.pack(side=tk.LEFT, padx=(10, 0))
    add_button_hover_effect(open_btn)
    ttk.Label(
        status_body,
        textvariable=service_hint_var,
        style='Hint.TLabel',
        background=COLORS['card'],
        wraplength=430,
    ).pack(anchor='w', pady=(16, 0))
    capability_frame = tk.Frame(status_body, bg=COLORS['card'])
    capability_frame.pack(fill=tk.X, pady=(18, 0))
    capability_data = [
        ("账号", account_count_var),
        ("项目", project_count_var),
        ("方法", tk.StringVar(value=f"{len(MCP_TOOL_NAMES)} 个方法")),
    ]
    for label_text, value_var in capability_data:
        tile = make_metric_tile(capability_frame, label_text, value_var, COLORS['primary'])
        tile.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

    tools_grid = ttk.Frame(method_body, style='Card.TFrame')
    tools_grid.pack(fill=tk.BOTH, expand=True)

    def render_tool_list(enabled: bool = False) -> None:
        """根据服务状态渲染 MCP 工具方法清单。"""
        for widget in tools_grid.winfo_children():
            widget.destroy()
        if not enabled:
            make_empty_state(
                tools_grid,
                "list-checks",
                "等待服务启动",
                f"服务启动成功后会展示当前支持的全部 {len(MCP_TOOL_NAMES)} 个 MCP 方法，并按使用场景分组。",
            )
            return
        row_index = 0
        for group_name, group_tools in group_mcp_tools(MCP_TOOL_NAMES).items():
            tk.Label(
                tools_grid,
                text=f"{group_name}  {len(group_tools)}",
                bg=COLORS['card'],
                fg=COLORS['primary'],
                font=('Segoe UI', 9, 'bold'),
            ).grid(row=row_index, column=0, sticky='w', pady=(8 if row_index else 0, 4))
            row_index += 1
            for tool_name, tool_desc in group_tools:
                item = tk.Frame(tools_grid, bg=COLORS['card'])
                item.grid(row=row_index, column=0, sticky='ew', pady=1)
                tk.Label(
                    item,
                    text="●",
                    foreground=COLORS['success'],
                    background=COLORS['card'],
                    font=('Segoe UI', 8, 'bold'),
                ).pack(side=tk.LEFT)
                tk.Label(
                    item,
                    text=f"  {tool_name}",
                    foreground=COLORS['text_primary'],
                    background=COLORS['card'],
                    font=('Consolas', 8, 'bold'),
                ).pack(side=tk.LEFT)
                tk.Label(
                    item,
                    text=f"  {tool_desc}",
                    foreground=COLORS['text_muted'],
                    background=COLORS['card'],
                    font=('Segoe UI', 8),
                    wraplength=360,
                    justify=tk.LEFT,
                ).pack(side=tk.LEFT)
                row_index += 1

    render_tool_list(False)

    mcp_card = make_card(service_page, "MCP 配置代码", "file-json")
    mcp_card.pack(fill=tk.X, pady=(14, 0))
    mcp_body = card_body(mcp_card)
    mcp_code = tk.Text(
        mcp_body,
        height=5,
        font=('Consolas', 9),
        bg='#1E293B',
        fg='#E2E8F0',
        insertbackground='#E2E8F0',
        selectbackground=COLORS['primary'],
        wrap=tk.NONE,
        state=tk.DISABLED,
        padx=12,
        pady=10,
        relief='flat',
        borderwidth=1,
        highlightthickness=1,
        highlightbackground=COLORS['border'],
    )
    mcp_code.pack(fill=tk.X)
    copy_btn = ttk.Button(mcp_body, text="复制配置", style='Small.TButton', width=14)
    copy_btn.pack(anchor='e', pady=(10, 0))

    def build_mcp_config_code() -> str:
        """生成 JSON 格式 MCP 配置片段。"""
        try:
            port = int(port_var.get())
        except ValueError:
            port = 8000
        return (
            '{\n'
            '  "mcpServers": {\n'
            '    "lanhu": {\n'
            f'      "url": "{current_mcp_url(port)}"\n'
            '    }\n'
            '  }\n'
            '}'
        )

    def update_mcp_code() -> None:
        """刷新 MCP 手动配置代码。"""
        mcp_code.config(state=tk.NORMAL)
        mcp_code.delete(1.0, tk.END)
        mcp_code.insert(tk.END, build_mcp_config_code())
        mcp_code.config(state=tk.DISABLED)

    def copy_code() -> None:
        """复制 MCP 配置代码到剪贴板。"""
        root.clipboard_clear()
        root.clipboard_append(build_mcp_config_code())
        log("[OK] MCP 配置代码已复制到剪贴板", 'success')

    copy_btn.config(command=copy_code)

    # 项目页
    project_summary = tk.Frame(projects_page, bg=COLORS['bg'])
    project_summary.pack(fill=tk.X)
    project_status_card = make_card(project_summary, "项目概览", "folder-kanban")
    project_status_body = card_body(project_status_card)
    ttk.Label(
        project_status_body,
        textvariable=project_count_var,
        style='Status.TLabel',
        background=COLORS['card'],
    ).pack(anchor='w')
    ttk.Label(
        project_status_body,
        textvariable=project_status_var,
        style='Hint.TLabel',
        background=COLORS['card'],
        wraplength=420,
    ).pack(anchor='w', pady=(6, 0))
    ttk.Label(
        project_status_body,
        text="读取成功后可直接复制 tid/pid 项目链接给 AI，用于 PRD、设计图和切图分析。",
        style='Hint.TLabel',
        background=COLORS['card'],
        wraplength=420,
    ).pack(anchor='w', pady=(6, 0))
    project_action_card = make_card(project_summary, "项目操作", "refresh-cw")
    pack_responsive_pair(project_summary, project_status_card, project_action_card)
    project_action_body = card_body(project_action_card)
    
    refresh_projects_btn = ttk.Button(project_action_body, text="刷新项目", style='Primary.TButton')
    refresh_projects_btn.pack(side=tk.LEFT, pady=(0, 10))
    add_button_hover_effect(refresh_projects_btn)
    
    open_lanhu_home_btn = ttk.Button(
        project_action_body,
        text="打开蓝湖",
        style='TButton',
        command=lambda: webbrowser.open(DEFAULT_LANHU_LOGIN_URL),
    )
    open_lanhu_home_btn.pack(side=tk.LEFT, padx=(10, 0), pady=(0, 10))
    add_button_hover_effect(open_lanhu_home_btn)
    manual_project_row = ttk.Frame(project_action_body, style='Card.TFrame')
    manual_project_row.pack(fill=tk.X, pady=(6, 0))
    manual_project_url_var = tk.StringVar()
    
    project_url_entry = ttk.Entry(
        manual_project_row,
        textvariable=manual_project_url_var,
    )
    project_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    add_entry_focus_effect(project_url_entry)
    
    save_project_btn = ttk.Button(manual_project_row, text="保存项目链接", style='Small.TButton', width=14)
    save_project_btn.pack(side=tk.LEFT, padx=(8, 0))
    add_button_hover_effect(save_project_btn)
    ttk.Label(
        project_action_body,
        text="如果自动读取失败，可在蓝湖打开任意项目后复制地址粘贴到这里；保存后同样会出现在当前账号项目列表。",
        style='Hint.TLabel',
        background=COLORS['card'],
        wraplength=520,
    ).pack(anchor='w', pady=(8, 0))

    project_diagnostic_var = tk.StringVar(value=f"自动读取会通过蓝湖 team_projects 接口获取项目列表，并合并登录缓存和本地项目。")
    ttk.Label(
        project_action_body,
        textvariable=project_diagnostic_var,
        style='Hint.TLabel',
        background=COLORS['card'],
        wraplength=520,
        justify=tk.LEFT,
    ).pack(anchor='w', pady=(6, 0))

    projects_card = make_card(projects_page, "当前账号项目", "folder-kanban")
    projects_card.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
    projects_body = card_body(projects_card)
    projects_list = ttk.Frame(projects_body, style='Card.TFrame')
    projects_list.pack(fill=tk.BOTH, expand=True)

    def render_project_rows(projects: list[dict], message: str = "") -> None:
        """渲染当前账号项目列表。"""
        current_signature = (project_rows_signature(projects), message)
        project_count_var.set(f"{len(projects)} 个项目")
        overview_project_var.set(f"{len(projects)} 个项目")
        if project_rows_state["signature"] == current_signature:
            return
        project_rows_state["signature"] = current_signature
        for widget in projects_list.winfo_children():
            widget.destroy()
        if not projects:
            empty_text = message or "尚未读取到项目。请先登录账号，然后点击刷新项目。"
            make_empty_state(
                projects_list,
                "folder-kanban",
                "还没有读取到项目",
                f"{empty_text} 也可以手动粘贴蓝湖项目链接保存到本地项目列表。",
            )
            return
        for index, project in enumerate(projects):
            row = tk.Frame(
                projects_list,
                bg='#F8FAFC' if index % 2 == 0 else COLORS['card'],
                highlightbackground=COLORS['border_light'],
                highlightthickness=1,
                bd=0,
            )
            row.pack(fill=tk.X, pady=(0 if index == 0 else 8, 0))
            row_inner = tk.Frame(row, bg=row.cget('bg'))
            row_inner.pack(fill=tk.X, padx=12, pady=10)
            badge = tk.Label(
                row_inner,
                text=str(project.get("type", "项目"))[:2],
                bg=COLORS['primary_light'],
                fg=COLORS['primary'],
                width=4,
                font=('Segoe UI', 9, 'bold'),
            )
            badge.pack(side=tk.LEFT, ipady=6)
            info = tk.Frame(row_inner, bg=row.cget('bg'))
            info.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(12, 0))
            tk.Label(
                info,
                text=str(project.get("name", "未命名项目")),
                bg=row.cget('bg'),
                fg=COLORS['text_primary'],
                font=('Segoe UI', 10, 'bold'),
            ).pack(anchor='w')
            meta_parts = [
                f"PID {project.get('id') or '-'}",
                f"TID {project.get('team_id') or '-'}",
            ]
            if project.get("team_name"):
                meta_parts.append(f"团队 {project.get('team_name')}")
            if project.get("owner_name"):
                meta_parts.append(f"负责人 {project.get('owner_name')}")
            if project.get("updated_at"):
                meta_parts.append(f"更新 {project.get('updated_at')}")
            if project.get("source"):
                meta_parts.append(f"来源 {project.get('source')}")
            tk.Label(
                info,
                text="  |  ".join(meta_parts),
                bg=row.cget('bg'),
                fg=COLORS['text_muted'],
                font=('Segoe UI', 8),
            ).pack(anchor='w', pady=(3, 0))

            def open_project(project_url: str = str(project.get("url", ""))) -> None:
                """打开项目链接。"""
                if project_url:
                    webbrowser.open(project_url)

            def copy_project(project_url: str = str(project.get("url", ""))) -> None:
                """复制项目链接。"""
                if project_url:
                    root.clipboard_clear()
                    root.clipboard_append(project_url)
                    log("项目链接已复制", 'success')

            actions = tk.Frame(row_inner, bg=row.cget('bg'))
            actions.pack(side=tk.RIGHT)

            def open_design_browser_for_project(
                project_id: str = str(project.get("id", "")),
                team_id: str = str(project.get("team_id", "")),
                project_name: str = str(project.get("name", "")),
            ) -> None:
                """打开设计稿浏览窗口。"""
                open_design_browser(root, project_id, team_id, project_name, get_active_account, log)

            ttk.Button(actions, text="设计稿", style='Small.TButton', width=8, command=open_design_browser_for_project).pack(side=tk.LEFT)
            ttk.Button(actions, text="打开", style='Small.TButton', width=8, command=open_project).pack(side=tk.LEFT, padx=(8, 0))
            ttk.Button(actions, text="复制", style='Small.TButton', width=8, command=copy_project).pack(side=tk.LEFT, padx=(8, 0))

    def refresh_projects() -> None:
        """后台刷新当前登录账号的项目列表。"""
        nonlocal is_refreshing_projects
        if is_refreshing_projects:
            project_status_var.set("正在刷新项目，请稍候...")
            return
        active = get_active_account()
        if not active or not active.get("cookie"):
            project_status_var.set("请先登录蓝湖账号。")
            render_project_rows([], "请先在账号页登录蓝湖账号，然后再刷新项目。")
            show_page("account")
            return
        is_refreshing_projects = True
        refresh_projects_btn.config(state=tk.DISABLED, text="刷新中...")
        project_status_var.set("正在读取蓝湖项目...")
        log("正在读取当前账号项目列表", 'info')

        def _load() -> None:
            ok, message, projects = load_projects_for_account(active)
            root.after(0, lambda: _finish(ok, message, projects))

        def _finish(ok: bool, message: str, projects: list[dict]) -> None:
            nonlocal is_refreshing_projects
            is_refreshing_projects = False
            refresh_projects_btn.config(state=tk.NORMAL, text="刷新项目")
            project_status_var.set(message)
            project_diagnostic_var.set(
                f"接口候选 {len(PROJECT_ENDPOINTS)} 个（team_projects）；当前结果 {len(projects)} 个。{message}"
            )
            render_project_rows(projects, message)
            log(message, 'success' if ok else 'warn')

        threading.Thread(target=_load, daemon=True).start()

    refresh_projects_btn.config(command=refresh_projects)

    def save_manual_project_from_input() -> None:
        """保存用户粘贴的蓝湖项目链接。"""
        active = get_active_account()
        account_id = str(active.get("id") if active else "")
        ok, message, project = save_manual_project(manual_project_url_var.get(), account_id)
        log(message, 'success' if ok else 'warn')
        if not ok:
            messagebox.showwarning("项目链接", message)
            return
        manual_project_url_var.set("")
        merged_projects = merge_project_lists(cached_projects_for_account(account_id) + ([project] if project else []))
        render_project_rows(merged_projects, message)
        project_status_var.set(message)
        project_diagnostic_var.set(f"已保存手动项目链接；当前本地缓存 {len(merged_projects)} 个项目。")

    save_project_btn.config(command=save_manual_project_from_input)
    render_project_rows([])

    # 账号页
    account_card = make_card(account_page, "蓝湖信息与登录", "shield-check")
    account_card.pack(fill=tk.X)
    account_body = card_body(account_card)
    account_top = ttk.Frame(account_body, style='Card.TFrame')
    account_top.pack(fill=tk.X)
    account_title_var = tk.StringVar()
    account_meta_var = tk.StringVar()
    login_url_var = tk.StringVar(value=get_saved_login_url())
    account_info = ttk.Frame(account_top, style='Card.TFrame')
    account_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
    ttk.Label(
        account_info,
        textvariable=account_title_var,
        style='Status.TLabel',
        background=COLORS['card'],
    ).pack(anchor='w')
    ttk.Label(
        account_info,
        textvariable=account_meta_var,
        style='Hint.TLabel',
        background=COLORS['card'],
        wraplength=720,
        justify=tk.LEFT,
    ).pack(anchor='w', pady=(4, 0))
    account_combo = ttk.Combobox(account_top, textvariable=account_var, width=30, state='readonly')
    account_combo.pack(side=tk.RIGHT)

    account_detail_grid = tk.Frame(account_body, bg=COLORS['card'])
    account_detail_grid.pack(fill=tk.X, pady=(14, 0))
    account_detail_vars = {
        "email": tk.StringVar(value="未读取到"),
        "mobile": tk.StringVar(value="未读取到"),
        "username": tk.StringVar(value="未读取到"),
        "avatar": tk.StringVar(value="未读取到"),
    }
    for detail_index, (detail_label, detail_key) in enumerate((
        ("邮箱", "email"),
        ("手机", "mobile"),
        ("用户名", "username"),
        ("头像", "avatar"),
    )):
        detail_cell = tk.Frame(account_detail_grid, bg=COLORS['surface'], highlightbackground=COLORS['border_light'], highlightthickness=1)
        detail_cell.grid(row=0, column=detail_index, sticky='ew', padx=(0 if detail_index == 0 else 8, 0))
        account_detail_grid.columnconfigure(detail_index, weight=1)
        tk.Label(detail_cell, text=detail_label, bg=COLORS['surface'], fg=COLORS['text_muted'], font=('Segoe UI', 8)).pack(anchor='w', padx=10, pady=(8, 0))
        tk.Label(
            detail_cell,
            textvariable=account_detail_vars[detail_key],
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            font=('Segoe UI', 9, 'bold'),
            wraplength=180,
            justify=tk.LEFT,
        ).pack(anchor='w', padx=10, pady=(2, 8))

    login_url_row = ttk.Frame(account_body, style='Card.TFrame')
    login_url_row.pack(fill=tk.X, pady=(14, 0))
    ttk.Label(
        login_url_row,
        text="登录地址",
        style='Hint.TLabel',
        background=COLORS['card'],
    ).pack(side=tk.LEFT)
    login_url_entry = ttk.Entry(login_url_row, textvariable=login_url_var, width=56)
    login_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 8))
    add_entry_focus_effect(login_url_entry)
    
    browser_btn = ttk.Button(
        login_url_row,
        text="浏览器打开",
        style='Small.TButton',
        width=14,
        command=lambda: webbrowser.open(login_url_var.get().strip() or DEFAULT_LANHU_LOGIN_URL),
    )
    browser_btn.pack(side=tk.LEFT)
    add_button_hover_effect(browser_btn)

    account_button_row = ttk.Frame(account_body, style='Card.TFrame')
    account_button_row.pack(fill=tk.X, pady=(14, 0))
    
    login_btn = ttk.Button(account_button_row, text="添加账号 / 一键登录", style='Primary.TButton')
    login_btn.pack(side=tk.LEFT)
    add_button_hover_effect(login_btn)
    
    refresh_profile_btn = ttk.Button(account_button_row, text="刷新资料", style='TButton')
    refresh_profile_btn.pack(side=tk.LEFT, padx=(10, 0))
    add_button_hover_effect(refresh_profile_btn)
    
    save_cookie_btn = ttk.Button(account_button_row, text="保存 Cookie", style='Success.TButton')
    save_cookie_btn.pack(side=tk.LEFT, padx=(10, 0))
    add_button_hover_effect(save_cookie_btn)
    
    logout_btn = ttk.Button(account_button_row, text="退出当前账号", style='Danger.TButton')
    logout_btn.pack(side=tk.LEFT, padx=(10, 0))
    add_button_hover_effect(logout_btn)

    accounts_card = make_card(account_page, "已登录账号", "user")
    accounts_card.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
    accounts_body = card_body(accounts_card)
    accounts_list = ttk.Frame(accounts_body, style='Card.TFrame')
    accounts_list.pack(fill=tk.BOTH, expand=True)

    cookie_card = make_card(account_page, "手动 Cookie", "key-round")
    cookie_card.pack(fill=tk.X, pady=(14, 0))
    cookie_body = card_body(cookie_card)
    ttk.Label(
        cookie_body,
        text="仅在 WebView 登录受网络或代理影响时使用。界面默认只展示摘要，保存时会使用完整 Cookie。",
        style='Hint.TLabel',
        background=COLORS['card'],
        wraplength=740,
    ).pack(anchor='w', pady=(0, 8))
    cookie_text = tk.Text(
        cookie_body,
        height=4,
        font=('Consolas', 9),
        bg='#FFFFFF',
        fg=COLORS['text_primary'],
        insertbackground=COLORS['text_primary'],
        selectbackground=COLORS['primary_light'],
        wrap=tk.WORD,
        relief='solid',
        borderwidth=1,
        highlightthickness=1,
        highlightbackground=COLORS['border'],
        padx=10,
        pady=8,
    )
    cookie_text.pack(fill=tk.X)

    def sync_cookie_text() -> None:
        """把当前 Cookie 摘要同步到文本框，避免默认明文暴露完整 Cookie。"""
        cookie_text.delete(1.0, tk.END)
        cookie_text.insert(tk.END, mask_cookie_value(cookie_var.get()))

    def account_label(account: dict) -> str:
        """生成账号下拉显示文字。"""
        contact = account_primary_contact(account)
        suffix = f" ({contact})" if contact != "未读取联系方式" else ""
        return f"{account.get('name', '蓝湖用户')}{suffix}"

    def render_account_rows(accounts: list[dict], active_id: str) -> None:
        """渲染多账号列表，并给每个账号提供切换和退出操作。"""
        current_signature = account_rows_signature(accounts, active_id)
        if account_rows_state["signature"] == current_signature:
            return
        account_rows_state["signature"] = current_signature
        for widget in accounts_list.winfo_children():
            widget.destroy()
        if not accounts:
            empty = ttk.Frame(accounts_list, style='Card.TFrame')
            empty.pack(fill=tk.X)
            ttk.Label(
                empty,
                text="还没有账号。点击「添加账号 / 一键登录」后，账号会保存到这里。",
                style='Hint.TLabel',
                background=COLORS['card'],
            ).pack(anchor='w')
            return
        for index, account in enumerate(accounts):
            is_active = account.get("id") == active_id
            row = tk.Frame(
                accounts_list,
                bg='#F8FAFC' if is_active else COLORS['card'],
                highlightbackground=COLORS['primary_light'] if is_active else COLORS['border_light'],
                highlightthickness=1,
                bd=0,
            )
            row.pack(fill=tk.X, pady=(0 if index == 0 else 8, 0))
            row_inner = tk.Frame(row, bg=row.cget('bg'))
            row_inner.pack(fill=tk.X, padx=12, pady=10)
            avatar_path = avatar_cache_path(account)
            avatar_widget = None
            if avatar_path.exists():
                try:
                    from PIL import Image, ImageTk

                    source_image = Image.open(avatar_path)
                    source_image.thumbnail((36, 36))
                    avatar_image = ImageTk.PhotoImage(source_image)
                    avatar_images[str(avatar_path)] = avatar_image
                    avatar_widget = tk.Label(row_inner, image=avatar_image, bg=row.cget('bg'), width=36, height=36)
                except (ImportError, OSError, tk.TclError):
                    if avatar_path.suffix.lower() in (".png", ".gif"):
                        try:
                            avatar_image = tk.PhotoImage(file=str(avatar_path))
                            avatar_images[str(avatar_path)] = avatar_image
                            avatar_widget = tk.Label(row_inner, image=avatar_image, bg=row.cget('bg'), width=36, height=36)
                        except tk.TclError:
                            avatar_widget = None
            if avatar_widget is None:
                avatar_widget = tk.Label(
                    row_inner,
                    text=str(account.get("name", "蓝湖用户"))[:1].upper(),
                    bg=COLORS['primary'] if is_active else COLORS['border_light'],
                    fg='#FFFFFF' if is_active else COLORS['text_secondary'],
                    width=3,
                    font=('Segoe UI', 11, 'bold'),
                )
            avatar_widget.pack(side=tk.LEFT, ipady=5)
            info = tk.Frame(row_inner, bg=row.cget('bg'))
            info.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(12, 0))
            name_line = tk.Frame(info, bg=row.cget('bg'))
            name_line.pack(anchor='w', fill=tk.X)
            tk.Label(
                name_line,
                text=str(account.get("name", "蓝湖用户")),
                bg=row.cget('bg'),
                fg=COLORS['text_primary'],
                font=('Segoe UI', 10, 'bold'),
            ).pack(side=tk.LEFT)
            if is_active:
                tk.Label(
                    name_line,
                    text="当前使用",
                    bg=COLORS['primary_light'],
                    fg=COLORS['primary'],
                    font=('Segoe UI', 8, 'bold'),
                    padx=8,
                    pady=2,
                ).pack(side=tk.LEFT, padx=(8, 0))
            tk.Label(
                info,
                text=account_detail_line(account),
                bg=row.cget('bg'),
                fg=COLORS['text_muted'],
                font=('Segoe UI', 8),
            ).pack(anchor='w', pady=(3, 0))
            tk.Label(
                info,
                text=account_profile_line(account),
                bg=row.cget('bg'),
                fg=COLORS['text_muted'],
                font=('Segoe UI', 8),
                wraplength=520,
                justify=tk.LEFT,
            ).pack(anchor='w', pady=(2, 0))
            tk.Label(
                info,
                text=account_cookie_line(account),
                bg=row.cget('bg'),
                fg=COLORS['text_muted'],
                font=('Segoe UI', 8),
                wraplength=520,
                justify=tk.LEFT,
            ).pack(anchor='w', pady=(2, 0))

            def switch_account(account_id: str = str(account.get("id", ""))) -> None:
                """切换到指定账号。"""
                if ServiceManager.is_running():
                    messagebox.showwarning("服务运行中", "请先停止服务，再切换蓝湖账号。")
                    return
                if set_active_account(account_id):
                    refresh_accounts()
                    log("已切换蓝湖账号", 'info')

            def logout_account(account_id: str = str(account.get("id", "")), name: str = str(account.get("name", "蓝湖用户"))) -> None:
                """退出指定账号。"""
                do_logout_account(account_id, name)

            actions = tk.Frame(row_inner, bg=row.cget('bg'))
            actions.pack(side=tk.RIGHT)
            ttk.Button(
                actions,
                text="切换",
                style='Small.TButton',
                width=8,
                command=switch_account,
                state=tk.DISABLED if is_active else tk.NORMAL,
            ).pack(side=tk.LEFT)
            ttk.Button(
                actions,
                text="退出",
                style='Small.TButton',
                width=8,
                command=logout_account,
            ).pack(side=tk.LEFT, padx=(8, 0))

    def refresh_accounts() -> None:
        """刷新账号区域显示。"""
        nonlocal account_options, full_cookie
        accounts = get_accounts()
        account_options = accounts
        account_combo['values'] = [account_label(account) for account in accounts]
        account_count_var.set(f"{len(accounts)} 个账号")
        active = get_active_account()
        if active:
            account_var.set(account_label(active))
            full_cookie = active.get("cookie", "")
            cookie_var.set(full_cookie)
            account_title_var.set(f"已登录: {active.get('name', '蓝湖用户')}")
            account_meta_var.set(
                f"{account_detail_line(active)}\n{account_profile_line(active)}\n{account_cookie_line(active)}"
            )
            account_detail_vars["email"].set(str(active.get("email") or "未读取到"))
            account_detail_vars["mobile"].set(str(active.get("mobile") or "未读取到"))
            account_detail_vars["username"].set(str(active.get("username") or active.get("nickname") or "未读取到"))
            account_detail_vars["avatar"].set("已缓存" if avatar_cache_path(active).exists() else ("已读取 URL" if active.get("avatar") else "未读取到"))
            login_status_var.set(f"当前账号\n{active.get('name', '蓝湖用户')}")
            overview_account_var.set(str(active.get('name') or account_primary_contact(active)))
            service_hint_var.set("账号已就绪，可以启动 MCP 服务。")
            project_status_var.set("账号已就绪，可刷新当前用户项目。")
        else:
            account_var.set("")
            full_cookie = ""
            cookie_var.set("")
            account_title_var.set("未登录蓝湖")
            account_meta_var.set("登录后才能启动 MCP 服务；支持多个蓝湖账号切换。")
            account_detail_vars["email"].set("未读取到")
            account_detail_vars["mobile"].set("未读取到")
            account_detail_vars["username"].set("未读取到")
            account_detail_vars["avatar"].set("未读取到")
            login_status_var.set("未登录\n服务启动会被拦截")
            overview_account_var.set("未登录")
            service_hint_var.set("请先完成蓝湖登录，服务启动需要有效 Cookie。")
            project_status_var.set("登录后可读取当前账号项目。")
            render_project_rows([])
        render_account_rows(accounts, active.get("id", "") if active else "")
        sync_cookie_text()
        update_mcp_code()

        def _download_avatars() -> None:
            """后台缓存头像，完成后刷新账号列表。"""
            changed = False
            for account in accounts:
                if account.get("avatar") and not avatar_cache_path(account).exists():
                    changed = bool(download_avatar(account)) or changed
            if changed:
                root.after(0, refresh_accounts)

        threading.Thread(target=_download_avatars, daemon=True).start()

    def refresh_account_profile(cookie_value: str, base_info: Optional[dict] = None) -> None:
        """后台尝试补全当前账号的蓝湖用户资料。"""
        if not cookie_value:
            return
        source_info = base_info or {}

        def _load_profile() -> None:
            ok, message, profile_info = fetch_lanhu_user_profile(cookie_value)
            if not ok:
                root.after(0, lambda: log(f"账号资料补全未成功: {message}", 'warn'))
                return
            if profile_info.get("name") == "蓝湖用户" and source_info.get("name"):
                profile_info["name"] = source_info.get("name")
            merged_info = merge_identity_info(profile_info, source_info)
            account = upsert_account(cookie_value, merged_info)
            root.after(0, lambda: _finish_profile(message, account))

        def _finish_profile(message: str, account: Optional[dict]) -> None:
            refresh_accounts()
            if account:
                log(f"{message}: {account_detail_line(account)}", 'success')
                return
            log(message, 'info')

        threading.Thread(target=_load_profile, daemon=True).start()

    def refresh_current_profile() -> None:
        """主动刷新当前账号资料和项目。"""
        nonlocal is_refreshing_profile
        if is_refreshing_profile:
            log("账号资料正在刷新，请稍候", 'info')
            return
        active = get_active_account()
        if not active or not active.get("cookie"):
            messagebox.showwarning("需要登录", "请先登录蓝湖账号。")
            return
        is_refreshing_profile = True
        refresh_profile_btn.config(state=tk.DISABLED)
        log("正在刷新当前账号资料...", 'info')

        def _restore_button() -> None:
            nonlocal is_refreshing_profile
            is_refreshing_profile = False
            refresh_profile_btn.config(state=tk.NORMAL)
            refresh_projects()

        refresh_account_profile(str(active.get("cookie") or ""), active)
        root.after(1600, _restore_button)

    def on_account_change(*args: object) -> None:
        """处理账号下拉切换。"""
        selected = account_var.get()
        for account in account_options:
            if account_label(account) == selected:
                if set_active_account(account.get("id", "")):
                    refresh_accounts()
                    log(f"已切换蓝湖账号: {account.get('name', '蓝湖用户')}", 'info')
                return

    account_combo.bind("<<ComboboxSelected>>", on_account_change)

    def do_login() -> None:
        """用独立进程弹出 WebView 登录蓝湖。"""
        try:
            flog("=== 一键登录开始 ===")
            log("正在打开蓝湖登录窗口...", 'info')
            result_file = DATA_DIR / '.login_result.json'
            if result_file.exists():
                result_file.unlink()
            helper_path = APP_DIR / 'lanhu_login_helper.py'
            if not helper_path.exists():
                helper_path = Path(__file__).with_name('lanhu_login_helper.py')
            if getattr(sys, 'frozen', False):
                helper_command = [
                    sys.executable,
                    '--login-helper',
                    str(result_file),
                    str(WEBVIEW_STORAGE_DIR),
                    login_url_var.get().strip() or DEFAULT_LANHU_LOGIN_URL,
                ]
            else:
                python_exe = shutil.which('python') or shutil.which('python3')
                if not python_exe:
                    for candidate in [r'C:\Users\swiml\AppData\Local\Programs\Python\Python312\python.exe']:
                        if os.path.exists(candidate):
                            python_exe = candidate
                            break
                if not python_exe:
                    messagebox.showerror("错误", "找不到 Python 解释器。")
                    return
                helper_command = [
                    python_exe,
                    str(helper_path),
                    str(result_file),
                    str(WEBVIEW_STORAGE_DIR),
                    login_url_var.get().strip() or DEFAULT_LANHU_LOGIN_URL,
                ]
            save_login_url(login_url_var.get())
        except Exception as error:
            flog(f"初始化异常: {error}", 'error')
            flog(traceback.format_exc(), 'error')
            messagebox.showerror("错误", f"初始化失败:\n{error}")
            return

        login_btn.config(state=tk.DISABLED)

        def _on_ok(result: dict) -> None:
            """处理登录成功结果。"""
            nonlocal full_cookie
            cookie_str = str(result.get('cookies', ''))
            user_info = parse_user_payload(result)
            user_name = user_info.get('name') or '蓝湖用户'
            full_cookie = cookie_str
            account = upsert_account(cookie_str, user_info)
            refresh_accounts()
            log(f"[OK] 登录成功，用户: {user_name}", 'success')
            log(f"账号详情: {account_detail_line(account or user_info)}", 'info')
            if account:
                log(f"当前账号已切换为: {account.get('name')}", 'info')
            refresh_account_profile(cookie_str, user_info)
            refresh_projects()

        def _handle_result(result: dict) -> None:
            """把登录子进程结果回传到主线程。"""
            login_btn.config(state=tk.NORMAL)
            diagnostics = result.get("diagnostics", [])
            if isinstance(diagnostics, list):
                for item in diagnostics[-4:]:
                    log(f"登录诊断: {item}", 'info')
            if result.get('status') == 'success' and result.get('cookies'):
                _on_ok(result)
                return
            error = str(result.get('error') or '').strip()
            if error:
                log(f"登录失败: {error.replace(chr(10), ' ')}", 'error')
                should_open_browser = messagebox.askyesno(
                    "登录失败",
                    f"{error}\n\n是否改用系统浏览器打开蓝湖登录页？登录后可复制 Cookie 保存为账号。",
                )
                if should_open_browser:
                    webbrowser.open(login_url_var.get().strip() or DEFAULT_LANHU_LOGIN_URL)
                return
            log("未检测到蓝湖登录，登录窗口已关闭或超时", 'warn')

        def _run() -> None:
            """后台运行登录辅助进程。"""
            try:
                flog(f"启动子进程: {' '.join(helper_command)}")
                creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                proc = subprocess.Popen(
                    helper_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=creation_flags,
                )
                flog(f"子进程PID: {proc.pid}")
                stdout, stderr = proc.communicate()
                flog(f"退出码: {proc.returncode}")
                if stdout:
                    flog(f"stdout: {stdout.decode('utf-8', errors='replace')[:800]}")
                if stderr:
                    flog(f"stderr: {stderr.decode('utf-8', errors='replace')[:800]}")
                if result_file.exists():
                    result = json.loads(result_file.read_text(encoding='utf-8'))
                    root.after(0, lambda r=result: _handle_result(r))
                else:
                    root.after(0, lambda: _handle_result({"status": "cancelled"}))
            except Exception as error:
                flog(f"异常: {error}", 'error')
                flog(traceback.format_exc(), 'error')
                root.after(0, lambda e=error: messagebox.showerror("错误", str(e)))
                root.after(0, lambda: login_btn.config(state=tk.NORMAL))

        threading.Thread(target=_run, daemon=True).start()

    def do_save_cookie() -> None:
        """保存用户手动输入的 Cookie。"""
        nonlocal full_cookie
        cookie_value = cookie_text.get(1.0, tk.END).strip()
        if cookie_value == mask_cookie_value(full_cookie):
            cookie_value = full_cookie
        if not cookie_value:
            messagebox.showwarning("提示", "Cookie 为空，请先登录或手动输入。")
            return
        account = upsert_account(cookie_value, {"name": "手动 Cookie 账号"})
        full_cookie = cookie_value
        refresh_accounts()
        log(f"[OK] Cookie 已保存 ({len(cookie_value)} 字符)", 'success')
        refresh_account_profile(cookie_value, account or {"name": "手动 Cookie 账号"})
        messagebox.showinfo("成功", f"Cookie 已保存。\n账号: {account.get('name') if account else '未知'}")

    def do_logout_account(account_id: str = "", account_name: str = "") -> None:
        """退出当前或指定蓝湖账号。"""
        active = get_active_account()
        target_id = account_id or (active.get("id", "") if active else "")
        target_name = account_name or (active.get("name", "蓝湖用户") if active else "蓝湖用户")
        if not target_id:
            messagebox.showinfo("提示", "当前没有已登录账号。")
            return
        if ServiceManager.is_running():
            messagebox.showwarning("服务运行中", "请先停止服务，再退出蓝湖账号。")
            return
        if not messagebox.askyesno("退出账号", f"确定退出 {target_name} 吗？"):
            return
        remove_account(target_id)
        refresh_accounts()
        log(f"已退出账号: {target_name}", 'warn')

    login_btn.config(command=do_login)
    refresh_profile_btn.config(command=refresh_current_profile)
    save_cookie_btn.config(command=do_save_cookie)
    logout_btn.config(command=do_logout_account)

    # AI 工具页
    tools_summary = tk.Frame(tools_page, bg=COLORS['bg'])
    tools_summary.pack(fill=tk.X)
    tools_status_card = make_card(tools_summary, "识别概览", "bot")
    tools_status_body = card_body(tools_status_card)
    ttk.Label(
        tools_status_body,
        text="已检测工具",
        style='Hint.TLabel',
        background=COLORS['card'],
    ).pack(anchor='w')
    ttk.Label(
        tools_status_body,
        textvariable=ide_count_var,
        style='Status.TLabel',
        background=COLORS['card'],
    ).pack(anchor='w', pady=(4, 0))
    tools_action_card = make_card(tools_summary, "批量操作", "wand-sparkles")
    pack_responsive_pair(tools_summary, tools_status_card, tools_action_card)
    tools_action_body = card_body(tools_action_card)
    
    config_all_btn = ttk.Button(tools_action_body, text="一键配置全部", style='Primary.TButton')
    config_all_btn.pack(side=tk.LEFT)
    add_button_hover_effect(config_all_btn)
    
    refresh_ide_btn = ttk.Button(tools_action_body, text="重新检测", style='TButton')
    refresh_ide_btn.pack(side=tk.LEFT, padx=(10, 0))
    add_button_hover_effect(refresh_ide_btn)

    ide_card = make_card(tools_page, "AI 开发工具", "plug-zap")
    ide_card.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
    ide_body = card_body(ide_card)
    ide_grid = ttk.Frame(ide_body, style='Card.TFrame')
    ide_grid.pack(fill=tk.BOTH, expand=True)

    def refresh_ides() -> None:
        """刷新 AI 工具识别结果。"""
        for widget in ide_grid.winfo_children():
            widget.destroy()
        detected = IDEManager.detect_all()
        details = IDEManager.get_detection_details()
        installed_count = sum(1 for value in detected.values() if value)
        ide_count_var.set(f"{installed_count} / {len(detected)}")
        overview_ide_var.set(f"{installed_count} / {len(detected)} 个工具")
        max_cols = 1 if root.winfo_width() < 1160 else 2
        for index, (name, installed) in enumerate(detected.items()):
            row = index // max_cols
            col = index % max_cols
            cell_bg = '#F8FAFC' if installed else '#FFFFFF'
            cell = tk.Frame(
                ide_grid,
                bg=cell_bg,
                highlightbackground=COLORS['primary_light'] if installed else COLORS['border_light'],
                highlightthickness=1,
            )
            cell.grid(row=row, column=col, sticky='ew', padx=(0 if col == 0 else 16, 0), pady=3)
            ide_grid.columnconfigure(col, weight=1)
            detail = details.get(name, {})
            cell_inner = tk.Frame(cell, bg=cell_bg)
            cell_inner.pack(fill=tk.X, padx=12, pady=10)
            create_lucide_icon(
                cell_inner,
                str(detail.get('icon') or 'plug-zap'),
                COLORS['success'] if installed else COLORS['text_muted'],
                20,
                cell_bg,
            ).pack(side=tk.LEFT, padx=(0, 10))
            title = tk.Frame(cell_inner, bg=cell_bg)
            title.pack(side=tk.LEFT, fill=tk.X, expand=True)
            status_text = "●" if installed else "○"
            status_color = COLORS['success'] if installed else COLORS['text_muted']
            tk.Label(
                title,
                text=f"{status_text} {name}",
                foreground=status_color,
                background=cell_bg,
                font=('Segoe UI', 9, 'bold' if installed else 'normal'),
            ).pack(anchor='w')
            detail_text = detail.get('exe_path') or detail.get('config_path') or "未发现安装路径或配置目录"
            tk.Label(
                title,
                text=str(detail_text),
                fg=COLORS['text_muted'],
                bg=cell_bg,
                font=('Segoe UI', 8),
                wraplength=420,
                justify=tk.LEFT,
            ).pack(anchor='w', pady=(4, 0))
            if installed:
                def make_cfg(ide: str = name) -> None:
                    """配置单个 AI 工具。"""
                    try:
                        port = int(port_var.get())
                    except ValueError:
                        messagebox.showerror("错误", "请先输入有效端口号。")
                        return
                    ok, msg = IDEManager.configure(ide, port)
                    if ok:
                        log(f"[OK] {msg}", 'success')
                    else:
                        log(f"[WARN] {msg}", 'warn')
                        messagebox.showwarning("配置提示", msg)

                ttk.Button(cell_inner, text="配置", style='Small.TButton', width=10, command=make_cfg).pack(side=tk.RIGHT, padx=(10, 0))
        log(f"检测到 {installed_count}/{len(detected)} 个已安装的 AI 工具", 'info')

    def _config_all() -> None:
        """批量配置所有已识别的 AI 工具。"""
        try:
            port = int(port_var.get())
        except ValueError:
            messagebox.showerror("错误", "请先输入有效端口号。")
            return
        results = IDEManager.configure_all(port)
        messages = []
        for name, ok, msg in results:
            prefix = "[OK]" if ok else "[ERROR]"
            messages.append(f"{prefix} {name}: {msg}")
            log(f"{prefix} {name}: {msg}", 'success' if ok else 'error')
        if messages:
            messagebox.showinfo("配置结果", "\n".join(messages))
        else:
            messagebox.showinfo("提示", "未检测到已安装的 AI 工具。")

    config_all_btn.config(command=_config_all)
    refresh_ide_btn.config(command=refresh_ides)
    overview_config_btn.config(command=lambda: (show_page("tools"), _config_all()))
    ide_layout_state = {"wide": True}

    def refresh_ides_on_resize(event: object = None) -> None:
        """窗口跨过布局断点时重排 AI 工具卡片。"""
        is_wide = root.winfo_width() >= 1160
        if ide_layout_state["wide"] == is_wide:
            return
        ide_layout_state["wide"] = is_wide
        refresh_ides()

    root.bind("<Configure>", refresh_ides_on_resize, add="+")

    def do_start() -> None:
        """启动 MCP 服务。"""
        valid, port, error_text = validate_port(port_var.get())
        if error_text:
            messagebox.showerror("端口错误", error_text)
            return
        active_account = get_active_account()
        if not active_account or not active_account.get("cookie"):
            messagebox.showwarning("需要登录", "请先完成蓝湖登录并选择一个账号，再启动服务。")
            log("请先登录蓝湖账号，服务启动已拦截", 'warn')
            show_page("account")
            return
        start_btn.config(state=tk.DISABLED)
        stop_btn.config(state=tk.DISABLED)
        service_status_var.set("● 启动中...")
        overview_service_var.set("启动中")
        status_lbl.config(style='StatusWarn.TLabel')
        service_hint_var.set("正在启动服务，请稍候。")
        root.update()

        def _start() -> None:
            ok, msg = ServiceManager.start(port, on_server_output, on_server_error)
            root.after(0, lambda: _on_result(ok, msg))

        threading.Thread(target=_start, daemon=True).start()

    def _on_result(ok: bool, msg: str) -> None:
        """处理服务启动结果。"""
        if ok:
            service_status_var.set(f"● 运行中 (:{port_var.get()})")
            overview_service_var.set(f"运行中 :{port_var.get()}")
            status_lbl.config(style='StatusRunning.TLabel')
            start_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)
            service_hint_var.set(f"MCP 地址: {current_mcp_url(int(port_var.get()))}")
            render_tool_list(True)
            update_mcp_code()
            log(f"[OK] {msg} -> http://localhost:{port_var.get()}/", 'success')
            return
        service_status_var.set("● 启动失败")
        overview_service_var.set("启动失败")
        status_lbl.config(style='StatusError.TLabel')
        start_btn.config(state=tk.NORMAL)
        stop_btn.config(state=tk.DISABLED)
        service_hint_var.set("启动失败，请查看日志并确认端口、服务端文件和账号状态。")
        render_tool_list(False)
        log(f"[ERROR] {msg}", 'error')
        messagebox.showerror("启动失败", msg)

    def do_stop() -> None:
        """停止 MCP 服务。"""
        ok, msg = ServiceManager.stop()
        service_status_var.set("● 未运行")
        overview_service_var.set("未运行")
        status_lbl.config(style='StatusError.TLabel')
        start_btn.config(state=tk.NORMAL)
        stop_btn.config(state=tk.DISABLED)
        service_hint_var.set("服务已停止。")
        render_tool_list(False)
        log(f"[STOP] {msg}", 'info' if ok else 'warn')

    start_btn.config(command=do_start)
    stop_btn.config(command=do_stop)
    overview_login_btn.config(command=lambda: (show_page("account"), do_login()))
    overview_start_btn.config(command=do_start)

    def on_port_change(*args: object) -> None:
        """端口变化时同步 MCP 配置代码。"""
        update_mcp_code()

    port_var.trace_add('write', on_port_change)

    def on_close() -> None:
        """窗口关闭时停止后台服务。"""
        if ServiceManager.is_running():
            ServiceManager.stop()
        root.destroy()

    update_mcp_code()
    refresh_accounts()
    refresh_ides()
    animate_sidebar_pulse()

    try:
        _, _, server_source = build_server_start_command()
        log(f"[OK] MCP 服务端就绪: {server_source}", 'success')
    except FileNotFoundError as error:
        log(f"[WARN] {error}", 'warn')
    log(f"数据目录: {DATA_DIR}", 'info')
    active_account = get_active_account()
    if active_account:
        log(f"蓝湖账号: {active_account.get('name', '蓝湖用户')} ({len(load_cookie())} 字符 Cookie)", 'success')
    else:
        log("蓝湖账号: 未登录，请先点击一键登录", 'warn')
    log("点击「启动服务」开始使用", 'info')

    root.protocol("WM_DELETE_WINDOW", on_close)
    show_page("overview")
    if os.environ.get("LANHU_GUI_SMOKE_CLOSE") == "1":
        root.after(500, on_close)
    root.mainloop()


def run_login_helper_from_gui_args() -> int:
    """作为打包后的登录助手子进程运行。"""
    result_file = Path(sys.argv[2]) if len(sys.argv) > 2 else DATA_DIR / '.login_result.json'
    flog(f"登录助手分支启动: args={sys.argv}")
    try:
        from lanhu_login_helper import main as login_main

        sys.argv = [sys.argv[0]] + sys.argv[2:]
        return login_main()
    except Exception as error:
        flog(f"登录助手分支异常: {error}", 'error')
        flog(traceback.format_exc(), 'error')
        try:
            result_file.parent.mkdir(parents=True, exist_ok=True)
            result_file.write_text(
                json.dumps(
                    {
                        "status": "error",
                        "cookies": "",
                        "user": {},
                        "storage": {},
                        "url": "",
                        "error": f"登录助手启动失败: {error}",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding='utf-8',
            )
        except OSError:
            pass
        return 1


def run_server_from_gui_args() -> int:
    """作为打包后的 MCP 服务子进程运行。"""
    try:
        # 清理 GUI 分支参数，避免服务端模块误读。
        sys.argv = [sys.argv[0]] + [arg for arg in sys.argv[1:] if arg != '--server']
        flog("MCP 内置服务分支启动")
        import lanhu_mcp_server
        try:
            # 扩展模块会在导入时把高还原设计工具注册到同一个 mcp 实例。
            __import__('lanhu_mcp.server')
            flog("已加载高还原设计扩展工具")
        except Exception as import_error:
            flog(f"加载高还原设计扩展工具失败: {import_error}", 'warning')
        transport = os.getenv("MCP_TRANSPORT", "http").lower()
        if transport == "stdio":
            lanhu_mcp_server.mcp.run(transport="stdio")
        else:
            host = os.getenv("SERVER_HOST", "0.0.0.0")
            port = int(os.getenv("SERVER_PORT", "8000"))
            flog(f"MCP HTTP 服务监听: {host}:{port}/mcp")
            lanhu_mcp_server.mcp.run(transport="http", path="/mcp", host=host, port=port)
        return 0
    except Exception as error:
        flog(f"MCP 内置服务分支异常: {error}", 'error')
        flog(traceback.format_exc(), 'error')
        return 1


if __name__ == '__main__':
    if '--login-helper' in sys.argv:
        raise SystemExit(run_login_helper_from_gui_args())
    if '--server' in sys.argv:
        raise SystemExit(run_server_from_gui_args())
    create_gui()
