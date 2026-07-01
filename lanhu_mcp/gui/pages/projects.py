"""Projects page (v2) — enriched with stat summary, filter chips, view toggle."""

from __future__ import annotations

import time
import webbrowser
from typing import Dict, List, Optional, Tuple

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge, CountBadge, stat_chip,
    primary_button, secondary_button, ghost_icon_button, empty_state,
    run_in_background, toast, show_error,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...core import projects as projects_core
from ...services.lanhu_api import load_projects_for_account
from .designs import DesignBrowser


class ProjectsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._list = ft.Column(spacing=theme.space("3"))
        self._recent = ft.Column(spacing=theme.space("2"))
        self._grid = ft.Row(wrap=True, spacing=theme.space("4"), run_spacing=theme.space("4"))
        self._manual_field = ft.TextField(label="项目链接", dense=True, expand=True)
        self._search_field = ft.TextField(
            label="搜索项目", dense=True, expand=True, prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self._apply_filter(do_update=True),
        )
        self._all_projects: List[dict] = []
        self._refreshing = False
        self._refresh_btn_holder = ft.Row(spacing=theme.space("2"))
        self._stat_section = ft.Row(spacing=theme.space("4"), wrap=True)
        self._view_mode = "list"  # "list" | "grid"
        self._design_browser = DesignBrowser(ctx)
        self._list_sig = None
        self._filter: Optional[str] = None  # None=all, "mine", "shared", "recent"

    # ── helpers ───────────────────────────────────────────────────
    def _safe(self, fn, default):
        try:
            return fn()
        except Exception:
            return default

    def _active_id(self) -> str:
        active = self._safe(accounts_core.get_active_account, None)
        return (active or {}).get("id", "") if active else ""

    def _copy(self, text: str) -> None:
        try:
            self.ctx.page.set_clipboard(text)
            toast(self.ctx.page, "已复制", "ok", self.ctx.palette)
        except Exception:
            toast(self.ctx.page, "复制失败", "error", self.ctx.palette)

    def _open(self, url: str, project: Optional[dict] = None) -> None:
        if not url:
            return
        if project:
            self._remember(project)
        try:
            webbrowser.open(url)
        except Exception:
            toast(self.ctx.page, "无法打开链接", "error", self.ctx.palette)

    def _remember(self, project: dict) -> None:
        self._safe(lambda: projects_core.record_recent_project(project, self._active_id()), None)
        self._render_recent()

    def _design(self, pid: str, tid: str, name: str, project: dict) -> None:
        self._remember(project)
        self._design_browser.open_for(pid, tid, name)

    # ── stat ──────────────────────────────────────────────────────
    def _render_stat_section(self) -> None:
        p = self.ctx.palette
        total = len(self._all_projects)
        teams = len({p.get("team_name") or p.get("tid") or "" for p in self._all_projects})
        self._stat_section.controls = [
            stat_chip(p, "全部项目", str(total), icon=ft.Icons.FOLDER, accent=p.primary),
            stat_chip(p, "团队", str(teams), icon=ft.Icons.GROUP, accent=p.accent),
            stat_chip(p, "搜索", ("激活" if self._search_field.value else "无"), icon=ft.Icons.SEARCH, accent=p.warning),
        ]

    # ── recent ────────────────────────────────────────────────────
    def _render_recent(self) -> None:
        p = self.ctx.palette
        items = self._safe(lambda: projects_core.recent_projects(self._active_id(), 6), [])
        if not items:
            self._recent.controls = [
                empty_state(p, "打开或浏览过的项目会出现在这里", icon=ft.Icons.HISTORY)
            ]
            return
        rows: List[ft.Control] = []
        for proj in items:
            name = proj.get("name") or "?"
            url = proj.get("url") or ""
            actions: List[ft.Control] = []
            if url:
                actions.append(
                    ghost_icon_button(ft.Icons.OPEN_IN_NEW, lambda e, u=url, pr=proj: self._open(u, pr), tooltip="打开")
                )
            rows.append(
                ft.Row([
                    ft.Icon(ft.Icons.HISTORY, size=14, color=p.text_muted),
                    ft.Text(name, color=p.text_primary, size=theme.font_size("sm"), expand=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row(actions, spacing=theme.space("1")),
                ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
        self._recent.controls = rows

    # ── list / grid ───────────────────────────────────────────────
    def _list_signature(self, projects: List[dict]) -> str:
        if not projects:
            return "EMPTY"
        parts = ["|".join(str(p.get(k, "")) for k in ("name", "url", "team_name", "id", "tid")) for p in projects]
        return "\n".join(parts)

    def _render_list(self, projects: List[dict]) -> None:
        p = self.ctx.palette
        signature = self._list_signature(projects)
        if signature == self._list_sig and self._list.controls:
            return
        self._list_sig = signature
        if not projects:
            empty_ctrl = empty_state(p, "暂无项目", icon=ft.Icons.FOLDER_OPEN)
            self._list.controls = [empty_ctrl]
            self._grid.controls = [empty_ctrl]
            return
        rows: List[ft.Control] = []
        grid_tiles: List[ft.Control] = []
        for proj in projects:
            name = proj.get("name") or "未命名"
            url = proj.get("url") or ""
            meta_parts = [x for x in [
                proj.get("team_name"), proj.get("owner_name"),
                proj.get("updated_at"), proj.get("source"),
            ] if x]
            meta = "  ·  ".join(str(x) for x in meta_parts)
            proj_id = str(proj.get("id") or proj.get("project_id") or "")
            team_id = str(proj.get("team_id") or proj.get("tid") or "")

            # ── bag of tags ──
            tags: List[ft.Control] = []
            if proj.get("team_name"):
                tags.append(
                    ft.Container(
                        ft.Text(proj["team_name"], size=theme.font_size("xs"), color=p.primary),
                        bgcolor=p.primary_light, border_radius=theme.radius("full"),
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                    )
                )
            if proj.get("owner_name"):
                tags.append(
                    ft.Container(
                        ft.Text(proj["owner_name"], size=theme.font_size("xs"), color=p.accent),
                        bgcolor=p.accent_light, border_radius=theme.radius("full"),
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                    )
                )
            # Actions
            actions: List[ft.Control] = []
            if proj_id:
                actions.append(
                    ghost_icon_button(ft.Icons.IMAGE,
                                      lambda e, pid=proj_id, tid=team_id, nm=name, pr=proj: self._design(pid, tid, nm, pr),
                                      tooltip="浏览设计稿")
                )
            if url:
                actions.append(
                    ghost_icon_button(ft.Icons.OPEN_IN_NEW, lambda e, u=url, pr=proj: self._open(u, pr), tooltip="打开")
                )
                actions.append(
                    ghost_icon_button(ft.Icons.CONTENT_COPY, lambda e, u=url: self._copy(u), tooltip="复制链接")
                )

            # List card
            rows.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.FOLDER, color=p.warning, size=20),
                        ft.Column([
                            ft.Text(name, weight=theme.WEIGHT_MEDIUM, color=p.text_primary),
                            ft.Text(meta, size=theme.font_size("xs"), color=p.text_muted),
                            ft.Row(tags, spacing=theme.space("1")) if tags else ft.Container(),
                        ], spacing=4, expand=True),
                        ft.Row(actions, spacing=theme.space("1")),
                    ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=p.card,
                    border=ft.border.all(1, p.border_light),
                    border_radius=theme.radius("xl"),
                    padding=theme.space("4"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=2, color=p.shadow_sm, offset=ft.Offset(0, 1)),
                )
            )

            # Grid tile
            grid_tiles.append(
                ft.Container(
                    width=260,
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                ft.Icon(ft.Icons.FOLDER, color="#FFFFFF", size=20),
                                bgcolor=p.warning, border_radius=theme.radius("md"),
                                padding=theme.space("2"),
                            ),
                            ft.Container(expand=True),
                            ft.Row(actions, spacing=theme.space("1")),
                        ], spacing=theme.space("2")),
                        ft.Text(name, weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Row(tags, spacing=theme.space("1")) if tags else ft.Container(),
                        ft.Text(meta or " ", size=theme.font_size("xs"), color=p.text_muted, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=theme.space("2")),
                    bgcolor=p.card,
                    border=ft.border.all(1, p.border_light),
                    border_radius=theme.radius("xl"),
                    padding=theme.space("4"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=3, color=p.shadow_sm, offset=ft.Offset(0, 1)),
                    ink=True,
                    on_click=lambda e, pid=proj_id, nm=name, pr=proj: self._on_grid_click(pid, nm, pr),
                )
            )

        self._list.controls = rows
        self._grid.controls = grid_tiles

    def _on_grid_click(self, pid: str, name: str, proj: dict) -> None:
        # In grid mode, expanding with more options (future)
        pass

    def _render_view(self) -> ft.Control:
        if self._view_mode == "grid":
            return self._grid
        return self._list

    # ── filter chips ──────────────────────────────────────────────
    def _apply_filter(self, do_update: bool = False) -> None:
        query = (self._search_field.value or "").strip().lower()
        filtered = self._all_projects
        if query:
            filtered = [p for p in filtered if query in " ".join(
                str(p.get(k, "")) for k in ("name", "url", "team_name", "owner_name")).lower()]
        if self._filter:
            now = time.time()
            if self._filter == "recent":
                filtered = [p for p in filtered if p.get("_recent_since", 0) > now - 86400 * 7]
            elif self._filter == "mine":
                owner = self._safe(lambda: (accounts_core.get_active_account() or {}).get("username"), "")
                filtered = [p for p in filtered if p.get("owner_name") == owner]
            elif self._filter == "shared":
                filtered = [p for p in filtered if p.get("team_name")]
        self._render_list(filtered)
        self._render_stat_section()
        if do_update:
            try:
                self.ctx.page.update()
            except Exception:
                pass

    def _set_filter(self, kind: Optional[str]) -> None:
        self._filter = kind if self._filter != kind else None
        self._apply_filter(do_update=True)

    def _filter_chips(self) -> ft.Control:
        p = self.ctx.palette
        kinds = [
            (None, "全部"),
            ("mine", "我的"),
            ("shared", "团队"),
            ("recent", "最近更新"),
        ]
        chips = []
        for k, label in kinds:
            active = self._filter == k
            chips.append(
                ft.Container(
                    content=ft.Text(label, size=theme.font_size("sm"),
                                    color=p.text_on_primary if active else p.text_secondary),
                    bgcolor=p.primary if active else p.surface,
                    border_radius=theme.radius("full"),
                    padding=ft.padding.symmetric(horizontal=14, vertical=6),
                    on_click=lambda e, kind=k: self._set_filter(kind),
                    ink=True,
                    animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                )
            )
        return ft.Row(chips, spacing=theme.space("2"))

    def _toggle_view(self, e) -> None:
        if self._view_mode == "list":
            self._view_mode = "grid"
        else:
            self._view_mode = "list"
        self._render_list(self._all_projects)
        self._render_stat_section()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # ── refresh ───────────────────────────────────────────────────
    def _render_refresh_button(self) -> None:
        if self._refreshing:
            self._refresh_btn_holder.controls = [
                ft.Row([ft.ProgressRing(width=16, height=16),
                        ft.Text("刷新中…", color=self.ctx.palette.text_secondary)], spacing=theme.space("2"))
            ]
        else:
            self._refresh_btn_holder.controls = [
                secondary_button("刷新项目", lambda e: self._refresh_remote(), icon=ft.Icons.REFRESH)
            ]

    def _set_projects(self, projects: List[dict]) -> None:
        self._all_projects = list(projects or [])
        self._apply_filter()

    def _load_cached(self) -> None:
        projects = self._safe(lambda: projects_core.cached_projects_for_account(self._active_id()), [])
        self._set_projects(projects)

    def refresh(self) -> None:
        self._render_refresh_button()
        self._load_cached()
        self._render_recent()
        self._render_stat_section()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    def _refresh_remote(self) -> None:
        active = self._safe(accounts_core.get_active_account, None)
        if not active:
            toast(self.ctx.page, "请先登录", "warn", self.ctx.palette)
            return
        if self._refreshing:
            return
        self._refreshing = True
        self._render_refresh_button()
        self._apply_filter(do_update=True)

        def work():
            return load_projects_for_account(active)

        def done(result):
            self._refreshing = False
            self._render_refresh_button()
            ok, msg, projects = result if isinstance(result, tuple) and len(result) == 3 else (False, "", [])
            if ok:
                self._set_projects(projects or [])
                self.ctx.add_log(f"项目刷新成功（{len(projects or [])} 个）")
            else:
                self.ctx.add_log(f"项目刷新失败: {msg}")
                toast(self.ctx.page, msg or "失败", "error", self.ctx.palette)
                self._load_cached()

        def err(exc):
            self._refreshing = False
            self._render_refresh_button()
            show_error(self.ctx.page, exc, "项目刷新", self.ctx.palette, self.ctx.add_log)
            self._load_cached()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _save_manual(self) -> None:
        url = (self._manual_field.value or "").strip()
        if not url:
            toast(self.ctx.page, "请输入项目链接", "warn", self.ctx.palette)
            return
        ok, msg, _ = self._safe(lambda: projects_core.save_manual_project(url, self._active_id()), (False, "失败", None))
        toast(self.ctx.page, msg or ("已保存" if ok else "失败"), "ok" if ok else "error", self.ctx.palette)
        if ok:
            self._manual_field.value = ""
            self._load_cached()
            self._render_stat_section()
            self.ctx.page.update()

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render_refresh_button()
        self._load_cached()
        self._render_recent()
        self._render_stat_section()

        manual_card = gradient_card(
            p,
            ft.Column([
                ft.Text("手动添加项目", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Row([self._manual_field, primary_button("保存", lambda e: self._save_manual(), icon=ft.Icons.ADD)],
                       spacing=theme.space("2")),
                ft.Text("接口读取失败或权限不足时，可粘贴蓝湖项目链接作为兜底。",
                        size=theme.font_size("xs"), color=p.text_muted),
            ], spacing=theme.space("3")),
        )

        stats_card = gradient_card(p, self._stat_section, padding=theme.space("4"))

        list_header = ft.Row([
            ft.Text("项目列表", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
            self._filter_chips(),
            ft.Container(expand=True),
            ghost_icon_button(
                ft.Icons.VIEW_MODULE if self._view_mode == "list" else ft.Icons.VIEW_LIST,
                self._toggle_view,
                tooltip="切换视图"
            ),
            self._refresh_btn_holder,
        ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        list_card = card(p, ft.Column([list_header, self._search_field, self._render_view()], spacing=theme.space("3")))

        recent_card = card(
            p,
            ft.Column([
                ft.Text("最近打开", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Divider(height=1, color=p.border_light),
                self._recent,
            ], spacing=theme.space("3")),
        )

        return ft.Column(
            [
                section_title(p, "项目", "查看与管理 · 设计稿浏览"),
                manual_card,
                stats_card,
                recent_card,
                list_card,
            ],
            spacing=theme.space("5"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )


__all__ = ["ProjectsPage"]
