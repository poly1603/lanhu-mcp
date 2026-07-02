"""Projects page — paginated grid with rich project cards."""

from __future__ import annotations

import math
import time
from typing import List, Optional

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

PAGE_SIZE = 10


class ProjectsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._grid = ft.GridView(
            runs_count=2, max_extent=480, child_aspect_ratio=2.0,
            spacing=theme.space("4"), run_spacing=theme.space("4"),
        )
        self._stat_bar = ft.Row(spacing=theme.space("4"), wrap=True)
        self._page_text = ft.Text("", size=theme.font_size("sm"), color=lambda: self.ctx.palette.text_muted)
        self._busy = False
        self._all_projects: list[dict] = []
        self._current_page = 1

    # ── stats ─────────────────────────────────────────────────────
    def _render_stats(self, projects: list[dict]) -> None:
        p = self.ctx.palette
        team_ids = set(pr.get("team_id", "") for pr in projects if pr.get("team_id"))
        api_count = sum(1 for pr in projects if pr.get("source", "").lower() in ("api", "蓝湖接口"))
        self._stat_bar.controls = [
            stat_chip(p, "项目总数", str(len(projects)), icon=ft.Icons.FOLDER, accent=p.accent),
            stat_chip(p, "关联团队", str(len(team_ids)), icon=ft.Icons.GROUPS, accent=p.primary),
            stat_chip(p, "API 数据", str(api_count), icon=ft.Icons.CLOUD, accent=p.success),
        ]

    # ── pagination ────────────────────────────────────────────────
    def _total_pages(self) -> int:
        return max(1, math.ceil(len(self._all_projects) / PAGE_SIZE))

    def _page_projects(self) -> list[dict]:
        start = (self._current_page - 1) * PAGE_SIZE
        return self._all_projects[start: start + PAGE_SIZE]

    def _render_page_controls(self) -> None:
        p = self.ctx.palette
        total = self._total_pages()
        self._page_text.value = f"第 {self._current_page} / {total} 页"

    def _prev_page(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self._render_grid()
            self._render_page_controls()
            try:
                self.ctx.page.update()
            except Exception:
                pass

    def _next_page(self) -> None:
        if self._current_page < self._total_pages():
            self._current_page += 1
            self._render_grid()
            self._render_page_controls()
            try:
                self.ctx.page.update()
            except Exception:
                pass

    # ── project grid ─────────────────────────────────────────────
    def _render_grid(self) -> None:
        p = self.ctx.palette
        page_projects = self._page_projects()

        if not page_projects:
            self._grid.controls = [
                card(p, ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.FOLDER_OPEN, size=48, color=p.text_muted),
                        ft.Text("暂无项目", size=theme.font_size("lg"), weight=theme.WEIGHT_MEDIUM, color=p.text_secondary),
                        ft.Text("登录蓝湖账号后刷新项目列表", size=theme.font_size("sm"), color=p.text_muted),
                    ], spacing=theme.space("2"), horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=theme.space("8"),
                )),
            ]
            return

        cards: List[ft.Control] = []
        for proj in page_projects:
            cards.append(self._project_card(p, proj))
        self._grid.controls = cards

    def _project_card(self, p, proj: dict) -> ft.Container:
        name = proj.get("name", "未命名项目")
        source = proj.get("source", "")
        proj_type = proj.get("type", "项目")
        team_id = proj.get("team_id", "")
        team_name = proj.get("team_name", "")
        owner_name = proj.get("owner_name", "")
        updated_at = proj.get("updated_at", "")
        created_at = proj.get("created_at", "")
        proj_url = proj.get("url", "")
        proj_id = proj.get("id", "")
        proj_color = proj.get("color") or self._color_for(name)

        # Cover area with gradient
        cover = ft.Container(
            content=ft.Text(name[:1].upper() or "P", color="#FFFFFF", size=28, weight=theme.WEIGHT_BOLD),
            height=64,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left, end=ft.alignment.bottom_right,
                colors=[proj_color, proj_color + "AA"],
            ),
            alignment=ft.alignment.center,
            border_radius=theme.radius("xl"),
        )

        # Source badge
        badge = StatusBadge(p, source, "ok" if source in ("api", "蓝湖接口") else "idle")

        # Meta info
        meta_items: List[ft.Control] = []
        if team_name or team_id:
            meta_items.append(ft.Row([
                ft.Icon(ft.Icons.GROUPS, size=12, color=p.text_muted),
                ft.Text(team_name or team_id, size=theme.font_size("xs"), color=p.text_muted),
            ], spacing=theme.space("1")))
        if owner_name:
            meta_items.append(ft.Row([
                ft.Icon(ft.Icons.PERSON, size=12, color=p.text_muted),
                ft.Text(owner_name, size=theme.font_size("xs"), color=p.text_muted),
            ], spacing=theme.space("1")))
        if updated_at:
            meta_items.append(ft.Row([
                ft.Icon(ft.Icons.UPDATE, size=12, color=p.text_muted),
                ft.Text(f"更新: {updated_at[:10]}", size=theme.font_size("xs"), color=p.text_muted),
            ], spacing=theme.space("1")))
        if created_at:
            meta_items.append(ft.Row([
                ft.Icon(ft.Icons.CALENDAR_TODAY, size=12, color=p.text_muted),
                ft.Text(f"创建: {created_at[:10]}", size=theme.font_size("xs"), color=p.text_muted),
            ], spacing=theme.space("1")))

        # Actions
        actions = ft.Row([
            ghost_icon_button(ft.Icons.OPEN_IN_NEW,
                              lambda e, u=proj_url: self._open_url(u) if u else None,
                              tooltip="打开项目"),
            ghost_icon_button(ft.Icons.CONTENT_COPY,
                              lambda e, tid=team_id, pid=proj_id: self._copy_links(tid, pid),
                              tooltip="复制链接"),
        ], spacing=theme.space("1"))

        content = ft.Column([
            cover,
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(name, size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD,
                                color=p.text_primary, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        badge,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(proj_type, size=theme.font_size("xs"), color=p.accent),
                    ft.Column(meta_items, spacing=theme.space("1")) if meta_items else ft.Container(),
                    ft.Divider(height=1, color=p.border_light),
                    ft.Row([ft.Container(expand=True), actions], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], spacing=theme.space("2")),
                padding=ft.padding.only(left=theme.space("4"), right=theme.space("4"), bottom=theme.space("4")),
            ),
        ], spacing=0)

        return ft.Container(
            content=content,
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=4, color=p.shadow_sm, offset=ft.Offset(0, 2)),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    @staticmethod
    def _color_for(name: str) -> str:
        colors = ["#0052D9", "#00A870", "#ED7B2F", "#E34D59", "#7B61FF", "#00809A", "#F59D0A", "#4A8DF7"]
        return colors[hash(name) % len(colors)]

    # ── lifecycle ─────────────────────────────────────────────────
    def refresh(self) -> None:
        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        active_id = (active or {}).get("id", "") if active else ""

        if not active_id:
            self._all_projects = []
        else:
            self._all_projects = projects_core.cached_projects_for_account(active_id)

        self._current_page = 1
        self._render_stats(self._all_projects)
        self._render_grid()
        self._render_page_controls()
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
            time.sleep(0.3)
            return active_id

        def done(active_id: str):
            self._busy = False
            self._all_projects = projects_core.cached_projects_for_account(active_id or "")
            self._current_page = 1
            self._render_stats(self._all_projects)
            self._render_grid()
            self._render_page_controls()
            self.ctx.add_log(f"[OK] [PROJECTS] 获取到 {len(self._all_projects)} 个项目")
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

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette

        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        active_id = (active or {}).get("id", "") if active else ""
        self._all_projects = projects_core.cached_projects_for_account(active_id)
        self._current_page = 1
        self._render_stats(self._all_projects)
        self._render_grid()
        self._render_page_controls()

        header_card = gradient_card(
            p,
            ft.Row([
                ft.Column([
                    ft.Text("项目管理", size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
                    ft.Text(f"共 {len(self._all_projects)} 个项目", size=theme.font_size("sm"), color=p.text_muted),
                ], spacing=theme.space("1"), expand=True),
                ft.Row([
                    primary_button("刷新项目", lambda e: self._refresh_projects(), icon=ft.Icons.REFRESH),
                ], spacing=theme.space("3")),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # Pagination bar
        pagination_bar = ft.Row([
            secondary_button("上一页", lambda e: self._prev_page(), icon=ft.Icons.CHEVRON_LEFT),
            self._page_text,
            secondary_button("下一页", lambda e: self._next_page(), icon=ft.Icons.CHEVRON_RIGHT),
        ], spacing=theme.space("3"), alignment=ft.MainAxisAlignment.CENTER)

        return ft.ListView(
            controls=[
                ft.Container(
                    content=section_title(p, "项目", "浏览管理关联项目 · 分页加载"),
                    padding=ft.padding.only(left=theme.space("4"), top=theme.space("3"), right=theme.space("4"), bottom=theme.space("3")),
                ),
                ft.Container(
                    content=ft.Column([
                        header_card,
                        gradient_card(p, self._stat_bar, padding=theme.space("4")),
                        self._grid,
                        pagination_bar,
                    ], spacing=theme.space("4")),
                    padding=ft.padding.only(left=theme.space("4"), top=theme.space("1"), right=theme.space("4")),
                ),
            ],
            spacing=0,
            expand=True,
        )


__all__ = ["ProjectsPage"]
