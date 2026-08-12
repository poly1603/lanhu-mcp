"""Regression tests for the persistent terminal log stream."""

from pathlib import Path
from types import SimpleNamespace

from lanhu_mcp.gui import state
from lanhu_mcp.gui.pages.logs import LogsPage


def _page() -> SimpleNamespace:
    return SimpleNamespace(update=lambda: None)


def test_context_restores_persists_and_clears_logs(tmp_path, monkeypatch) -> None:
    log_file = Path(tmp_path) / "app.log"
    monkeypatch.setattr(state, "LOG_FILE", log_file)

    context = state.AppContext(_page())
    context.add_log("[MCP] tools/call lanhu_get_designs arguments={\"cookie\":\"secret\"}")

    persisted = log_file.read_text(encoding="utf-8")
    assert "lanhu_get_designs" in persisted
    assert persisted.startswith("20")

    restored = state.AppContext(_page())
    assert len(restored.get_logs()) == 1
    assert "lanhu_get_designs" in restored.get_logs()[0]

    restored.clear_logs()
    assert restored.get_logs() == []
    assert log_file.read_text(encoding="utf-8") == ""


def test_logs_page_uses_internal_follow_tail_terminal(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(state, "LOG_FILE", Path(tmp_path) / "app.log")
    context = state.AppContext(_page())
    page = LogsPage(context)

    page.build()

    assert page._terminal.auto_scroll is True
    assert page.TERMINAL_HEIGHT >= 500
    assert page._terminal.controls
