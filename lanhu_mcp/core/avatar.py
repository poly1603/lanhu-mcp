"""账号头像下载与本地缓存（带大小上限）。

从 ``lanhu_mcp_gui.py`` 抽取的纯逻辑，仅依赖标准库，供 Tkinter / Flet GUI 复用。
"""
from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .accounts import cookie_fingerprint
from .paths import AVATAR_CACHE_DIR, AVATAR_MAX_BYTES, flog

__all__ = [
    "avatar_cache_path",
    "download_avatar",
]


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
