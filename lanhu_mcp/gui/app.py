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
from .components import StatusBadge, toast
from ..core import accounts as accounts_core
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
        self._navigation_sequence = 0

        self._switcher = ft.AnimatedSwitcher(
            content=ft.Container(),
            duration=240,
            reverse_duration=160,
            transition=ft.AnimatedSwitcherTransition.FADE,
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
        )
        self._content_container = ft.Container(
            content=self._switcher,
            padding=ft.padding.all(0),
            expand=True,
            bgcolor=self.ctx.palette.bg,
        )

        self._nav_buttons: Dict[str, ft.Container] = {}
        self._nav_badges: Dict[str, ft.Container] = {}
        self._port_field = ft.TextField(
            value=str(port), width=96, height=42, dense=True, text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER, on_change=self._on_port_change,
            border_radius=theme.radius("md"),
        )
        self.ctx.on_port_change = self._sync_port_field
        self._state_unsubscribe = self.ctx.subscribe_state(self._on_context_state)

    def _on_context_state(self, _reason: str) -> None:
        """Keep shell chrome and the visible page in sync with shared state."""
        if not hasattr(self, "_topbar") or not hasattr(self, "_sidebar"):
            return
        try:
            self._sidebar.content = self._build_sidebar().content
            self._topbar.content = self._build_topbar().content
            self._sync_nav_styles()
            page_obj = self._pages.get(self._current)
            if page_obj is not None:
                page_obj.refresh()
            self.page.update()
        except Exception:
            # A page may emit state while it is being replaced during startup.
            pass
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

    def _page_transition_content(self, key: str) -> ft.Container:
        """Wrap each navigation target so AnimatedSwitcher always sees a new page."""
        self._navigation_sequence += 1
        return ft.Container(
            key=f"workspace-{key}-{self._navigation_sequence}",
            content=self._page(key).build(),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

    # ── navigation ────────────────────────────────────────────────
    def navigate(self, key: str) -> None:
        if key not in dict((k, l) for k, l, _ in NAV_ITEMS):
            return
        now = time.time()
        previous_nav_time = self._last_nav_time
        if key == self._current and now - previous_nav_time < 0.3:
            return  # debounce
        self._last_nav_time = now
        self._current = key
        page_obj = self._page(key)
        # 先 build（创建控件树），再 refresh 注入数据
        self._switcher.duration = 180 if now - previous_nav_time < 1.0 else 260
        self._switcher.reverse_duration = 140
        self._switcher.transition = ft.AnimatedSwitcherTransition.FADE
        self._switcher.content = self._page_transition_content(key)
        try:
            page_obj.refresh()
        except Exception:
            pass
        self._sync_nav_styles()
        self._update_badges()
        self._topbar.content = self._build_topbar().content
        try:
            self.page.update()
        except Exception:
            pass

    def _sync_nav_styles(self) -> None:
        p = self.ctx.palette
        for key, btn in self._nav_buttons.items():
            active = key == self._current
            btn.bgcolor = p.sidebar_active if active else None
            btn.border = ft.border.all(1, p.primary_hover if active else "#00000000")
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
                self.ctx.set_port(port)

    def _sync_port_field(self, port: int) -> None:
        """Reflect page-originated port changes in the persistent topbar field."""
        self._port_field.value = str(port)
        self._port_field.error_text = None

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
            border=ft.border.all(1, "#00000000"),
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        )
        self._nav_buttons[key] = btn
        return btn

    def _build_sidebar(self) -> ft.Container:
        p = self.ctx.palette

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
                        width=42, height=42,
                        alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text(APP_TITLE, size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.sidebar_text),
                        ft.Text("Design MCP Console", size=theme.font_size("xs"), color=p.text_disabled),
                    ], spacing=0, expand=True),
                ],
                spacing=theme.space("3"),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=theme.space("3"), top=theme.space("5"), bottom=theme.space("5")),
        )

        # Divider below brand
        divider = ft.Container(height=1, bgcolor=p.sidebar_hover, margin=ft.margin.only(bottom=theme.space("4")))

        nav = ft.Column(
            [self._build_nav_button(k, l, i) for k, l, i in NAV_ITEMS],
            spacing=theme.space("1"),
        )

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
            bgcolor=theme.alpha("#FFFFFF", 0x10),
            on_click=self._toggle_theme,
            ink=True,
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        )

        running = self.ctx.service.is_running()
        service_state = ft.Container(
            content=ft.Row([
                ft.Container(width=7, height=7, bgcolor=p.success if running else p.text_disabled,
                             border_radius=theme.radius("full")),
                ft.Text("服务运行中" if running else "服务未启动", size=theme.font_size("xs"), color=p.sidebar_text),
            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=theme.alpha("#FFFFFF", 0x08),
            border=ft.border.all(1, theme.alpha("#FFFFFF", 0x12)),
            border_radius=theme.radius("full"),
            padding=ft.padding.symmetric(horizontal=theme.space("3"), vertical=theme.space("2")),
        )
        bottom = ft.Column([service_state, ft.Container(height=theme.space("2")), theme_toggle], spacing=0)

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

        running = self.ctx.service.is_running()
        self._port_field.border_color = p.border
        self._port_field.focused_border_color = p.primary
        self._port_field.bgcolor = p.input_bg
        self._port_field.color = p.text_primary
        self._port_field.text_size = theme.font_size("base")
        self._port_field.disabled = running
        self._port_field.tooltip = "服务运行时端口不可修改"

        # Port section
        port_section = ft.Row(
            [
                ft.Text("端口", color=p.text_secondary, size=theme.font_size("sm")),
                self._port_field,
            ],
            spacing=theme.space("2"),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        current_label = next((label for key, label, _icon in NAV_ITEMS if key == self._current), "控制台")
        try:
            active_account = accounts_core.get_active_account()
        except Exception:
            active_account = None
        account_label = accounts_core.account_primary_contact(active_account) if active_account else "未登录"
        account_chip = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.PERSON_OUTLINE, size=16, color=p.text_secondary),
                ft.Text(account_label, size=theme.font_size("xs"), color=p.text_secondary,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=theme.space("1"), tight=True),
            bgcolor=p.surface,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("full"),
            padding=ft.padding.symmetric(horizontal=theme.space("3"), vertical=theme.space("2")),
            on_click=lambda _event: self.navigate("accounts"),
            ink=True,
            tooltip="管理蓝湖账号",
        )
        return ft.Container(
            height=68,
            bgcolor=p.card,
            border=ft.border.only(bottom=ft.border.BorderSide(1, p.border_light)),
            padding=ft.padding.symmetric(horizontal=theme.space("6")),
            content=ft.Row(
                [
                    ft.Column([
                        ft.Text(current_label, size=theme.font_size("lg"),
                                weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                        ft.Text("蓝湖设计资产与 MCP 服务工作台", size=theme.font_size("xs"), color=p.text_muted),
                    ], spacing=0),
                    ft.Container(expand=True),
                    account_chip,
                    StatusBadge(p, "服务运行中" if running else "服务未启动", "ok" if running else "idle"),
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
        self._switcher.content = self._page_transition_content("overview")
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
    try:
        shell = AppShell(page)
        shell.mount()
    except Exception as e:
        import traceback
        print(f"AppShell mount error: {e}")
        traceback.print_exc()
        # 显示错误页面
        page.controls.clear()
        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color="red", size=48),
                    ft.Text(f"应用启动失败: {e}", size=16, weight=ft.FontWeight.BOLD),
                    ft.Text(traceback.format_exc(), size=12, selectable=True),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                expand=True,
            )
        )
        page.update()


def run() -> None:
    """Launch the Flet desktop app."""
    try:
        ft.app(target=main)
    except Exception as e:
        import traceback
        print(f"Flet app error: {e}")
        traceback.print_exc()
        raise


__all__ = ["AppShell", "main", "run", "APP_TITLE", "NAV_ITEMS"]
