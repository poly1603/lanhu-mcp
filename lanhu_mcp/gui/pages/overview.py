"""Overview page — enriched dashboard: stat bar, metric tiles, timeline, quick actions."""

from __future__ import annotations

import time
from typing import List, Tuple

import flet as ft

from .. import theme
from ..components import (
    metric_tile, stat_chip, quick_action_tile, gradient_card, section_title,
    StatusBadge, timeline_item,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...core import projects as projects_core
from ...services.tools_registry import discover_mcp_tools


class OverviewPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._metrics_row = ft.Row(wrap=True, spacing=theme.space("4"), run_spacing=theme.space("4"))
        self._stat_bar = ft.Row(spacing=theme.space("4"), wrap=True)
        self._status_badge_holder = ft.Row(spacing=theme.space("2"))
        self._timeline = ft.Column(spacing=theme.space("1"))
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
            "tools_list": [t[0] if isinstance(t, (tuple, list)) and len(t) > 0 else (str(t) if not isinstance(t, str) else t) for t in (tools[:12] if tools else [])],
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
        chips: List[ft.Control] = [
            stat_chip(p, "账号", str(data["accounts"]), icon=ft.Icons.PERSON, accent=p.primary),
            stat_chip(p, "MCP 方法", str(data["tools"]), icon=ft.Icons.BUILD, accent=p.accent),
            stat_chip(p, "项目", str(data["projects"]), icon=ft.Icons.FOLDER, accent=p.warning),
            stat_chip(p, "IDE", f"{data['ide_installed']}/{data['ide_total']}", icon=ft.Icons.TERMINAL, accent=p.accent_warm),
            stat_chip(p, "日志", str(min(len(self.ctx.get_logs()), 999)), icon=ft.Icons.ARTICLE, accent=p.success),
        ]
        self._stat_bar.controls = chips

    # ── metric tiles ──────────────────────────────────────────────
    def _render_metrics(self, data: dict) -> None:
        p = self.ctx.palette
        running = data["running"]
        tiles: List[ft.Control] = [
            metric_tile(p, "当前账号", data["account_label"], icon=ft.Icons.PERSON, accent=p.primary,
                        sub="登录后可使用完整功能" if data["account_label"] == "未登录" else "已登录"),
            metric_tile(p, "服务状态", "运行中" if running else "已停止", icon=ft.Icons.DNS,
                        accent=p.success if running else p.text_muted,
                        trend="up" if running else None,
                        sub=f"端口 {self.ctx.port}" if running else "点击启动"),
            metric_tile(p, "MCP 方法", str(data["tools"]), icon=ft.Icons.BUILD, accent=p.accent,
                        sub="可用工具总数"),
            metric_tile(p, "项目", str(data["projects"]), icon=ft.Icons.FOLDER_OUTLINED, accent=p.warning,
                        sub="蓝湖关联项目"),
            metric_tile(p, "账号", str(data["accounts"]), icon=ft.Icons.GROUP, accent=p.primary),
            metric_tile(p, "已识别 IDE", str(data["ide_installed"]), icon=ft.Icons.TERMINAL, accent=p.accent_warm,
                        sub=f"共 {data['ide_total']} 种支持"),
        ]
        self._metrics_row.controls = tiles

    # ── timeline ──────────────────────────────────────────────────
    def _render_timeline(self) -> None:
        p = self.ctx.palette
        recent_logs = self.ctx.get_logs()[-6:]
        if not recent_logs:
            self._timeline.controls = [
                ft.Text("暂无活动记录", size=theme.font_size("sm"), color=p.text_muted)
            ]
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
            short = line[:80] + ("…" if len(line) > 80 else "")
            items.append(timeline_item(p, short, time="", kind=kind))
        self._timeline.controls = items

    # ── quick actions ─────────────────────────────────────────────
    def _build_quick_actions(self) -> ft.Control:
        p = self.ctx.palette

        def goto(target: str):
            return lambda e: self._goto(target)

        return ft.Row(
            [
                quick_action_tile(p, "启动服务", "连接蓝湖 MCP 服务", ft.Icons.PLAY_ARROW,
                                  goto("service"), accent=p.success),
                quick_action_tile(p, "管理账号", "登录或切换蓝湖账号", ft.Icons.PERSON_ADD,
                                  goto("accounts"), accent=p.primary),
                quick_action_tile(p, "配置 AI 工具", "将 MCP 写入 IDE 配置", ft.Icons.SETTINGS,
                                  goto("ide"), accent=p.accent),
            ],
            spacing=theme.space("4"),
            wrap=True,
        )

    # ── lifecycle ─────────────────────────────────────────────────
    def refresh(self) -> None:
        data = self._gather()
        self._render_stat_bar(data)
        self._render_metrics(data)
        self._render_timeline()
        self._status_badge_holder.controls = [
            StatusBadge(self.ctx.palette,
                        "服务运行中" if data["running"] else "服务未启动",
                        "ok" if data["running"] else "idle"),
            StatusBadge(self.ctx.palette, f"端口 {self.ctx.port}", "info"),
        ]
        self._loaded_at = time.strftime("%H:%M:%S")
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # ── helper: two-column Row for cards ──────────────────────────
    @staticmethod
    def _two_col_row(left: ft.Control, right: ft.Control, p) -> ft.Row:
        return ft.Row(
            [left, right],
            spacing=theme.space("4"),
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette
        data = self._gather()

        self._render_stat_bar(data)
        self._render_metrics(data)
        self._render_timeline()

        self._status_badge_holder.controls = [
            StatusBadge(p, "服务运行中" if data["running"] else "服务未启动",
                        "ok" if data["running"] else "idle"),
            StatusBadge(p, f"端口 {self.ctx.port}", "info"),
        ]

        # ── 欢迎横幅 ────────────────────────────────────────────
        welcome_banner = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(
                        "欢迎使用 Lanhu MCP",
                        size=theme.font_size("3xl"),
                        weight=theme.WEIGHT_BOLD,
                        color=p.text_on_primary,
                    ),
                    ft.Text(
                        "连接蓝湖设计与 AI 开发，让项目、设计稿、切图和团队消息一键直达 Codex、Claude、Cursor 等 AI IDE。",
                        size=theme.font_size("base"),
                        color=p.text_on_primary,
                        opacity=0.9,
                    ),
                ], expand=True, spacing=theme.space("2")),
                ft.Column([
                    self._status_badge_holder,
                    ft.Text(
                        f"加载于 {self._loaded_at}",
                        size=theme.font_size("xs"),
                        color=p.text_on_primary,
                        opacity=0.7,
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=theme.space("2")),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            gradient=ft.LinearGradient(
                begin=ft.alignment.center_left,
                end=ft.alignment.center_right,
                colors=[p.primary_gradient_start, p.primary_gradient_end],
            ),
            border_radius=theme.radius("xl"),
            padding=ft.padding.symmetric(horizontal=theme.space("8"), vertical=theme.space("6")),
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=12, color=p.shadow_lg,
                offset=ft.Offset(0, 4),
            ),
        )

        # ── 统计卡片条 ──────────────────────────────────────────
        stat_section = gradient_card(p, self._stat_bar, padding=theme.space("4"))

        # ── 指标卡片行 (2行 x 3列) ─────────────────────────────
        tiles = self._metrics_row.controls
        row1_tiles = tiles[:3] if len(tiles) >= 3 else tiles
        row2_tiles = tiles[3:6] if len(tiles) > 3 else []

        metrics_section = ft.Column([
            ft.Row(row1_tiles, spacing=theme.space("4"), wrap=True),
        ], spacing=theme.space("4"))
        if row2_tiles:
            metrics_section.controls.append(
                ft.Row(row2_tiles, spacing=theme.space("4"), wrap=True)
            )

        # ── 左列：快捷操作 + 支持的工具 ────────────────────────
        quick_actions_section = gradient_card(
            p,
            ft.Column([
                ft.Text("快捷操作", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Container(height=theme.space("2")),
                self._build_quick_actions(),
            ], spacing=0),
            padding=theme.space("4"),
        )

        # 支持的 MCP 方法标签云
        tool_tags: List[ft.Control] = []
        for name in data.get("tools_list", []):
            short_name = name.replace("lanhu_", "").replace("_", " ")[:20]
            tool_tags.append(
                ft.Container(
                    content=ft.Text(short_name, size=theme.font_size("xs"), color=p.accent),
                    bgcolor=p.accent_light,
                    border_radius=theme.radius("full"),
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                )
            )
        if not tool_tags:
            tool_tags = [ft.Text("启动服务后加载", size=theme.font_size("sm"), color=p.text_muted)]

        tools_card = gradient_card(
            p,
            ft.Column([
                ft.Text("支持的 MCP 方法", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Text(f"共 {data['tools']} 个可用工具", size=theme.font_size("sm"), color=p.text_muted),
                ft.Container(height=theme.space("2")),
                ft.Row(tool_tags, spacing=theme.space("2"), wrap=True),
            ], spacing=theme.space("2")),
            padding=theme.space("4"),
        )

        # ── 右列：最近活动 + 已识别 IDE ────────────────────────
        timeline_card = gradient_card(
            p,
            ft.Column([
                ft.Text("最近活动", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Divider(height=1, color=p.border_light),
                self._timeline,
            ], spacing=theme.space("3")),
            padding=theme.space("4"),
        )

        # 已识别 IDE 卡片
        ide_tags: List[ft.Control] = []
        for name in data.get("ide_names", []):
            ide_tags.append(
                ft.Container(
                    content=ft.Text(name, size=theme.font_size("xs"), color=p.success),
                    bgcolor=p.success_light,
                    border_radius=theme.radius("full"),
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                )
            )
        if not ide_tags:
            ide_tags = [ft.Text("未检测到已安装 IDE", size=theme.font_size("sm"), color=p.text_muted)]

        ide_card = gradient_card(
            p,
            ft.Column([
                ft.Text("已识别 AI 工具", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Text(f"已安装 {data['ide_installed']} / 共 {data['ide_total']} 种", size=theme.font_size("sm"), color=p.text_muted),
                ft.Container(height=theme.space("2")),
                ft.Row(ide_tags, spacing=theme.space("2"), wrap=True),
            ], spacing=theme.space("2")),
            padding=theme.space("4"),
        )

        # ── 功能亮点 (4 列) ─────────────────────────────────────
        features_row = ft.Row(
            [
                self._feature_card(p, "安全登录", "WebView2 + Cookie 双模式登录", ft.Icons.SECURITY, p.primary),
                self._feature_card(p, "极速响应", "本地 MCP 服务毫秒级响应", ft.Icons.SPEED, p.success),
                self._feature_card(p, "多端兼容", "覆盖 15+ AI 开发工具", ft.Icons.EXTENSION, p.accent_warm),
                self._feature_card(p, "设计还原", "高还原开发全链路支持", ft.Icons.DESIGN_SERVICES, p.accent),
            ],
            spacing=theme.space("4"),
            wrap=True,
        )

        # ── 底部信息 ─────────────────────────────────────────────
        footer = ft.Container(
            content=ft.Row([
                ft.Text("Lanhu MCP Server", size=theme.font_size("sm"), color=p.text_muted),
                ft.Container(expand=True),
                ft.Text(f"端口: {self.ctx.port}", size=theme.font_size("sm"), color=p.text_muted),
            ]),
            padding=ft.padding.only(top=theme.space("6")),
        )

        # ── 组装内容 (用 ListView 实现滚动) ─────────────────────
        scroll_content = ft.ListView(
            controls=[
                welcome_banner,
                ft.Container(height=theme.space("4")),
                stat_section,
                ft.Container(height=theme.space("4")),
                metrics_section,
                ft.Divider(height=1, color=p.border_light),
                self._two_col_row(quick_actions_section, timeline_card, p),
                ft.Container(height=theme.space("2")),
                self._two_col_row(tools_card, ide_card, p),
                ft.Container(height=theme.space("4")),
                ft.Text("核心能力", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Container(height=theme.space("2")),
                features_row,
                footer,
                ft.Container(height=theme.space("4")),
            ],
            spacing=theme.space("4"),
            padding=ft.padding.symmetric(horizontal=theme.space("6"), vertical=theme.space("4")),
            expand=True,
        )

        return ft.Container(
            content=scroll_content,
            bgcolor=p.bg,
            expand=True,
        )

    def _feature_card(self, p: Palette, title: str, desc: str, icon: str, accent: str) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Icon(icon, color=accent, size=24),
                    bgcolor=accent + "15",
                    border_radius=theme.radius("lg"),
                    padding=theme.space("3"),
                    width=48,
                    height=48,
                    alignment=ft.alignment.center,
                ),
                ft.Text(title, size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Text(desc, size=theme.font_size("sm"), color=p.text_muted),
            ], spacing=theme.space("2")),
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("5"),
            expand=True,
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=4, color=p.shadow_sm,
                offset=ft.Offset(0, 2),
            ),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    def _goto(self, target: str) -> None:
        if self.ctx.navigate:
            self.ctx.navigate(target)


__all__ = ["OverviewPage"]
