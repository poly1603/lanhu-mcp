from __future__ import annotations

from types import SimpleNamespace

from lanhu_mcp.services import browser_login
from lanhu_mcp.services.lanhu_api import lanhu_api_headers
from lanhu_mcp.core import accounts as accounts_core


def test_default_browser_login_collects_valid_cookie_immediately() -> None:
    cookie = SimpleNamespace(
        name="lanhu_auth_token",
        value="valid-token-123",
        domain=".lanhuapp.com",
    )

    result = browser_login.run_default_browser_login(
        "https://lanhuapp.com/web/",
        timeout=1,
        poll_interval=0.2,
        open_browser=lambda _url: True,
        read_cookie=lambda: (
            browser_login._format_cookie_objects([cookie], "lanhuapp.com"),
            "chrome",
            [],
        ),
    )

    assert result["status"] == "success"
    assert result["source"] == "default-browser"
    assert result["cookies"] == "lanhu_auth_token=valid-token-123"


def test_browser_cookie_formatter_ignores_other_domains_and_duplicates() -> None:
    cookies = [
        SimpleNamespace(name="user_token", value="first", domain=".lanhuapp.com"),
        SimpleNamespace(name="user_token", value="second", domain=".lanhuapp.com"),
        SimpleNamespace(name="other", value="secret", domain="example.com"),
    ]

    assert browser_login._format_cookie_objects(cookies, "lanhuapp.com") == "user_token=first"


def test_default_browser_login_reports_unreadable_cookie_store_without_waiting() -> None:
    result = browser_login.run_default_browser_login(
        "https://lanhuapp.com/web/",
        timeout=10,
        open_browser=lambda _url: True,
        read_cookie=lambda: ("", "", ["browser-cookie-read-unavailable"]),
    )

    assert result["status"] == "error"
    assert "Cookie" in str(result["error"])


def test_missing_browser_readers_is_reported_as_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(browser_login, "_reader_order", lambda: [])

    _cookie, _browser, diagnostics = browser_login.read_default_browser_cookie()

    assert "browser-cookie-read-unavailable" in diagnostics


def test_login_prefers_managed_webview_window(monkeypatch) -> None:
    expected = {
        "status": "success",
        "cookies": "lanhu_auth_token=fallback-token",
        "source": "managed-webview",
    }
    messages: list[str] = []

    def fake_managed_webview_login(*_args, **kwargs):
        on_output = kwargs.get("on_output")
        if callable(on_output):
            on_output("已打开蓝湖登录窗口。")
        return expected

    monkeypatch.setattr(accounts_core, "_run_managed_webview_login", fake_managed_webview_login)
    monkeypatch.setattr(browser_login, "run_default_browser_login", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("browser sync should not run")))

    result = accounts_core.launch_login_helper(on_output=messages.append)

    assert result == expected
    assert any("登录窗口" in message for message in messages)


def test_project_api_accepts_auth_token_cookie_name() -> None:
    headers = lanhu_api_headers("lanhu_auth_token=token-abc; SERVERID=anonymous")

    assert headers["Cookie"].startswith("lanhu_auth_token=token-abc")
    assert headers["Authorization"].startswith("Basic ")
