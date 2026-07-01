from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import lanhu_login_helper


def test_smoke_mode_skips_webview_start(tmp_path: Path, monkeypatch) -> None:
    """烟测模式下不应真正启动 WebView。"""
    result_file = tmp_path / "result.json"
    storage_dir = tmp_path / "webview"

    def _should_not_run(*args, **kwargs) -> object:
        raise AssertionError("webview.start should not run in smoke mode")

    fake_webview = types.SimpleNamespace(
        create_window=lambda *args, **kwargs: object(),
        start=_should_not_run,
    )

    monkeypatch.setenv("LANHU_LOGIN_HELPER_SMOKE", "1")
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lanhu_login_helper.py",
            str(result_file),
            str(storage_dir),
            "https://lanhuapp.com/web/",
        ],
    )

    exit_code = lanhu_login_helper.main()

    assert exit_code == 0
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert payload["url"] == "about:blank"
