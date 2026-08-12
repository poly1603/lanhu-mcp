"""Shared Lanhu MCP branding assets for the desktop shell."""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import os
from functools import lru_cache
from pathlib import Path
import uuid

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


class _Guid(ctypes.Structure):
    _fields_ = [("data", ctypes.c_ubyte * 16)]


class _PropertyKey(ctypes.Structure):
    _fields_ = [("fmtid", _Guid), ("pid", wintypes.DWORD)]


class _PropVariant(ctypes.Structure):
    _fields_ = [
        ("vt", wintypes.WORD),
        ("reserved1", wintypes.WORD),
        ("reserved2", wintypes.WORD),
        ("reserved3", wintypes.WORD),
        ("value", ctypes.c_void_p),
    ]


def _guid(value: str) -> _Guid:
    return _Guid((ctypes.c_ubyte * 16).from_buffer_copy(uuid.UUID(value).bytes_le))


def _set_window_app_user_model_id(hwnd: int) -> bool:
    """Attach Lanhu's shell identity to the native Flet window.

    Flet's Python process creates a separate ``flet.exe`` process.  Setting
    the AppUserModelID only on the Python process therefore does not fix the
    taskbar item.  Windows exposes the per-window property store for exactly
    this case; assigning the ID here makes the child window belong to Lanhu
    instead of presenting Flet's file metadata in the taskbar menu.
    """
    if not hwnd:
        return False
    try:
        ole32 = ctypes.windll.ole32
        shell32 = ctypes.windll.shell32
        ole32.CoInitializeEx(None, 2)

        iid = _guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")  # IPropertyStore
        key = _PropertyKey(_guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), 5)
        store = ctypes.c_void_p()
        shell32.SHGetPropertyStoreForWindow.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(_Guid),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        shell32.SHGetPropertyStoreForWindow.restype = ctypes.c_long
        if shell32.SHGetPropertyStoreForWindow(
            wintypes.HWND(hwnd), ctypes.byref(iid), ctypes.byref(store)
        ) != 0 or not store.value:
            return False

        vtable = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        SetValue = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.POINTER(_PropertyKey),
            ctypes.POINTER(_PropVariant),
        )(vtable[6])
        Commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[7])
        value = ctypes.create_unicode_buffer(WINDOW_APP_USER_MODEL_ID)
        prop = _PropVariant(vt=31, value=ctypes.cast(value, ctypes.c_void_p))  # VT_LPWSTR
        result = SetValue(store, ctypes.byref(key), ctypes.byref(prop))
        if result == 0:
            result = Commit(store)

        Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
        Release(store)
        return result == 0
    except (AttributeError, OSError, TypeError, ValueError):
        return False
    finally:
        try:
            ctypes.windll.ole32.CoUninitialize()
        except (AttributeError, OSError):
            pass


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
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int

        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        matching_hwnds: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def visit(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(max(length + 1, 2))
            user32.GetWindowTextW(hwnd, title, len(title))
            if title.value != window_title:
                return True
            matching_hwnds.append(int(hwnd))
            return True

        user32.EnumWindows(visit, 0)
        if not matching_hwnds:
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
        # ``ctypes.wintypes`` does not provide LRESULT on all Python builds.
        # It is a pointer-sized signed integer, so use the portable ctypes
        # spelling instead of allowing an AttributeError to cancel the whole
        # native identity update.
        user32.SendMessageW.restype = ctypes.c_ssize_t
        applied = False
        for hwnd in matching_hwnds:
            user32.SendMessageW(hwnd, 0x0080, 1, icon_handle)  # WM_SETICON/ICON_BIG
            user32.SendMessageW(hwnd, 0x0080, 0, icon_handle)  # WM_SETICON/ICON_SMALL
            # Flet can briefly expose both its host and view HWND with the
            # same title. Apply the shell identity to each matching window so
            # Windows cannot keep the child taskbar item under Flet.
            applied = _set_window_app_user_model_id(hwnd) or applied
        _runtime_icon_handles.append(int(icon_handle))
        return applied
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
