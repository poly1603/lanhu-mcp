"""Service page (v2) — enriched start/stop panel, health bar, method tabs."""

from __future__ import annotations

import time
from typing import List, Optional

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge, CountBadge,
    primary_button, secondary_button, danger_button, ghost_icon_button,
    stat_chip, field_row,
    run_in_background, toast, show_error,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...services.ide_config import mcp_config_snippets
from ...services.tools_registry import discover_mcp_tools, group_mcp_tools


MCP_URL_MAP: dict = {}


class ServicePage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._status_holder = ft.Row(spacing=theme.space("2"))
        self._health_section = ft.Row(spacing=theme.space("4"), wrap=True)
        self._action_holder = ft.Row(spacing=theme.space("3"))
        self._url_text = ft.Text(selectable=True, size=theme.font_size("sm"))
        self._methods_container = ft.Column(spacing=theme.space("2"))
        self._busy = False
        self._started_at: Optional[float] = None

    # ── helpers ───────────────────────────────────────────────────
    def _mcp_url(self) -> str:
        try:
            cached = MCP_URL_MAP.get(self.ctx.port)
            if cached:
                return cached
            return accounts_core.current_mcp_url(self.ctx.port)
        except Exception:
            return f"http://localhost:{self.ctx.port}/mcp"

    def _uptime(self) -> str:
        if not self._started_at:
            return "—"
        elapsed = int(time.time() - self._started_at)
        if elapsed < 60:
            return f"{elapsed}s"
        if elapsed < 3600:
            return f"{elapsed // 60}m {elapsed % 60}s"
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        return f"{h}h {m}m"

    # ── status ────────────────────────────────────────────────────
    def _render_status(self) -> None:
        p = self.ctx.palette
        running = self.ctx.service.is_running()
        self._status_holder.controls = [
            StatusBadge(p, "运行中" if running else "已停止", "ok" if running else "idle"),
            StatusBadge(p, f"端口 {self.ctx.port}", "info"),
        ]
        self._url_text.value = self._mcp_url()
        self._url_text.color = p.text_primary

        # Health stats
        uptime = self._uptime()
        chips: List[ft.Control] = [
            stat_chip(p, "运行时长", uptime, icon=ft.Icons.TIMER, accent=p.accent),
            stat_chip(p, "MCP 端点", "/mcp", icon=ft.Icons.LINK, accent=p.primary),
            stat_chip(p, "地址", f"localhost:{self.ctx.port}", icon=ft.Icons.ROUTER, accent=p.warning),
        ]
        self._health_section.controls = chips

        # Action buttons
        if self._busy:
            self._action_holder.controls = [
                ft.Row([ft.ProgressRing(width=16, height=16),
                        ft.Text("处理中…", color=p.text_secondary)], spacing=theme.space("2"))
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

    # ── actions ───────────────────────────────────────────────────
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
            if ok:
                self._started_at = time.time()
                MCP_URL_MAP[self.ctx.port] = self._mcp_url()
            else:
                self._started_at = None
            self.ctx.add_log(msg or ("服务已启动" if ok else "服务启动失败"))
            toast(self.ctx.page, msg or ("服务已启动" if ok else "服务启动失败"),
                  "ok" if ok else "error", self.ctx.palette)
            self._render_status()
            self._build_methods()
            self.ctx.page.update()

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
            self._started_at = None
            ok, msg = result if isinstance(result, tuple) else (bool(result), "")
            self.ctx.add_log(msg or ("服务已停止" if ok else "停止失败"))
            toast(self.ctx.page, msg or ("服务已停止" if ok else "停止失败"),
                  "ok" if ok else "error", self.ctx.palette)
            self._render_status()
            self.ctx.page.update()

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
            import httpx
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
                ft.Column([
                    ft.Row([
                        ft.Text(label, weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary, expand=True),
                        ghost_icon_button(ft.Icons.CONTENT_COPY, lambda e, t=text: copy(t), tooltip="复制"),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(
                        content=ft.Text(text, selectable=True, size=theme.font_size("xs"),
                                        color=p.text_secondary, font_family=theme.FONT_MONO),
                        bgcolor=p.surface, border=ft.border.all(1, p.border_light),
                        border_radius=theme.radius("sm"), padding=theme.space("3"),
                    ),
                ], spacing=theme.space("2")),
            )
        dlg = ft.AlertDialog(
            title=ft.Text("MCP 接入配置", color=p.text_primary),
            content=ft.Container(
                width=560,
                content=ft.Column(blocks, spacing=theme.space("4"), scroll=ft.ScrollMode.AUTO, tight=True),
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
        self._build_methods()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # ── methods list (grouped expansion tiles) ────────────────────
    def _build_methods(self) -> None:
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
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=14, color=p.success),
                        ft.Text(name, size=theme.font_size("sm"), weight=theme.WEIGHT_MEDIUM, color=p.text_primary),
                        ft.Text(summary, size=theme.font_size("xs"), color=p.text_muted, expand=True),
                    ], spacing=theme.space("2")),
                    bgcolor=p.surface if group_controls.__len__() % 2 == 0 else None,
                    border_radius=theme.radius("sm"),
                    padding=theme.space("1"),
                )
                for name, summary in items
            ]
            badge = CountBadge(p, len(items), "info")
            group_controls.append(
                ft.ExpansionTile(
                    title=ft.Row([
                        ft.Text(group_name, weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                        badge,
                    ], spacing=theme.space("2"), tight=True),
                    controls=[ft.Container(ft.Column(rows, spacing=theme.space("1")),
                                           padding=ft.padding.only(left=12, bottom=8))],
                    initially_expanded=len(items) <= 6,
                )
            )

        header = ft.Row([
            ft.Text(f"支持的 MCP 方法", size=theme.font_size("lg"),
                    weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
            ft.Container(expand=True),
            CountBadge(p, len(tools), "info"),
        ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self._methods_container.controls = [header] + group_controls

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render_status()

        # ── Control section (split into left/right) ──
        left_col = ft.Column([
            ft.Text("MCP 服务", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
            ft.Row([ft.Text("服务地址", size=theme.font_size("sm"), color=p.text_secondary, width=72),
                    self._url_text], spacing=theme.space("3")),
            self._action_holder,
        ], spacing=theme.space("4"))

        right_col = ft.Column([
            ft.Text("服务信息", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
            self._health_section,
        ], spacing=theme.space("4"))

        control_card = gradient_card(
            p,
            ft.Row([
                ft.Container(content=left_col, expand=1),
                ft.VerticalDivider(width=1, color=p.border_light),
                ft.Container(content=right_col, expand=2, padding=ft.padding.only(left=theme.space("6"))),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
        )

        self._build_methods()
        methods_card = card(p, ft.Column(self._methods_container.controls + [ft.Container(height=theme.space("2"))],
                                         spacing=theme.space("3"), tight=True))

        return ft.Column(
            [
                ft.Row([
                    section_title(p, "服务", "启动 MCP 服务 · 健康监控 · 方法清单"),
                    ft.Container(expand=True),
                    self._status_holder,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                control_card,
                methods_card,
            ],
            spacing=theme.space("6"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )


__all__ = ["ServicePage"]
