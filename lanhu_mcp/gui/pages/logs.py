"""Real-time terminal-style log viewer for the desktop shell."""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from typing import Callable, List, Optional

import flet as ft

from .. import theme
from ..components import (
    empty_state,
    gradient_card,
    primary_button,
    secondary_button,
    section_title,
    stat_chip,
    toast,
    page_banner,
)
from ..state import AppContext
from ...core.cleanup import clear_local_cache


LEVEL_STYLES = {
    "info": ("#0052D9", "#ECF2FE"),
    "warn": ("#ED7B2F", "#FEF3E8"),
    "error": ("#E34D59", "#FDECEE"),
    "ok": ("#00A870", "#E8F8F2"),
    "debug": ("#999999", "#F3F3F3"),
    "mcp": ("#7B61FF", "#F0ECFF"),
}

TERMINAL_COLORS = {
    "info": "#D7E3F4",
    "warn": "#FBBF72",
    "error": "#FB7185",
    "ok": "#86EFAC",
    "debug": "#8FA3BF",
    "mcp": "#C4B5FD",
}

MCP_PATTERNS = [
    re.compile(r"\[MCP\]", re.IGNORECASE),
    re.compile(r"\[TEST\]", re.IGNORECASE),
    re.compile(r"tools/call", re.IGNORECASE),
    re.compile(r"method.*call", re.IGNORECASE),
    re.compile(r"mcp.*method", re.IGNORECASE),
    re.compile(r"jsonrpc", re.IGNORECASE),
]


class LogsPage:
    """A bounded, persistent console that follows the newest line."""

    TERMINAL_HEIGHT = 540

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._terminal = ft.ListView(
            expand=True,
            spacing=0,
            padding=0,
            auto_scroll=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        self._search_field = ft.TextField(
            label="搜索日志关键词",
            hint_text="例如：tools/call、ERROR、lanhu_get_designs",
            dense=True,
            expand=True,
            prefix_icon=ft.Icons.SEARCH,
            on_change=lambda _event: self._apply_filter(do_update=True),
        )
        self._filter_level = "all"
        self._show_mcp_only = False
        self._time_range = "all"
        self._log_unsub: Optional[Callable] = None
        self._mounted = False
        self._refresh_lock = threading.Lock()
        self._refresh_pending = False
        self._stat_bar = ft.Row(spacing=theme.space("3"), wrap=True)
        self._count_text = ft.Text("", size=theme.font_size("xs"))
        self._all_lines_cache: List[str] = []
        self._cleanup_dialog: Optional[ft.AlertDialog] = None

    # ── filters ───────────────────────────────────────────────────
    def _level_chips(self) -> ft.Control:
        p = self.ctx.palette
        kinds = [
            ("all", "全部"),
            ("mcp", "MCP 调用"),
            ("info", "信息"),
            ("warn", "警告"),
            ("error", "错误"),
            ("ok", "成功"),
        ]
        chips = []
        for kind, label in kinds:
            active = (kind == "mcp" and self._show_mcp_only) or (
                kind == self._filter_level and not self._show_mcp_only
            )
            fg, bg = LEVEL_STYLES.get(kind, (p.text_secondary, p.surface))
            chips.append(
                ft.Container(
                    content=ft.Text(label, size=theme.font_size("sm"), color="#FFFFFF" if active else fg),
                    bgcolor=fg if active else bg,
                    border_radius=theme.radius("full"),
                    padding=ft.padding.symmetric(horizontal=14, vertical=6),
                    on_click=lambda _event, selected=kind: self._set_level(selected),
                    ink=True,
                    animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                )
            )
        return ft.Row(chips, spacing=theme.space("2"))

    def _set_level(self, level: str) -> None:
        if level == "mcp":
            self._show_mcp_only = not self._show_mcp_only
            self._filter_level = "all"
        else:
            self._show_mcp_only = False
            self._filter_level = level if self._filter_level != level else "all"
        self._apply_filter(do_update=True)

    def _time_chips(self) -> ft.Control:
        p = self.ctx.palette
        kinds = [("all", "全部时间"), ("1h", "最近 1 小时"), ("24h", "最近 24 小时"), ("7d", "最近 7 天")]
        chips = []
        for kind, label in kinds:
            active = self._time_range == kind
            chips.append(
                ft.Container(
                    content=ft.Text(
                        label,
                        size=theme.font_size("xs"),
                        color=p.text_on_primary if active else p.text_secondary,
                    ),
                    bgcolor=p.primary if active else p.surface,
                    border_radius=theme.radius("full"),
                    padding=ft.padding.symmetric(horizontal=12, vertical=4),
                    on_click=lambda _event, selected=kind: self._set_time_range(selected),
                    ink=True,
                    animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                )
            )
        return ft.Row(chips, spacing=theme.space("2"))

    def _set_time_range(self, value: str) -> None:
        self._time_range = value if self._time_range != value else "all"
        self._apply_filter(do_update=True)

    # ── classification and filtering ─────────────────────────────
    @staticmethod
    def _is_mcp_log(line: str) -> bool:
        return any(pattern.search(line) for pattern in MCP_PATTERNS)

    @classmethod
    def _classify(cls, line: str) -> str:
        if cls._is_mcp_log(line):
            return "mcp"
        if "[ERR]" in line or "[FAIL]" in line or "[ERROR]" in line:
            return "error"
        if "[WARN]" in line or "[WARNING]" in line:
            return "warn"
        if "[OK]" in line:
            return "ok"
        if "[DEBUG]" in line:
            return "debug"
        return "info"

    @staticmethod
    def _extract_timestamp(line: str) -> Optional[float]:
        full = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        if full:
            try:
                return datetime.strptime(full.group(1), "%Y-%m-%d %H:%M:%S").timestamp()
            except ValueError:
                pass
        short = re.search(r"(\d{2}:\d{2}:\d{2})", line)
        if short:
            try:
                now = datetime.now()
                return datetime.strptime(
                    f"{now:%Y-%m-%d} {short.group(1)}", "%Y-%m-%d %H:%M:%S"
                ).timestamp()
            except ValueError:
                pass
        return None

    def _filtered_lines(self) -> List[str]:
        lines = self.ctx.get_logs()
        self._all_lines_cache = list(lines)
        if self._time_range != "all":
            cutoff = {"1h": 3600, "24h": 86400, "7d": 604800}.get(self._time_range, 0)
            if cutoff:
                now = time.time()
                lines = [
                    line for line in lines
                    if not self._extract_timestamp(line)
                    or self._extract_timestamp(line) > now - cutoff
                ]

        if self._show_mcp_only:
            lines = [line for line in lines if self._is_mcp_log(line)]
        elif self._filter_level != "all":
            lines = [line for line in lines if self._classify(line) == self._filter_level]

        query = (self._search_field.value or "").strip().lower()
        if query:
            lines = [line for line in lines if query in line.lower()]
        return lines

    def _render_stat_bar(self, lines: list[str]) -> None:
        p = self.ctx.palette
        err_count = sum(1 for line in lines if self._classify(line) == "error")
        warn_count = sum(1 for line in lines if self._classify(line) == "warn")
        ok_count = sum(1 for line in lines if self._classify(line) == "ok")
        mcp_count = sum(1 for line in lines if self._is_mcp_log(line))
        self._stat_bar.controls = [
            stat_chip(p, "全部", str(len(lines)), icon=ft.Icons.ARTICLE, accent=p.primary),
            stat_chip(p, "MCP 调用", str(mcp_count), icon=ft.Icons.CALL_MADE, accent=p.accent),
            stat_chip(p, "错误", str(err_count), icon=ft.Icons.ERROR, accent=p.danger),
            stat_chip(p, "警告", str(warn_count), icon=ft.Icons.WARNING, accent=p.warning),
            stat_chip(p, "成功", str(ok_count), icon=ft.Icons.CHECK_CIRCLE, accent=p.success),
        ]

    def _render(self) -> None:
        lines = self._filtered_lines()
        p = self.ctx.palette
        self._count_text.value = f"显示 {len(lines)} 条 · 共保存 {len(self._all_lines_cache)} 条"
        self._count_text.color = p.text_muted
        self._render_stat_bar(self._all_lines_cache)

        if not lines:
            self._terminal.controls = [
                ft.Container(
                    content=ft.Text(
                        "$ 等待 MCP 服务输出…",
                        color="#86EFAC",
                        size=theme.font_size("sm"),
                        font_family=theme.FONT_MONO,
                        selectable=True,
                    ),
                    padding=ft.padding.symmetric(horizontal=14, vertical=12),
                )
            ]
            return

        spans = []
        for index, line in enumerate(lines):
            suffix = "\n" if index < len(lines) - 1 else ""
            color = TERMINAL_COLORS.get(self._classify(line), TERMINAL_COLORS["info"])
            spans.append(ft.TextSpan(line + suffix, style=ft.TextStyle(color=color)))
        console_text = ft.Text(
            spans=spans,
            size=theme.font_size("sm"),
            font_family=theme.FONT_MONO,
            selectable=True,
            expand=True,
        )
        self._terminal.controls = [
            ft.Container(
                content=console_text,
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                alignment=ft.alignment.top_left,
            )
        ]

    # ── live updates ──────────────────────────────────────────────
    def _schedule_refresh(self, _line: str = "") -> None:
        with self._refresh_lock:
            if not self._mounted or self._refresh_pending:
                return
            self._refresh_pending = True
        try:
            self.ctx.page.run_thread(self._flush_scheduled_refresh)
        except Exception:
            self._flush_scheduled_refresh()

    def _flush_scheduled_refresh(self) -> None:
        with self._refresh_lock:
            self._refresh_pending = False
        if self._mounted:
            self.refresh()

    def _scroll_to_bottom(self) -> None:
        try:
            self._terminal.auto_scroll = True
            self._terminal.scroll_to(offset=-1, duration=0)
        except Exception:
            pass

    def refresh(self) -> None:
        self._render()
        try:
            self.ctx.page.update()
            # Replacing the single console text control does not always trigger
            # Flet's auto-scroll by itself, so explicitly follow the tail.
            self._scroll_to_bottom()
        except Exception:
            pass

    def _on_mount(self) -> None:
        self._mounted = True
        if self._log_unsub is None:
            self._log_unsub = self.ctx.subscribe_logs(self._schedule_refresh)
        self.refresh()

    def _on_unmount(self) -> None:
        self._mounted = False
        with self._refresh_lock:
            self._refresh_pending = False
        if self._log_unsub is not None:
            try:
                self._log_unsub()
            except Exception:
                pass
            self._log_unsub = None

    # ── actions ───────────────────────────────────────────────────
    def _clear(self) -> None:
        self.ctx.clear_logs()
        self.refresh()
        toast(self.ctx.page, "日志已清空", "ok", self.ctx.palette)

    def _clear_cache(self) -> None:
        """Ask before removing disposable logs and local behavior state."""
        if self._cleanup_dialog is not None:
            return
        p = self.ctx.palette

        def close_dialog() -> None:
            self._cleanup_dialog = None
            try:
                self.ctx.page.close(dialog)
            except Exception:
                dialog.open = False

        def confirm(_event) -> None:
            close_dialog()
            summary = clear_local_cache(self.ctx)
            self._filter_level = "all"
            self._show_mcp_only = False
            self._time_range = "all"
            self._search_field.value = ""
            self.refresh()
            # AppShell reloads its in-memory close preference on this signal,
            # so the next top-right close asks again after cleanup.
            self.ctx.notify_state_change("cache_cleared")
            removed = (
                f"日志 {summary['logs']} 条、最近项目 {summary['recent_projects']} 条、"
                f"头像缓存 {summary['avatars']} 个"
            )
            if summary["close_behavior"]:
                removed += "，关闭行为已重置"
            toast(self.ctx.page, f"已清理 {removed}", "ok", p)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("清理本地缓存与行为", color=p.text_primary),
            content=ft.Container(
                width=520,
                content=ft.Column([
                    ft.Text(
                        "将清理持久化日志、最近项目记录、头像缓存和窗口关闭行为。",
                        color=p.text_primary,
                    ),
                    ft.Text(
                        "不会删除账号 Cookie、账号资料、项目配置或 AI 工具配置。清理后下次点击右上角关闭按钮会重新询问行为。",
                        size=theme.font_size("sm"),
                        color=p.text_muted,
                    ),
                ], spacing=theme.space("2"), tight=True),
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _event: close_dialog()),
                ft.FilledButton(
                    "确认清理",
                    icon=ft.Icons.CLEANING_SERVICES_OUTLINED,
                    on_click=confirm,
                ),
            ],
        )
        self._cleanup_dialog = dialog
        try:
            self.ctx.page.open(dialog)
        except Exception:
            self._cleanup_dialog = None

    def _copy_all(self) -> None:
        lines = self.ctx.get_logs()
        try:
            self.ctx.page.set_clipboard("\n".join(lines))
            toast(self.ctx.page, f"已复制 {len(lines)} 条日志", "ok", self.ctx.palette)
        except Exception:
            toast(self.ctx.page, "复制日志失败", "error", self.ctx.palette)

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render()

        toolbar = ft.Container(
            content=ft.Column([
                ft.Row([
                    self._level_chips(),
                    ft.Container(expand=True),
                    self._count_text,
                ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    self._time_chips(),
                    ft.Container(width=theme.space("2")),
                    ft.Container(content=self._search_field, expand=True),
                ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=theme.space("3")),
            padding=theme.space("4"),
            bgcolor=p.card,
            border_radius=theme.radius("lg"),
            border=ft.border.all(1, p.border_light),
        )

        terminal_header = ft.Container(
            content=ft.Row([
                ft.Container(width=8, height=8, bgcolor="#22C55E", border_radius=theme.radius("full")),
                ft.Text("MCP SERVICE OUTPUT", size=theme.font_size("xs"), color="#A5B4FC",
                        font_family=theme.FONT_MONO, weight=theme.WEIGHT_BOLD),
                ft.Container(expand=True),
                ft.Text("LIVE · FOLLOW TAIL", size=theme.font_size("xs"), color="#86EFAC",
                        font_family=theme.FONT_MONO),
            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=theme.space("3"), right=theme.space("3"), top=theme.space("2"), bottom=theme.space("2")),
        )
        log_viewer = ft.Container(
            content=ft.Column([
                terminal_header,
                ft.Divider(height=1, color="#253550"),
                self._terminal,
            ], spacing=0, expand=True),
            height=self.TERMINAL_HEIGHT,
            border_radius=theme.radius("lg"),
            border=ft.border.all(1, "#253550"),
            padding=theme.space("2"),
            bgcolor="#0B1020",
        )
        guide = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.TIPS_AND_UPDATES_OUTLINED, size=18, color=p.primary),
                ft.Text(
                    "服务端会实时记录 AI 的 tools/call 请求、耗时和结果；窗口自动跟随最新输出。文本可选择，支持 Ctrl+C 或复制全部。",
                    size=theme.font_size("sm"), color=p.text_secondary, expand=True,
                ),
            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=p.primary_light,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
        )
        header = ft.Column([
            page_banner(p, "日志", "命令行输出 · AI MCP 调用 · 持久化 · 自动跟随底部", "logs"),
            ft.Container(
                content=ft.Row([
                    ft.Container(expand=True),
                    secondary_button("复制全部", lambda _event: self._copy_all(), icon=ft.Icons.CONTENT_COPY),
                    primary_button("清空日志", lambda _event: self._clear(), icon=ft.Icons.DELETE_OUTLINE),
                    secondary_button("清理缓存与行为", lambda _event: self._clear_cache(), icon=ft.Icons.CLEANING_SERVICES_OUTLINED),
                ], spacing=theme.space("2"), wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.only(left=theme.space("6"), right=theme.space("6")),
                bgcolor=p.card,
            ),
        ], spacing=theme.space("3"), tight=True)
        body = ft.Column([
            gradient_card(p, self._stat_bar, padding=theme.space("4")),
            guide,
            toolbar,
            log_viewer,
        ], spacing=theme.space("3"),
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        body_surface = ft.Container(
            content=body,
            padding=ft.padding.only(left=theme.space("6"), top=theme.space("1"), right=theme.space("6"), bottom=theme.space("6")),
            bgcolor=p.card,
        )
        # Keep exactly one vertical scroll owner for the page.  A scrollable
        # Column nested in the animated shell can receive an unconstrained
        # height and leave the content below a large neutral canvas.  The
        # page ListView owns vertical scrolling; all direct children are
        # content-sized and the terminal keeps its own fixed-height viewport.
        scroll_view = ft.ListView(
            controls=[
                header,
                body_surface,
            ],
            spacing=0,
            expand=True,
            padding=0,
        )
        scroll_view.bgcolor = p.card
        return scroll_view


__all__ = ["LogsPage"]
