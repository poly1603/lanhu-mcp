"""Flet application shell for Lanhu MCP.

Builds the window chrome (sidebar navigation + top bar) and routes between the
page views in :mod:`lanhu_mcp.gui.pages`. All business logic is delegated to the
:class:`~lanhu_mcp.gui.state.AppContext` and the backend ``core`` / ``services``
packages.

Entry point::

    from lanhu_mcp.gui.app import run
    run()
"""

from __future__ import annotations

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

# (key, label, icon)
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

        self._content = ft.Container(expand=True, padding=theme.space("8"))
        self._nav_buttons: Dict[str, ft.Container] = {}
        self._port_field = ft.TextField(
            value=str(port), width=96, dense=True, text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER, on_change=self._on_port_change,
        )

    # -- page registry --------------------------------------------------
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

    # -- navigation -----------------------------------------------------
    def navigate(self, key: str) -> None:
        if key not in dict((k, l) for k, l, _ in NAV_ITEMS):
            return
        self._current = key
        page_obj = self._page(key)
        self._content.content = page_obj.build()
        self._sync_nav_styles()
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

    # -- handlers -------------------------------------------------------
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
        # Rebuild current page so palette-derived colors refresh.
        self._pages.clear()
        self.navigate(self._current)

    # -- chrome ---------------------------------------------------------
    def _build_nav_button(self, key: str, label: str, icon: str) -> ft.Container:
        p = self.ctx.palette
        btn = ft.Container(
            content=ft.Row(
                [ft.Icon(icon, size=20, color=p.sidebar_text),
                 ft.Text(label, size=theme.font_size("md"), color=p.sidebar_text)],
                spacing=theme.space("3"),
            ),
            padding=ft.padding.symmetric(horizontal=theme.space("4"), vertical=theme.space("3")),
            border_radius=theme.radius("md"),
            on_click=lambda e, k=key: self.navigate(k),
            ink=True,
        )
        self._nav_buttons[key] = btn
        return btn

    def _build_sidebar(self) -> ft.Container:
        p = self.ctx.palette
        brand = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.Icons.HUB, color=p.primary, size=26),
                 ft.Text(APP_TITLE, size=theme.font_size("xl"),
                         weight=theme.WEIGHT_BOLD, color=p.sidebar_text)],
                spacing=theme.space("2"),
            ),
            padding=ft.padding.only(left=theme.space("4"), top=theme.space("4"),
                                    bottom=theme.space("6")),
        )
        nav = ft.Column(
            [self._build_nav_button(k, l, i) for k, l, i in NAV_ITEMS],
            spacing=theme.space("1"),
        )
        return ft.Container(
            width=232,
            bgcolor=p.sidebar,
            padding=theme.space("3"),
            content=ft.Column([brand, nav, ft.Container(expand=True)], expand=True),
        )

    def _build_topbar(self) -> ft.Container:
        p = self.ctx.palette
        self._theme_icon = ft.Icon(
            ft.Icons.DARK_MODE_OUTLINED if self.ctx.mode == "light" else ft.Icons.LIGHT_MODE_OUTLINED,
            color=p.text_secondary,
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
                    ft.Text("端口", color=p.text_secondary),
                    self._port_field,
                    ft.IconButton(content=self._theme_icon, tooltip="切换主题",
                                  on_click=self._toggle_theme),
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
        self._content.bgcolor = p.bg

    # -- mount ----------------------------------------------------------
    def mount(self) -> None:
        p = self.ctx.palette
        self.page.title = APP_TITLE
        self.page.padding = 0
        self.page.bgcolor = p.bg
        self.page.theme = theme.build_theme(theme.LIGHT)
        self.page.dark_theme = theme.build_theme(theme.DARK)
        self.page.theme_mode = ft.ThemeMode.DARK if self.ctx.mode == "dark" else ft.ThemeMode.LIGHT
        self.page.window.min_width = 1060
        self.page.window.min_height = 700
        self.page.window.width = 1360
        self.page.window.height = 860

        self._sidebar = self._build_sidebar()
        self._topbar = self._build_topbar()
        right = ft.Column([self._topbar, self._content], spacing=0, expand=True)
        self.page.add(ft.Row([self._sidebar, right], spacing=0, expand=True))

        self.navigate("overview")


def main(page: ft.Page) -> None:
    shell = AppShell(page)
    shell.mount()


def run() -> None:
    """Launch the Flet desktop app."""
    ft.app(target=main)


__all__ = ["AppShell", "main", "run", "APP_TITLE", "NAV_ITEMS"]
