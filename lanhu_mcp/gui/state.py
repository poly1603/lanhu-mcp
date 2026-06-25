"""Shared application context for the Flet GUI.

A single :class:`AppContext` instance is created in :mod:`lanhu_mcp.gui.app`
and passed to every page. It owns:

- the current theme palette + mode
- the MCP server port
- long-lived service handles (:class:`ServiceManager`, :class:`IDEManager`)
- an in-memory log buffer with subscriber callbacks

Pages read state from the context and call service methods through it; they
never instantiate services themselves.
"""

from __future__ import annotations

import threading
from typing import Callable, List, Optional

import flet as ft

from . import theme
from .theme import Palette
from ..services.service_manager import ServiceManager
from ..services.ide_config import IDEManager

LOG_BUFFER_LIMIT = 2000


class AppContext:
    def __init__(self, page: ft.Page, *, mode: str = "light", port: int = 8000) -> None:
        self.page = page
        self.mode = mode
        self.palette: Palette = theme.get_palette(mode)
        self.port = port

        # Long-lived service handles.
        self.service = ServiceManager()
        self.ide = IDEManager()

        # In-memory log buffer + subscribers.
        self._logs: List[str] = []
        self._log_lock = threading.Lock()
        self._log_subscribers: List[Callable[[str], None]] = []

        # Page navigation hook (set by the app shell).
        self.navigate: Optional[Callable[[str], None]] = None

    # -- theme ----------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.palette = theme.get_palette(mode)

    # -- logging --------------------------------------------------------
    def add_log(self, line: str) -> None:
        text = str(line).rstrip("\n")
        if not text:
            return
        with self._log_lock:
            self._logs.append(text)
            if len(self._logs) > LOG_BUFFER_LIMIT:
                del self._logs[: len(self._logs) - LOG_BUFFER_LIMIT]
            subscribers = list(self._log_subscribers)
        for callback in subscribers:
            try:
                callback(text)
            except Exception:  # noqa: BLE001 - never let a subscriber break logging
                pass

    def get_logs(self) -> List[str]:
        with self._log_lock:
            return list(self._logs)

    def clear_logs(self) -> None:
        with self._log_lock:
            self._logs.clear()
            subscribers = list(self._log_subscribers)
        for callback in subscribers:
            try:
                callback("")
            except Exception:  # noqa: BLE001
                pass

    def subscribe_logs(self, callback: Callable[[str], None]) -> Callable[[], None]:
        with self._log_lock:
            self._log_subscribers.append(callback)

        def unsubscribe() -> None:
            with self._log_lock:
                if callback in self._log_subscribers:
                    self._log_subscribers.remove(callback)

        return unsubscribe


__all__ = ["AppContext", "LOG_BUFFER_LIMIT"]
