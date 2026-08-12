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

import re
import threading
from collections import Counter
from datetime import datetime
from typing import Callable, List, Optional

import flet as ft

from . import theme
from .theme import Palette
from ..core.paths import LOG_FILE
from ..services.service_manager import ServiceManager
from ..services.ide_config import IDEManager

LOG_BUFFER_LIMIT = 2000
LOG_READ_TAIL_BYTES = 2 * 1024 * 1024
_LOG_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s")
_MCP_CALL_RE = re.compile(r"\[MCP\]\s+(?!GUI\s)tools/call\s+([A-Za-z0-9_]+)\s+arguments=")


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
        # Keep the first frame cheap.  The persisted tail can be large and is
        # not needed to mount the dashboard; logs are loaded lazily when the
        # log page is opened.
        self._logs: List[str] = []
        self._logs_loaded = False
        self._log_lock = threading.Lock()
        self._log_subscribers: List[Callable[[str], None]] = []
        self._state_subscribers: List[Callable[[str], None]] = []

        # Page navigation hook (set by the app shell).
        self.navigate: Optional[Callable[[str], None]] = None
        # Optional shell actions used by dashboard quick actions.
        self.start_service: Optional[Callable[[], None]] = None
        self.open_login: Optional[Callable[[], None]] = None

        # Active account id (set by accounts page refresh).
        self.active_account_id: str = ""

        # Optional hook used by the shell to keep chrome controls in sync
        # when a page changes the port programmatically.
        self.on_port_change: Optional[Callable[[int], None]] = None

    # -- theme ----------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.palette = theme.get_palette(mode)

    def set_port(self, port: int) -> None:
        """Update the service port and notify the shell when available."""
        self.port = int(port)
        callback = self.on_port_change
        if callback is not None:
            try:
                callback(self.port)
            except Exception:
                # A stale UI hook must never block a port change.
                pass

    # -- logging --------------------------------------------------------
    @staticmethod
    def _load_persisted_logs() -> List[str]:
        """Load only the recent tail so a large history cannot block startup."""
        try:
            with LOG_FILE.open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - LOG_READ_TAIL_BYTES))
                raw = handle.read().decode("utf-8", errors="replace")
            lines = raw.splitlines()
            if size > LOG_READ_TAIL_BYTES and lines:
                # The first decoded line may start halfway through a UTF-8
                # record; discard it rather than showing a damaged command.
                lines = lines[1:]
            return [line for line in lines if line][-LOG_BUFFER_LIMIT:]
        except (OSError, UnicodeError):
            return []

    @staticmethod
    def _timestamp_line(text: str) -> str:
        if _LOG_TIMESTAMP_RE.match(text):
            return text
        return f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {text}"

    @staticmethod
    def _persist_line(line: str) -> None:
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with LOG_FILE.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.write("\n")
        except OSError:
            # Logging must never make a UI action fail.  The in-memory stream
            # remains available even if the data directory is temporarily
            # unavailable or locked by another process.
            pass

    def add_log(self, line: str, *, persist: bool = True) -> None:
        text = str(line).rstrip("\n")
        if not text:
            return
        display_line = self._timestamp_line(text)
        with self._log_lock:
            self._logs_loaded = True
            self._logs.append(display_line)
            if len(self._logs) > LOG_BUFFER_LIMIT:
                del self._logs[: len(self._logs) - LOG_BUFFER_LIMIT]
            if persist:
                self._persist_line(display_line)
            subscribers = list(self._log_subscribers)
        for callback in subscribers:
            try:
                callback(display_line)
            except Exception:  # noqa: BLE001 - never let a subscriber break logging
                pass

    def get_logs(self) -> List[str]:
        if not self._logs_loaded:
            with self._log_lock:
                if not self._logs_loaded:
                    self._logs = self._load_persisted_logs()
                    self._logs_loaded = True
        with self._log_lock:
            return list(self._logs)

    def usage_stats(self) -> dict:
        """Summarize recent persisted console activity for the overview page."""
        logs = self.get_logs()
        methods: Counter[str] = Counter()
        daily: Counter[str] = Counter()
        project_events = 0
        account_events = 0
        error_count = 0
        recent_events: list[str] = []
        for line in logs:
            method_match = _MCP_CALL_RE.search(line)
            if method_match:
                method = method_match.group(1)
                methods[method] += 1
                if len(line) >= 10:
                    daily[line[:10]] += 1
                recent_events.append(line)
            if "[PROJECTS]" in line:
                project_events += 1
                recent_events.append(line)
            if "[ACCOUNT]" in line or "[LOGIN]" in line:
                account_events += 1
                recent_events.append(line)
            if "[ERR]" in line or "[ERROR]" in line or "-> ERROR" in line:
                error_count += 1
        return {
            "total_calls": sum(methods.values()),
            "method_counts": methods.most_common(8),
            "daily_calls": sorted(daily.items())[-7:],
            "project_events": project_events,
            "account_events": account_events,
            "error_count": error_count,
            "recent_events": recent_events[-8:][::-1],
        }

    def clear_logs(self) -> None:
        with self._log_lock:
            self._logs_loaded = True
            self._logs.clear()
            try:
                LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                # Truncate in place so an already-open FileHandler can
                # continue writing to the same path on Windows.
                with LOG_FILE.open("w", encoding="utf-8"):
                    pass
            except OSError:
                pass
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


    def notify_state_change(self, reason: str = "state") -> None:
        """Notify the shell that shared state changed."""
        with self._log_lock:
            subscribers = list(self._state_subscribers)
        for callback in subscribers:
            try:
                callback(str(reason or "state"))
            except Exception:
                pass

    def subscribe_state(self, callback: Callable[[str], None]) -> Callable[[], None]:
        with self._log_lock:
            self._state_subscribers.append(callback)

        def unsubscribe() -> None:
            with self._log_lock:
                if callback in self._state_subscribers:
                    self._state_subscribers.remove(callback)

        return unsubscribe
__all__ = ["AppContext", "LOG_BUFFER_LIMIT", "LOG_READ_TAIL_BYTES"]
