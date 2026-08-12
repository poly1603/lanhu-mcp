"""Regression coverage for the second-round desktop UX fixes."""

from pathlib import Path
from types import SimpleNamespace

import flet as ft

from lanhu_mcp.core import accounts as accounts_core
from lanhu_mcp.gui import app as app_module
from lanhu_mcp.gui import state
from lanhu_mcp.gui import theme
from lanhu_mcp.gui.app import AppShell
from lanhu_mcp.gui.components import page_frame
from lanhu_mcp.gui.pages.service import project_argument_values


def test_legacy_placeholder_account_is_collapsed_into_real_profile() -> None:
    real = {
        "id": "profile-1",
        "name": "刘勇",
        "email": "979741120@qq.com",
        "username": "刘勇",
        "cookie_fingerprint": "real-cookie",
    }
    data = accounts_core._normalize_accounts_data({
        "active_id": "legacy-cookie",
        "accounts": [
            {
                "id": "legacy-cookie",
                "name": "已登录账号",
                "role": "Developer",
                "cookie_fingerprint": "legacy-cookie",
                "cookie": "old-cookie",
            },
            real,
        ],
    })

    assert len(data["accounts"]) == 1
    assert data["accounts"][0]["email"] == "979741120@qq.com"
    assert data["active_id"] == "profile-1"


def test_upsert_same_identity_with_new_cookie_does_not_create_second_account(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    cookie_file = tmp_path / "cookie.txt"
    env_file = tmp_path / ".env"
    data_dir = tmp_path / "data"
    monkeypatch.setattr(accounts_core, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(accounts_core, "COOKIE_FILE", cookie_file)
    monkeypatch.setattr(accounts_core, "ENV_FILE", env_file)
    monkeypatch.setattr(accounts_core, "DATA_DIR", data_dir)

    first = accounts_core.upsert_account(
        "user_token=first",
        {"id": "user-1", "name": "刘勇", "email": "user@example.test"},
    )
    second = accounts_core.upsert_account(
        "user_token=rotated",
        {"id": "user-1", "name": "刘勇", "email": "user@example.test"},
    )

    assert first is not None and second is not None
    assert len(accounts_core.get_accounts()) == 1
    assert accounts_core.get_active_account()["id"] == "user-1"
    assert accounts_core.get_active_account()["cookie"] == "user_token=rotated"


def test_project_selector_fills_required_url_when_project_has_only_ids() -> None:
    values = project_argument_values({"id": "pid-1", "team_id": "tid-1"})

    assert values["project_id"] == "pid-1"
    assert values["pid"] == "pid-1"
    assert values["team_id"] == "tid-1"
    assert values["tid"] == "tid-1"
    assert values["url"].endswith("pid=pid-1&tid=tid-1")


def test_usage_stats_counts_server_calls_but_not_gui_preview_duplicates(monkeypatch, tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    monkeypatch.setattr(state, "LOG_FILE", log_file)
    context = state.AppContext(SimpleNamespace(update=lambda: None))
    context.add_log("[MCP] tools/call lanhu_get_designs arguments={}")
    context.add_log("[MCP] GUI tools/call lanhu_get_designs arguments={}")
    context.add_log("[MCP] tools/call lanhu_get_pages arguments={}")
    context.add_log("[ERR] lanhu_get_pages -> ERROR")

    usage = context.usage_stats()

    assert usage["total_calls"] == 2
    assert usage["method_counts"] == [("lanhu_get_designs", 1), ("lanhu_get_pages", 1)]
    assert usage["error_count"] == 1


def test_overview_chart_controls_construct_without_browser_runtime() -> None:
    from lanhu_mcp.gui.pages.overview import OverviewPage

    page = OverviewPage(SimpleNamespace(palette=theme.LIGHT))
    chart = page._method_chart({
        "usage": {"method_counts": [("lanhu_get_designs", 2)]},
    })

    assert isinstance(chart, ft.BarChart)
    assert len(chart.bar_groups) == 1


def test_page_frame_keeps_body_content_sized_inside_scroll_view() -> None:
    view = page_frame(theme.LIGHT, "总览", "测试", ft.Column([ft.Text("content")]))

    assert view.controls[1].expand is not True


def test_overview_uses_stable_stack_for_metrics_and_activity() -> None:
    from lanhu_mcp.gui.pages.overview import OverviewPage

    usage = {
        "total_calls": 2,
        "method_counts": [("lanhu_get_designs", 2)],
        "daily_calls": [("2026-08-11", 2)],
        "project_events": 1,
        "account_events": 1,
        "error_count": 0,
        "recent_events": [],
    }
    context = SimpleNamespace(
        palette=theme.LIGHT,
        port=8000,
        service=SimpleNamespace(is_running=lambda: True),
        ide=SimpleNamespace(detect_all=lambda: {"Codex": True}),
        usage_stats=lambda: usage,
    )
    overview = OverviewPage(context)
    overview._gather = lambda: {
        "accounts": 1,
        "active": {},
        "tools": 28,
        "projects": 1,
        "recent_projects": [],
        "ide_installed": 1,
        "ide_total": 1,
        "running": True,
        "account_label": "u@example.test",
        "usage": usage,
    }

    body = overview.build().controls[1].content

    assert isinstance(body, ft.Column)
    assert len(body.controls) == 8
    assert isinstance(body.controls[1], ft.ResponsiveRow)
    assert all(isinstance(control, ft.Container) for control in body.controls[1].controls)


def test_first_close_prompts_then_persists_window_choice(monkeypatch, tmp_path: Path) -> None:
    preferences = tmp_path / "window_preferences.json"
    monkeypatch.setattr(app_module, "WINDOW_PREFERENCES_FILE", preferences)

    class FakeWindow:
        visible = True

        def to_front(self) -> None:
            pass

    class FakePage:
        def __init__(self) -> None:
            self.window = FakeWindow()
            self.opened: list[ft.AlertDialog] = []

        def open(self, dialog: ft.AlertDialog) -> None:
            self.opened.append(dialog)

        def close(self, _dialog: ft.AlertDialog) -> None:
            pass

        def update(self) -> None:
            pass

        def run_thread(self, callback) -> None:
            callback()

    page = FakePage()
    shell = AppShell(page)
    assert shell._close_behavior is None

    shell._on_window_event(SimpleNamespace(type="close", data=""))
    assert len(page.opened) == 1
    page.opened[0].actions[0].on_click(None)

    assert shell._close_behavior == "window"
    assert page.window.visible is False
    assert preferences.exists()

    shell._on_window_event(SimpleNamespace(type="close", data=""))
    assert len(page.opened) == 1

    second_shell = AppShell(FakePage())
    assert second_shell._close_behavior == "window"
