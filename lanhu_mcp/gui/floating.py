"""Small native Windows always-on-top service status window.

This deliberately uses user32/GDI through ctypes instead of a second Flet or
Tk window.  It keeps the floating indicator lightweight and avoids another
event loop or a second embedded browser surface.
"""

from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes
from typing import Callable, Optional

from .branding import logo_ico_path, logo_path, _asset_path


Callback = Callable[[], None]

if os.name == "nt":
    _user32 = ctypes.windll.user32
    _gdi32 = ctypes.windll.gdi32
    _kernel32 = ctypes.windll.kernel32
    _LRESULT = ctypes.c_ssize_t
    _WNDPROC = ctypes.WINFUNCTYPE(
        _LRESULT, wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t
    )

    class _Point(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class _Rect(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class _PaintStruct(ctypes.Structure):
        _fields_ = [
            ("hdc", ctypes.c_void_p),
            ("fErase", wintypes.BOOL),
            ("rcPaint", _Rect),
            ("fRestore", wintypes.BOOL),
            ("fIncUpdate", wintypes.BOOL),
            ("rgbReserved", ctypes.c_ubyte * 32),
        ]

    class _WndClass(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", _WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", ctypes.c_void_p),
            ("hIcon", ctypes.c_void_p),
            ("hCursor", ctypes.c_void_p),
            ("hbrBackground", ctypes.c_void_p),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    class _Msg(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", ctypes.c_size_t),
            ("lParam", ctypes.c_ssize_t),
            ("time", wintypes.DWORD),
            ("pt", _Point),
        ]

    _kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    _user32.CreateWindowExW.restype = wintypes.HWND
    _user32.CreatePopupMenu.restype = wintypes.HMENU
    _user32.TrackPopupMenu.restype = ctypes.c_uint
    _user32.BeginPaint.restype = ctypes.c_void_p
    _gdi32.CreateSolidBrush.restype = ctypes.c_void_p
    _gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
    _gdi32.Ellipse.restype = wintypes.BOOL

    # Explicit signatures keep HWND/HMENU values intact on 64-bit Windows;
    # ctypes otherwise defaults pointer parameters to 32-bit C ints.
    _kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    _user32.RegisterClassW.argtypes = [ctypes.POINTER(_WndClass)]
    _user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, ctypes.c_void_p, ctypes.c_void_p,
    ]
    _user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    _user32.GetSystemMetrics.restype = ctypes.c_int
    _user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
    _user32.SetTimer.restype = ctypes.c_size_t
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.ShowWindow.restype = wintypes.BOOL
    # The second argument accepts either a resource ID (IDC_ARROW) or a
    # string pointer, so keep it pointer-sized rather than LPCWSTR.
    _user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    _user32.LoadCursorW.restype = ctypes.c_void_p
    _user32.SetCursor.argtypes = [ctypes.c_void_p]
    _user32.SetCursor.restype = ctypes.c_void_p
    _user32.SetWindowRgn.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
    _user32.SetWindowRgn.restype = ctypes.c_int
    _user32.UpdateWindow.argtypes = [wintypes.HWND]
    _user32.UpdateWindow.restype = wintypes.BOOL
    _user32.GetMessageW.argtypes = [ctypes.POINTER(_Msg), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    _user32.GetMessageW.restype = ctypes.c_int
    _user32.TranslateMessage.argtypes = [ctypes.POINTER(_Msg)]
    _user32.TranslateMessage.restype = wintypes.BOOL
    _user32.DispatchMessageW.argtypes = [ctypes.POINTER(_Msg)]
    _user32.DispatchMessageW.restype = _LRESULT
    _user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.POINTER(_Rect), wintypes.BOOL]
    _user32.InvalidateRect.restype = wintypes.BOOL
    _user32.ReleaseCapture.restype = wintypes.BOOL
    _user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
    _user32.SendMessageW.restype = _LRESULT
    _user32.DestroyWindow.argtypes = [wintypes.HWND]
    _user32.DestroyWindow.restype = wintypes.BOOL
    _user32.PostQuitMessage.argtypes = [ctypes.c_int]
    _user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
    _user32.DefWindowProcW.restype = _LRESULT
    _user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(_PaintStruct)]
    _user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(_PaintStruct)]
    _user32.EndPaint.restype = wintypes.BOOL
    _user32.FillRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Rect), ctypes.c_void_p]
    _user32.FillRect.restype = ctypes.c_int
    _user32.DrawTextW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(_Rect), wintypes.UINT]
    _user32.DrawTextW.restype = ctypes.c_int
    _user32.LoadImageW.restype = ctypes.c_void_p
    _user32.LoadImageW.argtypes = [
        ctypes.c_void_p, wintypes.LPCWSTR, wintypes.UINT,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    _user32.DrawIconEx.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p, wintypes.UINT,
    ]
    _user32.DrawIconEx.restype = wintypes.BOOL
    _user32.DestroyIcon.argtypes = [ctypes.c_void_p]
    _user32.DestroyIcon.restype = wintypes.BOOL
    _user32.CreatePopupMenu.argtypes = []
    _user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    _user32.AppendMenuW.restype = wintypes.BOOL
    _user32.GetCursorPos.argtypes = [ctypes.POINTER(_Point)]
    _user32.GetCursorPos.restype = wintypes.BOOL
    _user32.TrackPopupMenu.argtypes = [
        wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, wintypes.HWND, ctypes.POINTER(_Rect),
    ]
    _user32.DestroyMenu.argtypes = [wintypes.HMENU]
    _user32.DestroyMenu.restype = wintypes.BOOL
    _gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
    _gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    _gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
    _gdi32.Ellipse.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    _gdi32.Ellipse.restype = wintypes.BOOL
    _gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    _gdi32.DeleteObject.restype = wintypes.BOOL
    _gdi32.SetBkMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _gdi32.SetTextColor.argtypes = [ctypes.c_void_p, wintypes.COLORREF]
    _gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _gdi32.SelectObject.restype = ctypes.c_void_p
    _gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    _gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    _gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    _gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    _gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    _gdi32.BitBlt.restype = wintypes.BOOL
    _gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]


class FloatingStatus:
    """A compact icon-only status button with click and right-click actions."""

    WIDTH = 68
    HEIGHT = 68
    _WM_UPDATE = 0x8001
    _WM_PAINT = 0x000F
    _WM_CLOSE = 0x0010
    _WM_DESTROY = 0x0002
    _WM_SETCURSOR = 0x0020
    _WM_LBUTTONUP = 0x0202
    _WM_RBUTTONUP = 0x0205
    _WM_NCLBUTTONDOWN = 0x00A1
    _HTCAPTION = 2
    _SW_HIDE = 0
    _SW_SHOWNOACTIVATE = 4
    _WS_EX_TOOLWINDOW = 0x00000080
    _WS_EX_TOPMOST = 0x00000008
    _WS_EX_NOACTIVATE = 0x08000000
    _WS_POPUP = 0x80000000
    _MF_STRING = 0x00000000
    _MF_GRAYED = 0x00000001
    _MF_SEPARATOR = 0x00000800
    _TPM_RETURNCMD = 0x0100
    _SWP_NOSIZE = 0x0001
    _SWP_NOMOVE = 0x0002
    _SWP_NOACTIVATE = 0x0010
    _HWND_TOPMOST = -1
    _IMAGE_ICON = 1
    _LR_LOADFROMFILE = 0x00000010
    _DI_NORMAL = 0x0003

    _ID_SHOW = 4101
    _ID_START = 4102
    _ID_STOP = 4103
    _ID_HIDE = 4104
    _ID_EXIT = 4105

    def __init__(
        self,
        *,
        is_running: Callable[[], bool],
        on_show: Callback,
        on_start: Callback,
        on_stop: Callback,
        on_exit: Callback,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._is_running = is_running
        self._on_show = on_show
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_exit = on_exit
        self._on_error = on_error
        self._running = False
        self._state_lock = threading.Lock()
        self._hwnd = None
        self._thread: Optional[threading.Thread] = None
        self._stop_requested = False
        self._wndproc = None
        self._logo_hicon = None
        self._logo_bitmap = None
        self._icon_running = False

    def start(self) -> None:
        if os.name != "nt":
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_requested = False
        self._thread = threading.Thread(target=self._run, name="lanhu-floating-status", daemon=True)
        self._thread.start()

    def update(self, running: bool) -> None:
        with self._state_lock:
            self._running = bool(running)
        hwnd = self._hwnd
        if hwnd is not None and os.name == "nt":
            try:
                _user32.PostMessageW(hwnd, self._WM_UPDATE, 0, 0)
            except Exception:
                pass

    def show(self) -> None:
        if self._hwnd is not None and os.name == "nt":
            _user32.ShowWindow(self._hwnd, self._SW_SHOWNOACTIVATE)
            _user32.SetWindowPos(self._hwnd, self._HWND_TOPMOST, 0, 0, 0, 0,
                                 self._SWP_NOMOVE | self._SWP_NOSIZE | self._SWP_NOACTIVATE)

    def hide(self) -> None:
        if self._hwnd is not None and os.name == "nt":
            _user32.ShowWindow(self._hwnd, self._SW_HIDE)

    def stop(self, *, wait: bool = True, timeout: float = 1.5) -> None:
        """Close the native window and wait briefly for its message loop."""
        self._stop_requested = True
        hwnd = self._hwnd
        if hwnd is not None and os.name == "nt":
            try:
                _user32.PostMessageW(hwnd, self._WM_CLOSE, 0, 0)
            except Exception:
                pass
        thread = self._thread
        if wait and thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, timeout))
        if thread is not None and not thread.is_alive():
            self._thread = None

    def _run(self) -> None:
        try:
            self._wndproc = _WNDPROC(self._window_proc)
            instance = _kernel32.GetModuleHandleW(None)
            class_name = f"LanhuMCPFloatingStatus_{id(self)}"
            wnd_class = _WndClass()
            wnd_class.lpfnWndProc = self._wndproc
            wnd_class.hInstance = instance
            # Use the normal arrow explicitly so the floating control never
            # inherits a busy/loading cursor from the main window.
            wnd_class.hCursor = _user32.LoadCursorW(None, 32512)  # IDC_ARROW
            wnd_class.lpszClassName = class_name
            _user32.RegisterClassW(ctypes.byref(wnd_class))

            screen_w = _user32.GetSystemMetrics(0)
            screen_h = _user32.GetSystemMetrics(1)
            x = max(0, screen_w - self.WIDTH - 24)
            y = max(0, screen_h - self.HEIGHT - 80)
            hwnd = _user32.CreateWindowExW(
                self._WS_EX_TOOLWINDOW | self._WS_EX_TOPMOST | self._WS_EX_NOACTIVATE,
                class_name,
                "Lanhu MCP",
                self._WS_POPUP,
                x, y, self.WIDTH, self.HEIGHT,
                None, None, instance, None,
            )
            if not hwnd:
                self._report_error("桌面悬浮框创建失败")
                return
            self._hwnd = hwnd
            region = _gdi32.CreateRoundRectRgn(0, 0, self.WIDTH + 1, self.HEIGHT + 1, 24, 24)
            if region:
                # SetWindowRgn takes ownership of the region handle.
                _user32.SetWindowRgn(hwnd, region, True)
            self._logo_hicon = self._load_logo_icon()
            _user32.ShowWindow(hwnd, self._SW_SHOWNOACTIVATE)
            _user32.UpdateWindow(hwnd)

            if self._stop_requested:
                _user32.DestroyWindow(hwnd)
                return

            msg = _Msg()
            while not self._stop_requested and _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                _user32.TranslateMessage(ctypes.byref(msg))
                _user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as error:  # noqa: BLE001 - optional visual affordance
            self._report_error(f"桌面悬浮框启动失败: {error}")
        finally:
            if self._logo_hicon is not None:
                try:
                    _user32.DestroyIcon(self._logo_hicon)
                except Exception:
                    pass
                self._logo_hicon = None
            if self._logo_bitmap is not None:
                try:
                    _gdi32.DeleteObject(self._logo_bitmap)
                except Exception:
                    pass
                self._logo_bitmap = None
            self._hwnd = None

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == self._WM_PAINT:
            self._paint(hwnd)
            return 0
        if message == self._WM_UPDATE:
            with self._state_lock:
                running = self._running
            if running != self._icon_running:
                if self._logo_hicon is not None:
                    _user32.DestroyIcon(self._logo_hicon)
                self._logo_hicon = self._load_logo_icon()
            _user32.InvalidateRect(hwnd, None, True)
            return 0
        if message == self._WM_SETCURSOR:
            cursor = _user32.LoadCursorW(None, 32512)  # IDC_ARROW
            if cursor:
                _user32.SetCursor(cursor)
            return 1
        if message == self._WM_LBUTTONUP:
            try:
                self._on_show()
            except Exception as error:  # noqa: BLE001
                self._report_error(f"打开主窗口失败: {error}")
            return 0
        if message == self._WM_RBUTTONUP:
            self._show_menu(hwnd)
            return 0
        if message == self._WM_CLOSE:
            _user32.DestroyWindow(hwnd)
            return 0
        if message == self._WM_DESTROY:
            _user32.PostQuitMessage(0)
            return 0
        return _user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def _paint(self, hwnd) -> None:
        paint = _PaintStruct()
        hdc = _user32.BeginPaint(hwnd, ctypes.byref(paint))
        try:
            rect = _Rect(0, 0, self.WIDTH, self.HEIGHT)
            brush = _gdi32.CreateSolidBrush(self._color(16, 24, 40))
            _user32.FillRect(hdc, ctypes.byref(rect), brush)
            _gdi32.DeleteObject(brush)
            if self._logo_hicon is not None:
                # Draw the logo at native 48px size.  The old 64x60 ICO was
                # stretched by GDI and made the white nodes visibly jagged.
                _user32.DrawIconEx(hdc, 10, 10, self._logo_hicon, 48, 48, 0, None, self._DI_NORMAL)
        finally:
            _user32.EndPaint(hwnd, ctypes.byref(paint))

    def _show_menu(self, hwnd) -> None:
        menu = _user32.CreatePopupMenu()
        if not menu:
            return
        try:
            running = self._safe_running()
            self._append_menu(menu, self._ID_SHOW, "显示主窗口")
            self._append_menu(menu, self._ID_START, "启动 MCP 服务", disabled=running)
            self._append_menu(menu, self._ID_STOP, "停止 MCP 服务", disabled=not running)
            _user32.AppendMenuW(menu, self._MF_SEPARATOR, 0, None)
            self._append_menu(menu, self._ID_HIDE, "隐藏悬浮框")
            self._append_menu(menu, self._ID_EXIT, "退出 Lanhu MCP")
            point = _Point()
            _user32.GetCursorPos(ctypes.byref(point))
            command = _user32.TrackPopupMenu(
                menu, self._TPM_RETURNCMD, point.x, point.y, 0, hwnd, None
            )
            callbacks = {
                self._ID_SHOW: self._on_show,
                self._ID_START: self._on_start,
                self._ID_STOP: self._on_stop,
                self._ID_HIDE: self.hide,
                self._ID_EXIT: self._on_exit,
            }
            callback = callbacks.get(command)
            if callback is not None:
                try:
                    callback()
                except Exception as error:  # noqa: BLE001
                    self._report_error(f"悬浮框操作失败: {error}")
        finally:
            _user32.DestroyMenu(menu)

    def _append_menu(self, menu, command: int, label: str, disabled: bool = False) -> None:
        flags = self._MF_STRING | (self._MF_GRAYED if disabled else 0)
        _user32.AppendMenuW(menu, flags, command, label)

    def _load_logo_icon(self):
        with self._state_lock:
            running = self._running
        self._icon_running = running
        filename = "lanhu_mcp_status_running.ico" if running else "lanhu_mcp_status_idle.ico"
        path = _asset_path(filename)
        if not path.exists():
            path = logo_ico_path()
        if not path.exists():
            return None
        try:
            return _user32.LoadImageW(
                None,
                str(path),
                FloatingStatus._IMAGE_ICON,
                # Request the exact native frame from the multi-size ICO.
                # LR_DEFAULTSIZE made Windows select a small frame, which
                # was then enlarged by DrawIconEx and looked jagged.
                48,
                48,
                FloatingStatus._LR_LOADFROMFILE,
            )
        except Exception:
            return None

    def _safe_running(self) -> bool:
        try:
            return bool(self._is_running())
        except Exception:
            return False

    @staticmethod
    def _color(red: int, green: int, blue: int) -> int:
        return red | (green << 8) | (blue << 16)

    def _report_error(self, message: str) -> None:
        if self._on_error is not None:
            try:
                self._on_error(message)
            except Exception:
                pass


__all__ = ["FloatingStatus"]
