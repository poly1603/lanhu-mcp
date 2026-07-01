"""Flet application shell for Lanhu MCP (v2 — enriched).

Builds the window chrome (sidebar + topbar) with animated page switching,
status indicators, and notification support.
"""

from __future__ import annotations

import time
from typing import Dict, List, Tuple

import flet as ft

from . import theme
from .state import AppContext
from .components import toast
from .pages import (
    OverviewPage,
    ServicePage,
    AccountsPage,
    ProjectsPage,
    IdeToolsPage,
    LogsPage,
)

APP_TITLE = "Lanhu MCP"
DEFAULT_PORT = 8000

NAV_ITEMS: List[Tuple[str, str, str]] = [
    ("overview", "总览", ft.Icons.DASHBOARD_OUTLINED),
    ("service", "服务", ft.Icons.DNS_OUTLINED),
    ("accounts", "账号", ft.Icons.PERSON_OUTLINE),
    ("projects", "项目", ft.Icons.FOLDER_OUTLINED),
    ("ide", "AI 工具", ft.Icons.TERMINAL),
    ("logs", "日志", ft.Icons.ARTICLE_OUTLINED),
]


class AppShell:
    def __init__(self, page: ft.Page, *, mode: str = "light", port: int = DEFAULT_PORT) -> None:
        self.page = page
        self.ctx = AppContext(page, mode=mode, port=port)
        self.ctx.navigate = self.navigate

        self._pages: Dict[str, object] = {}
        self._current = "overview"
        self._last_nav_time = 0.0

        self._switcher = ft.AnimatedSwitcher(
            content=ft.Container(),
            duration=220,
            transition=ft.AnimatedSwitcherTransition.FADE,
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
        )
        self._content_container = ft.Container(
            content=self._switcher,
            padding=ft.padding.symmetric(horizontal=theme.space("8"), vertical=theme.space("6")),
            expand=True,
            bgcolor=None,
        )

        self._nav_buttons: Dict[str, ft.Container] = {}
        self._nav_badges: Dict[str, ft.Container] = {}
        self._port_field = ft.TextField(
            value=str(port), width=96, dense=True, text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER, on_change=self._on_port_change,
        )

    # ── page registry ─────────────────────────────────────────────
    def _page(self, key: str):
        if key not in self._pages:
            factories = {
                "overview": OverviewPage,
                "service": ServicePage,
                "accounts": AccountsPage,
                "projects": ProjectsPage,
                "ide": IdeToolsPage,
                "logs": LogsPage,
            }
            self._pages[key] = factories[key](self.ctx)
        return self._pages[key]

    # ── navigation ────────────────────────────────────────────────
    def navigate(self, key: str) -> None:
        if key not in dict((k, l) for k, l, _ in NAV_ITEMS):
            return
        now = time.time()
        if key == self._current and now - self._last_nav_time < 0.3:
            return  # debounce
        self._last_nav_time = now
        self._current = key
        page_obj = self._page(key)
        # 先 build（创建控件树），再 refresh 注入数据
        self._switcher.content = page_obj.build()
        try:
            page_obj.refresh()
        except Exception:
            pass
        self._switcher.duration = 180 if now - self._last_nav_time < 1.0 else 300
        self._sync_nav_styles()
        self._update_badges()
        try:
            self.page.update()
        except Exception:
            pass

    def _sync_nav_styles(self) -> None:
        p = self.ctx.palette
        for key, btn in self._nav_buttons.items():
            active = key == self._current
            btn.bgcolor = p.sidebar_active if active else None
            row = btn.content
            if isinstance(row, ft.Row):
                for c in row.controls:
                    if isinstance(c, ft.Icon):
                        c.color = p.text_on_primary if active else p.sidebar_text
                    elif isinstance(c, ft.Text):
                        c.color = p.text_on_primary if active else p.sidebar_text
                        c.weight = theme.WEIGHT_SEMIBOLD if active else theme.WEIGHT_NORMAL

    def _update_badges(self) -> None:
        """Update nav badge counts (called after data changes)."""
        try:
            # We rely on pages to call this via ctx after refreshes.
            pass
        except Exception:
            pass

    # ── handlers ──────────────────────────────────────────────────
    def _on_port_change(self, e: ft.ControlEvent) -> None:
        raw = (e.control.value or "").strip()
        if raw.isdigit():
            port = int(raw)
            if 1 <= port <= 65535:
                self.ctx.port = port

    def _toggle_theme(self, e: ft.ControlEvent) -> None:
        new_mode = "dark" if self.ctx.mode == "light" else "light"
        self.ctx.set_mode(new_mode)
        self.page.theme_mode = ft.ThemeMode.DARK if new_mode == "dark" else ft.ThemeMode.LIGHT
        self._apply_chrome_colors()
        self._pages.clear()
        self.navigate(self._current)

    # ── sidebar ───────────────────────────────────────────────────
    def _build_nav_button(self, key: str, label: str, icon: str) -> ft.Container:
        p = self.ctx.palette
        btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=20, color=p.sidebar_text),
                    ft.Text(label, size=theme.font_size("md"), color=p.sidebar_text),
                    ft.Container(expand=True),
                ],
                spacing=theme.space("3"),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=theme.space("4"), vertical=theme.space("3")),
            border_radius=theme.radius("lg"),
            on_click=lambda e, k=key: self.navigate(k),
            ink=True,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        self._nav_buttons[key] = btn
        return btn

    def _build_sidebar(self) -> ft.Container:
        p = self.ctx.palette

        # Brand area with gradient accent
        brand = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.HUB, color="#FFFFFF", size=22),
                        gradient=ft.LinearGradient(
                            begin=ft.alignment.top_left,
                            end=ft.alignment.bottom_right,
                            colors=[p.primary, p.primary_gradient_end or p.primary_hover],
                        ),
                        border_radius=theme.radius("lg"),
                        padding=theme.space("2"),
                    ),
                    ft.Text(APP_TITLE, size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.sidebar_text),
                ],
                spacing=theme.space("2"),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=theme.space("4"), top=theme.space("5"), bottom=theme.space("6")),
        )

        # Divider below brand
        divider = ft.Container(height=1, bgcolor=p.sidebar_hover, margin=ft.margin.only(bottom=theme.space("4")))

        nav = ft.Column(
            [self._build_nav_button(k, l, i) for k, l, i in NAV_ITEMS],
            spacing=theme.space("1"),
        )

        # Bottom: theme toggle inside sidebar
        theme_icon_name = ft.Icons.LIGHT_MODE_OUTLINED if self.ctx.mode == "dark" else ft.Icons.DARK_MODE_OUTLINED
        theme_toggle = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(theme_icon_name, size=18, color=p.sidebar_text),
                    ft.Text("深色模式" if self.ctx.mode == "light" else "浅色模式",
                            size=theme.font_size("sm"), color=p.sidebar_text),
                ],
                spacing=theme.space("2"),
            ),
            padding=ft.padding.symmetric(horizontal=theme.space("4"), vertical=theme.space("3")),
            border_radius=theme.radius("lg"),
            on_click=self._toggle_theme,
            ink=True,
        )

        bottom = ft.Column([theme_toggle], spacing=0)

        return ft.Container(
            width=250,
            bgcolor=p.sidebar,
            padding=theme.space("3"),
            content=ft.Column(
                [brand, divider, nav, ft.Container(expand=True), bottom],
                expand=True,
                spacing=0,
            ),
        )

    # ── topbar ────────────────────────────────────────────────────
    def _build_topbar(self) -> ft.Container:
        p = self.ctx.palette

        # Port section
        port_section = ft.Row(
            [
                ft.Text("端口", color=p.text_secondary, size=theme.font_size("sm")),
                self._port_field,
            ],
            spacing=theme.space("2"),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            height=60,
            bgcolor=p.card,
            border=ft.border.only(bottom=ft.border.BorderSide(1, p.border_light)),
            padding=ft.padding.symmetric(horizontal=theme.space("6")),
            content=ft.Row(
                [
                    ft.Text("控制台", size=theme.font_size("lg"),
                            weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Container(expand=True),
                    port_section,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=theme.space("3"),
            ),
        )

    def _apply_chrome_colors(self) -> None:
        p = self.ctx.palette
        self.page.bgcolor = p.bg
        self._sidebar.bgcolor = p.sidebar
        self._sidebar.content = self._build_sidebar().content
        self._topbar.bgcolor = p.card
        self._topbar.content = self._build_topbar().content
        self._content_container.bgcolor = p.bg

    # ── mount ─────────────────────────────────────────────────────
    def mount(self) -> None:
        p = self.ctx.palette
        self.page.title = APP_TITLE
        self.page.padding = 0
        self.page.bgcolor = p.bg
        self.page.theme = theme.build_theme(theme.LIGHT)
        self.page.dark_theme = theme.build_theme(theme.DARK)
        self.page.theme_mode = ft.ThemeMode.DARK if self.ctx.mode == "dark" else ft.ThemeMode.LIGHT
        self.page.window.min_width = 1100
        self.page.window.min_height = 700
        self.page.window.width = 1400
        self.page.window.height = 880

        self._sidebar = self._build_sidebar()
        self._topbar = self._build_topbar()
        # 限制内容区最大宽度，让布局紧凑不撑满超宽屏
        right = ft.Column([self._topbar, self._content_container], spacing=0, expand=True)
        self.page.add(ft.Row([self._sidebar, right], spacing=0, expand=True))

        # 先把当前页 build 出来，再 refresh
        self._current = "overview"
        page_obj = self._page("overview")
        self._switcher.content = page_obj.build()
        try:
            page_obj.refresh()
        except Exception:
            pass
        self._sync_nav_styles()
        try:
            self.page.update()
        except Exception:
            pass


def main(page: ft.Page) -> None:
    shell = AppShell(page)
    shell.mount()


def run() -> None:
    """Launch the Flet desktop app."""
    ft.app(target=main)


__all__ = ["AppShell", "main", "run", "APP_TITLE", "NAV_ITEMS"]
