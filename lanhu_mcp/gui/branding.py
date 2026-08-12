"""Shared Lanhu MCP branding assets for the desktop shell."""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import os
from functools import lru_cache
from pathlib import Path

from ..core.paths import APP_DIR, FROZEN_TEMP_DIR


def _asset_path(filename: str) -> Path:
    candidates = [
        FROZEN_TEMP_DIR / "assets" / filename,
        APP_DIR / "assets" / filename,
        Path(__file__).resolve().parents[2] / "assets" / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def logo_path() -> Path:
    return _asset_path("lanhu_mcp_logo.png")


def logo_ico_path() -> Path:
    return _asset_path("lanhu_mcp.ico")


def banner_path(name: str = "shared") -> Path:
    """Return a page banner, falling back to the shared artwork."""
    requested = _asset_path(f"banner-{name}.png")
    if requested.exists():
        return requested
    return _asset_path("banner-shared.png")


def window_icon_path() -> Path:
    """Return the native window icon format supported by the current OS."""
    return logo_ico_path() if os.name == "nt" else logo_path()


WINDOW_APP_USER_MODEL_ID = "LanhuMCP.Desktop"
_runtime_icon_handles: list[int] = []


def apply_windows_app_identity(window_title: str) -> bool:
    """Apply the supplied logo to the live Flet window on Windows.

    The PyInstaller icon covers the executable, but Flutter/Flet creates its
    own native window class at runtime. Setting both the AppUserModelID and
    the live HWND icon prevents Windows from showing the framework's default
    red/blue icon in the taskbar. The icon handle is kept alive for the
    lifetime of the process because Windows does not copy it for WM_SETICON.
    """
    if os.name != "nt":
        return False
    try:
        shell32 = ctypes.windll.shell32
        shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(WINDOW_APP_USER_MODEL_ID))

        user32 = ctypes.windll.user32
        user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int

        current_pid = os.getpid()
        found_hwnd = wintypes.HWND()

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def visit(hwnd, _lparam):
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if process_id.value != current_pid or not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(max(length + 1, 2))
            user32.GetWindowTextW(hwnd, title, len(title))
            if title.value == window_title or not found_hwnd.value:
                found_hwnd.value = hwnd
                if title.value == window_title:
                    return False
            return True

        user32.EnumWindows(visit, 0)
        hwnd = found_hwnd.value
        if not hwnd:
            return False

        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            ctypes.c_wchar_p,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        image_icon = 1
        load_from_file = 0x00000010
        icon_handle = user32.LoadImageW(
            None,
            str(logo_ico_path()),
            image_icon,
            48,
            48,
            load_from_file,
        )
        if not icon_handle:
            return False

        user32.SendMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.SendMessageW.restype = wintypes.LRESULT
        user32.SendMessageW(hwnd, 0x0080, 1, icon_handle)  # WM_SETICON/ICON_BIG
        user32.SendMessageW(hwnd, 0x0080, 0, icon_handle)  # WM_SETICON/ICON_SMALL
        _runtime_icon_handles.append(int(icon_handle))
        return True
    except (AttributeError, OSError, TypeError, ValueError):
        return False


@lru_cache(maxsize=1)
def logo_base64() -> str:
    try:
        return base64.b64encode(logo_path().read_bytes()).decode("ascii")
    except OSError:
        return ""


__all__ = [
    "WINDOW_APP_USER_MODEL_ID",
    "logo_path",
    "logo_ico_path",
    "banner_path",
    "window_icon_path",
    "logo_base64",
    "apply_windows_app_identity",
]
