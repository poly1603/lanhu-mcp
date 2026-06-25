"""Overview page — high-level dashboard of account / service / projects / tools."""

from __future__ import annotations

from typing import List

import flet as ft

from .. import theme
from ..components import metric_tile, card, section_title, StatusBadge, primary_button
from ..state import AppContext
from ...core import accounts as accounts_core
from ...core import projects as projects_core
from ...services.tools_registry import discover_mcp_tools


class OverviewPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._metrics_row = ft.Row(wrap=True, spacing=theme.space("4"), run_spacing=theme.space("4"))
        self._status_badge_holder = ft.Row(spacing=theme.space("2"))

    # -- data -----------------------------------------------------------
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
        except Exception:
            ide_installed = 0
        return {
            "accounts": len(account_list),
            "active": active,
            "tools": len(tools),
            "projects": len(project_list),
            "ide_installed": ide_installed,
            "running": self.ctx.service.is_running(),
        }

    def _render_metrics(self, data: dict) -> None:
        p = self.ctx.palette
        running = data["running"]
        active = data["active"]
        account_label = accounts_core.account_primary_contact(active) if active else "未登录"
        tiles: List[ft.Control] = [
            metric_tile(p, "当前账号", account_label or "未登录", icon=ft.Icons.PERSON, accent=p.primary),
            metric_tile(p, "服务状态", "运行中" if running else "已停止", icon=ft.Icons.DNS,
                        accent=p.success if running else p.text_muted),
            metric_tile(p, "MCP 方法", str(data["tools"]), icon=ft.Icons.BUILD, accent=p.accent),
            metric_tile(p, "项目", str(data["projects"]), icon=ft.Icons.FOLDER, accent=p.warning),
            metric_tile(p, "账号数", str(data["accounts"]), icon=ft.Icons.GROUP, accent=p.primary),
            metric_tile(p, "已识别 IDE", str(data["ide_installed"]), icon=ft.Icons.TERMINAL, accent=p.accent_warm),
        ]
        self._metrics_row.controls = tiles
        self._status_badge_holder.controls = [
            StatusBadge(p, "服务运行中" if running else "服务未启动", "ok" if running else "idle"),
            StatusBadge(p, f"端口 {self.ctx.port}", "info"),
        ]

    def refresh(self) -> None:
        self._render_metrics(self._gather())
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # -- view -----------------------------------------------------------
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render_metrics(self._gather())

        quick_actions = ft.Row(
            [
                primary_button("启动服务", lambda e: self._goto("service"), icon=ft.Icons.PLAY_ARROW),
                primary_button("管理账号", lambda e: self._goto("accounts"), icon=ft.Icons.PERSON_ADD),
                primary_button("配置 AI 工具", lambda e: self._goto("ide"), icon=ft.Icons.SETTINGS),
            ],
            spacing=theme.space("3"),
            wrap=True,
        )

        return ft.Column(
            [
                ft.Row(
                    [section_title(p, "总览", "Lanhu MCP 桌面控制台"), ft.Container(expand=True), self._status_badge_holder],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self._metrics_row,
                card(
                    p,
                    ft.Column(
                        [
                            ft.Text("快速操作", size=theme.font_size("lg"),
                                    weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                            quick_actions,
                        ],
                        spacing=theme.space("4"),
                    ),
                ),
            ],
            spacing=theme.space("6"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _goto(self, target: str) -> None:
        if self.ctx.navigate:
            self.ctx.navigate(target)


__all__ = ["OverviewPage"]
