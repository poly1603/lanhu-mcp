"""Regression tests for the lightweight desktop shell additions."""

from types import SimpleNamespace

import flet as ft

from lanhu_mcp.gui import theme
from lanhu_mcp.gui.app import AppShell
from lanhu_mcp.gui.floating import FloatingStatus
from lanhu_mcp.gui.pages.ide_tools import IDE_CARD_HEIGHT, IdeToolsPage


def test_ide_tools_use_intrinsic_height_responsive_cards() -> None:
    details = {
        "Claude Code": {
            "installed": True,
            "configured_at": "",
            "config_dir": r"C:\Users\test\.claude",
            "config_path": r"C:\Users\test\.claude.json",
        },
        "Trae": {"installed": True, "configured_at": "", "config_dir": r"C:\Users\test\.trae"},
        "Codex": {"installed": True, "configured_at": "", "exe_path": r"C:\Codex\codex.exe"},
    }
    ctx = SimpleNamespace(
        palette=theme.LIGHT,
        page=SimpleNamespace(update=lambda: None),
        ide=SimpleNamespace(get_detection_details=lambda: details),
        port=8000,
        add_log=lambda _line: None,
    )

    page = IdeToolsPage(ctx)
    page.build()

    assert isinstance(page._grid, ft.ResponsiveRow)
    assert len(page._grid.controls) == 3
    assert all(control.col == {"sm": 12, "md": 6, "lg": 4, "xl": 4} for control in page._grid.controls)
    assert all(isinstance(control.content, ft.Container) for control in page._grid.controls)
    assert all(control.content.height == IDE_CARD_HEIGHT for control in page._grid.controls)


def test_floating_status_is_native_and_does_not_create_a_flet_page() -> None:
    floating = FloatingStatus(
        is_running=lambda: False,
        on_show=lambda: None,
        on_start=lambda: None,
        on_stop=lambda: None,
        on_exit=lambda: None,
    )

    assert floating.WIDTH == 68
    assert floating.HEIGHT == 68
    assert floating._thread is None


def test_shell_skips_high_frequency_mcp_state_rebuild() -> None:
    class FakeWindow:
        def __init__(self) -> None:
            self.visible = True

        def to_front(self) -> None:
            pass

    page = SimpleNamespace(window=FakeWindow(), run_thread=lambda callback: callback(), update=lambda: None)
    shell = AppShell(page)
    shell._on_context_state("mcp_call")
    assert not hasattr(shell, "_topbar")


def test_shell_disposes_inactive_page() -> None:
    page = SimpleNamespace(window=SimpleNamespace(), run_thread=lambda callback: callback(), update=lambda: None)
    shell = AppShell(page)
    disposed = []

    class PageWithCleanup:
        def _on_unmount(self) -> None:
            disposed.append(True)

    shell._pages["temporary"] = PageWithCleanup()
    shell._dispose_page("temporary")

    assert disposed == [True]
    assert "temporary" not in shell._pages
