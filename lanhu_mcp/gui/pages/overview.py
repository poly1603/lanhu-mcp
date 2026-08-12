"""Data-first overview dashboard.

The overview intentionally focuses on information that helps answer three
questions quickly: what is available, what has been used, and what happened
recently.  Long explanatory cards belong on the dedicated pages instead.
"""

from __future__ import annotations

import time
from typing import List

import flet as ft

from .. import theme
from ..components import metric_tile, page_frame, stat_chip, timeline_item, primary_button, secondary_button
from ..state import AppContext
from ...core import accounts as accounts_core
from ...core import projects as projects_core
from ...services.tools_registry import discover_mcp_tools

SP = "3"


class OverviewPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._loaded_at = time.strftime("%H:%M:%S")

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

        active_id = str((active or {}).get("id") or "")
        try:
            project_list = projects_core.cached_projects_for_account(active_id)
        except Exception:
            project_list = []
        try:
            recent_projects = projects_core.recent_projects(active_id, limit=5)
        except Exception:
            recent_projects = []

        try:
            ide_map = self.ctx.ide.detect_all()
        except Exception:
            ide_map = {}
        usage = self.ctx.usage_stats()
        return {
            "accounts": len(account_list),
            "active": active,
            "tools": len(tools),
            "projects": len(project_list),
            "recent_projects": recent_projects,
            "ide_installed": sum(1 for value in ide_map.values() if value),
            "ide_total": len(ide_map),
            "running": self.ctx.service.is_running(),
            "account_label": accounts_core.account_primary_contact(active) if active else "未登录",
            "usage": usage,
        }

    @staticmethod
    def _card(palette, content: ft.Control, *, padding: int = 18) -> ft.Container:
        return ft.Container(
            content=content,
            bgcolor=palette.card,
            border=ft.border.all(1, palette.border_light),
            border_radius=theme.radius("xl"),
            padding=padding,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=10,
                color=palette.shadow_sm,
                offset=ft.Offset(0, 4),
            ),
        )

    def _render_stat_bar(self, data: dict) -> ft.Row:
        p = self.ctx.palette
        usage = data["usage"]
        return ft.Row(
            controls=[
                stat_chip(p, "账号", str(data["accounts"]), icon=ft.Icons.PERSON, accent=p.primary),
                stat_chip(p, "AI 工具", str(data["tools"]), icon=ft.Icons.EXTENSION, accent=p.accent),
                stat_chip(p, "项目", str(data["projects"]), icon=ft.Icons.FOLDER, accent=p.warning),
                stat_chip(p, "MCP 调用", str(usage["total_calls"]), icon=ft.Icons.SHOW_CHART, accent=p.success),
                stat_chip(p, "错误", str(usage["error_count"]), icon=ft.Icons.ERROR_OUTLINE, accent=p.danger),
            ],
            spacing=theme.space(SP),
            wrap=True,
        )

    def _render_metrics(self, data: dict) -> ft.Row:
        p = self.ctx.palette
        usage = data["usage"]
        running = data["running"]
        metrics = [
            metric_tile(
                p, "服务状态", "运行中" if running else "已停止",
                icon=ft.Icons.DNS, accent=p.success if running else p.text_muted,
                sub=f"HTTP 端口 {self.ctx.port}" if running else "可从服务页启动",
            ),
            metric_tile(
                p, "AI 工具", str(data["tools"]),
                icon=ft.Icons.EXTENSION, accent=p.accent,
                sub="已扫描到的本机工具",
            ),
            metric_tile(
                p, "MCP 调用", str(usage["total_calls"]),
                icon=ft.Icons.QUERY_STATS, accent=p.primary,
                sub=f"项目记录 {usage['project_events']} 条",
            ),
            metric_tile(
                p, "最近项目", str(data["projects"]),
                icon=ft.Icons.FOLDER_OUTLINED, accent=p.warning,
                sub="当前账号可访问项目",
            ),
            metric_tile(
                p, "已登录账号", str(data["accounts"]),
                icon=ft.Icons.GROUP_OUTLINED, accent=p.primary,
                sub="支持切换多个蓝湖账号",
            ),
            metric_tile(
                p, "已识别 IDE", f"{data['ide_installed']}/{data['ide_total']}",
                icon=ft.Icons.TERMINAL, accent=p.accent_warm,
                sub="本机开发工具检测结果",
            ),
        ]
        # Keep this row independent from ResponsiveRow.  The overview lives
        # inside a ListView and some Flet desktop builds can resolve nested
        # ResponsiveRow controls to zero height before the first update.
        return ft.ResponsiveRow(
            controls=[ft.Container(content=metric, col={"sm": 12, "md": 6, "lg": 3, "xl": 3}) for metric in metrics],
            spacing=theme.space(SP),
            run_spacing=theme.space(SP),
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def _quick_actions(self) -> ft.Container:
        p = self.ctx.palette
        return self._card(p, ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("快速开始", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Text("从这里直接完成常用操作", size=theme.font_size("xs"), color=p.text_muted),
                ], spacing=0),
                ft.Container(expand=True),
                ft.Icon(ft.Icons.ROCKET_LAUNCH_OUTLINED, color=p.primary, size=20),
            ]),
            ft.Row([
                primary_button("启动 MCP 服务", lambda _event: self.ctx.start_service() if self.ctx.start_service else self._goto("service"), icon=ft.Icons.PLAY_ARROW),
                secondary_button("添加新账号", lambda _event: self.ctx.open_login() if self.ctx.open_login else self._goto("accounts"), icon=ft.Icons.PERSON_ADD_ALT_1),
                secondary_button("配置 AI 工具", lambda _event: self._goto("ide"), icon=ft.Icons.EXTENSION),
            ], spacing=theme.space("3"), wrap=True),
        ], spacing=theme.space("3")))

    def _method_chart(self, data: dict) -> ft.Control:
        p = self.ctx.palette
        counts = data["usage"].get("method_counts", [])
        if not counts:
            return ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.INSERT_CHART_OUTLINED, size=32, color=p.text_muted),
                    ft.Text("还没有 MCP 调用记录", color=p.text_muted, size=theme.font_size("sm")),
                    ft.Text("启动服务并从 AI 工具调用方法后，这里会自动统计。", color=p.text_muted, size=theme.font_size("xs")),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=theme.space("2")),
                alignment=ft.alignment.center,
                height=230,
            )

        labels = [name.replace("lanhu_", "")[:12] for name, _count in counts]
        values = [count for _name, count in counts]
        maximum = max(values or [1])
        chart = ft.BarChart(
            bar_groups=[
                ft.BarChartGroup(
                    x=index,
                    bar_rods=[ft.BarChartRod(
                        to_y=count,
                        width=24,
                        color=p.primary,
                        border_radius=5,
                        tooltip=f"{name}: {count}",
                    )],
                )
                for index, ((name, _count), count) in enumerate(zip(counts, values))
            ],
            max_y=max(1, maximum + 1),
            min_y=0,
            height=230,
            interactive=True,
            horizontal_grid_lines=ft.ChartGridLines(interval=1, color=p.border_light, width=1),
            left_axis=ft.ChartAxis(show_labels=True, labels_interval=1, labels_size=28),
            bottom_axis=ft.ChartAxis(
                labels=[
                    ft.ChartAxisLabel(value=index, label=ft.Text(label, size=10, color=p.text_muted))
                    for index, label in enumerate(labels)
                ],
                labels_size=34,
            ),
        )
        return chart

    def _daily_chart(self, data: dict) -> ft.Control:
        p = self.ctx.palette
        daily = data["usage"].get("daily_calls", [])
        if not daily:
            return ft.Text("暂无按日期统计的数据", color=p.text_muted, size=theme.font_size("sm"))
        points = [
            ft.LineChartDataPoint(
                x=index,
                y=count,
                show_tooltip=True,
                tooltip=f"{day}: {count}",
            )
            for index, (day, count) in enumerate(daily)
        ]
        labels = [day[5:] for day, _count in daily]
        return ft.LineChart(
            data_series=[ft.LineChartData(
                data_points=points,
                color=p.primary,
                stroke_width=3,
                curved=True,
                point=True,
                below_line_bgcolor=theme.alpha(p.primary, 0x16),
            )],
            min_y=0,
            max_y=max(1, max(count for _day, count in daily) + 1),
            height=180,
            interactive=True,
            horizontal_grid_lines=ft.ChartGridLines(interval=1, color=p.border_light, width=1),
            left_axis=ft.ChartAxis(show_labels=True, labels_interval=1, labels_size=28),
            bottom_axis=ft.ChartAxis(
                labels=[
                    ft.ChartAxisLabel(value=index, label=ft.Text(label, size=10, color=p.text_muted))
                    for index, label in enumerate(labels)
                ],
                labels_size=28,
            ),
        )

    def _chart_card(self, data: dict) -> ft.Container:
        p = self.ctx.palette
        return self._card(p, ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("最近调用方法", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Text("从持久化日志汇总 MCP tools/call 次数", size=theme.font_size("xs"), color=p.text_muted),
                ], spacing=0, expand=True),
                ft.Icon(ft.Icons.BAR_CHART, color=p.primary, size=20),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self._method_chart(data),
        ], spacing=theme.space("2")))

    def _recent_activity_card(self, data: dict) -> ft.Container:
        p = self.ctx.palette
        events = data["usage"].get("recent_events", [])
        controls: List[ft.Control] = []
        for line in events[:6]:
            kind = "error" if any(marker in line for marker in ("[ERR]", "[ERROR]", "-> ERROR")) else "info"
            controls.append(timeline_item(p, line[:88], time="", kind=kind))
        if not controls:
            controls.append(ft.Text("暂无最近使用记录", color=p.text_muted, size=theme.font_size("sm")))
        return self._card(p, ft.Column([
            ft.Row([
                ft.Text("最近使用记录", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Container(expand=True),
                ft.Text(f"{data['usage']['total_calls']} 次调用", size=theme.font_size("xs"), color=p.text_muted),
            ]),
            ft.Column(controls, spacing=0),
        ], spacing=theme.space("2")))

    def _project_card(self, data: dict) -> ft.Container:
        p = self.ctx.palette
        rows: List[ft.Control] = []
        for project in data.get("recent_projects", [])[:5]:
            name = str(project.get("name") or project.get("title") or "未命名项目")
            updated = str(project.get("updated_at") or project.get("last_used_at") or "")
            rows.append(ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.FOLDER_OUTLINED, color=p.warning, size=18),
                        bgcolor=theme.alpha(p.warning, 0x16), border_radius=theme.radius("md"),
                        width=34, height=34, alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text(name, size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(updated or "最近访问", size=theme.font_size("xs"), color=p.text_muted),
                    ], spacing=0, expand=True),
                ], spacing=theme.space("2")),
                padding=ft.padding.symmetric(vertical=theme.space("1")),
            ))
        if not rows:
            rows.append(ft.Text("暂无最近项目记录", color=p.text_muted, size=theme.font_size("sm")))
        return self._card(p, ft.Column([
            ft.Row([
                ft.Text("最近项目", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Container(expand=True),
                ft.Text(str(data["usage"]["project_events"]) + " 条项目事件", size=theme.font_size("xs"), color=p.text_muted),
            ]),
            ft.Column(rows, spacing=0),
        ], spacing=theme.space("2")))

    def _daily_card(self, data: dict) -> ft.Container:
        p = self.ctx.palette
        usage = data["usage"]
        return self._card(p, ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("最近 7 天调用趋势", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Text(f"账号事件 {usage['account_events']} 条 · 错误 {usage['error_count']} 条", size=theme.font_size("xs"), color=p.text_muted),
                ], spacing=0, expand=True),
                ft.Icon(ft.Icons.TRENDING_UP, color=p.success, size=20),
            ]),
            self._daily_chart(data),
        ], spacing=theme.space("2")))

    def _footer(self, data: dict) -> ft.Row:
        p = self.ctx.palette
        return ft.Row([
            ft.Row([
                ft.Container(width=7, height=7, bgcolor=p.success if data["running"] else p.text_muted, border_radius=7),
                ft.Text("服务运行中" if data["running"] else "服务未启动", size=theme.font_size("xs"), color=p.text_muted),
            ], spacing=theme.space("1")),
            ft.Container(expand=True),
            ft.Text(f"刷新于 {self._loaded_at}", size=theme.font_size("xs"), color=p.text_muted),
        ])

    def refresh(self) -> None:
        # The shell normally rebuilds the active page after state changes. A
        # refresh hook is kept for background service/account updates.
        self._loaded_at = time.strftime("%H:%M:%S")
        try:
            self.ctx.page.update()
        except Exception:
            pass

    def build(self) -> ft.Control:
        p = self.ctx.palette
        data = self._gather()
        self._loaded_at = time.strftime("%H:%M:%S")
        body = ft.Column([
            self._card(p, self._render_stat_bar(data), padding=12),
            self._render_metrics(data),
            self._quick_actions(),
            self._chart_card(data),
            self._recent_activity_card(data),
            self._project_card(data),
            self._daily_card(data),
            self._footer(data),
        ], spacing=theme.space(SP), horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        return page_frame(p, "总览", "查看 MCP 调用、项目活动和本机 AI 工具使用情况", body, banner="overview")

    def _goto(self, target: str) -> None:
        if self.ctx.navigate:
            self.ctx.navigate(target)


__all__ = ["OverviewPage"]
