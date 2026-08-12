from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from lanhu_mcp.core import cleanup as cleanup_core
from lanhu_mcp.core import projects as projects_core
from lanhu_mcp.gui import state
from lanhu_mcp.services import tools_registry


def _page() -> SimpleNamespace:
    return SimpleNamespace(update=lambda: None)


def test_clear_local_cache_keeps_account_and_project_files(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "app.log"
    recent_file = tmp_path / "recent_projects.json"
    preferences = tmp_path / "window_preferences.json"
    avatar_dir = tmp_path / "avatars"
    avatar_dir.mkdir()
    (avatar_dir / "account.png").write_bytes(b"avatar")
    preferences.write_text('{"close_behavior":"window"}', encoding="utf-8")

    monkeypatch.setattr(state, "LOG_FILE", log_file)
    monkeypatch.setattr(cleanup_core, "WINDOW_PREFERENCES_FILE", preferences)
    monkeypatch.setattr(cleanup_core, "AVATAR_CACHE_DIR", avatar_dir)
    monkeypatch.setattr(projects_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(projects_core, "RECENT_PROJECTS_FILE", recent_file)

    context = state.AppContext(_page())
    context.add_log("[UI] close window")
    projects_core.record_recent_project({"id": "p1", "team_id": "t1", "name": "Demo"})
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text('{"accounts": [{"id": "account-1"}]}', encoding="utf-8")

    summary = cleanup_core.clear_local_cache(context)

    assert summary["logs"] == 1
    assert summary["recent_projects"] == 1
    assert summary["avatars"] == 1
    assert summary["close_behavior"] is True
    assert context.get_logs() == []
    assert projects_core.recent_projects() == []
    assert not preferences.exists()
    assert not (avatar_dir / "account.png").exists()
    assert accounts_file.exists()


def test_packaged_method_schema_has_required_design_url(monkeypatch) -> None:
    monkeypatch.setattr(tools_registry, "tool_source_candidates", lambda: [Path("missing-source.py")])
    specs = tools_registry.tool_argument_specs("lanhu_get_designs")

    assert [item["name"] for item in specs] == ["url", "sector_filter"]
    assert specs[0]["required"] is True


def test_source_method_schema_hides_injected_context(monkeypatch, tmp_path) -> None:
    source = tmp_path / "tools.py"
    source.write_text(
        "from typing import Annotated\n"
        "class M:\n"
        "    def tool(self, fn): return fn\n"
        "m = M()\n"
        "@m.tool()\n"
        "def demo(url: Annotated[str, 'url'], ctx=None):\n"
        "    return {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tools_registry, "tool_source_candidates", lambda: [source])

    specs = tools_registry.tool_argument_specs("demo")

    assert [item["name"] for item in specs] == ["url"]
