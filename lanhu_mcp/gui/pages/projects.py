"""Projects page — list, refresh, open, copy link, add manual project."""

from __future__ import annotations

import webbrowser
from typing import List

import flet as ft

from .. import theme
from ..components import (
    section_title,
    card,
    primary_button,
    secondary_button,
    ghost_icon_button,
    empty_state,
    run_in_background,
    toast,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...core import projects as projects_core
from ...services.lanhu_api import load_projects_for_account
from .designs import DesignBrowser


class ProjectsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._list = ft.Column(spacing=theme.space("2"))
        self._manual_field = ft.TextField(label="项目链接", dense=True, expand=True)
        self._refreshing = False
        self._refresh_btn_holder = ft.Row(spacing=theme.space("2"))
        self._design_browser = DesignBrowser(ctx)
        # Signature of the last rendered list; skip rebuild when unchanged.
        self._list_sig = None

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
            toast(self.ctx.page, "已复制项目链接", "ok", self.ctx.palette)
        except Exception:
            toast(self.ctx.page, "复制失败", "error", self.ctx.palette)

    def _open(self, url: str) -> None:
        if not url:
            return
        try:
            webbrowser.open(url)
        except Exception:
            toast(self.ctx.page, "无法打开链接", "error", self.ctx.palette)

    def _list_signature(self, projects: List[dict]) -> str:
        """Visible-field fingerprint; raw/internal keys are ignored."""
        if not projects:
            return "EMPTY"
        parts: List[str] = []
        for proj in projects:
            parts.append("|".join(str(proj.get(k, "")) for k in (
                "name", "url", "team_name", "owner_name", "updated_at",
                "source", "id", "project_id", "team_id", "tid",
            )))
        return "\n".join(parts)

    def _render_list(self, projects: List[dict]) -> None:
        p = self.ctx.palette
        signature = self._list_signature(projects)
        if signature == self._list_sig and self._list.controls:
            return  # nothing visible changed; avoid widget churn
        self._list_sig = signature
        if not projects:
            self._list.controls = [
                empty_state(p, "暂无项目，可刷新或手动添加项目链接", icon=ft.Icons.FOLDER_OPEN)
            ]
            return
        rows: List[ft.Control] = []
        for proj in projects:
            name = proj.get("name") or "未命名项目"
            url = proj.get("url") or ""
            meta_parts = [
                x for x in [proj.get("team_name"), proj.get("owner_name"),
                            proj.get("updated_at"), proj.get("source")] if x
            ]
            meta = "  ·  ".join(str(x) for x in meta_parts)
            actions: List[ft.Control] = []
            proj_id = str(proj.get("id") or proj.get("project_id") or "")
            team_id = str(proj.get("team_id") or proj.get("tid") or "")
            if proj_id:
                actions.append(ghost_icon_button(
                    ft.Icons.IMAGE,
                    lambda e, pid=proj_id, tid=team_id, nm=name: self._design_browser.open_for(pid, tid, nm),
                    tooltip="浏览设计稿"))
            if url:
                actions.append(ghost_icon_button(ft.Icons.OPEN_IN_NEW, lambda e, u=url: self._open(u),
                                                  tooltip="打开项目"))
                actions.append(ghost_icon_button(ft.Icons.CONTENT_COPY, lambda e, u=url: self._copy(u),
                                                  tooltip="复制链接"))
            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.FOLDER, color=p.warning),
                            ft.Column(
                                [
                                    ft.Text(name, weight=theme.WEIGHT_MEDIUM, color=p.text_primary),
                                    ft.Text(meta or f"项目 ID: {proj.get('id', '')}",
                                            size=theme.font_size("xs"), color=p.text_muted),
                                ],
                                spacing=2, expand=True,
                            ),
                            ft.Row(actions, spacing=theme.space("1")),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=theme.space("3"),
                    ),
                    bgcolor=p.surface,
                    border=ft.border.all(1, p.border_light),
                    border_radius=theme.radius("md"),
                    padding=theme.space("3"),
                )
            )
        self._list.controls = rows

    def _render_refresh_button(self) -> None:
        if self._refreshing:
            self._refresh_btn_holder.controls = [
                ft.Row([ft.ProgressRing(width=16, height=16),
                        ft.Text("刷新中…", color=self.ctx.palette.text_secondary)],
                       spacing=theme.space("2"))
            ]
        else:
            self._refresh_btn_holder.controls = [
                secondary_button("刷新项目", lambda e: self._refresh_remote(), icon=ft.Icons.REFRESH)
            ]

    def _load_cached(self) -> None:
        projects = self._safe(lambda: projects_core.cached_projects_for_account(self._active_id()), [])
        self._render_list(projects)

    def refresh(self) -> None:
        self._render_refresh_button()
        self._load_cached()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # -- actions --------------------------------------------------------
    def _refresh_remote(self) -> None:
        active = self._safe(accounts_core.get_active_account, None)
        if not active:
            toast(self.ctx.page, "请先登录账号", "warn", self.ctx.palette)
            return
        if self._refreshing:
            return
        self._refreshing = True
        self._render_refresh_button()
        try:
            self.ctx.page.update()
        except Exception:
            pass

        def work():
            return load_projects_for_account(active)

        def done(result):
            self._refreshing = False
            self._render_refresh_button()
            ok, msg, projects = result if isinstance(result, tuple) and len(result) == 3 else (False, "", [])
            if ok:
                self._render_list(projects or [])
                self.ctx.add_log(f"项目刷新成功，共 {len(projects or [])} 个")
            else:
                self.ctx.add_log(f"项目刷新失败: {msg}")
                toast(self.ctx.page, msg or "项目刷新失败", "error", self.ctx.palette)
                self._load_cached()

        def err(exc):
            self._refreshing = False
            self._render_refresh_button()
            self.ctx.add_log(f"项目刷新异常: {exc}")

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _save_manual(self) -> None:
        url = (self._manual_field.value or "").strip()
        if not url:
            toast(self.ctx.page, "请输入项目链接", "warn", self.ctx.palette)
            return
        ok, msg, _proj = self._safe(
            lambda: projects_core.save_manual_project(url, self._active_id()),
            (False, "保存失败", None),
        )
        toast(self.ctx.page, msg or ("已保存" if ok else "保存失败"),
              "ok" if ok else "error", self.ctx.palette)
        if ok:
            self._manual_field.value = ""
            self._load_cached()
            self.ctx.page.update()

    # -- view -----------------------------------------------------------
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render_refresh_button()
        self._load_cached()

        manual_card = card(
            p,
            ft.Column(
                [
                    ft.Text("手动添加项目", size=theme.font_size("lg"),
                            weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Row(
                        [self._manual_field,
                         primary_button("保存", lambda e: self._save_manual(), icon=ft.Icons.ADD)],
                        spacing=theme.space("2"),
                    ),
                    ft.Text("接口读取失败或权限不足时，可粘贴蓝湖项目链接作为兜底。",
                            size=theme.font_size("xs"), color=p.text_muted),
                ],
                spacing=theme.space("3"),
            ),
        )
        list_card = card(
            p,
            ft.Column(
                [
                    ft.Row([ft.Text("项目列表", size=theme.font_size("lg"),
                                    weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                            ft.Container(expand=True), self._refresh_btn_holder],
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    self._list,
                ],
                spacing=theme.space("3"),
            ),
        )
        return ft.Column(
            [
                section_title(p, "项目", "查看与管理当前账号的蓝湖项目"),
                manual_card,
                list_card,
            ],
            spacing=theme.space("6"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )


__all__ = ["ProjectsPage"]
