"""Default-browser login bridge for Lanhu.

The desktop app opens the user's normal browser and watches the local browser
cookie store for a Lanhu authentication cookie.  This keeps the login session
in the browser the user already trusts, while only returning Lanhu cookies to
the local app.
"""

from __future__ import annotations

import os
import time
import webbrowser
from collections.abc import Callable, Iterable

DEFAULT_DOMAIN = "lanhuapp.com"
DEFAULT_TIMEOUT_SECONDS = 300.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.5


def _default_browser_kind() -> str:
    """Return the Windows HTTPS default browser family when detectable."""
    if os.name != "nt":
        return ""
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            prog_id = str(winreg.QueryValueEx(key, "ProgId")[0]).lower()
    except (OSError, ImportError):
        return ""
    if "edge" in prog_id:
        return "edge"
    if "chrome" in prog_id:
        return "chrome"
    if "firefox" in prog_id:
        return "firefox"
    if "brave" in prog_id:
        return "brave"
    if "opera" in prog_id:
        return "opera"
    return ""


def _reader_order() -> list[tuple[str, Callable[..., object]]]:
    try:
        import browser_cookie3
    except ImportError:
        return []

    readers: dict[str, Callable[..., object]] = {
        "chrome": browser_cookie3.chrome,
        "edge": browser_cookie3.edge,
        "firefox": browser_cookie3.firefox,
        "brave": browser_cookie3.brave,
        "opera": browser_cookie3.opera,
        "chromium": browser_cookie3.chromium,
    }
    preferred = _default_browser_kind()
    ordered: list[tuple[str, Callable[..., object]]] = []
    if preferred and preferred in readers:
        ordered.append((preferred, readers.pop(preferred)))
    ordered.extend(readers.items())
    return ordered


def _iter_cookie_objects(raw: object) -> Iterable[object]:
    if raw is None:
        return ()
    try:
        return iter(raw)  # type: ignore[arg-type]
    except TypeError:
        return ()


def _format_cookie_objects(raw: object, domain: str) -> str:
    pairs: list[str] = []
    seen: set[str] = set()
    domain_text = domain.lower().lstrip(".")
    for item in _iter_cookie_objects(raw):
        name = str(getattr(item, "name", "") or "").strip()
        value = getattr(item, "value", None)
        host = str(getattr(item, "domain", "") or "").lower().lstrip(".")
        if not name or value is None:
            continue
        if host and domain_text not in host:
            continue
        if name in seen:
            continue
        seen.add(name)
        pairs.append(f"{name}={value}")
    return "; ".join(pairs)


def read_default_browser_cookie(domain: str = DEFAULT_DOMAIN) -> tuple[str, str, list[str]]:
    """Read Lanhu cookies from the preferred installed browser.

    The return value is ``(cookie_header, browser_name, diagnostics)``.  A
    missing optional dependency or a locked browser database is reported in
    diagnostics instead of raising into the UI thread.
    """
    readers = _reader_order()
    if not readers:
        return "", "", [
            "未安装 browser-cookie3，无法读取默认浏览器 Cookie；请重新运行安装程序。",
            "browser-cookie-read-unavailable",
        ]

    diagnostics: list[str] = []
    readable_stores = 0
    for browser_name, reader in readers:
        try:
            raw = reader(domain_name=domain)
            readable_stores += 1
            cookie = _format_cookie_objects(raw, domain)
            if cookie:
                return cookie, browser_name, diagnostics
        except Exception as error:  # noqa: BLE001 - browser stores differ by platform
            diagnostics.append(f"{browser_name}: {error}")
    if readable_stores == 0:
        diagnostics.append("browser-cookie-read-unavailable")
    return "", "", diagnostics


def run_default_browser_login(
    login_url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    open_browser: Callable[[str], object] | None = None,
    read_cookie: Callable[[], tuple[str, str, list[str]]] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Open the default browser and wait for a valid Lanhu login cookie."""
    normalized_url = (login_url or "https://lanhuapp.com/web/").strip()
    opener = open_browser or (lambda url: webbrowser.open(url, new=2, autoraise=True))
    reader = read_cookie or (lambda: read_default_browser_cookie(DEFAULT_DOMAIN))
    diagnostics: list[str] = []
    try:
        opened = opener(normalized_url)
        if opened is False:
            diagnostics.append("系统默认浏览器未返回打开成功状态，仍会继续检测 Cookie。")
    except Exception as error:  # noqa: BLE001
        return {
            "status": "error",
            "cookies": "",
            "user": {},
            "storage": {},
            "url": normalized_url,
            "error": f"无法打开系统默认浏览器: {error}",
            "diagnostics": diagnostics,
            "source": "default-browser",
        }

    deadline = time.monotonic() + max(1.0, float(timeout))
    last_browser = ""
    while time.monotonic() < deadline:
        try:
            cookie, browser_name, read_diagnostics = reader()
        except Exception as error:  # noqa: BLE001
            cookie, browser_name, read_diagnostics = "", "", [str(error)]
        if browser_name and browser_name != last_browser:
            last_browser = browser_name
            diagnostics.append(f"正在检测 {browser_name} 浏览器的蓝湖登录状态")
            if on_status:
                on_status(diagnostics[-1])
        if read_diagnostics:
            diagnostics.extend(read_diagnostics[-2:])
        if "browser-cookie-read-unavailable" in read_diagnostics:
            return {
                "status": "error",
                "cookies": "",
                "user": {},
                "storage": {},
                "url": normalized_url,
                "login_url": normalized_url,
                "error": (
                    "默认浏览器的 Cookie 数据库当前不可读取。请关闭浏览器后重试；"
                    "若公司设备限制本地 Cookie 读取，请使用手动 Cookie 登录。"
                ),
                "diagnostics": diagnostics,
                "source": "default-browser",
            }
        if cookie:
            try:
                from lanhu_login_helper import has_valid_auth_cookie

                valid = has_valid_auth_cookie(cookie)
            except Exception:
                valid = False
            if valid:
                try:
                    from ..core.accounts import user_info_from_cookie

                    user = user_info_from_cookie(cookie)
                except Exception:
                    user = {}
                diagnostics.append("已从默认浏览器读取到有效蓝湖登录 Cookie")
                return {
                    "status": "success",
                    "cookies": cookie,
                    "user": user,
                    "storage": {},
                    "sessionStorage": {},
                    "appState": {},
                    "url": normalized_url,
                    "login_url": normalized_url,
                    "diagnostics": diagnostics,
                    "source": "default-browser",
                }
        time.sleep(max(0.2, float(poll_interval)))

    return {
        "status": "cancelled",
        "cookies": "",
        "user": {},
        "storage": {},
        "url": normalized_url,
        "login_url": normalized_url,
        "error": "等待超时，未检测到有效蓝湖登录 Cookie。请确认已在默认浏览器完成登录后再点击刷新。",
        "diagnostics": diagnostics,
        "source": "default-browser",
    }


__all__ = [
    "DEFAULT_DOMAIN",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "read_default_browser_cookie",
    "run_default_browser_login",
]
