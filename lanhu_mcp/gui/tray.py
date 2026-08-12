"""Lazy Windows/system-tray integration for the desktop shell.

The tray dependency is imported only when the GUI starts.  Server and login
branches therefore do not pay the import or image allocation cost.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from .branding import logo_path


Callback = Callable[[], None]


class TrayController:
    """Own a pystray icon on a daemon thread and expose small menu actions."""

    def __init__(
        self,
        *,
        is_running: Callable[[], bool],
        on_show: Callback,
        on_hide: Callback,
        on_start: Callback,
        on_stop: Callback,
        on_floating: Callback,
        on_exit: Callback,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._is_running = is_running
        self._on_show = on_show
        self._on_hide = on_hide
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_floating = on_floating
        self._on_exit = on_exit
        self._on_error = on_error
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._stopping = False

    @property
    def available(self) -> bool:
        with self._lock:
            return self._icon is not None

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stopping = False
            self._thread = threading.Thread(target=self._run, name="lanhu-tray", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        try:
            import pystray
            from PIL import Image, ImageDraw

            try:
                icon_image = Image.open(logo_path()).convert("RGBA")
                icon_image = icon_image.resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                icon_image = Image.new("RGBA", (64, 64), (37, 99, 235, 255))
                draw = ImageDraw.Draw(icon_image)
                draw.line((32, 15, 20, 32, 32, 49, 44, 32, 32, 15), fill="white", width=5, joint="curve")
                for x, y in ((20, 32), (32, 15), (32, 49), (44, 32)):
                    draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill="white")

            icon = pystray.Icon(
                "LanhuMCP",
                icon_image,
                "Lanhu MCP",
                menu=self._build_menu(pystray),
            )
            with self._lock:
                self._icon = icon
                stopping = self._stopping
            if stopping:
                return
            icon.run()
        except Exception as error:  # noqa: BLE001 - tray is an optional shell feature
            self._report_error(f"系统托盘启动失败: {error}")
        finally:
            with self._lock:
                self._icon = None

    def _build_menu(self, pystray):
        running = self._safe_running()

        def action(callback: Callback):
            def invoke(_icon, _item) -> None:
                try:
                    callback()
                except Exception as error:  # noqa: BLE001
                    self._report_error(f"托盘操作失败: {error}")
            return invoke

        noop = lambda: None
        status = "● 服务运行中" if running else "○ 服务已停止"
        return pystray.Menu(
            pystray.MenuItem("Lanhu MCP", action(noop), enabled=False),
            pystray.MenuItem(status, action(noop), enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("窗口", pystray.Menu(
                pystray.MenuItem("打开控制台", action(self._on_show), default=True),
                pystray.MenuItem("隐藏窗口", action(self._on_hide)),
            )),
            pystray.MenuItem("服务控制", pystray.Menu(
                pystray.MenuItem("▶ 启动 MCP 服务", action(self._on_start), enabled=lambda _item: not running),
                pystray.MenuItem("■ 停止 MCP 服务", action(self._on_stop), enabled=lambda _item: running),
            )),
            pystray.MenuItem("显示悬浮状态", action(self._on_floating)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出应用", action(self._on_exit)),
        )

    def update(self) -> None:
        """Refresh menu state after a service transition."""
        with self._lock:
            icon = self._icon
        if icon is None:
            return
        try:
            import pystray
            icon.menu = self._build_menu(pystray)
            icon.title = "Lanhu MCP · 服务运行中" if self._safe_running() else "Lanhu MCP · 服务未启动"
            icon.update_menu()
        except Exception:
            pass

    def stop(self, *, wait: bool = True, timeout: float = 1.5) -> None:
        with self._lock:
            self._stopping = True
            icon = self._icon
            thread = self._thread
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
        if wait and thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, timeout))
        if thread is not None and not thread.is_alive():
            with self._lock:
                if self._thread is thread:
                    self._thread = None

    def _safe_running(self) -> bool:
        try:
            return bool(self._is_running())
        except Exception:
            return False

    def _report_error(self, message: str) -> None:
        if self._on_error is not None:
            try:
                self._on_error(message)
            except Exception:
                pass


__all__ = ["TrayController"]
