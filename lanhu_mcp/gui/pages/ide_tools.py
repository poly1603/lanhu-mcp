"""AI IDE tools page — detect installed IDEs and write the MCP config."""

from __future__ import annotations

from typing import List

import flet as ft

from .. import theme
from ..components import (
    section_title,
    card,
    StatusBadge,
    primary_button,
    secondary_button,
    empty_state,
    run_in_background,
    toast,
)
from ..state import AppContext


class IdeToolsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._grid = ft.Row(wrap=True, spacing=theme.space("4"), run_spacing=theme.space("4"))

    def _safe(self, fn, default):
        try:
            return fn()
        except Exception:
            return default

    def _tile(self, name: str, detail: dict) -> ft.Control:
        p = self.ctx.palette
        installed = bool(detail.get("installed"))
        config_dir = detail.get("config_dir") or detail.get("exe_path") or "未检测到安装路径"
        badge = StatusBadge(p, "已安装" if installed else "未检测到", "ok" if installed else "idle")
        action = (
            primary_button("配置", lambda e, n=name: self._configure(n), icon=ft.Icons.SETTINGS)
            if installed
            else ft.Container()
        )
        return ft.Container(
            width=320,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.TERMINAL,
                                    color=p.primary if installed else p.text_muted),
                            ft.Text(name, weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary, expand=True),
                            badge,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=theme.space("2"),
                    ),
                    ft.Text(str(config_dir), size=theme.font_size("xs"), color=p.text_muted,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([action]),
                ],
                spacing=theme.space("2"),
            ),
            bgcolor=p.surface,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("lg"),
            padding=theme.space("4"),
        )

    def _render(self) -> None:
        p = self.ctx.palette
        details = self._safe(self.ctx.ide.get_detection_details, {})
        if not details:
            self._grid.controls = [empty_state(p, "未检测到任何 AI IDE", icon=ft.Icons.DEVELOPER_MODE)]
            return
        installed = [(n, d) for n, d in details.items() if d.get("installed")]
        others = [(n, d) for n, d in details.items() if not d.get("installed")]
        ordered = installed + others
        self._grid.controls = [self._tile(n, d) for n, d in ordered]

    def refresh(self) -> None:
        self._render()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # -- actions --------------------------------------------------------
    def _configure(self, name: str) -> None:
        def work():
            return self.ctx.ide.configure(name, self.ctx.port)

        def done(result):
            ok, msg = result if isinstance(result, tuple) else (bool(result), "")
            self.ctx.add_log(msg or ("已配置" if ok else "配置失败"))
            toast(self.ctx.page, msg or ("已配置" if ok else "配置失败"),
                  "ok" if ok else "error", self.ctx.palette)

        run_in_background(self.ctx.page, work, on_done=done)

    def _configure_all(self) -> None:
        def work():
            return self.ctx.ide.configure_all(self.ctx.port)

        def done(results):
            results = results or []
            ok_count = sum(1 for _n, ok, _m in results if ok)
            for n, ok, m in results:
                self.ctx.add_log(f"[{'OK' if ok else 'FAIL'}] {n}: {m}")
            toast(self.ctx.page, f"已配置 {ok_count}/{len(results)} 个 IDE",
                  "ok" if ok_count else "warn", self.ctx.palette)
            self.refresh()

        run_in_background(self.ctx.page, work, on_done=done)

    # -- view -----------------------------------------------------------
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render()
        toolbar = card(
            p,
            ft.Row(
                [
                    ft.Text("将 Lanhu MCP 写入已安装的 AI 编程工具配置",
                            color=p.text_secondary, expand=True),
                    secondary_button("重新检测", lambda e: self.refresh(), icon=ft.Icons.REFRESH),
                    primary_button("全部配置", lambda e: self._configure_all(), icon=ft.Icons.DONE_ALL),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=theme.space("3"),
            ),
        )
        return ft.Column(
            [
                section_title(p, "AI 工具", "检测并配置 AI IDE 的 MCP 接入"),
                toolbar,
                self._grid,
            ],
            spacing=theme.space("6"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )


__all__ = ["IdeToolsPage"]
