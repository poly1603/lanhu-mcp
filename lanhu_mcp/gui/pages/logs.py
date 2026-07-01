"""Logs page (v2) — enriched with level filter chips, search highlight, export."""

from __future__ import annotations

import io
import re
import threading
from typing import List, Optional

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge, CountBadge, stat_chip,
    primary_button, secondary_button, ghost_icon_button, empty_state,
    toast,
)
from ..state import AppContext


LEVEL_STYLES = {
    "info": ("#0052D9", "#ECF2FE"),
    "warn": ("#ED7B2F", "#FEF3E8"),
    "error": ("#E34D59", "#FDECEE"),
    "ok": ("#00A870", "#E8F8F2"),
    "debug": ("#999999", "#F3F3F3"),
}


class LogsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._list = ft.ListView(expand=True, spacing=2, auto_scroll=True, padding=12)
        self._search_field = ft.TextField(
            label="搜索日志", dense=True, expand=True, prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self._apply_filter(do_update=True),
        )
        self._filter_level: str = "all"  # "all" | "info" | "warn" | "error" | "ok"
        self._log_unsub: Optional[Callable] = None
        self._stat_bar = ft.Row(spacing=theme.space("4"), wrap=True)
        self._all_lines_cache: List[str] = []

    # ── filter chips ──────────────────────────────────────────────
    def _level_chips(self) -> ft.Control:
        p = self.ctx.palette
        kinds = [
            ("all", "全部"),
            ("info", "信息"),
            ("warn", "警告"),
            ("error", "错误"),
            ("ok", "成功"),
        ]
        chips = []
        for k, label in kinds:
            active = self._filter_level == k
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
        self._filter_level = level if self._filter_level != level else "all"
        self._apply_filter(do_update=True)

    # ── stats ─────────────────────────────────────────────────────
    def _render_stat_bar(self) -> None:
        p = self.ctx.palette
        lines = self.ctx.get_logs()
        info_count = sum(1 for l in lines if "[INFO]" in l or "=== " in l and not "[ERR]" in l)
        warn_count = sum(1 for l in lines if "[WARN]" in l)
        err_count = sum(1 for l in lines if "[ERR]" in l or "[FAIL]" in l)
        ok_count = sum(1 for l in lines if "[OK]" in l)
        self._stat_bar.controls = [
            stat_chip(p, "全部", str(len(lines)), icon=ft.Icons.ARTICLE, accent=p.primary),
            stat_chip(p, "错误", str(err_count), icon=ft.Icons.ERROR, accent=p.danger),
            stat_chip(p, "警告", str(warn_count), icon=ft.Icons.WARNING, accent=p.warning),
            stat_chip(p, "成功", str(ok_count), icon=ft.Icons.CHECK_CIRCLE, accent=p.success),
            stat_chip(p, "信息", str(info_count), icon=ft.Icons.INFO, accent=p.accent),
        ]

    # ── render ────────────────────────────────────────────────────
    def _render(self) -> None:
        p = self.ctx.palette
        query = (self._search_field.value or "").strip().lower()
        lines = self.ctx.get_logs()
        self._all_lines_cache = list(lines)

        # Level filter
        if self._filter_level != "all":
            level_map = {
                "info": lambda x: "[INFO]" in x or ("=== " in x and "[ERR]" not in x),
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

        if not lines:
            self._list.controls = [
                empty_state(p, "没有匹配的日志项",
                            icon=ft.Icons.SEARCH_OFF if query else ft.Icons.ARTICLE_OUTLINED)
            ]
        else:
            items: List[ft.Control] = []
            for line in lines:
                level = "info"
                if "[ERR]" in line or "[FAIL]" in line:
                    level = "error"
                elif "[WARN]" in line:
                    level = "warn"
                elif "[OK]" in line:
                    level = "ok"
                elif "=== " in line:
                    level = "info"

                fg, _bg = LEVEL_STYLES.get(level, (p.text_secondary, p.surface))
                items.append(
                    ft.Row([
                        ft.Icon({
                            "error": ft.Icons.ERROR,
                            "warn": ft.Icons.WARNING,
                            "ok": ft.Icons.CHECK_CIRCLE,
                            "info": ft.Icons.INFO,
                        }.get(level, ft.Icons.FIBER_MANUAL_RECORD), size=12, color=fg),
                        ft.Text(line, selectable=True, size=theme.font_size("sm"),
                                color=p.log_text if hasattr(p, "log_text") else p.text_primary,
                                font_family=theme.FONT_MONO, expand=True),
                    ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.START)
                )
            self._list.controls = items

        self._render_stat_bar()

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
        """Called when page is first displayed; sub to log updates."""
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

        # 一行 toolbar：级别 chips + 搜索 + 按钮
        toolbar = ft.Container(
            content=ft.Row(
                [
                    self._level_chips(),
                    ft.Container(width=theme.space("3")),
                    ft.Container(
                        content=self._search_field,
                        expand=True,
                    ),
                    ft.Container(width=theme.space("2")),
                    ghost_icon_button(ft.Icons.DELETE_OUTLINE, lambda e: self._clear(), tooltip="清空"),
                    primary_button("导出", lambda e: self._export(), icon=ft.Icons.SAVE),
                ],
                spacing=theme.space("3"),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=theme.space("4"),
            bgcolor=p.card,
            border_radius=theme.radius("lg"),
            border=ft.border.all(1, p.border_light),
        )

        return ft.Column(
            [
                section_title(p, "日志", "实时输出 · 级别筛选 · 搜索"),
                gradient_card(p, self._stat_bar, padding=theme.space("4")),
                toolbar,
                ft.Container(
                    content=self._list,
                    expand=True,
                    border_radius=theme.radius("lg"),
                    border=ft.border.all(1, p.border_light),
                    padding=theme.space("2"),
                    bgcolor=p.surface,
                ),
            ],
            spacing=theme.space("4"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )


__all__ = ["LogsPage"]
