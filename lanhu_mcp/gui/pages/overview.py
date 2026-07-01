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
            "projects": len(project_list),
            "ide_installed": ide_installed,
            "ide_total": ide_total,
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
        recent_logs = self.ctx.get_logs()[-4:]
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

        header = ft.Row(
            [
                section_title(p, "总览", "Lanhu MCP 桌面控制台 · 仪表盘"),
                ft.Container(expand=True),
                self._status_badge_holder,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        stat_section = gradient_card(p, self._stat_bar, padding=theme.space("4"))
        timeline_card = gradient_card(
            p,
            ft.Column([
                ft.Text("最近活动", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Divider(height=1, color=p.border_light),
                self._timeline,
            ], spacing=theme.space("3")),
        )

        return ft.Column(
            [
                header,
                ft.Container(height=theme.space("2")),
                stat_section,
                self._metrics_row,
                timeline_card,
                ft.Text("快捷操作", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                self._build_quick_actions(),
            ],
            spacing=theme.space("6"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _goto(self, target: str) -> None:
        if self.ctx.navigate:
            self.ctx.navigate(target)


__all__ = ["OverviewPage"]
