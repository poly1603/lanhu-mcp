"""回归测试：打包服务必须能找到运行目录外的有效 Cookie 文件。"""

from __future__ import annotations

import json
from pathlib import Path

import lanhu_mcp_server


def test_cookie_file_candidates_include_executable_parent(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "dist" / "LanhuMCP.exe"
    executable.parent.mkdir()
    monkeypatch.setattr(lanhu_mcp_server.sys, "executable", str(executable))
    monkeypatch.setenv("LANHU_COOKIE_FILE", "")

    candidates = lanhu_mcp_server._cookie_file_candidates()

    assert executable.parent / "cookie.json" in candidates
    assert tmp_path / "cookie.json" in candidates


def test_load_cookie_prefers_explicit_file_over_stale_environment(monkeypatch, tmp_path: Path) -> None:
    cookie_path = tmp_path / "current-cookie.json"
    cookie_path.write_text(
        json.dumps({"lanhu_cookie": "session=current; user_token=current-token"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LANHU_COOKIE_FILE", str(cookie_path))
    monkeypatch.setenv("LANHU_COOKIE", "user_token=stale-token")

    assert lanhu_mcp_server._load_cookie() == "session=current; user_token=current-token"
    assert lanhu_mcp_server.COOKIE_SOURCE == str(cookie_path)
