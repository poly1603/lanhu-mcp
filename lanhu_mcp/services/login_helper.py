"""UI-agnostic launcher for the pywebview-based Lanhu login helper.

The login helper runs in a **separate process** (a pywebview window) so it can
host a WebView2/Edge browser without blocking or polluting the main GUI process.
Both the legacy Tkinter GUI and the new Flet GUI call :func:`run_login_helper`
to obtain the login result dictionary.

The returned dict mirrors what the helper writes to its result file, e.g.::

    {"status": "success", "cookies": "...", "user": {...}, "diagnostics": [...]}
    {"status": "error", "error": "..."}
    {"status": "cancelled"}

This module never imports any GUI toolkit; the caller is responsible for
running it off the UI thread and for parsing the user payload
(see :func:`lanhu_mcp.core.accounts.parse_user_payload`).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import List, Optional

from ..core.paths import APP_DIR, DATA_DIR, WEBVIEW_STORAGE_DIR, flog

__all__ = ["find_login_helper_script", "build_login_helper_command", "run_login_helper"]

# Fallback interpreter locations used only in source (non-frozen) mode when the
# active environment does not expose ``python`` on PATH.
_PYTHON_FALLBACKS = [
    r"C:\Users\swiml\AppData\Local\Programs\Python\Python312\python.exe",
]


def find_login_helper_script() -> Optional[Path]:
    """Locate ``lanhu_login_helper.py`` next to the app or repo root."""
    candidates = [
        APP_DIR / "lanhu_login_helper.py",
        Path(__file__).resolve().parent.parent.parent / "lanhu_login_helper.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _resolve_python_executable() -> Optional[str]:
    python_exe = shutil.which("python") or shutil.which("python3")
    if python_exe:
        return python_exe
    for candidate in _PYTHON_FALLBACKS:
        if os.path.exists(candidate):
            return candidate
    return None


def build_login_helper_command(result_file: Path, login_url: str) -> Optional[List[str]]:
    """Build the subprocess command for the login helper.

    Returns ``None`` when no usable interpreter / helper script can be found
    in source mode.
    """
    if getattr(sys, "frozen", False):
        # Packaged: re-invoke ourselves with the --login-helper branch.
        return [
            sys.executable,
            "--login-helper",
            str(result_file),
            str(WEBVIEW_STORAGE_DIR),
            login_url,
        ]

    helper_path = find_login_helper_script()
    if not helper_path:
        flog("找不到 lanhu_login_helper.py", "error")
        return None
    python_exe = _resolve_python_executable()
    if not python_exe:
        flog("找不到 Python 解释器，无法启动登录助手", "error")
        return None
    return [
        python_exe,
        str(helper_path),
        str(result_file),
        str(WEBVIEW_STORAGE_DIR),
        login_url,
    ]


def run_login_helper(login_url: str, *, timeout: float = 300.0) -> dict:
    """Run the login helper subprocess and return its result dictionary.

    This call is **blocking** and must be executed off the UI thread. The
    result file is read after the subprocess exits; if it is missing the login
    is treated as cancelled.
    """
    login_url = (login_url or "").strip()
    result_file = DATA_DIR / ".login_result.json"
    try:
        if result_file.exists():
            result_file.unlink()
    except OSError:
        pass

    command = build_login_helper_command(result_file, login_url)
    if not command:
        return {"status": "error", "error": "无法启动登录助手：缺少 Python 解释器或登录助手脚本。"}

    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        flog(f"启动登录助手子进程: {' '.join(command)}")
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        flog(f"登录助手退出码: {proc.returncode}")
        if stdout:
            flog(f"登录助手 stdout: {stdout.decode('utf-8', errors='replace')[:800]}")
        if stderr:
            flog(f"登录助手 stderr: {stderr.decode('utf-8', errors='replace')[:800]}")
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
        flog("登录助手超时", "error")
        return {"status": "error", "error": "登录助手超时，请重试或改用系统浏览器登录。"}
    except Exception as error:  # noqa: BLE001
        flog(f"登录助手异常: {error}", "error")
        flog(traceback.format_exc(), "error")
        return {"status": "error", "error": str(error)}

    if result_file.exists():
        try:
            return json.loads(result_file.read_text(encoding="utf-8"))
        except Exception as error:  # noqa: BLE001
            flog(f"解析登录结果失败: {error}", "error")
            return {"status": "error", "error": f"登录结果解析失败：{error}"}
    return {"status": "cancelled"}
