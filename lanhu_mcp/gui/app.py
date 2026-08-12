"""Flet application shell for Lanhu MCP (v2 — enriched).

Builds the window chrome (sidebar + topbar) with animated page switching,
status indicators, and notification support.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Dict, List, Tuple

import flet as ft

from . import theme
from .branding import apply_windows_app_identity, logo_base64, window_icon_path
from .state import AppContext
from .tray import TrayController
from .floating import FloatingStatus
from .components import StatusBadge, toast
from ..core import accounts as accounts_core
from ..core.paths import WINDOW_PREFERENCES_FILE
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
_CLOSE_BEHAVIOR_WINDOW = "window"
_CLOSE_BEHAVIOR_EXIT = "exit"
_CLOSE_BEHAVIORS = {_CLOSE_BEHAVIOR_WINDOW, _CLOSE_BEHAVIOR_EXIT}

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
        self.ctx.start_service = self._start_service_from_shell
        self.ctx.open_login = self._open_login_from_shell

        self._pages: Dict[str, object] = {}
        self._current = "overview"
        self._last_nav_time = 0.0
        self._navigation_sequence = 0
        self._allow_window_close = False
        self._exiting = False
        self._close_behavior = self._load_close_behavior()
        self._close_dialog: ft.AlertDialog | None = None

        self._switcher = ft.AnimatedSwitcher(
            content=ft.Container(),
            expand=True,
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
            alignment=ft.alignment.top_left,
            # The sidebar owns the outer gray canvas.  Keep the workspace a
            # continuous surface so pages do not float inside a second gray
            # rectangle, especially while the AnimatedSwitcher is measuring.
            bgcolor=self.ctx.palette.card,
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
        self._tray = TrayController(
            is_running=self.ctx.service.is_running,
            on_show=lambda: self._dispatch_ui(self._show_window),
            on_hide=lambda: self._dispatch_ui(self._hide_window),
            on_start=lambda: self._dispatch_ui(self._start_service_from_shell),
            on_stop=lambda: self._dispatch_ui(self._stop_service_from_shell),
            on_floating=lambda: self._dispatch_ui(self._show_floating),
            on_exit=lambda: self._dispatch_ui(self._exit_from_shell),
            on_error=self._log_shell_error,
        )
        self._floating = FloatingStatus(
            is_running=self.ctx.service.is_running,
            on_show=lambda: self._dispatch_ui(self._show_window),
            on_start=lambda: self._dispatch_ui(self._start_service_from_shell),
            on_stop=lambda: self._dispatch_ui(self._stop_service_from_shell),
            on_exit=lambda: self._dispatch_ui(self._exit_from_shell),
            on_error=self._log_shell_error,
        )

    def _on_context_state(self, _reason: str) -> None:
        """Keep shell chrome and the visible page in sync with shared state."""
        if _reason == "cache_cleared":
            # The cleanup action removes the persisted first-close choice. Do
            # not keep the old value alive in this running shell.
            self._close_behavior = self._load_close_behavior()
        # MCP calls are high-frequency and do not change service status. Do
        # not rebuild the sidebar/topbar/page tree for every request.
        if _reason != "mcp_call":
            self._sync_auxiliary_status()
        if _reason == "mcp_call":
            return
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

    def _dispatch_ui(self, callback) -> None:
        """Run a tray/native-window callback on Flet's UI executor."""
        try:
            self.page.run_thread(callback)
        except Exception:
            try:
                callback()
            except Exception as error:  # noqa: BLE001
                self._log_shell_error(str(error))

    def _log_shell_error(self, message: str) -> None:
        try:
            self.ctx.add_log(f"[WARN] {message}")
        except Exception:
            pass

    def _sync_auxiliary_status(self) -> None:
        running = self.ctx.service.is_running()
        self._tray.update()
        self._floating.update(running)

    def _apply_runtime_windows_icon(self, attempts: int = 6) -> None:
        """Retry after Flet creates its native HWND, without blocking startup."""
        if apply_windows_app_identity(APP_TITLE) or attempts <= 0:
            return
        retry = threading.Timer(
            0.25,
            lambda: self._apply_runtime_windows_icon(attempts - 1),
        )
        retry.daemon = True
        retry.start()

    def _show_window(self) -> None:
        try:
            self.page.window.visible = True
            self.page.update()
            self.page.window.to_front()
        except Exception:
            pass

    def _hide_window(self) -> None:
        try:
            self.page.window.visible = False
            # Flet queues window attributes until the next update. Without
            # this explicit flush the first "仅关闭窗口" choice can leave
            # the native window visible even though the preference is saved.
            self.page.update()
        except Exception:
            pass

    def _show_floating(self) -> None:
        self._floating.show()

    def _start_service_from_shell(self) -> None:
        self.navigate("service")
        page_obj = self._pages.get("service")
        start = getattr(page_obj, "_start", None)
        if callable(start):
            start()

    def _open_login_from_shell(self) -> None:
        self.navigate("accounts")
        page_obj = self._pages.get("accounts")
        add_account = getattr(page_obj, "_add_account", None)
        if callable(add_account):
            add_account()

    def _stop_service_from_shell(self) -> None:
        page_obj = self._pages.get("service")
        stop = getattr(page_obj, "_stop", None)
        if callable(stop):
            stop()
        else:
            def stop_without_page() -> None:
                ok, message = self.ctx.service.stop()
                self.ctx.add_log(message or ("[OK] MCP 服务已停止" if ok else "[WARN] MCP 服务未运行"))
                self.ctx.notify_state_change("service")

            threading.Thread(target=stop_without_page, name="lanhu-shell-stop", daemon=True).start()

    def _exit_from_shell(self) -> None:
        if self._exiting:
            return
        self._exiting = True
        self._allow_window_close = True
        # Tray and floating controls own separate native message-loop threads.
        # Stop and join them before destroying the Flet window so an exit does
        # not leave a desktop widget or tray icon behind.
        self._tray.stop(wait=True)
        self._floating.stop(wait=True)
        for key in list(self._pages):
            self._dispose_page(key)
        try:
            self._state_unsubscribe()
        except Exception:
            pass

        def stop_service() -> None:
            try:
                if self.ctx.service.is_running():
                    self.ctx.service.stop()
            finally:
                self._dispatch_ui(self._close_window)

        threading.Thread(target=stop_service, name="lanhu-shell-exit", daemon=True).start()

    def _close_window(self) -> None:
        try:
            self.page.window.prevent_close = False
            destroy = getattr(self.page.window, "destroy", None)
            if callable(destroy):
                destroy()
            else:
                self.page.window.close()
        except Exception:
            try:
                self.page.window.close()
            except Exception:
                pass

    @staticmethod
    def _load_close_behavior() -> str | None:
        """Load the user's first-close choice, if one has been saved."""
        try:
            payload = json.loads(WINDOW_PREFERENCES_FILE.read_text(encoding="utf-8"))
            value = payload.get("close_behavior") if isinstance(payload, dict) else None
            return value if isinstance(value, str) and value in _CLOSE_BEHAVIORS else None
        except (OSError, json.JSONDecodeError):
            return None

    def _save_close_behavior(self, behavior: str) -> None:
        try:
            WINDOW_PREFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
            WINDOW_PREFERENCES_FILE.write_text(
                json.dumps({"close_behavior": behavior}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            # The in-memory choice still applies for this process when the
            # preferences directory is temporarily unavailable.
            pass

    def _choose_close_behavior(self, behavior: str, dialog: ft.AlertDialog) -> None:
        self._close_behavior = behavior
        self._save_close_behavior(behavior)
        self._close_dialog = None
        try:
            self.page.close(dialog)
        except Exception:
            dialog.open = False
            try:
                self.page.update()
            except Exception:
                pass
        if behavior == _CLOSE_BEHAVIOR_EXIT:
            self._exit_from_shell()
        else:
            self._hide_window()

    def _prompt_close_behavior(self) -> None:
        if self._close_dialog is not None:
            return
        p = self.ctx.palette
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("关闭 Lanhu MCP", color=p.text_primary),
            content=ft.Container(
                width=440,
                content=ft.Column([
                    ft.Text("请选择以后点击窗口关闭按钮时的行为：", color=p.text_primary),
                    ft.Text(
                        "关闭窗口：隐藏到系统托盘，服务继续运行。\n"
                        "退出程序：停止服务并完全退出 Lanhu MCP。",
                        size=theme.font_size("sm"),
                        color=p.text_muted,
                    ),
                ], spacing=theme.space("2"), tight=True),
            ),
            actions=[
                ft.TextButton(
                    "仅关闭窗口",
                    on_click=lambda _event: self._choose_close_behavior(_CLOSE_BEHAVIOR_WINDOW, dialog),
                ),
                ft.FilledButton(
                    "退出程序",
                    icon=ft.Icons.EXIT_TO_APP,
                    on_click=lambda _event: self._choose_close_behavior(_CLOSE_BEHAVIOR_EXIT, dialog),
                ),
            ],
        )
        self._close_dialog = dialog
        try:
            self.page.open(dialog)
        except Exception:
            self._close_dialog = None

    def _on_window_event(self, event) -> None:
        event_name = str(getattr(event, "type", "")).lower()
        event_data = str(getattr(event, "data", "")).lower()
        if "close" not in event_name and event_data != "close":
            return
        if self._allow_window_close or self._exiting:
            return
        if self._close_behavior == _CLOSE_BEHAVIOR_WINDOW:
            self._hide_window()
        elif self._close_behavior == _CLOSE_BEHAVIOR_EXIT:
            self._exit_from_shell()
        else:
            self._prompt_close_behavior()

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

    def _dispose_page(self, key: str) -> None:
        """Release an inactive page and any page-owned workers/caches."""
        page_obj = self._pages.pop(key, None)
        if page_obj is None:
            return
        on_unmount = getattr(page_obj, "_on_unmount", None)
        if callable(on_unmount):
            try:
                on_unmount()
            except Exception:
                pass

    def _page_transition_content(self, key: str) -> ft.Container:
        """Wrap each navigation target so AnimatedSwitcher always sees a new page."""
        self._navigation_sequence += 1
        return ft.Container(
            key=f"workspace-{key}-{self._navigation_sequence}",
            content=self._page(key).build(),
            expand=True,
            alignment=ft.alignment.top_left,
            bgcolor=self.ctx.palette.card,
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
        if key != self._current:
            self._dispose_page(self._current)
        self._last_nav_time = now
        self._current = key
        page_obj = self._page(key)
        # 先 build（创建控件树），再 refresh 注入数据
        self._switcher.duration = 180 if now - previous_nav_time < 1.0 else 260
        self._switcher.reverse_duration = 140
        self._switcher.transition = ft.AnimatedSwitcherTransition.FADE
        self._switcher.content = self._page_transition_content(key)
        try:
            on_mount = getattr(page_obj, "_on_mount", None)
            if callable(on_mount):
                on_mount()
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
        # The executable icon alone does not update Flet/Flutter's live
        # taskbar window. Apply the same supplied Lanhu logo to that HWND too.
        self._apply_runtime_windows_icon()
        self._sync_auxiliary_status()

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
        for page_obj in self._pages.values():
            on_unmount = getattr(page_obj, "_on_unmount", None)
            if callable(on_unmount):
                on_unmount()
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

        logo_data = logo_base64()
        logo_control = (
            ft.Image(
                src_base64=logo_data,
                width=42,
                height=42,
                fit=ft.ImageFit.COVER,
                border_radius=theme.radius("lg"),
                semantics_label="Lanhu MCP Logo",
            )
            if logo_data
            else ft.Container(
                content=ft.Icon(ft.Icons.HUB, color="#FFFFFF", size=22),
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=[p.primary, p.primary_gradient_end or p.primary_hover],
                ),
                border_radius=theme.radius("lg"),
                width=42,
                height=42,
                alignment=ft.alignment.center,
            )
        )

        brand = ft.Container(
            content=ft.Row(
                [
                    logo_control,
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
            content=ft.Container(
                height=68,
                alignment=ft.alignment.center,
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
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=theme.space("3"),
                    expand=True,
                ),
                expand=True,
            ),
        )

    def _apply_chrome_colors(self) -> None:
        p = self.ctx.palette
        self.page.bgcolor = p.bg
        self._sidebar.bgcolor = p.sidebar
        self._sidebar.content = self._build_sidebar().content
        self._topbar.bgcolor = p.card
        self._topbar.content = self._build_topbar().content
        self._content_container.bgcolor = p.card

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
        try:
            # Flet exposes a native center command; use it after dimensions
            # are assigned so the first frame does not open in a corner.
            self.page.window.center()
        except Exception:
            pass
        try:
            # Flet 0.28 exposes a cross-platform native window icon. Keep the
            # Win32 HWND patch below as a fallback for taskbar integration.
            self.page.window.icon = str(window_icon_path())
        except Exception:
            pass
        self.page.window.prevent_close = True
        self.page.window.on_event = self._on_window_event

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
            on_mount = getattr(page_obj, "_on_mount", None)
            if callable(on_mount):
                on_mount()
            page_obj.refresh()
        except Exception:
            pass
        self._sync_nav_styles()
        try:
            self.page.update()
        except Exception:
            pass
        try:
            self.page.window.center()
        except Exception:
            pass
        self._sync_auxiliary_status()
        self._tray.start()
        self._floating.start()


def main(page: ft.Page) -> None:
    try:
        # Set the AppUserModelID before the native window is created. The
        # helper also retries the HWND-specific icon after mount.
        apply_windows_app_identity(APP_TITLE)
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
        ft.app(target=main, name=APP_TITLE)
    except Exception as e:
        import traceback
        print(f"Flet app error: {e}")
        traceback.print_exc()
        raise


__all__ = ["AppShell", "main", "run", "APP_TITLE", "NAV_ITEMS"]
