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
from urllib.parse import quote, urlencode, urlparse

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
WEBVIEW_STORAGE_DIR = DATA_DIR / 'webview'
AVATAR_CACHE_DIR = DATA_DIR / 'avatars'
LOG_FILE = DATA_DIR / 'app.log'
DEFAULT_LANHU_LOGIN_URL = 'https://lanhuapp.com/web/'

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
# 现代配色方案
# ============================================
COLORS = {
    'bg': '#F4F6F4',           # 主背景 - 低饱和暖灰
    'sidebar': '#172033',      # 侧边栏背景 - 深色导航
    'sidebar_hover': '#243049', # 侧边栏悬停背景
    'sidebar_active': '#243049',# 侧边栏选中背景
    'sidebar_text': '#E5E7EB', # 侧边栏文字
    'card': '#FFFFFF',         # 卡片背景 - 白色
    'primary': '#1D4ED8',      # 主色调 - 工具蓝
    'primary_hover': '#1E40AF',
    'primary_light': '#DBEAFE',# 主色浅色背景
    'success': '#15803D',      # 成功绿
    'danger': '#B91C1C',       # 错误红
    'warning': '#B45309',      # 警告橙
    'text_primary': '#172033', # 主文字
    'text_secondary': '#526070',# 次要文字
    'text_muted': '#7C8794',   # 弱化文字
    'border': '#D7DEE7',       # 边框
    'border_light': '#EEF2F6',
    'log_bg': '#111827',       # 日志背景（深色终端风）
    'log_text': '#E5E7EB',
    'accent': '#0F766E',       # 强调青绿
    'shadow': 'rgba(0, 0, 0, 0.05)',  # 卡片阴影色
}


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
    if depth > 5:
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
        if lowered_key in {"id", "uid", "userid", "user_id", "memberid", "member_id"}:
            score += 4
        if lowered_key in {"name", "nickname", "realname", "real_name", "username", "user_name"}:
            score += 3
        if lowered_key in {"email", "mail", "mobile", "phone", "avatar", "avatarurl"}:
            score += 2
        if lowered_key in {"company", "companyname", "team", "teamname", "role", "rolename"}:
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
        for key in ("name", "title", "label", "nickname", "realName", "teamName", "companyName", "roleName"):
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
        read_identity(("name", "nickname", "nickName", "realName", "real_name", "username", "userName"))
        or read_identity(("mobile", "phone", "email", "mail"))
        or "蓝湖用户"
    )
    email = read_identity(("email", "mail"))
    mobile = read_identity(("mobile", "phone", "tel", "telephone"))
    username = read_identity(("username", "userName", "account", "loginName"))
    nickname = read_identity(("nickname", "nickName"))
    user_id = read_identity(("id", "userId", "uid", "user_id", "memberId", "member_id"))
    avatar = read_identity((
        "avatar",
        "avatarUrl",
        "avatar_url",
        "headImg",
        "head_img",
        "headimgurl",
        "portrait",
        "photo",
    ))
    company = read_identity(("company", "companyName", "enterprise", "organization", "orgName"))
    team = read_identity(("team", "teamName", "space", "workspace", "projectTeam"))
    role = read_identity(("role", "roleName", "identity", "permission", "position"))
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
    user_info = user_info or {}
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
            content = response.read(1024 * 1024)
        if content:
            cache_path.write_bytes(content)
            return cache_path
    except (OSError, urllib.error.URLError, TimeoutError):
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
    "/api/project/list",
    "/api/project/list?type=all",
    "/api/project/list?project_type=all",
    "/api/projects",
    "/api/projects/list",
    "/api/project/projects",
    "/api/project/my",
    "/api/team/projects",
    "/api/teams/projects",
    "/api/project/my_projects",
    "/api/v1/project/list",
    "/api/v1/projects",
]

USER_PROFILE_ENDPOINTS = [
    "/api/user/info",
    "/api/user/profile",
    "/api/user/current",
    "/api/user/getCurrentUser",
    "/api/member/info",
    "/api/account/info",
    "/api/session",
]


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


def discover_mcp_tools() -> list[tuple[str, str]]:
    """发现当前服务支持的全部 MCP 工具。"""
    discovered: dict[str, str] = {}
    for source_path in tool_source_candidates():
        for tool_name, description in scan_mcp_tools_from_file(source_path):
            discovered.setdefault(tool_name, description)
    if not discovered:
        discovered = TOOL_DESCRIPTIONS.copy()
    return sorted(discovered.items(), key=lambda item: tool_sort_key(item[0]))


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
    """生成访问蓝湖 Web API 的基础请求头。"""
    return {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 LanhuMCP Desktop",
        "Accept": "application/json, text/plain, */*",
        "Referer": DEFAULT_LANHU_LOGIN_URL,
    }


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
            for key in ("project_id", "projectId", "pid", "id")
        ) and any(
            key in value
            for key in ("name", "project_name", "projectName", "title")
        )
        if has_project_marker:
            items.append(value)
        for nested_value in value.values():
            items.extend(collect_dict_items(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            items.extend(collect_dict_items(nested_value))
    return items


def normalize_project_item(item: dict) -> dict:
    """把蓝湖不同接口返回的项目字段统一为界面可用结构。"""
    team_payload = parse_json_object(item.get("team") or item.get("workspace") or {})
    owner_payload = parse_json_object(item.get("owner") or item.get("creator") or item.get("user") or {})
    project_id = (
        item.get("project_id")
        or item.get("projectId")
        or item.get("pid")
        or item.get("projectID")
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
        "raw": item,
    }


def fetch_lanhu_projects(cookie: str) -> tuple[bool, str, list[dict]]:
    """尝试读取当前账号可访问项目列表。"""
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
        projects = [
            normalize_project_item(item)
            for item in collect_dict_items(payload)
        ]
        unique_projects: dict[str, dict] = {}
        for project in projects:
            key = project.get("id") or project.get("url") or project.get("name")
            if key:
                unique_projects.setdefault(str(key), project)
        if unique_projects:
            return True, f"已从 {endpoint} 读取项目", list(unique_projects.values())
        errors.append(f"{endpoint}: 未发现项目字段")
    return False, "；".join(errors[-3:]) if errors else "未读取到项目", []


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
    """应用现代主题样式"""
    # ttk 必须在函数内部导入，避免依赖 create_gui 的局部变量。
    from tkinter import ttk

    style = ttk.Style()

    # 尝试使用 clam 主题作为基础（比默认好看）
    available_themes = style.theme_names()
    if 'clam' in available_themes:
        style.theme_use('clam')

    # ===== 全局配置 =====
    style.configure('.', background=COLORS['bg'], foreground=COLORS['text_primary'])
    style.map('.', background=[('active', COLORS['primary_hover'])])

    # ===== Frame =====
    style.configure('TFrame', background=COLORS['bg'])
    style.configure('Card.TFrame', background=COLORS['card'])

    # ===== Label =====
    style.configure('TLabel', background=COLORS['bg'], foreground=COLORS['text_primary'],
                    font=('Segoe UI', 9))
    style.configure('Title.TLabel', background=COLORS['bg'], foreground=COLORS['text_primary'],
                    font=('Segoe UI', 24, 'bold'))
    style.configure('Subtitle.TLabel', background=COLORS['bg'], foreground=COLORS['text_secondary'],
                    font=('Segoe UI', 10))
    style.configure('Status.TLabel', background=COLORS['card'], foreground=COLORS['text_primary'],
                    font=('Segoe UI', 11, 'bold'))
    style.configure('StatusRunning.TLabel', background=COLORS['card'], foreground=COLORS['success'],
                    font=('Segoe UI', 11, 'bold'))
    style.configure('StatusError.TLabel', background=COLORS['card'], foreground=COLORS['danger'],
                    font=('Segoe UI', 11, 'bold'))
    style.configure('StatusWarn.TLabel', background=COLORS['card'], foreground=COLORS['warning'],
                    font=('Segoe UI', 11, 'bold'))
    style.configure('Hint.TLabel', background=COLORS['card'], foreground=COLORS['text_muted'],
                    font=('Segoe UI', 8))

    # ===== LabelFrame（卡片容器）=====
    style.configure('Card.TLabelframe', background=COLORS['card'], foreground=COLORS['text_primary'])
    style.configure('Card.TLabelframe.Label', background=COLORS['card'],
                    foreground=COLORS['primary'], font=('Segoe UI', 10, 'bold'),
                    padding=(10, 5, 0, 5))
    style.configure('TLabelframe', background=COLORS['card'], foreground=COLORS['text_primary'])
    style.configure('TLabelframe.Label', background=COLORS['card'],
                    foreground=COLORS['primary'], font=('Segoe UI', 10, 'bold'))

    # ===== Button =====
    style.configure('TButton', font=('Segoe UI', 9), padding=(12, 6),
                    background='#FFFFFF', foreground=COLORS['text_primary'],
                    borderwidth=1, relief='solid')
    style.map('TButton',
              background=[('active', COLORS['primary_light'] if 'primary_light' in COLORS else '#E0E7FF'),
                         ('pressed', COLORS['primary'])],
              foreground=[('active', COLORS['primary']), ('pressed', '#FFFFFF')],
              bordercolor=[('focus', COLORS['primary'])])

    style.configure('Primary.TButton', font=('Segoe UI', 10, 'bold'), padding=(16, 8),
                    background=COLORS['primary'], foreground='#FFFFFF',
                    borderwidth=0, relief='flat')
    style.map('Primary.TButton',
              background=[('active', COLORS['primary_hover']), ('pressed', '#2D4BD4')],
              foreground=[('active', '#FFFFFF'), ('pressed', '#FFFFFF')])

    style.configure('Success.TButton', font=('Segoe UI', 9), padding=(12, 6),
                    background=COLORS['success'], foreground='#FFFFFF',
                    borderwidth=0, relief='flat')
    style.map('Success.TButton',
              background=[('active', '#16A34A'), ('pressed', '#15803D')])

    style.configure('Danger.TButton', font=('Segoe UI', 9), padding=(12, 6),
                    background=COLORS['danger'], foreground='#FFFFFF',
                    borderwidth=0, relief='flat')
    style.map('Danger.TButton',
              background=[('active', '#DC2626'), ('pressed', '#B91C1C')])

    style.configure('Small.TButton', font=('Segoe UI', 8), padding=(8, 4),
                    background=COLORS['border_light'], foreground=COLORS['text_secondary'],
                    borderwidth=0, relief='flat')

    # ===== Entry =====
    style.configure('TEntry', font=('Consolas', 9), padding=(8, 6),
                    fieldbackground='#FFFFFF', insertcolor=COLORS['text_primary'])

    # ===== ScrolledText =====
    style.configure('Log.TFrame', background=COLORS['log_bg'])

    return style


def create_gui() -> None:
    """创建 Lanhu MCP 桌面控制台。"""
    bootstrap_tcl_tk_runtime()
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        ctypes.windll.user32.MessageBoxW(0, "需要安装 tkinter", "错误", 0)
        return

    try:
        root = tk.Tk()
    except Exception as error:
        flog(f"Tkinter 窗口创建失败: {error}", 'error')
        ctypes.windll.user32.MessageBoxW(0, f"GUI 启动失败:\n{error}", "错误", 0)
        return

    root.title("Lanhu MCP 控制台")
    icon_path = APP_DIR / 'icon.ico'
    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass
    root.geometry("1180x760")
    root.minsize(1040, 680)
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
    header_title_var = tk.StringVar(value="服务")
    header_desc_var = tk.StringVar(value="启动前会校验蓝湖登录态，启动后显示全部 MCP 方法。")
    service_status_var = tk.StringVar(value="● 未运行")
    service_hint_var = tk.StringVar(value="请先登录蓝湖账号，然后启动 MCP 服务。")
    account_count_var = tk.StringVar(value="0 个账号")
    ide_count_var = tk.StringVar(value="0 / 0")
    account_options: list[dict] = []
    full_cookie = load_cookie()
    cookie_var.set(full_cookie)

    main = tk.Frame(root, bg=COLORS['bg'])
    main.pack(fill=tk.BOTH, expand=True)

    sidebar = tk.Frame(main, width=228, bg=COLORS['sidebar'])
    sidebar.pack(side=tk.LEFT, fill=tk.Y)
    sidebar.pack_propagate(False)

    content = tk.Frame(main, bg=COLORS['bg'])
    content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    brand = tk.Frame(sidebar, bg=COLORS['sidebar'])
    brand.pack(fill=tk.X, padx=18, pady=(22, 20))
    brand_mark = tk.Frame(brand, bg=COLORS['sidebar'])
    brand_mark.pack(anchor='w', fill=tk.X)
    mark_box = tk.Frame(brand_mark, bg="#2563EB", width=34, height=34)
    mark_box.pack(side=tk.LEFT)
    mark_box.pack_propagate(False)
    tk.Label(mark_box, text="L", fg="#FFFFFF", bg="#2563EB", font=('Segoe UI', 15, 'bold')).pack(expand=True)
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
        fg="#AAB4C2",
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
        fg="#7DD3FC",
        bg=COLORS['sidebar'],
        font=('Segoe UI', 8, 'bold'),
    ).pack(anchor='w', pady=(0, 5))
    tk.Label(
        sidebar_footer,
        textvariable=login_status_var,
        fg="#C7D2FE",
        bg=COLORS['sidebar'],
        font=('Segoe UI', 9),
        wraplength=184,
        justify=tk.LEFT,
    ).pack(anchor='w')

    header = tk.Frame(content, bg=COLORS['bg'])
    header.pack(fill=tk.X, padx=24, pady=(22, 14))
    header_text = tk.Frame(header, bg=COLORS['bg'])
    header_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Label(
        header_text,
        textvariable=header_title_var,
        bg=COLORS['bg'],
        fg=COLORS['text_primary'],
        font=('Segoe UI', 22, 'bold'),
    ).pack(anchor='w')
    tk.Label(
        header_text,
        textvariable=header_desc_var,
        bg=COLORS['bg'],
        fg=COLORS['text_secondary'],
        font=('Segoe UI', 10),
    ).pack(anchor='w', pady=(4, 0))
    header_stats = tk.Frame(header, bg=COLORS['bg'])
    header_stats.pack(side=tk.RIGHT)
    for stat_label, stat_var in (
        ("账号", account_count_var),
        ("项目", project_count_var),
        ("方法", tk.StringVar(value=str(len(MCP_TOOL_NAMES)))),
    ):
        stat_cell = tk.Frame(header_stats, bg="#FFFFFF", highlightbackground=COLORS['border_light'], highlightthickness=1)
        stat_cell.pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(stat_cell, text=stat_label, bg="#FFFFFF", fg=COLORS['text_muted'], font=('Segoe UI', 8)).pack(padx=12, pady=(7, 0))
        tk.Label(stat_cell, textvariable=stat_var, bg="#FFFFFF", fg=COLORS['text_primary'], font=('Segoe UI', 10, 'bold')).pack(padx=12, pady=(1, 7))

    page_shell = tk.Frame(content, bg=COLORS['bg'])
    page_shell.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 18))
    pages: dict[str, tk.Frame] = {}
    nav_buttons: dict[str, tk.Frame] = {}
    icon_images: dict[str, object] = {}
    avatar_images: dict[str, object] = {}

    def create_page(page_key: str) -> tk.Frame:
        """创建一个右侧页面容器。"""
        page = tk.Frame(page_shell, bg=COLORS['bg'])
        pages[page_key] = page
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

        if icon_name in ("service", "server-cog", "settings"):
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
        """创建自绘卡片容器，统一边距、标题和浅边框。"""
        card = tk.Frame(
            parent,
            bg=COLORS['card'],
            highlightbackground=COLORS['border_light'],
            highlightcolor=COLORS['border_light'],
            highlightthickness=1,
            bd=0,
        )
        header_frame = tk.Frame(card, bg=COLORS['card'])
        header_frame.pack(fill=tk.X, padx=padding, pady=(padding, 8))
        make_icon_label(header_frame, icon_name, COLORS['primary']).pack(side=tk.LEFT)
        tk.Label(
            header_frame,
            text=title,
            bg=COLORS['card'],
            fg=COLORS['text_primary'],
            font=('Segoe UI', 10, 'bold'),
        ).pack(side=tk.LEFT, padx=(8, 0))
        body = ttk.Frame(card, style='Card.TFrame')
        body.pack(fill=tk.BOTH, expand=True, padx=padding, pady=(0, padding))
        setattr(card, "body", body)
        return card

    def card_body(card: tk.Frame) -> ttk.Frame:
        """返回卡片内容区。"""
        return getattr(card, "body")

    def set_nav_active(page_key: str) -> None:
        """更新左侧导航选中态。"""
        for key, button in nav_buttons.items():
            is_active = key == page_key
            bg_color = COLORS['sidebar_active'] if is_active else COLORS['sidebar']
            fg_color = '#FFFFFF' if is_active else COLORS['sidebar_text']
            button.config(bg=bg_color)
            indicator = getattr(button, "indicator", None)
            if indicator:
                indicator.config(bg=COLORS['primary'] if is_active else bg_color)
            for child in button.winfo_children():
                child.config(bg=bg_color)
                if isinstance(child, tk.Label):
                    child.config(fg=fg_color)

    def show_page(page_key: str) -> None:
        """切换主内容页面。"""
        page_meta = {
            "service": ("服务", "登录蓝湖后启动 MCP 服务，启动成功后显示全部可用方法。"),
            "projects": ("项目", "读取当前蓝湖账号可访问的项目，便于复制项目链接给 AI 使用。"),
            "tools": ("AI 工具", "自动识别 Codex、Claude、Mimo、Cursor、Trae 等工具并写入 MCP 配置。"),
            "account": ("账号", "蓝湖登录信息集中管理，支持多用户保存、切换和退出。"),
            "logs": ("日志", "查看服务输出、登录诊断和配置写入记录。"),
        }
        for page in pages.values():
            page.pack_forget()
        pages[page_key].pack(fill=tk.BOTH, expand=True)
        header_title_var.set(page_meta[page_key][0])
        header_desc_var.set(page_meta[page_key][1])
        set_nav_active(page_key)

    nav_items = [
        ("service", "service", "服务"),
        ("projects", "projects", "项目"),
        ("tools", "tools", "AI 工具"),
        ("account", "account", "账号"),
        ("logs", "logs", "日志"),
    ]
    tk.Label(
        nav_host,
        text="菜单",
        anchor='w',
        fg="#8EA0B8",
        bg=COLORS['sidebar'],
        font=('Segoe UI', 8, 'bold'),
    ).pack(fill=tk.X, padx=12, pady=(0, 6))
    for key, icon_name, title in nav_items:
        nav_button = tk.Frame(
            nav_host,
            bg=COLORS['sidebar'],
            cursor='hand2',
        )
        nav_button.pack(fill=tk.X, pady=3)
        nav_indicator = tk.Frame(nav_button, width=3, bg=COLORS['sidebar'])
        nav_indicator.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        setattr(nav_button, "indicator", nav_indicator)
        nav_icon = create_lucide_icon(nav_button, icon_name, COLORS['sidebar_text'], 17, COLORS['sidebar'])
        nav_icon.pack(side=tk.LEFT, padx=(4, 8), pady=11)
        nav_label = tk.Label(
            nav_button,
            text=title,
            anchor='w',
            bg=COLORS['sidebar'],
            fg=COLORS['sidebar_text'],
            cursor='hand2',
            font=('Segoe UI', 10, 'bold'),
        )
        nav_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=11)
        nav_button.bind("<Button-1>", lambda event, page_key=key: show_page(page_key))
        nav_icon.bind("<Button-1>", lambda event, page_key=key: show_page(page_key))
        nav_label.bind("<Button-1>", lambda event, page_key=key: show_page(page_key))
        nav_buttons[key] = nav_button

    service_page = create_page("service")
    projects_page = create_page("projects")
    tools_page = create_page("tools")
    account_page = create_page("account")
    logs_page = create_page("logs")

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
    status_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
    method_card = make_card(service_top, f"支持的方法 ({len(MCP_TOOL_NAMES)})", "list-checks")
    method_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
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
    port_entry = ttk.Entry(service_status_row, textvariable=port_var, width=8, font=('Consolas', 11, 'bold'))
    port_entry.pack(side=tk.LEFT)

    service_actions = ttk.Frame(status_body, style='Card.TFrame')
    service_actions.pack(fill=tk.X, pady=(18, 0))
    start_btn = ttk.Button(service_actions, text="启动服务", style='Primary.TButton', width=15)
    start_btn.pack(side=tk.LEFT)
    stop_btn = ttk.Button(service_actions, text="停止", style='Danger.TButton', width=10, state=tk.DISABLED)
    stop_btn.pack(side=tk.LEFT, padx=(10, 0))
    ttk.Button(
        service_actions,
        text="打开",
        style='Small.TButton',
        width=13,
        command=lambda: webbrowser.open(f"http://localhost:{port_var.get()}/"),
    ).pack(side=tk.LEFT, padx=(10, 0))
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
        cell = tk.Frame(capability_frame, bg='#F8FAFC', highlightbackground=COLORS['border_light'], highlightthickness=1)
        cell.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Label(cell, text=label_text, bg='#F8FAFC', fg=COLORS['text_muted'], font=('Segoe UI', 8)).pack(anchor='w', padx=10, pady=(8, 0))
        tk.Label(cell, textvariable=value_var, bg='#F8FAFC', fg=COLORS['text_primary'], font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(2, 8))

    tools_grid = ttk.Frame(method_body, style='Card.TFrame')
    tools_grid.pack(fill=tk.BOTH, expand=True)

    def render_tool_list(enabled: bool = False) -> None:
        """根据服务状态渲染 MCP 工具方法清单。"""
        for widget in tools_grid.winfo_children():
            widget.destroy()
        if not enabled:
            ttk.Label(
                tools_grid,
                text=f"服务启动成功后显示当前支持的全部 {len(MCP_TOOL_NAMES)} 个 MCP 方法。",
                style='Hint.TLabel',
                background=COLORS['card'],
                wraplength=420,
            ).grid(row=0, column=0, sticky='w')
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
    project_status_card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
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
    project_action_card.pack(side=tk.LEFT, fill=tk.X, expand=True)
    project_action_body = card_body(project_action_card)
    refresh_projects_btn = ttk.Button(project_action_body, text="刷新项目", style='Primary.TButton')
    refresh_projects_btn.pack(side=tk.LEFT)
    open_lanhu_home_btn = ttk.Button(
        project_action_body,
        text="打开蓝湖",
        style='TButton',
        command=lambda: webbrowser.open(DEFAULT_LANHU_LOGIN_URL),
    )
    open_lanhu_home_btn.pack(side=tk.LEFT, padx=(10, 0))

    projects_card = make_card(projects_page, "当前账号项目", "folder-kanban")
    projects_card.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
    projects_body = card_body(projects_card)
    projects_list = ttk.Frame(projects_body, style='Card.TFrame')
    projects_list.pack(fill=tk.BOTH, expand=True)

    def render_project_rows(projects: list[dict], message: str = "") -> None:
        """渲染当前账号项目列表。"""
        for widget in projects_list.winfo_children():
            widget.destroy()
        project_count_var.set(f"{len(projects)} 个项目")
        if not projects:
            empty_text = message or "尚未读取到项目。请先登录账号，然后点击刷新项目。"
            ttk.Label(
                projects_list,
                text=empty_text,
                style='Hint.TLabel',
                background=COLORS['card'],
                wraplength=720,
            ).pack(anchor='w')
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
            ttk.Button(actions, text="打开", style='Small.TButton', width=8, command=open_project).pack(side=tk.LEFT)
            ttk.Button(actions, text="复制", style='Small.TButton', width=8, command=copy_project).pack(side=tk.LEFT, padx=(8, 0))

    def refresh_projects() -> None:
        """后台刷新当前登录账号的项目列表。"""
        active = get_active_account()
        if not active or not active.get("cookie"):
            project_status_var.set("请先登录蓝湖账号。")
            render_project_rows([], "请先在账号页登录蓝湖账号，然后再刷新项目。")
            show_page("account")
            return
        refresh_projects_btn.config(state=tk.DISABLED)
        project_status_var.set("正在读取蓝湖项目...")
        log("正在读取当前账号项目列表", 'info')

        def _load() -> None:
            ok, message, projects = fetch_lanhu_projects(active.get("cookie", ""))
            root.after(0, lambda: _finish(ok, message, projects))

        def _finish(ok: bool, message: str, projects: list[dict]) -> None:
            refresh_projects_btn.config(state=tk.NORMAL)
            project_status_var.set(message)
            render_project_rows(projects, message)
            log(message, 'success' if ok else 'warn')

        threading.Thread(target=_load, daemon=True).start()

    refresh_projects_btn.config(command=refresh_projects)
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
    ttk.Button(
        login_url_row,
        text="浏览器打开",
        style='Small.TButton',
        width=14,
        command=lambda: webbrowser.open(login_url_var.get().strip() or DEFAULT_LANHU_LOGIN_URL),
    ).pack(side=tk.LEFT)

    account_button_row = ttk.Frame(account_body, style='Card.TFrame')
    account_button_row.pack(fill=tk.X, pady=(14, 0))
    login_btn = ttk.Button(account_button_row, text="添加账号 / 一键登录", style='Primary.TButton')
    login_btn.pack(side=tk.LEFT)
    save_cookie_btn = ttk.Button(account_button_row, text="保存 Cookie", style='Success.TButton')
    save_cookie_btn.pack(side=tk.LEFT, padx=(10, 0))
    logout_btn = ttk.Button(account_button_row, text="退出当前账号", style='Danger.TButton')
    logout_btn.pack(side=tk.LEFT, padx=(10, 0))

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
            login_status_var.set(f"当前账号\n{active.get('name', '蓝湖用户')}")
            service_hint_var.set("账号已就绪，可以启动 MCP 服务。")
            project_status_var.set("账号已就绪，可刷新当前用户项目。")
        else:
            account_var.set("")
            full_cookie = ""
            cookie_var.set("")
            account_title_var.set("未登录蓝湖")
            account_meta_var.set("登录后才能启动 MCP 服务；支持多个蓝湖账号切换。")
            login_status_var.set("未登录\n服务启动会被拦截")
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
                root.after(0, lambda: render_account_rows(get_accounts(), get_active_account().get("id", "") if get_active_account() else ""))

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
    save_cookie_btn.config(command=do_save_cookie)
    logout_btn.config(command=do_logout_account)

    # AI 工具页
    tools_summary = tk.Frame(tools_page, bg=COLORS['bg'])
    tools_summary.pack(fill=tk.X)
    tools_status_card = make_card(tools_summary, "识别概览", "bot")
    tools_status_card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
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
    tools_action_card.pack(side=tk.LEFT, fill=tk.X, expand=True)
    tools_action_body = card_body(tools_action_card)
    config_all_btn = ttk.Button(tools_action_body, text="一键配置全部", style='Primary.TButton')
    config_all_btn.pack(side=tk.LEFT)
    refresh_ide_btn = ttk.Button(tools_action_body, text="重新检测", style='TButton')
    refresh_ide_btn.pack(side=tk.LEFT, padx=(10, 0))

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
        max_cols = 2
        for index, (name, installed) in enumerate(detected.items()):
            row = index // max_cols
            col = index % max_cols
            cell = ttk.Frame(ide_grid, style='Card.TFrame', padding=(0, 6))
            cell.grid(row=row, column=col, sticky='ew', padx=(0 if col == 0 else 16, 0), pady=3)
            ide_grid.columnconfigure(col, weight=1)
            detail = details.get(name, {})
            title = ttk.Frame(cell, style='Card.TFrame')
            title.pack(fill=tk.X)
            status_text = "●" if installed else "○"
            status_color = COLORS['success'] if installed else COLORS['text_muted']
            ttk.Label(
                title,
                text=f"{status_text} {name}",
                foreground=status_color,
                background=COLORS['card'],
                font=('Segoe UI', 9, 'bold' if installed else 'normal'),
            ).pack(side=tk.LEFT)
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

                ttk.Button(title, text="配置", style='Small.TButton', width=10, command=make_cfg).pack(side=tk.RIGHT)
            detail_text = detail.get('exe_path') or detail.get('config_path') or "未发现安装路径或配置目录"
            ttk.Label(
                cell,
                text=str(detail_text),
                style='Hint.TLabel',
                background=COLORS['card'],
                wraplength=420,
            ).pack(anchor='w', pady=(4, 0))
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
            status_lbl.config(style='StatusRunning.TLabel')
            start_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)
            service_hint_var.set(f"MCP 地址: {current_mcp_url(int(port_var.get()))}")
            render_tool_list(True)
            update_mcp_code()
            log(f"[OK] {msg} -> http://localhost:{port_var.get()}/", 'success')
            return
        service_status_var.set("● 启动失败")
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
        status_lbl.config(style='StatusError.TLabel')
        start_btn.config(state=tk.NORMAL)
        stop_btn.config(state=tk.DISABLED)
        service_hint_var.set("服务已停止。")
        render_tool_list(False)
        log(f"[STOP] {msg}", 'info' if ok else 'warn')

    start_btn.config(command=do_start)
    stop_btn.config(command=do_stop)

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
    show_page("service")
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
