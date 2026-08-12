"""Projects page — paginated grid with rich project cards."""

from __future__ import annotations

import math
from typing import List
from urllib.parse import urlencode

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge,
    primary_button, secondary_button, ghost_icon_button,
    toast, page_banner,
)
from ..state import AppContext
from .designs import DesignBrowser
from ...core import accounts as accounts_core
from ...core import projects as projects_core
from ...services.lanhu_api import load_projects_for_account

PAGE_SIZE = 10


class ProjectsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        # Keep one vertical scroll owner (the page ListView). The project
        # cards themselves are a tight ResponsiveRow so the grid never claims
        # a second viewport and leaves a blank block above the content.
        self._grid = ft.ResponsiveRow(
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=theme.space("4"),
            run_spacing=theme.space("4"),
        )
        self._stat_bar = ft.ResponsiveRow(
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=theme.space("3"),
            run_spacing=theme.space("3"),
        )
        self._page_text = ft.Text("", size=theme.font_size("sm"), color=lambda: self.ctx.palette.text_muted)
        self._busy = False
        self._all_projects: list[dict] = []
        self._current_page = 1
        self._design_browser = DesignBrowser(ctx)
        self._auto_loaded_account_id = ""
        self._status_text = ft.Text("", size=theme.font_size("xs"))
        self._search_field = ft.TextField(
            hint_text="搜索项目、团队或负责人",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            width=280,
            on_change=self._on_search_change,
        )

    # ── stats ─────────────────────────────────────────────────────
        self._team_filter = ft.Dropdown(
            label="团队", value="__all__", width=148, dense=True,
            options=[ft.DropdownOption("__all__", "全部团队")],
            on_change=self._on_filter_change,
        )
        self._type_filter = ft.Dropdown(
            label="类型", value="__all__", width=132, dense=True,
            options=[ft.DropdownOption("__all__", "全部类型")],
            on_change=self._on_filter_change,
        )
        self._sort_field = ft.Dropdown(
            label="排序", value="updated_desc", width=148, dense=True,
            options=[
                ft.DropdownOption("updated_desc", "最近更新"),
                ft.DropdownOption("name_asc", "名称 A-Z"),
                ft.DropdownOption("team_asc", "团队名称"),
            ],
            on_change=self._on_filter_change,
        )

    def _on_unmount(self) -> None:
        """Release thumbnail workers and image references when leaving page."""
        self._design_browser._close()

    def _close_design_browser(self) -> None:
        self._design_browser._close()

    def _project_stat_tile(
        self,
        p,
        label: str,
        value: str,
        sub: str,
        icon: str,
        accent: str,
    ) -> ft.Container:
        """Build a compact metric tile matching the reference dashboard."""
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon, size=20, color=accent),
                    bgcolor=theme.alpha(accent, 0x18),
                    border_radius=theme.radius("lg"),
                    width=42,
                    height=42,
                    alignment=ft.alignment.center,
                ),
                ft.Column([
                    ft.Text(label, size=theme.font_size("xs"), color=p.text_muted),
                    ft.Text(value, size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
                    ft.Text(sub, size=theme.font_size("xs"), color=p.text_muted, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=0, expand=True),
            ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("3"),
        )

    def _render_stats(self, projects: list[dict]) -> None:
        p = self.ctx.palette
        team_ids = set(pr.get("team_id", "") for pr in projects if pr.get("team_id"))
        api_count = sum(1 for pr in projects if pr.get("source", "").lower() in ("api", "蓝湖接口"))
        manual_count = max(0, len(projects) - api_count)
        self._stat_bar.controls = [
            ft.Container(
                content=self._project_stat_tile(p, "全部项目", str(len(projects)), "已保存的蓝湖项目", ft.Icons.FOLDER_OUTLINED, p.primary),
                col={"sm": 12, "md": 6, "lg": 3, "xl": 3},
            ),
            ft.Container(
                content=self._project_stat_tile(p, "关联团队", str(len(team_ids)), "按团队归类", ft.Icons.GROUPS_OUTLINED, p.accent),
                col={"sm": 12, "md": 6, "lg": 3, "xl": 3},
            ),
            ft.Container(
                content=self._project_stat_tile(p, "蓝湖接口", str(api_count), "接口同步项目", ft.Icons.CLOUD_OUTLINED, p.success),
                col={"sm": 12, "md": 6, "lg": 3, "xl": 3},
            ),
            ft.Container(
                content=self._project_stat_tile(p, "本地链接", str(manual_count), "登录缓存或手动添加", ft.Icons.LINK, p.accent_warm),
                col={"sm": 12, "md": 6, "lg": 3, "xl": 3},
            ),
        ]

    # ── pagination ────────────────────────────────────────────────
    def _total_pages(self) -> int:
        return max(1, math.ceil(len(self._filtered_projects()) / PAGE_SIZE))

    def _page_projects(self) -> list[dict]:
        start = (self._current_page - 1) * PAGE_SIZE
        return self._filtered_projects()[start: start + PAGE_SIZE]

    def _sync_filter_options(self) -> None:
        """Refresh classification options after a new account payload arrives."""
        teams = sorted({str(item.get("team_name") or item.get("team_id") or "").strip() for item in self._all_projects if str(item.get("team_name") or item.get("team_id") or "").strip()})
        types = sorted({str(item.get("type") or "项目").strip() for item in self._all_projects if str(item.get("type") or "项目").strip()})
        current_team = self._team_filter.value or "__all__"
        current_type = self._type_filter.value or "__all__"
        self._team_filter.options = [ft.DropdownOption("__all__", "全部团队")] + [ft.DropdownOption(value, value) for value in teams]
        self._type_filter.options = [ft.DropdownOption("__all__", "全部类型")] + [ft.DropdownOption(value, value) for value in types]
        self._team_filter.value = current_team if current_team in {"__all__", *teams} else "__all__"
        self._type_filter.value = current_type if current_type in {"__all__", *types} else "__all__"

    def _on_filter_change(self, _event: ft.ControlEvent) -> None:
        self._current_page = 1
        self._render_grid()
        self._render_page_controls()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    def _filtered_projects(self) -> list[dict]:
        query = str(self._search_field.value or "").strip().lower()
        team = str(self._team_filter.value or "__all__")
        project_type = str(self._type_filter.value or "__all__")
        items = list(self._all_projects)
        if query:
            items = [
                project for project in items
                if query in " ".join(str(project.get(field) or "") for field in ("name", "team_name", "team_id", "owner_name", "id")).lower()
            ]
        if team != "__all__":
            items = [project for project in items if str(project.get("team_name") or project.get("team_id") or "") == team]
        if project_type != "__all__":
            items = [project for project in items if str(project.get("type") or "项目") == project_type]
        sort_mode = str(self._sort_field.value or "updated_desc")
        if sort_mode == "name_asc":
            items.sort(key=lambda project: str(project.get("name") or "").casefold())
        elif sort_mode == "team_asc":
            items.sort(key=lambda project: (str(project.get("team_name") or project.get("team_id") or "").casefold(), str(project.get("name") or "").casefold()))
        else:
            items.sort(key=lambda project: str(project.get("updated_at") or project.get("created_at") or ""), reverse=True)
        return items
    def _on_search_change(self, _event: ft.ControlEvent) -> None:
        self._current_page = 1
        self._render_grid()
        self._render_page_controls()
        try:
            self.ctx.page.update()
        except Exception:
            pass

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
                        ft.Row([
                            primary_button("刷新项目", lambda e: self._refresh_projects(), icon=ft.Icons.REFRESH),
                            secondary_button("管理账号", lambda e: self.ctx.navigate("accounts") if self.ctx.navigate else None, icon=ft.Icons.PERSON),
                        ], spacing=theme.space("3")),
                    ], spacing=theme.space("3"), horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=theme.space("8"),
                )),
            ]
            self._grid.controls[0].col = {"sm": 12, "md": 12, "lg": 12, "xl": 12}
            return

        cards: List[ft.Control] = []
        for proj in page_projects:
            cards.append(ft.Container(
                content=self._project_card(p, proj),
                col={"sm": 12, "md": 6, "lg": 4, "xl": 3},
            ))
        self._grid.controls = cards

    def _project_card(self, p, proj: dict) -> ft.Container:
        name = proj.get("name") or "未命名项目"
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

        project_icon = ft.Container(
            content=ft.Icon(ft.Icons.FOLDER_OUTLINED, color=proj_color, size=22),
            bgcolor=theme.alpha(proj_color, 0x16),
            border_radius=theme.radius("lg"),
            width=44,
            height=44,
            alignment=ft.alignment.center,
        )

        # Source badge
        badge = StatusBadge(p, source, "ok" if source in ("api", "蓝湖接口") else "idle")

        # Meta info
        meta_items: List[ft.Control] = []
        if team_name or team_id:
            meta_items.append(ft.Row([
                ft.Icon(ft.Icons.GROUPS, size=12, color=p.text_muted),
                ft.Text(team_name or team_id, size=theme.font_size("xs"), color=p.text_muted,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=theme.space("1")))
        if owner_name:
            meta_items.append(ft.Row([
                ft.Icon(ft.Icons.PERSON, size=12, color=p.text_muted),
                ft.Text(owner_name, size=theme.font_size("xs"), color=p.text_muted,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=theme.space("1")))
        if updated_at:
            meta_items.append(ft.Row([
                ft.Icon(ft.Icons.UPDATE, size=12, color=p.text_muted),
                ft.Text(f"更新: {updated_at[:10]}", size=theme.font_size("xs"), color=p.text_muted,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=theme.space("1")))
        elif created_at:
            meta_items.append(ft.Row([
                ft.Icon(ft.Icons.CALENDAR_TODAY, size=12, color=p.text_muted),
                ft.Text(f"创建: {created_at[:10]}", size=theme.font_size("xs"), color=p.text_muted,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=theme.space("1")))

        # Actions
        action_controls: List[ft.Control] = []
        if proj_id:
            action_controls.append(
                ghost_icon_button(ft.Icons.IMAGE_OUTLINED,
                                  lambda e, pid=proj_id, tid=team_id, n=name: self._browse_designs(pid, tid, n),
                                  tooltip="浏览设计稿")
            )
        action_controls.extend([
            ghost_icon_button(ft.Icons.OPEN_IN_NEW,
                              lambda e, u=proj_url: self._open_url(u) if u else None,
                              tooltip="打开项目",
                              disabled=not bool(proj_url)),
            ghost_icon_button(ft.Icons.CONTENT_COPY,
                              lambda e, tid=team_id, pid=proj_id: self._copy_links(tid, pid),
                              tooltip="复制链接",
                              disabled=not bool(team_id or proj_id)),
        ])
        actions = ft.Container(
            content=ft.Row(action_controls, spacing=theme.space("1")),
            bgcolor=p.surface,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("full"),
            padding=ft.padding.symmetric(horizontal=theme.space("2"), vertical=1),
        )

        content = ft.Column([
            ft.Row([
                project_icon,
                ft.Column([
                    ft.Text(name, size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD,
                            color=p.text_primary, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(proj_type, size=theme.font_size("xs"), color=p.text_muted),
                ], spacing=theme.space("1"), expand=True),
                badge,
            ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=1, color=p.border_light),
            ft.Column(meta_items, spacing=theme.space("1")) if meta_items else ft.Text("暂无团队或更新时间信息", size=theme.font_size("xs"), color=p.text_muted),
            ft.Row([ft.Container(expand=True), actions], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=theme.space("3"))

        return ft.Container(
            content=content,
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color=p.shadow_sm, offset=ft.Offset(0, 3)),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            on_click=lambda _event, pid=proj_id, tid=team_id, project_name=name: self._browse_designs(pid, tid, project_name) if pid else None,
            ink=True,
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
        self._sync_filter_options()
        self._render_stats(self._all_projects)
        self._render_grid()
        self._render_page_controls()
        p = self.ctx.palette
        self._status_text.color = p.text_muted
        if not active_id:
            self._status_text.value = "登录后可自动读取当前账号的蓝湖项目。"
        elif self._all_projects:
            self._status_text.value = f"当前显示 {len(self._filtered_projects())} / {len(self._all_projects)} 个项目"
        else:
            self._status_text.value = "正在准备项目数据；也可以添加已有的蓝湖项目链接。"
        try:
            self.ctx.page.update()
        except Exception:
            pass
        if active_id and active and active.get("cookie") and self._auto_loaded_account_id != active_id:
            self._auto_loaded_account_id = active_id
            self._refresh_projects(silent=True)

    # ── actions ───────────────────────────────────────────────────
    def _refresh_projects(self, *, silent: bool = False) -> None:
        if self._busy:
            toast(self.ctx.page, "刷新进行中，请稍候", "info", self.ctx.palette)
            return
        self._busy = True
        self._status_text.value = "正在从蓝湖同步项目，请稍候..."
        self._status_text.color = self.ctx.palette.primary
        self.ctx.add_log("[PROJECTS] 刷新项目列表…")

        def work():
            try:
                active = accounts_core.get_active_account()
            except Exception:
                active = None
            if not active or not active.get("cookie"):
                return False, "请先在账号页完成蓝湖登录。", []
            return load_projects_for_account(active)

        def done(result):
            self._busy = False
            ok, message, projects = result
            self._all_projects = projects or []
            if not self._all_projects:
                active_id = str((accounts_core.get_active_account() or {}).get("id") or "")
                self._all_projects = projects_core.cached_projects_for_account(active_id)
            self._current_page = 1
            self._render_stats(self._all_projects)
            self._render_grid()
            self._render_page_controls()
            self._status_text.value = message
            self._status_text.color = self.ctx.palette.success if ok else self.ctx.palette.warning
            self.ctx.notify_state_change("projects")
            self.ctx.add_log(f"[OK] [PROJECTS] 获取到 {len(self._all_projects)} 个项目")
            self.ctx.page.update()

            if not silent:
                toast(self.ctx.page, message, "ok" if ok else "warn", self.ctx.palette)

        def err(exc):
            self._busy = False
            self._status_text.value = f"项目同步失败: {exc}"
            self._status_text.color = self.ctx.palette.danger
            from ..components import show_error
            show_error(self.ctx.page, exc, "刷新项目", self.ctx.palette, self.ctx.add_log)

        from ..components import run_in_background
        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _add_manual_project(self) -> None:
        p = self.ctx.palette
        url_field = ft.TextField(
            label="蓝湖项目链接",
            hint_text="粘贴包含 tid 和 pid 的蓝湖项目地址",
            autofocus=True,
            min_lines=2,
            max_lines=3,
            multiline=True,
            width=520,
        )

        def close_dialog() -> None:
            try:
                self.ctx.page.close(dialog)
            except Exception:
                dialog.open = False
                self.ctx.page.update()

        def save_project(_event) -> None:
            active = accounts_core.get_active_account() or {}
            account_id = str(active.get("id") or "")
            ok, message, _project = projects_core.save_manual_project(
                str(url_field.value or ""), account_id
            )
            if not ok:
                toast(self.ctx.page, message, "warn", p)
                return
            close_dialog()
            self.refresh()
            toast(self.ctx.page, message, "ok", p)

        dialog = ft.AlertDialog(
            title=ft.Text("添加项目链接", color=p.text_primary),
            content=url_field,
            actions=[
                ft.TextButton("取消", on_click=lambda _event: close_dialog()),
                ft.FilledButton("保存项目", icon=ft.Icons.ADD_LINK, on_click=save_project),
            ],
        )
        self.ctx.page.open(dialog)

    def _open_url(self, url: str) -> None:
        import webbrowser
        webbrowser.open(url)

    def _browse_designs(self, project_id: str, team_id: str, project_name: str) -> None:
        self._design_browser.open_for(project_id, team_id, project_name)

    def _copy_links(self, team_id: str, project_id: str) -> None:
        p = self.ctx.palette
        try:
            lines = []
            if team_id:
                lines.append(f"Team: https://lanhuapp.com/web/#/team/{team_id}")
            if project_id:
                query = {"pid": project_id}
                if team_id:
                    query["tid"] = team_id
                lines.append(
                    "Project: https://lanhuapp.com/web/#/item/project/stage?"
                    + urlencode(query)
                )
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
        self._sync_filter_options()
        self._render_stats(self._all_projects)
        self._render_grid()
        self._render_page_controls()

        header = ft.Container(
            content=page_banner(p, "项目", "管理和浏览已连接的蓝湖项目，快速访问设计资源与文档", "projects"),
            bgcolor=p.card,
        )

        # Pagination bar
        pagination_bar = ft.Row([
            secondary_button("上一页", lambda e: self._prev_page(), icon=ft.Icons.CHEVRON_LEFT),
            self._page_text,
            secondary_button("下一页", lambda e: self._next_page(), icon=ft.Icons.CHEVRON_RIGHT),
        ], spacing=theme.space("3"), alignment=ft.MainAxisAlignment.CENTER)

        tip_card = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.AUTO_AWESOME, size=20, color=p.accent),
                ft.Text("项目卡片支持打开蓝湖、复制项目链接、浏览设计稿并生成还原提示词。",
                        size=theme.font_size("sm"), color=p.text_secondary, expand=True),
            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=p.accent_light,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
        )

        self._search_field.border_color = p.border
        self._search_field.focused_border_color = p.primary
        self._search_field.color = p.text_primary
        self._search_field.bgcolor = p.card
        for field in (self._team_filter, self._type_filter, self._sort_field):
            field.border_color = p.border
            field.focused_border_color = p.primary
            field.color = p.text_primary
            field.bgcolor = p.card
        toolbar_controls = ft.Row([
            self._search_field,
            self._team_filter,
            self._type_filter,
            self._sort_field,
            secondary_button("添加项目链接", lambda _event: self._add_manual_project(), icon=ft.Icons.ADD_LINK),
            primary_button("同步项目", lambda _event: self._refresh_projects(), icon=ft.Icons.REFRESH),
        ], spacing=theme.space("3"), wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        toolbar_meta = ft.Row([
            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=p.primary),
            self._status_text,
            ft.Container(expand=True),
            pagination_bar,
        ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER)
        toolbar = ft.Container(
            content=ft.Column([toolbar_controls, toolbar_meta], spacing=theme.space("2"), tight=True),
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
        )

        body = ft.Column([
            toolbar,
            gradient_card(p, self._stat_bar, padding=theme.space("4")),
            tip_card,
            self._grid,
        ], spacing=theme.space("4"), tight=True)
        view = ft.ListView(
            controls=[
                header,
                ft.Container(
                    content=body,
                    bgcolor=p.card,
                    padding=ft.padding.only(
                        left=theme.space("6"), top=theme.space("1"),
                        right=theme.space("6"), bottom=theme.space("6"),
                    ),
                ),
            ],
            spacing=0,
            expand=True,
        )
        # Keep the page itself on the same white workspace surface as the
        # shell.  The cards provide the subtle borders/shadows; the old gray
        # ListView background made the area above the project grid look empty.
        view.bgcolor = p.card
        return view


__all__ = ["ProjectsPage"]
