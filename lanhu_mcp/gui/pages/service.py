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
    secondary_button,
    danger_button,
    ghost_icon_button,
    run_in_background,
    toast,
    show_error,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...services.ide_config import mcp_config_snippets
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
                secondary_button("健康检查", lambda e: self._health_check(), icon=ft.Icons.MONITOR_HEART),
                secondary_button("复制接入配置", lambda e: self._show_config(), icon=ft.Icons.CONTENT_COPY),
            ]
        else:
            self._action_holder.controls = [
                primary_button("启动服务", lambda e: self._start(), icon=ft.Icons.PLAY_ARROW),
                secondary_button("复制接入配置", lambda e: self._show_config(), icon=ft.Icons.CONTENT_COPY),
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

        def err(exc):
            self._busy = False
            show_error(self.ctx.page, exc, "服务启动", self.ctx.palette, self.ctx.add_log)
            self._render_status()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

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

        def err(exc):
            self._busy = False
            show_error(self.ctx.page, exc, "服务停止", self.ctx.palette, self.ctx.add_log)
            self._render_status()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _health_check(self) -> None:
        url = self._mcp_url()
        self.ctx.add_log(f"健康检查: {url}")
        toast(self.ctx.page, "正在检查 MCP 服务…", "info", self.ctx.palette)

        def work():
            import httpx  # lazy: keep GUI cold-start light
            # MCP streamable-http 端点对裸 GET 通常返回 4xx/406，但能连通即视为存活。
            resp = httpx.get(url, timeout=5.0, headers={"Accept": "text/event-stream"})
            return resp.status_code

        def done(status):
            alive = isinstance(status, int) and status < 500
            msg = f"服务可达 (HTTP {status})" if alive else f"服务异常 (HTTP {status})"
            self.ctx.add_log(msg)
            toast(self.ctx.page, msg, "ok" if alive else "error", self.ctx.palette)

        def err(exc):
            show_error(self.ctx.page, exc, "健康检查", self.ctx.palette, self.ctx.add_log)

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _show_config(self) -> None:
        p = self.ctx.palette
        try:
            snippets = mcp_config_snippets(self.ctx.port)
        except Exception:
            snippets = []

        def copy(text: str) -> None:
            try:
                self.ctx.page.set_clipboard(text)
                toast(self.ctx.page, "配置已复制", "ok", p)
            except Exception as exc:
                show_error(self.ctx.page, exc, "复制配置", p, self.ctx.add_log)

        blocks: List[ft.Control] = []
        for label, text in snippets:
            blocks.append(
                ft.Column(
                    [
                        ft.Row([ft.Text(label, weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary,
                                        expand=True),
                                ghost_icon_button(ft.Icons.CONTENT_COPY,
                                                  lambda e, t=text: copy(t), tooltip="复制")],
                               vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Container(
                            content=ft.Text(text, selectable=True, size=theme.font_size("xs"),
                                            color=p.text_secondary, font_family="monospace"),
                            bgcolor=p.surface, border=ft.border.all(1, p.border_light),
                            border_radius=theme.radius("sm"), padding=theme.space("3"),
                        ),
                    ],
                    spacing=theme.space("2"),
                )
            )
        dlg = ft.AlertDialog(
            title=ft.Text("MCP 接入配置", color=p.text_primary),
            content=ft.Container(
                width=560,
                content=ft.Column(blocks, spacing=theme.space("4"), scroll=ft.ScrollMode.AUTO,
                                  tight=True),
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: self._close_dialog(dlg))],
        )
        self.ctx.page.open(dlg)

    def _close_dialog(self, dlg: ft.AlertDialog) -> None:
        try:
            self.ctx.page.close(dlg)
        except Exception:
            try:
                dlg.open = False
                self.ctx.page.update()
            except Exception:
                pass

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
