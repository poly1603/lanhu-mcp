"""Focused interaction tests for the modular Flet service surface."""

from types import SimpleNamespace

from lanhu_mcp.gui import theme
from lanhu_mcp.gui.pages import service as service_page
from lanhu_mcp.gui.state import AppContext


class _StoppedService:
    def is_running(self) -> bool:
        return False


def _service_context(port: int = 8000) -> SimpleNamespace:
    return SimpleNamespace(
        page=SimpleNamespace(update=lambda: None, open=lambda _control: None),
        palette=theme.LIGHT,
        service=_StoppedService(),
        port=port,
        navigate=lambda _key: None,
        add_log=lambda _line: None,
        set_port=lambda value: None,
    )


def test_context_set_port_notifies_the_shell() -> None:
    ctx = AppContext(SimpleNamespace())
    observed: list[int] = []
    ctx.on_port_change = observed.append

    ctx.set_port(8012)

    assert ctx.port == 8012
    assert observed == [8012]


def test_service_page_suggests_the_first_available_port(monkeypatch) -> None:
    ctx = _service_context()
    page = service_page.ServicePage(ctx)
    monkeypatch.setattr(service_page, "is_port_in_use", lambda value: value in {8001, 8002})

    assert page._suggest_available_port() == 8003


def test_service_page_stops_scanning_after_a_small_port_window(monkeypatch) -> None:
    ctx = _service_context()
    page = service_page.ServicePage(ctx)
    checked: list[int] = []

    def occupied(value: int) -> bool:
        checked.append(value)
        return True

    monkeypatch.setattr(service_page, "is_port_in_use", occupied)

    assert page._suggest_available_port() is None
    assert checked == list(range(8001, 8017))
