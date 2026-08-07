"""Logs page — full-featured log viewer with MCP method call tracking."""

from __future__ import annotations

import re
import time
import threading
from datetime import datetime
from typing import List, Optional, Callable

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge, CountBadge, stat_chip,
    primary_button, secondary_button, empty_state,
    toast,
)
from ..state import AppContext


LEVEL_STYLES = {
    "info": ("#0052D9", "#ECF2FE"),
    "warn": ("#ED7B2F", "#FEF3E8"),
    "error": ("#E34D59", "#FDECEE"),
    "ok": ("#00A870", "#E8F8F2"),
    "debug": ("#999999", "#F3F3F3"),
    "mcp": ("#7B61FF", "#F0ECFF"),
}

LEVEL_ICONS = {
    "error": ft.Icons.ERROR,
    "warn": ft.Icons.WARNING,
    "ok": ft.Icons.CHECK_CIRCLE,
    "info": ft.Icons.INFO,
    "debug": ft.Icons.FIBER_MANUAL_RECORD,
    "mcp": ft.Icons.CALL_MADE,
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
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._list = ft.ListView(expand=True, spacing=2, auto_scroll=True, padding=12)
        self._search_field = ft.TextField(
            label="搜索日志关键词", dense=True, expand=True, prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self._apply_filter(do_update=True),
        )
        self._filter_level: str = "all"
        self._log_unsub: Optional[Callable] = None
        self._stat_bar = ft.Row(spacing=theme.space("3"), wrap=True)
        self._all_lines_cache: List[str] = []
        self._expanded_index: Optional[int] = None
        self._time_range: str = "all"
        self._count_text = ft.Text("", size=theme.font_size("xs"))
        self._show_mcp_only: bool = False

    # ── filter chips ──────────────────────────────────────────────
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
        for k, label in kinds:
            active = (k == "mcp" and self._show_mcp_only) or (k == self._filter_level and not self._show_mcp_only)
            fg, bg = LEVEL_STYLES.get(k, (p.text_secondary, p.surface))
            chips.append(
                ft.Container(
                    content=ft.Text(label, size=theme.font_size("sm"),
                                    color="#FFFFFF" if active else fg),
                    bgcolor=fg if active else bg,
                    border_radius=theme.radius("full"),
                    padding=ft.padding.symmetric(horizontal=14, vertical=6),
                    on_click=lambda e, kind=k: self._set_level(kind),
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

    # ── time range chips ──────────────────────────────────────────
    def _time_chips(self) -> ft.Control:
        p = self.ctx.palette
        kinds = [
            ("all", "全部时间"),
            ("1h", "最近 1 小时"),
            ("24h", "最近 24 小时"),
            ("7d", "最近 7 天"),
        ]
        chips = []
        for k, label in kinds:
            active = self._time_range == k
            chips.append(
                ft.Container(
                    content=ft.Text(label, size=theme.font_size("xs"),
                                    color=p.text_on_primary if active else p.text_secondary),
                    bgcolor=p.primary if active else p.surface,
                    border_radius=theme.radius("full"),
                    padding=ft.padding.symmetric(horizontal=12, vertical=4),
                    on_click=lambda e, kind=k: self._set_time_range(kind),
                    ink=True,
                    animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                )
            )
        return ft.Row(chips, spacing=theme.space("2"))

    def _set_time_range(self, r: str) -> None:
        self._time_range = r if self._time_range != r else "all"
        self._apply_filter(do_update=True)

    # ── stats ─────────────────────────────────────────────────────
    def _render_stat_bar(self, lines: list) -> None:
        p = self.ctx.palette
        err_count = sum(1 for l in lines if "[ERR]" in l or "[FAIL]" in l)
        warn_count = sum(1 for l in lines if "[WARN]" in l)
        ok_count = sum(1 for l in lines if "[OK]" in l)
        mcp_count = sum(1 for l in lines if self._is_mcp_log(l))
        info_count = len(lines) - err_count - warn_count - ok_count - mcp_count
        self._stat_bar.controls = [
            stat_chip(p, "全部", str(len(lines)), icon=ft.Icons.ARTICLE, accent=p.primary),
            stat_chip(p, "MCP 调用", str(mcp_count), icon=ft.Icons.CALL_MADE, accent=p.accent),
            stat_chip(p, "错误", str(err_count), icon=ft.Icons.ERROR, accent=p.danger),
            stat_chip(p, "警告", str(warn_count), icon=ft.Icons.WARNING, accent=p.warning),
            stat_chip(p, "成功", str(ok_count), icon=ft.Icons.CHECK_CIRCLE, accent=p.success),
        ]

    # ── MCP log detection ─────────────────────────────────────────
    @staticmethod
    def _is_mcp_log(line: str) -> bool:
        return any(p.search(line) for p in MCP_PATTERNS)

    # ── classify a log line ───────────────────────────────────────
    @staticmethod
    def _classify(line: str) -> str:
        if any(p.search(line) for p in MCP_PATTERNS):
            return "mcp"
        if "[ERR]" in line or "[FAIL]" in line:
            return "error"
        if "[WARN]" in line:
            return "warn"
        if "[OK]" in line:
            return "ok"
        if "[DEBUG]" in line:
            return "debug"
        return "info"

    # ── highlight search matches ──────────────────────────────────
    def _highlight(self, line: str, query: str) -> ft.Control:
        p = self.ctx.palette
        if not query:
            return ft.Text(line, size=theme.font_size("sm"), font_family=theme.FONT_MONO,
                           color=p.text_primary, selectable=True, expand=True)
        parts = re.split(f"({re.escape(query)})", line, flags=re.IGNORECASE)
        spans = []
        for part in parts:
            if part.lower() == query.lower():
                spans.append(ft.TextSpan(part, bgcolor=p.warning_light, color=p.warning, weight=theme.WEIGHT_BOLD))
            else:
                spans.append(ft.TextSpan(part, style=ft.TextStyle(color=p.text_primary)))
        return ft.Text(spans=spans, size=theme.font_size("sm"), font_family=theme.FONT_MONO, selectable=True, expand=True)

    # ── render ────────────────────────────────────────────────────
    def _render(self) -> None:
        p = self.ctx.palette
        query = (self._search_field.value or "").strip().lower()
        lines = self.ctx.get_logs()
        self._all_lines_cache = list(lines)

        # Time range filter
        if self._time_range != "all":
            now = time.time()
            cutoff = {"1h": 3600, "24h": 86400, "7d": 604800}.get(self._time_range, 0)
            if cutoff:
                filtered = []
                for l in lines:
                    ts = self._extract_timestamp(l)
                    if ts and ts > now - cutoff:
                        filtered.append(l)
                    elif not ts:
                        filtered.append(l)
                lines = filtered

        # MCP only filter
        if self._show_mcp_only:
            lines = [l for l in lines if self._is_mcp_log(l)]
        elif self._filter_level != "all":
            level_map = {
                "info": lambda x: "[INFO]" in x or ("=== " in x and "[ERR]" not in x and not self._is_mcp_log(x)),
                "warn": lambda x: "[WARN]" in x,
                "error": lambda x: "[ERR]" in x or "[FAIL]" in x,
                "ok": lambda x: "[OK]" in x,
            }
            check = level_map.get(self._filter_level)
            if check:
                lines = [l for l in lines if check(l)]

        # Text search
        if query:
            lines = [l for l in lines if query in l.lower()]

        self._count_text.value = f"共 {len(lines)} 条"
        self._count_text.color = p.text_muted

        if not lines:
            self._list.controls = [
                empty_state(p, "没有匹配的日志项",
                            icon=ft.Icons.SEARCH_OFF if query else ft.Icons.ARTICLE_OUTLINED)
            ]
        else:
            items: List[ft.Control] = []
            for idx, line in enumerate(lines):
                level = self._classify(line)
                fg, bg = LEVEL_STYLES.get(level, (p.text_secondary, p.surface))
                icon = LEVEL_ICONS.get(level, ft.Icons.FIBER_MANUAL_RECORD)
                is_expanded = self._expanded_index == idx

                content_row = ft.Row([
                    ft.Icon(icon, size=14, color=fg),
                    ft.Container(content=self._highlight(line, query), expand=True),
                ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.START)

                detail_content = None
                if is_expanded:
                    meta_parts = []
                    tag_match = re.search(r"\[(ERR|FAIL|WARN|OK|INFO|DEBUG|MCP|TEST)\]", line)
                    if tag_match:
                        meta_parts.append(f"级别: {tag_match.group(1)}")
                    ts = self._extract_timestamp(line)
                    if ts:
                        meta_parts.append(f"时间: {datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')}")
                    meta_parts.append(f"长度: {len(line)} 字符")
                    meta_parts.append(f"序号: #{idx + 1}")
                    if level == "mcp":
                        meta_parts.append("类型: MCP 方法调用")

                    detail_content = ft.Container(
                        content=ft.Column([
                            ft.Divider(height=1, color=p.border_light),
                            ft.Text("  ".join(meta_parts), size=theme.font_size("xs"), color=p.text_muted, font_family=theme.FONT_MONO),
                        ], spacing=theme.space("1")),
                        padding=ft.padding.only(left=theme.space("4"), top=theme.space("1")),
                    )

                clickable = ft.Container(
                    content=ft.Column(
                        [content_row] + ([detail_content] if detail_content else []),
                        spacing=0, data=idx,
                    ),
                    bgcolor=bg if is_expanded or level == "mcp" else p.card,
                    border=ft.border.all(1, p.border_light),
                    border_radius=theme.radius("md"),
                    padding=theme.space("2"),
                    on_click=lambda e, i=idx: self._toggle_detail(i),
                    ink=True,
                    animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                )
                items.append(clickable)
            self._list.controls = items

        self._render_stat_bar(self._all_lines_cache)

    def _extract_timestamp(self, line: str) -> Optional[float]:
        m = re.search(r"(\d{2}:\d{2}:\d{2})", line)
        if m:
            try:
                now = datetime.now()
                parts = m.group(1).split(":")
                h, mi, s = int(parts[0]), int(parts[1]), int(parts[2])
                dt = now.replace(hour=h, minute=mi, second=s, microsecond=0)
                return dt.timestamp()
            except Exception:
                pass
        return None

    def _toggle_detail(self, idx: int) -> None:
        self._expanded_index = idx if self._expanded_index != idx else None
        self._apply_filter(do_update=True)

    def _apply_filter(self, do_update: bool = False) -> None:
        self._render()
        if do_update:
            try:
                self.ctx.page.update()
            except Exception:
                pass

    # ── lifecycle ─────────────────────────────────────────────────
    def refresh(self) -> None:
        self._render()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    def _on_mount(self) -> None:
        def on_log(line: str) -> None:
            self.refresh()
        if self._log_unsub is not None:
            try:
                self._log_unsub()
            except Exception:
                pass
        self._log_unsub = self.ctx.subscribe_logs(on_log)
        self.refresh()

    def _on_unmount(self) -> None:
        if self._log_unsub is not None:
            try:
                self._log_unsub()
            except Exception:
                pass
            self._log_unsub = None

    # ── actions ───────────────────────────────────────────────────
    def _clear(self) -> None:
        self.ctx.clear_logs()
        self._expanded_index = None
        self.refresh()

    def _export(self) -> None:
        p = self.ctx.palette
        lines = self.ctx.get_logs()
        text = "\n".join(lines)
        try:
            self.ctx.page.set_clipboard(text)
            toast(self.ctx.page, f"已复制 {len(lines)} 条日志到剪贴板", "ok", p)
        except Exception:
            toast(self.ctx.page, "复制失败", "error", p)

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render()

        toolbar_row1 = ft.Row([
            self._level_chips(),
            ft.Container(expand=True),
            self._count_text,
        ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        toolbar_row2 = ft.Row([
            self._time_chips(),
            ft.Container(width=theme.space("2")),
            ft.Container(content=self._search_field, expand=True),
        ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        toolbar = ft.Container(
            content=ft.Column([toolbar_row1, toolbar_row2], spacing=theme.space("3")),
            padding=theme.space("4"),
            bgcolor=p.card,
            border_radius=theme.radius("lg"),
            border=ft.border.all(1, p.border_light),
        )

        log_viewer = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=8, height=8, bgcolor="#22C55E", border_radius=theme.radius("full")),
                        ft.Text("MCP SERVICE OUTPUT", size=theme.font_size("xs"), color="#A5B4FC", font_family=theme.FONT_MONO, weight=theme.WEIGHT_BOLD),
                        ft.Container(expand=True),
                        ft.Text("live", size=theme.font_size("xs"), color="#86EFAC", font_family=theme.FONT_MONO),
                    ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.only(left=theme.space("3"), right=theme.space("3"), top=theme.space("2"), bottom=theme.space("2")),
                ),
                ft.Divider(height=1, color="#253550"),
                self._list,
            ], spacing=0, expand=True),
            expand=True,
            border_radius=theme.radius("lg"),
            border=ft.border.all(1, "#253550"),
            padding=theme.space("2"),
            bgcolor="#0B1020",
        )
        guide_card = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.TIPS_AND_UPDATES_OUTLINED, size=18, color=p.primary),
                ft.Text("点击日志行可展开查看元信息；可按 MCP 调用、错误、警告筛选，也可以一键复制全部日志用于排障。",
                        size=theme.font_size("sm"), color=p.text_secondary, expand=True),
            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=p.primary_light,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
        )

        header = ft.Container(
            content=ft.Row([
                section_title(p, "日志", "实时输出 · MCP 方法调用 · 分类筛选 · 搜索"),
                ft.Container(expand=True),
                secondary_button("清空", lambda e: self._clear(), icon=ft.Icons.DELETE_OUTLINE),
                primary_button("导出", lambda e: self._export(), icon=ft.Icons.SAVE),
            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=theme.space("6"), top=theme.space("5"), right=theme.space("6"), bottom=theme.space("3")),
        )

        body = ft.Column([
            gradient_card(p, self._stat_bar, padding=theme.space("4")),
            guide_card,
            toolbar,
            log_viewer,
        ], spacing=theme.space("3"))
        return ft.ListView(
            controls=[
                header,
                ft.Container(
                    content=body,
                    padding=ft.padding.only(left=theme.space("6"), top=theme.space("1"), right=theme.space("6"), bottom=theme.space("6")),
                ),
            ],
            spacing=0,
            expand=True,
        )


__all__ = ["LogsPage"]
