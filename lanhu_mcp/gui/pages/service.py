"""Service page — MCP service control with method cards and inline testing."""

from __future__ import annotations

import json
import time
from typing import List, Optional

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, page_frame, responsive_pair, StatusBadge, CountBadge,
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
        self._methods_container = ft.Column(spacing=theme.space("3"))
        self._busy = False
        self._started_at: Optional[float] = None
        self._test_results: dict = {}

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

    def _render_status(self) -> None:
        p = self.ctx.palette
        running = self.ctx.service.is_running()
        self._status_holder.controls = [
            StatusBadge(p, "运行中" if running else "已停止", "ok" if running else "idle"),
            StatusBadge(p, f"端口 {self.ctx.port}", "info"),
        ]
        self._url_text.value = self._mcp_url()
        self._url_text.color = p.text_primary

        uptime = self._uptime()
        self._health_section.controls = [
            stat_chip(p, "运行时长", uptime, icon=ft.Icons.TIMER, accent=p.accent),
            stat_chip(p, "MCP 端点", "/mcp", icon=ft.Icons.LINK, accent=p.primary),
            stat_chip(p, "地址", f"localhost:{self.ctx.port}", icon=ft.Icons.ROUTER, accent=p.warning),
        ]

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

    # ── start / stop ──────────────────────────────────────────────
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
            self._build_methods()
            self.ctx.page.update()

        def err(exc):
            self._busy = False
            show_error(self.ctx.page, exc, "服务停止", self.ctx.palette, self.ctx.add_log)
            self._render_status()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    # ── health check ──────────────────────────────────────────────
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

    # ── test a single method ──────────────────────────────────────
    def _test_method(self, method_name: str) -> None:
        url = self._mcp_url()
        p = self.ctx.palette
        self.ctx.add_log(f"[TEST] 调用方法: {method_name}")

        # Update the test button to show loading
        self._test_results[method_name] = {"status": "loading"}
        self._build_methods()
        self.ctx.page.update()

        def work():
            import httpx
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": method_name, "arguments": {}},
            }
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            resp = httpx.post(url, json=payload, headers=headers, timeout=15.0)
            return resp.status_code, resp.text[:500]

        def done(result):
            status_code, body = result
            ok = isinstance(status_code, int) and status_code < 400
            self._test_results[method_name] = {
                "status": "ok" if ok else "error",
                "code": status_code,
                "body": body,
            }
            self.ctx.add_log(f"[TEST] {method_name}: HTTP {status_code}")
            self._build_methods()
            self.ctx.page.update()

        def err(exc):
            self._test_results[method_name] = {
                "status": "error",
                "body": str(exc)[:200],
            }
            self.ctx.add_log(f"[TEST] {method_name}: {exc}")
            self._build_methods()
            self.ctx.page.update()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    # ── config dialog ─────────────────────────────────────────────
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
            blocks.append(ft.Column([
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
            ], spacing=theme.space("2")))

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

    # ── lifecycle ─────────────────────────────────────────────────
    def refresh(self) -> None:
        self._render_status()
        self._build_methods()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    def _build_methods(self) -> None:
        p = self.ctx.palette
        running = self.ctx.service.is_running()

        # Only show methods when service is running
        if not running:
            self._methods_container.controls = [
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE, size=28, color=p.primary),
                            bgcolor=p.primary_light,
                            border_radius=theme.radius("full"),
                            width=58,
                            height=58,
                            alignment=ft.alignment.center,
                        ),
                        ft.Column([
                            ft.Text("服务未启动", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                            ft.Text("启动 MCP 服务后可查看工具方法、测试调用，并复制 AI 工具接入配置。",
                                    size=theme.font_size("sm"), color=p.text_muted),
                        ], spacing=theme.space("1"), expand=True),
                        ft.Row([
                            primary_button("启动服务", lambda e: self._start(), icon=ft.Icons.PLAY_ARROW),
                            secondary_button("复制配置", lambda e: self._show_config(), icon=ft.Icons.CONTENT_COPY),
                        ], spacing=theme.space("2"), wrap=True),
                    ], spacing=theme.space("4"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=p.card,
                    border=ft.border.all(1, p.border_light),
                    border_radius=theme.radius("xl"),
                    padding=theme.space("5"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color=p.shadow_sm, offset=ft.Offset(0, 3)),
                ),
            ]
            return

        try:
            tools = discover_mcp_tools()
            groups = group_mcp_tools(tools)
        except Exception:
            tools, groups = [], {}

        group_controls: List[ft.Control] = []
        for group_name, items in groups.items():
            if not items:
                continue
            method_cards: List[ft.Control] = []
            for name, summary in items:
                test_info = self._test_results.get(name, {})
                test_status = test_info.get("status", "")
                method_cards.append(self._method_card(p, name, summary, test_status, test_info))
            badge = CountBadge(p, len(items), "info")
            methods_grid = ft.ResponsiveRow(
                [ft.Container(content=card, col={"sm": 12, "md": 6, "lg": 4}) for card in method_cards],
                spacing=theme.space("2"),
                run_spacing=theme.space("2"),
            )
            group_controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(group_name, size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                            badge,
                        ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Divider(height=1, color=p.border_light),
                        methods_grid,
                    ], spacing=theme.space("3")),
                    bgcolor=p.card,
                    border=ft.border.all(1, p.border_light),
                    border_radius=theme.radius("xl"),
                    padding=theme.space("5"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=4, color=p.shadow_sm, offset=ft.Offset(0, 2)),
                )
            )

        header = ft.Row([
            ft.Text("支持的 MCP 方法", size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
            ft.Container(expand=True),
            CountBadge(p, len(tools), "info"),
        ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self._methods_container.controls = [header] + group_controls

    def _method_card(self, p, name: str, summary: str, test_status: str, test_info: dict) -> ft.Container:
        # Status indicator
        if test_status == "loading":
            status_widget = ft.ProgressRing(width=16, height=16, stroke_width=2)
        elif test_status == "ok":
            status_widget = ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=p.success)
        elif test_status == "error":
            status_widget = ft.Icon(ft.Icons.ERROR_OUTLINE, size=16, color=p.danger)
        else:
            status_widget = ft.Container(width=16, height=16)

        # Short display name
        display_name = name.replace("lanhu_", "").replace("_", " ")

        test_btn = ghost_icon_button(
            ft.Icons.PLAY_CIRCLE_OUTLINE,
            lambda e, n=name: self._test_method(n),
            tooltip="测试调用",
        )

        result_text = None
        if test_info.get("body"):
            body = test_info["body"][:120]
            code = test_info.get("code", "")
            result_text = ft.Text(
                f"HTTP {code}: {body}" if code else body,
                size=theme.font_size("xs"),
                color=p.success if test_status == "ok" else p.danger,
                font_family=theme.FONT_MONO,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            )

        content_items = [
            ft.Row([
                status_widget,
                ft.Text(display_name, size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary, expand=True),
                test_btn,
            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(summary, size=theme.font_size("xs"), color=p.text_muted, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ]
        if result_text:
            content_items.append(result_text)

        return ft.Container(
            content=ft.Column(content_items, spacing=theme.space("1")),
            padding=ft.padding.symmetric(horizontal=theme.space("3"), vertical=theme.space("2")),
            border_radius=theme.radius("md"),
            bgcolor=p.success_light if test_status == "ok" else (p.danger_light if test_status == "error" else p.surface),
            border=ft.border.all(1, p.border_light),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    def _service_step(self, p, index: str, title: str, desc: str, icon: str, accent: str) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon, size=18, color=accent),
                    bgcolor=theme.alpha(accent, 0x16),
                    border_radius=theme.radius("md"),
                    width=38,
                    height=38,
                    alignment=ft.alignment.center,
                ),
                ft.Column([
                    ft.Text(f"{index}. {title}", size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Text(desc, size=theme.font_size("xs"), color=p.text_muted, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=0, expand=True),
            ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=p.surface,
            border_radius=theme.radius("lg"),
            padding=theme.space("3"),
        )

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render_status()

        running = self.ctx.service.is_running()

        # ── Service control card ──────────────────────────────────
        control_card = gradient_card(
            p,
            ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.DNS if running else ft.Icons.HOURGLASS_EMPTY,
                            color="#FFFFFF", size=28,
                        ),
                        gradient=ft.LinearGradient(
                            begin=ft.alignment.top_left, end=ft.alignment.bottom_right,
                            colors=[p.success, p.primary] if running else [p.text_muted, p.surface_hover],
                        ),
                        border_radius=theme.radius("lg"),
                        padding=theme.space("3"),
                        width=52, height=52,
                        alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text("MCP 服务控制", size=theme.font_size("xl"),
                                weight=theme.WEIGHT_BOLD, color=p.text_primary),
                        ft.Text(self._url_text.value or "", size=theme.font_size("sm"),
                                color=p.text_muted, selectable=True),
                    ], spacing=theme.space("1"), expand=True),
                    ft.Column([self._status_holder], horizontal_alignment=ft.CrossAxisAlignment.END),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=theme.space("4")),
                ft.Divider(height=1, color=p.border_light),
                self._action_holder,
            ], spacing=theme.space("4")),
        )

        # ── Health info card ──────────────────────────────────────
        info_card = gradient_card(
            p,
            ft.Column([
                ft.Text("服务信息", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                self._health_section,
            ], spacing=theme.space("3")),
        )

        steps_card = ft.Container(
            content=ft.ResponsiveRow([
                ft.Container(content=self._service_step(p, "1", "启动服务", "确认账号有效后启动本地 MCP HTTP 服务", ft.Icons.PLAY_ARROW, p.success), col={"sm": 12, "md": 4}),
                ft.Container(content=self._service_step(p, "2", "复制配置", "把当前端点写入 Cursor、Trae、Claude 等工具", ft.Icons.CONTENT_COPY, p.primary), col={"sm": 12, "md": 4}),
                ft.Container(content=self._service_step(p, "3", "测试方法", "在服务运行后验证工具方法是否可正常调用", ft.Icons.RULE, p.accent), col={"sm": 12, "md": 4}),
            ], spacing=theme.space("3"), run_spacing=theme.space("3")),
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color=p.shadow_sm, offset=ft.Offset(0, 3)),
        )

        # ── Methods section ───────────────────────────────────────
        self._build_methods()

        body = ft.Column([
            responsive_pair(control_card, info_card, spacing=theme.space("4")),
            steps_card,
            self._methods_container,
        ], spacing=theme.space("5"))

        return page_frame(p, "服务", "启动 MCP 服务 · 健康监控 · 方法清单与测试", body)


__all__ = ["ServicePage"]
