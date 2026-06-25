"""Service page — start/stop the MCP server, show URL and grouped methods."""

from __future__ import annotations

from typing import List

import flet as ft

from .. import theme
from ..components import (
    section_title,
    card,
    StatusBadge,
    primary_button,
    danger_button,
    run_in_background,
    toast,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...services.tools_registry import discover_mcp_tools, group_mcp_tools


class ServicePage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._status_holder = ft.Row(spacing=theme.space("2"))
        self._action_holder = ft.Row(spacing=theme.space("3"))
        self._url_text = ft.Text(selectable=True, size=theme.font_size("sm"))
        self._busy = False

    # -- helpers --------------------------------------------------------
    def _mcp_url(self) -> str:
        try:
            return accounts_core.current_mcp_url(self.ctx.port)
        except Exception:
            return f"http://localhost:{self.ctx.port}/mcp"

    def _render_status(self) -> None:
        p = self.ctx.palette
        running = self.ctx.service.is_running()
        self._status_holder.controls = [
            StatusBadge(p, "运行中" if running else "已停止", "ok" if running else "idle"),
            StatusBadge(p, f"端口 {self.ctx.port}", "info"),
        ]
        self._url_text.value = self._mcp_url()
        self._url_text.color = p.text_primary
        if self._busy:
            self._action_holder.controls = [
                ft.Row([ft.ProgressRing(width=16, height=16), ft.Text("处理中…", color=p.text_secondary)],
                       spacing=theme.space("2"))
            ]
        elif running:
            self._action_holder.controls = [
                danger_button(p, "停止服务", lambda e: self._stop(), icon=ft.Icons.STOP),
            ]
        else:
            self._action_holder.controls = [
                primary_button("启动服务", lambda e: self._start(), icon=ft.Icons.PLAY_ARROW),
            ]

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._render_status()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # -- actions --------------------------------------------------------
    def _start(self) -> None:
        active = None
        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        if not active:
            toast(self.ctx.page, "请先在账号页登录蓝湖账号", "warn", self.ctx.palette)
            if self.ctx.navigate:
                self.ctx.navigate("accounts")
            return
        self._set_busy(True)

        def work():
            return self.ctx.service.start(
                port=self.ctx.port,
                on_output=lambda line: self.ctx.add_log(line),
                on_error=lambda line: self.ctx.add_log(f"[ERR] {line}"),
            )

        def done(result):
            self._busy = False
            ok, msg = result if isinstance(result, tuple) else (bool(result), "")
            self.ctx.add_log(msg or ("服务已启动" if ok else "服务启动失败"))
            toast(self.ctx.page, msg or ("服务已启动" if ok else "服务启动失败"),
                  "ok" if ok else "error", self.ctx.palette)
            self._render_status()

        run_in_background(self.ctx.page, work, on_done=done,
                          on_error=lambda exc: (setattr(self, "_busy", False), self._render_status()))

    def _stop(self) -> None:
        self._set_busy(True)

        def work():
            return self.ctx.service.stop()

        def done(result):
            self._busy = False
            ok, msg = result if isinstance(result, tuple) else (bool(result), "")
            self.ctx.add_log(msg or ("服务已停止" if ok else "停止失败"))
            toast(self.ctx.page, msg or ("服务已停止" if ok else "停止失败"),
                  "ok" if ok else "error", self.ctx.palette)
            self._render_status()

        run_in_background(self.ctx.page, work, on_done=done,
                          on_error=lambda exc: (setattr(self, "_busy", False), self._render_status()))

    def refresh(self) -> None:
        self._render_status()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # -- methods list ---------------------------------------------------
    def _build_methods(self) -> ft.Control:
        p = self.ctx.palette
        try:
            tools = discover_mcp_tools()
            groups = group_mcp_tools(tools)
        except Exception:
            tools, groups = [], {}
        group_controls: List[ft.Control] = []
        for group_name, items in groups.items():
            if not items:
                continue
            rows = [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=14, color=p.success),
                        ft.Text(name, size=theme.font_size("sm"), weight=theme.WEIGHT_MEDIUM,
                                color=p.text_primary),
                        ft.Text(summary, size=theme.font_size("xs"), color=p.text_muted, expand=True),
                    ],
                    spacing=theme.space("2"),
                )
                for name, summary in items
            ]
            group_controls.append(
                ft.ExpansionTile(
                    title=ft.Text(f"{group_name}  ({len(items)})",
                                  weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    controls=[ft.Container(ft.Column(rows, spacing=theme.space("2")),
                                           padding=ft.padding.only(left=12, bottom=8))],
                    initially_expanded=True,
                )
            )
        header = ft.Text(f"支持的 MCP 方法（共 {len(tools)} 个）",
                         size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary)
        return card(p, ft.Column([header] + group_controls, spacing=theme.space("2")))

    # -- view -----------------------------------------------------------
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render_status()
        control_card = card(
            p,
            ft.Column(
                [
                    ft.Row([ft.Text("MCP 服务", size=theme.font_size("lg"),
                                    weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                            ft.Container(expand=True), self._status_holder],
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Row([ft.Text("服务地址", size=theme.font_size("sm"), color=p.text_secondary, width=72),
                            self._url_text], spacing=theme.space("3")),
                    self._action_holder,
                ],
                spacing=theme.space("4"),
            ),
        )
        return ft.Column(
            [
                section_title(p, "服务", "启动 MCP 服务并查看可用方法"),
                control_card,
                self._build_methods(),
            ],
            spacing=theme.space("6"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )


__all__ = ["ServicePage"]
