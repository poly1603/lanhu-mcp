"""Overview page — compact responsive dashboard."""

from __future__ import annotations

import time
from typing import List

import flet as ft

from .. import theme
from ..components import (
    metric_tile, stat_chip, quick_action_tile, gradient_card, page_frame, section_title,
    secondary_button, StatusBadge, timeline_item,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...core import projects as projects_core
from ...services.tools_registry import discover_mcp_tools

SP = "3"  # compact spacing


class OverviewPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._metrics_row = ft.ResponsiveRow(spacing=theme.space(SP), run_spacing=theme.space(SP),
                                    vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self._stat_bar = ft.Row(spacing=theme.space(SP), wrap=True)
        self._status_badge_holder = ft.Row(spacing=theme.space("2"))
        self._timeline = ft.Column(spacing=0)
        self._loaded_at = time.strftime("%H:%M:%S")

    # ── data ──────────────────────────────────────────────────────
    def _gather(self) -> dict:
        try:
            account_list = accounts_core.get_accounts()
        except Exception:
            account_list = []
        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        try:
            tools = discover_mcp_tools()
        except Exception:
            tools = []
        active_id = (active or {}).get("id", "") if active else ""
        try:
            project_list = projects_core.cached_projects_for_account(active_id)
        except Exception:
            project_list = []
        ide_map = {}
        try:
            ide_map = self.ctx.ide.detect_all()
            ide_installed = sum(1 for v in ide_map.values() if v)
            ide_total = len(ide_map)
        except Exception:
            ide_installed = 0
            ide_total = 0
        return {
            "accounts": len(account_list),
            "active": active,
            "tools": len(tools),
            "tools_list": [t[0] if isinstance(t, (tuple, list)) and len(t) > 0 else str(t) for t in (tools[:12] if tools else [])],
            "projects": len(project_list),
            "ide_installed": ide_installed,
            "ide_total": ide_total,
            "ide_names": [k for k, v in (ide_map.items() if ide_map else {}) if v][:8],
            "running": self.ctx.service.is_running(),
            "account_label": accounts_core.account_primary_contact(active) if active else "未登录",
        }

    # ── stat bar ──────────────────────────────────────────────────
    def _render_stat_bar(self, data: dict) -> None:
        p = self.ctx.palette
        self._stat_bar.controls = [
            stat_chip(p, "账号", str(data["accounts"]), icon=ft.Icons.PERSON, accent=p.primary),
            stat_chip(p, "方法", str(data["tools"]), icon=ft.Icons.BUILD, accent=p.accent),
            stat_chip(p, "项目", str(data["projects"]), icon=ft.Icons.FOLDER, accent=p.warning),
            stat_chip(p, "IDE", f"{data['ide_installed']}/{data['ide_total']}", icon=ft.Icons.TERMINAL, accent=p.accent_warm),
            stat_chip(p, "日志", str(min(len(self.ctx.get_logs()), 999)), icon=ft.Icons.ARTICLE, accent=p.success),
        ]

    # ── metric cards ──────────────────────────────────────────────
    def _render_metrics(self, data: dict) -> None:
        p = self.ctx.palette
        running = data["running"]
        metrics = [
            self._metric(p, "当前账号", data["account_label"], ft.Icons.PERSON, p.primary,
                         "已登录" if data["account_label"] != "未登录" else "未登录"),
            self._metric(p, "服务状态", "运行中" if running else "已停止",
                         ft.Icons.DNS, p.success if running else p.text_muted,
                         f"端口 {self.ctx.port}" if running else "点击服务菜单启动"),
            self._metric(p, "MCP 方法", str(data["tools"]), ft.Icons.EXTENSION, p.accent, "可用工具总数"),
            self._metric(p, "项目", str(data["projects"]), ft.Icons.FOLDER_OUTLINED, p.warning, "蓝湖关联项目"),
            self._metric(p, "账号数", str(data["accounts"]), ft.Icons.GROUP_OUTLINED, p.primary, "已保存账号"),
            self._metric(p, "已识别 IDE", str(data["ide_installed"]), ft.Icons.TERMINAL, p.accent_warm, f"共 {data['ide_total']} 种"),
        ]
        self._metrics_row.controls = [
            ft.Container(content=m, col={"sm": 6, "md": 4, "xl": 4})
            for m in metrics
        ]

    @staticmethod
    def _metric(p, label: str, value: str, icon: str, accent: str, sub: str) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, color=accent, size=18),
                        bgcolor=theme.alpha(accent, 0x16),
                        border_radius=theme.radius("md"),
                        width=36, height=36,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(expand=True),
                    ft.Text(label, size=theme.font_size("xs"), color=p.text_muted),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(value, size=theme.font_size("2xl"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
                ft.Text(sub, size=theme.font_size("xs"), color=p.text_muted, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=theme.space("2")),
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color=p.shadow_sm, offset=ft.Offset(0, 3)),
        )

    # ── timeline ──────────────────────────────────────────────────
    def _render_timeline(self) -> None:
        p = self.ctx.palette
        recent_logs = self.ctx.get_logs()[-5:]
        if not recent_logs:
            self._timeline.controls = [ft.Text("暂无活动记录", size=theme.font_size("xs"), color=p.text_muted)]
            return
        items: List[ft.Control] = []
        for line in recent_logs:
            kind = "info"
            if "[ERR]" in line or "[FAIL]" in line:
                kind = "error"
            elif "[OK]" in line or "成功" in line:
                kind = "ok"
            elif "[WARN]" in line:
                kind = "warn"
            short = line[:70] + ("…" if len(line) > 70 else "")
            items.append(timeline_item(p, short, time="", kind=kind))
        self._timeline.controls = items

    # ── quick actions ─────────────────────────────────────────────
    def _quick_actions(self) -> ft.Control:
        p = self.ctx.palette
        def goto(t): return lambda e: self._goto(t)
        return ft.Row([
            quick_action_tile(p, "启动服务", "连接蓝湖 MCP", ft.Icons.PLAY_ARROW, goto("service"), accent=p.success),
            quick_action_tile(p, "管理账号", "登录/切换账号", ft.Icons.PERSON_ADD, goto("accounts"), accent=p.primary),
            quick_action_tile(p, "配置 AI 工具", "写入 IDE 配置", ft.Icons.SETTINGS, goto("ide"), accent=p.accent),
        ], spacing=theme.space(SP), wrap=True)

    def _workflow_card(self, data: dict) -> ft.Container:
        p = self.ctx.palette
        steps = [
            ("1", "登录蓝湖账号", "获取项目、设计稿和 Cookie 权限", data["account_label"] != "未登录"),
            ("2", "启动 MCP 服务", "在本机暴露 HTTP MCP 端点", data["running"]),
            ("3", "配置 AI 工具", "把 MCP 地址写入常用 IDE", data["ide_installed"] > 0),
            ("4", "浏览项目设计", "从项目页打开设计稿并生成提示词", data["projects"] > 0),
        ]
        controls: List[ft.Control] = []
        for index, title, desc, done in steps:
            accent = p.success if done else p.primary
            controls.append(ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text("✓" if done else index, size=theme.font_size("xs"), weight=theme.WEIGHT_BOLD,
                                        color=p.text_on_primary if done else accent),
                        bgcolor=accent if done else theme.alpha(accent, 0x16),
                        border_radius=theme.radius("full"),
                        width=28,
                        height=28,
                        alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text(title, size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                        ft.Text(desc, size=theme.font_size("xs"), color=p.text_muted),
                    ], spacing=0, expand=True),
                ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(vertical=theme.space("2")),
            ))
        return ft.Container(
            content=ft.Column([
                ft.Text("使用路径", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Column(controls, spacing=0),
            ], spacing=theme.space("2")),
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color=p.shadow_sm, offset=ft.Offset(0, 3)),
        )

    def _suggestion_card(self, data: dict) -> ft.Container:
        p = self.ctx.palette
        if data["account_label"] == "未登录":
            title, desc, icon, target = "先登录蓝湖账号", "登录后才能读取项目、设计稿和生成可用 MCP 地址。", ft.Icons.LOGIN, "accounts"
        elif not data["running"]:
            title, desc, icon, target = "启动 MCP 服务", "让 AI IDE 能通过本地 HTTP 端点访问蓝湖能力。", ft.Icons.PLAY_ARROW, "service"
        elif data["ide_installed"] and data["projects"] == 0:
            title, desc, icon, target = "刷新项目列表", "读取当前账号可访问项目，后续可浏览设计稿。", ft.Icons.SYNC, "projects"
        else:
            title, desc, icon, target = "配置 AI 工具", "一键写入 MCP 配置，把蓝湖能力接入日常开发流。", ft.Icons.SETTINGS, "ide"
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon, color=p.primary, size=22),
                    bgcolor=p.primary_light,
                    border_radius=theme.radius("lg"),
                    width=44,
                    height=44,
                    alignment=ft.alignment.center,
                ),
                ft.Column([
                    ft.Text("下一步建议", size=theme.font_size("xs"), color=p.text_muted),
                    ft.Text(title, size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Text(desc, size=theme.font_size("xs"), color=p.text_muted),
                ], spacing=0, expand=True),
                secondary_button("前往", lambda e, t=target: self._goto(t), icon=ft.Icons.ARROW_FORWARD),
            ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=p.primary_light,
            border=ft.border.all(1, p.primary_light_hover),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
        )

    # ── lifecycle ─────────────────────────────────────────────────
    def refresh(self) -> None:
        data = self._gather()
        self._render_stat_bar(data)
        self._render_metrics(data)
        self._render_timeline()
        self._status_badge_holder.controls = [
            StatusBadge(self.ctx.palette, "运行中" if data["running"] else "已停止", "ok" if data["running"] else "idle"),
            StatusBadge(self.ctx.palette, f"端口 {self.ctx.port}", "info"),
        ]
        self._loaded_at = time.strftime("%H:%M:%S")
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette
        data = self._gather()
        self._render_stat_bar(data)
        self._render_metrics(data)
        self._render_timeline()
        self._status_badge_holder.controls = [
            StatusBadge(p, "运行中" if data["running"] else "已停止", "ok" if data["running"] else "idle"),
            StatusBadge(p, f"端口 {self.ctx.port}", "info"),
        ]

        # ── 横幅 ────────────────────────────────────────────────
        banner = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text("欢迎使用 Lanhu MCP", size=theme.font_size("2xl"), weight=theme.WEIGHT_BOLD, color=p.text_on_primary),
                    ft.Text("连接蓝湖设计与 AI 开发，让项目、设计稿、切图和团队消息直达 AI IDE。",
                            size=theme.font_size("sm"), color=p.text_on_primary, opacity=0.9),
                ], expand=True, spacing=0),
                ft.Column([
                    self._status_badge_holder,
                    ft.Row([
                        ft.Container(
                            content=ft.Row([ft.Icon(ft.Icons.PLAY_ARROW, size=16, color=p.text_on_primary), ft.Text("启动服务", size=theme.font_size("sm"), color=p.text_on_primary)], spacing=theme.space("1")),
                            bgcolor=theme.alpha("#FFFFFF", 0x22),
                            border=ft.border.all(1, theme.alpha("#FFFFFF", 0x36)),
                            border_radius=theme.radius("full"),
                            padding=ft.padding.symmetric(horizontal=theme.space("3"), vertical=theme.space("2")),
                            ink=True,
                            on_click=lambda e: self._goto("service"),
                        ),
                        ft.Container(
                            content=ft.Row([ft.Icon(ft.Icons.SETTINGS, size=16, color=p.text_on_primary), ft.Text("配置工具", size=theme.font_size("sm"), color=p.text_on_primary)], spacing=theme.space("1")),
                            bgcolor=theme.alpha("#FFFFFF", 0x12),
                            border=ft.border.all(1, theme.alpha("#FFFFFF", 0x28)),
                            border_radius=theme.radius("full"),
                            padding=ft.padding.symmetric(horizontal=theme.space("3"), vertical=theme.space("2")),
                            ink=True,
                            on_click=lambda e: self._goto("ide"),
                        ),
                    ], spacing=theme.space("2")),
                    ft.Text(f"加载于 {self._loaded_at}", size=theme.font_size("xs"), color=p.text_on_primary, opacity=0.7),
                ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=theme.space("2")),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            gradient=ft.LinearGradient(begin=ft.alignment.center_left, end=ft.alignment.center_right,
                                       colors=[p.primary_gradient_start, p.primary_gradient_end]),
            border_radius=theme.radius("lg"),
            padding=ft.padding.symmetric(horizontal=theme.space("5"), vertical=theme.space("4")),
        )

        # ── 统计条 ──────────────────────────────────────────────
        stat_bar = ft.Container(content=self._stat_bar, bgcolor=p.card,
                                border_radius=theme.radius("md"), padding=theme.space("3"),
                                border=ft.border.all(1, p.border_light))

        # ── 指标卡片 ────────────────────────────────────────────
        metrics = ft.Container(content=self._metrics_row, padding=0)

        # ── 左列 ────────────────────────────────────────────────
        tool_tags: List[ft.Control] = []
        for name in data.get("tools_list", []):
            tool_tags.append(ft.Container(
                content=ft.Text(name.replace("lanhu_", "").replace("_", " ")[:18],
                                size=theme.font_size("xs"), color=p.accent),
                bgcolor=p.accent_light, border_radius=theme.radius("full"),
                padding=ft.padding.symmetric(horizontal=7, vertical=3),
            ))
        if not tool_tags:
            tool_tags = [ft.Text("启动服务后加载", size=theme.font_size("xs"), color=p.text_muted)]

        quick_card = ft.Container(
            content=ft.Column([
                ft.Text("快捷操作", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                self._quick_actions(),
            ], spacing=theme.space("2")),
            bgcolor=p.card, border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("lg"), padding=theme.space("4"),
        )

        tools_card = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("MCP 方法", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Container(expand=True),
                    ft.Text(f"{data['tools']} 个", size=theme.font_size("xs"), color=p.text_muted),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row(tool_tags, spacing=theme.space("1"), wrap=True),
            ], spacing=theme.space("2")),
            bgcolor=p.card, border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("lg"), padding=theme.space("4"),
        )

        # ── 右列 ────────────────────────────────────────────────
        timeline_card = ft.Container(
            content=ft.Column([
                ft.Text("最近活动", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                self._timeline,
            ], spacing=theme.space("2")),
            bgcolor=p.card, border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("lg"), padding=theme.space("4"),
        )

        ide_tags: List[ft.Control] = []
        for name in data.get("ide_names", []):
            ide_tags.append(ft.Container(
                content=ft.Text(name, size=theme.font_size("xs"), color=p.success),
                bgcolor=p.success_light, border_radius=theme.radius("full"),
                padding=ft.padding.symmetric(horizontal=7, vertical=3),
            ))
        if not ide_tags:
            ide_tags = [ft.Text("未检测到", size=theme.font_size("xs"), color=p.text_muted)]

        ide_card = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("已识别 IDE", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Container(expand=True),
                    ft.Text(f"{data['ide_installed']}/{data['ide_total']}", size=theme.font_size("xs"), color=p.text_muted),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row(ide_tags, spacing=theme.space("1"), wrap=True),
            ], spacing=theme.space("2")),
            bgcolor=p.card, border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("lg"), padding=theme.space("4"),
        )

        top_flow = ft.ResponsiveRow([
            ft.Container(content=self._suggestion_card(data), col={"sm": 12, "md": 6}),
            ft.Container(content=self._workflow_card(data), col={"sm": 12, "md": 6}),
        ], spacing=theme.space(SP), run_spacing=theme.space(SP), vertical_alignment=ft.CrossAxisAlignment.START)

        main_grid = ft.ResponsiveRow([
            ft.Container(content=quick_card, col={"sm": 12, "md": 6, "lg": 5}),
            ft.Container(content=tools_card, col={"sm": 12, "md": 6, "lg": 4}),
            ft.Container(content=ide_card, col={"sm": 12, "md": 12, "lg": 3}),
        ], spacing=theme.space(SP), run_spacing=theme.space(SP), vertical_alignment=ft.CrossAxisAlignment.START)

        # ── 核心能力 ────────────────────────────────────────────
        feat_grid = ft.GridView(runs_count=4, max_extent=280, child_aspect_ratio=1.5,
                                spacing=theme.space(SP), run_spacing=theme.space(SP))
        feat_grid.controls = [
            self._feat(p, "安全登录", "WebView2 + Cookie 双模式", ft.Icons.SECURITY, p.primary),
            self._feat(p, "极速响应", "本地 MCP 毫秒级响应", ft.Icons.SPEED, p.success),
            self._feat(p, "多端兼容", "覆盖 15+ AI 工具", ft.Icons.EXTENSION, p.accent_warm),
            self._feat(p, "设计还原", "高还原开发全链路", ft.Icons.DESIGN_SERVICES, p.accent),
        ]
        feat_section = ft.Column([
            ft.Text("核心能力", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
            feat_grid,
        ], spacing=theme.space("2"))

        footer = ft.Row([
            ft.Text("Lanhu MCP Server", size=theme.font_size("xs"), color=p.text_muted),
            ft.Container(expand=True),
            ft.Text(f"端口: {self.ctx.port}", size=theme.font_size("xs"), color=p.text_muted),
        ])

        body = ft.Column([banner, metrics, main_grid, top_flow, footer], spacing=theme.space("3"))
        return page_frame(p, "总览", "账号、服务、项目和 AI 工具的当前状态", body)

    def _feat(self, p, title: str, desc: str, icon: str, accent: str) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Icon(icon, color=accent, size=20),
                    bgcolor=theme.alpha(accent, 0x18), border_radius=theme.radius("md"),
                    width=36, height=36, alignment=ft.alignment.center,
                ),
                ft.Text(title, size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Text(desc, size=theme.font_size("xs"), color=p.text_muted),
            ], spacing=theme.space("1")),
            bgcolor=p.card, border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("lg"), padding=theme.space("3"),
        )

    def _goto(self, target: str) -> None:
        if self.ctx.navigate:
            self.ctx.navigate(target)


__all__ = ["OverviewPage"]
