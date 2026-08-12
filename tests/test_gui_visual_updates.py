from pathlib import Path
from types import SimpleNamespace

import flet as ft

from lanhu_mcp.gui import branding
from lanhu_mcp.gui import theme
from lanhu_mcp.gui.components.widgets import page_banner, page_frame
from lanhu_mcp.gui.pages.designs import DesignBrowser
from lanhu_mcp.gui.pages.logs import LogsPage
from lanhu_mcp.gui.floating import FloatingStatus
from lanhu_mcp.gui.app import AppShell


def test_page_banners_are_project_assets() -> None:
    for name in ("overview", "ai", "projects", "service", "accounts", "logs"):
        path = branding.banner_path(name)
        assert path.is_file()
        assert path.stat().st_size > 100_000


def test_page_banner_has_fixed_compact_height() -> None:
    banner = page_banner(SimpleNamespace(), "总览", "说明", "overview")
    assert banner.height == 126
    assert isinstance(banner.content, ft.Column)
    assert banner.image is not None
    assert banner.gradient is not None
    assert banner.content.expand is not True


def test_native_icons_include_an_exact_48px_frame() -> None:
    for name in ("lanhu_mcp.ico", "lanhu_mcp_status_idle.ico", "lanhu_mcp_status_running.ico"):
        path = Path("assets") / name
        assert path.is_file()
        from PIL import Image

        assert (48, 48) in Image.open(path).info.get("sizes", set())
    assert FloatingStatus._LR_LOADFROMFILE == 0x10


def test_app_context_defers_persisted_log_read_until_requested(tmp_path, monkeypatch) -> None:
    from lanhu_mcp.gui import state

    monkeypatch.setattr(state, "LOG_FILE", tmp_path / "app.log")
    state.LOG_FILE.write_text("2026-08-12 10:00:00 hello\n", encoding="utf-8")
    context = state.AppContext(SimpleNamespace())
    assert context._logs == []
    assert context.get_logs() == ["2026-08-12 10:00:00 hello"]


def test_topbar_uses_a_full_height_centered_inner_row() -> None:
    page = SimpleNamespace(window=SimpleNamespace(), update=lambda: None, run_thread=lambda fn: fn())
    shell = AppShell(page)
    topbar = shell._build_topbar()
    assert topbar.height == 68
    assert isinstance(topbar.content, ft.Container)
    assert topbar.content.height == 68
    assert topbar.content.alignment == ft.alignment.center
    assert topbar.content.content.alignment == ft.MainAxisAlignment.CENTER


def test_design_dialog_has_explicit_close_controls() -> None:
    browser = DesignBrowser(SimpleNamespace(palette=theme.LIGHT, page=None))
    dialog = browser._build_dialog()
    assert dialog.modal is True
    assert dialog.actions
    title = dialog.title
    assert isinstance(title, ft.Row)
    assert any(isinstance(control, ft.IconButton) for control in title.controls)


def test_logs_page_has_one_page_scroll_owner() -> None:
    context = SimpleNamespace(
        palette=theme.LIGHT,
        page=SimpleNamespace(update=lambda: None),
        get_logs=lambda: [],
        subscribe_logs=lambda _callback: lambda: None,
    )
    page = LogsPage(context)
    view = page.build()

    assert isinstance(view, ft.ListView)
    assert view.expand is True
    assert view.controls[1].expand is not True
    assert page._terminal.auto_scroll is True


def test_exit_destroys_flet_window_after_stopping_shell_surfaces(monkeypatch) -> None:
    class FakeWindow:
        prevent_close = True

        def __init__(self) -> None:
            self.destroyed = False
            self.closed = False

        def destroy(self) -> None:
            self.destroyed = True

        def close(self) -> None:
            self.closed = True

    class FakePage:
        def __init__(self) -> None:
            self.window = FakeWindow()
            self.updated = 0

        def update(self) -> None:
            self.updated += 1

        def run_thread(self, callback) -> None:
            callback()

    page = FakePage()
    shell = AppShell(page)
    stopped = []
    monkeypatch.setattr(shell._tray, "stop", lambda **_kwargs: stopped.append("tray"))
    monkeypatch.setattr(shell._floating, "stop", lambda **_kwargs: stopped.append("floating"))
    monkeypatch.setattr(shell.ctx.service, "is_running", lambda: False)

    shell._exit_from_shell()

    assert stopped == ["tray", "floating"]
    assert page.window.destroyed is True
    assert page.window.closed is False
