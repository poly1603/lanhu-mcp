"""Logs page — live output buffer with simple text filter."""

from __future__ import annotations

import flet as ft

from .. import theme
from ..components import section_title, secondary_button
from ..state import AppContext


class LogsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._filter = ""
        self._list = ft.ListView(expand=True, spacing=2, auto_scroll=True, padding=12)
        self._unsubscribe = None

    def _matches(self, line: str) -> bool:
        return self._filter.lower() in line.lower() if self._filter else True

    def _line_control(self, line: str) -> ft.Control:
        return ft.Text(
            line,
            size=theme.font_size("sm"),
            font_family=theme.FONT_MONO,
            color=self.ctx.palette.log_text,
            selectable=True,
        )

    def _rebuild(self) -> None:
        self._list.controls = [
            self._line_control(l) for l in self.ctx.get_logs() if self._matches(l)
        ]

    def _on_new_log(self, line: str) -> None:
        if line == "":
            self._rebuild()
        elif self._matches(line):
            self._list.controls.append(self._line_control(line))
        try:
            self.ctx.page.update()
        except Exception:
            pass

    def _on_filter_change(self, e: ft.ControlEvent) -> None:
        self._filter = e.control.value or ""
        self._rebuild()
        self.ctx.page.update()

    def refresh(self) -> None:
        self._rebuild()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._rebuild()
        if self._unsubscribe is None:
            self._unsubscribe = self.ctx.subscribe_logs(self._on_new_log)

        filter_field = ft.TextField(
            hint_text="过滤日志…",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            on_change=self._on_filter_change,
            expand=True,
        )

        log_surface = ft.Container(
            content=self._list,
            bgcolor=p.log_bg,
            border_radius=theme.radius("lg"),
            expand=True,
        )

        return ft.Column(
            [
                ft.Row(
                    [
                        section_title(p, "日志", "服务与操作的实时输出"),
                        ft.Container(expand=True),
                        secondary_button("清空", lambda e: self._clear(), icon=ft.Icons.DELETE_OUTLINE),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                filter_field,
                log_surface,
            ],
            spacing=theme.space("4"),
            expand=True,
        )

    def _clear(self) -> None:
        self.ctx.clear_logs()
        self._rebuild()
        self.ctx.page.update()


__all__ = ["LogsPage"]
