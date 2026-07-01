"""GUI helper optimization tests."""

from pathlib import Path
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

import pytest

import lanhu_mcp_gui as gui
import lanhu_mcp.core.avatar as avatar_core
import lanhu_mcp.services.tools_registry as tools_registry


@pytest.fixture(autouse=True)
def reset_mcp_tool_cache() -> Generator[None, None, None]:
    """每个用例后恢复工具缓存，避免影响同进程后续测试。"""
    tools_registry._MCP_TOOLS_CACHE = None
    yield
    tools_registry._MCP_TOOLS_CACHE = None


def test_discover_mcp_tools_reuses_cache_until_refresh(monkeypatch: "MonkeyPatch", tmp_path: Path) -> None:
    """工具扫描结果应可复用，避免每次刷新界面都重复 AST 扫描。"""
    source_path = tmp_path / "server.py"
    source_path.write_text("placeholder", encoding="utf-8")
    calls: list[Path] = []

    def fake_candidates() -> list[Path]:
        """返回测试用源码候选。"""
        return [source_path]

    def fake_scan(path: Path) -> list[tuple[str, str]]:
        """记录扫描次数并返回固定工具。"""
        calls.append(path)
        return [("lanhu_get_pages", "获取页面")]

    monkeypatch.setattr(tools_registry, "tool_source_candidates", fake_candidates)
    monkeypatch.setattr(tools_registry, "scan_mcp_tools_from_file", fake_scan)

    first_result = gui.discover_mcp_tools(refresh=True)
    second_result = gui.discover_mcp_tools()

    assert first_result == second_result
    assert first_result == [("lanhu_get_pages", "获取页面")]
    assert calls == [source_path]


def test_discover_mcp_tools_refresh_rescans_sources(monkeypatch: "MonkeyPatch", tmp_path: Path) -> None:
    """强制刷新时应重新扫描源码，用于打包或热更新后的工具列表更新。"""
    source_path = tmp_path / "server.py"
    source_path.write_text("placeholder", encoding="utf-8")
    calls: list[Path] = []

    monkeypatch.setattr(tools_registry, "tool_source_candidates", lambda: [source_path])

    def fake_scan(path: Path) -> list[tuple[str, str]]:
        """每次扫描都返回同一个工具，同时记录调用次数。"""
        calls.append(path)
        return [("lanhu_get_designs", "获取设计图")]

    monkeypatch.setattr(tools_registry, "scan_mcp_tools_from_file", fake_scan)

    assert gui.discover_mcp_tools(refresh=True) == [("lanhu_get_designs", "获取设计图")]
    assert gui.discover_mcp_tools(refresh=True) == [("lanhu_get_designs", "获取设计图")]
    assert calls == [source_path, source_path]


def test_merge_project_lists_deduplicates_same_team_and_project_across_routes() -> None:
    """同一 tid/pid 即使来自不同路由，也应在项目页只显示一条。"""
    projects = [
        {
            "id": "pid-1",
            "team_id": "tid-1",
            "name": "旧名称",
            "url": "https://lanhuapp.com/web/#/item/project/stage?tid=tid-1&pid=pid-1",
            "source": "登录缓存",
        },
        {
            "id": "pid-1",
            "team_id": "tid-1",
            "name": "新名称",
            "url": "https://lanhuapp.com/web/#/item/project/product?tid=tid-1&pid=pid-1",
            "updated_at": "2026-06-22 10:00:00",
            "source": "蓝湖接口",
        },
    ]

    merged_projects = gui.merge_project_lists(projects)

    assert len(merged_projects) == 1
    assert merged_projects[0]["id"] == "pid-1"
    assert merged_projects[0]["team_id"] == "tid-1"
    assert merged_projects[0]["name"] == "新名称"
    assert merged_projects[0]["updated_at"] == "2026-06-22 10:00:00"


def test_download_avatar_skips_response_larger_than_limit(monkeypatch: "MonkeyPatch", tmp_path: Path) -> None:
    """头像响应超过限制时应跳过读取，避免占用内存并写入半截图片。"""
    account = {"id": "account-1", "avatar": "https://example.test/avatar.png"}

    class TooLargeResponse:
        """模拟服务端声明超大头像响应。"""

        headers = {"Content-Length": str(gui.AVATAR_MAX_BYTES + 1)}

        def __enter__(self) -> "TooLargeResponse":
            """进入响应上下文。"""
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
            """退出响应上下文。"""
            return False

        def read(self, size: int) -> bytes:
            """大文件不应被读取。"""
            raise AssertionError("oversized avatar should not be read")

    monkeypatch.setattr(avatar_core, "AVATAR_CACHE_DIR", tmp_path)
    monkeypatch.setattr(gui.urllib.request, "urlopen", lambda request, timeout=0: TooLargeResponse())

    assert gui.download_avatar(account) is None
    assert not gui.avatar_cache_path(account).exists()


def test_sidebar_pulse_animation_uses_low_cost_interval() -> None:
    """侧栏呼吸条应使用更低频率的刷新节奏，降低持续 CPU/GDI 开销。"""
    assert gui.animation_interval_ms("sidebar_pulse") == 180


def test_sidebar_pulse_pauses_when_window_is_not_active() -> None:
    """窗口失焦或最小化时应暂停非必要动画。"""
    assert gui.should_run_sidebar_pulse("normal", True) is True
    assert gui.should_run_sidebar_pulse("normal", False) is False
    assert gui.should_run_sidebar_pulse("iconic", True) is False
    assert gui.should_run_sidebar_pulse("withdrawn", True) is False


def test_project_rows_signature_ignores_raw_payload_noise() -> None:
    """项目列表摘要应忽略 raw 等噪声字段，避免无意义重渲染。"""
    first_signature = gui.project_rows_signature([
        {
            "id": "pid-1",
            "team_id": "tid-1",
            "name": "蓝湖项目",
            "url": "https://lanhuapp.com/web/#/item/project/stage?tid=tid-1&pid=pid-1",
            "raw": {"counter": 1},
        }
    ])
    second_signature = gui.project_rows_signature([
        {
            "id": "pid-1",
            "team_id": "tid-1",
            "name": "蓝湖项目",
            "url": "https://lanhuapp.com/web/#/item/project/stage?tid=tid-1&pid=pid-1",
            "raw": {"counter": 2},
        }
    ])

    assert first_signature == second_signature


def test_project_rows_signature_changes_for_visible_project_updates() -> None:
    """项目可见字段变化时摘要应变化，保证界面仍会刷新。"""
    old_signature = gui.project_rows_signature([
        {"id": "pid-1", "team_id": "tid-1", "name": "旧名称"}
    ])
    new_signature = gui.project_rows_signature([
        {"id": "pid-1", "team_id": "tid-1", "name": "新名称"}
    ])

    assert old_signature != new_signature


def test_account_rows_signature_uses_visible_account_fields() -> None:
    """账号列表摘要只跟界面可见字段和当前账号状态相关。"""
    accounts = [
        {
            "id": "account-1",
            "name": "蓝湖用户",
            "email": "user@example.test",
            "cookie": "token=secret",
            "raw": {"volatile": 1},
        }
    ]
    first_signature = gui.account_rows_signature(accounts, "account-1")
    accounts[0]["raw"] = {"volatile": 2}
    second_signature = gui.account_rows_signature(accounts, "account-1")
    inactive_signature = gui.account_rows_signature(accounts, "")

    assert first_signature == second_signature
    assert first_signature != inactive_signature
