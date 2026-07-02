"""Projects page — browse and manage Lanhu projects for the active account."""

from __future__ import annotations

import time
from typing import List

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge, CountBadge,
    primary_button, secondary_button, ghost_icon_button,
    stat_chip, toast,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...core import projects as projects_core


class ProjectsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._projects_grid = ft.Column(spacing=theme.space("3"))
        self._stat_bar = ft.Row(spacing=theme.space("4"), wrap=True)
        self._busy = False

    # ── stats ─────────────────────────────────────────────────────
    def _render_stats(self, projects: list[dict]) -> None:
        p = self.ctx.palette
        team_ids = set(pr.get("team_id", "") for pr in projects if pr.get("team_id"))
        total = len(projects)
        self._stat_bar.controls = [
            stat_chip(p, "项目总数", str(total), icon=ft.Icons.FOLDER, accent=p.accent),
            stat_chip(p, "关联团队", str(len(team_ids)), icon=ft.Icons.GROUPS, accent=p.primary),
            stat_chip(p, "数据来源", "API" if total else "—", icon=ft.Icons.CLOUD, accent=p.success),
        ]

    # ── project grid ─────────────────────────────────────────────
    def _render_grid(self, projects: list[dict], show_empty: bool = False) -> None:
        p = self.ctx.palette
        if not projects and show_empty:
            self._projects_grid.controls = [
                card(p, ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.FOLDER_OPEN, size=48, color=p.text_muted),
                        ft.Text("暂无项目", size=theme.font_size("lg"), weight=theme.WEIGHT_MEDIUM, color=p.text_secondary),
                        ft.Text("登录蓝湖账号后可查看关联项目", size=theme.font_size("sm"), color=p.text_muted),
                    ], spacing=theme.space("2"), horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=theme.space("8"),
                )),
            ]
            return

        if not projects:
            return

        cards: List[ft.Control] = []
        for proj in projects:
            source = proj.get("source", "")
            badge = StatusBadge(p, source, "ok" if source == "api" else "idle")
            name = proj.get("name", "未命名项目")
            avatar_widget = ft.Container(
                content=ft.Text(
                    name[:1].upper() or "P",
                    color="#FFFFFF",
                    size=theme.font_size("base"),
                    weight=theme.WEIGHT_BOLD,
                ),
                width=40, height=40,
                bgcolor=proj.get("color") or p.primary,
                border_radius=theme.radius("lg"),
                alignment=ft.alignment.center,
            )

            meta_items: List[ft.Control] = []
            team_id = proj.get("team_id", "")
            if team_id:
                meta_items.append(ft.Row([
                    ft.Icon(ft.Icons.GROUPS, size=14, color=p.text_muted),
                    ft.Text(team_id, size=theme.font_size("xs"), color=p.text_muted),
                ], spacing=theme.space("1")))
            updated_at = proj.get("updated_at", "")
            if updated_at:
                meta_items.append(ft.Row([
                    ft.Icon(ft.Icons.SCHEDULE, size=14, color=p.text_muted),
                    ft.Text(updated_at, size=theme.font_size("xs"), color=p.text_muted),
                ], spacing=theme.space("1")))
            proj_type = proj.get("type", "")
            if proj_type:
                meta_items.append(ft.Row([
                    ft.Icon(ft.Icons.TYPE_SPECIMEN, size=14, color=p.text_muted),
                    ft.Text(proj_type, size=theme.font_size("xs"), color=p.text_muted),
                ], spacing=theme.space("1")))

            proj_url = proj.get("url", "")
            proj_id = proj.get("id", "")
            actions = ft.Row([
                ghost_icon_button(ft.Icons.OPEN_IN_NEW,
                                  lambda e, u=proj_url: self._open_url(u) if u else None,
                                  tooltip="打开项目"),
                ghost_icon_button(ft.Icons.CONTENT_COPY,
                                  lambda e, tid=team_id, pid=proj_id: self._copy_links(tid, pid),
                                  tooltip="复制链接"),
            ], spacing=theme.space("1"))

            card_content = ft.Row([
                avatar_widget,
                ft.Column([
                    ft.Row([
                        ft.Text(name, weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary, expand=True),
                        badge,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Column(meta_items, spacing=theme.space("1")) if meta_items else ft.Container(),
                ], spacing=theme.space("2"), expand=True),
                actions,
            ], spacing=theme.space("4"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

            cards.append(card(p, card_content))

        self._projects_grid.controls = cards

    # ── lifecycle ─────────────────────────────────────────────────
    def refresh(self) -> None:
        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        active_id = (active or {}).get("id", "") if active else ""

        if not active_id:
            self._render_stats([])
            self._render_grid([], show_empty=True)
        else:
            projects = projects_core.cached_projects_for_account(active_id)
            self._render_stats(projects)
            self._render_grid(projects, show_empty=True)
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # ── actions ───────────────────────────────────────────────────
    def _refresh_projects(self) -> None:
        if self._busy:
            toast(self.ctx.page, "刷新进行中，请稍候", "info", self.ctx.palette)
            return
        self._busy = True
        self.ctx.add_log("[PROJECTS] 刷新项目列表…")

        def work():
            try:
                active = accounts_core.get_active_account()
            except Exception:
                active = None
            active_id = (active or {}).get("id", "") if active else ""
            # Re-read from cache (network refresh handled by server)
            time.sleep(0.3)
            return active_id

        def done(active_id: str):
            self._busy = False
            projects = projects_core.cached_projects_for_account(active_id or "")
            self._render_stats(projects)
            self._render_grid(projects, show_empty=True)
            self.ctx.add_log(f"[OK] [PROJECTS] 获取到 {len(projects)} 个项目")
            self.ctx.page.update()

        def err(exc):
            self._busy = False
            from ..components import show_error
            show_error(self.ctx.page, exc, "刷新项目", self.ctx.palette, self.ctx.add_log)

        from ..components import run_in_background
        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _open_url(self, url: str) -> None:
        import webbrowser
        webbrowser.open(url)

    def _copy_links(self, team_id: str, project_id: str) -> None:
        p = self.ctx.palette
        try:
            lines = []
            if team_id:
                lines.append(f"Team: https://lanhuapp.com/web/#/team/{team_id}")
            if project_id:
                lines.append(f"Project: https://lanhuapp.com/web/#/project/{project_id}")
            text = "\n".join(lines)
            self.ctx.page.set_clipboard(text)
            toast(self.ctx.page, "项目链接已复制", "ok", p)
        except Exception:
            toast(self.ctx.page, "复制失败", "error", p)

    def _copy_project_url(self) -> None:
        p = self.ctx.palette
        try:
            active = accounts_core.get_active_account()
            active_id = (active or {}).get("id", "") if active else ""
            projects = projects_core.cached_projects_for_account(active_id or "")
            if not projects:
                toast(self.ctx.page, "暂无项目可复制", "warn", p)
                return
            links = []
            for proj in projects:
                url = proj.get("url", "")
                name = proj.get("name", "未命名")
                team_id = proj.get("team_id", "")
                proj_id = proj.get("id", "")
                if url:
                    links.append(f"{name}: {url}")
                elif team_id or proj_id:
                    parts = []
                    if team_id:
                        parts.append(f"https://lanhuapp.com/web/#/team/{team_id}")
                    if proj_id:
                        parts.append(f"https://lanhuapp.com/web/#/project/{proj_id}")
                    links.append(f"{name}: {' → '.join(parts)}")
            if links:
                self.ctx.page.set_clipboard("\n".join(links))
                toast(self.ctx.page, "项目链接已复制", "ok", p)
            else:
                toast(self.ctx.page, "暂无项目可复制", "warn", p)
        except Exception:
            toast(self.ctx.page, "复制失败", "error", p)

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette

        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        active_id = (active or {}).get("id", "") if active else ""
        projects = projects_core.cached_projects_for_account(active_id)
        self._render_stats(projects)
        self._render_grid(projects, show_empty=True)

        header_card = gradient_card(
            p,
            ft.Row([
                ft.Column([
                    ft.Text("项目管理", size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
                    ft.Text(f"共 {len(projects)} 个项目", size=theme.font_size("sm"), color=p.text_muted),
                ], spacing=theme.space("1"), expand=True),
                ft.Row([
                    primary_button("刷新项目", lambda e: self._refresh_projects(), icon=ft.Icons.REFRESH),
                    secondary_button("复制项目链接", lambda e: self._copy_project_url(), icon=ft.Icons.CONTENT_COPY),
                ], spacing=theme.space("3")),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        return ft.ListView(
            controls=[
                ft.Container(
                    content=section_title(p, "项目", "浏览管理关联项目 · API 与本地链接聚合"),
                    padding=ft.padding.symmetric(horizontal=theme.space("6"), vertical=theme.space("4")),
                ),
                ft.Container(
                    content=ft.Column([
                        header_card,
                        gradient_card(p, self._stat_bar, padding=theme.space("4")),
                        self._projects_grid,
                    ], spacing=theme.space("4")),
                    padding=ft.padding.symmetric(horizontal=theme.space("6"), vertical=theme.space("2")),
                ),
            ],
            spacing=0,
            expand=True,
        )


__all__ = ["ProjectsPage"]
